"""The GVH food leaf categories that ``Ingredient.leaf_ids`` may reference (docs/DATA.md).

Source, in order of preference: ``core.category`` (``is_leaf AND is_food``) when the database has categories,
otherwise the research leaf list of 2026-10-12
(``research/gap-gvh-promo-and-stability/data/leaf_categories.csv``), where a leaf is food when its top
category is one of the six food top categories of BUILD-BRIEF §4.1.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import psycopg

from bpf.content.errors import ContentError
from bpf.content.jsonio import display_path

FOOD_TOP_CATEGORIES: frozenset[str] = frozenset(
    {
        "Tejtermék, sajt, tojás",
        "Hús, hal, felvágott",
        "Zöldség, gyümölcs",
        "Pékáru",
        "Tartós élelmiszerek, italok",
        "Speciális étrend",
    }
)
_LEAF_CSV_COLUMNS = ("leaf_id", "leaf", "l2_id", "l2", "top_id", "top")


@dataclass(frozen=True, slots=True)
class FoodLeaves:
    """Food leaf id -> leaf name, and where the list came from (for messages)."""

    names: dict[int, str]
    source: str

    def __contains__(self, leaf_id: object) -> bool:
        return leaf_id in self.names


def food_leaves_from_csv(path: Path) -> FoodLeaves:
    """Food leaves of the research leaf list. Raises :class:`ContentError` when the file is unusable."""
    where = display_path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContentError([f"{where}: cannot read the leaf list: {exc}"]) from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != _LEAF_CSV_COLUMNS:
        raise ContentError([f"{where}: expected columns {','.join(_LEAF_CSV_COLUMNS)}"])
    names: dict[int, str] = {}
    for row in reader:
        if row["top"] in FOOD_TOP_CATEGORIES:
            names[int(row["leaf_id"])] = row["leaf"]
    if not names:
        raise ContentError([f"{where}: no food leaves found"])
    return FoodLeaves(names, where)


def food_leaves_from_db(conn: psycopg.Connection) -> FoodLeaves | None:
    """Food leaves from ``core.category``; None when the table is still empty (no reference ingest yet)."""
    rows = conn.execute("SELECT id, name, is_leaf, is_food FROM core.category").fetchall()
    if not rows:
        return None
    names = {int(cid): str(name) for cid, name, is_leaf, is_food in rows if is_leaf and is_food}
    return FoodLeaves(names, "core.category")
