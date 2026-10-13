"""Store-vs-chain price rule (ENGINE.md ``resolve_price``; BUILD-BRIEF §4.1 traps 1 and 3;
research/gvh-location/verify.md "productMinAmount"). The amounts reproduce the documented cases (Spar
spaghetti, Tesco counter chicken, Spar paprika) as test inputs only; chains, stores and ids are fictional."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bpf.pricing import Catalogue, ResolvedPrice, Store, resolve_price
from tests.fixtures.pricing.builders import catalogue, chain, chain_price, product, store, store_price

D = Decimal
SPAGHETTI = product("syn-spagetti", "Don Francesco spagetti 500 g", 50, packaging="0.5")
STORE_1 = store("alfa-110", "alfa")
STORE_2 = store("alfa-120", "alfa")


def _cat(**kwargs: object) -> Catalogue:
    return catalogue(products=[SPAGHETTI], chains=[chain("alfa"), chain("beta")], **kwargs)  # type: ignore[arg-type]


def _resolve(cat: Catalogue, st: Store = STORE_1, *, loyalty: bool = False) -> ResolvedPrice | None:
    return resolve_price(SPAGHETTI, st, cat, include_loyalty=loyalty)


# ───────────── chain-typical price: productMinAmount, never the per-type minimum ─────────────


def test_product_min_amount_beats_normal_amount() -> None:
    # Spar spaghetti: prices[] NORMAL 294 (2 outlier stores), productMinAmount 699 (296 stores) -> 699.
    cat = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", 699, normal=294, same=False)])
    assert _resolve(cat) == ResolvedPrice(SPAGHETTI.id, "alfa-110", D(699), "NORMAL", "chain", "assumed")


def test_discounted_when_typical_price_is_the_discount() -> None:
    # Tesco counter chicken: NORMAL 2030 everywhere, DISCOUNTED 1699 in 118/119 stores, pma 1699.
    cat = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", 1699, normal=2030, discounted=1699)])
    resolved = _resolve(cat)
    assert resolved is not None
    assert (resolved.amount, resolved.price_type) == (D(1699), "DISCOUNTED")


def test_single_store_discount_does_not_label_the_typical_price() -> None:
    # Spar "Étkezési paprika lédig": NORMAL min 815, DISCOUNTED 399 in one store, pma 853 -> NORMAL 853.
    cat = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", 853, normal=815, discounted=399)])
    resolved = _resolve(cat)
    assert resolved is not None
    assert (resolved.amount, resolved.price_type) == (D(853), "NORMAL")


def test_discount_equal_to_normal_is_normal() -> None:
    cat = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", 500, normal=500, discounted=500)])
    resolved = _resolve(cat)
    assert resolved is not None
    assert resolved.price_type == "NORMAL"


def test_xlsx_fallback_only_when_min_equals_max() -> None:
    same = _cat(
        chain_prices=[chain_price(SPAGHETTI.id, "alfa", None, normal=480, xlsx_min=500, xlsx_max=500)]
    )
    resolved = _resolve(same)
    assert resolved is not None
    assert resolved.amount == D(500)
    assert resolved.price_type == "NORMAL"

    varies = _cat(
        chain_prices=[chain_price(SPAGHETTI.id, "alfa", None, normal=294, xlsx_min=294, xlsx_max=699)]
    )
    assert _resolve(varies) is None

    only_min = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", None, xlsx_min=294)])
    assert _resolve(only_min) is None

    nothing = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", None, normal=294, discounted=250)])
    assert _resolve(nothing) is None


def test_xlsx_fallback_is_labelled_discounted_when_it_is_the_discount() -> None:
    cat = _cat(
        chain_prices=[
            chain_price(SPAGHETTI.id, "alfa", None, normal=600, discounted=450, xlsx_min=450, xlsx_max=450)
        ]
    )
    resolved = _resolve(cat)
    assert resolved is not None
    assert (resolved.amount, resolved.price_type) == (D(450), "DISCOUNTED")


@pytest.mark.parametrize("bad", ["0", "-5"])
def test_non_positive_amounts_count_as_missing(bad: str) -> None:
    cat = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", bad, xlsx_min=500, xlsx_max=500)])
    resolved = _resolve(cat)
    assert resolved is not None
    assert resolved.amount == D(500)
    zero_everywhere = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", bad, xlsx_min=bad, xlsx_max=bad)])
    assert _resolve(zero_everywhere) is None


def test_no_row_for_this_chain_is_none() -> None:
    cat = _cat(chain_prices=[chain_price(SPAGHETTI.id, "beta", 650)])
    assert _resolve(cat) is None


# ───────────── LOYALTY ─────────────


@pytest.mark.parametrize(
    ("include", "same", "loyalty", "expected"),
    [
        (True, True, 599, (D(599), "LOYALTY")),
        (False, True, 599, (D(699), "NORMAL")),  # not requested
        (True, False, 599, (D(699), "NORMAL")),  # loyalty price not uniform across the chain
        (True, None, 599, (D(699), "NORMAL")),  # unknown uniformity
        (True, True, 699, (D(699), "NORMAL")),  # not below the typical price
        (True, True, 750, (D(699), "NORMAL")),
    ],
)
def test_chain_loyalty_rule(
    include: bool, same: bool | None, loyalty: int, expected: tuple[Decimal, str]
) -> None:
    cat = _cat(chain_prices=[chain_price(SPAGHETTI.id, "alfa", 699, loyalty=loyalty, same=same)])
    resolved = _resolve(cat, loyalty=include)
    assert resolved is not None
    assert (resolved.amount, resolved.price_type) == expected


# ───────────── per-store rows ─────────────


def test_store_row_beats_chain_row() -> None:
    cat = _cat(
        chain_prices=[chain_price(SPAGHETTI.id, "alfa", 699)],
        store_prices=[store_price(SPAGHETTI.id, "alfa-110", normal=750)],
    )
    assert _resolve(cat) == ResolvedPrice(SPAGHETTI.id, "alfa-110", D(750), "NORMAL", "store", "confirmed")
    # Another store of the same chain without a row keeps the chain price.
    other = _resolve(cat, STORE_2)
    assert other is not None
    assert (other.amount, other.scope) == (D(699), "chain")


def test_store_row_wins_even_without_a_chain_row() -> None:
    cat = _cat(store_prices=[store_price(SPAGHETTI.id, "alfa-110", normal=750)])
    resolved = _resolve(cat)
    assert resolved is not None
    assert resolved.scope == "store"


def test_store_row_takes_min_of_normal_and_discounted() -> None:
    cat = _cat(store_prices=[store_price(SPAGHETTI.id, "alfa-110", normal=750, discounted=599)])
    resolved = _resolve(cat)
    assert resolved is not None
    assert (resolved.amount, resolved.price_type) == (D(599), "DISCOUNTED")


def test_store_row_tie_is_reported_as_normal() -> None:
    cat = _cat(store_prices=[store_price(SPAGHETTI.id, "alfa-110", normal=599, discounted=599)])
    resolved = _resolve(cat)
    assert resolved is not None
    assert resolved.price_type == "NORMAL"


def test_store_row_loyalty_only_when_included() -> None:
    cat = _cat(store_prices=[store_price(SPAGHETTI.id, "alfa-110", normal=750, discounted=650, loyalty=550)])
    without = _resolve(cat)
    with_loyalty = _resolve(cat, loyalty=True)
    assert without is not None
    assert (without.amount, without.price_type) == (D(650), "DISCOUNTED")
    assert with_loyalty is not None
    assert (with_loyalty.amount, with_loyalty.price_type) == (D(550), "LOYALTY")


def test_store_row_without_usable_amount_falls_back_to_chain_and_proves_carriage() -> None:
    cat = _cat(
        chain_prices=[chain_price(SPAGHETTI.id, "alfa", 699)],
        store_prices=[store_price(SPAGHETTI.id, "alfa-110", loyalty=500)],  # LOYALTY only, not requested
        availability={(SPAGHETTI.id, "chain-alfa"): {"alfa-120"}},  # stale list without spar-110
    )
    resolved = _resolve(cat)
    assert resolved is not None
    assert (resolved.amount, resolved.scope, resolved.availability) == (D(699), "chain", "confirmed")


# ───────────── availability ─────────────


def test_availability_confirmed_assumed_and_not_carried() -> None:
    rows = [chain_price(SPAGHETTI.id, "alfa", 699)]
    listed = _cat(chain_prices=rows, availability={(SPAGHETTI.id, "chain-alfa"): {"alfa-110"}})
    confirmed = _resolve(listed)
    assert confirmed is not None
    assert confirmed.availability == "confirmed"
    assert _resolve(listed, STORE_2) is None  # list known, store not in it: not carried

    unknown = _cat(chain_prices=rows)
    assumed = _resolve(unknown, STORE_2)
    assert assumed is not None
    assert assumed.availability == "assumed"

    empty = _cat(chain_prices=rows, availability={(SPAGHETTI.id, "chain-alfa"): set()})
    assert _resolve(empty) is None


def test_availability_list_of_another_chain_does_not_apply() -> None:
    cat = _cat(
        chain_prices=[chain_price(SPAGHETTI.id, "alfa", 699)],
        availability={(SPAGHETTI.id, "chain-beta"): {"beta-1"}},
    )
    resolved = _resolve(cat)
    assert resolved is not None
    assert resolved.availability == "assumed"


def test_store_without_data_has_no_price() -> None:
    dark = store("alfa-dark", "alfa", has_data=False)
    cat = _cat(
        chain_prices=[chain_price(SPAGHETTI.id, "alfa", 699)],
        store_prices=[store_price(SPAGHETTI.id, "alfa-dark", normal=650)],
    )
    assert resolve_price(SPAGHETTI, dark, cat) is None
