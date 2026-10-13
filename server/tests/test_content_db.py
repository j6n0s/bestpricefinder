"""Content load into PostgreSQL as bpf_ingest: one transaction, idempotent, deletions, ingest_run, DB prices.

Runs against a throwaway cluster of its own (``pg_factory``), because loading commits data.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import shutil
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest

from bpf.content.__main__ import main
from bpf.content.coverage import db_prices
from bpf.content.ingredients import IngredientRecord
from bpf.content.leaves import FOOD_TOP_CATEGORIES, food_leaves_from_db
from bpf.content.load import load_content
from bpf.content.paths import LEAF_CATEGORIES_CSV, ContentPaths
from bpf.content.writer import fail_run, start_run, write_content
from bpf.db import connect
from tests.pgcluster import PgCluster

pytestmark = pytest.mark.db

FIXTURES = Path(__file__).parent / "fixtures" / "content"


@pytest.fixture(scope="module")
def cluster(pg_factory: Callable[..., PgCluster]) -> PgCluster:
    return pg_factory()


@pytest.fixture
def clean(cluster: PgCluster) -> PgCluster:
    """Empty content, price and run tables before each test (TRUNCATE bypasses the row triggers)."""
    with cluster.connect("admin", autocommit=True) as conn:
        conn.execute(
            "TRUNCATE app.recipe_line, app.recipe, app.ingredient, app.ksh_price, app.nutrition, "
            "core.product_chain_day, core.store_price_day, core.product_availability, core.product, "
            "core.store, core.category, core.chain, ops.ingest_run CASCADE"
        )
    return cluster


def fixture_paths(root: Path) -> ContentPaths:
    shutil.copytree(FIXTURES / "recipes", root / "recipes")
    for name in ("ingredients.json", "ksh.csv", "reference_prices.csv"):
        shutil.copy(FIXTURES / name, root / name)
    return ContentPaths(
        ingredients=root / "ingredients.json",
        recipes_dir=root / "recipes",
        ksh=root / "ksh.csv",
        nutrition=root / "nutrition.json",
        reference_prices=root / "reference_prices.csv",
    )


def rows(cluster: PgCluster, sql: str, *params: object) -> list[tuple[Any, ...]]:
    with cluster.connect("admin") as conn:
        return conn.execute(sql, params).fetchall()


def runs(cluster: PgCluster) -> list[tuple[Any, ...]]:
    return rows(cluster, "SELECT id, kind, status, stats, warnings, error FROM ops.ingest_run ORDER BY id")


def edit_json(path: Path, change: Callable[[dict[str, Any]], None]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_load_twice_is_idempotent_and_removed_content_is_deleted(clean: PgCluster, tmp_path: Path) -> None:
    settings = clean.settings()
    paths = fixture_paths(tmp_path)

    assert main([], paths=paths, settings=settings) == 0
    assert rows(clean, "SELECT count(*) FROM app.ingredient") == [(10,)]
    assert rows(clean, "SELECT id FROM app.recipe ORDER BY id") == [
        ("csirke-gombaval",),
        ("lencse-tojassal",),
        ("sult-lazac",),
    ]
    assert rows(clean, "SELECT count(*) FROM app.recipe_line") == [(14,)]
    first = runs(clean)
    assert [(r[1], r[2]) for r in first] == [("content", "ok")]
    assert first[0][3]["ingredients_inserted"] == 10
    assert first[0][3]["recipes_inserted"] == 3
    assert first[0][3]["ksh_inserted"] == 2
    stamps = dict(rows(clean, "SELECT id, updated_at FROM app.recipe"))

    # the same files again: nothing changes
    assert main([], paths=paths, settings=settings) == 0
    second = runs(clean)[-1]
    assert second[2] == "ok"
    stats = second[3]
    assert stats["ingredients_unchanged"] == 10
    assert stats["ingredients_inserted"] == stats["ingredients_updated"] == 0
    assert stats["recipes_unchanged"] == 3
    assert stats["recipes_inserted"] == stats["recipes_updated"] == 0
    assert stats["recipes_deleted"] == stats["ingredients_deleted"] == stats["ksh_deleted"] == 0
    assert stats["ksh_unchanged"] == 2
    assert dict(rows(clean, "SELECT id, updated_at FROM app.recipe")) == stamps
    assert second[4] == []

    # remove one recipe, change another
    edit_json(paths.recipes_dir / "b.json", lambda d: d.update(recipes=[]))
    edit_json(paths.recipes_dir / "a.json", lambda d: d["recipes"][1]["lines"][0].update(qty=0.5))
    assert main([], paths=paths, settings=settings) == 0
    assert rows(clean, "SELECT id FROM app.recipe ORDER BY id") == [
        ("csirke-gombaval",),
        ("lencse-tojassal",),
    ]
    assert rows(clean, "SELECT count(*) FROM app.recipe_line WHERE recipe_id = 'sult-lazac'") == [(0,)]
    assert rows(
        clean, "SELECT qty FROM app.recipe_line WHERE recipe_id = 'lencse-tojassal' AND line_no = 1"
    ) == [(Decimal("0.500"),)]
    now = dict(rows(clean, "SELECT id, updated_at FROM app.recipe"))
    assert now["csirke-gombaval"] == stamps["csirke-gombaval"]
    assert now["lencse-tojassal"] > stamps["lencse-tojassal"]
    third = runs(clean)[-1]
    assert third[3]["recipes_deleted"] == 1
    assert third[3]["recipes_updated"] == 1
    assert third[4] == ["recipes deleted (no longer in data/recipes): sult-lazac"]

    # remove the ingredients only that recipe used
    edit_json(
        paths.ingredients,
        lambda d: d.update(ingredients=[i for i in d["ingredients"] if i["id"] not in ("kapor", "lazac")]),
    )
    assert main([], paths=paths, settings=settings) == 0
    assert rows(clean, "SELECT count(*) FROM app.ingredient") == [(8,)]
    fourth = runs(clean)[-1]
    assert fourth[3]["ingredients_deleted"] == 2
    assert fourth[4] == ["ingredients deleted (no longer in data/ingredients.json): kapor, lazac"]


def _write_ksh(path: Path, egg_period: str, egg_price: int, *, with_mushrooms: bool = True) -> None:
    lines = [
        "code,name,unit,unit_qty,price,period",
        f'11001,"Tojás, 10 darab",db,10,{egg_price},{egg_period}',
    ]
    if with_mushrooms:
        lines.append('14111,"Gomba, kg",kg,1,2000,2026-09-01')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ksh_rows(cluster: PgCluster) -> list[tuple[Any, ...]]:
    return rows(cluster, "SELECT code, period, price FROM app.ksh_price ORDER BY code, period")


def test_ksh_history_nutrition_and_ingredient_updates(clean: PgCluster, tmp_path: Path) -> None:
    settings = clean.settings()
    paths = fixture_paths(tmp_path)
    # SYNTHETIC composition row (made-up round numbers), linked from one ingredient
    synthetic = {"code": "T1", "source": "ciqual", "name": "SYNTHETIC test row", "kcal": 100, "protein_g": 10}
    for key in ("carb_g", "sugar_g", "fat_g", "satfat_g", "fiber_g", "salt_g"):
        synthetic[key] = None
    paths.nutrition.write_text(json.dumps({"version": 1, "rows": [synthetic]}), encoding="utf-8")
    edit_json(paths.ingredients, lambda d: d["ingredients"][4].update(nutrition_code="T1"))  # lencse
    assert main([], paths=paths, settings=settings) == 0
    assert rows(clean, "SELECT code, source, kcal, carb_g FROM app.nutrition") == [
        ("T1", "ciqual", Decimal("100.00"), None)
    ]
    assert rows(clean, "SELECT nutrition_code FROM app.ingredient WHERE id = 'lencse'") == [("T1",)]
    assert runs(clean)[-1][3]["nutrition_inserted"] == 1
    assert ksh_rows(clean) == [
        ("11001", date(2026, 9, 1), Decimal("80.00")),
        ("14111", date(2026, 9, 1), Decimal("2000.00")),
    ]

    # a new month for eggs: inserted; the September row stays as history; ksh_latest shows October
    _write_ksh(paths.ksh, "2026-10-01", 900)
    edit_json(paths.ingredients, lambda d: d["ingredients"][4].update(name_hu="lencse (száraz)"))
    assert main([], paths=paths, settings=settings) == 0
    stats = runs(clean)[-1][3]
    assert (stats["ksh_inserted"], stats["ksh_unchanged"], stats["ksh_deleted"]) == (1, 1, 0)
    assert (stats["ingredients_updated"], stats["ingredients_unchanged"]) == (1, 9)
    assert stats["nutrition_unchanged"] == 1
    assert ksh_rows(clean) == [
        ("11001", date(2026, 9, 1), Decimal("80.00")),
        ("11001", date(2026, 10, 1), Decimal("90.00")),
        ("14111", date(2026, 9, 1), Decimal("2000.00")),
    ]
    with clean.connect("api") as conn:
        assert conn.execute("SELECT period, price FROM api.ksh_latest WHERE code = '11001'").fetchone() == (
            date(2026, 10, 1),
            Decimal("90.00"),
        )

    # reloading the older file: the later row of that code would shadow it, so it is deleted
    _write_ksh(paths.ksh, "2026-09-01", 800)
    assert main([], paths=paths, settings=settings) == 0
    assert runs(clean)[-1][3]["ksh_deleted"] == 1
    assert ksh_rows(clean) == [
        ("11001", date(2026, 9, 1), Decimal("80.00")),
        ("14111", date(2026, 9, 1), Decimal("2000.00")),
    ]

    # a code no longer in the file (and no longer referenced) stays as history
    _write_ksh(paths.ksh, "2026-09-01", 800, with_mushrooms=False)
    edit_json(paths.ingredients, lambda d: d["ingredients"][1].update(ksh_code=None))  # gomba
    assert main(["--allow-low-coverage"], paths=paths, settings=settings) == 0  # gomba is now unpriced
    assert ksh_rows(clean)[-1] == ("14111", date(2026, 9, 1), Decimal("2000.00"))
    assert runs(clean)[-1][3]["ksh_deleted"] == 0


def test_loaded_rows_and_api_views(clean: PgCluster, tmp_path: Path) -> None:
    assert main([], paths=fixture_paths(tmp_path), settings=clean.settings()) == 0
    with clean.connect("api") as conn:
        egg = conn.execute(
            "SELECT unit, piece_weight_kg, pantry, leaf_ids, product_units, ksh_code, tags, perishable_days "
            "FROM api.ingredient WHERE id = 'tojas'"
        ).fetchone()
        assert egg == ("db", Decimal("0.0550"), False, [14], ["db"], "11001", ["egg"], 21)
        # KSH: the table has no unit_qty, so the price is stored per ONE unit (800 Ft / 10 db)
        assert conn.execute(
            "SELECT unit, price, period FROM api.ksh_latest WHERE code = '11001'"
        ).fetchone() == ("db", Decimal("80.00"), date(2026, 9, 1))
        recipe = conn.execute(
            "SELECT title, slots, servings, minutes, tags, tested FROM api.recipe "
            "WHERE id = 'csirke-gombaval'"
        ).fetchone()
        assert recipe == (
            "Serpenyős csirke gombával",
            ["ebed", "vacsora"],
            2,
            30,
            ["foetel", "baromfi"],
            False,
        )
        lines = conn.execute(
            "SELECT line_no, ingredient_id, qty, optional FROM api.recipe_line "
            "WHERE recipe_id = 'sult-lazac' "
            "ORDER BY line_no"
        ).fetchall()
        assert lines[-1] == (4, "kapor", Decimal("0.010"), True)
    notes = rows(clean, "SELECT notes FROM app.ingredient WHERE id = 'csirkemell'")
    assert notes == [("Synthetic test fixture.",)]
    assert rows(clean, "SELECT source FROM app.recipe GROUP BY source") == [("original",)]


def test_a_database_error_rolls_everything_back_and_marks_the_run_failed(
    clean: PgCluster, tmp_path: Path
) -> None:
    content = load_content(fixture_paths(tmp_path))
    first = next(iter(content.ingredients.values()))
    broken = IngredientRecord(dataclasses.replace(first.ingredient, list_group="Not-A-Group"), first.notes)
    bad = dataclasses.replace(content, ingredients={**content.ingredients, first.ingredient.id: broken})
    with connect("ingest", settings=clean.settings(), autocommit=True) as conn:
        run_id = start_run(conn)
        with pytest.raises(psycopg.errors.CheckViolation):
            write_content(conn, bad, run_id=run_id, warnings=[])
        fail_run(conn, run_id, "CheckViolation: test")
    assert rows(clean, "SELECT count(*) FROM app.ingredient") == [(0,)]  # nothing of the transaction survived
    assert rows(clean, "SELECT count(*) FROM app.ksh_price") == [(0,)]
    [run] = runs(clean)
    assert run[2] == "failed"
    assert run[5] == "CheckViolation: test"
    assert rows(clean, "SELECT finished_at IS NOT NULL FROM ops.ingest_run") == [(True,)]


def test_ingest_role_has_the_privileges_the_loader_needs(clean: PgCluster) -> None:
    """The loader needs what migration 0001 grants bpf_ingest (DELETE on app tables, an advisory lock)."""
    with clean.connect("ingest") as conn, conn.transaction(force_rollback=True):
        conn.execute("DELETE FROM app.recipe")
        conn.execute("DELETE FROM app.ingredient")
        conn.execute("DELETE FROM app.ksh_price")
        conn.execute("SELECT pg_advisory_xact_lock(1)")


def _insert_prices(conn: psycopg.Connection, *, leaves: list[tuple[int, str]]) -> None:
    conn.execute(
        "INSERT INTO core.chain (id, name, slug, is_grocery) VALUES "
        "('c-aldi', 'Aldi', 'aldi', true), ('c-lidl', 'Lidl', 'lidl', true), ('c-dm', 'dm', 'dm', false)"
    )
    for leaf_id, name in leaves:
        conn.execute(
            "INSERT INTO core.category (id, parent_id, name, path, level, is_leaf, is_food) "
            "VALUES (%s, NULL, %s, %s, 3, true, true)",
            (leaf_id, name, f"x/{leaf_id}"),
        )
    conn.execute(
        "INSERT INTO core.category (id, parent_id, name, path, level, is_leaf, is_food) "
        "VALUES (126, NULL, 'Toalettpapír', 'h/126', 3, true, false), "
        "(2017, NULL, 'Szárnyasok', 'h', 2, false, true)"
    )
    conn.execute(
        "INSERT INTO core.product "
        "(id, name, category_id, unit, unit_title, packaging, first_seen, last_seen) VALUES "
        "('p1', 'Friss csirkemellfilé', 18, 'kg', 'kg', NULL, CURRENT_DATE, CURRENT_DATE), "
        "('p2', 'Csirkemell tokány, kg', 18, 'kg', 'kg', NULL, CURRENT_DATE, CURRENT_DATE), "
        "('p3', 'Csirkemellfilé 500 g', 18, 'kg', 'csomag', 0.5, CURRENT_DATE, CURRENT_DATE)"
    )
    conn.execute(
        "INSERT INTO core.product_chain_day "
        "(data_date, product_id, chain_id, product_min_amount, xlsx_min, xlsx_max) "
        "VALUES (CURRENT_DATE, 'p1', 'c-aldi', 300, NULL, NULL), "
        "(CURRENT_DATE, 'p3', 'c-lidl', NULL, 200, 200), "
        "(CURRENT_DATE, 'p2', 'c-aldi', 10, NULL, NULL), (CURRENT_DATE, 'p1', 'c-dm', 1, NULL, NULL)"
    )
    conn.execute(
        "INSERT INTO ops.ingest_run (kind, status, data_date, finished_at) "
        "VALUES ('daily', 'ok', CURRENT_DATE, now())"
    )


def test_db_prices_and_leaves_from_the_database(clean: PgCluster, tmp_path: Path) -> None:
    content = load_content(fixture_paths(tmp_path))
    ingredients = list(content.ingredient_map().values())
    with clean.connect("ingest") as conn, conn.transaction(force_rollback=True):
        assert db_prices(conn, ingredients) == (None, {})  # no daily run yet
        assert food_leaves_from_db(conn) is None  # no categories yet
        _insert_prices(conn, leaves=[(18, "Csirkemellfilé")])
        today = conn.execute("SELECT CURRENT_DATE").fetchone()[0]  # type: ignore[index]
        data_date, prices = db_prices(conn, ingredients)
        assert data_date == today
        # Aldi 300 Ft/kg (loose), Lidl 200 Ft / 0.5 kg = 400 Ft/kg (XLSX min == max); tokány and dm ignored
        assert prices == {"csirkemell": Decimal(350)}
        leaves = food_leaves_from_db(conn)
        assert leaves is not None
        assert (leaves.names, leaves.source) == ({18: "Csirkemellfilé"}, "core.category")


def test_coverage_report_and_load_use_db_prices_and_db_leaves(
    clean: PgCluster, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with LEAF_CATEGORIES_CSV.open(encoding="utf-8", newline="") as fh:
        food = [(int(r["leaf_id"]), r["leaf"]) for r in csv.DictReader(fh) if r["top"] in FOOD_TOP_CATEGORIES]
    with clean.connect("ingest") as conn, conn.transaction():
        _insert_prices(conn, leaves=food)
    settings = clean.settings()
    paths = fixture_paths(tmp_path)
    # chicken now costs 350 Ft/kg: csirke-gombaval = 175 + 20 GVH vs 100 KSH -> 66 % < 90 %
    assert main(["--coverage-report"], paths=paths, settings=settings) == 1
    out = capsys.readouterr().out
    assert "Prices: DB chain prices of" in out
    assert "(leaves: core.category)" in out
    assert "FAIL csirke-gombaval: 66.1% < 90.0%" in out
    assert rows(clean, "SELECT count(*) FROM ops.ingest_run WHERE kind = 'content'") == [
        (0,)
    ]  # report never writes
    assert main([], paths=paths, settings=settings) == 1  # the load is blocked too
    assert rows(clean, "SELECT count(*) FROM app.recipe") == [(0,)]
    assert main(["--allow-low-coverage"], paths=paths, settings=settings) == 0
    [run] = rows(clean, "SELECT status, warnings FROM ops.ingest_run WHERE kind = 'content'")
    assert run == (
        "ok",
        ["recipe below the coverage rule, loaded with --allow-low-coverage: csirke-gombaval"],
    )

    # a leaf the DB does not list as a food leaf is rejected (the DB list wins over the research list)
    edit_json(paths.ingredients, lambda d: d["ingredients"][0].update(leaf_ids=[126]))
    assert main(["--dry-run"], paths=paths) == 1  # research list: 126 is not food either
    capsys.readouterr()
    assert main([], paths=paths, settings=settings) == 1
    assert "126 is not a GVH food leaf (checked against core.category)" in capsys.readouterr().err
