"""data/ingredients.json: every validation rule (good and bad fixtures), and the real ontology."""

from __future__ import annotations

import csv
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bpf.content.coverage import REFERENCE_ALIASES, load_reference_prices
from bpf.content.errors import ContentError
from bpf.content.ingredients import parse_ingredients
from bpf.content.ksh import load_ksh
from bpf.content.leaves import FOOD_TOP_CATEGORIES, FoodLeaves, food_leaves_from_csv
from bpf.content.load import load_ingredients
from bpf.content.paths import INGREDIENTS_PATH, LEAF_CATEGORIES_CSV, REFERENCE_PRICES_CSV
from bpf.content.vocab import INGREDIENT_TAGS, LIST_GROUPS
from bpf.pricing import Catalogue, Chain, Ingredient, Product, candidate_products, fold_name

FIXTURES = Path(__file__).parent / "fixtures" / "content"
LEAVES = food_leaves_from_csv(LEAF_CATEGORIES_CSV)
KSH = load_ksh(FIXTURES / "ksh.csv")


def good(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "csirkemell",
        "name_hu": "csirkemellfilé",
        "list_group": "hus_hal",
        "unit": "kg",
        "piece_weight_kg": None,
        "density_kg_per_l": None,
        "pantry": False,
        "leaf_ids": [18],
        "include_patterns": [],
        "exclude_patterns": ["tokany"],
        "product_units": [],
        "ksh_code": None,
        "nutrition_code": None,
        "tags": ["poultry"],
        "perishable_days": 2,
        "notes": None,
    }
    item.update(overrides)
    return item


def problems_of(
    items: list[Any], *, nutrition_codes: frozenset[str] = frozenset(), top: Any = None
) -> list[str]:
    data = top if top is not None else {"version": 1, "ingredients": items}
    try:
        parse_ingredients(data, "ing.json", leaves=LEAVES, ksh=KSH, nutrition_codes=nutrition_codes)
    except ContentError as exc:
        return list(exc.problems)
    return []


def assert_problem(items: list[Any], expected: str, **kwargs: Any) -> None:
    found = problems_of(items, **kwargs)
    assert any(expected in p for p in found), found


# ───────────────────────────── good fixtures ─────────────────────────────


def test_fixture_ontology_loads() -> None:
    ingredients = load_ingredients(FIXTURES / "ingredients.json", ksh=KSH, nutrition_codes=())
    assert list(ingredients) == sorted(ingredients)
    egg = ingredients["tojas"]
    assert isinstance(egg, Ingredient)
    assert (egg.unit, egg.piece_weight_kg, egg.product_units) == ("db", Decimal("0.055"), ("db",))
    assert ingredients["olaj"].pantry
    assert ingredients["olaj"].leaf_ids == (51,)


@pytest.mark.parametrize(
    "item",
    [
        good(),
        good(unit="db", piece_weight_kg=Decimal("0.2"), product_units=["db", "kg"]),
        good(product_units=["db"], piece_weight_kg=Decimal("0.0002")),
        good(unit="l", density_kg_per_l=Decimal("1.03"), product_units=["l", "kg"], tags=["dairy"]),
        good(pantry=True, leaf_ids=[51], exclude_patterns=[], tags=["fat_oil"]),  # pantry with leaves
        good(pantry=True, leaf_ids=[], exclude_patterns=[], tags=["spice"]),  # pantry, never priced
        good(leaf_ids=[], exclude_patterns=[], ksh_code="14111", tags=["vegetable"]),
        good(
            unit="db", piece_weight_kg=Decimal("0.055"), leaf_ids=[14], exclude_patterns=[], ksh_code="11001"
        ),
        good(unit="kg", piece_weight_kg=Decimal("0.055"), leaf_ids=[], exclude_patterns=[], ksh_code="11001"),
        good(nutrition_code="C1"),
        good(perishable_days=None, notes="x" * 500, density_kg_per_l=Decimal("4.999")),
        good(piece_weight_kg=Decimal("9999.9999")),
        good(piece_weight_kg=Decimal("0.1200")),  # trailing zeros do not count as decimals
        good(leaf_ids=[68, 120]),  # 'Speciális étrend' leaves are food too
    ],
)
def test_good_ingredients(item: dict[str, Any]) -> None:
    assert problems_of([item], nutrition_codes=frozenset({"C1"})) == []


