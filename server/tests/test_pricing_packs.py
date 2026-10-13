"""Pack options and exact pack optimisation (ENGINE.md ``pack_options``, ``optimise_packs``;
research/recipe-coverage/notes.md §8.A-B and §10). Pack sizes/prices mirror the documented examples;
all data is synthetic."""

from __future__ import annotations

import itertools
import math
import random
import time
from collections.abc import Sequence
from decimal import Decimal
from fractions import Fraction

import pytest

import bpf.pricing.packs as packs
from bpf.pricing import Ingredient, LinePick, PackOption, optimise_packs, pack_options, to_canonical
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


def opt(pid: str, size: str | None, price: str | int) -> PackOption:
    size_d = None if size is None else D(size)
    price_d = D(price)
    unit_price = price_d if size_d is None or size_d <= 0 else price_d / size_d
    return PackOption(pid, f"name {pid}", size_d, price_d, unit_price, "NORMAL", "chain", "assumed")


def summary(picks: Sequence[LinePick] | None) -> list[tuple[str, int, Decimal, Decimal]]:
    assert picks is not None
    return [(p.option.product_id, p.count, p.qty, p.cost) for p in picks]


def total(picks: Sequence[LinePick] | None) -> Decimal:
    assert picks is not None
    return sum((p.cost for p in picks), D(0))


# ───────────── pack_options ─────────────


def _one_store_catalogue(products: list, prices: list, ing_list: list):  # type: ignore[no-untyped-def]
    return catalogue(
        ingredients=ing_list,
        products=products,
        chains=[chain("alfa")],
        stores=[store("a1", "alfa")],
        chain_prices=prices,
    )


def test_pack_options_fixed_pack_in_canonical_units() -> None:
    sour_cream = ingredient("tejfol12", leaf_ids=[6])
    cat = _one_store_catalogue(
        [product("t450", "Tejföl 12% 450 g", 6, packaging="0.45")],
        [chain_price("t450", "alfa", 359)],
        [sour_cream],
    )
    (option,) = pack_options(sour_cream, cat.stores["a1"], cat)
    assert option.size == D("0.45")
    assert option.price == D(359)
    assert option.unit_price == D("797.7777777777777777777777778")  # 359 / 0.45, recomputed
    assert (option.price_type, option.scope, option.availability) == ("NORMAL", "chain", "assumed")
    assert not option.variable_weight


@pytest.mark.parametrize("title", ["kg", "KG", " Kg "])
def test_unit_title_kg_is_variable_weight_even_with_packaging(title: str) -> None:
    tomato = ingredient("paradicsom", leaf_ids=[34])
    cat = _one_store_catalogue(
        [product("p1", "Paradicsom 1kg", 34, unit_title=title, packaging="1")],
        [chain_price("p1", "alfa", 429)],
        [tomato],
    )
    (option,) = pack_options(tomato, cat.stores["a1"], cat)
    assert option.size is None
    assert option.price == D(429)
    assert option.unit_price == D(429)


def test_no_packaging_is_variable_weight() -> None:
    chicken = ingredient("csirkecomb", leaf_ids=[19])
    cat = _one_store_catalogue(
        [product("c1", "Friss csirkecomb, kg", 19, unit_title="csomag", packaging=None)],
        [chain_price("c1", "alfa", 755)],
        [chicken],
    )
    (option,) = pack_options(chicken, cat.stores["a1"], cat)
    assert option.variable_weight
    assert option.price == D(755)


def test_db_product_without_packaging_is_one_piece_not_sold_by_weight() -> None:
    # "Karfiol db" (999 Ft/db): a per-piece product with no packaging is bought in whole pieces.
    cauliflower = ingredient("karfiol", leaf_ids=[44], piece_weight="0.75")
    cat = _one_store_catalogue(
        [product("k1", "Karfiol db", 44, unit="db", unit_title="csomag", packaging=None)],
        [chain_price("k1", "alfa", 999)],
        [cauliflower],
    )
    (option,) = pack_options(cauliflower, cat.stores["a1"], cat)
    assert not option.variable_weight
    assert option.size == D("0.75")
    assert option.price == D(999)
    (pick,) = optimise_packs(D("0.5"), [option])
    assert pick.count == 1
    assert pick.cost == D(999)


