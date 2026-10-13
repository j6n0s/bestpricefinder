"""Unit normalisation (ENGINE.md ``to_canonical``; BUILD-BRIEF §4.1 trap 5). Synthetic data only."""

from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from bpf.pricing import to_canonical
from tests.fixtures.pricing.builders import ingredient

D = Decimal


@pytest.mark.parametrize("unit", ["kg", "l", "db"])
def test_same_unit_is_identity(unit: str) -> None:
    ing = ingredient("x", unit=unit)  # type: ignore[arg-type]
    assert to_canonical(D("0.175"), unit, ing) == D("0.175")


def test_db_to_kg_via_piece_weight() -> None:
    onion = ingredient("voroshagyma", unit="kg", piece_weight="0.12")
    assert to_canonical(D(3), "db", onion) == D("0.36")


def test_kg_to_db_via_piece_weight() -> None:
    egg = ingredient("tojas", unit="db", piece_weight="0.0625")
    assert to_canonical(D("0.5"), "kg", egg) == D(8)


def test_kg_to_db_non_terminating_rounds_to_28_significant_digits() -> None:
    garlic = ingredient("fokhagyma", unit="db", piece_weight="0.067")
    result = to_canonical(D("0.2"), "kg", garlic)
    assert result == D("2.985074626865671641791044776")


def test_db_kg_without_piece_weight_is_not_convertible() -> None:
    assert to_canonical(D(1), "db", ingredient("a", unit="kg")) is None
    assert to_canonical(D(1), "kg", ingredient("b", unit="db")) is None


@pytest.mark.parametrize("bad", ["0", "-0.1"])
def test_non_positive_piece_weight_is_not_convertible(bad: str) -> None:
    assert to_canonical(D(1), "db", ingredient("a", unit="kg", piece_weight=bad)) is None


def test_l_to_kg_only_with_density() -> None:
    cream = ingredient("tejszin", unit="kg", density="1.03")
    assert to_canonical(D(2), "l", cream) == D("2.06")
    assert to_canonical(D("1.03"), "kg", ingredient("tej", unit="l", density="1.03")) == D(1)


def test_l_kg_without_density_is_none_even_with_piece_weight() -> None:
    ing = ingredient("tejfol", unit="kg", piece_weight="0.2")
    assert to_canonical(D(1), "l", ing) is None
    assert to_canonical(D(1), "kg", ingredient("tej", unit="l", piece_weight="1")) is None


def test_db_l_is_never_convertible() -> None:
    both = ingredient("x", unit="l", piece_weight="0.5", density="1")
    assert to_canonical(D(1), "db", both) is None
    assert to_canonical(D(1), "l", ingredient("y", unit="db", piece_weight="0.5", density="1")) is None


@pytest.mark.parametrize("unit", ["g", "ml", "csomag", "KG", "", "darab"])
def test_unknown_units_are_none(unit: str) -> None:
    ing = ingredient("x", unit="kg", piece_weight="0.1", density="1")
    assert to_canonical(D(1), unit, ing) is None


def test_result_does_not_depend_on_the_callers_decimal_context() -> None:
    ing = ingredient("x", unit="kg", piece_weight="0.1234")
    with localcontext() as ctx:
        ctx.prec = 3
        result = to_canonical(D("12.345"), "db", ing)
    assert result == D("1.5233730")  # 12.345 x 0.1234, exact
