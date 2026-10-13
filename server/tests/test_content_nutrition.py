"""data/nutrition/nutrition.json (optional): parsing, validation and the ingredients' nutrition_code check.

Every value below is SYNTHETIC (round made-up numbers written for the tests), never composition data.
"""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bpf.content.errors import ContentError, Problems
from bpf.content.load import load_content
from bpf.content.nutrition import ROW_KEYS, load_nutrition
from bpf.content.paths import ContentPaths
from bpf.pricing import NutritionRow

FIXTURES = Path(__file__).parent / "fixtures" / "content"


def row(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "code": "T1",
        "source": "ciqual",
        "name": "SYNTHETIC test row",
        "kcal": 100,
        "protein_g": 10,
        "carb_g": 1.5,
        "sugar_g": 0,
        "fat_g": 2.25,
        "satfat_g": None,
        "fiber_g": 0,
        "salt_g": 0.1,
    }
    item.update(overrides)
    return item


def write(tmp_path: Path, data: Any) -> Path:
    path = tmp_path / "nutrition.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def load(tmp_path: Path, data: Any) -> tuple[dict[str, NutritionRow], list[str]]:
    problems = Problems()
    rows = load_nutrition(write(tmp_path, data), problems)
    return rows, list(problems.items)


def test_missing_file_means_no_composition_data(tmp_path: Path) -> None:
    problems = Problems()
    assert load_nutrition(tmp_path / "absent.json", problems) == {}
    assert not problems


def test_good_file(tmp_path: Path) -> None:
    rows, problems = load(tmp_path, {"version": 1, "rows": [row(), row(code="T2", source="frida", kcal=0)]})
    assert problems == []
    assert list(rows) == ["T1", "T2"]
    first = rows["T1"]
    assert first == NutritionRow(
        code="T1",
        source="ciqual",
        name="SYNTHETIC test row",
        kcal=Decimal(100),
        protein_g=Decimal(10),
        carb_g=Decimal("1.5"),
        sugar_g=Decimal(0),
        fat_g=Decimal("2.25"),
        satfat_g=None,
        fiber_g=Decimal(0),
        salt_g=Decimal("0.1"),
    )
    assert all(isinstance(v, Decimal) for v in (first.carb_g, first.fat_g, first.salt_g))  # never float
    assert rows["T2"].source == "frida"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"code": ""}, "code: must be a string of 1-40"),
        ({"code": "x" * 41}, "code: must be a string of 1-40"),
        ({"code": " T1"}, "code: must be a string of 1-40"),
        ({"code": 5}, "code: must be a string of 1-40"),
        ({"source": "off"}, "source: must be one of ciqual, frida, usda"),  # no Open Food Facts
        ({"source": None}, "source: must be one of"),
        ({"name": ""}, "name: must be a string of 1-200"),
        ({"name": "x" * 201}, "name: must be a string of 1-200"),
        ({"kcal": -1}, "kcal: must be null or a number >= 0 with at most 2 decimals"),
        ({"fat_g": 1.234}, "fat_g: must be null or a number >= 0 with at most 2 decimals"),
        ({"salt_g": "0.1"}, "salt_g: must be null or a number"),
        ({"sugar_g": True}, "sugar_g: must be null or a number"),
        ({"protein_g": 1000000}, "protein_g: must be null or a number"),
    ],
)
def test_bad_rows(tmp_path: Path, overrides: dict[str, Any], expected: str) -> None:
    rows, problems = load(tmp_path, {"version": 1, "rows": [row(**overrides)]})
    assert rows == {}
    assert any(expected in p for p in problems), problems


def test_bad_structure(tmp_path: Path) -> None:
    _, problems = load(tmp_path, {"version": 1, "rows": [row(), row()]})
    assert any("duplicate code 'T1'" in p for p in problems)
    bad = row()
    del bad["fiber_g"]
    bad["vitamin_c"] = 1
    _, problems = load(tmp_path, {"version": 1, "rows": [bad]})
    assert any("missing keys: fiber_g" in p for p in problems)
    assert any("unknown keys: vitamin_c" in p for p in problems)
    _, problems = load(tmp_path, {"version": 2, "rows": []})
    assert any("version: must be 1" in p for p in problems)
    _, problems = load(tmp_path, {"version": 1, "rows": {}})
    assert any("rows: must be a list" in p for p in problems)
    _, problems = load(tmp_path, {"version": 1})
    assert any("missing keys: rows" in p for p in problems)
    assert ROW_KEYS[:3] == ("code", "source", "name")


def test_unreadable_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "nutrition.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContentError, match="invalid JSON"):
        load_nutrition(path, Problems())


def _paths(root: Path) -> ContentPaths:
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


def _set_nutrition_code(paths: ContentPaths, ingredient_id: str, code: str) -> None:
    data = json.loads(paths.ingredients.read_text(encoding="utf-8"))
    for item in data["ingredients"]:
        if item["id"] == ingredient_id:
            item["nutrition_code"] = code
    paths.ingredients.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_nutrition_codes_are_checked_against_the_nutrition_file(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _set_nutrition_code(paths, "lencse", "T1")
    with pytest.raises(ContentError, match="'T1' is not in the nutrition file"):
        load_content(paths)  # no nutrition file yet
    write(tmp_path, {"version": 1, "rows": [row()]})
    content = load_content(paths)
    assert content.ingredients["lencse"].ingredient.nutrition_code == "T1"
    assert list(content.nutrition) == ["T1"]


def test_problems_in_the_nutrition_file_stop_the_load(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    write(tmp_path, {"version": 1, "rows": [row(source="off")]})
    with pytest.raises(ContentError, match="source: must be one of"):
        load_content(paths)