# ───────────────────────────── bad fixtures, one rule each ─────────────────────────────


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"id": "Csirke"}, "must match"),
        ({"id": "a"}, "must match"),
        ({"id": "x" * 41}, "must match"),
        ({"id": "csirke-mell"}, "must match"),
        ({"id": "csirke\n"}, "must match"),
        ({"id": 5}, "must match"),
        ({"name_hu": ""}, "name_hu: must be a string of 1-80"),
        ({"name_hu": " csirke"}, "name_hu: must be a string of 1-80"),
        ({"name_hu": "x" * 81}, "name_hu: must be a string of 1-80"),
        ({"list_group": "hus"}, "list_group: 'hus' is not one of"),
        ({"unit": "g"}, "unit: 'g' is not one of"),
        ({"piece_weight_kg": 0}, "piece_weight_kg: must be null or a number greater than 0"),
        ({"piece_weight_kg": Decimal("-0.1")}, "piece_weight_kg: must be null or a number greater than 0"),
        ({"piece_weight_kg": "0.1"}, "piece_weight_kg: must be null or a number greater than 0"),
        ({"piece_weight_kg": True}, "piece_weight_kg: must be null or a number greater than 0"),
        ({"piece_weight_kg": Decimal("10000")}, "piece_weight_kg: must be null or a number greater than 0"),
        ({"piece_weight_kg": Decimal("0.00001")}, "more than 4 decimals"),
        ({"density_kg_per_l": Decimal(5)}, "density_kg_per_l: must be null or a number greater than 0"),
        ({"density_kg_per_l": 0}, "density_kg_per_l: must be null or a number greater than 0"),
        ({"density_kg_per_l": Decimal("1.0005")}, "more than 3 decimals"),
        ({"pantry": "no"}, "pantry: must be true or false"),
        ({"pantry": 0}, "pantry: must be true or false"),
        ({"leaf_ids": [999]}, "999 is not a GVH food leaf"),
        ({"leaf_ids": [126]}, "126 is not a GVH food leaf"),  # Toalettpapír: a leaf, but not food
        ({"leaf_ids": [2001]}, "2001 is not a GVH food leaf"),  # level-2 node, not a leaf
        ({"leaf_ids": [123]}, "123 is not a GVH food leaf"),  # baby food: not a food top category
        ({"leaf_ids": ["18"]}, "must be a list of integers"),
        ({"leaf_ids": [True]}, "must be a list of integers"),
        ({"leaf_ids": 18}, "must be a list of integers"),
        ({"leaf_ids": [18, 18]}, "leaf_ids: contains duplicates"),
        ({"include_patterns": ["Csirke"]}, "lower case"),
        ({"include_patterns": ["filé"]}, "must be ASCII"),
        ({"exclude_patterns": ["panírozott"]}, "must be ASCII"),
        ({"exclude_patterns": ["x" * 121]}, "121 characters"),
        ({"exclude_patterns": ["(tokany"]}, "does not compile"),
        ({"exclude_patterns": ["a?"]}, "matches the empty string"),
        ({"exclude_patterns": ["tokany", "tokany"]}, "contains duplicates"),
        ({"include_patterns": "csirke"}, "must be a list of strings"),
        ({"include_patterns": [1]}, "must be a list of strings"),
        ({"leaf_ids": [], "exclude_patterns": ["tokany"]}, "need leaf_ids"),
        ({"leaf_ids": [], "exclude_patterns": [], "product_units": ["kg"]}, "need leaf_ids"),
        ({"product_units": ["g"]}, "'g' is not one of"),
        ({"product_units": ["kg", "kg"]}, "contains duplicates"),
        ({"unit": "db"}, "unit db or a db product unit requires piece_weight_kg"),
        ({"product_units": ["kg", "db"]}, "unit db or a db product unit requires piece_weight_kg"),
        ({"unit": "l", "product_units": ["kg"], "tags": ["dairy"]}, "requires density_kg_per_l"),
        ({"product_units": ["l"]}, "requires density_kg_per_l"),
        ({"unit": "l", "tags": ["red_meat"]}, "must be weighable in kg"),
        ({"tags": ["chicken"]}, "'chicken' is not one of"),
        ({"tags": ["poultry", "poultry"]}, "contains duplicates"),
        ({"ksh_code": "99999"}, "99999 is not in the KSH file"),
        ({"ksh_code": "bad code"}, "must be null or match"),
        ({"ksh_code": 11001}, "must be null or match"),
        (
            {"ksh_code": "11001"},
            "priced per db, which does not convert to kg",
        ),  # eggs per db, no piece weight
        ({"unit": "l", "density_kg_per_l": Decimal(1), "ksh_code": "11001"}, "priced per db"),
        ({"nutrition_code": "X9"}, "'X9' is not in the nutrition file"),
        ({"nutrition_code": "x" * 41}, "must be null or 1-40 characters"),
        ({"perishable_days": 0}, "perishable_days: must be null or an integer from 1 to 3650"),
        ({"perishable_days": 3651}, "perishable_days: must be null or an integer from 1 to 3650"),
        ({"perishable_days": Decimal("1.5")}, "perishable_days: must be null or an integer"),
        ({"perishable_days": True}, "perishable_days: must be null or an integer"),
        ({"notes": "x" * 501}, "notes: must be null or a string of at most 500"),
        ({"notes": 5}, "notes: must be null or a string"),
        ({"name_hu": "egészséges csirkemell"}, "health-claim words"),
        ({"notes": "Diétás termék."}, "health-claim words"),
    ],
)
def test_bad_ingredient(overrides: dict[str, Any], expected: str) -> None:
    assert_problem([good(**overrides)], expected, nutrition_codes=frozenset({"C1"}))


