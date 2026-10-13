"""``data/nutrition/nutrition.json`` (optional): composition per 100 g from CIQUAL, Frida or USDA FDC.

The file is written by a converter from a locally downloaded official table; no hand-typed or remembered
values (docs/DATA.md). While it does not exist the loader loads no nutrition rows, and any ingredient with a
``nutrition_code`` is an error. Values must fit ``app.nutrition`` (``numeric(8,2)``, >= 0).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast, get_args

from bpf.content.errors import Problems
from bpf.content.ingredients import as_decimal, check_keys, decimal_places
from bpf.content.jsonio import display_path, read_json
from bpf.pricing.model import NutritionRow

NutritionSource = Literal["ciqual", "frida", "usda"]
SOURCES: tuple[str, ...] = get_args(NutritionSource)
VALUE_KEYS: tuple[str, ...] = (
    "kcal",
    "protein_g",
    "carb_g",
    "sugar_g",
    "fat_g",
    "satfat_g",
    "fiber_g",
    "salt_g",
)
ROW_KEYS: tuple[str, ...] = ("code", "source", "name", *VALUE_KEYS)
VALUE_LIMIT = Decimal(1_000_000)  # numeric(8,2)
VALUE_MAX_PLACES = 2
MAX_CODE_LENGTH = 40
MAX_NAME_LENGTH = 200


def _row(obj: dict[str, Any], where: str, problems: Problems) -> NutritionRow | None:
    before = len(problems)
    code = obj["code"]
    if not isinstance(code, str) or not 1 <= len(code) <= MAX_CODE_LENGTH or code != code.strip():
        problems.add(f"{where}.code", f"must be a string of 1-{MAX_CODE_LENGTH} characters")
    if obj["source"] not in SOURCES:
        problems.add(f"{where}.source", f"must be one of {', '.join(SOURCES)}")
    name = obj["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME_LENGTH:
        problems.add(f"{where}.name", f"must be a string of 1-{MAX_NAME_LENGTH} characters")
    values: dict[str, Decimal | None] = {}
    for key in VALUE_KEYS:
        raw = obj[key]
        if raw is None:
            values[key] = None
            continue
        number = as_decimal(raw)
        if number is None or not 0 <= number < VALUE_LIMIT or decimal_places(number) > VALUE_MAX_PLACES:
            problems.add(f"{where}.{key}", "must be null or a number >= 0 with at most 2 decimals")
            continue
        values[key] = number
    if len(problems) > before:
        return None
    return NutritionRow(code=code, source=cast(NutritionSource, obj["source"]), name=name, **values)


def load_nutrition(path: Path, problems: Problems) -> dict[str, NutritionRow]:
    """Rows of the nutrition file (empty when the file does not exist); problems are appended."""
    if not path.exists():
        return {}
    where = display_path(path)
    data = read_json(path)
    if not check_keys(data, ("version", "rows"), where, problems):
        return {}
    top = cast(dict[str, Any], data)
    if top["version"] != 1 or isinstance(top["version"], bool):
        problems.add(f"{where}.version", "must be 1")
    rows = top["rows"]
    if not isinstance(rows, list):
        problems.add(f"{where}.rows", "must be a list")
        return {}
    result: dict[str, NutritionRow] = {}
    for index, obj in enumerate(rows):
        at = f"{where}.rows[{index}]"
        if not check_keys(obj, ROW_KEYS, at, problems):
            continue
        row = _row(cast(dict[str, Any], obj), at, problems)
        if row is None:
            continue
        if row.code in result:
            problems.add(at, f"duplicate code {row.code!r}")
            continue
        result[row.code] = row
    return result