def test_db_pack_for_kg_ingredient_uses_piece_weight() -> None:
    onion = ingredient("voroshagyma", leaf_ids=[40], piece_weight="0.12")
    cat = _one_store_catalogue(
        [product("h3", "Vöröshagyma 3 db", 40, unit="db", packaging="3")],
        [chain_price("h3", "alfa", 99)],
        [onion],
    )
    (option,) = pack_options(onion, cat.stores["a1"], cat)
    assert option.size == D("0.36")
    assert option.price == D(99)
    assert option.unit_price == D(275)  # 99 / 0.36


def test_loose_db_product_priced_per_piece_becomes_per_kg() -> None:
    # "Sárgarépa csomós": unit db, unitTitle kg; the amount is per product unit (per db).
    carrot = ingredient("sargarepa", leaf_ids=[36], piece_weight="0.08")
    cat = _one_store_catalogue(
        [product("r1", "Sárgarépa csomós", 36, unit="db", unit_title="kg", packaging="1")],
        [chain_price("r1", "alfa", 40)],
        [carrot],
    )
    (option,) = pack_options(carrot, cat.stores["a1"], cat)
    assert option.size is None
    assert option.price == D(500)


def test_loose_kg_product_for_db_ingredient_is_per_piece() -> None:
    lemon = ingredient("citrom", unit="db", leaf_ids=[32], piece_weight="0.1")
    cat = _one_store_catalogue(
        [product("l1", "Citrom lédig", 32, unit_title="kg")],
        [chain_price("l1", "alfa", 799)],
        [lemon],
    )
    (option,) = pack_options(lemon, cat.stores["a1"], cat)
    assert option.size is None
    assert option.price == D("79.9")


def test_pack_options_skip_unpriced_and_carry_price_metadata_ordered_by_id() -> None:
    yoghurt = ingredient("joghurt", leaf_ids=[7])
    cat = catalogue(
        ingredients=[yoghurt],
        products=[
            product("j3", "Joghurt 500 g", 7, packaging="0.5"),
            product("j1", "Joghurt 175 g", 7, packaging="0.175"),
            product("j2", "Joghurt 1 kg", 7, packaging="1"),
        ],
        chains=[chain("alfa")],
        stores=[store("a1", "alfa")],
        chain_prices=[chain_price("j3", "alfa", 249), chain_price("j1", "alfa", 75)],
        store_prices=[store_price("j3", "a1", discounted=199, normal=249)],
        availability={("j1", "chain-alfa"): {"a1"}},
    )
    options = pack_options(yoghurt, cat.stores["a1"], cat)
    assert [(o.product_id, o.price, o.price_type, o.scope, o.availability) for o in options] == [
        ("j1", D(75), "NORMAL", "chain", "confirmed"),
        ("j3", D(199), "DISCOUNTED", "store", "confirmed"),
    ]


# ───────────── optimise_packs: documented examples ─────────────

SOUR_CREAM = [opt("t175", "0.175", 149), opt("t450", "0.45", 359)]


def test_tejfol_200g_buys_two_small_packs() -> None:
    # 2 x 0.175 = 0.35 kg for 298 Ft beats 0.45 kg for 359 Ft (research §8.A, T03).
    picks = optimise_packs(D("0.2"), SOUR_CREAM)
    assert summary(picks) == [("t175", 2, D("0.350"), D(298))]


def test_tejfol_60g_buys_one_small_pack() -> None:
    assert summary(optimise_packs(D("0.06"), SOUR_CREAM)) == [("t175", 1, D("0.175"), D(149))]


def test_mixed_combination_450_plus_175() -> None:
    # 0.6 kg: 4 x 0.175 = 596, 2 x 0.45 = 718, 0.45 + 0.175 = 508 (cheapest, 0.025 kg left over).
    picks = optimise_packs(D("0.6"), SOUR_CREAM)
    assert summary(picks) == [("t175", 1, D("0.175"), D(149)), ("t450", 1, D("0.45"), D(359))]


