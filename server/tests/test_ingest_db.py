"""DB integration of the ingest, as ``bpf_ingest``, against the fake GVH (docs/ENGINE.md ``bpf.ingest``).

These tests COMMIT price history, including rows for a past day that the append-only trigger then protects
forever, so they run in a private throwaway cluster (``pg_factory``), never in the shared ``pg`` cluster.
Each test starts from empty tables (TRUNCATE, which the row-level history trigger does not intercept).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

from bpf.config import Settings
from bpf.gvh import GvhClient
from bpf.ingest import IngestBusyError, budapest_today, run_availability, run_daily, run_reference
from bpf.ingest.__main__ import main as cli_main
from bpf.ingest.common import BUDAPEST, IngestOutcome
from tests.fakegvh import (
    CONTACT,
    NO_DATA_STORES,
    FakeClock,
    FakeGvh,
    FakeWorld,
    build_world,
    fake_settings,
    summarise,
)
from tests.pgcluster import PgCluster

pytestmark = pytest.mark.db

SERVER_DIR = Path(__file__).resolve().parents[1]
WORLD = build_world()
TODAY = budapest_today()
PAST = date(2026, 1, 5)  # long before "yesterday": the append-only trigger protects it
INGREDIENT_LEAVES = [7, 18, 50]


def at_half_past_midnight(day: date) -> datetime:
    """00:30 in Budapest on ``day``: still the previous day in UTC, so a UTC-based date would be wrong."""
    return datetime(day.year, day.month, day.day, 0, 30, tzinfo=BUDAPEST)


@pytest.fixture(scope="module")
def cluster(pg_factory: Callable[..., PgCluster]) -> PgCluster:
    return pg_factory()


@pytest.fixture
def admin(cluster: PgCluster) -> Iterator[psycopg.Connection]:
    with cluster.connect("admin", autocommit=True) as conn:
        yield conn


@pytest.fixture(autouse=True)
def empty_tables(cluster: PgCluster) -> None:
    with cluster.connect("admin", autocommit=True) as conn:
        conn.execute(
            "TRUNCATE core.product_chain_day, core.store_price_day, core.product_availability, core.product, "
            "core.store, core.category, core.chain, ops.ingest_run, app.recipe_line, app.recipe, "
            "app.ingredient RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def conn(cluster: PgCluster) -> Iterator[psycopg.Connection]:
    with cluster.connect("ingest", autocommit=True) as connection:
        yield connection


def set_ontology(admin: psycopg.Connection, leaves: list[int]) -> None:
    admin.execute(
        "INSERT INTO app.ingredient (id, name_hu, list_group, unit, leaf_ids) "
        "VALUES ('zz_test_ingredient', 'teszt', 'egyeb', 'kg', %s)",
        (leaves,),
    )


def client_for(transport: httpx.BaseTransport, **kwargs: Any) -> GvhClient:
    clock = FakeClock()
    return GvhClient(fake_settings(), transport=transport, clock=clock.monotonic, sleep=clock.sleep, **kwargs)


def daily(
    conn: psycopg.Connection,
    fake: FakeGvh,
    *,
    transport: httpx.BaseTransport | None = None,
    day: date | None = None,
    max_requests: int | None = None,
    **kwargs: Any,
) -> IngestOutcome:
    instant = at_half_past_midnight(day or fake.data_date)
    with client_for(transport or fake.transport(), max_requests=max_requests) as client:
        return run_daily(conn, client, clock=lambda: instant, **kwargs)


def patched(fake: FakeGvh, path_prefix: str, mutate: Callable[[Any], Any]) -> httpx.MockTransport:
    """The fake, with the JSON body of responses under ``path_prefix`` rewritten by ``mutate``."""

    def handler(request: httpx.Request) -> httpx.Response:
        response = fake.handler(request)
        if request.url.path.startswith(path_prefix) and response.status_code == 200:
            body = json.dumps(mutate(json.loads(response.content))).encode()
            return httpx.Response(200, content=body, headers={"content-type": "application/json"})
        return response

    return httpx.MockTransport(handler)


def one(conn: psycopg.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def run_row(admin: psycopg.Connection, run_id: int | None) -> dict[str, Any]:
    cur = admin.execute("SELECT * FROM ops.ingest_run WHERE id = %s", (run_id,))
    row = cur.fetchone()
    assert row is not None
    assert cur.description is not None
    return dict(zip([c.name for c in cur.description], row, strict=True))


def table(admin: psycopg.Connection, name: str) -> list[tuple[Any, ...]]:
    return admin.execute(f"SELECT * FROM core.{name} ORDER BY 1, 2, 3").fetchall()  # noqa: S608 - test constant


def codes(outcome: IngestOutcome) -> list[str]:
    return [w["code"] for w in outcome.warnings]


def varying_targets(
    world: FakeWorld, leaves: list[int], *, budapest_only: bool = True
) -> dict[str, set[str]]:
    """What the ingest should request: varying pairs, ingredient leaves, the chain's (Budapest) stores."""
    targets: dict[str, set[str]] = {}
    for product in world.products.values():
        if product.leaf_id not in leaves:
            continue
        for offer in product.offers:
            summary = summarise(offer)
            if summary is not None and summary.daily_min < summary.daily_max:
                stores = (
                    world.budapest_stores(offer.chain) if budapest_only else world.chains[offer.chain].stores
                )
                targets.setdefault(product.id, set()).update(stores)
    return targets


