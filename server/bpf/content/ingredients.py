"""``data/ingredients.json``: the ingredient ontology, parsed into ``model.Ingredient`` and validated.

Every rule of docs/DATA.md is checked, plus the column limits of ``app.ingredient`` (so that nothing is
rounded or rejected later by the database) and a few consistency rules that protect the engine:

* ids are unique, match ``^[a-z0-9_]{2,40}$`` and the list is sorted by id; display names are unique;
* ``list_group``, ``unit``, ``product_units`` and ``tags`` come from their vocabularies, without repeats;
* every ``leaf_ids`` entry is a GVH food leaf (see :mod:`bpf.content.leaves`);
* every include/exclude regex compiles, is at most 120 characters, is lower-case ASCII and cannot match the
  empty string (:func:`bpf.content.vocab.pattern_problems`); name rules and ``product_units`` need
  ``leaf_ids``;
* ``unit=db`` or ``db`` in ``product_units`` needs ``piece_weight_kg``; an ``l``/``kg`` mix needs
  ``density_kg_per_l`` (the engine converts l <-> kg only through it);
* ``piece_weight_kg`` fits ``numeric(8,4)``, ``density_kg_per_l`` is in (0, 5) with at most 3 decimals,
  ``perishable_days`` is 1..3650;
* ``ksh_code`` exists in the KSH file and its unit converts to the canonical unit;
* ``nutrition_code`` exists in the nutrition file;
* an ingredient tagged ``red_meat``/``processed_meat`` can be weighed in kg (the planner's red-meat rule);
* no health-claim words in ``name_hu`` or ``notes``.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from bpf.content.errors import ContentError, Problems
from bpf.content.jsonio import display_path, read_json
from bpf.content.leaves import FoodLeaves
from bpf.content.vocab import (
    INGREDIENT_ID_RE,
    INGREDIENT_TAGS,
    KSH_CODE_RE,
    LIST_GROUPS,
    RED_MEAT_TAGS,
    UNITS,
    health_claim_stems,
    pattern_problems,
)
from bpf.pricing.model import Ingredient, KshPrice, Unit, fold_name

INGREDIENT_KEYS: tuple[str, ...] = (
    "id",
    "name_hu",
    "list_group",
    "unit",
    "piece_weight_kg",
    "density_kg_per_l",
    "pantry",
    "leaf_ids",
    "include_patterns",
    "exclude_patterns",
    "product_units",
    "ksh_code",
    "nutrition_code",
    "tags",
    "perishable_days",
    "notes",
)
MAX_NAME_LENGTH = 80  # app.ingredient.name_hu
MAX_NOTES_LENGTH = 500  # app.ingredient.notes
MAX_NUTRITION_CODE_LENGTH = 40
PIECE_WEIGHT_MAX_PLACES = 4  # numeric(8,4)
PIECE_WEIGHT_LIMIT = Decimal(10_000)
DENSITY_MAX_PLACES = 3  # numeric(6,3), CHECK (> 0 AND < 5)
DENSITY_LIMIT = Decimal(5)
PERISHABLE_DAYS_RANGE = range(1, 3651)


@dataclass(frozen=True, slots=True)
class IngredientRecord:
    """One validated ingredient plus the file-only ``notes`` (stored in ``app.ingredient.notes``)."""

    ingredient: Ingredient
    notes: str | None


def decimal_places(value: Decimal) -> int:
    """Number of digits after the decimal point once trailing zeros are dropped (0.120 -> 2, 5 -> 0)."""
    exponent = value.normalize().as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def as_decimal(value: object) -> Decimal | None:
    """A finite ``Decimal`` from a JSON number (``int`` or ``Decimal``; a ``bool`` is not one), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal) and value.is_finite():
        return value
    return None


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_keys(obj: object, expected: tuple[str, ...], where: str, problems: Problems) -> bool:
    """``obj`` is an object with exactly the ``expected`` keys (none missing, none unknown)."""
    if not isinstance(obj, dict):
        problems.add(where, "must be a JSON object")
        return False
    missing = [k for k in expected if k not in obj]
    unknown = [k for k in obj if k not in expected]
    if missing:
        problems.add(where, f"missing keys: {', '.join(missing)}")
    if unknown:
        problems.add(where, f"unknown keys: {', '.join(unknown)}")
    return not missing and not unknown


