"""Every /api endpoint against a real migrated cluster, a SYNTHETIC hand-made catalogue inserted as
``bpf_ingest`` (tests/fixtures/api/seed.py), and the API connecting as ``bpf_api`` through ``bpf.db``.

Expected numbers are computed by hand from the seed (data date 2026-10-12, "today" 2026-10-13):

Quote 1 (csirkemell 1.2 kg, tojás 12 db, rizs 0.5 kg, napraforgóolaj 0.2 l, só, pirospaprika 0.02 kg, fahéj):
* alfa-1: chicken loose 1.2 x 2490 = 2988 (the 0.5 kg pack at 1390 is dearer than 0.5 kg loose, 1245);
  eggs 2 x 899 = 1798 (used 12 x 1798 / 20 = 1078.80); rice 499 (used 249.50, in the availability list:
  confirmed); oil 799 (used 159.80). Checkout 6084, used 4476.10, 3 lines only "assumed" available.
* beta-1: chicken 3 x 1290 = 3870 (store row: min(1490 NORMAL, 1290 DISCOUNTED), used 1.2 x 3870 / 1.5 =
  3096); eggs 2 x 499 (6-packs, listed at beta-1) = 998; rice 549 (used 274.50); oil not sold at beta:
  unavailable. Checkout 5417, used 4368.50.
* beta-2: chicken chain price 3 x 1490 = 4470 (used 3576); the 6-pack is not listed at beta-2, so eggs are
  2 x 999 = 1998 (used 1198.80); rice 549. Checkout 7017, used 5049.30.
* gamma-1: chicken 1.2 x 2390 = 2868; eggs 2 x 949 DISCOUNTED = 1898 (used 1138.80); rice 499; oil 749.
  Checkout 6014, used 4406.10.
* Ranking: missing oil is imputed at the median of the other stores' oil cost, (799 + 749) / 2 = 774:
  gamma-1 6014 (1), alfa-1 6084 (2), beta-1 5417 + 774 = 6191 (3), beta-2 7017 + 774 = 7791 (4).
  The best pair saves less than 1,500 Ft: no split.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

from bpf.api.repo import CatalogueProvider, assemble_snapshot
from bpf.api.texts import DISCLAIMER_EN, DISCLAIMER_HU
from bpf.planner import suggest_plan
from bpf.pricing import SLOTS_3, PlanRequest
from tests.fixtures.api import seed
from tests.fixtures.api.memory import memory_raw
from tests.fixtures.api.seed import TestClient
from tests.pgcluster import PgCluster, free_port

pytestmark = pytest.mark.db

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "permissions-policy": "geolocation=(self), camera=(), microphone=(), payment=(), usb=()",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}
SENTINEL = "zzSENTINEL7f3a"


@pytest.fixture(scope="module")
def cluster(pg_factory: Callable[..., PgCluster]) -> PgCluster:
    cluster = pg_factory()
    with cluster.connect("ingest") as conn:  # committed on exit
        seed.seed_all(conn)
    return cluster


@pytest.fixture(scope="module")
def api(cluster: PgCluster) -> Iterator[tuple[TestClient, CatalogueProvider]]:
    with seed.client_for(seed.api_settings(cluster.settings())) as pair:
        yield pair


@pytest.fixture
def client(api: tuple[TestClient, CatalogueProvider]) -> TestClient:
    return api[0]


def assert_security_headers(headers: Any) -> None:
    for name, value in SECURITY_HEADERS.items():
        assert headers.get(name) == value, name
    assert "server" not in headers
    assert "strict-transport-security" not in headers  # BPF_HSTS is off by default


# ───────────────────────────── the provider ─────────────────────────────


def test_views_load_exactly_the_seeded_catalogue(api: tuple[TestClient, CatalogueProvider]) -> None:
    """Every column read from the api.* views lands in the right field (compared with the same data built
    in memory); only products of leaves referenced by ingredients are loaded."""
    _, provider = api
    loaded = provider.snapshot()
    expected = assemble_snapshot(memory_raw(key=loaded.key))
    for name in (
        "data_date",
        "ingredients",
        "products",
        "chains",
        "stores",
        "chain_prices",
        "store_prices",
        "availability",
        "products_by_leaf",
        "ksh",
        "recipes",
        "nutrition",
    ):
        assert getattr(loaded.catalogue, name) == getattr(expected.catalogue, name), name
    assert loaded.stores == expected.stores
    assert loaded.recipe_costs == expected.recipe_costs
    assert loaded.recipe_summaries == expected.recipe_summaries
    assert loaded.ingested_at == expected.ingested_at
    assert loaded.ksh_period == date(2026, 9, 1)
    assert loaded.nutrition_sources == frozenset({"ciqual"})
    raw = provider.source.load()  # the availability run comes from api.ingest_latest (migration 0003)
    assert raw.availability_finished_at == seed.AVAILABILITY_FINISHED_AT
    assert raw.availability_finished_at == memory_raw().availability_finished_at
    availability_key = (seed.AVAILABILITY_DATE, seed.AVAILABILITY_FINISHED_AT)
    assert loaded.key[2:4] == availability_key  # part of the cache key


def test_api_role_reads_ingest_latest_not_ingest_run(cluster: PgCluster) -> None:
    """bpf_api reads kind, data date and finish time from api.ingest_latest (never ops.ingest_run itself)."""
    with cluster.connect("api") as conn:
        rows = conn.execute(
            "SELECT kind, data_date, finished_at FROM api.ingest_latest ORDER BY kind"
        ).fetchall()
        assert rows == [
            ("availability", seed.AVAILABILITY_DATE, seed.AVAILABILITY_FINISHED_AT),
            ("daily", seed.DATA_DATE, seed.run_finished_at(seed.DATA_DATE)),
        ]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT 1 FROM ops.ingest_run")


def test_api_session_is_bpf_api_and_read_only(api: tuple[TestClient, CatalogueProvider]) -> None:
    _, provider = api
    assert provider.session_info() == ("bpf_api", "on")


def test_catalogue_is_cached_between_requests(api: tuple[TestClient, CatalogueProvider]) -> None:
    client, provider = api
    first = provider.snapshot()
    client.get("/api/stores")
    client.get("/api/recipes")
    assert provider.snapshot() is first


# ───────────────────────────── GET endpoints ─────────────────────────────


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True, "data_date": "2026-10-12"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert_security_headers(response.headers)


def test_meta(client: TestClient) -> None:
    response = client.get("/api/meta")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.json() == {
        "data_date": "2026-10-12",
        "ingested_at": "2026-10-12T02:45:00Z",
        "stale": False,
        "ksh_period": "2026-09-01",
        "chains": [
            {"id": "zz-chain-alfa", "slug": "alfa", "name": "Alfa", "is_grocery": True},
            {"id": "zz-chain-beta", "slug": "beta", "name": "Beta", "is_grocery": True},
            {"id": "zz-chain-delta", "slug": "delta", "name": "Delta", "is_grocery": False},
            {"id": "zz-chain-gamma", "slug": "gamma", "name": "Gamma", "is_grocery": True},
        ],
        "attribution": {
            "gvh": {
                "text_hu": "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), 2026-10-12",
                "text_en": "Source: GVH Árfigyelő (arfigyelo.gvh.hu), 2026-10-12",
                "url": "https://arfigyelo.gvh.hu",
                "license": None,
            },
            "ksh": {
                "text_hu": "Forrás: KSH",
                "text_en": "Source: KSH (Hungarian Central Statistical Office)",
                "url": "https://www.ksh.hu/stadat_files/ara/hu/ara0044.html",
                "license": "CC BY 4.0",
            },
            "nutrition": {
                "text_hu": "Tápérték-adatok forrása: ANSES-CIQUAL",
                "text_en": "Nutrition data: ANSES-CIQUAL",
                "url": "https://ciqual.anses.fr",
                "license": "Licence Ouverte / Etalab 2.0",
            },
        },
        "disclaimer_hu": "Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal.",
        "disclaimer_en": DISCLAIMER_EN,
    }
    assert DISCLAIMER_HU == "Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal."


def _store(sid: str, chain: str, postal: str, city: str, fmt: str | None, has_data: bool) -> dict[str, Any]:
    return {
        "id": sid,
        "chain": chain,
        "postal_code": postal,
        "city": city,
        "address": f"Teszt utca {sid}",
        "lat": 47.5,
        "lon": 19.05,
        "format": fmt,
        "is_budapest": postal.startswith("1"),
        "has_data": has_data,
    }


def test_stores_and_has_data_rule(client: TestClient) -> None:
    """An availability run finished 2 days before the data date (api.ingest_latest), so has_data follows
    has_data_date: beta-2 (1 day old) has data, gamma-2 (20 days old) and delta-1 (never) have none.
    Without a recent availability run every store has data (tests/test_api_refresh.py)."""
    response = client.get("/api/stores")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.json() == {
        "data_date": "2026-10-12",
        "stores": [
            _store("alfa-1", "alfa", "1051", "Budapest", "hyper", True),
            _store("beta-1", "beta", "1111", "Budapest", "hyper", True),
            _store("beta-2", "beta", "1111", "Budapest", None, True),
            _store("delta-1", "delta", "1051", "Budapest", "hyper", False),
            _store("gamma-1", "gamma", "6720", "Szeged", "hyper", True),
            _store("gamma-2", "gamma", "6720", "Szeged", None, False),
        ],
    }


def test_ingredients(client: TestClient) -> None:
    response = client.get("/api/ingredients")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"
    rows = {i["id"]: i for i in response.json()["ingredients"]}
    assert list(rows) == sorted(rows)
    assert {k: v["priced_by"] for k, v in rows.items()} == {
        "csirkemell": "gvh",
        "fahej": "none",  # no leaves, no KSH row
        "napraforgoolaj": "gvh",  # a pantry staple WITH leaves is priced
        "pirospaprika": "ksh",
        "rizs": "gvh",
        "sertescomb": "none",
        "so": "none",  # pantry without leaves: never priced
        "tojas": "gvh",
    }
    assert rows["tojas"] == {
        "id": "tojas",
        "name_hu": "tojás",
        "list_group": "tejtermek_tojas",
        "unit": "db",
        "piece_weight_kg": 0.06,
        "pantry": False,
        "priced_by": "gvh",
        "tags": ["egg"],
    }
    assert rows["so"]["pantry"] is True


SUMMARIES = {
    # alfa 1494 + 199.6, beta 1788 + 219.6, gamma 1434 + 199.6 (chicken + rice; pantry/optional lines out) / 4
    "zz-csirkes-rizs": (408.4, ["gamma"], 1.0),
    # eggs 4 x min(499/6, 999/10) = 332.67 + rice 109.8 at beta -> 221.23; alfa 229.70, gamma 239.70
    "zz-tojasos-rizs": (221.23, ["beta"], 1.0),
    # rice 0.2 kg: alfa 99.8 / 2 = 49.90 = gamma; a tie group, never broken
    "zz-rizs-koret": (49.9, ["alfa", "gamma"], 1.0),
    # chicken 0.5 kg at gamma 1195 / 2 = 597.50; paprika missing everywhere, KSH estimate 40:
    # share 1195 / 1235 = 0.96761 (rounded down)
    "zz-paprikas-csirke": (597.5, ["gamma"], 0.9676),
    "zz-porkolt": (None, [], 0.0),  # nothing priceable
}


def test_recipe_list_costs_and_ties(client: TestClient) -> None:
    response = client.get("/api/recipes")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    body = response.json()
    assert body["data_date"] == "2026-10-12"
    ids = [r["id"] for r in body["recipes"]]
    # sorted by accent-folded title: csirkes rizs, paprikas csirke, parolt rizs, porkolt, tojasos rizs
    assert ids == ["zz-csirkes-rizs", "zz-paprikas-csirke", "zz-rizs-koret", "zz-porkolt", "zz-tojasos-rizs"]
    for recipe in body["recipes"]:
        cost, cheapest, share = SUMMARIES[recipe["id"]]
        assert recipe["cost_per_serving_from"] == cost, recipe["id"]
        assert recipe["cheapest_chains"] == cheapest, recipe["id"]
        assert recipe["priced_share"] == share, recipe["id"]
    first = body["recipes"][0]
    assert first == {
        "id": "zz-csirkes-rizs",
        "title": "Csirkés rizs",
        "summary": "Szintetikus teszt: Csirkés rizs",
        "slots": ["ebed", "vacsora"],
        "servings": 4,
        "minutes": 40,
        "tags": ["foetel", "baromfi"],
        "tested": False,
        "cost_per_serving_from": 408.4,
        "cheapest_chains": ["gamma"],
        "priced_share": 1.0,
    }


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("slot=reggeli", ["zz-tojasos-rizs"]),
        ("tag=husmentes", ["zz-rizs-koret", "zz-tojasos-rizs"]),
        ("q=RIZS", ["zz-csirkes-rizs", "zz-rizs-koret", "zz-tojasos-rizs"]),
        ("q=p%C3%A1rolt", ["zz-rizs-koret"]),  # "párolt": accent-insensitive
        ("q=parolt", ["zz-rizs-koret"]),
        ("slot=ebed&tag=sertes", ["zz-porkolt"]),
        ("q=nincs+ilyen", []),
    ],
)
def test_recipe_filters(client: TestClient, query: str, expected: list[str]) -> None:
    response = client.get(f"/api/recipes?{query}")
    assert response.status_code == 200
    assert [r["id"] for r in response.json()["recipes"]] == expected


@pytest.mark.parametrize(
    ("query", "field"),
    [
        ("q=a", "query.q"),
        (f"q={'x' * 41}", "query.q"),
        ("slot=lunch", "query.slot"),
        ("tag=egeszseges", "query.tag"),
    ],
)
def test_recipe_filter_errors(client: TestClient, query: str, field: str) -> None:
    response = client.get(f"/api/recipes?{query}")
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_request", "fields": [field]}


def test_recipe_detail_with_costs_and_lines(client: TestClient) -> None:
    response = client.get("/api/recipes/zz-csirkes-rizs")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    body = response.json()
    assert body["data_date"] == "2026-10-12"
    assert body["steps"] == [seed.STEP]
    assert body["lines"] == [
        {
            "line_no": 1,
            "ingredient_id": "csirkemell",
            "ingredient_name": "csirkemell",
            "qty": 0.6,
            "unit": "kg",
            "display": "60 dkg",
            "optional": False,
            "pantry": False,
        },
        {
            "line_no": 2,
            "ingredient_id": "rizs",
            "ingredient_name": "rizs",
            "qty": 0.4,
            "unit": "kg",
            "display": "40 dkg",
            "optional": False,
            "pantry": False,
        },
        {
            "line_no": 3,
            "ingredient_id": "napraforgoolaj",
            "ingredient_name": "napraforgóolaj",
            "qty": 0.03,
            "unit": "l",
            "display": "3 ek",
            "optional": False,
            "pantry": True,
        },
        {
            "line_no": 4,
            "ingredient_id": "so",
            "ingredient_name": "só",
            "qty": 0.005,
            "unit": "kg",
            "display": "1 tk",
            "optional": False,
            "pantry": True,
        },
        {
            "line_no": 5,
            "ingredient_id": "pirospaprika",
            "ingredient_name": "pirospaprika",
            "qty": 0.005,
            "unit": "kg",
            "display": "1 tk",
            "optional": True,
            "pantry": False,
        },
    ]
    # chain-typical used cost per serving: alfa (2490 x 0.6 + 499 x 0.4) / 4 = 423.40; beta 1490 per 0.5 kg
    # = 2980/kg -> (1788 + 219.6) / 4 = 501.90; gamma (1434 + 199.6) / 4 = 408.40; the drugstore is left out
    assert body["chain_costs"] == [
        {"chain": "alfa", "cost_per_serving": 423.4, "rank": 2, "priced_share": 1.0, "missing": []},
        {"chain": "beta", "cost_per_serving": 501.9, "rank": 3, "priced_share": 1.0, "missing": []},
        {"chain": "gamma", "cost_per_serving": 408.4, "rank": 1, "priced_share": 1.0, "missing": []},
    ]
    assert body["cost_per_serving_from"] == 408.4
    assert body["nutrition"] is None  # only the rice (40 % of the mass) has composition data


def test_recipe_detail_missing_lines_null_costs_and_nutrition(client: TestClient) -> None:
    eggs = client.get("/api/recipes/zz-tojasos-rizs").json()
    assert [c["missing"] for c in eggs["chain_costs"]] == [["fahej"]] * 3
    assert [c["cost_per_serving"] for c in eggs["chain_costs"]] == [229.7, 221.23, 239.7]
    paprika = client.get("/api/recipes/zz-paprikas-csirke").json()
    # 1245 / (1245 + 40), 1490 / 1530, 1195 / 1235, rounded down to 4 decimals
    assert [c["priced_share"] for c in paprika["chain_costs"]] == [0.9688, 0.9738, 0.9676]
    pork = client.get("/api/recipes/zz-porkolt").json()
    assert pork["cost_per_serving_from"] is None
    assert pork["chain_costs"] == [
        {
            "chain": slug,
            "cost_per_serving": None,
            "rank": None,
            "priced_share": 0.0,
            "missing": ["sertescomb"],
        }
        for slug in ("alfa", "beta", "gamma")
    ]
    # rice only: 0.1 kg per serving = 100 g, so the per-serving values equal the synthetic per-100 g row
    rice = client.get("/api/recipes/zz-rizs-koret").json()
    assert rice["nutrition"] == {
        "kcal": 100.0,
        "protein_g": 10.0,
        "carb_g": 20.0,
        "sugar_g": 1.0,
        "fat_g": 2.0,
        "satfat_g": 0.5,
        "fiber_g": 3.0,
        "salt_g": 0.1,
        "coverage": 1.0,
    }


@pytest.mark.parametrize(
    "path",
    [
        "/api/recipes/nincs-ilyen",
        "/api/recipes/ZZ-PORKOLT",
        "/api/recipes/a",
        f"/api/recipes/{'a' * 61}",
        "/api/recipes/zz_porkolt",
    ],
)
def test_recipe_detail_not_found(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "fields": []}
    assert response.headers["cache-control"] == "no-store"
    assert_security_headers(response.headers)


def test_history(client: TestClient) -> None:
    """Per chain and day the cheapest candidate's unit price; the window ends at the latest successful data
    date (the 2026-10-13 row of a run that never finished is left out) and spans ``days`` days."""
    response = client.get("/api/ingredients/rizs/history")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    alfa = [
        {"date": "2026-10-01", "unit_price": 479.0},
        {"date": "2026-10-09", "unit_price": 489.0},
        {"date": "2026-10-10", "unit_price": 440.0},  # the 5 kg pack: 2200 / 5
        {"date": "2026-10-11", "unit_price": 499.0},
        {"date": "2026-10-12", "unit_price": 499.0},
    ]
    assert response.json() == {
        "ingredient_id": "rizs",
        "unit": "kg",
        "days": 30,
        "series": [
            {"chain": "alfa", "points": alfa},
            {"chain": "beta", "points": [{"date": "2026-10-12", "unit_price": 549.0}]},
            {"chain": "delta", "points": [{"date": "2026-10-12", "unit_price": 650.0}]},
            {
                "chain": "gamma",
                "points": [
                    {"date": "2026-10-11", "unit_price": 519.0},
                    {"date": "2026-10-12", "unit_price": 499.0},
                ],
            },
        ],
    }
    week = client.get("/api/ingredients/rizs/history?days=7&chain=alfa").json()
    assert week["days"] == 7
    assert week["series"] == [{"chain": "alfa", "points": alfa[1:]}]
    salt = client.get("/api/ingredients/so/history").json()
    assert salt["series"] == []  # no GVH mapping


@pytest.mark.parametrize(
    ("path", "status", "fields"),
    [
        ("/api/ingredients/nincs/history", 404, []),
        ("/api/ingredients/RIZS/history", 404, []),
        ("/api/ingredients/rizs/history?chain=zeta", 422, ["query.chain"]),
        ("/api/ingredients/rizs/history?chain=Alfa!", 422, ["query.chain"]),
        ("/api/ingredients/rizs/history?days=6", 422, ["query.days"]),
        ("/api/ingredients/rizs/history?days=366", 422, ["query.days"]),
        ("/api/ingredients/rizs/history?days=x", 422, ["query.days"]),
    ],
)
def test_history_errors(client: TestClient, path: str, status: int, fields: list[str]) -> None:
    response = client.get(path)
    assert response.status_code == status
    assert response.json()["fields"] == fields


@pytest.mark.parametrize(
    ("path", "cache_control"),
    [
        ("/api/health", "no-store"),
        ("/api/meta", "public, max-age=300"),
        ("/api/stores", "public, max-age=3600"),
        ("/api/ingredients", "public, max-age=3600"),
        ("/api/recipes", "public, max-age=300"),
        ("/api/recipes?slot=ebed", "public, max-age=300"),
        ("/api/recipes/zz-csirkes-rizs", "public, max-age=300"),
        ("/api/ingredients/rizs/history", "public, max-age=300"),
    ],
)
def test_etag_and_304(client: TestClient, path: str, cache_control: str) -> None:
    first = client.get(path)
    etag = first.headers["etag"]
    assert etag.startswith('"')
    assert etag.endswith('"')
    assert len(etag) == 66  # a strong validator: the full sha256
    assert client.get(path).headers["etag"] == etag  # stable
    for header in (etag, f"W/{etag}", f'"other", {etag}', "*"):
        cached = client.get(path, headers={"If-None-Match": header})
        assert cached.status_code == 304, header
        assert cached.content == b""
        assert cached.headers["etag"] == etag
        assert cached.headers["cache-control"] == cache_control
        assert_security_headers(cached.headers)
    fresh = client.get(path, headers={"If-None-Match": '"something-else"'})
    assert fresh.status_code == 200
    assert fresh.content == first.content


def test_etags_differ_between_representations(client: TestClient) -> None:
    tags = {client.get(p).headers["etag"] for p in ("/api/recipes", "/api/recipes?slot=ebed", "/api/stores")}
    assert len(tags) == 3


# ───────────────────────────── POST /api/list ─────────────────────────────


def test_list(client: TestClient) -> None:
    """zz-csirkes-rizs for 2 (x 0.5) + zz-rizs-koret for 4 (x 2), 0.1 kg rice at home, optional lines out:
    chicken 0.3; rice 0.2 + 0.4 - 0.1 = 0.5; oil 0.015; salt 0.0025 -> 0.003 (half-up). Sorted by list group
    (hus_hal, szaraz_tartos, fuszer_olaj), then folded name."""
    response = client.post(
        "/api/list",
        json={
            "items": [
                {"recipe_id": "zz-csirkes-rizs", "servings": 2},
                {"recipe_id": "zz-rizs-koret", "servings": 4},
            ],
            "on_hand": [{"ingredient_id": "rizs", "qty": 0.1}],
            "include_optional": False,
        },
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "lines": [
            {
                "ingredient_id": "csirkemell",
                "name_hu": "csirkemell",
                "qty": 0.3,
                "unit": "kg",
                "list_group": "hus_hal",
                "pantry": False,
                "recipe_ids": ["zz-csirkes-rizs"],
            },
            {
                "ingredient_id": "rizs",
                "name_hu": "rizs",
                "qty": 0.5,
                "unit": "kg",
                "list_group": "szaraz_tartos",
                "pantry": False,
                "recipe_ids": ["zz-csirkes-rizs", "zz-rizs-koret"],
            },
            {
                "ingredient_id": "napraforgoolaj",
                "name_hu": "napraforgóolaj",
                "qty": 0.015,
                "unit": "l",
                "list_group": "fuszer_olaj",
                "pantry": True,
                "recipe_ids": ["zz-csirkes-rizs"],
            },
            {
                "ingredient_id": "so",
                "name_hu": "só",
                "qty": 0.003,
                "unit": "kg",
                "list_group": "fuszer_olaj",
                "pantry": True,
                "recipe_ids": ["zz-csirkes-rizs"],
            },
        ]
    }


def test_list_optional_lines_and_on_hand_removal(client: TestClient) -> None:
    response = client.post(
        "/api/list",
        json={
            "items": [{"recipe_id": "zz-csirkes-rizs", "servings": 4}],
            "on_hand": [{"ingredient_id": "rizs", "qty": 0.3}, {"ingredient_id": "rizs", "qty": 0.1}],
        },
    )
    assert response.status_code == 200
    lines = {line["ingredient_id"]: line["qty"] for line in response.json()["lines"]}
    # rice 0.4 - (0.3 + 0.1) = 0: removed; the optional paprika is in by default
    assert lines == {"csirkemell": 0.6, "napraforgoolaj": 0.03, "pirospaprika": 0.005, "so": 0.005}


def test_list_unknown_ids(client: TestClient) -> None:
    response = client.post(
        "/api/list",
        json={
            "items": [
                {"recipe_id": "zz-porkolt", "servings": 1},
                {"recipe_id": "nincs-ilyen", "servings": 1},
            ],
            "on_hand": [{"ingredient_id": "nincs_ilyen", "qty": 1}],
        },
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": "invalid_request",
        "fields": ["items.1.recipe_id", "on_hand.0.ingredient_id"],
    }


# ───────────────────────────── POST /api/quote ─────────────────────────────

QUOTE_1 = {
    "lines": [
        {"ingredient_id": "csirkemell", "qty": 1.2},
        {"ingredient_id": "tojas", "qty": 12},
        {"ingredient_id": "rizs", "qty": 0.5},
        {"ingredient_id": "napraforgoolaj", "qty": 0.2},
        {"ingredient_id": "so", "qty": 0.01},
        {"ingredient_id": "pirospaprika", "qty": 0.02},
        {"ingredient_id": "fahej", "qty": 0.005},
    ],
    "store_ids": ["alfa-1", "beta-1", "beta-2", "gamma-1"],
}


def _option(
    pid: str,
    name: str,
    size: float | None,
    price: float,
    unit: float,
    ptype: str = "NORMAL",
    scope: str = "chain",
    availability: str = "assumed",
) -> dict[str, Any]:
    return {
        "product_id": pid,
        "product_name": name,
        "pack_size": size,
        "pack_price": price,
        "unit_price": unit,
        "price_type": ptype,
        "price_scope": scope,
        "availability": availability,
    }


CSM_A_ALFA = _option("zz-p-csm-a", "FRISS CSIRKEMELL FILE PULTOS", None, 2490.0, 2490.0)
CSM_B_ALFA = _option("zz-p-csm-b", "Csirkemellfilé tálcás 500 g", 0.5, 1390.0, 2780.0)
TOJAS10_ALFA = _option("zz-p-tojas-10", "Tojás M 10 db", 10.0, 899.0, 89.9)
RIZS_ALFA = _option("zz-p-rizs-1", "Rizs 1 kg", 1.0, 499.0, 499.0, availability="confirmed")
OLAJ_ALFA = _option("zz-p-olaj-1", "Napraforgóolaj 1 l", 1.0, 799.0, 799.0)


def _priced(
    ing: str,
    qty: float,
    unit: str,
    picks: list[tuple[dict[str, Any], int, float, float]],
    checkout: float,
    used: float,
    leftover: float,
    alternatives: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ingredient_id": ing,
        "qty": qty,
        "unit": unit,
        "status": "priced",
        "picks": [{"option": o, "count": c, "qty": q, "cost": cost} for o, c, q, cost in picks],
        "checkout_cost": checkout,
        "used_cost": used,
        "leftover_qty": leftover,
        "ksh_estimate": None,
        "alternatives": alternatives or [],
    }


def _other(ing: str, qty: float, status: str, ksh: float | None = None) -> dict[str, Any]:
    return {
        "ingredient_id": ing,
        "qty": qty,
        "unit": "l" if ing == "napraforgoolaj" else "kg",
        "status": status,
        "picks": [],
        "checkout_cost": None,
        "used_cost": None,
        "leftover_qty": None,
        "ksh_estimate": ksh,
        "alternatives": [],
    }


def test_quote_full_response(client: TestClient) -> None:
    response = client.post("/api/quote", json=QUOTE_1)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert_security_headers(response.headers)
    body = response.json()
    assert body["data_date"] == "2026-10-12"
    assert body["scope_note_hu"] == "a kiválasztott boltok közül, a 2026-10-12-i GVH-adatok alapján"
    assert body["scope_note_en"] == "among the selected stores, based on GVH data of 2026-10-12"
    assert body["attribution"]["gvh"]["text_hu"] == "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), 2026-10-12"
    assert body["attribution"]["ksh"]["text_hu"] == "Forrás: KSH"
    stores = {s["store_id"]: s for s in body["stores"]}
    assert list(stores) == QUOTE_1["store_ids"]  # request order

    alfa = stores["alfa-1"]
    assert alfa["chain"] == "alfa"
    assert alfa["lines"] == [
        _priced("csirkemell", 1.2, "kg", [(CSM_A_ALFA, 1, 1.2, 2988.0)], 2988.0, 2988.0, 0.0, [CSM_B_ALFA]),
        _priced("tojas", 12.0, "db", [(TOJAS10_ALFA, 2, 20.0, 1798.0)], 1798.0, 1078.8, 8.0),
        _priced("rizs", 0.5, "kg", [(RIZS_ALFA, 1, 1.0, 499.0)], 499.0, 249.5, 0.5),
        _priced("napraforgoolaj", 0.2, "l", [(OLAJ_ALFA, 1, 1.0, 799.0)], 799.0, 159.8, 0.8),
        _other("so", 0.01, "pantry"),
        _other("pirospaprika", 0.02, "ksh_estimate", 80.0),  # 0.02 kg x 4000 Ft/kg (KSH)
        _other("fahej", 0.005, "unpriced"),
    ]
    assert (alfa["checkout_total"], alfa["used_total"], alfa["missing"]) == (6084.0, 4476.1, [])
    assert (alfa["assumed_count"], alfa["ksh_estimate_total"]) == (3, 80.0)

    beta1 = stores["beta-1"]
    csm_b_store = _option(
        "zz-p-csm-b", "Csirkemellfilé tálcás 500 g", 0.5, 1290.0, 2580.0, "DISCOUNTED", "store", "confirmed"
    )
    tojas6 = _option("zz-p-tojas-6", "Tojás L 6 db", 6.0, 499.0, 83.17, availability="confirmed")
    tojas10_beta = _option("zz-p-tojas-10", "Tojás M 10 db", 10.0, 999.0, 99.9)
    assert beta1["lines"][0] == _priced(
        "csirkemell", 1.2, "kg", [(csm_b_store, 3, 1.5, 3870.0)], 3870.0, 3096.0, 0.3
    )
    assert beta1["lines"][1] == _priced(
        "tojas", 12.0, "db", [(tojas6, 2, 12.0, 998.0)], 998.0, 998.0, 0.0, [tojas10_beta]
    )
    assert beta1["lines"][3] == _other("napraforgoolaj", 0.2, "unavailable")
    assert (beta1["checkout_total"], beta1["used_total"], beta1["missing"]) == (
        5417.0,
        4368.5,
        ["napraforgoolaj"],
    )
    assert beta1["assumed_count"] == 1  # only the rice

    beta2 = stores["beta-2"]
    csm_b_chain = _option("zz-p-csm-b", "Csirkemellfilé tálcás 500 g", 0.5, 1490.0, 2980.0)
    assert beta2["lines"][0]["picks"][0] == {"option": csm_b_chain, "count": 3, "qty": 1.5, "cost": 4470.0}
    assert beta2["lines"][1]["picks"][0]["option"]["product_id"] == "zz-p-tojas-10"  # 6-pack not listed here
    assert (beta2["checkout_total"], beta2["used_total"], beta2["assumed_count"]) == (7017.0, 5049.3, 3)

    gamma = stores["gamma-1"]
    assert gamma["lines"][1]["picks"][0]["option"]["price_type"] == "DISCOUNTED"
    assert (gamma["checkout_total"], gamma["used_total"], gamma["missing"]) == (6014.0, 4406.1, [])

    assert body["ranking"] == [
        {
            "store_id": "gamma-1",
            "rank": 1,
            "checkout_total": 6014.0,
            "penalized_total": 6014.0,
            "missing_count": 0,
        },
        {
            "store_id": "alfa-1",
            "rank": 2,
            "checkout_total": 6084.0,
            "penalized_total": 6084.0,
            "missing_count": 0,
        },
        {
            "store_id": "beta-1",
            "rank": 3,
            "checkout_total": 5417.0,
            "penalized_total": 6191.0,
            "missing_count": 1,
        },
        {
            "store_id": "beta-2",
            "rank": 4,
            "checkout_total": 7017.0,
            "penalized_total": 7791.0,
            "missing_count": 1,
        },
    ]
    assert body["split"] is None


def test_quote_two_store_split(client: TestClient) -> None:
    """10 kg chicken + 150 eggs: beta-1 25,800 + 12,475 (25 six-packs) = 38,275; gamma-1 23,900 + 14,235 =
    38,135. Chicken at gamma + eggs at beta = 36,375, saving 1,760 >= 1,500."""
    response = client.post(
        "/api/quote",
        json={
            "lines": [{"ingredient_id": "csirkemell", "qty": 10}, {"ingredient_id": "tojas", "qty": 150}],
            "store_ids": ["beta-1", "gamma-1"],
        },
    )
    body = response.json()
    assert [(r["store_id"], r["rank"], r["checkout_total"]) for r in body["ranking"]] == [
        ("gamma-1", 1, 38135.0),
        ("beta-1", 2, 38275.0),
    ]
    assert body["split"] == {
        "store_ids": ["gamma-1", "beta-1"],
        "total": 36375.0,
        "saving": 1760.0,
        "assignment": {"csirkemell": "gamma-1", "tojas": "beta-1"},
    }


def test_quote_ties_share_a_rank(client: TestClient) -> None:
    response = client.post(
        "/api/quote",
        json={"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": ["beta-2", "alfa-1", "beta-1"]},
    )
    ranking = [(r["store_id"], r["rank"], r["penalized_total"]) for r in response.json()["ranking"]]
    assert ranking == [("alfa-1", 1, 499.0), ("beta-1", 2, 549.0), ("beta-2", 2, 549.0)]


def test_quote_loyalty_only_on_request(client: TestClient) -> None:
    request = {"lines": [{"ingredient_id": "napraforgoolaj", "qty": 1}], "store_ids": ["gamma-1"]}
    plain = client.post("/api/quote", json=request).json()["stores"][0]["lines"][0]
    assert (plain["checkout_cost"], plain["picks"][0]["option"]["price_type"]) == (749.0, "NORMAL")
    loyal = client.post("/api/quote", json={**request, "include_loyalty": True}).json()["stores"][0]["lines"][
        0
    ]
    assert (loyal["checkout_cost"], loyal["picks"][0]["option"]["price_type"]) == (699.0, "LOYALTY")


def test_quote_store_without_data(client: TestClient) -> None:
    """gamma-2 has no data on the latest date: every GVH line is unavailable there (never a chain price)."""
    response = client.post(
        "/api/quote",
        json={
            "lines": [{"ingredient_id": "rizs", "qty": 1}, {"ingredient_id": "so", "qty": 0.01}],
            "store_ids": ["gamma-2"],
        },
    )
    store = response.json()["stores"][0]
    assert [line["status"] for line in store["lines"]] == ["unavailable", "pantry"]
    assert (store["checkout_total"], store["missing"]) == (0.0, ["rizs"])


def test_quote_quantities_are_rounded_half_up(client: TestClient) -> None:
    response = client.post(
        "/api/quote",
        json={"lines": [{"ingredient_id": "csirkemell", "qty": 1.0005}], "store_ids": ["alfa-1"]},
    )
    line = response.json()["stores"][0]["lines"][0]
    assert (line["qty"], line["checkout_cost"]) == (1.001, 2492.49)  # 1.001 x 2490 = 2492.49


@pytest.mark.parametrize(
    ("body", "fields"),
    [
        (
            {"lines": [{"ingredient_id": "nincs_ilyen", "qty": 1}], "store_ids": ["alfa-1", "nincs-1"]},
            ["lines.0.ingredient_id", "store_ids.1"],
        ),
        (
            {
                "lines": [{"ingredient_id": "rizs", "qty": 1}, {"ingredient_id": "rizs", "qty": 2}],
                "store_ids": ["alfa-1"],
            },
            ["body"],
        ),
        ({"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": ["alfa-1", "alfa-1"]}, ["body"]),
        ({"lines": [], "store_ids": ["alfa-1"]}, ["lines"]),
        ({"lines": [{"ingredient_id": "rizs", "qty": 0}], "store_ids": ["alfa-1"]}, ["lines.0.qty"]),
        ({"lines": [{"ingredient_id": "rizs", "qty": 1000.001}], "store_ids": ["alfa-1"]}, ["lines.0.qty"]),
        (
            {"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": [f"s{i}" for i in range(26)]},
            ["store_ids"],
        ),
        ({"lines": [{"ingredient_id": "rizs", "qty": 1}]}, ["store_ids"]),
        ({"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": ["alfa-1"], "lat": 47.5}, ["body"]),
    ],
)
def test_quote_validation(client: TestClient, body: dict[str, Any], fields: list[str]) -> None:
    response = client.post("/api/quote", json=body)
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_request", "fields": fields}
    assert response.headers["cache-control"] == "no-store"
    assert_security_headers(response.headers)


# ───────────────────────────── /api/plan ─────────────────────────────


def test_plan_suggest_matches_the_planner(
    client: TestClient, api: tuple[TestClient, CatalogueProvider]
) -> None:
    request = {"days": 7, "slots": 3, "people": 2, "seed": 42}
    response = client.post("/api/plan/suggest", json=request)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert client.post("/api/plan/suggest", json=request).json() == body  # same seed and input, same plan
    cat = api[1].snapshot().catalogue
    plan = suggest_plan(
        list(cat.recipes.values()), cat.ingredients, PlanRequest(days=7, slots=SLOTS_3, people=2, seed=42)
    )
    assert body["days"] == [{"index": d.index, "meals": dict(d.meals)} for d in plan.days]
    assert body["warnings"] == list(plan.warnings)
    assert "no_fish_recipe_available" in body["warnings"]  # the synthetic library has no "hal" recipe
    assert "no_legume_recipe_available" in body["warnings"]
    assert [d["index"] for d in body["days"]] == list(range(7))
    pools = {slot: {r.id for r in cat.recipes.values() if slot in r.slots} for slot in SLOTS_3}
    for day in body["days"]:
        assert set(day["meals"]) == set(SLOTS_3)
        for slot, recipe_id in day["meals"].items():
            assert recipe_id is None or recipe_id in pools[slot]
    assert {c["rule"] for c in body["checks"]} == {
        "fish",
        "legume",
        "meat_free_day",
        "red_meat",
        "potato",
        "sweets",
        "variety",
    }


def test_plan_suggest_exclusions_and_budget(client: TestClient) -> None:
    body = client.post(
        "/api/plan/suggest",
        json={
            "days": 7,
            "slots": 5,
            "exclude_tags": ["baromfi"],
            "exclude_ingredients": ["zz_nincs_ilyen"],
            "weekly_budget": 20000,
            "seed": 7,
        },
    ).json()
    used = {r for d in body["days"] for r in d["meals"].values() if r is not None}
    assert used.isdisjoint({"zz-csirkes-rizs", "zz-paprikas-csirke"})
    assert all(set(d["meals"]) == {"reggeli", "tizorai", "ebed", "uzsonna", "vacsora"} for d in body["days"])
    assert "slot_pool_empty:tizorai" in body["warnings"]
    budget = [c for c in body["checks"] if c["rule"] == "budget"]
    assert len(budget) == 1
    assert budget[0]["limit"] == "≤ 20000 Ft"


def test_plan_check(client: TestClient) -> None:
    """One day, 2 people: the pork recipe has 0.8 kg red meat for 4 servings = 200 g per person (limit for one
    day 600 x 1 // 7 = 85 g); budget: zz-csirkes-rizs costs 408.40 per serving x 2 = 816.80 -> 817 Ft, the
    pork has no estimate, limit 1000 x 1 // 7 = 142 Ft."""
    response = client.post(
        "/api/plan/check",
        json={
            "days": [{"index": 0, "meals": {"ebed": "zz-porkolt", "vacsora": "zz-csirkes-rizs"}}],
            "people": 2,
            "weekly_budget": 1000,
        },
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "checks": [
            {"week": 0, "rule": "fish", "ok": True, "value": "n/a", "limit": "≥ 1"},
            {"week": 0, "rule": "legume", "ok": True, "value": "n/a", "limit": "≥ 1"},
            {"week": 0, "rule": "meat_free_day", "ok": True, "value": "n/a", "limit": "≥ 1"},
            {"week": 0, "rule": "red_meat", "ok": False, "value": "200 g/fő", "limit": "≤ 85 g/fő"},
            {
                "week": 0,
                "rule": "potato",
                "ok": True,
                "value": "0 nap egymás után",
                "limit": "≤ 1 nap egymás után",
            },
            {"week": 0, "rule": "sweets", "ok": True, "value": "0 édes", "limit": "≤ 2"},
            {
                "week": 0,
                "rule": "variety",
                "ok": True,
                "value": "0 ismétlés",
                "limit": "0 ismétlés 5 napon belül",
            },
            {
                "week": 0,
                "rule": "budget",
                "ok": False,
                "value": "817 Ft + 1 ár nélküli étel",
                "limit": "≤ 142 Ft",
            },
        ]
    }


def test_plan_check_variety_window(client: TestClient) -> None:
    days = [{"index": i, "meals": {"ebed": "zz-rizs-koret"}} for i in (0, 2)]
    strict = client.post("/api/plan/check", json={"days": days, "no_repeat_days": 5}).json()["checks"]
    loose = client.post("/api/plan/check", json={"days": days, "no_repeat_days": 2}).json()["checks"]
    assert [c["ok"] for c in strict if c["rule"] == "variety"] == [False]
    assert [c["ok"] for c in loose if c["rule"] == "variety"] == [True]


@pytest.mark.parametrize(
    ("days", "fields"),
    [
        ([{"index": 0, "meals": {"ebed": "nincs-ilyen"}}], ["days.0.meals.ebed"]),
        ([{"index": 0, "meals": {}}, {"index": 0, "meals": {"vacsora": "zz-porkolt"}}], ["days.1.index"]),
        ([{"index": 31, "meals": {}}], ["days.0.index"]),
        ([{"index": 0, "meals": {"brunch": "zz-porkolt"}}], ["days.0.meals"]),
        ([{"index": 0, "meals": {"ebed": "ZZ"}}], ["days.0.meals.ebed"]),
        ([], ["days"]),
    ],
)
def test_plan_check_validation(client: TestClient, days: list[Any], fields: list[str]) -> None:
    response = client.post("/api/plan/check", json={"days": days})
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_request", "fields": fields}


# ───────────────────────────── errors and headers ─────────────────────────────


@pytest.mark.parametrize(
    ("method", "path", "allow"),
    [
        ("PUT", "/api/quote", "POST"),
        ("GET", "/api/quote", "POST"),
        ("DELETE", "/api/stores", "GET"),
        ("POST", "/api/stores", "GET"),
        ("PATCH", "/api/recipes/zz-porkolt", "GET"),
        ("OPTIONS", "/api/meta", "GET"),
    ],
)
def test_method_not_allowed(client: TestClient, method: str, path: str, allow: str) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 405
    assert response.json() == {"error": "method_not_allowed", "fields": []}
    assert response.headers["allow"] == allow
    assert "access-control-allow-origin" not in response.headers  # no CORS unless configured
    assert_security_headers(response.headers)


@pytest.mark.parametrize("path", ["/api/nope", "/api", "/api/", "/api/stores/", "/", "/index.html", "/terv"])
def test_not_found_without_web_build(client: TestClient, path: str) -> None:
    for method in ("GET", "POST"):
        response = client.request(method, path)
        assert response.status_code == 404, (method, path)
        assert response.json() == {"error": "not_found", "fields": []}
        assert response.headers["content-type"] == "application/json; charset=utf-8"
        assert_security_headers(response.headers)


def test_payload_too_large_before_parsing(client: TestClient) -> None:
    body = b'{"lines": [' + b" " * 70_000 + b"]}"
    response = client.post("/api/quote", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.json() == {"error": "payload_too_large", "fields": []}
    assert_security_headers(response.headers)
    exact = b'{"x":"' + b"a" * (65_536 - 8) + b'"}'
    assert len(exact) == 65_536
    at_limit = client.post("/api/quote", content=exact, headers={"Content-Type": "application/json"})
    assert at_limit.status_code == 422  # read and parsed: the limit itself is allowed


@pytest.mark.parametrize(
    "content_type",
    [
        None,
        "text/plain",
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=x",
        "application/json; charset=latin-1",
        "application/jsonx",
        "application/vnd.api+json",
    ],
)
def test_unsupported_media_type(client: TestClient, content_type: str | None) -> None:
    headers = {} if content_type is None else {"Content-Type": content_type}
    response = client.post("/api/quote", content=b'{"lines": []}', headers=headers)
    assert response.status_code == 415
    assert response.json() == {"error": "unsupported_media_type", "fields": []}
    assert_security_headers(response.headers)


@pytest.mark.parametrize(
    "content_type", ["application/json", "Application/JSON; charset=UTF-8", "application/json;charset=utf8"]
)
def test_json_content_types_accepted(client: TestClient, content_type: str) -> None:
    response = client.post(
        "/api/plan/check",
        content=b'{"days": [{"index": 0, "meals": {}}]}',
        headers={"Content-Type": content_type},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/quote", {"lines": [{"ingredient_id": SENTINEL, "qty": 1}], "store_ids": [SENTINEL]}),
        ("/api/quote", {"lines": [{"ingredient_id": "rizs", "qty": SENTINEL}], "store_ids": ["alfa-1"]}),
        ("/api/quote", {SENTINEL: SENTINEL, "lines": [], "store_ids": []}),
        (
            "/api/quote",
            {"lines": [{"ingredient_id": "rizs", "qty": 1, SENTINEL: 1}], "store_ids": ["alfa-1"]},
        ),
        ("/api/list", {"items": [{"recipe_id": SENTINEL.lower(), "servings": 1}]}),
        ("/api/list", {"items": [{"recipe_id": "zz-porkolt", "servings": f"1{SENTINEL}"}]}),
        ("/api/plan/suggest", {"exclude_tags": [SENTINEL], "days": SENTINEL}),
        ("/api/plan/check", {"days": [{"index": 0, "meals": {SENTINEL: SENTINEL}}]}),
        ("/api/plan/check", {"days": [{"index": 0, "meals": {"ebed": SENTINEL.lower()}}]}),
    ],
)
def test_422_never_echoes_input(client: TestClient, path: str, body: dict[str, Any]) -> None:
    response = client.post(path, json=body)
    assert response.status_code == 422
    assert set(response.json()) == {"error", "fields"}
    assert response.json()["error"] == "invalid_request"
    assert SENTINEL.lower() not in response.text.lower()


def test_rate_limit_429(cluster: PgCluster) -> None:
    """Default limit: 120/min with a burst of 30 per client; the 31st immediate request is refused."""
    settings = seed.api_settings(cluster.settings(), api_rate_limit_per_minute=120)
    with seed.client_for(settings) as (client, _):
        clock = seed.FakeClock()
        client.app.state.rate_limiter.clock = clock  # type: ignore[attr-defined]  # frozen: no refill
        statuses = [client.get("/api/health").status_code for _ in range(30)]
        assert statuses == [200] * 30
        refused = client.get("/api/stores")
        assert refused.status_code == 429
        assert refused.json() == {"error": "rate_limited", "fields": []}
        assert refused.headers["retry-after"] == "1"  # 2 tokens per second
        assert_security_headers(refused.headers)
        other_client = client.get("/api/health", headers={"X-Forwarded-For": "203.0.113.9"})
        assert other_client.status_code == 429  # proxy headers are not trusted by default
        clock.advance(0.5)  # 120/min = 2 tokens per second: one token back
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health").status_code == 429


def test_cors_only_when_configured(cluster: PgCluster) -> None:
    settings = seed.api_settings(cluster.settings(), allowed_origins=["https://app.example"])
    with seed.client_for(settings) as (client, _):
        response = client.get("/api/health", headers={"Origin": "https://app.example"})
        assert response.headers["access-control-allow-origin"] == "https://app.example"
        preflight = client.options(
            "/api/quote",
            headers={
                "Origin": "https://app.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert preflight.status_code == 200
        assert_security_headers(preflight.headers)
        stranger = client.get("/api/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in stranger.headers


def test_hsts_when_enabled(cluster: PgCluster) -> None:
    settings = seed.api_settings(cluster.settings(), hsts=True)
    with seed.client_for(settings) as (client, _):
        for path in ("/api/health", "/api/nope"):
            assert (
                client.get(path).headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
            )


def test_health_down_when_database_unreachable(cluster: PgCluster) -> None:
    settings = seed.api_settings(cluster.settings(), db_port=free_port(), db_host="127.0.0.1")
    with seed.client_for(settings) as (client, _):
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json() == {"status": "down", "db": False, "data_date": None}
        assert response.headers["cache-control"] == "no-store"
        assert_security_headers(response.headers)
        stores = client.get("/api/stores")  # nothing cached and no database: no data
        assert stores.status_code == 503
        assert stores.json() == {"error": "no_data", "fields": []}


def test_numbers_are_json_numbers_with_bounded_decimals(client: TestClient) -> None:
    text = client.post("/api/quote", json=QUOTE_1).text

    def walk(value: Any) -> Iterator[float]:
        if isinstance(value, dict):
            for item in value.values():
                yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, float):
            yield value

    for number in walk(json.loads(text)):
        assert Decimal(repr(number)) == Decimal(repr(number)).quantize(Decimal("0.001"))
    assert not re.search(r"\d\.\d{4,}", text)
    assert "NaN" not in text
    assert "Infinity" not in text


def test_data_date_window(client: TestClient) -> None:
    """The history window is anchored on the latest successful data date, not on the wall clock."""
    days = client.get("/api/ingredients/rizs/history?days=7").json()["series"][0]["points"]
    assert date.fromisoformat(days[0]["date"]) >= seed.DATA_DATE - timedelta(days=6)


def test_python_m_bpf_api_serves_with_its_own_pool(cluster: PgCluster, tmp_path: Path) -> None:
    """The real entry point: uvicorn on 127.0.0.1, settings from BPF_ENV_FILE, the lifespan opening a bpf_api
    pool, no Server header, the security headers, and a clean shutdown."""
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("BPF_")}
    env.update(BPF_ENV_FILE=str(cluster.env_file), BPF_WEB_BUILD_DIR=str(tmp_path / "no-build"))
    proc = subprocess.Popen(  # noqa: S603 - fixed argv
        [sys.executable, "-m", "bpf.api", "--port", str(port), "--log-level", "warning"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        response = None
        while time.monotonic() < deadline:
            try:
                response = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2)
                break
            except httpx.TransportError:
                time.sleep(0.2)
        assert response is not None, "the server did not start"
        assert response.status_code == 200
        body = response.json()
        assert (body["db"], body["data_date"]) == (True, "2026-10-12")
        assert "server" not in response.headers
        assert response.headers["x-frame-options"] == "DENY"
        stores = httpx.get(f"http://127.0.0.1:{port}/api/stores", timeout=5)
        assert len(stores.json()["stores"]) == 6
        assert httpx.get(f"http://127.0.0.1:{port}/", timeout=5).status_code == 404  # no web build: API only
    finally:
        proc.send_signal(signal.SIGINT)
        output, _ = proc.communicate(timeout=30)
    assert proc.returncode == 0, output
    assert "Traceback" not in output


def test_python_m_bpf_api_logs_no_websocket_client_address(cluster: PgCluster, tmp_path: Path) -> None:
    """The access log is off because it would record client IPs; uvicorn's WebSocket rejection would still
    log '<client> - "WebSocket <path?query>" 403' at INFO (the default level of run-api.sh), with the real
    client address behind the proxy. ``python -m bpf.api`` turns WebSockets off, so such a request is
    ordinary HTTP: answered with the security headers, and logged without an address or the query."""
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("BPF_")}
    env.update(
        BPF_ENV_FILE=str(cluster.env_file),
        BPF_WEB_BUILD_DIR=str(tmp_path / "no-build"),
        BPF_TRUST_PROXY_HEADERS="true",
    )
    proc = subprocess.Popen(  # noqa: S603 - fixed argv
        [sys.executable, "-m", "bpf.api", "--port", str(port), "--log-level", "info"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2)
                break
            except httpx.TransportError:
                assert time.monotonic() < deadline, "the server did not start"
                time.sleep(0.2)
        response = httpx.get(
            f"http://127.0.0.1:{port}/api/health?marker=zz9wsmarker",
            headers={
                "Connection": "Upgrade",
                "Upgrade": "websocket",
                "Sec-WebSocket-Version": "13",
                "Sec-WebSocket-Key": "c3ludGhldGljLWtleS0xNg==",
                "X-Forwarded-For": "203.0.113.77",
            },
            timeout=5,
        )
        assert response.status_code == 200  # not 101, not uvicorn's bare 403
        for name, value in SECURITY_HEADERS.items():
            assert response.headers[name] == value, name
    finally:
        proc.send_signal(signal.SIGINT)
        output, _ = proc.communicate(timeout=30)
    assert proc.returncode == 0, output
    assert "Application startup complete" in output  # INFO lines are in the output
    assert "203.0.113.77" not in output
    assert "zz9wsmarker" not in output
    assert "WebSocket /" not in output
