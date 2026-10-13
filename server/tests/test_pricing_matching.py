"""Ingredient -> candidate products (ENGINE.md ``candidate_products``; BUILD-BRIEF §4.1 traps 5-6;
research/recipe-coverage/notes.md §8 C-E). Product names imitate GVH name shapes; all data is synthetic."""

from __future__ import annotations

import pytest

from bpf.pricing import Catalogue, Ingredient, Product, candidate_products, fold_name
from tests.fixtures.pricing.builders import catalogue, ingredient, product


def _ids(ing: Ingredient, products: list[Product]) -> list[str]:
    return [p.id for p in candidate_products(ing, catalogue(products=products))]


# ───────────── name rules on folded names ─────────────

CHICKEN = ingredient(
    "csirkemellfile",
    leaf_ids=[18],
    include=["csirkemell"],
    exclude=["panir", "fustolt", "tokany", "felezett", "csontos"],
)


def test_fold_name_matches_tesco_counter_names() -> None:
    assert fold_name("14. FRISS CSIRKEMELL FILE PULTOS QQ") == "14. friss csirkemell file pultos qq"
    assert fold_name("  Csirkemell   FILÉ ") == "csirkemell file"


def test_tesco_counter_name_matches_include() -> None:
    products = [product("pult-qq", "14. FRISS CSIRKEMELL FILE PULTOS QQ", 18)]
    assert _ids(CHICKEN, products) == ["pult-qq"]


def test_accented_name_matches_ascii_pattern() -> None:
    products = [product("p1", "Friss csirkemellfilé, tálcás", 18)]
    assert _ids(CHICKEN, products) == ["p1"]


@pytest.mark.parametrize(
    "name",
    [
        "Panírozott csirkemell",  # breaded: excluded by "panir"
        "PANÍROZOTT CSIRKEMELL CSÍKOK",
        "Csirkemell tokány, kg",  # mis-filed in the Csirkemellfilé leaf (notes §8.E)
        "Felezett csirkemell",  # bone-in, mis-filed (notes §8.E)
        "Füstölt csirkemell sonka",
    ],
)
def test_excluded_variants(name: str) -> None:
    assert _ids(CHICKEN, [product("p1", name, 18)]) == []


def test_exclude_wins_over_include() -> None:
    ing = ingredient("x", leaf_ids=[1], include=["joghurt"], exclude=["gorog"])
    assert _ids(ing, [product("p1", "Görög joghurt", 1)]) == []


def test_any_include_pattern_is_enough_and_none_means_all() -> None:
    ing = ingredient("paprika", leaf_ids=[35], include=["tv", "etkezesi", "lecso"])
    products = [
        product("a", "TV paprika", 35),
        product("b", "Étkezési paprika lédig", 35),
        product("c", "Kápia paprika", 35),
    ]
    assert _ids(ing, products) == ["a", "b"]
    assert _ids(ingredient("any", leaf_ids=[35]), products) == ["a", "b", "c"]


def test_patterns_are_regexes_searched_anywhere_in_the_folded_name() -> None:
    lean_mince = ingredient("daralt_sertes", leaf_ids=[85], include=[r"\b(7|10|20) ?%"], exclude=[r"\b30 ?%"])
    products = [
        product("a", "Sertés darálthús 20 %, 1kg", 85),
        product("b", "Sertés darálthús 30%", 85),
        product("c", "Darált sertéshús 7%", 85),
        product("d", "Darált sertés 120%", 85),  # \b blocks "120"
    ]
    assert _ids(lean_mince, products) == ["a", "c"]


def test_patterns_are_not_folded_so_accented_patterns_never_match() -> None:
    # docs/DATA.md: patterns must be lower-case ASCII; an accented pattern cannot match a folded name.
    ing = ingredient("x", leaf_ids=[7], include=["görög"])
    assert _ids(ing, [product("p1", "Görög joghurt", 7)]) == []


# ───────────── mis-filed SKUs and multi-variant SKUs (research §8.D-E) ─────────────


def test_misfiled_trappista_in_natur_joghurt_leaf() -> None:
    yoghurt = ingredient("natur_joghurt", leaf_ids=[7], exclude=["gorog", "trapp", "habart", "kremes"])
    products = [
        product("a", "Milsani natúr joghurt 0,1% 175g", 7),
        product("b", "Tejmalom érlelt trappista db", 7),  # mis-filed cheese
        product("c", "RN NATÚR GÖRÖG LIGHT JOGHURT 1 kg QQ", 7),  # Greek yoghurt is its own ingredient
    ]
    assert _ids(yoghurt, products) == ["a"]


def test_feta_leaf_holds_non_feta_white_cheeses() -> None:
    feta = ingredient("feta", leaf_ids=[113], include=["feta"], exclude=["trap"])
    products = [
        product("a", "Milbona Görög feta sajt, 200g", 113),
        product("b", "TOLLE LIGHT TRAP. FÉL SAJT", 113),
        product("c", "Fitaki sajt", 113),
        product("d", "Apetina fehér sajt", 113),
    ]
    assert _ids(feta, products) == ["a"]


def test_smoked_edami_in_trappista_leaf() -> None:
    trappista = ingredient(
        "trappista", leaf_ids=[10], include=["trapp"], exclude=["light", "fustolt", "edami"]
    )
    products = [
        product("a", "Kokárdás trappista sajt kg", 10),
        product("b", "Cheeseland füstölt edami", 10),
        product("c", "Light trappista szeletek", 10),
    ]
    assert _ids(trappista, products) == ["a"]