def shop_calls(fake: FakeGvh) -> dict[str, list[list[str]]]:
    calls: dict[str, list[list[str]]] = {}
    for request in fake.requests:
        parts = request.path.split("/")
        if len(parts) == 6 and parts[4] == "shop":
            calls.setdefault(parts[3], []).append(parts[5].split(","))
    return calls


# ───────────────────────────── reference ─────────────────────────────


def test_reference_run_upserts_chains_categories_and_stores(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    fake = FakeGvh(WORLD, data_date=TODAY)
    with client_for(fake.transport()) as client:
        outcome = run_reference(conn, client, clock=lambda: at_half_past_midnight(TODAY))
    assert outcome.status == "ok", outcome
    assert (outcome.requests, outcome.data_date) == (3, TODAY)
    assert dict(admin.execute("SELECT slug, is_grocery FROM core.chain").fetchall()) == {
        "aldi": True,
        "auchan": True,
        "lidl": True,
        "penny": True,
        "spar": True,
        "tesco": True,
        "dm": False,
        "rossmann": False,
        "muller": False,
    }
    assert one(admin, "SELECT name FROM core.chain WHERE slug = 'muller'") == "Müller"
    assert one(admin, "SELECT id FROM core.chain WHERE slug = 'spar'") == WORLD.chains["Spar"].uuid
    formats = dict(
        admin.execute(
            "SELECT id, format FROM core.store WHERE id = ANY(%s)",
            (["tesco-1009", "tesco-4062", "tesco-5016", "tesco-3002", "spar-110", "aldi-J179"],),
        ).fetchall()
    )
    assert formats == {
        "tesco-1009": "hyper",
        "tesco-4062": "express",
        "tesco-5016": "other",
        "tesco-3002": "other",
        "spar-110": None,
        "aldi-J179": None,
    }
    assert one(admin, "SELECT count(*) FROM core.store") == 1829
    assert one(admin, "SELECT count(*) FROM core.store WHERE is_budapest") == 419
    assert one(admin, "SELECT count(*) FROM core.store WHERE format IS NOT NULL") == 197
    assert one(admin, "SELECT count(*) FROM core.category") == 9 + 42 + 161
    assert one(admin, "SELECT count(*) FROM core.category WHERE is_leaf AND is_food") == 120
    run = run_row(admin, outcome.run_id)
    assert (run["kind"], run["status"], run["data_date"], run["requests"]) == ("reference", "ok", TODAY, 3)
    assert run["bytes"] == outcome.bytes > 100_000
    assert run["finished_at"] is not None
    assert run["error"] is None
    assert [w["code"] for w in run["warnings"]] == ["store_coordinate_outlier"]
    assert "rossmann-364" in run["warnings"][0]["stores"][0]
    assert run["stats"]["stores"] == 1829

    before = admin.execute("SELECT * FROM core.store ORDER BY id").fetchall()
    with client_for(fake.transport()) as client:
        again = run_reference(conn, client, data_date=TODAY)
    assert again.status == "ok"
    assert admin.execute("SELECT * FROM core.store ORDER BY id").fetchall() == before


def test_reference_skips_stores_that_would_violate_checks(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    def add_bad_stores(shops: list[dict[str, Any]]) -> list[dict[str, Any]]:
        template = shops[0]
        return [
            *shops,
            dict(template, uuid="bad id!"),
            dict(template, uuid="zz-swapped", location={"latitude": 19.05, "longitude": 47.5}),
            dict(template, uuid="zz-far", location={"latitude": 52.2, "longitude": 21.0}),
            dict(template, uuid="zz-noloc", location=None),
            dict(template, uuid="zz-badpc", postalCode="H-1011"),
        ]

    fake = FakeGvh(WORLD, data_date=TODAY)
    with client_for(patched(fake, "/api/shops", add_bad_stores)) as client:
        outcome = run_reference(conn, client, data_date=TODAY)
    assert outcome.status == "ok", outcome
    assert one(admin, "SELECT count(*) FROM core.store") == 1830
    assert one(admin, "SELECT postal_code IS NULL AND NOT is_budapest FROM core.store WHERE id = 'zz-badpc'")
    skipped = {w["reason"]: w["stores"] for w in outcome.warnings if w["code"] == "store_skipped"}
    assert skipped == {
        "coordinates outside the allowed range": ["zz-far", "zz-swapped"],
        "invalid id": ["'bad id!'"],
        "no coordinates": ["zz-noloc"],
    }
    assert "store_field_nulled" in codes(outcome)


# ───────────────────────────── daily ─────────────────────────────


def test_daily_run_lifecycle_and_chain_rows(
    conn: psycopg.Connection, admin: psycopg.Connection, cluster: PgCluster
) -> None:
    set_ontology(admin, INGREDIENT_LEAVES)
    fake = FakeGvh(WORLD, data_date=TODAY)
    seen_status: list[str] = []

    def observing(request: httpx.Request) -> httpx.Response:
        if not seen_status:
            with cluster.connect("admin", autocommit=True) as probe:
                seen_status.append(one(probe, "SELECT status FROM ops.ingest_run ORDER BY id DESC LIMIT 1"))
        return fake.handler(request)

    instant = at_half_past_midnight(TODAY)
    assert instant.astimezone(UTC).date() == TODAY - timedelta(days=1)
    outcome = daily(conn, fake, transport=httpx.MockTransport(observing))
    assert outcome.status == "ok", outcome
    assert seen_status == ["running"]
    assert outcome.data_date == TODAY  # Budapest date of the injected clock, not the UTC date
    assert set(codes(outcome)) == {"store_coordinate_outlier", "unknown_unit", "availability_stale"}

    run = run_row(admin, outcome.run_id)
    assert (run["kind"], run["status"], run["data_date"], run["error"]) == ("daily", "ok", TODAY, None)
    assert run["requests"] == outcome.requests == len(fake.requests)
    assert run["bytes"] == outcome.bytes > 0
    assert run["finished_at"] >= run["started_at"]
    assert [w["code"] for w in run["warnings"]] == codes(outcome)
    stats = run["stats"]
    assert stats["food_leaves"] == stats["leaves_fetched"] == 120
    assert stats["chains"] == 9
    assert stats["stores"] == 1829
    assert stats["store_price_rows"] > 0
    assert one(admin, "SELECT data_date FROM api.latest") == TODAY

    food_pairs = {
        (p.id, WORLD.chains[o.chain].uuid)
        for p in WORLD.products.values()
        if WORLD.leaves[p.leaf_id].is_food and p.unit != "csomag"
        for o in p.offers
    }
    stored = set(
        admin.execute(
            "SELECT product_id, chain_id FROM core.product_chain_day WHERE data_date = %s", (TODAY,)
        )
    )
    assert stored == food_pairs
    assert (
        one(admin, "SELECT count(*) FROM core.product WHERE id = %s", (WORLD.special["unknown_unit"],)) == 0
    )
    assert (
        one(
            admin,
            "SELECT count(*) FROM core.product WHERE category_id NOT IN "
            "(SELECT id FROM core.category WHERE is_food)",
        )
        == 0
    )  # non-food XLSX rows are not ingested

    spar = WORLD.chains["Spar"].uuid
    pma, normal, normal_unit, xmin, xmax = admin.execute(
        "SELECT product_min_amount, normal_amount, normal_unit, xlsx_min, xlsx_max "
        "FROM core.product_chain_day "
        "WHERE data_date = %s AND product_id = %s AND chain_id = %s",
        (TODAY, WORLD.special["spar_outlier"], spar),
    ).fetchone()
    assert (pma, normal, normal_unit, xmin, xmax) == (699, 294, 588, 294, 699)

    multi = {
        row[0]: row[1:]
        for row in admin.execute(
            "SELECT c.slug, d.product_min_amount, d.xlsx_min, d.stores_carrying, d.chain_store_count "
            "FROM core.product_chain_day d JOIN core.chain c ON c.id = d.chain_id "
            "WHERE d.data_date = %s AND d.product_id = %s",
            (TODAY, WORLD.special["multichain"]),
        )
    }
    assert sorted(multi) == ["aldi", "auchan", "penny", "spar", "tesco"]
    assert multi["spar"] == (None, Decimal(129), 40, 375)  # hidden by the 3-chain listing cap, from the XLSX
    assert multi["auchan"] == (None, Decimal(119), 4, 26)
    assert multi["aldi"][0] == Decimal(139)

    loose = admin.execute(
        "SELECT unit, unit_title, packaging FROM core.product WHERE id = %s", (WORLD.special["tesco_zone"],)
    ).fetchone()
    assert loose == ("kg", "kg", Decimal(1))


def test_daily_per_store_calls_only_for_varying_pairs_budapest_and_ontology_leaves(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    set_ontology(admin, INGREDIENT_LEAVES)
    fake = FakeGvh(WORLD, data_date=TODAY)
    outcome = daily(conn, fake)
    assert outcome.status == "ok", outcome
    calls = shop_calls(fake)
    expected = varying_targets(WORLD, INGREDIENT_LEAVES)
    assert {pid: {s for chunk in chunks for s in chunk} for pid, chunks in calls.items()} == expected
    assert all(len(chunks) == 1 for chunks in calls.values())  # <= 200 Budapest stores per product here
    budapest = {s.id for s in WORLD.stores.values() if s.budapest}
    assert {s for chunks in calls.values() for chunk in chunks for s in chunk} <= budapest
    assert WORLD.special["spar_outlier"] in calls
    assert WORLD.special["penny_promo_all"] not in calls  # same daily price everywhere

    spar_offer = WORLD.products[WORLD.special["spar_outlier"]].offers[0]
    prices = dict(
        admin.execute(
            "SELECT store_id, normal_amount FROM core.store_price_day "
            "WHERE data_date = %s AND product_id = %s",
            (TODAY, WORLD.special["spar_outlier"]),
        ).fetchall()
    )
    assert set(prices) == set(WORLD.budapest_stores("Spar")) - NO_DATA_STORES
    assert {s for s, amount in prices.items() if amount == 294} == spar_offer.special
    assert all(amount == 699 for s, amount in prices.items() if s not in spar_offer.special)

    with_rows = {row[0] for row in admin.execute("SELECT DISTINCT store_id FROM core.store_price_day")}
    marked = {row[0] for row in admin.execute("SELECT id FROM core.store WHERE has_data_date = %s", (TODAY,))}
    assert marked == with_rows
    assert one(admin, "SELECT count(*) FROM core.store WHERE has_data_date IS NOT NULL") == len(with_rows)
    assert not marked & NO_DATA_STORES
    assert outcome.stats["stores_marked_has_data"] == len(with_rows)


def test_daily_with_an_empty_ontology_makes_no_per_store_calls(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    fake = FakeGvh(WORLD, data_date=TODAY)
    outcome = daily(conn, fake)
    assert outcome.status == "ok", outcome
    assert shop_calls(fake) == {}
    assert "no_ingredient_leaves" in codes(outcome)
    assert one(admin, "SELECT count(*) FROM core.store_price_day") == 0
    assert one(admin, "SELECT count(*) FROM core.store WHERE has_data_date IS NOT NULL") == 0


def test_daily_all_stores_scope_chunks_by_200(conn: psycopg.Connection, admin: psycopg.Connection) -> None:
    set_ontology(admin, [50])
    fake = FakeGvh(WORLD, data_date=TODAY)
    outcome = daily(conn, fake, budapest_only=False)
    assert outcome.status == "ok", outcome
    calls = shop_calls(fake)
    expected = varying_targets(WORLD, [50], budapest_only=False)
    assert {pid: {s for chunk in chunks for s in chunk} for pid, chunks in calls.items()} == expected
    spar_chunks = calls[WORLD.special["spar_outlier"]]
    assert [len(chunk) for chunk in spar_chunks] == [200, len(WORLD.chains["Spar"].stores) - 200]


def test_daily_run_is_idempotent(conn: psycopg.Connection, admin: psycopg.Connection) -> None:
    set_ontology(admin, INGREDIENT_LEAVES)
    first = daily(conn, FakeGvh(WORLD, data_date=TODAY))
    snapshot = {
        name: table(admin, name) for name in ("product", "product_chain_day", "store_price_day", "store")
    }
    second = daily(conn, FakeGvh(WORLD, data_date=TODAY))
    assert (first.status, second.status) == ("ok", "ok")
    assert {name: table(admin, name) for name in snapshot} == snapshot
    assert admin.execute("SELECT status FROM ops.ingest_run ORDER BY id").fetchall() == [("ok",), ("ok",)]


def test_failed_leaf_makes_the_run_partial_and_never_erases_listing_values(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    good = daily(conn, FakeGvh(WORLD, data_date=TODAY))
    assert good.status == "ok"
    fake = FakeGvh(WORLD, data_date=TODAY)
    fake.fail("/api/products-by-category/50", 500, times=100)
    outcome = daily(conn, fake)
    assert outcome.status == "partial", outcome
    (warning,) = [w for w in outcome.warnings if w["code"] == "listing_failed"]
    assert warning["leaves"] == [50]
    assert len(fake.paths("/api/products-by-category/50")) == 4  # 1 try + 3 retries
    assert run_row(admin, outcome.run_id)["status"] == "partial"
    assert one(admin, "SELECT data_date FROM api.latest") == TODAY  # a partial day is still served
    row = admin.execute(
        "SELECT product_min_amount, normal_amount, xlsx_min FROM core.product_chain_day "
        "WHERE data_date = %s AND product_id = %s",
        (TODAY, WORLD.special["spar_outlier"]),
    ).fetchone()
    assert row == (699, 294, 294)  # listing columns kept from the first run, XLSX columns refreshed


def test_failed_leaf_on_the_first_run_leaves_xlsx_only_rows(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    fake = FakeGvh(WORLD, data_date=TODAY)
    fake.fail("/api/products-by-category/50", 503, times=100)
    outcome = daily(conn, fake)
    assert outcome.status == "partial"
    row = admin.execute(
        "SELECT d.product_min_amount, d.xlsx_min, d.xlsx_max, p.unit_title FROM core.product_chain_day d "
        "JOIN core.product p ON p.id = d.product_id WHERE d.data_date = %s AND d.product_id = %s",
        (TODAY, WORLD.special["spar_outlier"]),
    ).fetchone()
    assert row == (None, 294, 699, None)


def test_stale_xlsx_fails_the_run_before_anything_is_written(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    fake = FakeGvh(WORLD, data_date=TODAY)
    fake.xlsx_date = TODAY - timedelta(days=1)
    outcome = daily(conn, fake)
    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error.startswith("StaleXlsxError: stale daily XLSX")
    assert fake.paths("/api/products-by-category") == []  # no listing after a stale XLSX
    assert outcome.requests == 4  # 3 reference + 1 XLSX
    run = run_row(admin, outcome.run_id)
    assert (run["status"], run["error"]) == ("failed", outcome.error)
    assert one(admin, "SELECT count(*) FROM core.product_chain_day") == 0
    assert one(admin, "SELECT data_date FROM api.latest") is None


def test_listing_schema_change_fails_loudly_but_archives_the_xlsx(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    fake = FakeGvh(WORLD, data_date=TODAY)
    fake.drift = "type_change"
    outcome = daily(conn, fake)
    assert outcome.status == "failed"
    assert outcome.error is not None
    assert "GvhSchemaError" in outcome.error
    assert "productMinAmount" in outcome.error
    assert len(fake.paths("/api/products-by-category")) == 1  # stopped at the first bad page
    assert one(admin, "SELECT count(*) FROM core.product_chain_day WHERE xlsx_min IS NOT NULL") > 0
    assert one(admin, "SELECT count(*) FROM core.product_chain_day WHERE product_min_amount IS NOT NULL") == 0
    assert one(admin, "SELECT data_date FROM api.latest") is None  # a failed day is never served


def test_leaves_gvh_no_longer_lists_are_not_fetched(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    assert daily(conn, FakeGvh(WORLD, data_date=TODAY)).status == "ok"

    def drop_leaf_50(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for top in tree:
            for l2 in top["categoryNodes"]:
                l2["categoryNodes"] = [leaf for leaf in l2["categoryNodes"] if leaf["id"] != 50]
        return tree

    fake = FakeGvh(WORLD, data_date=TODAY)
    outcome = daily(conn, fake, transport=patched(fake, "/api/categories", drop_leaf_50))
    assert outcome.status == "ok", outcome
    assert fake.paths("/api/products-by-category/50") == []
    assert outcome.stats["leaves_fetched"] == 119
    assert one(admin, "SELECT count(*) FROM core.category WHERE id = 50") == 1  # kept: products reference it


def test_unreachable_reference_falls_back_to_stored_data(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    fake = FakeGvh(WORLD, data_date=TODAY)
    fake.fail("/api/chain-stores", 503, times=100)
    first = daily(conn, fake)
    assert first.status == "failed"
    assert first.error is not None
    assert "reference data unavailable and none stored yet" in first.error

    assert daily(conn, FakeGvh(WORLD, data_date=TODAY)).status == "ok"
    fake = FakeGvh(WORLD, data_date=TODAY)
    fake.fail("/api/shops", 503, times=100)
    outcome = daily(conn, fake)
    assert outcome.status == "partial", outcome
    assert "reference_failed" in codes(outcome)
    assert outcome.stats["leaves_fetched"] == 120


def test_unknown_fields_are_recorded_as_drift_warnings(conn: psycopg.Connection) -> None:
    fake = FakeGvh(WORLD, data_date=TODAY)
    fake.drift = "extra_field"
    outcome = daily(conn, fake)
    assert outcome.status == "ok"
    (drift,) = [w for w in outcome.warnings if w["code"] == "schema_drift"]
    assert drift["fields"] == ["ListingProduct.newField"]


def test_request_budget_makes_the_run_partial(conn: psycopg.Connection, admin: psycopg.Connection) -> None:
    set_ontology(admin, INGREDIENT_LEAVES)
    fake = FakeGvh(WORLD, data_date=TODAY)
    outcome = daily(conn, fake, max_requests=40)
    assert outcome.status == "partial"
    assert outcome.requests == len(fake.requests) == 40
    assert "request_budget_exhausted" in codes(outcome)
    assert one(admin, "SELECT count(*) FROM core.product_chain_day") > 0


def test_history_trigger_is_respected(conn: psycopg.Connection, admin: psycopg.Connection) -> None:
    """A past day is append-only: a re-run inserts nothing new and never tries to UPDATE archived rows."""
    set_ontology(admin, INGREDIENT_LEAVES)
    first = daily(conn, FakeGvh(WORLD, data_date=PAST))
    assert first.status == "ok", first
    archived = {name: table(admin, name) for name in ("product_chain_day", "store_price_day")}
    assert archived["product_chain_day"]
    assert archived["store_price_day"]

    def cheaper(page: dict[str, Any]) -> dict[str, Any]:
        for product in page["products"]:
            for chain in product["pricesOfChainStores"]:
                chain["productMinAmount"] -= 1
        return page

    changed = FakeGvh(WORLD, data_date=PAST)
    second = daily(conn, changed, transport=patched(changed, "/api/products-by-category", cheaper))
    assert second.status == "ok", second
    kept = [w["count"] for w in second.warnings if w["code"] == "history_append_only"]
    assert kept == [len(archived["product_chain_day"]), len(archived["store_price_day"])]
    assert {name: table(admin, name) for name in archived} == archived
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="append-only"):
        conn.execute("UPDATE core.product_chain_day SET product_min_amount = 1 WHERE data_date = %s", (PAST,))


def test_has_data_date_never_moves_backwards(conn: psycopg.Connection, admin: psycopg.Connection) -> None:
    set_ontology(admin, INGREDIENT_LEAVES)
    assert daily(conn, FakeGvh(WORLD, data_date=TODAY)).status == "ok"
    marked = one(admin, "SELECT count(*) FROM core.store WHERE has_data_date = %s", (TODAY,))
    assert marked > 0
    assert daily(conn, FakeGvh(WORLD, data_date=PAST)).status == "ok"
    assert one(admin, "SELECT count(*) FROM core.store WHERE has_data_date = %s", (TODAY,)) == marked
    assert one(admin, "SELECT count(*) FROM core.store WHERE has_data_date = %s", (PAST,)) == 0


def test_runs_of_the_same_kind_do_not_overlap(conn: psycopg.Connection, cluster: PgCluster) -> None:
    with cluster.connect("ingest", autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock(727100, 2)")
        with pytest.raises(IngestBusyError):
            daily(conn, FakeGvh(WORLD, data_date=TODAY))
        other.execute("SELECT pg_advisory_unlock(727100, 2)")


def test_a_transactional_connection_is_refused(cluster: PgCluster) -> None:
    with cluster.connect("ingest") as plain, pytest.raises(ValueError, match="autocommit"):
        daily(plain, FakeGvh(WORLD, data_date=TODAY))


# ───────────────────────────── availability ─────────────────────────────


def test_availability_run_writes_lists_and_marks_stores(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    set_ontology(admin, [7, 50])
    assert daily(conn, FakeGvh(WORLD, data_date=TODAY)).status == "ok"
    admin.execute("UPDATE core.store SET has_data_date = NULL")
    fake = FakeGvh(WORLD, data_date=TODAY)
    with client_for(fake.transport()) as client:
        outcome = run_availability(conn, client, clock=lambda: at_half_past_midnight(TODAY))
    assert outcome.status == "ok", outcome
    products = [p for p in WORLD.products.values() if p.leaf_id in (7, 50)]
    assert outcome.requests == len(products) == len(fake.paths("/api/product/"))
    expected = {(p.id, WORLD.chains[o.chain].uuid): sorted(o.stores) for p in products for o in p.offers}
    stored = {
        (pid, cid): ids
        for pid, cid, ids in admin.execute(
            "SELECT product_id, chain_id, store_ids FROM core.product_availability WHERE as_of = %s", (TODAY,)
        )
    }
    assert stored == expected
    listed = {s for ids in expected.values() for s in ids}
    marked = {row[0] for row in admin.execute("SELECT id FROM core.store WHERE has_data_date = %s", (TODAY,))}
    assert marked == listed
    assert not marked & NO_DATA_STORES
    run = run_row(admin, outcome.run_id)
    assert (run["kind"], run["status"], run["data_date"]) == ("availability", "ok", TODAY)
    assert run["stats"]["availability_rows"] == len(expected)

    with client_for(FakeGvh(WORLD, data_date=TODAY).transport()) as client:
        again = run_availability(conn, client, data_date=TODAY)
    assert again.status == "ok"
    assert one(admin, "SELECT count(*) FROM core.product_availability") == len(expected)


def test_availability_needs_an_ontology_and_a_daily_run(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    fake = FakeGvh(WORLD, data_date=TODAY)
    with client_for(fake.transport()) as client:
        empty = run_availability(conn, client, data_date=TODAY)
    assert (empty.status, codes(empty), empty.requests) == ("ok", ["no_ingredient_leaves"], 0)
    set_ontology(admin, [7])
    with client_for(fake.transport()) as client:
        no_daily = run_availability(conn, client, data_date=TODAY)
    assert (no_daily.status, codes(no_daily), no_daily.requests) == ("ok", ["no_daily_data"], 0)


def test_availability_missing_product_makes_the_run_partial(
    conn: psycopg.Connection, admin: psycopg.Connection
) -> None:
    set_ontology(admin, [7])
    assert daily(conn, FakeGvh(WORLD, data_date=TODAY)).status == "ok"
    fake = FakeGvh(WORLD, data_date=TODAY)
    gone = WORLD.special["multichain"]
    fake.fail(f"/api/product/{gone}", 404)
    with client_for(fake.transport()) as client:
        outcome = run_availability(conn, client, data_date=TODAY)
    assert outcome.status == "partial"
    (warning,) = [w for w in outcome.warnings if w["code"] == "product_not_found"]
    assert warning["products"] == [gone]
    assert one(admin, "SELECT count(*) FROM core.product_availability WHERE product_id = %s", (gone,)) == 0


def test_availability_schema_change_fails_after_archiving_valid_batches(
    conn: psycopg.Connection, admin: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bpf.ingest import availability

    monkeypatch.setattr(availability, "BATCH_SIZE", 2)
    set_ontology(admin, [7])
    assert daily(conn, FakeGvh(WORLD, data_date=TODAY)).status == "ok"
    products = sorted(p.id for p in WORLD.leaf_products(7))
    fake = FakeGvh(WORLD, data_date=TODAY)

    def break_third(detail: dict[str, Any]) -> dict[str, Any]:
        return (
            {k: v for k, v in detail.items() if k != "chainStores"} if detail["id"] == products[2] else detail
        )

    with client_for(patched(fake, "/api/product/", break_third)) as client:
        outcome = run_availability(conn, client, data_date=TODAY)
    assert outcome.status == "failed"
    assert outcome.error is not None
    assert "chainStores: missing" in outcome.error
    stored = {row[0] for row in admin.execute("SELECT DISTINCT product_id FROM core.product_availability")}
    assert stored == set(products[:2])


# ───────────────────────────── CLI ─────────────────────────────


def test_cli_end_to_end_over_real_sockets(
    cluster: PgCluster, admin: psycopg.Connection, capsys: pytest.CaptureFixture[str]
) -> None:
    """``main()`` with the threaded fake server (real HTTP) and an injected sleep."""
    set_ontology(admin, INGREDIENT_LEAVES)
    fake = FakeGvh(WORLD, data_date=TODAY)
    clock = FakeClock()
    with fake.serve() as server:
        settings = cluster.settings(
            gvh_base_url=server.api_base, gvh_xlsx_url=server.xlsx_url, contact_email=CONTACT
        )

        def factory(s: Settings, budget: int | None) -> GvhClient:
            return GvhClient(s, max_requests=budget, clock=clock.monotonic, sleep=clock.sleep)

        def run(*argv: str) -> int:
            return cli_main(
                list(argv),
                settings=settings,
                client_factory=factory,
                clock=lambda: at_half_past_midnight(TODAY),
            )

        assert run("reference") == 0
        assert run("daily") == 0
        assert run("availability") == 0
        assert run("daily", "--max-requests", "30") == 3
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith(f"reference {TODAY.isoformat()}: ok (run ")
    assert out[1].startswith(f"daily {TODAY.isoformat()}: ok")
    assert out[3].startswith(f"daily {TODAY.isoformat()}: partial")
    statuses = admin.execute("SELECT kind, status FROM ops.ingest_run ORDER BY id").fetchall()
    assert statuses == [("reference", "ok"), ("daily", "ok"), ("availability", "ok"), ("daily", "partial")]
    assert all(r.user_agent and CONTACT in r.user_agent for r in fake.requests)


def _subprocess_env(cluster: PgCluster, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("BPF_")}
    env.update(
        BPF_ENV_FILE=str(cluster.env_file), NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost"
    )
    env.update(extra)
    return env


def test_cli_subprocess_exit_codes(cluster: PgCluster, admin: psycopg.Connection) -> None:
    """``python -m bpf.ingest`` for real (real clock, real 1 s throttle) against a 3-leaf fake."""
    set_ontology(admin, [7, 50])
    tiny = build_world(leaf_subset=frozenset({7, 40, 50}))
    today = budapest_today()
    fake = FakeGvh(tiny, data_date=today)

    def cli(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "bpf.ingest", *args],
            cwd=SERVER_DIR,
            env=_subprocess_env(cluster, **env),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

    with fake.serve() as server:
        gvh = {"BPF_GVH_BASE_URL": server.api_base, "BPF_GVH_XLSX_URL": server.xlsx_url}
        reference = cli("reference", BPF_CONTACT_EMAIL=CONTACT, **gvh)
        assert reference.returncode == 0, reference.stderr
        result = cli("daily", "--budapest-only", BPF_CONTACT_EMAIL=CONTACT, **gvh)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith(f"daily {today.isoformat()}: ok")
        fake.xlsx_date = today - timedelta(days=1)
        stale = cli("daily", BPF_CONTACT_EMAIL=CONTACT, **gvh)
        assert stale.returncode == 1
        assert "StaleXlsxError" in stale.stdout
        no_contact = cli("reference", **gvh)
        assert no_contact.returncode == 1
        assert "BPF_CONTACT_EMAIL" in no_contact.stderr
        bad_date = cli("daily", "--date", "2026-13-01", BPF_CONTACT_EMAIL=CONTACT, **gvh)
        assert bad_date.returncode == 2
        both = cli("daily", "--budapest-only", "--all-stores", BPF_CONTACT_EMAIL=CONTACT, **gvh)
        assert both.returncode == 2
    for output in (reference, result, stale, no_contact):
        text = output.stdout + output.stderr
        assert cluster.password("ingest") not in text  # never log secrets
        assert '"pricesOfChainStores"' not in text  # never log response bodies
    statuses = admin.execute("SELECT kind, status FROM ops.ingest_run ORDER BY id").fetchall()
    assert statuses == [("reference", "ok"), ("daily", "ok"), ("daily", "failed")]
    assert one(admin, "SELECT count(*) FROM core.store_price_day") > 0
