"""Store-vs-chain price rule (ENGINE.md ``resolve_price``; BUILD-BRIEF §4.1 traps 1 and 3).

* A store without data (``has_data`` False) has no price.
* A per-store price row wins over the chain row: min of NORMAL / DISCOUNTED (+ LOYALTY when
  ``include_loyalty``), scope ``store``, availability ``confirmed``.
* Otherwise the chain-typical price: ``product_min_amount`` (the price charged by >= 80 % of the chain's
  carrying stores, which is what GVH displays). ``ChainPrice.normal_amount`` and friends are per-type
  MINIMA across stores (often one outlier store) and are never used as the price. When
  ``product_min_amount`` is missing, the XLSX price is used only when ``xlsx_min == xlsx_max`` (every store
  charges it).
* Amounts that are missing, zero, negative or not finite are treated as "no price" (GVH prices are > 0;
  a zero would silently make an ingredient free).
"""

from __future__ import annotations

from decimal import Decimal

from bpf.pricing._num import exact, is_positive
from bpf.pricing.model import Catalogue, ChainPrice, PriceType, Product, ResolvedPrice, Store, StorePrice

# Preference when two price types have the same amount: report the plainer one.
_TYPE_ORDER: dict[PriceType, int] = {"NORMAL": 0, "DISCOUNTED": 1, "LOYALTY": 2}


def chain_typical_amount(cp: ChainPrice) -> Decimal | None:
    """The chain-typical price: ``product_min_amount``, else the XLSX price when min == max, else None."""
    if is_positive(cp.product_min_amount):
        return cp.product_min_amount
    if is_positive(cp.xlsx_min) and cp.xlsx_max is not None and cp.xlsx_min == cp.xlsx_max:
        return cp.xlsx_min
    return None


def _chain_price_type(cp: ChainPrice, amount: Decimal) -> PriceType:
    """DISCOUNTED when the chosen amount equals a discounted amount below the normal amount, else NORMAL."""
    disc, normal = cp.discounted_amount, cp.normal_amount
    if disc is not None and normal is not None and amount == disc and disc < normal:
        return "DISCOUNTED"
    return "NORMAL"


def _store_row_price(sp: StorePrice, include_loyalty: bool) -> tuple[Decimal, PriceType] | None:
    """Cheapest usable amount of a per-store row (LOYALTY only when included); ties keep the plainer type."""
    offers: list[tuple[Decimal | None, PriceType]] = [
        (sp.normal_amount, "NORMAL"),
        (sp.discounted_amount, "DISCOUNTED"),
    ]
    if include_loyalty:
        offers.append((sp.loyalty_amount, "LOYALTY"))
    usable = [(amount, ptype) for amount, ptype in offers if is_positive(amount)]
    if not usable:
        return None
    return min(usable, key=lambda offer: (offer[0], _TYPE_ORDER[offer[1]]))


@exact
def resolve_price(
    product: Product, store: Store, cat: Catalogue, *, include_loyalty: bool = False
) -> ResolvedPrice | None:
    """The price of ``product`` at ``store`` after the store-vs-chain rule; None when not carried/priced."""
    if not store.has_data:
        return None
    sp = cat.store_prices.get((product.id, store.id))
    if sp is not None:
        picked = _store_row_price(sp, include_loyalty)
        if picked is not None:
            amount, ptype = picked
            return ResolvedPrice(product.id, store.id, amount, ptype, "store", "confirmed")
    cp = cat.chain_prices.get((product.id, store.chain_id))
    if cp is None:
        return None
    carriers = cat.availability.get((product.id, store.chain_id))
    # A per-store row (even one without a usable amount) proves the store carries the product.
    carried_here = sp is not None or (carriers is not None and store.id in carriers)
    if carriers is not None and not carried_here:
        return None
    amount = chain_typical_amount(cp)
    if amount is None:
        return None
    ptype = _chain_price_type(cp, amount)
    loyalty = cp.loyalty_amount
    if include_loyalty and cp.price_same_everywhere is True and is_positive(loyalty) and loyalty < amount:
        amount, ptype = loyalty, "LOYALTY"
    availability = "confirmed" if carried_here else "assumed"
    return ResolvedPrice(product.id, store.id, amount, ptype, "chain", availability)