def test_mixed_vegetables_in_parsley_root_leaf() -> None:
    parsley = ingredient("petrezselyemgyoker", leaf_ids=[37], exclude=["vegyeszoldseg"])
    products = [
        product("a", "Petrezs.gyök.500g girbe-gurba", 37),
        product("b", "Spar hegykői vegyeszöldség 1kg", 37),
    ]
    assert _ids(parsley, products) == ["a"]


@pytest.mark.parametrize(
    "name",
    [
        "Milsani/Milfina tejföl 12% 450g",
        "Milbona Natúr joghurt, 2féle",
        "BON-RI zöld lencse/vörös lencse 500g",
        "Kemencés Kedvencek fehér kenyér vagy teljeskiőrlésű kenyér",
        "Hazánk Kincsei Paprikás szárazkolbász, több ízben",
        "Termék többféle",
    ],
)
def test_multi_variant_skus_are_excluded_by_a_variant_pattern(name: str) -> None:
    ing = ingredient("x", leaf_ids=[1], exclude=["/", r"\bvagy\b", r"\d ?fele\b", r"tobbfele", r"tobb izben"])
    assert _ids(ing, [product("p1", name, 1)]) == []


def test_single_variant_names_survive_the_variant_pattern() -> None:
    ing = ingredient("x", leaf_ids=[1], exclude=["/", r"\bvagy\b", r"\d ?fele\b", r"tobbfele"])
    assert _ids(ing, [product("p1", "Vagyóczky tejföl 12% 450 g", 1)]) == ["p1"]  # "vagy" inside a word


# ───────────── unit rules ─────────────


def test_product_units_filter() -> None:
    onion = ingredient("voroshagyma", leaf_ids=[40], product_units=["kg"], piece_weight="0.12")
    products = [
        product("a", "Vöröshagyma 2kg", 40, unit="kg", packaging="2"),
        product("b", "Vöröshagyma db", 40, unit="db", packaging="1"),
    ]
    assert _ids(onion, products) == ["a"]


def test_empty_product_units_allows_every_convertible_unit() -> None:
    onion = ingredient("voroshagyma", leaf_ids=[40], piece_weight="0.12")
    products = [
        product("a", "Vöröshagyma 2kg", 40, unit="kg", packaging="2"),
        product("b", "Vöröshagyma db", 40, unit="db", packaging="1"),
        product("c", "Hagymás cucc 1 l", 40, unit="l", packaging="1"),  # l not convertible without density
    ]
    assert _ids(onion, products) == ["a", "b"]


def test_db_product_needs_piece_weight() -> None:
    products = [product("a", "Karfiol db", 45, unit="db", packaging="1")]
    assert _ids(ingredient("karfiol", leaf_ids=[45]), products) == []
    assert _ids(ingredient("karfiol", leaf_ids=[45], piece_weight="0.75"), products) == ["a"]


def test_allowed_but_unconvertible_unit_is_still_excluded() -> None:
    ing = ingredient("tejfol", leaf_ids=[6], product_units=["kg", "l"])  # no density
    products = [product("a", "Tejföl 1 l", 6, unit="l"), product("b", "Tejföl 450 g", 6, packaging="0.45")]
    assert _ids(ing, products) == ["b"]


# ───────────── leaves and ordering ─────────────


def test_leaf_membership_multiple_leaves_and_order_by_product_id() -> None:
    milk = ingredient("tej15", leaf_ids=[4, 2], unit="l")
    products = [
        product("z-uht", "UHT tej 1,5%", 4, unit="l"),
        product("a-esl", "ESL tej 1,5%", 2, unit="l"),
        product("m-other", "Kakaó 1 l", 3, unit="l"),
    ]
    assert _ids(milk, products) == ["a-esl", "z-uht"]


def test_unknown_leaf_and_dangling_product_ids_are_ignored() -> None:
    cat = catalogue(products=[product("a", "X", 1)])
    dangling = Catalogue(
        data_date=cat.data_date,
        ingredients={},
        products=cat.products,
        chains={},
        stores={},
        chain_prices={},
        store_prices={},
        availability={},
        products_by_leaf={1: ("a", "ghost", "a")},
    )
    ing = ingredient("x", leaf_ids=[1, 999])
    assert [p.id for p in candidate_products(ing, dangling)] == ["a"]


def test_no_leaves_means_no_candidates() -> None:
    assert _ids(ingredient("so", pantry=True), [product("a", "Só", 1)]) == []


def test_memoised_matching_never_leaks_between_rule_sets_or_catalogues() -> None:
    products = [product("a", "Natúr joghurt", 7), product("b", "Görög joghurt", 7)]
    plain = ingredient("natur", leaf_ids=[7], exclude=["gorog"])
    greek = ingredient("gorog", leaf_ids=[7], include=["gorog"])
    assert _ids(plain, products) == ["a"]
    assert _ids(greek, products) == ["b"]
    assert _ids(plain, products) == ["a"]
    # The same ingredient against a catalogue where product "a" was renamed.
    renamed = [product("a", "Görög joghurt light", 7), product("b", "Görög joghurt", 7)]
    assert _ids(plain, renamed) == []
    assert _ids(greek, renamed) == ["a", "b"]


def test_lists_instead_of_tuples_still_work() -> None:
    # Defensive: a loader that forgot to convert lists to tuples must not break matching.
    ing = Ingredient(
        id="x",
        name_hu="x",
        list_group="egyeb",
        unit="kg",
        leaf_ids=[1],
        include_patterns=["joghurt"],
        exclude_patterns=[],  # type: ignore[arg-type]
    )
    assert _ids(ing, [product("a", "Joghurt", 1)]) == ["a"]