@pytest.mark.parametrize(
    ("eggs", "expected"),
    [
        ("1", [("e10", 1)]),  # 455 for a 45.5 Ft need (research §8.A)
        ("10", [("e10", 1)]),
        ("12", [("e10", 2)]),  # 910 < 1290
        ("25", [("e30", 1)]),  # 1290 < 3 x 455 = 1365
        ("31", [("e10", 1), ("e30", 1)]),  # 1745 < 2 x 1290 and < 4 x 455
    ],
)
def test_eggs_with_10_and_30_packs(eggs: str, expected: list[tuple[str, int]]) -> None:
    picks = optimise_packs(D(eggs), [opt("e10", "10", 455), opt("e30", "30", 1290)])
    assert [(p.option.product_id, p.count) for p in picks or ()] == expected


def test_variable_weight_is_bought_exactly() -> None:
    picks = optimise_packs(D("0.237"), [opt("loose", None, 799)])
    assert summary(picks) == [("loose", 1, D("0.237"), D("189.363"))]


def test_variable_weight_combines_with_packs() -> None:
    # 0.6 kg tomatoes: 0.5 kg pack (350) + 0.1 kg loose (80) = 430 < 0.6 kg loose (480) < 2 packs (700).
    picks = optimise_packs(D("0.6"), [opt("pack", "0.5", 350), opt("loose", None, 800)])
    assert summary(picks) == [("loose", 1, D("0.100"), D("80.000")), ("pack", 1, D("0.5"), D(350))]


def test_pack_dearer_than_loose_is_never_used() -> None:
    picks = optimise_packs(D("1"), [opt("pack", "1", 900), opt("loose", None, 800)])
    assert summary(picks) == [("loose", 1, D(1), D(800))]


def test_only_the_cheapest_loose_option_is_used() -> None:
    picks = optimise_packs(D("0.3"), [opt("b", None, 700), opt("a", None, 650), opt("c", None, 650)])
    assert summary(picks) == [("a", 1, D("0.3"), D("195.0"))]


# ───────────── optimise_packs: tie-breaks ─────────────


def test_tie_identical_packs_choose_lower_product_id() -> None:
    picks = optimise_packs(D("0.3"), [opt("b", "0.5", 300), opt("a", "0.5", 300)])
    assert summary(picks) == [("a", 1, D("0.5"), D(300))]


def test_tie_equal_cost_prefers_less_leftover() -> None:
    # Both cost 300: 1 kg (0.2 kg left) vs 0.8 kg (0 left).
    picks = optimise_packs(D("0.8"), [opt("a", "1", 300), opt("b", "0.8", 300)])
    assert summary(picks) == [("b", 1, D("0.8"), D(300))]


def test_tie_equal_cost_and_leftover_prefers_fewer_packs() -> None:
    # 1 kg for 200 vs 2 x 0.5 kg for 2 x 100.
    picks = optimise_packs(D("1"), [opt("a", "0.5", 100), opt("b", "1", 200)])
    assert summary(picks) == [("b", 1, D(1), D(200))]


def test_tie_everything_equal_prefers_more_of_the_lower_product_id() -> None:
    # 0.6 kg: 0.3 + 0.3 (a) or 0.2 + 0.4 (b + c): both 2 packs, 600 Ft, no leftover -> "a" sorts first.
    options = [opt("c", "0.4", 400), opt("b", "0.2", 200), opt("a", "0.3", 300)]
    picks = optimise_packs(D("0.6"), options)
    assert summary(picks) == [("a", 2, D("0.6"), D(600))]


def test_result_is_independent_of_input_order() -> None:
    options = [opt("x", "0.175", 149), opt("y", "0.45", 359), opt("z", None, 820), opt("w", "1", 790)]
    reference = summary(optimise_packs(D("1.3"), options))
    for permutation in itertools.permutations(options):
        assert summary(optimise_packs(D("1.3"), permutation)) == reference


# ───────────── optimise_packs: edge cases ─────────────


def test_no_options_is_none() -> None:
    assert optimise_packs(D(1), []) is None


@pytest.mark.parametrize("qty", ["0", "-1"])
def test_nothing_needed_buys_nothing(qty: str) -> None:
    assert optimise_packs(D(qty), SOUR_CREAM) == ()


@pytest.mark.parametrize(
    ("qty", "options"),
    [
        (D("NaN"), SOUR_CREAM),
        (D("Infinity"), SOUR_CREAM),
        (D(1), [opt("a", "0", 100)]),
        (D(1), [opt("a", "-1", 100)]),
        (D(1), [opt("a", "1", -1)]),
        (D(1), [PackOption("a", "a", D(1), D("NaN"), D(1), "NORMAL", "chain", "assumed")]),
    ],
)
def test_invalid_input_raises(qty: Decimal, options: list[PackOption]) -> None:
    with pytest.raises(ValueError, match="must be"):
        optimise_packs(qty, options)


