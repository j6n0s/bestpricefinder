"""Per-chain price history from our own archive (ENGINE.md ``ingredient_history``). Synthetic data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from bpf.pricing import ingredient_history
from tests.fixtures.pricing.builders import catalogue, ingredient, product

D = Decimal
D1, D2, D3 = date(2026, 10, 11), date(2026, 10, 12), date(2026, 10, 13)

YOGHURT = ingredient("natur_joghurt", leaf_ids=[7], exclude=["gorog"])
CAT = catalogue(
    ingredients=[YOGHURT],
    products=[
        product("j175", "Natúr joghurt 175 g", 7, packaging="0.175"),
        product("j1kg", "Natúr joghurt 1 kg", 7, packaging="1"),
        product("jloose", "Natúr joghurt kimért", 7, unit_title="kg"),
        product("greek", "Görög joghurt 1 kg", 7, packaging="1"),  # excluded by the name rules
        product("other", "Kefir 1 kg", 8, packaging="1"),  # another leaf
    ],
)


def test_min_canonical_unit_price_per_chain_and_date_sorted() -> None:
    rows = [
        (D2, "j175", "chain-alfa", D(70)),  # 400/kg
        (D1, "j175", "chain-alfa", D(84)),  # 480/kg
        (D1, "j1kg", "chain-alfa", D(450)),  # 450/kg  <- min on D1
        (D2, "j1kg", "chain-alfa", D(450)),  # 450/kg
        (D2, "greek", "chain-alfa", D(100)),  # not a candidate
        (D2, "other", "chain-alfa", D(100)),  # not a candidate
        (D3, "jloose", "chain-beta", D(390)),  # sold by weight: 390/kg
        (D2, "jloose", "chain-beta", None),  # no price that day
        (D1, "unknown", "chain-beta", D(1)),  # unknown product
        (D3, "j175", "chain-beta", D(0)),  # non-positive: ignored
    ]
    history = ingredient_history(YOGHURT, CAT, rows)
    assert list(history) == ["chain-alfa", "chain-beta"]
    assert history["chain-alfa"] == ((D1, D(450)), (D2, D(400)))
    assert history["chain-beta"] == ((D3, D(390)),)


def test_unit_conversion_for_pieces() -> None:
    egg = ingredient("tojas", unit="db", leaf_ids=[14], piece_weight="0.06")
    cat = catalogue(
        ingredients=[egg],
        products=[
            product("e10", "Tojás 10 db", 14, unit="db", packaging="10"),
            product("ekg", "Tojás 1 kg", 14),
        ],
    )
    history = ingredient_history(egg, cat, [(D1, "e10", "c", D(500)), (D1, "ekg", "c", D(1000))])
    assert history == {"c": ((D1, D(50)),)}  # 500/10 = 50 per egg; 1000 Ft/kg x 0.06 = 60 per egg


def test_no_rows_gives_empty_history() -> None:
    assert ingredient_history(YOGHURT, CAT, []) == {}
    assert ingredient_history(YOGHURT, CAT, iter([(D1, "greek", "c", D(1))])) == {}