def string_list(value: object, where: str, problems: Problems) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        problems.add(where, "must be a list of strings")
        return None
    if len(set(value)) != len(value):
        problems.add(where, "contains duplicates")
    return cast(list[str], value)


def _vocab_list(value: object, vocab: Collection[str], where: str, problems: Problems) -> list[str]:
    items = string_list(value, where, problems)
    if items is None:
        return []
    for item in items:
        if item not in vocab:
            problems.add(where, f"{item!r} is not one of {', '.join(sorted(vocab))}")
    return items


def _patterns(value: object, where: str, problems: Problems) -> list[str]:
    items = string_list(value, where, problems)
    if items is None:
        return []
    for index, pattern in enumerate(items):
        for problem in pattern_problems(pattern):
            problems.add(f"{where}[{index}] {pattern!r}", problem)
    return items


def _leaf_ids(value: object, leaves: FoodLeaves, where: str, problems: Problems) -> list[int]:
    if not isinstance(value, list) or not all(is_int(v) for v in value):
        problems.add(where, "must be a list of integers")
        return []
    ids = cast(list[int], value)
    if len(set(ids)) != len(ids):
        problems.add(where, "contains duplicates")
    for leaf_id in ids:
        if leaf_id not in leaves:
            problems.add(where, f"{leaf_id} is not a GVH food leaf (checked against {leaves.source})")
    return ids


def _optional_decimal(
    value: object, where: str, problems: Problems, *, max_places: int, limit: Decimal
) -> Decimal | None:
    if value is None:
        return None
    number = as_decimal(value)
    if number is None or not 0 < number < limit:
        problems.add(where, f"must be null or a number greater than 0 and below {limit}")
        return None
    if decimal_places(number) > max_places:
        problems.add(where, f"{number} has more than {max_places} decimals (the database would round it)")
        return None
    return number


def convertible(from_unit: str, to_unit: str, piece_weight: Decimal | None, density: Decimal | None) -> bool:
    """Can a quantity in ``from_unit`` be expressed in ``to_unit`` for an ingredient with these factors?

    Mirrors the engine (bpf.pricing.units): same unit; db <-> kg via piece weight; l <-> kg via density."""
    if from_unit == to_unit:
        return True
    pair = {from_unit, to_unit}
    if pair == {"db", "kg"}:
        return piece_weight is not None
    if pair == {"l", "kg"}:
        return density is not None
    return False


@dataclass(frozen=True, slots=True)
class _Context:
    leaves: FoodLeaves
    ksh: Mapping[str, KshPrice]
    nutrition_codes: Collection[str]


def _str_field(obj: dict[str, Any], key: str, where: str, problems: Problems, max_length: int) -> str | None:
    value = obj[key]
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > max_length:
        problems.add(
            f"{where}.{key}", f"must be a string of 1-{max_length} characters without surrounding spaces"
        )
        return None
    return value


