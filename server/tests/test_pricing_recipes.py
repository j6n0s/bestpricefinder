"""Chain-typical recipe cost (ENGINE.md ``recipe_chain_costs``). Synthetic data only."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from bpf.pricing import Catalogue, ChainRecipeCost, KshPrice, recipe_chain_costs
from tests.fixtures.pricing.builders import catalogue, chain, chain_price, ingredient, product, recipe

D = Decimal

INGREDIENTS = [
    ingredient("csirkemell", leaf_ids=[18]),
    ingredient("hagyma", leaf_ids=[40], piece_weight="0.1"),
    ingredient("tejfol", leaf_ids=[6]),
    ingredient("olaj", unit="l", leaf_ids=[51], pantry=True),
    ingredient("so", pantry=True),
    ingredient("zab", ksh_code="K-ZAB"),
    ingredient("spenot"),
]
PRODUCTS = [
    product("cm-loose", "Csirkemell lédig", 18, unit_title="kg"),
    product("cm-pack", "Csirkemell tálca 0,5 kg", 18, packaging="0.5"),
    product("h-db", "Vöröshagyma db", 40, unit="db", packaging="1"),
    product("h-2kg", "Vöröshagyma 2 kg", 40, packaging="2"),
    product("tf", "Tejföl 450 g", 6, packaging="0.45"),
    product("ol", "Étolaj 1 l", 51, unit="l"),
]
CHAINS = [chain("gamma"), chain("alfa"), chain("beta"), chain("drogeria", grocery=False)]
PRICES = [
    # alfa: chicken loose 2000/kg vs tray 900/0.5 kg = 1800/kg (cheapest); onion 2 kg 400 = 200/kg.
    chain_price("cm-loose", "alfa", 2000, normal=1500),  # normal_amount (one-store minimum) is ignored
    chain_price("cm-pack", "alfa", 900),
    chain_price("h-2kg", "alfa", 400),
    chain_price("tf", "alfa", 360),
    chain_price("ol", "alfa", 700),
    # beta: chicken 2100/kg; onion per piece 30 Ft = 300/kg; no sour cream.
    chain_price("cm-loose", "beta", 2100),
    chain_price("h-db", "beta", 30),
    # gamma: only onion, via XLSX fallback (min == max) 220/kg; chicken pma missing and xlsx min < max.
    chain_price("h-2kg", "gamma", None, xlsx_min=440, xlsx_max=440),
    chain_price("cm-pack", "gamma", None, xlsx_min=800, xlsx_max=950),
    chain_price("tf", "drogeria", 100),  # not a grocery chain
]
KSH = [KshPrice("K-ZAB", "Zabpehely", "kg", D(1), D(800), date(2026, 9, 1))]

RECIPE = recipe(
    "csirkes-tal",
    4,
    [
        ("csirkemell", "0.6"),
        ("hagyma", "0.2"),
        ("tejfol", "0.2"),
        ("olaj", "0.02"),  # pantry: excluded
        ("so", "0.005"),  # pantry: excluded
        ("tejfol", "0.1", True),  # optional: excluded
    ],
)


def _cat(**overrides: object) -> Catalogue:
    params: dict[str, object] = {
        "ingredients": INGREDIENTS,
        "products": PRODUCTS,
        "chains": CHAINS,
        "chain_prices": PRICES,
        "ksh": KSH,
    }
    params.update(overrides)
    return catalogue(**params)  # type: ignore[arg-type]


def _by_chain(costs: tuple[ChainRecipeCost, ...]) -> dict[str, ChainRecipeCost]:
    return {c.chain_id: c for c in costs}


def test_one_entry_per_grocery_chain_sorted_by_slug() -> None:
    costs = recipe_chain_costs(RECIPE, _cat())
    assert [c.chain_id for c in costs] == ["chain-alfa", "chain-beta", "chain-gamma"]


def test_chain_typical_used_cost_with_cheapest_candidate_per_line() -> None:
    costs = _by_chain(recipe_chain_costs(RECIPE, _cat()))
    alfa = costs["chain-alfa"]
    # chicken 0.6 x 1800 = 1080; onion 0.2 x 200 = 40; sour cream 0.2 x 360/0.45 = 160 -> 1280 / 4 servings
    assert alfa.cost_per_serving == D(320)
    assert alfa.priced_share == D(1)
    assert alfa.missing == ()


def test_missing_line_is_estimated_by_the_median_of_other_chains() -> None:
    beta = _by_chain(recipe_chain_costs(RECIPE, _cat()))["chain-beta"]
    # chicken 0.6 x 2100 = 1260; onion 0.2 x 300 = 60 -> priced 1320; sour cream missing:
    # other chains' cost for it: alfa 160 only -> estimate 160. share = 1320 / 1480.
    assert beta.cost_per_serving == D(330)
    assert beta.missing == ("tejfol",)
    assert beta.priced_share == D(1320) / D(1480)


def test_median_over_two_other_chains_and_xlsx_fallback() -> None:
    gamma = _by_chain(recipe_chain_costs(RECIPE, _cat()))["chain-gamma"]
    # onion via XLSX (min == max): 0.2 x 440/2 = 44. chicken: pma missing and XLSX min < max -> missing;
    # estimate = median(alfa 1080, beta 1260) = 1170. sour cream: estimate = alfa 160.
    assert gamma.cost_per_serving == D(11)  # 44 / 4
    assert gamma.missing == ("csirkemell", "tejfol")
    assert gamma.priced_share == D(44) / D(44 + 1170 + 160)


def test_ksh_then_zero_estimates_for_lines_no_chain_prices() -> None:
    dish = recipe("zabos", 2, [("tejfol", "0.45"), ("zab", "0.5"), ("spenot", "0.3")])
    alfa = _by_chain(recipe_chain_costs(dish, _cat()))["chain-alfa"]
    # sour cream 360; oats: no chain -> KSH 0.5 x 800 = 400; spinach: no chain, no KSH -> 0.
    assert alfa.cost_per_serving == D(180)
    assert alfa.missing == ("zab", "spenot")
    assert alfa.priced_share == D(360) / D(760)


def test_nothing_priced_gives_none_and_zero_share() -> None:
    dish = recipe("csak-spenot", 2, [("spenot", "0.3"), ("so", "0.01")])
    for cost in recipe_chain_costs(dish, _cat()):
        assert cost.cost_per_serving is None
        assert cost.priced_share == 0
        assert cost.missing == ("spenot",)


def test_only_pantry_and_optional_lines() -> None:
    dish = recipe("pantry-only", 2, [("so", "0.01"), ("olaj", "0.02"), ("tejfol", "0.1", True)])
    for cost in recipe_chain_costs(dish, _cat()):
        assert (cost.cost_per_serving, cost.priced_share, cost.missing) == (None, 0, ())


def test_duplicate_ingredient_lines_are_listed_once_in_missing() -> None:
    dish = recipe("dupla", 1, [("tejfol", "0.1"), ("tejfol", "0.2")])
    beta = _by_chain(recipe_chain_costs(dish, _cat()))["chain-beta"]
    assert beta.missing == ("tejfol",)


def test_unknown_ingredient_raises() -> None:
    with pytest.raises(KeyError):
        recipe_chain_costs(recipe("rossz", 1, [("nincs", "1")]), _cat())
