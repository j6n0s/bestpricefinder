"""Per-chain price history of an ingredient from our own archive (ENGINE.md ``ingredient_history``).

``rows`` come from ``api.product_chain_history``: ``(data_date, product_id, chain_id, product_min_amount)``.
For each chain and date the result holds the minimum canonical unit price among the ingredient's current
candidate products (product metadata from the catalogue). Rows for other products, or with a missing or
non-positive amount, are ignored. Chains are returned in id order, points in date order.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from bpf.pricing._num import exact, is_positive
from bpf.pricing.matching import candidate_products
from bpf.pricing.model import Catalogue, Ingredient
from bpf.pricing.packs import canonical_unit_price


@exact
def ingredient_history(
    ing: Ingredient, cat: Catalogue, rows: Iterable[tuple[date, str, str, Decimal | None]]
) -> dict[str, tuple[tuple[date, Decimal], ...]]:
    """chain id -> ((date, min canonical unit price), ...) sorted by date."""
    candidates = {product.id: product for product in candidate_products(ing, cat)}
    best: dict[str, dict[date, Decimal]] = {}
    for data_date, product_id, chain_id, amount in rows:
        product = candidates.get(product_id)
        if product is None or not is_positive(amount):
            continue
        unit_price = canonical_unit_price(product, amount, ing)
        if unit_price is None:
            continue
        per_date = best.setdefault(chain_id, {})
        current = per_date.get(data_date)
        if current is None or unit_price < current:
            per_date[data_date] = unit_price
    return {chain_id: tuple(sorted(best[chain_id].items())) for chain_id in sorted(best)}