def test_missing_and_unknown_keys() -> None:
    item = good()
    del item["notes"]
    item["colour"] = "red"
    found = problems_of([item])
    assert any("missing keys: notes" in p for p in found)
    assert any("unknown keys: colour" in p for p in found)
    assert_problem(["not an object"], "must be a JSON object")


def test_duplicate_ids_names_and_sort_order() -> None:
    assert_problem([good(), good()], "duplicate id 'csirkemell'")
    assert_problem([good(id="b_item"), good(id="a_item", name_hu="más")], "must be sorted by id")
    assert_problem(
        [good(id="a_item"), good(id="b_item", name_hu="CSIRKEMELLFILÉ")], "is also used by 'a_item'"
    )


@pytest.mark.parametrize(
    ("top", "expected"),
    [
        ({"version": 2, "ingredients": [good()]}, "version: must be 1"),
        ({"version": True, "ingredients": [good()]}, "version: must be 1"),
        ({"version": 1, "ingredients": []}, "must be a non-empty list"),
        ({"version": 1, "ingredients": {}}, "must be a non-empty list"),
        ({"version": 1}, "missing keys: ingredients"),
        ({"version": 1, "ingredients": [good()], "extra": 1}, "unknown keys: extra"),
        ([good()], "must be a JSON object"),
    ],
)
def test_bad_top_level(top: Any, expected: str) -> None:
    assert_problem([], expected, top=top)


def test_every_problem_is_reported_at_once() -> None:
    found = problems_of([good(id="b_x", unit="g", tags=["x"]), good(id="a_x", name_hu="m", leaf_ids=[999])])
    assert len(found) >= 4  # unit, tag, leaf and sort order, all in one error


