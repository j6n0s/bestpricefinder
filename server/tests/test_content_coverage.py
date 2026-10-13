"""Coverage rule (>= 90 % of a recipe's estimated cost in GVH-mapped ingredients) on a tiny fixture."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bpf.content.coverage import (
    COVERAGE_THRESHOLD,
    ReferencePrice,
    UnitPrice,
    choose_prices,
    compute_coverage,
    gvh_reference_prices,
    ksh_price,
    load_reference_prices,
    product_unit_price,
    recipe_coverage,
    reference_price,
    render_report,
)
from bpf.content.errors import ContentError
from bpf.content.ksh import load_ksh
from bpf.content.load import load_ingredients
from bpf.content.paths import REFERENCE_PRICES_CSV
from bpf.content.recipes import load_recipes
from bpf.pricing import Catalogue, Chain, ChainPrice, Ingredient, KshPrice, Product, Recipe, RecipeLine

FIXTURES = Path(__file__).parent / "fixtures" / "content"
KSH = load_ksh(FIXTURES / "ksh.csv")
ING = load_ingredients(FIXTURES / "ingredients.json", ksh=KSH, nutrition_codes=())
RECIPES = load_recipes(FIXTURES / "recipes", ING)
REFS = load_reference_prices(FIXTURES / "reference_prices.csv")


def prices(db: dict[str, Decimal] | None = None) -> dict[str, UnitPrice]:
    return choose_prices(ING.values(), db_prices=db or {}, refs=REFS, ksh=KSH)


def test_fixture_recipes_coverage_from_reference_and_ksh_prices() -> None:
    results = {r.recipe_id: r for r in compute_coverage(RECIPES.values(), ING, prices())}
    chicken = results["csirke-gombaval"]
    # csirkemell 0.5 kg x 2000 + hagyma 0.1 kg x 200 (GVH) = 1020; gomba 0.05 kg x KSH 2000 = 100
    assert (chicken.gvh_cost, chicken.total_cost) == (Decimal("1020.0"), Decimal("1120.00"))
    assert chicken.share == Decimal(1020) / Decimal(1120)
    assert chicken.ok
    lentils = results["lencse-tojassal"]
    assert lentils.total_cost == Decimal(
        "540.0"
    )  # 0.4 x 800 + 0.1 x 200 + 4 db x 50; oil and salt are pantry
    assert lentils.share == 1
    assert lentils.ok
    salmon = results["sult-lazac"]
    assert salmon.missing == ()  # the unpriced kapor line is optional, so it is not counted
    assert [ln.ingredient_id for ln in salmon.lines] == ["lazac"]  # pantry oil and salt left out
    assert all(r.ok for r in results.values())


def test_price_source_order() -> None:
    chosen = prices({"csirkemell": Decimal(1000)})
    assert chosen["csirkemell"] == UnitPrice(Decimal(1000), "db")  # DB price wins for GVH ingredients
    assert chosen["lencse"] == UnitPrice(Decimal(800), "reference")  # no DB price: reference CSV
    assert chosen["gomba"] == UnitPrice(Decimal(2000), "ksh")  # non-GVH: KSH first
    assert chosen["tojas"] == UnitPrice(Decimal(50), "reference")  # GVH: KSH is never used for it
    assert "kapor" not in chosen  # no price anywhere
    assert "so" not in chosen


def test_db_price_changes_the_share() -> None:
    chicken = RECIPES["csirke-gombaval"]
    cov = recipe_coverage(chicken, ING, prices({"csirkemell": Decimal(100), "voroshagyma": Decimal(100)}))
    # GVH: 0.5 x 100 + 0.1 x 100 = 60; KSH gomba 100 -> 37.5 %
    assert cov.share == Decimal(60) / Decimal(160)
    assert not cov.ok


def _recipe(*lines: tuple[str, str, bool]) -> Recipe:
    return Recipe(
        id="r",
        title="R",
        slots=("ebed",),
        servings=2,
        lines=tuple(
            RecipeLine(i + 1, ing, Decimal(qty), "x", optional)
            for i, (ing, qty, optional) in enumerate(lines)
        ),
    )


def test_threshold_is_inclusive() -> None:
    fixed = {"lencse": UnitPrice(Decimal(90), "reference"), "gomba": UnitPrice(Decimal(10), "ksh")}
    at_limit = recipe_coverage(_recipe(("lencse", "1", False), ("gomba", "1", False)), ING, fixed)
    assert at_limit.share == COVERAGE_THRESHOLD
    assert at_limit.ok
    fixed["gomba"] = UnitPrice(Decimal("10.0001"), "ksh")
    below = recipe_coverage(_recipe(("lencse", "1", False), ("gomba", "1", False)), ING, fixed)
    assert below.share is not None
    assert below.share < COVERAGE_THRESHOLD
    assert not below.ok


def test_missing_non_gvh_price_fails_the_recipe_and_is_reported() -> None:
    cov = recipe_coverage(_recipe(("lencse", "1", False), ("kapor", "0.01", False)), ING, prices())
    assert cov.missing == cov.missing_other == ("kapor",)
    assert cov.missing_gvh == ()
    assert cov.share == 1  # the priced part alone would pass...
    assert not cov.ok  # ...but the unpriced non-GVH line could be worth anything
    report = render_report([cov], price_note="test", full=True)
    assert "FAIL r: no price for kapor (not GVH-mapped, so the share is unknown)" in report
    assert (
        "Non-GVH ingredients without a price in KSH or the reference CSV (their recipes fail): kapor"
        in report
    )
    assert "MISSING PRICE" in report


def test_missing_gvh_price_gives_a_lower_bound() -> None:
    """An unpriced GVH line can only raise the GVH share, so it is left out and the share is a lower bound."""
    fixed = {"lencse": UnitPrice(Decimal(900), "reference"), "gomba": UnitPrice(Decimal(100), "ksh")}
    passing = recipe_coverage(
        _recipe(("lencse", "1", False), ("sertescomb", "1", False), ("gomba", "1", False)), ING, fixed
    )
    assert passing.missing == passing.missing_gvh == ("sertescomb",)
    assert (passing.gvh_cost, passing.total_cost) == (Decimal(900), Decimal(1000))
    assert passing.lower_bound
    assert passing.ok  # 90 % without the pork; any pork price raises it
    failing = recipe_coverage(
        _recipe(("lencse", "1", False), ("sertescomb", "1", False), ("gomba", "2", False)), ING, fixed
    )
    assert failing.share == Decimal(900) / Decimal(1100)
    assert not failing.ok
    report = render_report([passing, failing], price_note="test", full=True)
    assert "ok (lower bound)" in report
    assert "LOW (lower bound)" in report
    assert "FAIL r: 81.8% < 90.0% (lower bound: no price for sertescomb)" in report
    assert "(left out; the share is a lower bound): sertescomb" in report
    assert "Non-GVH ingredients" not in report


def test_only_unpriced_gvh_lines_pass() -> None:
    cov = recipe_coverage(_recipe(("sertescomb", "1", False), ("lazac", "1", False)), ING, {})
    assert cov.missing_gvh == ("sertescomb", "lazac")
    assert cov.share is None
    assert cov.ok  # every counted line is GVH-mapped: 100 % whatever the prices
    mixed = recipe_coverage(_recipe(("sertescomb", "1", False), ("kapor", "1", False)), ING, {})
    assert (mixed.missing_gvh, mixed.missing_other) == (("sertescomb",), ("kapor",))
    assert not mixed.ok


def test_repeated_ingredient_is_reported_once() -> None:
    cov = recipe_coverage(_recipe(("kapor", "0.01", False), ("kapor", "0.02", False)), ING, {})
    assert cov.missing == cov.missing_other == ("kapor",)
    assert len(cov.lines) == 2


def test_recipe_of_only_pantry_or_optional_lines_passes_with_no_share() -> None:
    cov = recipe_coverage(_recipe(("so", "0.01", False), ("kapor", "0.01", True)), ING, prices())
    assert cov.share is None
    assert cov.ok
    assert cov.lines == ()


def test_report_lists_low_recipes() -> None:
    low = recipe_coverage(_recipe(("lencse", "0.1", False), ("gomba", "1", False)), ING, prices())
    report = render_report([low], price_note="reference", full=False)
    assert "FAIL r: 3.8% < 90.0%" in report  # 80 / (80 + 2000)
    assert "1 recipe(s), 1 failing." in report
    assert "share" not in report.splitlines()[1]  # no table unless full


# ───────────────────────────── unit conversion of reference and KSH prices ─────────────────────────────


def _ing(unit: str, **kwargs: object) -> Ingredient:
    return Ingredient(id="x", name_hu="x", list_group="egyeb", unit=unit, **kwargs)  # type: ignore[arg-type]


def test_reference_price_conversions() -> None:
    per_kg = {"x": ReferencePrice("x", "kg", Decimal(1200), "")}
    roll = _ing("db", piece_weight_kg=Decimal("0.06"))
    assert reference_price(roll, per_kg) == UnitPrice(Decimal(72), "reference")  # 1200 Ft/kg x 0.06 kg
    per_piece = {"x": ReferencePrice("x", "db", Decimal(379), "")}
    cucumber = _ing("kg", piece_weight_kg=Decimal("0.35"))
    assert reference_price(cucumber, per_piece) == UnitPrice(Decimal(379) / Decimal("0.35"), "reference")
    per_l = {"x": ReferencePrice("x", "l", Decimal(1000), "")}
    assert reference_price(_ing("kg"), per_l) is None  # l -> kg needs a density
    assert reference_price(_ing("kg", density_kg_per_l=Decimal("1.25")), per_l) == UnitPrice(
        Decimal(800), "reference"
    )
    assert reference_price(_ing("db"), per_piece) == UnitPrice(Decimal(379), "reference")
    assert reference_price(_ing("db"), per_kg) is None  # kg -> db needs a piece weight
    assert reference_price(_ing("kg"), {}) is None


def test_reference_aliases() -> None:
    tv = Ingredient(id="tv_paprika", name_hu="tv", list_group="x", unit="db", piece_weight_kg=Decimal("0.11"))
    refs = {"zoldpaprika": ReferencePrice("zoldpaprika", "kg", Decimal(700), "")}
    assert reference_price(tv, refs) == UnitPrice(Decimal(77), "reference")


def test_ksh_price_conversions() -> None:
    eggs = KshPrice("11001", "Tojás, 10 darab", "db", Decimal(10), Decimal(814), date(2026, 9, 1))
    assert ksh_price(_ing("db", ksh_code="11001"), {"11001": eggs}) == UnitPrice(Decimal("81.4"), "ksh")
    by_kg = _ing("kg", ksh_code="11001", piece_weight_kg=Decimal("0.055"))
    assert ksh_price(by_kg, {"11001": eggs}) == UnitPrice(Decimal(814) / Decimal("0.550"), "ksh")
    assert ksh_price(_ing("kg", ksh_code="11001"), {"11001": eggs}) is None  # db -> kg without a weight
    assert ksh_price(_ing("kg", ksh_code="99999"), {"11001": eggs}) is None
    assert ksh_price(_ing("kg"), {"11001": eggs}) is None


# ───────────────────────────── DB chain prices (pure part) ─────────────────────────────


def _catalogue(products: list[Product], chain_prices: list[ChainPrice]) -> Catalogue:
    by_leaf: dict[int, list[str]] = {}
    for p in products:
        by_leaf.setdefault(p.category_id, []).append(p.id)
    chains = {
        "aldi": Chain("aldi", "aldi", "Aldi", True),
        "lidl": Chain("lidl", "lidl", "Lidl", True),
        "spar": Chain("spar", "spar", "Spar", True),
        "dm": Chain("dm", "dm", "dm", False),
    }
    return Catalogue(
        data_date=date(2026, 10, 13),
        ingredients=ING,
        products={p.id: p for p in products},
        chains=chains,
        stores={},
        chain_prices={(cp.product_id, cp.chain_id): cp for cp in chain_prices},
        store_prices={},
        availability={},
        products_by_leaf={leaf: tuple(ids) for leaf, ids in by_leaf.items()},
    )


def test_gvh_reference_prices_median_of_chain_minima() -> None:
    products = [
        Product("p1", "Friss csirkemellfilé", 18, "kg", "kg", None),  # by weight: price per kg
        Product("p2", "TESCO CSIRKEMELL FILÉ 500 g QQ", 18, "kg", "csomag", Decimal("0.5")),  # pack
        Product("p3", "Csirkemell tokány, kg", 18, "kg", "kg", None),  # excluded by the name rules
        Product("p4", "Pult csirkemellfilé", 18, "kg", "kg", None),
    ]
    cps = [
        ChainPrice("p1", "aldi", product_min_amount=Decimal(2000)),
        ChainPrice("p2", "aldi", product_min_amount=Decimal(900)),  # 1800 Ft/kg: Aldi's cheapest
        ChainPrice("p3", "lidl", product_min_amount=Decimal(100)),  # tokány: ignored
        ChainPrice("p1", "lidl", product_min_amount=None, xlsx_min=Decimal(1900), xlsx_max=Decimal(1900)),
        ChainPrice(
            "p4", "spar", product_min_amount=None, xlsx_min=Decimal(1500), xlsx_max=Decimal(2500)
        ),  # no price
        ChainPrice("p1", "spar", product_min_amount=Decimal(2400)),
        ChainPrice("p1", "dm", product_min_amount=Decimal(10)),  # not a grocery chain
    ]
    result = gvh_reference_prices([ING["csirkemell"], ING["kapor"]], _catalogue(products, cps))
    assert result == {"csirkemell": Decimal(1900)}  # median of Aldi 1800, Lidl 1900, Spar 2400


def test_gvh_reference_prices_even_number_of_chains_and_units() -> None:
    products = [
        Product("e1", "Friss Tojás 10 db", 14, "db", "csomag", Decimal(10)),
        Product("e2", "Tojás 30 db", 14, "db", "csomag", Decimal(30)),
    ]
    cps = [
        ChainPrice("e1", "aldi", product_min_amount=Decimal(500)),
        ChainPrice("e2", "lidl", product_min_amount=Decimal(1800)),
    ]
    result = gvh_reference_prices([ING["tojas"]], _catalogue(products, cps))
    assert result == {"tojas": Decimal(55)}  # median of 50 and 60 Ft/db


def test_product_unit_price() -> None:
    onion = ING["voroshagyma"]  # kg, piece weight 0.12
    net = Product("n", "Vöröshagyma 3 db/csomag", 40, "db", "csomag", Decimal(3))
    assert product_unit_price(net, Decimal(72), onion) == Decimal(200)  # 72 Ft / 0.36 kg
    loose = Product("l", "Vöröshagyma lédig", 40, "kg", "kg", Decimal(1))
    assert product_unit_price(loose, Decimal(199), onion) == Decimal(199)
    oil = ING["olaj"]
    assert product_unit_price(Product("o", "olaj", 51, "kg", "csomag", Decimal(1)), Decimal(1), oil) is None


# ───────────────────────────── the research reference file ─────────────────────────────


def test_research_reference_prices_load() -> None:
    refs = load_reference_prices(REFERENCE_PRICES_CSV)
    assert refs["voroshagyma"].unit == "kg"
    assert refs["voroshagyma"].price == Decimal("207.0")
    assert refs["tojas"].unit == "db"
    assert refs["gomba"].basis.startswith("KSH ara0044")


def test_bad_reference_files(tmp_path: Path) -> None:
    path = tmp_path / "refs.csv"
    path.write_text("key,unit,price\nx,kg,1\n")
    with pytest.raises(ContentError, match="expected columns"):
        load_reference_prices(path)
    path.write_text("key,cls,unit,price,basis\nx,E,kg,abc,\n")
    with pytest.raises(ContentError, match="bad price"):
        load_reference_prices(path)
    path.write_text("key,cls,unit,price,basis\nx,E,g,1,\n")
    with pytest.raises(ContentError, match="bad unit or price"):
        load_reference_prices(path)
    with pytest.raises(ContentError, match="cannot read"):
        load_reference_prices(tmp_path / "missing.csv")
