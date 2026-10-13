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

_BRIDGED = ({"db", "kg"}, {"l", "kg"})


def _bridge(
    from_unit: str, to_unit: str, piece_weight: Decimal | None, density: Decimal | None
) -> Decimal | None:
    """kg per one db (piece weight) or per one l (density) for a cross-unit pair; None when missing."""
    if {from_unit, to_unit} not in _BRIDGED:
        return None
    bridge = piece_weight if "db" in (from_unit, to_unit) else density
    return bridge if is_positive(bridge) else None


def units_convertible(
    from_unit: str, to_unit: str, piece_weight: Decimal | None, density: Decimal | None
) -> bool:
    """True when quantities in ``from_unit`` can be expressed in ``to_unit``."""
    return from_unit == to_unit or _bridge(from_unit, to_unit, piece_weight, density) is not None


def convert_units(
    qty: Decimal, from_unit: str, to_unit: str, piece_weight: Decimal | None, density: Decimal | None
) -> Decimal | None:
    """Engine-internal conversion (call inside ``exact``): multiply into kg, divide out of kg."""
    if from_unit == to_unit:
        return qty
    bridge = _bridge(from_unit, to_unit, piece_weight, density)
    if bridge is None:
        return None
    if to_unit == "kg":  # db -> kg or l -> kg
        return qty * bridge
    return div(qty, bridge)  # kg -> db or kg -> l


def is_convertible(product_unit: str, ing: Ingredient) -> bool:
    """True when :func:`to_canonical` can convert ``product_unit`` quantities for this ingredient."""
    return units_convertible(product_unit, ing.unit, ing.piece_weight_kg, ing.density_kg_per_l)


def convert(qty: Decimal, product_unit: str, ing: Ingredient) -> Decimal | None:
    """Engine-internal :func:`to_canonical` without the context switch: call it inside ``exact``."""
    return convert_units(qty, product_unit, ing.unit, ing.piece_weight_kg, ing.density_kg_per_l)


@exact
def to_canonical(qty: Decimal, product_unit: str, ing: Ingredient) -> Decimal | None:
    """Convert ``qty`` in ``product_unit`` to ``ing.unit``; None when not convertible.

    db -> kg multiplies by the piece weight, kg -> db divides by it; l -> kg multiplies by the density,
    kg -> l divides by it. Multiplications are exact; divisions round to 28 significant digits."""
    return convert(qty, product_unit, ing)
