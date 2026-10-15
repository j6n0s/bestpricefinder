"""Per-recipe facts the planner rules need, and the input validation shared by the two public functions.

Pure: no I/O, no clock, no randomness. Quantities that come from a division (grams per serving) are exact
``Fraction`` values; money stays ``Decimal`` (only multiplied by whole numbers, so it stays exact).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from bpf.pricing.model import SLOTS_5, Ingredient, Recipe, Slot

SLOT_POS: Mapping[Slot, int] = {slot: pos for pos, slot in enumerate(SLOTS_5)}
"""Slot -> position in ``SLOTS_5`` (reggeli 0, tizorai 1, ebed 2, uzsonna 3, vacsora 4)."""

MAIN_SLOTS: tuple[Slot, ...] = ("reggeli", "ebed", "vacsora")
MAIN_POS: frozenset[int] = frozenset(SLOT_POS[slot] for slot in MAIN_SLOTS)
"""Main meals. tizorai and uzsonna are snacks: shorter no-repeat window, ignored by the potato rule."""

RED_MEAT_TAGS: frozenset[str] = frozenset(("red_meat", "processed_meat"))
POTATO_TAG = "potato"
PERISHABLE_MAX_DAYS = 7
"""An ingredient is perishable for leftover-aware grouping when ``perishable_days`` is set and <= this."""

MAX_PEOPLE = 12
MAX_DAYS = 31


@dataclass(frozen=True, slots=True)
class RecipeFacts:
    """What the rules need to know about one recipe, for one household size and cost table."""

    recipe_id: str
    fish: bool  # recipe tag "hal"
    legume: bool  # recipe tag "huvelyes"
    meat_free: bool  # recipe tag "husmentes"
    two_day: bool  # recipe tag "ket_napos": may fill the same slot on the next day
    potato: bool  # some line's ingredient is tagged "potato" (optional lines included)
    red_meat_g: Fraction  # raw g of red_meat/processed_meat lines per serving (optional lines included)
    cost: Decimal | None  # estimated cost of one meal for the household; None = no estimate
    perishables: tuple[str, ...]  # sorted ids of perishable ingredients on any line


def line_kg(qty: Decimal, ing: Ingredient) -> Fraction:
    """A recipe line quantity (in the ingredient's canonical unit) as exact kilograms.

    ``db`` converts via ``piece_weight_kg`` and ``l`` via ``density_kg_per_l``. Anything else raises
    ``ValueError``: the red meat rule must never silently ignore meat it cannot weigh."""
    if ing.unit == "kg":
        return Fraction(qty)
    if ing.unit == "db" and ing.piece_weight_kg is not None:
        return Fraction(qty) * Fraction(ing.piece_weight_kg)
    if ing.unit == "l" and ing.density_kg_per_l is not None:
        return Fraction(qty) * Fraction(ing.density_kg_per_l)
    raise ValueError(f"ingredient {ing.id!r}: cannot convert {ing.unit!r} to kg (no piece weight or density)")


def recipe_facts(
    recipe: Recipe, ingredients: Mapping[str, Ingredient], *, people: int, costs: Mapping[str, Decimal]
) -> RecipeFacts:
    """Derive the rule facts of ``recipe``. Unknown ingredient ids raise ``KeyError``."""
    if recipe.servings < 1:
        raise ValueError(f"recipe {recipe.id!r}: servings must be >= 1")
    red_kg = Fraction(0)
    potato = False
    perishables: set[str] = set()
    for line in recipe.lines:
        ing = ingredients.get(line.ingredient_id)
        if ing is None:
            raise KeyError(f"recipe {recipe.id!r} uses unknown ingredient {line.ingredient_id!r}")
        if RED_MEAT_TAGS.intersection(ing.tags):
            red_kg += line_kg(line.qty, ing)
        if POTATO_TAG in ing.tags:
            potato = True
        if ing.perishable_days is not None and ing.perishable_days <= PERISHABLE_MAX_DAYS:
            perishables.add(ing.id)
    per_serving = costs.get(recipe.id)
    tags = recipe.tags
    return RecipeFacts(
        recipe_id=recipe.id,
        fish="hal" in tags,
        legume="huvelyes" in tags,
        meat_free="husmentes" in tags,
        two_day="ket_napos" in tags,
        potato=potato,
        red_meat_g=red_kg * 1000 / recipe.servings,
        cost=None if per_serving is None else per_serving * people,
        perishables=tuple(sorted(perishables)),
    )


# ───────────────────────────── validation ─────────────────────────────


def validate_people(people: int) -> int:
    if isinstance(people, bool) or not isinstance(people, int) or not 1 <= people <= MAX_PEOPLE:
        raise ValueError(f"people must be an int in 1..{MAX_PEOPLE}")
    return people


def validate_non_negative_int(value: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{what} must be an int >= 0")
    return value


def validate_money(value: Decimal | int, what: str) -> Decimal:
    """A finite, non-negative amount as ``Decimal`` (ints are accepted and converted exactly)."""
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise TypeError(f"{what} must be a Decimal")
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{what} must be a finite amount >= 0")
    return amount


def validate_costs(costs: Mapping[str, Decimal] | None) -> dict[str, Decimal]:
    """Copy of the cost-per-serving table with every value validated."""
    if costs is None:
        return {}
    return {rid: validate_money(value, f"cost per serving of {rid!r}") for rid, value in costs.items()}
