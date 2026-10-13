"""Store ranking and the optional 2-store split (ENGINE.md ``rank_stores``, ``suggest_split``;
BUILD-BRIEF §6.3). Quotes are built by hand; all amounts are synthetic."""

from __future__ import annotations

import math
import random
from decimal import ROUND_HALF_UP, Decimal, localcontext

from bpf.pricing import QuoteLine, StoreQuote, rank_stores, suggest_split, whole_forints

D = Decimal


def quote(
    store_id: str, costs: dict[str, int | str | None], *, extra: tuple[QuoteLine, ...] = ()
) -> StoreQuote:
    """``costs``: ingredient -> checkout cost (priced) or None (unavailable)."""
    lines: list[QuoteLine] = []
    for ing_id, cost in costs.items():
        if cost is None:
            lines.append(QuoteLine(ing_id, D(1), "unavailable"))
        else:
            lines.append(QuoteLine(ing_id, D(1), "priced", checkout_cost=D(cost), used_cost=D(cost)))
    lines.extend(extra)
    priced = [line for line in lines if line.status == "priced"]
    return StoreQuote(
        store_id=store_id,
        lines=tuple(lines),
        checkout_total=sum((line.checkout_cost or D(0) for line in priced), D(0)),
        used_total=sum((line.used_cost or D(0) for line in priced), D(0)),
        missing=tuple(line.ingredient_id for line in lines if line.status == "unavailable"),
        assumed_count=0,
        ksh_estimate_total=D(0),
    )


# ───────────── rank_stores ─────────────


def test_missing_line_is_penalised_with_the_median_of_the_other_stores() -> None:
    quotes = [
        quote("s1", {"tej": 300, "lazac": None}),  # 300 + median(1500, 1800, 2400) = 2100
        quote("s2", {"tej": 400, "lazac": 1500}),  # 1900
        quote("s3", {"tej": 350, "lazac": 1800}),  # 2150
        quote("s4", {"tej": 500, "lazac": 2400}),  # 2900
    ]
    ranking = rank_stores(quotes)
    assert [(r.store_id, r.rank, r.checkout_total, r.penalized_total, r.missing_count) for r in ranking] == [
        ("s2", 1, D(1900), D(1900), 0),
        ("s1", 2, D(300), D(2100), 1),
        ("s3", 3, D(2150), D(2150), 0),
        ("s4", 4, D(2900), D(2900), 0),
    ]


def test_ties_share_a_rank_and_are_never_broken_by_store_or_chain_name() -> None:
    # BUILD-BRIEF §4.1 trap 13: equal (displayed) totals form one tie group: competition ranking 1, 1, 3.
    quotes = [
        quote("spar-1", {"repa": 489}),
        quote("aldi-1", {"repa": 489}),
        quote("lidl-1", {"repa": "489.40"}),  # 489 Ft when displayed: still tied
        quote("tesco-1", {"repa": "489.50"}),  # 490 Ft when displayed: next rank
    ]
    ranking = rank_stores(quotes)
    assert {r.store_id: r.rank for r in ranking} == {"aldi-1": 1, "lidl-1": 1, "spar-1": 1, "tesco-1": 4}
    assert [r.rank for r in ranking] == [1, 1, 1, 4]


def test_a_total_just_under_half_a_forint_ties_with_what_it_is_displayed_as() -> None:
    # Loose bananas, 0.505 kg: 999 Ft/kg = 504.495 Ft is sent as 504.50 and shown as "505 Ft", the same as
    # 1000 Ft/kg = 505 Ft. Rounding the exact amount straight to whole forints (504) would rank them 1 and 2.
    quotes = [quote("lidl-1", {"banan": "505.000"}), quote("aldi-1", {"banan": "504.495"})]
    ranking = rank_stores(quotes)
    assert [(r.store_id, r.rank) for r in ranking] == [("aldi-1", 1), ("lidl-1", 1)]
    assert [r.penalized_total for r in ranking] == [D("504.495"), D("505.000")]  # exact amounts kept


