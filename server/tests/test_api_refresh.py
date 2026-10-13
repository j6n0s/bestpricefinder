"""Catalogue cache life cycle against a real cluster (SYNTHETIC data, tests/fixtures/api/seed.py): no data
yet, the first successful ingest, the 60 s re-check, re-runs, failed runs, content changes, and a database
that goes away after the catalogue was loaded. Each test uses a cluster of its own (it commits data, and one
stops the server)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tests.fixtures.api import seed
from tests.fixtures.api.seed import DATA_DATE, FakeClock
from tests.pgcluster import PgCluster

pytestmark = pytest.mark.db

NEXT_DATE = DATA_DATE + timedelta(days=1)
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

        # ── 4. an availability refresh and a re-run of the same day ──
        with cluster.connect("ingest") as conn:
            seed.seed_availability(conn, DATA_DATE - timedelta(days=2))
            seed.add_run(conn, DATA_DATE, finished_at=datetime(2026, 10, 12, 5, 0, tzinfo=UTC))
        clock.advance(61)
        assert has_data(client) == {
            "alfa-1": True,
            "beta-1": True,
            "beta-2": True,
            "delta-1": False,
            "gamma-1": True,
            "gamma-2": False,
        }
        assert client.get("/api/meta").json()["ingested_at"] == "2026-10-12T05:00:00Z"

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
