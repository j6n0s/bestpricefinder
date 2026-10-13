"""Nutrition per serving (ENGINE.md ``nutrition_per_serving``).

The composition rows below are INVENTED round numbers for the arithmetic (see
tests/fixtures/pricing/README.md); they are not CIQUAL/Frida/USDA values and must never be shipped."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from bpf.pricing import Catalogue, NutritionPerServing, NutritionRow, Recipe, nutrition_per_serving
from tests.fixtures.pricing.builders import catalogue, ingredient, recipe

D = Decimal


def row(
    code: str, kcal: int, protein: int, carb: int, sugar: int, fat: int, satfat: int, fiber: int, salt: int
):  # type: ignore[no-untyped-def]
    return NutritionRow(
        code,
        "ciqual",
        f"synthetic {code}",
        *(D(v) for v in (kcal, protein, carb, sugar, fat, satfat, fiber, salt)),
    )


TABLE = [
    row("SYN-A", 100, 10, 20, 5, 2, 1, 3, 1),
    row("SYN-B", 200, 0, 40, 10, 8, 4, 0, 0),
    row("SYN-OIL", 900, 0, 0, 0, 100, 10, 0, 0),
    row("SYN-MILK", 50, 3, 5, 5, 2, 1, 0, 0),
]
INGREDIENTS = [
    ingredient("a", nutrition_code="SYN-A"),
    ingredient("b_db", unit="db", piece_weight="0.05", nutrition_code="SYN-B"),
    ingredient("olaj", unit="l", density="0.92", pantry=True, nutrition_code="SYN-OIL"),
    ingredient("tej", unit="l", density="1.03", nutrition_code="SYN-MILK"),
    ingredient("tej_nodensity", unit="l", nutrition_code="SYN-MILK"),
    ingredient("nodata"),
    ingredient("so", pantry=True),
]


def _cat(nutrition: list[NutritionRow] = TABLE) -> Catalogue:
    return catalogue(ingredients=INGREDIENTS, nutrition=nutrition)


def test_none_without_any_composition_data() -> None:
    dish = recipe("r", 2, [("a", "0.3")])
    assert nutrition_per_serving(dish, _cat(nutrition=[])) is None


def test_values_per_serving_with_a_tiny_table() -> None:
    dish = recipe("r", 2, [("a", "0.3"), ("b_db", "4"), ("olaj", "0.01"), ("so", "0.005")])
    result = nutrition_per_serving(dish, _cat())
    # masses: a 0.3 kg = 300 g; b 4 x 0.05 = 200 g; oil 0.01 l x 0.92 = 9.2 g (pantry); salt: no data.
    # kcal: 300 x 1.00 + 200 x 2.00 + 9.2 x 9.00 = 300 + 400 + 82.8 = 782.8 -> / 2 = 391.4
    assert result == NutritionPerServing(
        kcal=D("391.4"),
        protein_g=D(15),  # (30 + 0 + 0) / 2
        carb_g=D(70),  # (60 + 80) / 2
        sugar_g=D("17.5"),  # (15 + 20) / 2
        fat_g=D("15.6"),  # (6 + 16 + 9.2) / 2
        satfat_g=D("5.96"),  # (3 + 8 + 0.92) / 2
        fiber_g=D("4.5"),  # 9 / 2
        salt_g=D("1.5"),  # 3 / 2
        coverage=D(1),  # non-pantry mass 500 g, all with data (pantry lines do not count)
    )


def test_liquid_mass_uses_density() -> None:
    result = nutrition_per_serving(recipe("r", 1, [("tej", "0.5")]), _cat())
    assert result is not None
    assert result.kcal == D("257.5")


def test_liquid_without_density_has_unknown_mass_so_none() -> None:
    dish = recipe("r", 1, [("a", "1"), ("tej_nodensity", "0.1")])
    assert nutrition_per_serving(dish, _cat()) is None


def test_coverage_threshold() -> None:
    covered = recipe("r", 1, [("a", "0.8"), ("nodata", "0.2")])
    result = nutrition_per_serving(covered, _cat())
    assert result is not None
    assert result.coverage == D("0.8")
    assert result.kcal == D(800)
    short = recipe("r", 1, [("a", "0.79"), ("nodata", "0.21")])
    assert nutrition_per_serving(short, _cat()) is None


def test_partial_rows_count_as_no_data() -> None:
    partial = [replace(TABLE[0], fiber_g=None)]
    assert nutrition_per_serving(recipe("r", 1, [("a", "1")]), _cat(nutrition=partial)) is None


def test_optional_lines_are_left_out() -> None:
    dish = recipe("r", 1, [("a", "1"), ("nodata", "5", True)])
    result = nutrition_per_serving(dish, _cat())
    assert result is not None
    assert result.coverage == D(1)
    assert result.kcal == D(1000)


def test_only_pantry_lines_gives_none() -> None:
    assert nutrition_per_serving(recipe("r", 1, [("olaj", "0.1")]), _cat()) is None


@pytest.mark.parametrize("servings", [0, -1])
def test_invalid_servings_raise(servings: int) -> None:
    dish: Recipe = replace(recipe("r", 1, [("a", "1")]), servings=servings)
    with pytest.raises(ValueError, match="servings"):
        nutrition_per_serving(dish, _cat())
