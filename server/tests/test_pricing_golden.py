"""GOLDEN test (BUILD-BRIEF §7 "golden tests for 3 recipes x 3 stores"): a hand-built SYNTHETIC catalogue,
three recipes, three stores of three fictional chains. Every expected number is computed by hand in the
comments; the test runs the whole pipeline: build_list -> quote_store -> rank_stores -> suggest_split, plus
recipe_chain_costs per recipe.

Chain-typical unit prices used below (product_min_amount / canonical size):
               alfa                      beta                     gamma
  csirkemell   min(2000 loose,           1900 (1 kg pack; breaded  1699 (counter, pma = discount)
               900/0.5 = 1800) = 1800    and "tokány" excluded)
  tejföl       min(149/0.175, 360/0.45)  min(159/0.175, 342/0.45)  min(175/0.175, 360/0.45) = 800
               = 800 (the "A/B" SKU at   = 760
               199 is excluded)
  tojás        min(455/10, 1290/30) = 43 min(480/10, 300/6) = 48   min(520/10, 330/6) = 52
  burgonya     389/2 = 194.5             249 (loose)               299 (loose)
  vöröshagyma  min(379/2, 299) = 189.5   279 (loose)               45 Ft/db / 0.12 kg = 375
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from bpf.pricing import (
    KshPrice,
    StoreQuote,
    build_list,
    quote_store,
    rank_stores,
    recipe_chain_costs,
    suggest_split,
)
from tests.fixtures.pricing.builders import (
    catalogue,
    chain,
    chain_price,
    ingredient,
    product,
    recipe,
    store,
    store_price,
)

D = Decimal

INGREDIENTS = [
    ingredient(
        "csirkemell",
        leaf_ids=[18],
        include=["csirkemell"],
        exclude=["panir", "tokany"],
        list_group="hus_hal",
        name_hu="csirkemellfilé",
    ),
    ingredient("tejfol", leaf_ids=[6], exclude=["/"], list_group="tejtermek_tojas", name_hu="tejföl"),
    ingredient(
        "tojas", unit="db", leaf_ids=[14], piece_weight="0.06", list_group="tejtermek_tojas", name_hu="tojás"
    ),
    ingredient("burgonya", leaf_ids=[41], list_group="zoldseg_gyumolcs", name_hu="burgonya"),
    ingredient(
        "voroshagyma",
        leaf_ids=[40],
        piece_weight="0.12",
        list_group="zoldseg_gyumolcs",
        name_hu="vöröshagyma",
    ),
    ingredient("petrezselyem", ksh_code="K-PETR", list_group="zoldseg_gyumolcs", name_hu="petrezselyemzöld"),
    ingredient("olaj", unit="l", leaf_ids=[51], pantry=True, list_group="fuszer_olaj", name_hu="étolaj"),
    ingredient("so", pantry=True, list_group="fuszer_olaj", name_hu="só"),
]
PRODUCTS = [
    product("cm-a-loose", "Csirkemell filé lédig", 18, unit_title="kg"),
    product("cm-a-pack", "Csirkemellfilé 500 g tálcás", 18, packaging="0.5"),
    product("pult-csirkemell", "14. FRISS CSIRKEMELL FILE PULTOS QQ", 18, unit_title="kg"),
    product("cm-b-pan", "Panírozott csirkemell 500 g", 18, packaging="0.5"),
    product("cm-b-tok", "Csirkemell tokány, kg", 18, unit_title="kg"),
    product("cm-b-pack", "Csirkemellfilé 1 kg", 18, packaging="1"),
    product("tf175", "Tejföl 12% 175 g", 6, packaging="0.175"),
    product("tf450", "Tejföl 12% 450 g", 6, packaging="0.45"),
    product("tf-multi", "Milsani/Milfina tejföl 12% 450g", 6, packaging="0.45"),
    product("e10", "Friss tojás 10 db", 14, unit="db", packaging="10"),
    product("e30", "Tojás 30 db", 14, unit="db", packaging="30"),
    product("e6", "Tojás 6 db", 14, unit="db", packaging="6"),
    product("b2kg", "Burgonya 2 kg hálós", 41, packaging="2"),
    product("b-loose", "Burgonya lédig", 41, unit_title="kg"),
    product("h2kg", "Vöröshagyma 2 kg", 40, packaging="2"),
    product("h-loose", "Vöröshagyma lédig", 40, unit_title="kg"),
    product("h-db", "Vöröshagyma db", 40, unit="db", packaging="1"),
    product("o1", "Napraforgó étolaj 1 l", 51, unit="l", packaging="1"),
]
CHAIN_PRICES = [
    # alfa
    chain_price("cm-a-loose", "alfa", 2000),
    chain_price("cm-a-pack", "alfa", 900),
    chain_price("tf175", "alfa", 149),
    chain_price("tf450", "alfa", 360),
    chain_price("tf-multi", "alfa", 199),  # multi-variant SKU: excluded by the "/" rule
    chain_price("e10", "alfa", 455),
    chain_price("e30", "alfa", 1290),
    chain_price("b2kg", "alfa", 389),
    chain_price("h2kg", "alfa", 379),
    chain_price("h-loose", "alfa", 299),
    chain_price("o1", "alfa", 749),
    # beta
    chain_price("cm-b-pan", "beta", 800),  # excluded (breaded)
    chain_price("cm-b-tok", "beta", 1500),  # excluded (mis-filed "tokány")
    chain_price("cm-b-pack", "beta", 1900, normal=1490),  # normal_amount: a one-store minimum, ignored
    chain_price("tf175", "beta", 159),
    chain_price("tf450", "beta", 342),
    chain_price("e10", "beta", 480),
    chain_price("e6", "beta", 300),
    chain_price("b-loose", "beta", 249),
    chain_price("h-loose", "beta", 279),
    chain_price("o1", "beta", 699),
    # gamma (sells no oil)
    chain_price("pult-csirkemell", "gamma", 1699, normal=2030, discounted=1699, same=False),
    chain_price("tf175", "gamma", 175),
    chain_price("tf450", "gamma", 360),  # but not carried at store g1 (availability below)
    chain_price("e10", "gamma", 520),
    chain_price("e6", "gamma", 330),
    chain_price("b-loose", "gamma", 299),
    chain_price("h-db", "gamma", 45),
]
STORE_PRICES = [store_price("pult-csirkemell", "g1", normal=2030)]  # g1 has no discount: store row wins
AVAILABILITY = {("tf450", "chain-gamma"): {"g2"}, ("e10", "chain-gamma"): {"g1", "g2"}}
KSH = [KshPrice("K-PETR", "Petrezselyem (szintetikus)", "kg", D(1), D(5000), date(2026, 9, 1))]

PAPRIKAS = recipe(
    "csirkepaprikas",
    4,
    [("csirkemell", "0.6"), ("voroshagyma", "0.2"), ("tejfol", "0.2"), ("olaj", "0.03"), ("so", "0.01")],
)
RAKOTT = recipe(
    "rakott-krumpli", 4, [("burgonya", "1.0"), ("tojas", "4"), ("tejfol", "0.4"), ("olaj", "0.02")]
)
RANTOTTA = recipe(
    "rantotta",
    2,
    [("tojas", "4"), ("voroshagyma", "0.1"), ("petrezselyem", "0.02"), ("olaj", "0.01"), ("so", "0.002")],
)

CAT = catalogue(
    ingredients=INGREDIENTS,
    products=PRODUCTS,
    chains=[chain("alfa"), chain("beta"), chain("gamma")],
    stores=[store("a1", "alfa"), store("b1", "beta"), store("g1", "gamma"), store("g2", "gamma")],
    chain_prices=CHAIN_PRICES,
    store_prices=STORE_PRICES,
    availability=AVAILABILITY,
    ksh=KSH,
    recipes=[PAPRIKAS, RAKOTT, RANTOTTA],
)


def _quotes() -> dict[str, StoreQuote]:
    items = [(PAPRIKAS, D(4)), (RAKOTT, D(4)), (RANTOTTA, D(2))]
    lines = [(line.ingredient_id, line.qty) for line in build_list(items, CAT.ingredients)]
    return {sid: quote_store(lines, CAT.stores[sid], CAT) for sid in ("a1", "b1", "g1")}


def test_golden_shopping_list() -> None:
    items = [(PAPRIKAS, D(4)), (RAKOTT, D(4)), (RANTOTTA, D(2))]  # every recipe at its own servings
    lines = build_list(items, CAT.ingredients)
    assert [(line.ingredient_id, line.qty, line.pantry) for line in lines] == [
        ("burgonya", D("1.0"), False),
        ("petrezselyem", D("0.02"), False),
        ("voroshagyma", D("0.3"), False),  # 0.2 + 0.1
        ("tejfol", D("0.6"), False),  # 0.2 + 0.4
        ("tojas", D(8), False),  # 4 + 4
        ("csirkemell", D("0.6"), False),
        ("olaj", D("0.06"), True),  # 0.03 + 0.02 + 0.01
        ("so", D("0.012"), True),
    ]


def test_golden_store_a1() -> None:
    q = _quotes()["a1"]
    got = {line.ingredient_id: line for line in q.lines}
    # burgonya 1.0 kg: one 2 kg net (389), 1.0 kg left, used 1.0 x 389/2 = 194.5
    assert [(p.option.product_id, p.count) for p in got["burgonya"].picks] == [("b2kg", 1)]
    assert (got["burgonya"].checkout_cost, got["burgonya"].used_cost) == (D(389), D("194.5"))
    # vöröshagyma 0.3 kg: loose 0.3 x 299 = 89.7 (< 379 for the 2 kg net)
    assert [(p.option.product_id, p.qty) for p in got["voroshagyma"].picks] == [("h-loose", D("0.3"))]
    assert got["voroshagyma"].checkout_cost == D("89.7")
    assert [o.product_id for o in got["voroshagyma"].alternatives] == ["h2kg"]
    # tejföl 0.6 kg: 0.45 (360) + 0.175 (149) = 509 (4 x 149 = 596, 2 x 360 = 720); used 0.6 x 509/0.625
    assert sorted((p.option.product_id, p.count) for p in got["tejfol"].picks) == [("tf175", 1), ("tf450", 1)]
    assert (got["tejfol"].checkout_cost, got["tejfol"].used_cost) == (D(509), D("488.64"))
    assert got["tejfol"].leftover_qty == D("0.025")
    # tojás 8: one 10-pack 455 (30-pack 1290); used 8 x 45.5 = 364
    assert (got["tojas"].checkout_cost, got["tojas"].used_cost, got["tojas"].leftover_qty) == (
        D(455),
        D(364),
        D(2),
    )
    # csirkemell 0.6 kg: 0.5 kg tray (900) + 0.1 kg loose (200) = 1100 (2 trays 1800, 0.6 loose 1200)
    assert (got["csirkemell"].checkout_cost, got["csirkemell"].used_cost) == (D(1100), D(1100))
    # olaj 0.06 l (pantry with a GVH mapping, so priced): 1 l for 749, used 0.06 x 749 = 44.94
    assert (got["olaj"].status, got["olaj"].checkout_cost, got["olaj"].used_cost) == (
        "priced",
        D(749),
        D("44.94"),
    )
    assert got["so"].status == "pantry"
    assert (got["petrezselyem"].status, got["petrezselyem"].ksh_estimate) == (
        "ksh_estimate",
        D(100),
    )  # 0.02 x 5000
    # checkout: 389 + 89.7 + 509 + 455 + 1100 + 749 = 3291.7
    # used: 194.5 + 89.7 + 488.64 + 364 + 1100 + 44.94 = 2281.78
    assert (q.checkout_total, q.used_total) == (D("3291.7"), D("2281.78"))
    assert (q.missing, q.assumed_count, q.ksh_estimate_total) == ((), 6, D(100))


def test_golden_store_b1() -> None:
    q = _quotes()["b1"]
    got = {line.ingredient_id: line for line in q.lines}
    assert got["burgonya"].checkout_cost == D(249)  # loose 1.0 x 249
    assert got["voroshagyma"].checkout_cost == D("83.7")  # loose 0.3 x 279
    # tejföl: 342 + 159 = 501 (2 x 342 = 684, 4 x 159 = 636); used 0.6 x 501 / 0.625 = 480.96
    assert (got["tejfol"].checkout_cost, got["tejfol"].used_cost) == (D(501), D("480.96"))
    # tojás 8: 10-pack 480 (2 x 6-pack = 600); used 8 x 48 = 384
    assert (got["tojas"].checkout_cost, got["tojas"].used_cost) == (D(480), D(384))
    # csirkemell: only the 1 kg pack survives the name rules: 1900, used 0.6 x 1900 = 1140
    assert [p.option.product_id for p in got["csirkemell"].picks] == ["cm-b-pack"]
    assert (got["csirkemell"].checkout_cost, got["csirkemell"].used_cost) == (D(1900), D(1140))
    assert got["olaj"].checkout_cost == D(699)
    # checkout 249 + 83.7 + 501 + 480 + 1900 + 699 = 3912.7 ; used 249 + 83.7 + 480.96 + 384 + 1140 + 41.94
    assert (q.checkout_total, q.used_total) == (D("3912.7"), D("2379.60"))
    assert (q.missing, q.assumed_count) == ((), 6)


def test_golden_store_g1() -> None:
    q = _quotes()["g1"]
    got = {line.ingredient_id: line for line in q.lines}
    assert got["burgonya"].checkout_cost == D(299)
    # vöröshagyma 0.3 kg from 0.12 kg pieces at 45: 3 pieces = 135, 0.06 kg left; used 0.3 x 135/0.36
    assert [(p.option.product_id, p.count) for p in got["voroshagyma"].picks] == [("h-db", 3)]
    assert (got["voroshagyma"].checkout_cost, got["voroshagyma"].used_cost) == (D(135), D("112.5"))
    # tejföl: the 450 g pack is not carried at g1 -> 4 x 175 = 700 for 0.7 kg; used 0.6 x 700/0.7 = 600
    assert (got["tejfol"].checkout_cost, got["tejfol"].used_cost) == (D(700), D(600))
    # tojás: 10-pack 520 (confirmed by the availability list)
    assert got["tojas"].checkout_cost == D(520)
    assert got["tojas"].picks[0].option.availability == "confirmed"
    # csirkemell: g1's own row (2030, no discount) beats the chain's typical 1699: 0.6 x 2030 = 1218
    pick = got["csirkemell"].picks[0]
    assert (pick.option.scope, pick.option.price_type, got["csirkemell"].checkout_cost) == (
        "store",
        "NORMAL",
        D(1218),
    )
    assert got["olaj"].status == "unavailable"
    # checkout 299 + 135 + 700 + 520 + 1218 = 2872 ; used 299 + 112.5 + 600 + 416 + 1218 = 2645.5
    assert (q.checkout_total, q.used_total) == (D(2872), D("2645.5"))
    assert (q.missing, q.assumed_count) == (("olaj",), 3)  # burgonya, vöröshagyma, tejföl


def test_golden_ranking_and_split() -> None:
    quotes = _quotes()
    ranking = rank_stores(list(quotes.values()))
    # g1 misses oil: + median(749, 699) = 724 -> 2872 + 724 = 3596
    assert [(r.store_id, r.rank, r.checkout_total, r.penalized_total, r.missing_count) for r in ranking] == [
        ("a1", 1, D("3291.7"), D("3291.7"), 0),
        ("g1", 2, D(2872), D(3596), 1),
        ("b1", 3, D("3912.7"), D("3912.7"), 0),
    ]
    # Pairs: a1+b1 = 249 + 83.7 + 501 + 455 + 1100 + 699 = 3087.7 (saving 204);
    #        a1+g1 = 299 + 89.7 + 509 + 455 + 1100 + 749 = 3201.7;
    #        b1+g1 = 249 + 83.7 + 501 + 480 + 1218 + 699 = 3230.7.
    assert suggest_split(list(quotes.values())) is None  # 204 < 1500
    split = suggest_split(list(quotes.values()), threshold=D(200))
    assert split is not None
    assert (split.store_ids, split.total, split.saving) == (("a1", "b1"), D("3087.7"), D(204))
    assert dict(split.assignment) == {
        "burgonya": "b1",
        "voroshagyma": "b1",
        "tejfol": "b1",
        "tojas": "a1",
        "csirkemell": "a1",
        "olaj": "b1",
    }


def test_golden_recipe_chain_costs() -> None:
    def costs(r):  # type: ignore[no-untyped-def]
        return {
            c.chain_id: (c.cost_per_serving, c.priced_share, c.missing) for c in recipe_chain_costs(r, CAT)
        }

    # Paprikás (4): alfa 0.6x1800 + 0.2x189.5 + 0.2x800 = 1080 + 37.9 + 160 = 1277.9 -> 319.475
    #               beta 1140 + 55.8 + 152 = 1347.8 -> 336.95 ; gamma 1019.4 + 75 + 160 = 1254.4 -> 313.6
    assert costs(PAPRIKAS) == {
        "chain-alfa": (D("319.475"), D(1), ()),
        "chain-beta": (D("336.95"), D(1), ()),
        "chain-gamma": (D("313.6"), D(1), ()),
    }
    # Rakott krumpli (4): alfa 194.5 + 4x43 + 0.4x800 = 686.5 -> 171.625 ; beta 249 + 192 + 304 = 745
    #                     -> 186.25 ; gamma 299 + 208 + 320 = 827 -> 206.75
    assert costs(RAKOTT) == {
        "chain-alfa": (D("171.625"), D(1), ()),
        "chain-beta": (D("186.25"), D(1), ()),
        "chain-gamma": (D("206.75"), D(1), ()),
    }
    # Rántotta (2): parsley is KSH-only (estimate 0.02 x 5000 = 100 at every chain).
    #   alfa 4x43 + 0.1x189.5 = 190.95 -> 95.475, share 190.95/290.95
    #   beta 192 + 27.9 = 219.9 -> 109.95, share 219.9/319.9 ; gamma 208 + 37.5 = 245.5 -> 122.75
    result = costs(RANTOTTA)
    assert result["chain-alfa"][:1] == (D("95.475"),)
    assert result["chain-beta"][:1] == (D("109.95"),)
    assert result["chain-gamma"][:1] == (D("122.75"),)
    assert result["chain-alfa"][1].quantize(D("0.0001")) == (D("190.95") / D("290.95")).quantize(D("0.0001"))
    assert result["chain-beta"][1].quantize(D("0.0001")) == (D("219.9") / D("319.9")).quantize(D("0.0001"))
    assert result["chain-gamma"][1].quantize(D("0.0001")) == (D("245.5") / D("345.5")).quantize(D("0.0001"))
    assert {c[2] for c in result.values()} == {("petrezselyem",)}
