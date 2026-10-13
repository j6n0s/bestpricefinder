"""Write validated content to PostgreSQL as ``bpf_ingest``, in ONE transaction, and record the run.

* ``app.nutrition``: upsert (rows are never deleted; ingredients may still reference them).
* ``app.ingredient``: upsert; ingredients that are no longer in the file are deleted after the recipes
  (the files are the source of truth; ids are meant to be stable, so a deletion is reported as a warning).
* ``app.recipe`` + ``app.recipe_line``: a recipe whose row or lines changed is rewritten (lines replaced,
  ``updated_at`` bumped); unchanged recipes are not touched; recipes absent from the files are deleted
  (their lines go with them, ``ON DELETE CASCADE``).
* ``app.ksh_price``: upsert per (period, code) with the price per ONE unit (``price / unit_qty``; the table
  has no ``unit_qty`` column, see :mod:`bpf.content.ksh`). For every code in the file, rows of a LATER
  period are deleted, so that ``api.ksh_latest`` returns exactly the file's row (e.g. after reloading an
  older file). Rows of earlier periods are kept as history, and so are rows of codes no longer in the file
  (no ingredient can reference those: ``ksh_code`` is checked against the file).
* ``ops.ingest_run``: a ``content`` row is committed as ``running`` first, set to ``ok`` (with stats and
  warnings) inside the content transaction, or to ``failed`` (with the error) after a rollback.

A transaction-level advisory lock serialises concurrent content loads. Loading the same files twice changes
nothing the second time (idempotent).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from bpf.content.ingredients import IngredientRecord
from bpf.content.ksh import price_per_unit
from bpf.content.load import Content
from bpf.pricing.model import KshPrice, NutritionRow, Recipe

#: pg_advisory_xact_lock key: the ASCII bytes of "bpf-cont" as a big-endian bigint.
CONTENT_LOCK_KEY = int.from_bytes(b"bpf-cont", "big")
MAX_ERROR_LENGTH = 2000

_INGREDIENT_COLUMNS = (
    "name_hu",
    "list_group",
    "unit",
    "piece_weight_kg",
    "pantry",
    "leaf_ids",
    "include_patterns",
    "exclude_patterns",
    "product_units",
    "ksh_code",
    "nutrition_code",
    "notes",
    "tags",
    "perishable_days",
    "density_kg_per_l",
)
_CASTS = {
    "leaf_ids": "::integer[]",
    "include_patterns": "::text[]",
    "exclude_patterns": "::text[]",
    "product_units": "::text[]",
    "tags": "::text[]",
}


def _upsert_sql(table: str, key: tuple[str, ...], columns: tuple[str, ...], casts: Mapping[str, str]) -> str:
    """INSERT … ON CONFLICT DO UPDATE only when a value differs; RETURNING whether the row was inserted."""
    all_columns = (*key, *columns)
    values = ", ".join(f"%({c})s{casts.get(c, '')}" for c in all_columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns)
    current = ", ".join(f"{table}.{c}" for c in columns)
    excluded = ", ".join(f"EXCLUDED.{c}" for c in columns)
    return (
        # Only constant identifiers from this module are interpolated; values are bound parameters.
        f"INSERT INTO {table} ({', '.join(all_columns)}) VALUES ({values}) "  # noqa: S608
        f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {updates} "
        f"WHERE ({current}) IS DISTINCT FROM ({excluded}) "
        "RETURNING (xmax = 0) AS inserted"
    )


_INGREDIENT_UPSERT = _upsert_sql("app.ingredient", ("id",), _INGREDIENT_COLUMNS, _CASTS)
_NUTRITION_COLUMNS = (
    "source",
    "name",
    "kcal",
    "protein_g",
    "carb_g",
    "sugar_g",
    "fat_g",
    "satfat_g",
    "fiber_g",
    "salt_g",
)
_NUTRITION_UPSERT = _upsert_sql("app.nutrition", ("code",), _NUTRITION_COLUMNS, {})
_KSH_UPSERT = _upsert_sql("app.ksh_price", ("period", "code"), ("name", "unit", "price"), {})


def _count(cur: psycopg.Cursor[Any], stats: dict[str, int], prefix: str) -> None:
    row = cur.fetchone()
    if row is None:
        stats[f"{prefix}_unchanged"] += 1
    elif row[0]:
        stats[f"{prefix}_inserted"] += 1
    else:
        stats[f"{prefix}_updated"] += 1


def _new_stats(prefix: str) -> dict[str, int]:
    return {f"{prefix}_inserted": 0, f"{prefix}_updated": 0, f"{prefix}_unchanged": 0}


def upsert_nutrition(conn: psycopg.Connection, rows: Iterable[NutritionRow]) -> dict[str, int]:
    stats = _new_stats("nutrition")
    with conn.cursor() as cur:
        for row in rows:
            params = {"code": row.code, **{c: getattr(row, c) for c in _NUTRITION_COLUMNS}}
            cur.execute(_NUTRITION_UPSERT, params)
            _count(cur, stats, "nutrition")
    return stats


def upsert_ingredients(conn: psycopg.Connection, records: Iterable[IngredientRecord]) -> dict[str, int]:
    stats = _new_stats("ingredients")
    with conn.cursor() as cur:
        for record in records:
            ing = record.ingredient
            params: dict[str, Any] = {
                "id": ing.id,
                "name_hu": ing.name_hu,
                "list_group": ing.list_group,
                "unit": ing.unit,
                "piece_weight_kg": ing.piece_weight_kg,
                "pantry": ing.pantry,
                "leaf_ids": list(ing.leaf_ids),
                "include_patterns": list(ing.include_patterns),
                "exclude_patterns": list(ing.exclude_patterns),
                "product_units": list(ing.product_units),
                "ksh_code": ing.ksh_code,
                "nutrition_code": ing.nutrition_code,
                "notes": record.notes,
                "tags": list(ing.tags),
                "perishable_days": ing.perishable_days,
                "density_kg_per_l": ing.density_kg_per_l,
            }
            cur.execute(_INGREDIENT_UPSERT, params)
            _count(cur, stats, "ingredients")
    return stats


def delete_absent_ingredients(conn: psycopg.Connection, keep: Iterable[str]) -> list[str]:
    """Delete ingredients that are not in the file; returns their ids (sorted)."""
    rows = conn.execute(
        "DELETE FROM app.ingredient WHERE NOT (id = ANY(%s::text[])) RETURNING id", (sorted(keep),)
    ).fetchall()
    return sorted(str(r[0]) for r in rows)


def _recipe_key(recipe: Recipe) -> tuple[object, ...]:
    lines = [(ln.line_no, ln.ingredient_id, ln.qty, ln.display, ln.optional) for ln in recipe.lines]
    return (
        recipe.title,
        recipe.summary,
        list(recipe.slots),
        recipe.servings,
        recipe.minutes,
        list(recipe.tags),
        list(recipe.steps),
        recipe.tested,
        lines,
    )


def _existing_recipes(conn: psycopg.Connection) -> dict[str, tuple[object, ...]]:
    lines: dict[str, list[tuple[object, ...]]] = {}
    for recipe_id, line_no, ingredient_id, qty, display, optional in conn.execute(
        "SELECT recipe_id, line_no, ingredient_id, qty, display, optional FROM app.recipe_line "
        "ORDER BY recipe_id, line_no"
    ):
        lines.setdefault(recipe_id, []).append((line_no, ingredient_id, qty, display, optional))
    existing: dict[str, tuple[object, ...]] = {}
    for rid, title, summary, slots, servings, minutes, tags, steps, tested in conn.execute(
        "SELECT id, title, summary, slots, servings, minutes, tags, steps, tested FROM app.recipe"
    ):
        existing[rid] = (title, summary, slots, servings, minutes, tags, steps, tested, lines.get(rid, []))
    return existing


_RECIPE_INSERT = (
    "INSERT INTO app.recipe (id, title, summary, slots, servings, minutes, tags, steps, tested) "
    "VALUES (%(id)s, %(title)s, %(summary)s, %(slots)s::text[], %(servings)s, %(minutes)s, %(tags)s::text[], "
    "%(steps)s::text[], %(tested)s)"
)
_RECIPE_UPDATE = (
    "UPDATE app.recipe SET title = %(title)s, summary = %(summary)s, slots = %(slots)s::text[], "
    "servings = %(servings)s, minutes = %(minutes)s, tags = %(tags)s::text[], steps = %(steps)s::text[], "
    "tested = %(tested)s, updated_at = now() WHERE id = %(id)s"
)
_LINE_INSERT = (
    "INSERT INTO app.recipe_line (recipe_id, line_no, ingredient_id, qty, display, optional) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)


def _recipe_params(recipe: Recipe) -> dict[str, Any]:
    return {
        "id": recipe.id,
        "title": recipe.title,
        "summary": recipe.summary,
        "slots": list(recipe.slots),
        "servings": recipe.servings,
        "minutes": recipe.minutes,
        "tags": list(recipe.tags),
        "steps": list(recipe.steps),
        "tested": recipe.tested,
    }


def sync_recipes(conn: psycopg.Connection, recipes: Iterable[Recipe]) -> tuple[dict[str, int], list[str]]:
    """Make app.recipe/app.recipe_line equal to ``recipes``. Returns stats and the deleted recipe ids."""
    existing = _existing_recipes(conn)
    stats = _new_stats("recipes")
    wanted: set[str] = set()
    with conn.cursor() as cur:
        for recipe in recipes:
            wanted.add(recipe.id)
            old = existing.get(recipe.id)
            if old is not None and old == _recipe_key(recipe):
                stats["recipes_unchanged"] += 1
                continue
            if old is None:
                cur.execute(_RECIPE_INSERT, _recipe_params(recipe))
                stats["recipes_inserted"] += 1
            else:
                cur.execute(_RECIPE_UPDATE, _recipe_params(recipe))
                cur.execute("DELETE FROM app.recipe_line WHERE recipe_id = %s", (recipe.id,))
                stats["recipes_updated"] += 1
            cur.executemany(
                _LINE_INSERT,
                [
                    (recipe.id, ln.line_no, ln.ingredient_id, ln.qty, ln.display, ln.optional)
                    for ln in recipe.lines
                ],
            )
        removed = sorted(set(existing) - wanted)
        if removed:
            cur.execute("DELETE FROM app.recipe WHERE id = ANY(%s::text[])", (removed,))
    stats["recipes_deleted"] = len(removed)
    return stats, removed


def sync_ksh(conn: psycopg.Connection, rows: Iterable[KshPrice]) -> dict[str, int]:
    """Upsert the file's rows and delete later-period rows of the same codes (see the module docstring)."""
    stats = _new_stats("ksh")
    periods: list[object] = []
    codes: list[str] = []
    with conn.cursor() as cur:
        for row in rows:
            params = {
                "period": row.period,
                "code": row.code,
                "name": row.name,
                "unit": row.unit,
                "price": price_per_unit(row),
            }
            cur.execute(_KSH_UPSERT, params)
            _count(cur, stats, "ksh")
            periods.append(row.period)
            codes.append(row.code)
        cur.execute(
            "DELETE FROM app.ksh_price p "
            "USING unnest(%(codes)s::text[], %(periods)s::date[]) AS f(code, period) "
            "WHERE p.code = f.code AND p.period > f.period",
            {"periods": periods, "codes": codes},
        )
        stats["ksh_deleted"] = cur.rowcount
    return stats


