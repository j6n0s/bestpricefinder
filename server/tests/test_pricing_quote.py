"""Quoting a list at one store (ENGINE.md ``quote_store``; ``model.LineStatus``). Synthetic data only."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from bpf.pricing import Catalogue, KshPrice, QuoteLine, StoreQuote, quote_store
from tests.fixtures.pricing.builders import (
    catalogue,
    chain,
    chain_price,
    ingredient,
    product,
    store,
    store_price,
)

D = Decimal
PERIOD = date(2026, 9, 1)

INGREDIENTS = [
    ingredient("tejfol12", leaf_ids=[6]),
    ingredient("olaj", unit="l", leaf_ids=[51], pantry=True),  # pantry WITH a GVH mapping
    ingredient("so", pantry=True),  # pantry, no mapping
    ingredient("pirospaprika", pantry=True, ksh_code="K-PAPRIKA"),  # pantry wins over KSH
    ingredient("zabpehely", ksh_code="K-ZAB"),  # KSH only
    ingredient("tojas_ksh", unit="db", ksh_code="K-TOJAS", piece_weight="0.06"),
    ingredient("tojas_ksh_kg", unit="kg", ksh_code="K-TOJAS", piece_weight="0.0625"),
    ingredient("tonhal", ksh_code="K-MISSING"),  # code not in the KSH table
    ingredient("tojas_ksh_l", unit="l", ksh_code="K-TOJAS"),  # KSH unit not convertible
    ingredient("spenot"),  # nothing at all
    ingredient("lazac", leaf_ids=[93]),  # GVH-mapped, not sold by this chain
]
PRODUCTS = [
    product("t175", "Tejföl 12% 175 g", 6, packaging="0.175"),
    product("t450", "Tejföl 12% 450 g", 6, packaging="0.45"),
    product("t800", "Tejföl 12% 800 g", 6, packaging="0.8"),
    product("t330", "Tejföl 12% 330 g", 6, packaging="0.33"),
    product("t1kg", "Tejföl 12% 1 kg", 6, packaging="1"),
    product("o1", "Napraforgó étolaj 1 l", 51, unit="l", packaging="1"),
    product("l1", "Lazacfilé 250 g", 93, packaging="0.25"),
]
KSH = [
    KshPrice("K-ZAB", "Zabpehely", "kg", D(1), D(800), PERIOD),
    KshPrice("K-TOJAS", "Tojás, 10 darab", "db", D(10), D(700), PERIOD),
    KshPrice("K-PAPRIKA", "Fűszerpaprika", "kg", D(1), D(9000), PERIOD),
]


def _cat(**overrides: object) -> Catalogue:
    params: dict[str, object] = {
        "ingredients": INGREDIENTS,
        "products": PRODUCTS,
        "chains": [chain("alfa"), chain("beta")],
        "stores": [store("a1", "alfa"), store("a2", "alfa")],
        "chain_prices": [
            chain_price("t175", "alfa", 149),
            chain_price("t450", "alfa", 359),
            chain_price("t800", "alfa", 640),
            chain_price("t330", "alfa", 299),
            chain_price("t1kg", "alfa", 850),
            chain_price("o1", "alfa", 749),
            chain_price("l1", "beta", 1599),
        ],
        "ksh": KSH,
    }
    params.update(overrides)
    return catalogue(**params)  # type: ignore[arg-type]


def _line(quote: StoreQuote, ingredient_id: str) -> QuoteLine:
    return next(line for line in quote.lines if line.ingredient_id == ingredient_id)


def test_statuses() -> None:
    cat = _cat()
    lines = [
        ("tejfol12", D("0.2")),
        ("olaj", D("0.05")),
        ("so", D("0.01")),
        ("pirospaprika", D("0.01")),
        ("zabpehely", D("0.5")),
        ("tonhal", D("0.2")),
        ("tojas_ksh_l", D("1")),
        ("spenot", D("0.3")),
        ("lazac", D("0.4")),
    ]
    quote = quote_store(lines, cat.stores["a1"], cat)
    assert [(line.ingredient_id, line.status) for line in quote.lines] == [
        ("tejfol12", "priced"),
        ("olaj", "priced"),  # pantry with leaves is priced whenever it is sent
        ("so", "pantry"),
        ("pirospaprika", "pantry"),  # pantry without a GVH mapping is never priced, not even via KSH
        ("zabpehely", "ksh_estimate"),
        ("tonhal", "unpriced"),
        ("tojas_ksh_l", "unpriced"),
        ("spenot", "unpriced"),
        ("lazac", "unavailable"),
    ]
    assert quote.missing == ("lazac",)
    for line in quote.lines:
        if line.status != "priced":
            assert line.picks == ()
            assert line.checkout_cost is None
            assert line.used_cost is None
            assert line.leftover_qty is None
            assert line.alternatives == ()
        if line.status != "ksh_estimate":
            assert line.ksh_estimate is None


def test_used_cost_vs_checkout_cost() -> None:
    cat = _cat()
    quote = quote_store([("tejfol12", D("0.2"))], cat.stores["a1"], cat)
    line = quote.lines[0]
    # Cheapest cover of 0.2 kg: 2 x 0.175 kg = 298 Ft (0.45 kg = 359, 0.33 kg = 299, 0.8 kg = 640).
    assert [(p.option.product_id, p.count) for p in line.picks] == [("t175", 2)]
    assert line.checkout_cost == D(298)
    assert line.leftover_qty == D("0.150")
    # used = 0.2 kg x 298 Ft / 0.35 kg = 170.2857... Ft
    assert line.used_cost == D("170.2857142857142857142857143")
    assert quote.checkout_total == D(298)
    assert quote.used_total == line.used_cost


def test_alternatives_exclude_picks_and_are_ordered_by_single_option_checkout() -> None:
    cat = _cat()
    line = quote_store([("tejfol12", D("0.2"))], cat.stores["a1"], cat).lines[0]
    # Single-option checkout for 0.2 kg: t330 299, t450 359, t800 640, t1kg 850 -> first three.
    assert [o.product_id for o in line.alternatives] == ["t330", "t450", "t800"]


def test_alternatives_ties_by_product_id_and_at_most_three() -> None:
    cat = _cat(
        chain_prices=[
            chain_price("t175", "alfa", 100),
            chain_price("t450", "alfa", 400),
            chain_price("t330", "alfa", 400),
            chain_price("t800", "alfa", 400),
            chain_price("t1kg", "alfa", 400),
        ]
    )
    line = quote_store([("tejfol12", D("0.1"))], cat.stores["a1"], cat).lines[0]
    assert [o.product_id for o in line.alternatives] == ["t1kg", "t330", "t450"]


def test_ksh_estimate_is_labelled_and_never_in_checkout_total() -> None:
    cat = _cat()
    quote = quote_store(
        [("zabpehely", D("0.5")), ("tojas_ksh", D(3)), ("tojas_ksh_kg", D("0.25")), ("tejfol12", D("0.1"))],
        cat.stores["a1"],
        cat,
    )
    assert _line(quote, "zabpehely").ksh_estimate == D(400)  # 0.5 kg x 800 Ft/kg
    assert _line(quote, "tojas_ksh").ksh_estimate == D(210)  # 3 db x 700 Ft / 10 db
    # 0.25 kg of eggs = 4 eggs (0.0625 kg each); KSH 10 eggs = 0.625 kg -> 0.25 x 700 / 0.625 = 280
    assert _line(quote, "tojas_ksh_kg").ksh_estimate == D(280)
    assert quote.ksh_estimate_total == D(890)
    assert quote.checkout_total == D(149)


def test_assumed_count_counts_lines_with_any_assumed_pick() -> None:
    cat = _cat(
        store_prices=[store_price("t175", "a1", normal=149)],  # confirmed by the store row
        availability={("o1", "chain-alfa"): {"a1"}},  # confirmed by the list
    )
    quote = quote_store(
        [("tejfol12", D("0.1")), ("olaj", D(1))],
        cat.stores["a1"],
        cat,
    )
    assert quote.assumed_count == 0
    mixed = quote_store([("tejfol12", D("0.6"))], cat.stores["a1"], cat)  # 0.45 (assumed) + 0.175 (store)
    assert {p.option.availability for p in mixed.lines[0].picks} == {"assumed", "confirmed"}
    assert mixed.assumed_count == 1


def test_store_without_data_makes_every_mapped_line_unavailable() -> None:
    dark = store("a9", "alfa", has_data=False)
    cat = _cat(stores=[dark])
    quote = quote_store([("tejfol12", D("0.1")), ("so", D("0.01"))], dark, cat)
    assert [line.status for line in quote.lines] == ["unavailable", "pantry"]
    assert quote.missing == ("tejfol12",)
    assert quote.checkout_total == 0


def test_include_loyalty_reaches_the_price() -> None:
    cat = _cat(chain_prices=[chain_price("t450", "alfa", 359, loyalty=299, same=True)])
    plain = quote_store([("tejfol12", D("0.4"))], cat.stores["a1"], cat)
    loyal = quote_store([("tejfol12", D("0.4"))], cat.stores["a1"], cat, include_loyalty=True)
    assert plain.checkout_total == D(359)
    assert plain.lines[0].picks[0].option.price_type == "NORMAL"
    assert loyal.checkout_total == D(299)
    assert loyal.lines[0].picks[0].option.price_type == "LOYALTY"


def test_lines_keep_input_order_and_totals_sum_priced_lines() -> None:
    cat = _cat()
    quote = quote_store([("olaj", D(2)), ("spenot", D(1)), ("tejfol12", D("0.45"))], cat.stores["a2"], cat)
    assert [line.ingredient_id for line in quote.lines] == ["olaj", "spenot", "tejfol12"]
    assert quote.store_id == "a2"
    assert quote.checkout_total == D(749 * 2 + 359)
    assert quote.used_total == D(749 * 2 + 359)  # no leftover: used == checkout


def test_unknown_ingredient_raises_key_error() -> None:
    cat = _cat()
    with pytest.raises(KeyError):
        quote_store([("nincs_ilyen", D(1))], cat.stores["a1"], cat)


@pytest.mark.parametrize("qty", ["0", "-0.1", "NaN"])
def test_non_positive_quantity_raises(qty: str) -> None:
    cat = _cat()
    with pytest.raises(ValueError, match="must be finite and > 0"):
        quote_store([("tejfol12", D(qty))], cat.stores["a1"], cat)


def test_empty_list_gives_zero_totals() -> None:
    cat = _cat()
    quote = quote_store([], cat.stores["a1"], cat)
    assert quote.lines == ()
    assert quote.checkout_total == 0
    assert quote.used_total == 0
    assert quote.missing == ()
    assert quote.assumed_count == 0
    assert quote.ksh_estimate_total == 0


def test_results_do_not_depend_on_the_callers_decimal_context() -> None:
    from decimal import localcontext

    cat = _cat()
    lines = [("tejfol12", D("0.6")), ("zabpehely", D("0.333")), ("olaj", D("0.07"))]
    expected = quote_store(lines, cat.stores["a1"], cat)
    with localcontext() as ctx:
        ctx.prec = 4
        degraded = quote_store(lines, cat.stores["a1"], cat)
    assert degraded == expected
    assert expected.lines[0].used_cost == D("487.68")  # 0.6 x 508 / 0.625, not rounded to 4 digits