def test_free_pack_is_allowed_and_used() -> None:
    picks = optimise_packs(D(1), [opt("free", "0.5", 0), opt("paid", "1", 100)])
    assert summary(picks) == [("free", 2, D("1.0"), D(0))]


def test_large_quantity_with_non_terminating_sizes_is_fast_and_covers() -> None:
    # kg packs for a per-piece ingredient: sizes like 0.2 / 0.067 = 2.98507... pieces.
    garlic = ingredient("fokhagyma", unit="db", piece_weight="0.067")
    options = []
    for pid, kg, price in [("a", "0.2", 300), ("b", "0.5", 750), ("c", "1", 1500), ("d", "0.25", 375)]:
        size = to_canonical(D(kg), "kg", garlic)
        assert size is not None
        options.append(PackOption(pid, pid, size, D(price), D(price) / size, "NORMAL", "chain", "assumed"))
    started = time.perf_counter()
    picks = optimise_packs(D(1000), options)
    assert time.perf_counter() - started < 0.5
    assert picks is not None
    assert sum(p.qty for p in picks) >= D(1000)


# ───────────── optimise_packs vs a brute-force reference ─────────────


def _rank_order(options: Sequence[PackOption]) -> dict[int, int]:
    order = sorted(range(len(options)), key=lambda i: (options[i].product_id, i))
    return {index: rank for rank, index in enumerate(order)}