def test_a_total_below_the_displayed_half_forint_is_not_tied_upwards() -> None:
    # 504.494 is sent as 504.49 and shown as "504 Ft"; 504.2 is also "504 Ft"; 504.5 is "505 Ft".
    quotes = [
        quote("a", {"x": "504.494"}),
        quote("b", {"x": "504.2"}),
        quote("c", {"x": "504.5"}),
    ]
    assert {r.store_id: r.rank for r in rank_stores(quotes)} == {"a": 1, "b": 1, "c": 3}


def test_whole_forints_matches_the_api_money_then_client_rounding() -> None:
    # The API sends money as float(quantize half-up to 0.01) (bpf.api.present.money) and the client shows it
    # with Intl.NumberFormat maximumFractionDigits 0 (halfExpand, i.e. half away from zero, on the float).
    def displayed(amount: Decimal) -> Decimal:
        sent = float(amount.quantize(D("0.01"), rounding=ROUND_HALF_UP))
        return D(math.floor(sent + 0.5)) if sent >= 0 else -D(math.floor(-sent + 0.5))

    rng = random.Random(20261013)  # noqa: S311 - seeded test values, not security
    samples = [
        D(f"{whole}.{frac}")
        for whole in (0, 1, 412, 504, 99_999)
        for frac in ("49", "494", "495", "4999", "5")
    ]
    samples += [D(rng.randint(0, 10**9)) / D(10 ** rng.randint(0, 6)) for _ in range(5_000)]
    for amount in samples:
        assert whole_forints(amount) == displayed(amount), amount
    assert whole_forints(D("412.495")) == whole_forints(D("412.6")) == D(413)
    assert whole_forints(D("504.4949")) == D(504)
    with localcontext() as ctx:  # the caller's decimal context does not matter
        ctx.prec = 2
        assert whole_forints(D("123456.495")) == D(123457)


def test_equal_totals_with_different_missing_counts_are_not_tied() -> None:
    quotes = [
        quote("a", {"tej": 300, "liszt": 200, "lazac": None}),  # 500 + median(300) = 800, 1 missing
        quote("b", {"tej": 300, "liszt": 200, "lazac": 300}),  # 800, 0 missing
    ]
    ranking = rank_stores(quotes)
    assert [(r.store_id, r.rank) for r in ranking] == [("b", 1), ("a", 2)]


def test_even_number_of_other_prices_uses_the_mean_of_the_middle_two() -> None:
    quotes = [quote("s1", {"x": None}), quote("s2", {"x": 1000}), quote("s3", {"x": 1501})]
    penalised = {r.store_id: r.penalized_total for r in rank_stores(quotes)}
    assert penalised["s1"] == D("1250.5")


def test_no_penalty_when_no_other_store_has_the_line() -> None:
    quotes = [quote("s1", {"tej": 300, "x": None}), quote("s2", {"tej": 320, "x": None})]
    ranking = rank_stores(quotes)
    assert [(r.store_id, r.penalized_total, r.missing_count) for r in ranking] == [
        ("s1", D(300), 1),
        ("s2", D(320), 1),
    ]


def test_ties_break_on_missing_count_then_store_id() -> None:
    quotes = [
        quote("s3", {"a": 1000, "b": 500}),
        quote("s1", {"a": 1000, "b": None}),  # 1000 + median(500, 500) = 1500
        quote("s2", {"a": 1000, "b": 500}),
    ]
    assert [r.store_id for r in rank_stores(quotes)] == ["s2", "s3", "s1"]


def test_non_gvh_lines_never_count_as_missing() -> None:
    extra = (QuoteLine("so", D(1), "pantry"), QuoteLine("zab", D(1), "ksh_estimate", ksh_estimate=D(400)))
    quotes = [quote("s1", {"tej": 300}, extra=extra), quote("s2", {"tej": 310}, extra=extra)]
    assert [(r.store_id, r.penalized_total, r.missing_count) for r in rank_stores(quotes)] == [
        ("s1", D(300), 0),
        ("s2", D(310), 0),
    ]


def test_empty_input() -> None:
    assert rank_stores([]) == ()
    assert suggest_split([]) is None


# ───────────── suggest_split ─────────────


