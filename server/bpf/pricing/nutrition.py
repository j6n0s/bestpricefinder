"""Nutrition per serving from per-100 g composition rows (ENGINE.md ``nutrition_per_serving``).

Mass per line in kg: ``kg`` as is; ``db`` x ``piece_weight_kg``; ``l`` x ``density_kg_per_l`` only when the
density is set (no density is ever assumed, not even 1.0 for water-like liquids). Optional lines are not
part of the base recipe and are left out.

A line "has data" when its ``nutrition_code`` resolves to a row in ``cat.nutrition`` with all eight values
present (a partial row would silently understate a nutrient, so it counts as no data). Nutrients are summed
over every line with data and a known mass, pantry lines included (oil and sugar matter). ``coverage`` is
the share of the NON-pantry mass that has data. The result is None when the catalogue has no composition
data, no line has data, the recipe has no non-pantry mass, a non-pantry line's mass is unknown (the
coverage could not be computed honestly), or coverage < 0.8.
"""

from __future__ import annotations

from decimal import Decimal

from bpf.pricing._num import ZERO, div, exact
from bpf.pricing.model import Catalogue, Ingredient, NutritionPerServing, NutritionRow, Recipe

MIN_COVERAGE = Decimal("0.8")
NUTRIENTS: tuple[str, ...] = (
    "kcal",
    "protein_g",
    "carb_g",
    "sugar_g",
    "fat_g",
    "satfat_g",
    "fiber_g",
    "salt_g",
)
_PER_100G_TO_PER_KG = Decimal(10)


def line_mass_kg(qty: Decimal, ing: Ingredient) -> Decimal | None:
    """Mass in kg of ``qty`` canonical units of ``ing``; None when it cannot be known."""
    if ing.unit == "kg":
        return qty
    factor = ing.piece_weight_kg if ing.unit == "db" else ing.density_kg_per_l
    if factor is None or not factor.is_finite() or factor <= 0:
        return None
    return qty * factor


def _complete_row(ing: Ingredient, cat: Catalogue) -> NutritionRow | None:
    if ing.nutrition_code is None:
        return None
    row = cat.nutrition.get(ing.nutrition_code)
    if row is None:
        return None
    for name in NUTRIENTS:
        value = getattr(row, name)
        if value is None or not value.is_finite() or value < 0:
            return None
    return row


@exact
def nutrition_per_serving(recipe: Recipe, cat: Catalogue) -> NutritionPerServing | None:
    """Per-serving nutrients, or None when the data does not cover the recipe (see the module docstring)."""
    if recipe.servings <= 0:
        raise ValueError(f"recipe {recipe.id!r} has servings {recipe.servings}")
    if not cat.nutrition:
        return None
    totals = dict.fromkeys(NUTRIENTS, ZERO)
    base_mass = ZERO
    covered_mass = ZERO
    any_data = False
    for line in recipe.lines:
        if line.optional:
            continue
        ing = cat.ingredients[line.ingredient_id]  # KeyError: unknown ingredient in a recipe
        mass = line_mass_kg(line.qty, ing)
        row = _complete_row(ing, cat)
        if not ing.pantry:
            if mass is None:
                return None
            base_mass += mass
            if row is not None:
                covered_mass += mass
        if row is None or mass is None:
            continue
        any_data = True
        for name in NUTRIENTS:
            totals[name] += mass * _PER_100G_TO_PER_KG * getattr(row, name)
    if not any_data or base_mass <= 0:
        return None
    coverage = div(covered_mass, base_mass)
    if coverage < MIN_COVERAGE:
        return None
    per_serving = {name: div(total, recipe.servings) for name, total in totals.items()}
    return NutritionPerServing(**per_serving, coverage=coverage)
