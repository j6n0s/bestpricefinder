"""Unit normalisation: product units -> the ingredient's canonical unit (ENGINE.md ``to_canonical``).

Rules (BUILD-BRIEF §4.1 trap 5, docs/DATA.md):
* same unit: identity;
* ``db`` <-> ``kg`` only through ``Ingredient.piece_weight_kg``;
* ``l`` <-> ``kg`` only through ``Ingredient.density_kg_per_l``;
* everything else (``db`` <-> ``l``, unknown units such as ``g`` or ``csomag``) is not convertible: None.
"""

from __future__ import annotations

from decimal import Decimal

from bpf.pricing._num import div, exact, is_positive
from bpf.pricing.model import Ingredient


def _factor(ing: Ingredient, product_unit: str) -> Decimal | None:
    """kg per one ``product_unit`` for the cross-unit cases (None when the bridge value is missing)."""
    if product_unit == "db" or ing.unit == "db":
        bridge = ing.piece_weight_kg
    else:
        bridge = ing.density_kg_per_l
    return bridge if is_positive(bridge) else None


def is_convertible(product_unit: str, ing: Ingredient) -> bool:
    """True when :func:`to_canonical` can convert ``product_unit`` quantities for this ingredient."""
    if product_unit == ing.unit:
        return True
    if {product_unit, ing.unit} not in ({"db", "kg"}, {"l", "kg"}):
        return False
    return _factor(ing, product_unit) is not None


@exact
def to_canonical(qty: Decimal, product_unit: str, ing: Ingredient) -> Decimal | None:
    """Convert ``qty`` in ``product_unit`` to ``ing.unit``; None when not convertible.

    db -> kg multiplies by the piece weight, kg -> db divides by it; l -> kg multiplies by the density,
    kg -> l divides by it. Multiplications are exact; divisions round to 28 significant digits."""
    if product_unit == ing.unit:
        return qty
    if not is_convertible(product_unit, ing):
        return None
    factor = _factor(ing, product_unit)
    if factor is None:  # pragma: no cover - is_convertible checked it
        return None
    if ing.unit == "kg":  # db -> kg or l -> kg
        return qty * factor
    return div(qty, factor)  # kg -> db or kg -> l