def test_food_leaves_from_the_research_list() -> None:
    assert len(LEAVES.names) == 120  # BUILD-BRIEF §3: 120 food leaves
    assert {18, 120} <= set(LEAVES.names)
    assert not {126, 123} & set(LEAVES.names)
    assert len(FOOD_TOP_CATEGORIES) == 6


def test_leaf_check_uses_the_given_leaf_set() -> None:
    only_lentils = FoodLeaves({96: "Lencse"}, "core.category")
    with pytest.raises(ContentError, match=r"18 is not a GVH food leaf \(checked against core.category\)"):
        parse_ingredients({"version": 1, "ingredients": [good()]}, "x", leaves=only_lentils, ksh=KSH)


# ───────────────────────────── the real ontology ─────────────────────────────

REAL = load_ingredients(INGREDIENTS_PATH)


def test_real_ontology_passes_validation_and_has_the_planned_size() -> None:
    assert 130 <= len(REAL) <= 170
    groups = Counter(ing.list_group for ing in REAL.values())
    assert set(groups) == set(LIST_GROUPS)


def test_real_ontology_covers_the_gvh_list_of_build_brief_section_5() -> None:
    covered = {leaf for ing in REAL.values() for leaf in ing.leaf_ids}
    brief_leaves = {
        17,
        18,
        19,
        21,  # chicken (whole, breast, thigh), turkey breast
        15,
        16,
        85,
        86,  # pork leg and loin, minced pork and beef
        91,
        92,
        93,  # carp, catfish, sea fish fillet (incl. salmon)
        14,
        9,
        7,
        5,
        6,
        8,
        10,
        1,
        2,
        3,
        4,  # eggs, túró, yoghurt, tejföl, kefir, cheese, milk
        96,
        95,
        50,
        48,
        49,
        52,
        51,  # lentils, rice, pasta, wholemeal and rye bread, flour, oil
        34,
        35,
        36,
        37,
        38,
        40,
        39,
        41,
        43,
        44,
        45,
        97,
        59,
        98,  # vegetables, frozen peas and broccoli
        28,
        29,
        30,
        31,
        32,
        33,  # apple, pear, strawberry, banana, lemon, orange
    }
    assert brief_leaves <= covered, brief_leaves - covered


def test_real_ontology_reuses_research_keys() -> None:
    research_keys = set(load_reference_prices(REFERENCE_PRICES_CSV))
    for key in (
        "voroshagyma",
        "lencse",
        "fokhagyma",
        "tojas",
        "csirkemell",
        "turo",
        "joghurt",
        "kefir",
        "rizs",
        "teszta",
        "teszta_tk",
        "kenyer_tk",
        "burgonya",
        "olaj",
        "olivaolaj",
        "gomba",
        "szarazbab",
        "dio",
        "mez",
        "lazac",
        "tokehal",
        "harcsa",
        "ponty",
        "trappista",
        "tejfol12",
        "tejfol20",
    ):
        assert key in REAL, key
        assert key in research_keys, key
    for alias, target in REFERENCE_ALIASES.items():
        assert alias in REAL, alias
        assert target in research_keys, target


def test_every_gvh_ingredient_has_a_reference_price_except_the_documented_ones() -> None:
    refs = load_reference_prices(REFERENCE_PRICES_CSV)
    without = {
        ing.id for ing in REAL.values() if ing.leaf_ids and REFERENCE_ALIASES.get(ing.id, ing.id) not in refs
    }
    # GVH leaves the research did not price: their recipes are reported until the DB has prices.
    assert without == {
        "csirkeszarny",
        "egesz_csirke",
        "ementali",
        "feherpecsenye",
        "hasabburgonya",
        "parizsi",
        "sertes_tarja",
        "virsli",
    }


