"""Price a shopping list at one store (ENGINE.md ``quote_store``; statuses: ``model.LineStatus``).

Per line:
* GVH-mapped ingredient (``leaf_ids`` non-empty, pantry or not): its pack options at the store, then the
  exact pack optimisation -> ``priced``; no option -> ``unavailable``.
* Not GVH-mapped and ``pantry``: ``pantry`` (never priced).
* Not GVH-mapped, with a usable KSH row: ``ksh_estimate`` (labelled, never added to ``checkout_total``).
* Otherwise ``unpriced``.

``used_cost`` = qty x (checkout_cost / quantity bought): the required quantity at the average unit price of
the chosen picks. ``alternatives`` = up to 3 options not used in the picks, cheapest single-option checkout
cost for the same quantity first (ties: product id). A priced line counts towards ``assumed_count`` when
any of its picks is only ``assumed`` to be available.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from bpf.pricing._num import ZERO, div, exact, is_positive
from bpf.pricing.model import Catalogue, Ingredient, PackOption, QuoteLine, Store, StoreQuote
from bpf.pricing.packs import optimise, options_at
from bpf.pricing.units import convert

MAX_ALTERNATIVES = 3


def ksh_estimate(ing: Ingredient, qty: Decimal, cat: Catalogue) -> Decimal | None:
    """qty x the KSH national average per canonical unit, or None when no usable KSH price exists."""
    if ing.ksh_code is None:
        return None
    row = cat.ksh.get(ing.ksh_code)
    if row is None or not is_positive(row.unit_qty) or not is_positive(row.price):
        return None
    reference = convert(row.unit_qty, row.unit, ing)  # canonical units the KSH price is for
    if not is_positive(reference):
        return None
    return div(qty * row.price, reference)


def single_option_cost(qty: Decimal, option: PackOption) -> Decimal:
    """Checkout cost of covering ``qty`` with this option alone (whole packs, or the exact weight)."""
    if option.size is None:
        return option.price * qty
    whole, rest = divmod(qty, option.size)  # integer-part division is exact (it never rounds)
    return option.price * (whole + (1 if rest else 0))


def _alternatives(qty: Decimal, options: Sequence[PackOption], used: set[str]) -> tuple[PackOption, ...]:
    unused = [o for o in options if o.product_id not in used]
    ranked = sorted(unused, key=lambda o: (single_option_cost(qty, o), o.product_id))
    return tuple(ranked[:MAX_ALTERNATIVES])


def _priced_line(ingredient_id: str, qty: Decimal, options: Sequence[PackOption]) -> QuoteLine:
    picks = optimise(qty, options)
    if not picks:  # pragma: no cover - options is non-empty and qty > 0
        raise AssertionError("optimiser returned no picks")
    checkout = sum((pick.cost for pick in picks), ZERO)
    bought = sum((pick.qty for pick in picks), ZERO)
    used = div(qty * checkout, bought)
    return QuoteLine(
        ingredient_id=ingredient_id,
        qty=qty,
        status="priced",
        picks=picks,
        checkout_cost=checkout,
        used_cost=used,
        leftover_qty=bought - qty,
        alternatives=_alternatives(qty, options, {pick.option.product_id for pick in picks}),
    )


def _quote_line(
    ingredient_id: str, qty: Decimal, store: Store, cat: Catalogue, include_loyalty: bool
) -> QuoteLine:
    ing = cat.ingredients[ingredient_id]  # KeyError for unknown ids (the API validates first)
    if not qty.is_finite() or qty <= 0:
        raise ValueError(f"quantity for {ingredient_id!r} must be finite and > 0, got {qty!r}")
    if ing.leaf_ids:
        options = options_at(ing, store, cat, include_loyalty)
        if not options:
            return QuoteLine(ingredient_id, qty, "unavailable")
        return _priced_line(ingredient_id, qty, options)
    if ing.pantry:
        return QuoteLine(ingredient_id, qty, "pantry")
    estimate = ksh_estimate(ing, qty, cat)
    if estimate is not None:
        return QuoteLine(ingredient_id, qty, "ksh_estimate", ksh_estimate=estimate)
    return QuoteLine(ingredient_id, qty, "unpriced")


@exact
def quote_store(
    lines: Sequence[tuple[str, Decimal]], store: Store, cat: Catalogue, *, include_loyalty: bool = False
) -> StoreQuote:
    """Price every ``(ingredient_id, canonical qty)`` line at ``store``; lines keep their input order."""
    quoted = tuple(_quote_line(ing_id, qty, store, cat, include_loyalty) for ing_id, qty in lines)
    priced = [line for line in quoted if line.status == "priced"]
    return StoreQuote(
        store_id=store.id,
        lines=quoted,
        checkout_total=sum((line.checkout_cost or ZERO for line in priced), ZERO),
        used_total=sum((line.used_cost or ZERO for line in priced), ZERO),
        missing=tuple(line.ingredient_id for line in quoted if line.status == "unavailable"),
        assumed_count=sum(
            1 for line in priced if any(pick.option.availability == "assumed" for pick in line.picks)
        ),
        ksh_estimate_total=sum((line.ksh_estimate or ZERO for line in quoted), ZERO),
    )