def _reference_key(qty: Decimal, options: Sequence[PackOption]) -> tuple[object, ...]:
    """Brute force over every purchase: each fixed pack i bought 0..ceil(qty/s_i) times (an optimum never
    needs more: dropping one pack would still cover qty, which is strictly cheaper or leaves less), plus,
    when the packs fall short, the exact remaining weight from one variable-weight option (a weight split
    across two loose options never costs less and adds a pick). The key is the documented order:
    (cost, leftover, picks, more of the lower-ranked product id first)."""
    rank = _rank_order(options)
    q = Fraction(qty)
    fixed = [i for i, o in enumerate(options) if o.size is not None]
    loose = [i for i, o in enumerate(options) if o.size is None]
    best: tuple[object, ...] | None = None
    ranges = [range(int(-(-q // Fraction(options[i].size or 1))) + 1) for i in fixed]
    for counts in itertools.product(*ranges):
        covered = sum(c * Fraction(options[i].size or 0) for c, i in zip(counts, fixed, strict=True))
        cost = sum(c * Fraction(options[i].price) for c, i in zip(counts, fixed, strict=True))
        pairs = [(rank[i], -c) for c, i in zip(counts, fixed, strict=True) if c]
        variants: list[tuple[Fraction, Fraction, list[tuple[int, int]]]] = []
        if covered >= q:
            variants.append((cost, covered - q, pairs))
        else:
            for i in loose:
                weight = q - covered
                variants.append(
                    (cost + weight * Fraction(options[i].price), Fraction(0), [*pairs, (rank[i], -1)])
                )
        for v_cost, leftover, v_pairs in variants:
            key = (v_cost, leftover, -sum(c for _, c in v_pairs), tuple(sorted(v_pairs)))
            if best is None or key < best:
                best = key
    assert best is not None
    return best


def _result_key(qty: Decimal, options: Sequence[PackOption], picks: Sequence[LinePick]) -> tuple[object, ...]:
    rank = _rank_order(options)
    index_of = {id(o): i for i, o in enumerate(options)}
    cost = sum((Fraction(p.cost) for p in picks), Fraction(0))
    bought = sum((Fraction(p.qty) for p in picks), Fraction(0))
    pairs = [(rank[index_of[id(p.option)]], -p.count) for p in picks]
    for p in picks:  # internal consistency of every pick, checked exactly (no decimal context involved)
        if p.option.size is None:
            assert p.count == 1
            assert Fraction(p.cost) == Fraction(p.option.price) * Fraction(p.qty)
        else:
            assert Fraction(p.qty) == Fraction(p.option.size) * p.count
            assert Fraction(p.cost) == Fraction(p.option.price) * p.count
    return (cost, bought - Fraction(qty), -sum(c for _, c in pairs), tuple(sorted(pairs)))


_SIZES = ("0.1", "0.125", "0.175", "0.2", "0.25", "0.3", "0.33", "0.4", "0.45", "0.5", "0.75", "1", "2")
_PIECES = ("1", "4", "6", "10", "12", "15", "30")
_PRICES = (99, 100, 149, 150, 199, 200, 249, 299, 300, 359, 399, 450, 455, 599, 600, 999, 1290)


def _random_case(rng: random.Random) -> tuple[Decimal, list[PackOption]]:
    pieces = rng.random() < 0.25
    options: list[PackOption] = []
    for _ in range(rng.randint(1, 5)):
        pid = rng.choice("abcdef")  # small alphabet: duplicate product ids happen and must be stable
        if not pieces and rng.random() < 0.2:
            options.append(opt(pid, None, rng.choice(("299", "450", "799", "1000.5", "1200"))))
            continue
        size = rng.choice(_PIECES if pieces else _SIZES)
        if rng.random() < 0.25:  # proportional pricing creates exact unit-price ties
            price = str(D(size) * rng.choice((40, 800, 1000)))
        else:
            price = str(rng.choice(_PRICES)) if rng.random() < 0.9 else f"{rng.choice(_PRICES)}.5"
        options.append(opt(pid, size, price))
    qty = D(rng.randint(1, 40)) if pieces else D(rng.randint(1, 2500)) / 1000
    return qty, options


def _search_space(qty: Decimal, options: Sequence[PackOption]) -> int:
    space = 1
    for o in options:
        if o.size is not None:
            space *= int(-(-Fraction(qty) // Fraction(o.size))) + 1
    return space


def test_optimiser_matches_brute_force_on_500_seeded_cases() -> None:
    rng = random.Random(20261013)  # noqa: S311 - seeded test cases, not security
    checked = 0
    elapsed = 0.0
    while checked < 500:
        qty, options = _random_case(rng)
        if _search_space(qty, options) > 4_000:  # keep the brute force fast
            continue
        started = time.perf_counter()
        picks = optimise_packs(qty, options)
        elapsed += time.perf_counter() - started
        assert picks is not None
        assert _result_key(qty, options, picks) == _reference_key(qty, options), (qty, options)
        checked += 1
    mean_ms = elapsed / checked * 1000
    print(f"\noptimise_packs: {checked} cases, mean {mean_ms:.3f} ms per call")
    assert mean_ms <= 2.0  # ENGINE.md: <= 2 ms typical per call


def test_optimiser_does_not_depend_on_the_callers_decimal_context() -> None:
    from decimal import localcontext

    options = [opt("loose", None, "1234.5"), opt("pack", "0.5", 350)]
    expected = optimise_packs(D("0.6789"), options)
    with localcontext() as ctx:
        ctx.prec = 3
        degraded = optimise_packs(D("0.6789"), options)
    assert degraded == expected
    # 1 pack + 0.1789 kg loose = 350 + 220.85205 = 570.85205 (2 packs 700, all loose 838.10)
    assert total(expected) == D("570.85205")


def _hard_case(rng: random.Random, garlic: Ingredient) -> tuple[Decimal, list[PackOption]]:
    """Mixes kg packs converted to pieces (non-terminating sizes such as 2.9850746...), piece packs with
    proportional (tied) prices, free packs and free/cheap loose options."""
    options: list[PackOption] = []
    for _ in range(rng.randint(1, 7)):
        pid = rng.choice("abcdefgh")
        roll = rng.random()
        if roll < 0.15:
            price = D(rng.choice(["0", "10", "45.5", "52", "60.25"]))
            options.append(PackOption(pid, pid, None, price, price, "NORMAL", "chain", "assumed"))
            continue
        if roll < 0.5:
            size = to_canonical(D(rng.choice(["0.1", "0.2", "0.25", "0.5", "0.75", "1"])), "kg", garlic)
            assert size is not None
            price = D(rng.choice([0, 99, 150, 300, 375, 450, 750, 1500]))
        else:
            size = D(rng.choice(["1", "2", "3", "4", "6", "10", "12", "15", "30"]))
            tied = rng.random() < 0.15
            price = (
                size * rng.choice((43, 45, 50)) if tied else D(rng.choice([0, 45, 99, 150, 270, 455, 1290]))
            )
        options.append(PackOption(pid, pid, size, price, price, "NORMAL", "chain", "assumed"))
    qty = D(rng.randint(1, 40)) if rng.random() < 0.7 else D(rng.randint(1, 4000)) / 100
    return qty, options


def test_optimiser_matches_brute_force_on_hard_cases() -> None:
    rng = random.Random(7)  # noqa: S311 - seeded test cases, not security
    checked = 0
    while checked < 150:
        piece = rng.choice(["0.067", "0.06", "0.12", "0.333"])
        qty, options = _hard_case(rng, ingredient("fokhagyma", unit="db", piece_weight=piece))
        if _search_space(qty, options) > 2_000:
            continue
        picks = optimise_packs(qty, options)
        assert picks is not None
        assert _result_key(qty, options, picks) == _reference_key(qty, options), (qty, options)
        checked += 1


# ───────────── optimise_packs: many packs of near-equal unit price ─────────────

# Proportionally priced packs of one product (about 2375 Ft/kg, within 1 %): the unit-price lower bound is
# nearly tight, so a plain search over the pack counts explodes (one such call used to take minutes).
NEAR_EQUAL = [
    opt(f"p{index:02d}", size, price)
    for index, (size, price) in enumerate(
        [
            ("0.3", 714),
            ("1", 2375),
            ("0.75", 1781),
            ("0.33", 789),
            ("0.9", 2147),
            ("0.25", 594),
            ("0.45", 1069),
            ("0.175", 416),
            ("0.2", 475),
            ("0.8", 1900),
            ("0.4", 950),
            ("0.5", 1188),
            ("0.35", 831),
            ("0.125", 297),
        ]
    )
]
# Exactly proportional (2400 Ft/kg): every purchase costs the same per kg, the bound prunes nothing.
PROPORTIONAL = [
    opt(f"q{index:02d}", size, str(D(size) * 2400))
    for index, size in enumerate(["0.2", "0.35", "0.175", "0.4", "0.3", "0.8", "1", "0.75", "0.5", "0.25"])
]


def _grid_reference_key(qty: Decimal, options: Sequence[PackOption]) -> tuple[object, ...]:
    """Independent exact reference: a dynamic programme over every quantity on the pack-size grid (the
    lexicographic purchase key is additive, so the best purchase of each exact quantity extends the best of a
    smaller one), then the cheapest way to reach ``qty`` from each quantity (nothing, or loose weight)."""
    rank = _rank_order(options)
    fixed = [i for i, o in enumerate(options) if o.size is not None]
    loose = [i for i, o in enumerate(options) if o.size is None]
    sizes = {i: Fraction(options[i].size or 0) for i in fixed}
    grid = Fraction(
        math.gcd(*(s.numerator for s in sizes.values())), math.lcm(*(s.denominator for s in sizes.values()))
    )
    steps = {i: int(sizes[i] / grid) for i in fixed}
    q = Fraction(qty)
    top = math.ceil(q / grid) + max(steps.values())
    best: list[tuple[Fraction, int, tuple[int, ...]] | None] = [None] * (top + 1)
    best[0] = (Fraction(0), 0, (0,) * len(options))
    for amount in range(1, top + 1):
        for i in fixed:
            previous = best[amount - steps[i]] if steps[i] <= amount else None
            if previous is None:
                continue
            cost, picks, vector = previous
            moved = list(vector)
            moved[rank[i]] -= 1
            candidate = (cost + Fraction(options[i].price), picks + 1, tuple(moved))
            current = best[amount]
            if current is None or candidate < current:
                best[amount] = candidate
    overall: tuple[Fraction, Fraction, int, tuple[int, ...]] | None = None
    for amount, entry in enumerate(best):
        if entry is None:
            continue
        cost, picks, vector = entry
        bought = amount * grid
        keys: list[tuple[Fraction, Fraction, int, tuple[int, ...]]] = []
        if bought >= q:
            keys.append((cost, bought - q, picks, vector))
        else:
            for i in loose:
                moved = list(vector)
                moved[rank[i]] -= 1
                keys.append(
                    (cost + (q - bought) * Fraction(options[i].price), Fraction(0), picks + 1, tuple(moved))
                )
        for key in keys:
            if overall is None or key < overall:
                overall = key
    assert overall is not None
    cost, leftover, picks, vector = overall
    return (cost, leftover, picks, tuple((r, c) for r, c in enumerate(vector) if c))  # as _result_key


def _b_alone_cost(qty: Decimal, options: Sequence[PackOption]) -> Decimal:
    """Cost of covering qty with the best-unit-price pack alone (what any search result must not exceed)."""
    fixed = [o for o in options if o.size is not None]
    best = min(fixed, key=lambda o: (o.price / (o.size or 1), -(o.size or 0)))
    return best.price * math.ceil(qty / (best.size or 1))


@pytest.mark.parametrize(
    ("qty", "options", "expected_cost"),
    [
        (D("25.628"), NEAR_EQUAL, D(60_859)),
        (D("10.001"), NEAR_EQUAL, D(23_761)),
        (D("92.382"), PROPORTIONAL, D(221_760)),
        (D("97.721"), PROPORTIONAL, D(234_540)),
    ],
)
def test_many_packs_of_near_equal_unit_price_are_fast_and_exact(
    qty: Decimal, options: list[PackOption], expected_cost: Decimal
) -> None:
    started = time.perf_counter()
    picks = optimise_packs(qty, options)
    elapsed = time.perf_counter() - started
    assert elapsed < 0.5, f"{elapsed:.3f} s"
    assert picks is not None
    assert sum(p.qty for p in picks) >= qty
    assert total(picks) == expected_cost
    assert total(picks) <= _b_alone_cost(qty, options)
    assert _result_key(qty, options, picks) == _grid_reference_key(qty, options)


def _near_equal_case(rng: random.Random) -> tuple[Decimal, list[PackOption]]:
    """6-14 packs within about 1.5 % of one unit price (some exactly proportional), sometimes a loose option,
    up to 30 kg: the inputs that used to make the search explode."""
    sizes = (
        "0.1",
        "0.125",
        "0.175",
        "0.2",
        "0.25",
        "0.3",
        "0.33",
        "0.35",
        "0.4",
        "0.45",
        "0.5",
        "0.75",
        "1",
        "2",
    )
    base = rng.choice((800, 2375, 2400, 3990))
    options: list[PackOption] = []
    for index, size in enumerate(rng.sample(sizes, rng.randint(6, 14))):
        exact = D(size) * base
        price = exact if rng.random() < 0.4 else (exact * (1 + D(rng.randint(-15, 15)) / 1000)).quantize(D(1))
        options.append(opt(f"{rng.choice('abcdef')}{index % 3}", size, str(price)))
    if rng.random() < 0.3:
        options.append(opt("loose", None, str(base + rng.randint(-10, 40))))
    return D(rng.randint(1, 30_000)) / 1000, options


def test_optimiser_matches_a_dynamic_programme_on_large_near_equal_cases() -> None:
    rng = random.Random(20261014)  # noqa: S311 - seeded test cases, not security
    slowest = 0.0
    for _ in range(40):
        qty, options = _near_equal_case(rng)
        started = time.perf_counter()
        picks = optimise_packs(qty, options)
        slowest = max(slowest, time.perf_counter() - started)
        assert picks is not None
        assert _result_key(qty, options, picks) == _grid_reference_key(qty, options), (qty, options)
    print(f"\nnear-equal unit prices: slowest optimise_packs call {slowest * 1000:.1f} ms")
    assert slowest < 0.5


def test_search_cap_returns_a_covering_purchase_no_worse_than_the_best_pack_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A tiny cap stops the search early: the result is then the best purchase found so far, which always
    # covers qty and never costs more than the best-unit-price pack alone (the first purchase considered).
    monkeypatch.setattr(packs, "MAX_SEARCH_STEPS", 3)
    for qty in (D("25.628"), D("0.4"), D("3.333")):
        picks = optimise_packs(qty, NEAR_EQUAL)
        assert picks
        assert sum(p.qty for p in picks) >= qty
        assert total(picks) <= _b_alone_cost(qty, NEAR_EQUAL)
    monkeypatch.undo()
    assert total(optimise_packs(D("25.628"), NEAR_EQUAL)) == D(60_859)  # uncapped: the exact optimum
