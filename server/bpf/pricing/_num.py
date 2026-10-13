"""Decimal helpers for the pricing engine (private to ``bpf.pricing``).

Money and quantities are ``Decimal``. Results must not depend on whatever decimal context the caller has
set, so every public engine function runs inside :func:`exact`: precision 100, which makes additions and
multiplications of the engine's values exact. Division is the only operation that rounds, and it goes
through :func:`div` (28 significant digits, ROUND_HALF_EVEN) so it rounds the same way everywhere.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Sequence
from typing import TypeGuard
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)

_TRAPS = [InvalidOperation, DivisionByZero, Overflow]
_EXACT = Context(prec=100, rounding=ROUND_HALF_EVEN, Emax=999_999, Emin=-999_999, traps=_TRAPS)
_DIV = Context(prec=28, rounding=ROUND_HALF_EVEN, Emax=999_999, Emin=-999_999, traps=_TRAPS)

ZERO = Decimal(0)
ONE = Decimal(1)


def exact[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Run ``fn`` in the engine's exact decimal context (precision 100), whatever the caller's context."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        with localcontext(_EXACT):
            return fn(*args, **kwargs)

    return wrapper


def div(a: Decimal, b: Decimal | int) -> Decimal:
    """``a / b`` rounded to 28 significant digits (ROUND_HALF_EVEN). Raises on division by zero."""
    return _DIV.divide(a, b)


def is_positive(value: Decimal | None) -> TypeGuard[Decimal]:
    """True for a finite Decimal > 0 (None, NaN, infinities, zero and negatives are False)."""
    return value is not None and value.is_finite() and value > 0


def median(values: Sequence[Decimal]) -> Decimal:
    """Median of a non-empty sequence; the mean of the two middle values for an even count (exact)."""
    if not values:
        raise ValueError("median of an empty sequence")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    with localcontext(_EXACT):
        return (ordered[mid - 1] + ordered[mid]) / 2


def decimals(value: Decimal) -> int:
    """Number of digits after the decimal point in ``value``'s representation (0 for integers)."""
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):  # 'n', 'N', 'F': NaN or infinity
        raise ValueError(f"not a finite number: {value!r}")
    return max(0, -exponent)


def to_scaled_int(value: Decimal, places: int) -> int:
    """``value * 10**places`` as an exact int (pure integer arithmetic, no context rounding).

    ``places`` must be >= ``decimals(value)``."""
    sign, digits, exponent = value.as_tuple()
    if not isinstance(exponent, int):
        raise ValueError(f"not a finite number: {value!r}")
    shift = places + exponent
    if shift < 0:
        raise ValueError(f"{value!r} has more than {places} decimals")
    mantissa = int("".join(map(str, digits))) if digits else 0
    return (-1 if sign else 1) * mantissa * 10**shift


def from_scaled_int(value: int, places: int) -> Decimal:
    """Inverse of :func:`to_scaled_int`: ``value * 10**-places`` as an exact Decimal (no rounding)."""
    digits = tuple(int(ch) for ch in str(abs(value)))
    return Decimal((1 if value < 0 else 0, digits, -places))
