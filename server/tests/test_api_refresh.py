"""Catalogue cache life cycle against a real cluster (SYNTHETIC data, tests/fixtures/api/seed.py): no data
yet, the first successful ingest, the 60 s re-check, availability runs (the Store.has_data rule), re-runs,
failed runs, content changes (incl. a KSH row stored by the content loader), and a database that goes away
after the catalogue was loaded. Each test uses a cluster of its own (it commits data, and one
stops the server)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from bpf.content.writer import sync_ksh
from bpf.pricing import KshPrice
from tests.fixtures.api import seed
from tests.fixtures.api.seed import DATA_DATE, FakeClock
from tests.pgcluster import PgCluster

pytestmark = pytest.mark.db

NEXT_DATE = DATA_DATE + timedelta(days=1)
KSH_PERIOD = date(2026, 9, 1)
QUOTE = {"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": ["alfa-1"]}


def costs(client: seed.TestClient) -> dict[str, float | None]:
    return {r["id"]: r["cost_per_serving_from"] for r in client.get("/api/recipes").json()["recipes"]}


def has_data(client: seed.TestClient) -> dict[str, bool]:
    return {s["id"]: s["has_data"] for s in client.get("/api/stores").json()["stores"]}


def test_from_no_data_to_refreshed_catalogue(pg_factory: Callable[..., PgCluster]) -> None:
    cluster = pg_factory()
    clock = FakeClock()
    settings = seed.api_settings(cluster.settings())
    with seed.client_for(settings, clock=clock) as (client, provider):
        # ── 1. an empty database: no successful ingest, no content ──
        health = client.get("/api/health")
        assert (health.status_code, health.json()) == (
            200,
            {"status": "degraded", "db": True, "data_date": None},
        )
        meta = client.get("/api/meta").json()
        assert (meta["data_date"], meta["ingested_at"], meta["stale"], meta["ksh_period"]) == (
            None,
            None,
            True,
            None,
        )
        assert meta["attribution"]["gvh"]["text_hu"] == "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu)"
        assert meta["attribution"]["nutrition"] is None
        assert client.get("/api/stores").json() == {"data_date": None, "stores": []}
        assert client.get("/api/recipes").json() == {"data_date": None, "recipes": []}
        no_data = client.post("/api/quote", json=QUOTE)
        assert (no_data.status_code, no_data.json()) == (503, {"error": "no_data", "fields": []})
        assert no_data.headers["cache-control"] == "no-store"
        plan = client.post("/api/plan/suggest", json={"days": 3}).json()
        assert plan["warnings"][:3] == [
            "slot_pool_empty:reggeli",
            "slot_pool_empty:ebed",
            "slot_pool_empty:vacsora",
        ]

        # ── 2. reference data and content, still no successful daily run ──
        with cluster.connect("ingest") as conn:
            seed.seed_reference(conn)
            seed.seed_content(conn)
            seed.seed_day_prices(conn, DATA_DATE)  # written, but the run is still "running"
            seed.add_run(conn, DATA_DATE, status="running")
        assert client.get("/api/recipes").json()["recipes"] == []  # cached for 60 s
        clock.advance(61)
        assert set(costs(client).values()) == {None}  # recipes are listed, every cost is null
        assert all(r["priced_share"] == 0.0 for r in client.get("/api/recipes").json()["recipes"])
        assert set(has_data(client).values()) == {False}  # no data date: no store has data
        assert client.post("/api/quote", json=QUOTE).status_code == 503
        history = client.get("/api/ingredients/rizs/history")
        assert (history.status_code, history.json()) == (503, {"error": "no_data", "fields": []})
        budget = client.post("/api/plan/suggest", json={"days": 7, "weekly_budget": 10000}).json()
        assert "recipe_cost_missing" in budget["warnings"]
        assert "budget" not in {c["rule"] for c in budget["checks"]}

        # ── 3. the first successful daily run ──
        with cluster.connect("ingest") as conn:
            seed.add_run(conn, DATA_DATE)
        assert costs(client)["zz-csirkes-rizs"] is None  # still the cached catalogue
        clock.advance(59)
        assert costs(client)["zz-csirkes-rizs"] is None  # 59 s after the last check: still cached
        clock.advance(2)
        assert costs(client)["zz-csirkes-rizs"] == 408.4
        assert client.get("/api/health").json() == {"status": "ok", "db": True, "data_date": "2026-10-12"}
        assert client.post("/api/quote", json=QUOTE).json()["stores"][0]["checkout_total"] == 499.0
        # no availability refresh yet: every store counts as having data (even never-seen delta-1)
        assert set(has_data(client).values()) == {True}
        loaded = provider.snapshot()
        clock.advance(61)
        assert provider.snapshot() is loaded  # re-checked, unchanged: not reloaded

        # ── 4. availability: only a finished ok/partial run within 8 days of the data date counts ──
        with cluster.connect("ingest") as conn:
            seed.seed_availability(conn, seed.AVAILABILITY_DATE)  # lists alone are not a finished run
            seed.add_run(conn, seed.AVAILABILITY_DATE, kind="availability", status="failed")
            seed.add_run(conn, seed.AVAILABILITY_DATE, kind="availability", status="running")
        clock.advance(61)
        assert provider.snapshot() is loaded  # api.ingest_latest has no availability row: same key
        assert set(has_data(client).values()) == {True}
        with cluster.connect("ingest") as conn:  # ok, but finished 9 days before the data date
            seed.add_run(conn, DATA_DATE - timedelta(days=9), kind="availability")
        clock.advance(61)
        assert provider.snapshot() is not loaded  # the availability run is part of the cache key
        assert set(has_data(client).values()) == {True}
        with cluster.connect("ingest") as conn:  # 23:59 Budapest on day -9 (CEST): still 9 days
            late = datetime(2026, 10, 3, 21, 59, tzinfo=UTC)
            seed.add_run(conn, DATA_DATE - timedelta(days=9), kind="availability", finished_at=late)
        clock.advance(61)
        assert set(has_data(client).values()) == {True}
        recent = {
            "alfa-1": True,
            "beta-1": True,
            "beta-2": True,
            "delta-1": False,
            "gamma-1": True,
            "gamma-2": False,
        }
        with cluster.connect("ingest") as conn:  # a partial run 2 days before: recent, has_data_date decides
            seed.add_run(conn, seed.AVAILABILITY_DATE, kind="availability", status="partial")
        clock.advance(61)
        assert has_data(client) == recent
        quote = client.post("/api/quote", json={**QUOTE, "store_ids": ["gamma-2"]}).json()
        assert quote["stores"][0]["lines"][0]["status"] == "unavailable"  # no data: never a chain price
        # ── 4b. a re-run of the same day's daily ingest is picked up ──
        with cluster.connect("ingest") as conn:
            seed.add_run(conn, DATA_DATE, finished_at=datetime(2026, 10, 12, 5, 0, tzinfo=UTC))
        clock.advance(61)
        assert client.get("/api/meta").json()["ingested_at"] == "2026-10-12T05:00:00Z"
        assert has_data(client) == recent

        # ── 5. a newer data date: ignored while its run is failed or running, used once it is ok ──
        with cluster.connect("ingest") as conn:
            seed.seed_day_prices(conn, NEXT_DATE, overrides={("zz-p-rizs-1", "zz-chain-alfa"): Decimal(459)})
            seed.add_run(conn, NEXT_DATE, status="failed")
            seed.add_run(conn, NEXT_DATE, status="running")
        clock.advance(61)
        assert client.get("/api/meta").json()["data_date"] == "2026-10-12"
        assert costs(client)["zz-rizs-koret"] == 49.9
        with cluster.connect("ingest") as conn:
            seed.add_run(conn, NEXT_DATE, status="partial")  # partial runs count as successful
        clock.advance(61)
        assert client.get("/api/meta").json()["data_date"] == "2026-10-13"
        recipe = client.get("/api/recipes?q=parolt").json()["recipes"][0]
        assert (recipe["cost_per_serving_from"], recipe["cheapest_chains"]) == (
            45.9,
            ["alfa"],
        )  # 0.2 x 459 / 2
        assert client.post("/api/quote", json=QUOTE).json()["stores"][0]["checkout_total"] == 459.0

        # ── 6. a content change without a new run ──
        with cluster.connect("ingest") as conn:
            seed.add_recipe(
                conn, "zz-uj-recept", "Új recept", ["ebed"], 1, 10, ["gyors"], [("rizs", "0.1", "1", False)]
            )
        clock.advance(61)
        assert costs(client)["zz-uj-recept"] == 45.9  # 0.1 x 459

        # ── 7. a KSH row written by the content loader is per ONE unit (docs/DATA.md) ──
        # SYNTHETIC egg row as the CSV carries it: 814 Ft for unit_qty 10 db; sync_ksh stores 81.40 Ft/db.
        eggs = KshPrice(
            "zz-tojas-ksh", "Szintetikus tojás, 10 darab", "db", Decimal(10), Decimal(814), KSH_PERIOD
        )
        with cluster.connect("ingest") as conn:
            sync_ksh(conn, [eggs])
            conn.execute(
                "INSERT INTO app.ingredient (id, name_hu, list_group, unit, piece_weight_kg, pantry, "
                "ksh_code, tags) VALUES ('zz_ksh_tojas', 'szintetikus KSH-tojás', 'tejtermek_tojas', 'db', "
                "0.06, false, 'zz-tojas-ksh', ARRAY['egg'])"
            )
        clock.advance(61)
        stored = provider.snapshot().catalogue.ksh["zz-tojas-ksh"]
        assert (stored.unit, stored.unit_qty, stored.price) == ("db", Decimal(1), Decimal("81.40"))
        ten = {"lines": [{"ingredient_id": "zz_ksh_tojas", "qty": 10}], "store_ids": ["alfa-1"]}
        store = client.post("/api/quote", json=ten).json()["stores"][0]
        assert (store["lines"][0]["status"], store["lines"][0]["ksh_estimate"]) == ("ksh_estimate", 814.0)
        assert (store["ksh_estimate_total"], store["checkout_total"]) == (814.0, 0.0)  # never added
        priced_by = {i["id"]: i["priced_by"] for i in client.get("/api/ingredients").json()["ingredients"]}
        assert priced_by["zz_ksh_tojas"] == "ksh"


def test_database_down_after_loading(pg_factory: Callable[..., PgCluster]) -> None:
    """A loaded catalogue keeps being served when the database goes away (re-checks fail quietly); health
    reports down; history (which reads the archive) is unavailable."""
    cluster = pg_factory()
    with cluster.connect("ingest") as conn:
        seed.seed_all(conn)
    clock = FakeClock()
    with seed.client_for(seed.api_settings(cluster.settings()), clock=clock) as (client, _):
        stores = client.get("/api/stores")
        quote = client.post("/api/quote", json=QUOTE)
        assert stores.status_code == quote.status_code == 200
        cluster.script("db-stop.sh")
        health = client.get("/api/health")
        assert (health.status_code, health.json()) == (
            503,
            {"status": "down", "db": False, "data_date": None},
        )
        clock.advance(61)  # the re-check fails: the cached snapshot is served
        again = client.get("/api/stores")
        assert (again.status_code, again.content) == (200, stores.content)
        assert client.post("/api/quote", json=QUOTE).json() == quote.json()
        history = client.get("/api/ingredients/rizs/history")
        assert (history.status_code, history.json()) == (503, {"error": "no_data", "fields": []})