def _parse_one(obj: dict[str, Any], where: str, ctx: _Context, problems: Problems) -> IngredientRecord | None:
    before = len(problems)
    ing_id = obj["id"]
    if not isinstance(ing_id, str) or not INGREDIENT_ID_RE.fullmatch(ing_id):
        problems.add(f"{where}.id", f"{ing_id!r} must match ^{INGREDIENT_ID_RE.pattern}$")
    name = _str_field(obj, "name_hu", where, problems, MAX_NAME_LENGTH)
    if obj["list_group"] not in LIST_GROUPS:
        problems.add(f"{where}.list_group", f"{obj['list_group']!r} is not one of {', '.join(LIST_GROUPS)}")
    unit = obj["unit"]
    if unit not in UNITS:
        problems.add(f"{where}.unit", f"{unit!r} is not one of {', '.join(UNITS)}")
    piece_weight = _optional_decimal(
        obj["piece_weight_kg"],
        f"{where}.piece_weight_kg",
        problems,
        max_places=PIECE_WEIGHT_MAX_PLACES,
        limit=PIECE_WEIGHT_LIMIT,
    )
    density = _optional_decimal(
        obj["density_kg_per_l"],
        f"{where}.density_kg_per_l",
        problems,
        max_places=DENSITY_MAX_PLACES,
        limit=DENSITY_LIMIT,
    )
    if not isinstance(obj["pantry"], bool):
        problems.add(f"{where}.pantry", "must be true or false")
    leaf_ids = _leaf_ids(obj["leaf_ids"], ctx.leaves, f"{where}.leaf_ids", problems)
    include = _patterns(obj["include_patterns"], f"{where}.include_patterns", problems)
    exclude = _patterns(obj["exclude_patterns"], f"{where}.exclude_patterns", problems)
    product_units = _vocab_list(obj["product_units"], UNITS, f"{where}.product_units", problems)
    tags = _vocab_list(obj["tags"], INGREDIENT_TAGS, f"{where}.tags", problems)

    if not leaf_ids and (include or exclude or product_units):
        problems.add(where, "include_patterns, exclude_patterns and product_units need leaf_ids")
    if (unit == "db" or "db" in product_units) and piece_weight is None and obj["piece_weight_kg"] is None:
        problems.add(where, "unit db or a db product unit requires piece_weight_kg")
    mixes_l_and_kg = unit in UNITS and {unit, *product_units} >= {"l", "kg"}
    if mixes_l_and_kg and density is None and obj["density_kg_per_l"] is None:
        problems.add(where, "mixing l and kg (unit and product_units) requires density_kg_per_l")
    if RED_MEAT_TAGS.intersection(tags) and unit == "l" and obj["density_kg_per_l"] is None:
        problems.add(
            where, "a red_meat/processed_meat ingredient must be weighable in kg (unit l needs a density)"
        )

    ksh_code = obj["ksh_code"]
    if ksh_code is not None:
        if not isinstance(ksh_code, str) or not KSH_CODE_RE.fullmatch(ksh_code):
            problems.add(f"{where}.ksh_code", f"{ksh_code!r} must be null or match ^{KSH_CODE_RE.pattern}$")
        elif ksh_code not in ctx.ksh:
            problems.add(f"{where}.ksh_code", f"{ksh_code} is not in the KSH file")
        elif unit in UNITS and not convertible(ctx.ksh[ksh_code].unit, unit, piece_weight, density):
            problems.add(
                f"{where}.ksh_code",
                f"KSH row {ksh_code} is priced per {ctx.ksh[ksh_code].unit}, which does not convert to "
                f"{unit} "
                "(add piece_weight_kg or density_kg_per_l, or drop the code)",
            )
    nutrition_code = obj["nutrition_code"]
    if nutrition_code is not None:
        if not isinstance(nutrition_code, str) or not 1 <= len(nutrition_code) <= MAX_NUTRITION_CODE_LENGTH:
            problems.add(
                f"{where}.nutrition_code", f"must be null or 1-{MAX_NUTRITION_CODE_LENGTH} characters"
            )
        elif nutrition_code not in ctx.nutrition_codes:
            problems.add(f"{where}.nutrition_code", f"{nutrition_code!r} is not in the nutrition file")

    perishable = obj["perishable_days"]
    if perishable is not None and (not is_int(perishable) or perishable not in PERISHABLE_DAYS_RANGE):
        problems.add(f"{where}.perishable_days", "must be null or an integer from 1 to 3650")
    notes = obj["notes"]
    if notes is not None and (not isinstance(notes, str) or len(notes) > MAX_NOTES_LENGTH):
        problems.add(f"{where}.notes", f"must be null or a string of at most {MAX_NOTES_LENGTH} characters")
    for key, text in (("name_hu", name), ("notes", notes)):
        if isinstance(text, str) and (stems := health_claim_stems(text)):
            problems.add(
                f"{where}.{key}", f"contains health-claim words ({', '.join(stems)}); none are allowed"
            )

    if len(problems) > before:
        return None
    ingredient = Ingredient(
        id=ing_id,
        name_hu=cast(str, name),
        list_group=obj["list_group"],
        unit=cast(Unit, unit),
        piece_weight_kg=piece_weight,
        pantry=obj["pantry"],
        leaf_ids=tuple(leaf_ids),
        include_patterns=tuple(include),
        exclude_patterns=tuple(exclude),
        product_units=tuple(product_units),
        ksh_code=ksh_code,
        nutrition_code=nutrition_code,
        tags=tuple(tags),
        perishable_days=perishable,
        density_kg_per_l=density,
    )
    return IngredientRecord(ingredient, notes)


