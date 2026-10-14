"""Pure parts of the ingest (no database): dates, chain slugs, store formats and validation, categories, and
the listing + XLSX merge that becomes product_chain_day (BUILD-BRIEF §4.1 traps 1, 2, 5, 8, 10)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from bpf.gvh import GvhClient
from bpf.gvh.client import CategoryListing
from bpf.gvh.models import (
    ChainStore,
    parse_categories,
    parse_chain_stores,
    parse_product_page,
    parse_shop_prices,
    parse_shops,
)
from bpf.ingest import budapest_today, chain_slug, store_format
from bpf.ingest.common import IngestError, RunLog
from bpf.ingest.daily import (
    API_XLSX_MISMATCH_MAX_SHARE,
    ChainDayRow,
    ChainRef,
    ChainResolver,
    Issues,
    Snapshot,
    build_snapshot,
    check_date_agreement,
    date_agreement,
    listing_daily_min,
    per_store_targets,
    store_price_rows,
)
from bpf.ingest.reference import ChainRow, category_rows, chain_rows, coordinate_outliers, store_rows
from tests.fakegvh import (
    FakeClock,
    FakeGvh,
    build_world,
    category_tree,
    chain_stores_json,
    compared_pairs,
    fake_settings,
    shops_json,
    summarise,
)

DAY = date(2026, 10, 13)
WORLD = build_world()


def codes(log: RunLog) -> list[str]:
    return [w["code"] for w in log.warnings]


# ───────────────────────────── data date ─────────────────────────────


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (datetime(2026, 10, 12, 22, 30, tzinfo=UTC), date(2026, 10, 13)),  # 00:30 CEST: already the 13th
        (datetime(2026, 10, 12, 21, 59, tzinfo=UTC), date(2026, 10, 12)),
        (datetime(2026, 1, 5, 23, 30, tzinfo=UTC), date(2026, 1, 6)),  # CET (UTC+1)
        (datetime(2026, 1, 5, 22, 59, tzinfo=UTC), date(2026, 1, 5)),
        (datetime(2026, 10, 13, 4, 30, tzinfo=timezone(timedelta(hours=2))), date(2026, 10, 13)),
    ],
)
def test_data_date_is_today_in_budapest(instant: datetime, expected: date) -> None:
    assert budapest_today(lambda: instant) == expected


def test_data_date_needs_an_aware_clock() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        budapest_today(lambda: datetime(2026, 10, 13, 4, 30))  # noqa: DTZ001 - the point of the test


# ───────────────────────────── chains ─────────────────────────────


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Müller", "muller"),
        ("MÜLLER", "muller"),
        ("Mueller", "muller"),
        ("Spar", "spar"),
        ("SPAR", "spar"),
        ("PENNY Market", "penny"),
        ("dm drogerie markt", "dm"),
        ("Tesco-Global Áruházak", "tesco"),
        ("Lidl Magyarország", "lidl"),
        ("Aldi", "aldi"),
        ("Auchan", "auchan"),
        ("Rossmann", "rossmann"),
        ("CBA Príma", "cba-prima"),
        ("Új   Lánc!!", "uj-lanc"),
    ],
)
def test_chain_slug(name: str, slug: str) -> None:
    assert chain_slug(name) == slug


def test_chain_slug_needs_letters() -> None:
    with pytest.raises(ValueError, match="slug"):
        chain_slug(" -- ")


def test_chain_rows_from_the_fake() -> None:
    chains = parse_chain_stores(json.dumps({"chainStores": chain_stores_json(WORLD)}).encode()).value
    log = RunLog()
    rows = {row.slug: row for row in chain_rows(chains, log)}
    assert sorted(rows) == ["aldi", "auchan", "dm", "lidl", "muller", "penny", "rossmann", "spar", "tesco"]
    assert {slug for slug, row in rows.items() if row.is_grocery} == {
        "aldi",
        "auchan",
        "lidl",
        "penny",
        "spar",
        "tesco",
    }
    assert rows["muller"].name == "Müller"
    assert log.warnings == []


def test_unknown_chain_is_non_grocery_with_a_warning() -> None:
    log = RunLog()
    (row,) = chain_rows([ChainStore(uuid="u1", name="CBA Príma")], log)
    assert (row.slug, row.is_grocery) == ("cba-prima", False)
    assert codes(log) == ["unknown_chain"]


def test_colliding_chain_slugs_fail() -> None:
    with pytest.raises(IngestError, match="slug 'spar'"):
        chain_rows(
            [ChainStore(uuid="a", name="Spar"), ChainStore(uuid="b", name="SPAR Magyarország")], RunLog()
        )
    with pytest.raises(IngestError, match="twice"):
        chain_rows([ChainStore(uuid="a", name="Spar"), ChainStore(uuid="a", name="Lidl")], RunLog())
    with pytest.raises(IngestError, match="no chains"):
        chain_rows([], RunLog())


# ───────────────────────────── stores ─────────────────────────────


@pytest.mark.parametrize(
    ("store_id", "slug", "fmt"),
    [
        ("tesco-1009", "tesco", "hyper"),
        ("tesco-1890", "tesco", "hyper"),
        ("tesco-4062", "tesco", "express"),
        ("tesco-4005", "tesco", "express"),
        ("tesco-5016", "tesco", "other"),
        ("tesco-3002", "tesco", "other"),
        ("tesco-10000", "tesco", "other"),
        ("tesco-401", "tesco", "other"),
        ("tesco-x1000", "tesco", "other"),
        ("spar-110", "spar", None),
        ("aldi-J179", "aldi", None),
        ("tesco-1009", "spar", None),  # the chain decides, not the prefix
    ],
)
def test_store_format_from_id(store_id: str, slug: str, fmt: str | None) -> None:
    assert store_format(store_id, slug) == fmt


def _chains() -> dict[str, ChainRow]:
    return {c.uuid: ChainRow(c.uuid, c.name, chain_slug(c.name), True) for c in WORLD.chains.values()}


def _shop(**changes: Any) -> dict[str, Any]:
    base = {
        "uuid": "zz-1",
        "postalCode": "1011",
        "city": "Budapest",
        "address": "Fő utca 1.",
        "chainStoreUuid": WORLD.chains["Spar"].uuid,
        "location": {"latitude": 47.5, "longitude": 19.05},
        "openingTime": None,
    }
    return {**base, **changes}


def test_real_store_list_converts_completely() -> None:
    shops = parse_shops(json.dumps({"shops": shops_json(WORLD)}).encode()).value
    log = RunLog()
    rows = store_rows(shops, _chains(), log)
    assert len(rows) == 1829
    assert log.warnings == []
    by_id = {row.id: row for row in rows}
    assert by_id["tesco-4062"].format == "express"
    assert by_id["tesco-1009"].format == "hyper"
    assert by_id["tesco-5016"].format == "other"
    assert by_id["spar-110"].format is None
    assert by_id["lidl-316"].opening_raw is not None
    assert by_id["lidl-316"].opening_raw.startswith("Nyitvatartás")
    assert sum(1 for row in rows if row.postal_code and row.postal_code.startswith("1")) == 419


def test_only_the_known_coordinate_error_is_an_outlier() -> None:
    shops = parse_shops(json.dumps({"shops": shops_json(WORLD)}).encode()).value
    rows = store_rows(shops, _chains(), RunLog())
    outliers = coordinate_outliers(rows)
    assert [store_id for store_id, _ in outliers] == ["rossmann-364"]  # Zalaegerszeg, Platán sor 8
    assert outliers[0][1] > 100


def test_invalid_stores_are_skipped_or_nulled_never_crash() -> None:
    shops = parse_shops(
        json.dumps(
            {
                "shops": [
                    _shop(uuid="zz-ok"),
                    _shop(uuid="bad id!"),
                    _shop(uuid="x" * 41),
                    _shop(uuid="zz-ok"),  # duplicate
                    _shop(uuid="zz-chain", chainStoreUuid="unknown"),
                    _shop(uuid="zz-noloc", location=None),
                    _shop(uuid="zz-swapped", location={"latitude": 19.05, "longitude": 47.5}),
                    _shop(uuid="zz-north", location={"latitude": 49.01, "longitude": 19.0}),
                    _shop(uuid="zz-edge", location={"latitude": 49.0, "longitude": 23.5}),
                    _shop(uuid="zz-pc", postalCode="H-1011"),
                    _shop(uuid="zz-city", city="x" * 101, address="   ", openingTime="y" * 501),
                ]
            }
        ).encode()
    ).value
    log = RunLog()
    rows = {row.id: row for row in store_rows(shops, _chains(), log)}
    assert sorted(rows) == ["zz-city", "zz-edge", "zz-ok", "zz-pc"]
    assert rows["zz-pc"].postal_code is None
    assert (rows["zz-city"].city, rows["zz-city"].address, rows["zz-city"].opening_raw) == (None, None, None)
    skipped = {w["reason"]: w["stores"] for w in log.warnings if w["code"] == "store_skipped"}
    assert skipped == {
        "coordinates outside the allowed range": ["zz-north", "zz-swapped"],
        "duplicate id": ["zz-ok"],
        "invalid id": ["'bad id!'", repr("x" * 40)],
        "no coordinates": ["zz-noloc"],
        "unknown chain": ["zz-chain"],
    }
    nulled = {w["field"]: w["stores"] for w in log.warnings if w["code"] == "store_field_nulled"}
    assert nulled == {"city": ["zz-city"], "opening_raw": ["zz-city"], "postal_code": ["zz-pc"]}


# ───────────────────────────── categories ─────────────────────────────


def test_category_tree_flattens_with_food_flags() -> None:
    nodes = parse_categories(
        json.dumps({"categories": category_tree(list(WORLD.leaves.values()))}).encode()
    ).value
    log = RunLog()
    rows = category_rows(nodes, log)
    assert log.warnings == []
    assert [sum(1 for r in rows if r.level == level) for level in (1, 2, 3)] == [9, 42, 161]
    leaves = [r for r in rows if r.is_leaf]
    assert len(leaves) == 161
    assert sum(1 for r in leaves if r.is_food) == 120
    by_id = {r.id: r for r in rows}
    assert by_id[18].parent_id == 2017
    assert by_id[2017].parent_id == 1015
    assert by_id[1015].parent_id is None
    assert by_id[18].is_food
    assert not by_id[1123].is_food  # Baba
    assert [r.level for r in rows] == sorted(r.level for r in rows)  # parents before children


def test_missing_food_top_is_reported_and_none_fails() -> None:
    tree = category_tree(list(WORLD.leaves.values()))
    renamed = [dict(node, name="Pékáru és más") if node["id"] == 1046 else node for node in tree]
    log = RunLog()
    rows = category_rows(parse_categories(json.dumps({"categories": renamed}).encode()).value, log)
    assert codes(log) == ["food_category_missing"]
    assert not {r.id: r for r in rows}[46].is_food
    non_food = [node for node in tree if node["id"] not in {1001, 1015, 1028, 1046, 1050, 1068}]
    with pytest.raises(IngestError, match="food top"):
        category_rows(parse_categories(json.dumps({"categories": non_food}).encode()).value, RunLog())


def test_duplicate_category_ids_fail() -> None:
    tree = category_tree(list(WORLD.leaves.values()))
    tree[0]["categoryNodes"][0]["categoryNodes"].append({"id": 18, "name": "dup", "path": "x"})
    with pytest.raises(IngestError, match="18 appears twice"):
        category_rows(parse_categories(json.dumps({"categories": tree}).encode()).value, RunLog())


# ───────────────────────────── listing + XLSX -> product_chain_day ─────────────────────────────


@pytest.fixture(scope="module")
def snapshot_inputs() -> tuple[dict[int, Any], Any, ChainResolver, frozenset[int]]:
    clock = FakeClock()
    fake = FakeGvh(WORLD, data_date=DAY)
    food = frozenset(leaf.id for leaf in WORLD.leaves.values() if leaf.is_food)
    with GvhClient(
        fake_settings(), transport=fake.transport(), clock=clock.monotonic, sleep=clock.sleep
    ) as client:
        listings = {leaf: client.products_by_category(leaf) for leaf in sorted(food)}
        xlsx = client.daily_xlsx(DAY)
    chains = ChainResolver(ChainRef(c.uuid, chain_slug(c.name)) for c in WORLD.chains.values())
    return listings, xlsx, chains, food


@pytest.fixture(scope="module")
def snap_and_log(snapshot_inputs: tuple[Any, ...]) -> tuple[Any, RunLog]:
    listings, xlsx, chains, food = snapshot_inputs
    log = RunLog()
    return build_snapshot(listings, xlsx, chains=chains, food_leaves=food, log=log), log


def _row(snap: Any, key: str, chain: str) -> Any:
    return snap.rows[(WORLD.special[key], WORLD.chains[chain].uuid)]


def test_product_min_amount_is_kept_apart_from_the_prices_minima(snap_and_log: tuple[Any, RunLog]) -> None:
    snap, _ = snap_and_log
    row = _row(snap, "spar_outlier", "Spar")
    assert row.product_min_amount == Decimal(699)  # what GVH displays: >= 80 % of stores
    assert row.normal_amount == Decimal(294)  # prices[] = the cheapest single store (2 of ~370)
    assert row.normal_unit == Decimal(588)
    assert (row.xlsx_min, row.xlsx_max) == (Decimal(294), Decimal(699))
    assert row.varies_by_store
    split = _row(snap, "lidl_split", "Lidl")
    assert split.product_min_amount == Decimal(379)  # no price reaches 80 %: GVH falls back to the minimum


def test_promotion_and_loyalty_columns(snap_and_log: tuple[Any, RunLog]) -> None:
    snap, _ = snap_and_log
    promo = _row(snap, "penny_promo_all", "Penny")
    assert (promo.product_min_amount, promo.normal_amount, promo.discounted_amount) == (219, 379, 219)
    assert not promo.varies_by_store  # same daily price everywhere: no per-store call needed
    loyalty = _row(snap, "penny_loyalty", "Penny")
    assert (loyalty.loyalty_amount, loyalty.loyalty_unit) == (Decimal(799), Decimal("79.9"))
    assert loyalty.xlsx_min == Decimal(899)  # the XLSX excludes LOYALTY
    some = _row(snap, "spar_promo_some", "Spar")
    assert (some.product_min_amount, some.discounted_amount, some.price_same_everywhere) == (853, 399, True)


def test_three_chain_listing_cap_is_completed_from_the_xlsx(snap_and_log: tuple[Any, RunLog]) -> None:
    snap, _ = snap_and_log
    product = WORLD.special["multichain"]
    rows = {chain_id: row for (pid, chain_id), row in snap.rows.items() if pid == product}
    by_name = {WORLD.chain_by_uuid(chain_id).name: row for chain_id, row in rows.items()}
    assert sorted(by_name) == ["Aldi", "Auchan", "Penny", "Spar", "Tesco"]
    listed = {name for name, row in by_name.items() if row.has_listing}
    assert listed == {"Aldi", "Penny", "Tesco"}  # the listing shows the 3 chains with most stores
    for hidden in ("Auchan", "Spar"):
        row = by_name[hidden]
        assert row.has_xlsx
        assert row.product_min_amount is None
        assert row.normal_amount is None
    assert by_name["Spar"].xlsx_min == Decimal(129)  # cheaper than every listed chain
    assert by_name["Spar"].stores_carrying == 40
    assert by_name["Auchan"].stores_carrying == 4
    assert by_name["Auchan"].chain_store_count == 26


def test_every_xlsx_food_pair_has_a_row(snap_and_log: tuple[Any, RunLog]) -> None:
    snap, _ = snap_and_log
    expected = {
        (p.id, WORLD.chains[o.chain].uuid)
        for p in WORLD.products.values()
        if WORLD.leaves[p.leaf_id].is_food and p.unit != "csomag"
        for o in p.offers
    }
    assert set(snap.rows) == expected
    assert all(row.has_xlsx for row in snap.rows.values())
    assert snap.stats["xlsx_rows_not_food"] == sum(
        len(p.offers) for p in WORLD.products.values() if not WORLD.leaves[p.leaf_id].is_food
    )


def test_unknown_units_are_skipped_with_a_warning_naming_them(snap_and_log: tuple[Any, RunLog]) -> None:
    snap, log = snap_and_log
    assert WORLD.special["unknown_unit"] not in snap.products
    (warning,) = [w for w in log.warnings if w["code"] == "unknown_unit"]
    assert "csomag" in warning["message"]
    assert warning["units"] == {"csomag": [WORLD.special["unknown_unit"]]}
    assert warning["counts"] == {"csomag": 1}


def test_units_and_loose_items(snap_and_log: tuple[Any, RunLog]) -> None:
    snap, _ = snap_and_log
    carrot = snap.products[WORLD.special["carrot_db_kg"]]
    assert (carrot.unit, carrot.unit_title) == ("db", "kg")
    counter = snap.products[WORLD.special["tesco_zone"]]
    assert (counter.name, counter.unit_title, counter.packaging) == (
        "31. FRISS CSIRKEMELL FILE PULTOS QQ",
        "kg",
        1,
    )
    leaf_40_units = {p.unit for p in snap.products.values() if p.category_id == 40}
    assert leaf_40_units == {"kg", "db"}  # a mixed leaf (trap 5)
    assert {p.unit for p in snap.products.values()} == {"kg", "l", "db"}


def test_snapshot_without_warnings_except_the_unknown_unit(snap_and_log: tuple[Any, RunLog]) -> None:
    _, log = snap_and_log
    assert codes(log) == ["unknown_unit"]


def test_listing_failure_falls_back_to_xlsx_products(snapshot_inputs: tuple[Any, ...]) -> None:
    listings, xlsx, chains, food = snapshot_inputs
    partial = {leaf: listing for leaf, listing in listings.items() if leaf != 50}
    snap = build_snapshot(partial, xlsx, chains=chains, food_leaves=food, log=RunLog())
    product = snap.products[WORLD.special["spar_outlier"]]
    assert (product.from_listing, product.unit_title, product.packaging) == (False, None, Decimal("0.5"))
    row = _row(snap, "spar_outlier", "Spar")
    assert (row.has_listing, row.product_min_amount, row.xlsx_min) == (False, None, Decimal(294))


def test_inconsistent_unit_prices_and_out_of_range_values_are_reported(
    snapshot_inputs: tuple[Any, ...],
) -> None:
    _, _, chains, food = snapshot_inputs
    body = json.loads(FakeGvh(WORLD, data_date=DAY).respond("/api/products-by-category/50?limit=48").body)  # type: ignore[union-attr]
    item = body["products"][0]
    entry = item["pricesOfChainStores"][0]
    entry["prices"][0]["unitAmount"] = (
        entry["prices"][0]["amount"] / float(item["packaging"]) * 2
    )  # 100 % off
    entry["productMinAmount"] = -5
    page = parse_product_page(json.dumps({"products": [item], "count": 1}).encode()).value
    listing = CategoryListing(50, 1, tuple(page.products), 1, 0, False)
    log = RunLog()
    snap = build_snapshot({50: listing}, None, chains=chains, food_leaves=food, log=log)
    row = snap.rows[(item["id"], entry["id"])]
    assert row.product_min_amount is None
    assert set(codes(log)) == {"unit_price_inconsistent", "value_out_of_range"}


def test_unknown_chain_in_the_listing_is_matched_by_name_or_skipped(snapshot_inputs: tuple[Any, ...]) -> None:
    _, _, chains, food = snapshot_inputs
    body = json.loads(FakeGvh(WORLD, data_date=DAY).respond("/api/products-by-category/50?limit=48").body)  # type: ignore[union-attr]
    first, second = body["products"][:2]
    first["pricesOfChainStores"][0]["id"] = "new-uuid"  # name still known -> matched by name
    second["pricesOfChainStores"] = [dict(second["pricesOfChainStores"][0], id="new-2", name="Ismeretlen")]
    page = parse_product_page(json.dumps({"products": [first, second], "count": 2}).encode()).value
    log = RunLog()
    snap = build_snapshot(
        {50: CategoryListing(50, 2, tuple(page.products), 1, 0, False)},
        None,
        chains=chains,
        food_leaves=food,
        log=log,
    )
    name = first["pricesOfChainStores"][0]["name"]
    assert (first["id"], WORLD.chains[name].uuid) in snap.rows
    assert not [k for k in snap.rows if k[0] == second["id"]]
    assert set(codes(log)) == {"chain_matched_by_name", "unknown_chain"}


# ───────────────────────────── per-store targets ─────────────────────────────


def test_per_store_targets_only_varying_pairs_in_ingredient_leaves(snap_and_log: tuple[Any, RunLog]) -> None:
    snap, _ = snap_and_log
    budapest = {c.uuid: WORLD.budapest_stores(c.name) for c in WORLD.chains.values()}
    targets = per_store_targets(snap, frozenset({7, 50}), budapest)
    expected: dict[str, set[str]] = {}
    for product in WORLD.products.values():
        if product.leaf_id not in {7, 50}:
            continue
        for offer in product.offers:
            summary = summarise(offer)
            if summary is not None and summary.daily_min < summary.daily_max:
                expected.setdefault(product.id, set()).update(WORLD.budapest_stores(offer.chain))
    assert {pid: set(ids) for pid, ids in targets.items()} == expected
    assert WORLD.special["spar_outlier"] in targets
    multi = set(targets[WORLD.special["multichain"]])
    assert multi == set(WORLD.budapest_stores("Tesco"))  # only Tesco varies for this product
    assert all(list(ids) == sorted(ids) for ids in targets.values())
    assert list(targets) == sorted(targets)
    assert per_store_targets(snap, frozenset(), budapest) == {}


def test_store_price_rows_take_minima_and_ignore_unrequested_stores() -> None:
    parsed = parse_shop_prices(
        json.dumps(
            {
                "shops": [
                    {
                        "shopUuid": "spar-1",
                        "prices": [
                            {"type": "NORMAL", "amount": 699, "unitAmount": 1398},
                            {"type": "NORMAL", "amount": 650, "unitAmount": 1300},
                            {"type": "LOYALTY", "amount": 600, "unitAmount": 1200},
                        ],
                    },
                    {"shopUuid": "spar-2", "prices": []},
                    {"shopUuid": "spar-9", "prices": [{"type": "NORMAL", "amount": 1, "unitAmount": 2}]},
                ]
            }
        ).encode()
    )
    assert parsed is not None
    prices = {shop.shopUuid: tuple(shop.prices) for shop in parsed.value.shops}
    issues = Issues()
    rows = store_price_rows("p1", prices, frozenset({"spar-1", "spar-2"}), issues)
    assert len(rows) == 1  # spar-2 has no price; spar-9 was not requested
    (row,) = rows
    assert (row.normal_amount, row.normal_unit, row.loyalty_amount, row.discounted_amount) == (
        650,
        1300,
        600,
        None,
    )
    assert dict(issues.samples) == {"unexpected_shop": {"p1 spar-9"}}


def test_chain_resolver_accepts_a_one_shot_iterator() -> None:
    """Regression: the resolver iterates its input twice; a generator must not leave the slug map empty."""
    resolver = ChainResolver(ChainRef(c.uuid, chain_slug(c.name)) for c in WORLD.chains.values())
    assert resolver.by_name("SPAR") == WORLD.chains["Spar"].uuid
    assert resolver.by_name("Müller") == WORLD.chains["Müller"].uuid
    issues = Issues()
    assert resolver.by_uuid(WORLD.chains["Lidl"].uuid, "whatever", issues) == WORLD.chains["Lidl"].uuid
    assert resolver.by_name("Ismeretlen lánc") is None
    assert resolver.by_name("--") is None


def test_xlsx_row_of_a_listed_product_attaches_even_in_another_category(
    snapshot_inputs: tuple[Any, ...],
) -> None:
    listings, xlsx, chains, food = snapshot_inputs
    from dataclasses import replace

    product_id = WORLD.special["spar_outlier"]
    moved = tuple(replace(r, category_id=1157) if r.product_id == product_id else r for r in xlsx.rows)
    log = RunLog()
    snap = build_snapshot(listings, replace(xlsx, rows=moved), chains=chains, food_leaves=food, log=log)
    row = _row(snap, "spar_outlier", "Spar")
    assert (row.has_listing, row.has_xlsx, row.xlsx_min) == (True, True, Decimal(294))
    assert snap.products[product_id].category_id == 50  # the listing's leaf wins
    (mismatch,) = [w for w in log.warnings if w["code"] == "xlsx_listing_mismatch"]
    assert mismatch["items"] == [product_id]


# ───────────────────────────── date agreement (trap 10) ─────────────────────────────


def _fetch_inputs(fake: FakeGvh, leaves: frozenset[int]) -> tuple[dict[int, CategoryListing], Any]:
    clock = FakeClock()
    with GvhClient(
        fake_settings(), transport=fake.transport(), clock=clock.monotonic, sleep=clock.sleep
    ) as client:
        return {leaf: client.products_by_category(leaf) for leaf in sorted(leaves)}, client.daily_xlsx(DAY)


def _uuid_pairs(pairs: Any) -> set[tuple[str, str]]:
    return {(product_id, WORLD.chains[chain].uuid) for product_id, chain in pairs}


def test_same_day_listing_and_xlsx_agree_on_every_pair(snap_and_log: tuple[Any, RunLog]) -> None:
    snap, _ = snap_and_log
    agreement = date_agreement(snap)
    assert agreement.pairs == len(compared_pairs(WORLD)) == 632
    assert agreement.disagreeing == ()
    assert (agreement.agreement_share, agreement.mismatch_share) == (1.0, 0.0)
    log = RunLog()
    check_date_agreement(snap, log, chains=ChainResolver([]))
    assert log.warnings == []
    assert not log.degraded
    assert log.stats == {
        "api_xlsx_agreement": 1.0,
        "api_xlsx_pairs_compared": 632,
        "api_xlsx_pairs_disagreeing": 0,
    }


def test_the_comparable_listing_price_is_min_normal_discounted(snap_and_log: tuple[Any, RunLog]) -> None:
    """The XLSX minimum is the cheapest store's daily price (DISCOUNTED in, LOYALTY out). The listing's
    counterpart is min(NORMAL, DISCOUNTED) of prices[], never productMinAmount and never LOYALTY."""
    snap, _ = snap_and_log
    outlier = _row(snap, "spar_outlier", "Spar")  # productMinAmount 699 (80 % price), one store at 294
    assert (outlier.product_min_amount, listing_daily_min(outlier), outlier.xlsx_min) == (699, 294, 294)
    promo = _row(snap, "penny_promo_all", "Penny")  # NORMAL 379, DISCOUNTED 219
    assert (listing_daily_min(promo), promo.xlsx_min) == (219, 219)
    loyalty = _row(snap, "penny_loyalty", "Penny")  # NORMAL 899, LOYALTY 799
    assert (listing_daily_min(loyalty), loyalty.loyalty_amount, loyalty.xlsx_min) == (899, 799, 899)
    assert listing_daily_min(ChainDayRow("p", "c", has_listing=True, loyalty_amount=Decimal(5))) is None


def test_a_listing_still_on_the_previous_day_is_flagged() -> None:
    fake = FakeGvh(WORLD, data_date=DAY)
    fake.listing_lag = 0.02
    lagged = _uuid_pairs((pid, chain) for pid, chains in fake.lagged().items() for chain in chains)
    assert len(lagged) == 13  # round(2 % of 632)
    food = frozenset(leaf.id for leaf in WORLD.leaves.values() if leaf.is_food)
    listings, xlsx = _fetch_inputs(fake, food)
    chains = ChainResolver(ChainRef(c.uuid, chain_slug(c.name)) for c in WORLD.chains.values())
    snap = build_snapshot(listings, xlsx, chains=chains, food_leaves=food, log=RunLog())
    log = RunLog()
    agreement = check_date_agreement(snap, log, chains=chains)
    assert agreement.pairs == 632
    assert {(p.product_id, p.chain_id) for p in agreement.disagreeing} == lagged
    assert all(p.listing_min > p.xlsx_min for p in agreement.disagreeing)  # yesterday's price, 8 % higher
    assert log.degraded
    (warning,) = log.warnings
    assert warning["code"] == "api_xlsx_date_mismatch"
    assert "13 of 632" in warning["message"]
    assert (warning["share"], warning["threshold"], warning["pairs"], warning["disagreeing"]) == (
        round(13 / 632, 6),
        0.006,
        632,
        13,
    )
    first = agreement.disagreeing[0]
    assert len(warning["examples"]) == 10
    assert warning["examples"][0] == {
        "product": first.product_id,
        "chain": chain_slug(WORLD.chain_by_uuid(first.chain_id).name),
        "xlsx_min": str(first.xlsx_min),
        "listing_min": str(first.listing_min),
    }
    assert log.stats["api_xlsx_agreement"] == round(619 / 632, 6)
    assert log.stats["api_xlsx_pairs_disagreeing"] == 13


def _pairs_snapshot(agreeing: int, disagreeing: int) -> Snapshot:
    snap = Snapshot()
    for index in range(agreeing + disagreeing):
        listing = Decimal(100) if index < agreeing else Decimal(110)
        snap.rows[(f"p{index:04d}", "c")] = ChainDayRow(
            f"p{index:04d}",
            "c",
            has_listing=True,
            normal_amount=listing,
            has_xlsx=True,
            xlsx_min=Decimal(100),
        )
    return snap


@pytest.mark.parametrize(("disagreeing", "flagged"), [(0, False), (6, False), (7, True), (40, True)])
def test_the_mismatch_threshold_is_more_than_0_6_percent(disagreeing: int, flagged: bool) -> None:
    assert Decimal("0.006") == API_XLSX_MISMATCH_MAX_SHARE
    log = RunLog()
    agreement = check_date_agreement(
        _pairs_snapshot(1000 - disagreeing, disagreeing), log, chains=ChainResolver([])
    )
    assert agreement.pairs == 1000
    assert len(agreement.disagreeing) == disagreeing
    assert log.stats["api_xlsx_agreement"] == (1000 - disagreeing) / 1000  # recorded either way
    assert log.degraded is flagged
    if flagged:
        (warning,) = log.warnings
        assert warning["code"] == "api_xlsx_date_mismatch"
        assert len(warning["examples"]) == min(disagreeing, 10)
    else:
        assert log.warnings == []


def test_the_threshold_is_configurable() -> None:
    log = RunLog()
    check_date_agreement(_pairs_snapshot(990, 10), log, chains=ChainResolver([]), max_share=Decimal("0.02"))
    assert log.warnings == []


def test_only_pairs_priced_in_both_sources_are_compared() -> None:
    def row(pid: str, **values: Any) -> ChainDayRow:
        return ChainDayRow(pid, "c", **values)

    snap = Snapshot()
    for item in (
        row(
            "tie-low", has_listing=True, normal_amount=Decimal("100.5"), has_xlsx=True, xlsx_min=Decimal(100)
        ),
        row("over", has_listing=True, normal_amount=Decimal("100.51"), has_xlsx=True, xlsx_min=Decimal(100)),
        row(
            "disc",
            has_listing=True,
            normal_amount=Decimal(150),
            discounted_amount=Decimal(100),
            has_xlsx=True,
            xlsx_min=Decimal(100),
        ),
        row("xlsx-only", has_xlsx=True, xlsx_min=Decimal(1)),
        row("listing-only", has_listing=True, normal_amount=Decimal(1)),
        row(
            "loyalty-only", has_listing=True, loyalty_amount=Decimal(1), has_xlsx=True, xlsx_min=Decimal(100)
        ),
        row("no-xlsx-min", has_listing=True, normal_amount=Decimal(1), has_xlsx=True),
    ):
        snap.rows[(item.product_id, item.chain_id)] = item
    agreement = date_agreement(snap)
    assert agreement.pairs == 3
    assert [p.product_id for p in agreement.disagreeing] == ["over"]


def test_nothing_to_compare_leaves_the_day_unchecked() -> None:
    log = RunLog()
    agreement = check_date_agreement(Snapshot(), log, chains=ChainResolver([]))
    assert (agreement.pairs, agreement.agreement_share, agreement.mismatch_share) == (0, None, None)
    assert codes(log) == ["api_xlsx_date_unchecked"]
    assert log.degraded
    assert log.stats["api_xlsx_agreement"] is None


# ───────────────────────────── loyalty sources (trap 4) ─────────────────────────────


def test_loyalty_columns_mirror_the_listing_loyalty_entries_only(snap_and_log: tuple[Any, RunLog]) -> None:
    """Every loyalty value is the minimum LOYALTY entry of that chain in the listing JSON; pairs the listing
    does not show (XLSX only) and entries without LOYALTY have none, whatever the XLSX or productMinAmount."""
    snap, _ = snap_and_log
    fake = FakeGvh(WORLD, data_date=DAY)
    expected: dict[tuple[str, str], Decimal] = {}
    for leaf in sorted({p.category_id for p in snap.products.values()}):
        offset, count = 0, 1
        while offset < count:  # every page (leaf 18 has 101 products)
            target = f"/api/products-by-category/{leaf}?limit=48&offset={offset}"
            page = json.loads(fake.respond(target).body)  # type: ignore[union-attr]
            count, offset = page["count"], offset + 48
            for product in page["products"]:
                for chain in product["pricesOfChainStores"]:
                    loyalty = [p["amount"] for p in chain["prices"] if p["type"] == "LOYALTY"]
                    if loyalty:
                        expected[(product["id"], chain["id"])] = Decimal(min(loyalty))
    actual = {key: row.loyalty_amount for key, row in snap.rows.items() if row.loyalty_amount is not None}
    assert actual == expected
    assert expected  # the fake has loyalty prices (Penny, Auchan)
    assert all(row.loyalty_amount is None for row in snap.rows.values() if not row.has_listing)
    assert all(
        row.loyalty_amount < row.xlsx_min  # the XLSX daily minimum never includes the card price
        for row in snap.rows.values()
        if row.loyalty_amount is not None and row.xlsx_min is not None
    )


def test_loyalty_is_never_taken_from_the_xlsx_or_product_min_amount(snapshot_inputs: tuple[Any, ...]) -> None:
    """A chain whose listing has no LOYALTY entry keeps loyalty NULL even when the XLSX minimum and
    productMinAmount are both below its NORMAL price."""
    listings, xlsx, chains, food = snapshot_inputs
    from dataclasses import replace

    product_id = WORLD.special["penny_loyalty"]
    leaf = WORLD.products[product_id].leaf_id
    body = json.loads(
        FakeGvh(WORLD, data_date=DAY).respond(f"/api/products-by-category/{leaf}?limit=48").body
    )  # type: ignore[union-attr]
    for product in body["products"]:
        if product["id"] == product_id:
            (entry,) = product["pricesOfChainStores"]
            entry["prices"] = [p for p in entry["prices"] if p["type"] != "LOYALTY"]
            entry["productMinAmount"] = 700
    page = parse_product_page(json.dumps(body).encode()).value
    patched = {**listings, leaf: CategoryListing(leaf, page.count, tuple(page.products), 1, 0, False)}
    rows = tuple(replace(r, min_price=Decimal(650)) if r.product_id == product_id else r for r in xlsx.rows)
    snap = build_snapshot(patched, replace(xlsx, rows=rows), chains=chains, food_leaves=food, log=RunLog())
    row = _row(snap, "penny_loyalty", "Penny")
    assert (row.normal_amount, row.product_min_amount, row.xlsx_min) == (899, 700, 650)
    assert (row.loyalty_amount, row.loyalty_unit) == (None, None)