def test_real_ontology_pantry_staples_and_ksh_codes() -> None:
    for staple in (
        "so",
        "bors",
        "pirospaprika",
        "olaj",
        "olivaolaj",
        "finomliszt",
        "cukor",
        "ecet",
        "baberlevel",
        "romai_komeny",
        "komenymag",
        "majoranna",
        "oregano",
        "fahej",
        "alaple",
        "viz",
    ):
        assert REAL[staple].pantry, staple
    expected_ksh = {
        "pirospaprika": "15202",
        "szarazbab": "14601",
        "gomba": "14111",
        "dio": "14701",
        "mez": "13910",
        "lekvar": "14508",
        "so": "15204",
        "gorogdinnye": "14202",
    }
    for ing_id, code in expected_ksh.items():
        assert REAL[ing_id].ksh_code == code
    assert {i.id for i in REAL.values() if i.ksh_code} == set(expected_ksh)
    for ing in REAL.values():
        if ing.ksh_code:
            assert not ing.leaf_ids, f"{ing.id}: ksh_code is for non-GVH ingredients"


def test_real_ontology_tags() -> None:
    def tagged(tag: str) -> set[str]:
        return {i.id for i in REAL.values() if tag in i.tags}

    assert tagged("red_meat") == {
        "sertescomb",
        "sertes_karaj",
        "sertes_tarja",
        "daralt_sertes",
        "marha",
        "feherpecsenye",
        "daralt_marha",
        "sonka",
        "kolbasz",
        "szalonna",
    }
    assert tagged("processed_meat") == {"sonka", "pulykasonka", "kolbasz", "szalonna", "virsli", "parizsi"}
    assert tagged("legume") == {"lencse", "szarazbab", "sargaborso", "csicseri", "voros_bab_konzerv"}
    assert tagged("fish") == {"lazac", "tokehal", "harcsa", "ponty", "tonhal_konzerv"}
    assert tagged("poultry") >= {"csirkemell", "csirkecomb", "egesz_csirke", "pulykamell", "pulykasonka"}
    assert tagged("potato") == {"burgonya", "ujburgonya", "hasabburgonya"}
    assert tagged("egg") == {"tojas"}
    assert "legume" not in REAL["zoldborso"].tags  # green peas are a vegetable
    assert tagged("wholegrain") == {"kenyer_tk", "teszta_tk", "barna_rizs", "zabpehely"}
    assert tagged("sweet") >= {"cukor", "porcukor", "mez", "lekvar"}
    assert set().union(*(i.tags for i in REAL.values())) <= INGREDIENT_TAGS


RESEARCH_PIECE_WEIGHTS = {
    "voroshagyma": "0.12",
    "fokhagyma": "0.067",
    "tv_paprika": "0.11",
    "zoldpaprika": "0.11",
    "sargarepa": "0.08",
    "petrezselyemgyoker": "0.08",
    "citrom": "0.1",
    "alma": "0.18",
    "korte": "0.18",
    "banan": "0.17",
    "uborka": "0.35",
    "karfiol": "0.75",
    "tojas": "0.055",
}


def test_piece_weights_come_from_the_research_or_are_labelled_estimates() -> None:
    for ing_id, weight in RESEARCH_PIECE_WEIGHTS.items():
        assert REAL[ing_id].piece_weight_kg == Decimal(weight), ing_id
    notes = {r["id"]: r["notes"] or "" for r in _raw_items()}
    for ing in REAL.values():
        if ing.piece_weight_kg is not None:
            assert "ESTIMATE" in notes[ing.id] or "COMPUTED" in notes[ing.id], ing.id
        if ing.density_kg_per_l is not None:
            assert "ESTIMATE" in notes[ing.id], ing.id


def test_densities_only_for_dairy_sold_by_volume_and_weight() -> None:
    with_density = {i.id: i.density_kg_per_l for i in REAL.values() if i.density_kg_per_l is not None}
    assert set(with_density) == {
        "tejfol12",
        "tejfol20",
        "joghurt",
        "gorog_joghurt",
        "kefir",
        "fozotejszin",
        "habtejszin",
    }
    assert all(Decimal("0.95") <= d <= Decimal("1.1") for d in with_density.values())


def _raw_items() -> list[dict[str, Any]]:
    from bpf.content.jsonio import read_json

    return list(read_json(INGREDIENTS_PATH)["ingredients"])


