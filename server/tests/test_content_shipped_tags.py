"""Shipped data/recipes/*.json: tag policy that the loader does not enforce yet (BUILD-BRIEF §8.7).

``gyerekbarat`` (shown as "gyerekbarát") is a plain descriptive tag for simple, mild dishes children commonly
eat. A recipe that needs whole or chopped nuts or seeds (ingredient tag ``nut_seed``: peanuts, walnuts, poppy
seed) must not carry it: nut pieces are a choking hazard for small children and a common allergen, so the
tag would read as a suitability claim the content cannot stand behind. A ``nut_seed`` line that is optional
is fine, because the dish is complete without it.

The validator (``bpf.content.recipes``) has no such rule yet, so this test guards the shipped data directly.
"""

from __future__ import annotations

from bpf.content.load import load_ingredients
from bpf.content.paths import RECIPES_DIR
from bpf.content.recipes import load_recipes

CHILD_TAG = "gyerekbarat"
NUT_TAG = "nut_seed"


def test_gyerekbarat_recipes_have_no_required_nut_or_seed_line() -> None:
    ingredients = load_ingredients()
    recipes = load_recipes(RECIPES_DIR, ingredients)
    assert any(CHILD_TAG in recipe.tags for recipe in recipes.values())  # the check is not vacuous
    offending = {
        recipe.id: sorted(
            line.ingredient_id
            for line in recipe.lines
            if not line.optional and NUT_TAG in ingredients[line.ingredient_id].tags
        )
        for recipe in recipes.values()
        if CHILD_TAG in recipe.tags
    }
    assert {rid: ids for rid, ids in offending.items() if ids} == {}