def parse_ingredients(
    data: object,
    where: str,
    *,
    leaves: FoodLeaves,
    ksh: Mapping[str, KshPrice],
    nutrition_codes: Collection[str] = frozenset(),
) -> list[IngredientRecord]:
    """Validate parsed ``data/ingredients.json``; raises :class:`ContentError` listing every problem."""
    problems = Problems()
    if not check_keys(data, ("version", "ingredients"), where, problems):
        problems.raise_if_any()
    top = cast(dict[str, Any], data)
    if top["version"] != 1 or isinstance(top["version"], bool):
        problems.add(f"{where}.version", "must be 1")
    items = top["ingredients"]
    if not isinstance(items, list) or not items:
        problems.add(f"{where}.ingredients", "must be a non-empty list")
        problems.raise_if_any()
    ctx = _Context(leaves, ksh, nutrition_codes)
    records: list[IngredientRecord] = []
    seen_ids: dict[str, int] = {}
    seen_names: dict[str, str] = {}
    previous_id: str | None = None
    for index, obj in enumerate(cast(list[object], items)):
        label = obj.get("id") if isinstance(obj, dict) else None
        at = f"{where}.ingredients[{index}]" + (f" ({label})" if isinstance(label, str) else "")
        if isinstance(label, str):  # id-level checks run even when the rest of the object is invalid
            if label in seen_ids:
                problems.add(at, f"duplicate id {label!r} (first at index {seen_ids[label]})")
            else:
                seen_ids[label] = index
            if previous_id is not None and label < previous_id:
                problems.add(at, f"ingredients must be sorted by id ({label!r} comes after {previous_id!r})")
            previous_id = label
        if not check_keys(obj, INGREDIENT_KEYS, at, problems):
            continue
        record = _parse_one(cast(dict[str, Any], obj), at, ctx, problems)
        if record is None:
            continue
        ing = record.ingredient
        folded = fold_name(ing.name_hu)
        if folded in seen_names:
            problems.add(at, f"name_hu {ing.name_hu!r} is also used by {seen_names[folded]!r}")
        seen_names.setdefault(folded, ing.id)
        records.append(record)
    problems.raise_if_any()
    return records


def read_ingredient_records(
    path: Path,
    *,
    leaves: FoodLeaves,
    ksh: Mapping[str, KshPrice],
    nutrition_codes: Collection[str] = frozenset(),
) -> list[IngredientRecord]:
    """Read and validate an ingredients file (records keep the ``notes``)."""
    return parse_ingredients(
        read_json(path), display_path(path), leaves=leaves, ksh=ksh, nutrition_codes=nutrition_codes
    )


__all__ = [
    "INGREDIENT_KEYS",
    "ContentError",
    "IngredientRecord",
    "convertible",
    "parse_ingredients",
    "read_ingredient_records",
]