def test_split_saving_at_least_the_threshold_is_suggested_with_assignment() -> None:
    quotes = [
        quote("s1", {"hus": 3000, "tejtermek": 2500, "zoldseg": 1000}),  # 6500
        quote("s2", {"hus": 4000, "tejtermek": 1000, "zoldseg": 1100}),  # 6100 (best single)
        quote("s3", {"hus": 3500, "tejtermek": 2600, "zoldseg": 900}),  # 7000
    ]
    split = suggest_split(quotes)
    # Best pair s1+s2: hus 3000 (s1), tejtermek 1000 (s2), zoldseg 1000 (s1) = 5000;
    # saving 6100 - 5000 = 1100 < 1500.
    assert split is None
    split = suggest_split(quotes, threshold=D(1000))
    assert split is not None
    assert split.store_ids == ("s2", "s1")  # better-ranked store first
    assert (split.total, split.saving) == (D(5000), D(1100))
    assert dict(split.assignment) == {"hus": "s1", "tejtermek": "s2", "zoldseg": "s1"}


def test_split_threshold_is_inclusive_and_defaults_to_1500() -> None:
    base = {"a": 2000, "b": 2000}
    quotes = [quote("s1", {**base, "a": 500}), quote("s2", {**base, "b": 500})]
    # Single: 2500 each. Split: 500 + 500 = 1000 -> saving 1500 == threshold -> suggested.
    split = suggest_split(quotes)
    assert split is not None
    assert split.saving == D(1500)
    assert split.total == D(1000)
    # One forint less saving -> nothing.
    quotes = [quote("s1", {**base, "a": 501}), quote("s2", {**base, "b": 500})]
    assert suggest_split(quotes) is None


def test_equal_line_costs_go_to_the_better_ranked_store() -> None:
    quotes = [
        quote("s1", {"a": 100, "b": 3000, "c": 700}),  # 3800
        quote("s2", {"a": 100, "b": 1000, "c": 2000}),  # 3100 (rank 1)
    ]
    split = suggest_split(quotes, threshold=D(0))
    assert split is not None
    assert dict(split.assignment) == {"a": "s2", "b": "s2", "c": "s1"}
    assert split.total == D(1800)


def test_lines_missing_at_both_stores_are_left_out_but_judged_on_the_penalized_basis() -> None:
    quotes = [
        quote("s1", {"tej": 1000, "kenyer": 3000, "lazac": None}),
        quote("s2", {"tej": 3000, "kenyer": 1000, "lazac": None}),
        quote("s3", {"tej": 2000, "kenyer": 2000, "lazac": 2000}),  # 6000, complete: best single
    ]
    # s1 and s2 penalised: 4000 + 2000 = 6000 each; s3 6000 -> s3 ranks first (0 missing).
    # Pair s1+s2: 1000 + 1000 = 2000 actually paid, lazac missing at both -> penalised 2000 + 2000 = 4000;
    # saving = 6000 - 4000 = 2000 >= 1500.
    split = suggest_split(quotes)
    assert split is not None
    assert set(split.store_ids) == {"s1", "s2"}
    assert split.total == D(2000)
    assert split.saving == D(2000)
    assert "lazac" not in split.assignment


def test_a_pair_that_only_looks_cheap_because_both_lack_an_item_is_not_suggested() -> None:
    quotes = [
        quote("s1", {"tej": 300, "lazac": None}),
        quote("s2", {"tej": 290, "lazac": None}),
        quote("s3", {"tej": 400, "lazac": 3000}),  # best single (penalised s1 = 3300, s2 = 3290)
    ]
    # Literal "ignore lines missing at both": s1+s2 = 290 vs 3290 would look like a 3000 Ft saving.
    assert suggest_split(quotes) is None


def test_all_lines_at_one_store_is_not_a_split() -> None:
    quotes = [quote("s1", {"a": 100, "b": 100}), quote("s2", {"a": 5000, "b": 5000})]
    assert suggest_split(quotes, threshold=D(0)) is None


def test_single_quote_has_no_split() -> None:
    assert suggest_split([quote("s1", {"a": 100})]) is None