def start_run(conn: psycopg.Connection) -> int:
    """Commit an ``ops.ingest_run`` row (kind content, status running); returns its id."""
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO ops.ingest_run (kind, status) VALUES ('content', 'running') RETURNING id"
        ).fetchone()
    if row is None:  # pragma: no cover - INSERT … RETURNING always returns the row
        raise RuntimeError("ops.ingest_run insert returned no id")
    return int(row[0])


def fail_run(conn: psycopg.Connection, run_id: int, error: str) -> None:
    """Mark the run failed (in its own transaction, after the content transaction rolled back)."""
    with conn.transaction():
        conn.execute(
            "UPDATE ops.ingest_run SET status = 'failed', finished_at = now(), error = %s WHERE id = %s",
            (error[:MAX_ERROR_LENGTH], run_id),
        )


def write_content(
    conn: psycopg.Connection, content: Content, *, run_id: int, warnings: list[str]
) -> dict[str, int]:
    """Write everything in one transaction and mark the run ``ok`` in it. Returns the stats.

    Raises on any database error; the transaction is then rolled back and nothing is written."""
    stats: dict[str, int] = {}
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (CONTENT_LOCK_KEY,))
        stats |= upsert_nutrition(conn, content.nutrition.values())
        stats |= upsert_ingredients(conn, content.ingredients.values())
        recipe_stats, removed = sync_recipes(conn, content.recipes.values())
        stats |= recipe_stats
        deleted_ingredients = delete_absent_ingredients(conn, content.ingredients.keys())
        stats["ingredients_deleted"] = len(deleted_ingredients)
        stats |= sync_ksh(conn, content.ksh.values())
        run_warnings = list(warnings)
        if removed:
            run_warnings.append(f"recipes deleted (no longer in data/recipes): {', '.join(removed)}")
        if deleted_ingredients:
            run_warnings.append(
                f"ingredients deleted (no longer in data/ingredients.json): {', '.join(deleted_ingredients)}"
            )
        conn.execute(
            "UPDATE ops.ingest_run SET status = 'ok', finished_at = now(), stats = %s, warnings = %s "
            "WHERE id = %s",
            (Jsonb(stats), Jsonb(run_warnings), run_id),
        )
    return stats