def test_real_file_is_canonically_formatted() -> None:
    """2-space indent, keys in DATA.md order, sorted by id, UTF-8 without escapes, final newline."""
    text = INGREDIENTS_PATH.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert "\\u" not in text
    assert "\t" not in text
    items = _raw_items()
    assert [i["id"] for i in items] == sorted(i["id"] for i in items)
    assert all(list(i) == list(good()) for i in items)


# ───────────────────────────── name rules against real GVH product names ─────────────────────────────


def _names() -> list[dict[str, str]]:
    with (FIXTURES / "gvh_product_names.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


NAMES = _names()


def accepted(ing_id: str) -> set[str]:
    """Names in the ingredient's leaves that pass its include (ANY) / exclude (NONE) rules."""
    ing = REAL[ing_id]
    inc = [re.compile(p) for p in ing.include_patterns]
    exc = [re.compile(p) for p in ing.exclude_patterns]
    result = set()
    for row in NAMES:
        if int(row["leaf_id"]) not in ing.leaf_ids:
            continue
        folded = fold_name(row["name"])
        if (not inc or any(p.search(folded) for p in inc)) and not any(p.search(folded) for p in exc):
            result.add(row["name"])
    return result


def in_leaves(ing_id: str) -> set[str]:
    return {row["name"] for row in NAMES if int(row["leaf_id"]) in REAL[ing_id].leaf_ids}


EXPECTATIONS: dict[str, tuple[list[str], list[str]]] = {
    # ingredient: (names that must match, names that must not)
    "csirkemell": (
        [
            "14. FRISS CSIRKEMELL FILE PULTOS QQ",
            "Friss csirke belső mellfilé Ft/kg",
            "TESCO CSIRKEMELL FILÉ 500 g QQ",
        ],
        ["Csirkemell tokány, kg", "Húsfarm Felezett csirkemell, 650g"],
    ),
    "joghurt": (
        [
            "Milsani natúr joghurt 0,1% 175g",
            "Cserpes Sajtműhely natúr joghurt élőflórás 250 g",
            "NADUDVARI JOGHURT NATUR 3% 900 g QQ",
        ],
        [
            "Tejmalom érlelt trappista db",
            "Pro görnatjog 1 kg QQ",
            "DANONE GÖRÖG STILUSU JOGHURT 375 g QQ",
            "RN NATÚR GÖRÖG LIGHT JOGHURT 1 kg QQ",
        ],
    ),
    "gorog_joghurt": (
        [
            "Pro görnatjog 1 kg QQ",
            "DANONE GÖRÖG STILUSU JOGHURT 375 g QQ",
            "RN NATÚR GÖRÖG LIGHT JOGHURT 1 kg QQ",
            "Koliós Hercules High Protein zsírmentes görög joghurt 200 g",
        ],
        ["Milsani natúr joghurt 0,1% 175g", "Tejmalom érlelt trappista db"],
    ),
    "olivaolaj": (
        [
            "MONINI EXT.SZŰZ  OLIVAOLAJ 0,5L",
            "Frantó extra sz.olívaolaj750ml",
            "ESP. EVO 0,75l",
            "TS EXTRA VIRGIN OLIVE OIL 750 ml",
            "DESPAR extraszűz olívaolaj 1 l",
            "Korvel extra szűz olívaolaj 1 l",
        ],
        [
            "Primadonna Olívaolaj finomított és szűz olívaolajból, 1l",
            "Bellasan olívaolaj 1 l",
            "Orfeas Classic olívaolaj 1 l",
            "KAEFER OLIVENOEL EXTRA VERGINE BASILICO",
            "Dante extra szűz olívaolaj citrom darabokkal 250 ml",
            "BERTOLLI AIRFRYER OLÍVAOLAJ SPRAY 200ML*HU",
            "Mantova narancsos-fekete borsos extra szűz olíva olaj spray",
        ],
    ),
    "lazac": (
        [
            "MSC vadlazac filé 250g",
            "TS Atlantic salmon fillet portions 250 g",
            "Pult defrost norvég lazacfilé Ft/kg",
            "Selfish lazacfilé natúr 160 g",
        ],
        [
            "Fjord formázott lazac burger 2x100 g",
            "Selfish norvég lazacfilé grillfűszeres pácban 160 g",
            "Norvég lazacfilé+fűszervaj",
            "Seafood lazacfilé fűszeres vajjal 160 g",
            "Alaszkai tőkehalfilé",
        ],
    ),
    "tokehal": (
        [
            "TESCO ALAS. TOK EHAL FILE 475G",
            "TESCO ALASZKAI T OKEHAL 400G",
            "CLASSIC GYF.HEKK FILE 900G",
            "Alaszkai tőkehalfilé",
            "ROZMÁR LEPÉNYHAL FILÉ GYORSFAGY. 700 g",
        ],
        ["Gran m.pan.halszelet filéből", "MSC vadlazac filé 250g"],
    ),
    "trappista": (
        ["Tolle trappista sajt kg", "Milbona Trapper tégla sajt", "MIZO TRAPPISTA SAJT FT/KG"],
        ["Cheeseland füstölt edami sajt", "PURE MILK SAJTHASÁB", "Tolle füstölt, félkemény trappista sajt"],
    ),
    "kenyer_tk": (
        ["TELJ.K.TÖBBMAGV. KENYÉR 500G", "Teljes kiőrlésű kenyér 500 g", "Mátyás kenyere telj.kiőrl."],
        [
            "Kemencés Kedvencek fehér kenyér vagy teljeskiörlésű kenyér 4",
            "Kemencés kedvencek  (teljes kiőrlésű kenyér és félbarna kenyér) vegyes karton, 400g",
        ],
    ),
    "teszta_tk": (
        [
            "TO TELJK. FUSILLI 500G",
            "TS TEL.KIORLESU ORSO SZT.500G",
            "BARILLA T.KIŐR. SPAGHETTI 500G",
            "San fabio tejl.kiörl.spagetti",
            "BIO GOURMET SPAGETTI TK. DURUM SZÁRAZTÉSZTA 500 g",
            "Granoro Dedicato teljeskiőrlésű spaghetti száraztészta 500 g",
            "TS TELJ.KIÖR.SPA GETTI SZT.500G",
        ],
        [
            "ALNATURA SPAGETTI 500 g TELJES KIŐRLÉSŰ TÖNKÖLY",
            "Barilla Spaghetti szálas durum száraztészta 500 g",
        ],
    ),
    "teszta": (
        ["Barilla Spaghetti szálas durum száraztészta 500 g", "Tesco 4 tojásos spagetti 500 g", "Penne 500g"],
        [
            "TO TELJK. FUSILLI 500G",
            "BARILLA T.KIŐR. SPAGHETTI 500G",
            "Divella trikolor spagetti száraztészta 500 g",
            "ALNATURA TÖNKÖLY SPAGETTI 500 g",
        ],
    ),
    "teszta_tojasos": (
        [
            "HF 2T ORSÓ 500 G",
            "TS 4 TOJ. ORSO 5 00G",
            "SPAR spagetti négytojásos száraztészta 500 g",
            "Szabó spagetti 4tojásos 500g",
            "GYERMELYI 4 TOJ.  RÖVIDCSŐ 500G",
        ],
        [
            "Rummo Fusilli tojás nélküli durum száraztészta 500 g",
            "Barilla Spaghetti szálas durum száraztészta 500 g",
        ],
    ),
    "rizs": (["B rizs", "MESTER B RIZS 1  KG"], ["enerBiO basmati rizs - 1 kg", "Jázmin rizs"]),
    "daralt_sertes": ([], ["Darált sertés-marhahús"]),
    "voroshagyma": (["Vöröshagyma 3 db/csomag", "VÖRÖSHAGYMA LÉDIG QQ"], ["Salátahagyma 3 db"]),
    "banan": (["Banán bandázsolt 5 db/fürt"], ["Főzőbanán lédig"]),
    "tv_paprika": (["Hazai TV paprika 3db", "Étkezési fehér paprika 500 g"], ["Lecsópaprika 750g"]),
    "zoldpaprika": (["Lecsópaprika 750g", "Hazai TV paprika 3db"], []),
    "fokhagyma": (["Fokhagyma 3 db/csomag", "TS FOKHAGYMA 3 db QQ"], []),
    "tojas": (["Friss Tojás 10 db, S-es", "MU 30DB TOJÁS 1290G S MÉRET QQ"], []),
}


@pytest.mark.parametrize("ing_id", sorted(EXPECTATIONS))
def test_name_rules_on_real_gvh_names(ing_id: str) -> None:
    must, must_not = EXPECTATIONS[ing_id]
    names_here = in_leaves(ing_id)
    got = accepted(ing_id)
    for name in must + must_not:
        assert name in names_here, f"fixture lacks {name!r}"
    assert set(must) <= got, set(must) - got
    assert not set(must_not) & got, set(must_not) & got


def test_wholemeal_and_plain_pasta_rules_are_disjoint() -> None:
    assert not accepted("teszta") & accepted("teszta_tk")
    assert not accepted("joghurt") & accepted("gorog_joghurt")
    assert not accepted("lazac") & accepted("tokehal")


def test_no_include_rule_is_dead() -> None:
    """Every GVH ingredient with real names in its leaves accepts at least one (no rule matches nothing)."""
    dead = [i for i in REAL if REAL[i].leaf_ids and in_leaves(i) and not accepted(i)]
    assert dead == ["daralt_sertes"]  # its only sample name is a pork-beef mix, excluded on purpose


def test_rules_through_the_pricing_engine() -> None:
    """The same rules via bpf.pricing.candidate_products (leaf, name and unit filters together)."""
    rows = [r for r in NAMES if r["unit"] in ("kg", "l", "db")]
    products = {
        f"p{i}": Product(f"p{i}", r["name"], int(r["leaf_id"]), r["unit"]) for i, r in enumerate(rows)
    }
    by_leaf: dict[int, list[str]] = {}
    for pid, product in products.items():
        by_leaf.setdefault(product.category_id, []).append(pid)
    cat = Catalogue(
        data_date=None,
        ingredients=REAL,
        products=products,
        chains={"c": Chain("c", "c", "C", True)},
        stores={},
        chain_prices={},
        store_prices={},
        availability={},
        products_by_leaf={leaf: tuple(ids) for leaf, ids in by_leaf.items()},
    )
    names = {ing_id: {p.name for p in candidate_products(REAL[ing_id], cat)} for ing_id in REAL}
    assert "Csirkemell tokány, kg" not in names["csirkemell"]
    assert "14. FRISS CSIRKEMELL FILE PULTOS QQ" in names["csirkemell"]
    assert "Vöröshagyma 3 db/csomag" in names["voroshagyma"]  # db product converts with the piece weight
    assert "Csomós sárgarépa" not in names["sargarepa"]  # db bunch excluded by product_units kg
    assert "Sárgarépa 2kg" in names["sargarepa"]
    assert "Friss Tojás 10 db, S-es" in names["tojas"]
    for ing_id in REAL:
        assert names[ing_id] <= accepted(ing_id), ing_id


def test_ingredient_counts_by_group_and_tag_are_stable() -> None:
    """Pins the shape of the ontology (update deliberately together with data/ingredients.json)."""
    groups = Counter(ing.list_group for ing in REAL.values())
    assert sum(groups.values()) == len(REAL) == 159
    assert groups == Counter(
        {
            "zoldseg_gyumolcs": 47,
            "pekaru": 7,
            "tejtermek_tojas": 23,
            "hus_hal": 23,
            "szaraz_tartos": 32,
            "fagyasztott": 5,
            "fuszer_olaj": 21,
            "egyeb": 1,
        }
    )
