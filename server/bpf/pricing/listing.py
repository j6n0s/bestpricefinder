"""Aggregated shopping list (ENGINE.md ``build_list``; docs/API.md ``POST /api/list``).

Each recipe's line quantities are scaled by ``servings / recipe.servings`` and summed per ingredient; the
``on_hand`` quantities are subtracted and lines that drop to <= 0 are removed. Arithmetic is exact
(fractions); the remaining quantity is then rounded half-up to 0.001, the API's quantity grid, and a line
that rounds to 0 is removed as well. Pantry ingredients stay in the list with ``pantry=True``.

Order: ``list_group`` in the docs/DATA.md order (unknown groups last, alphabetically), then the
accent-folded ``name_hu`` (so "ánizs" sorts with the a's), then ``name_hu`` and the id as tie-breaks.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from fractions import Fraction

from bpf.pricing._num import from_scaled_int
from bpf.pricing.model import Ingredient, ListLine, Recipe, fold_name

LIST_GROUP_ORDER: tuple[str, ...] = (
    "zoldseg_gyumolcs",
    "pekaru",
    "tejtermek_tojas",
    "hus_hal",
    "szaraz_tartos",
    "fagyasztott",
    "fuszer_olaj",
    "egyeb",
)
_GROUP_RANK = {group: index for index, group in enumerate(LIST_GROUP_ORDER)}
_QTY_STEPS_PER_UNIT = 1000  # 0.001


def _round_qty(value: Fraction) -> Decimal:
    """Round a positive exact quantity half-up to 0.001."""
    steps = math.floor(value * _QTY_STEPS_PER_UNIT + Fraction(1, 2))
    return from_scaled_int(steps, 3)


def _fraction(value: Decimal | int, what: str) -> Fraction:
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError(f"{what} must be finite, got {value!r}")
    return Fraction(value)


def _sort_key(line: ListLine, ingredients: Mapping[str, Ingredient]) -> tuple[int, str, str, str, str]:
    name = ingredients[line.ingredient_id].name_hu
    rank = _GROUP_RANK.get(line.list_group, len(LIST_GROUP_ORDER))
    return (rank, line.list_group, fold_name(name), name, line.ingredient_id)


def build_list(
    items: Sequence[tuple[Recipe, Decimal]],
    ingredients: Mapping[str, Ingredient],
    *,
    on_hand: Mapping[str, Decimal] | None = None,
    include_optional: bool = True,
) -> tuple[ListLine, ...]:
    """Aggregate ``(recipe, servings wanted)`` items into shopping-list lines (see the module docstring)."""
    totals: dict[str, Fraction] = {}
    sources: dict[str, dict[str, None]] = {}
    for recipe, servings in items:
        wanted = _fraction(servings, "servings")
        if wanted <= 0 or recipe.servings <= 0:
            raise ValueError(f"servings must be > 0 (recipe {recipe.id!r})")
        factor = wanted / recipe.servings
        for line in recipe.lines:
            if line.optional and not include_optional:
                continue
            if line.ingredient_id not in ingredients:
                raise KeyError(line.ingredient_id)
            qty = _fraction(line.qty, "recipe line qty") * factor
            totals[line.ingredient_id] = totals.get(line.ingredient_id, Fraction(0)) + qty
            sources.setdefault(line.ingredient_id, {}).setdefault(recipe.id, None)

    lines: list[ListLine] = []
    for ingredient_id, total in totals.items():
        remaining = total
        if on_hand and ingredient_id in on_hand:
            remaining -= _fraction(on_hand[ingredient_id], "on_hand qty")
        if remaining <= 0:
            continue
        qty = _round_qty(remaining)
        if qty <= 0:
            continue
        ing = ingredients[ingredient_id]
        lines.append(
            ListLine(
                ingredient_id=ingredient_id,
                qty=qty,
                unit=ing.unit,
                list_group=ing.list_group,
                pantry=ing.pantry,
                recipe_ids=tuple(sources[ingredient_id]),
            )
        )
    lines.sort(key=lambda line: _sort_key(line, ingredients))
    return tuple(lines)
