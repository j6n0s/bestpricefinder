"""Full-stack API check (docs/E2E.md): the real stack up to the API, then the public API over real HTTP.

The ``stack`` fixture is :class:`tests.fullstack.FullStack`: a throwaway cluster from
``deploy/local/db-init.sh``, the fake GVH over HTTP (the REAL store list; SYNTHETIC products and prices, test
data only), the real ingest CLI (``reference``, ``daily``, ``availability``), the real content loader
(``data/``) and the real API (``python -m bpf.api``) serving ``web/build``. Nothing inside our system is
mocked. It takes about 4 minutes, because the ingest keeps its politeness floor of one request per second.

Skipped automatically when ``node`` or the web build is missing (``cd web && npm run build``), and, like every
``db`` test, when no PostgreSQL >= 16 is installed. The browser half is ``cd web && npm run test:fullstack``.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.fakegvh import NO_DATA_STORES, STORES_CSV, VALID_UNITS
from tests.fullstack import FullStack
from tests.fullstack.stack import CONTACT_EMAIL, DEFAULT_WEB_BUILD, INGREDIENTS_JSON, REPO_ROOT
from tests.pgcluster import PgUnavailable

pytestmark = pytest.mark.db

#: Nyugati tér (BUILD-BRIEF §10 test point) and the nearest real store of five grocery chains (research store
#: list): 30 m to 1 km away, all within the app's default 1.5 km radius.
NYUGATI = (47.5103, 19.0558)
NYUGATI_STORES = ("spar-8251", "tesco-4062", "lidl-274", "aldi-J067", "penny-293")
DISCLAIMER_HU = "Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal."
GROCERY = {"aldi", "auchan", "lidl", "penny", "spar", "tesco"}
HAS_DATA_WINDOW_DAYS = 8  # docs/ENGINE.md Store.has_data
RADIUS_KM = 1.5  # the app's default search radius
KSH_CSV = REPO_ROOT / "data" / "ksh" / "ara0044.csv"


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[FullStack]:
    if shutil.which("node") is None:
        pytest.skip("needs node: the full-stack suite serves the web build (docs/E2E.md)")
    if not (DEFAULT_WEB_BUILD / "index.html").is_file():
        pytest.skip("needs the web build: cd web && npm run build (docs/E2E.md)")
    stack = FullStack(run_dir=tmp_path_factory.mktemp("fullstack"), web_build=DEFAULT_WEB_BUILD)
    try:
        stack.start()  # tears itself down when a step fails
    except PgUnavailable as exc:
        pytest.skip(f"needs PostgreSQL >= 16: {exc}")
    try:
        yield stack
    finally:
        stack.close()
    assert stack.clean, f"teardown not clean: {stack.teardown_errors}"


@pytest.fixture(scope="module")
def client(stack: FullStack) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=stack.base_url, trust_env=False, timeout=30.0) as http:
        yield http


@pytest.fixture(scope="module")
def ontology(client: httpx.Client) -> dict[str, dict[str, Any]]:
    response = client.get("/api/ingredients")
    assert response.status_code == 200
    return {row["id"]: row for row in response.json()["ingredients"]}


# ───────────────────────────── the stack itself ─────────────────────────────


def test_every_step_ran_for_real_and_ended_ok(stack: FullStack) -> None:
    date = stack.data_date.isoformat()
    assert [step.name for step in stack.steps] == [
        "ingest-reference",
        "content",
        "ingest-daily",
        "ingest-availability",
    ]
    for step in stack.steps:
        assert (step.exit_code, step.status) == (0, "ok"), step
    for step, kind in zip(
        (stack.steps[0], *stack.steps[2:]), ("reference", "daily", "availability"), strict=True
    ):
        assert step.summary.startswith(f"{kind} {date}: ok (run "), step.summary
        assert step.argv[1:4] == ("-m", "bpf.ingest", kind)
        assert step.requests > 0
        # The ingest keeps its politeness floor over real HTTP. The client starts requests >= 1 s apart
        # (bpf.gvh.client); the fake's receipt times add scheduling jitter to a single gap (0.87 s was seen
        # under load) but not to the span, which only the first request's delay can shorten.
        if step.requests > 1:
            assert step.min_request_gap_s is not None
            assert step.request_span_s is not None
            assert step.request_span_s >= (step.requests - 1) * 1.0 - 0.5, step
            assert step.min_request_gap_s >= 0.5, step
    assert stack.steps[1].summary.startswith("loaded (ingest_run 2):")
    assert [(r["kind"], r["status"], r["error"]) for r in stack.runs] == [
        ("reference", "ok", None),
        ("content", "ok", None),
        ("daily", "ok", None),
        ("availability", "ok", None),
    ]
    assert [r["data_date"] for r in stack.runs if r["kind"] != "content"] == [date] * 3
    # Every request carried the descriptive User-Agent with the (non-routable) test contact.
    assert stack.fake is not None
    assert stack.fake.requests
    assert all(r.user_agent and CONTACT_EMAIL in r.user_agent for r in stack.fake.requests)
    assert len(stack.fake.requests) == sum(step.requests for step in stack.steps)


def test_state_has_no_secrets(stack: FullStack) -> None:
    assert stack.cluster is not None
    text = repr(stack.state())
    for role in ("api", "ingest", "migrator", "admin"):
        assert stack.cluster.password(role) not in text
    for log in sorted(Path(stack.log_dir).iterdir()):
        content = log.read_text(errors="replace")
        for role in ("api", "ingest", "migrator", "admin"):
            assert stack.cluster.password(role) not in content, log.name


# ───────────────────────────── the API ─────────────────────────────


def test_health_is_ok_for_the_fake_data_date(client: httpx.Client, stack: FullStack) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True, "data_date": stack.data_date.isoformat()}
    assert response.headers["cache-control"] == "no-store"


def test_meta_carries_the_fake_data_date_and_the_legal_texts(client: httpx.Client, stack: FullStack) -> None:
    meta = client.get("/api/meta").json()
    assert meta["data_date"] == stack.data_date.isoformat()
    assert meta["stale"] is False
    assert meta["disclaimer_hu"] == DISCLAIMER_HU
    assert meta["attribution"]["gvh"]["text_hu"].startswith("Forrás: GVH Árfigyelő (arfigyelo.gvh.hu)")
    assert meta["attribution"]["ksh"]["text_hu"].startswith("Forrás: KSH")
    assert {chain["slug"] for chain in meta["chains"] if chain["is_grocery"]} == GROCERY


def test_stores_are_the_real_list_and_follow_the_has_data_rule(
    client: httpx.Client, stack: FullStack
) -> None:
    assert stack.world is not None
    assert stack.cluster is not None
    body = client.get("/api/stores").json()
    assert body["data_date"] == stack.data_date.isoformat()
    stores = {store["id"]: store for store in body["stores"]}
    with STORES_CSV.open(encoding="utf-8", newline="") as handle:
        real = {row["uuid"]: row for row in csv.DictReader(handle)}
    assert set(stores) == set(real)
    for store_id, row in real.items():
        assert stores[store_id]["lat"] == pytest.approx(float(row["lat"]), abs=1e-6)
        assert stores[store_id]["lon"] == pytest.approx(float(row["lon"]), abs=1e-6)
    # An availability run finished just now, so has_data follows has_data_date (docs/ENGINE.md): the stores
    # that the fake's product details list in availableInShops (and the per-store answers) have data.
    carrying = {
        store_id
        for product in stack.world.products.values()
        if product.unit in VALID_UNITS
        for offer in product.offers
        for store_id in offer.stores
    }
    assert {sid for sid, store in stores.items() if store["has_data"]} == carrying
    assert not any(stores[sid]["has_data"] for sid in NO_DATA_STORES)
    assert all(stores[sid]["has_data"] for sid in NYUGATI_STORES)
    # ... and that is exactly the rule over the stored has_data_date.
    with stack.cluster.connect("admin") as conn:
        dates = dict(conn.execute("SELECT id, has_data_date FROM core.store").fetchall())
        finished = conn.execute(
            "SELECT data_date FROM api.ingest_latest WHERE kind = 'availability'"
        ).fetchone()
    assert finished == (stack.data_date,)
    for store_id, store in stores.items():
        has = dates[store_id]
        expected = has is not None and (stack.data_date - has).days <= HAS_DATA_WINDOW_DAYS
        assert store["has_data"] is expected, store_id


def test_a_quote_over_five_real_nyugati_stores_is_ranked(
    client: httpx.Client, stack: FullStack, ontology: dict[str, dict[str, Any]]
) -> None:
    with STORES_CSV.open(encoding="utf-8", newline="") as handle:
        real = {row["uuid"]: row for row in csv.DictReader(handle)}
    for store_id in NYUGATI_STORES:
        position = (float(real[store_id]["lat"]), float(real[store_id]["lon"]))
        assert _km(NYUGATI, position) < RADIUS_KM, store_id

    # A week's list from the real planner and list builder, as the app makes it.
    plan = client.post("/api/plan/suggest", json={"days": 7, "slots": 3, "people": 2, "seed": 0})
    assert plan.status_code == 200
    servings: dict[str, int] = {}
    for day in plan.json()["days"]:
        for recipe_id in day["meals"].values():
            assert recipe_id, "every slot is filled"
            servings[recipe_id] = servings.get(recipe_id, 0) + 2
    listed = client.post(
        "/api/list", json={"items": [{"recipe_id": r, "servings": n} for r, n in sorted(servings.items())]}
    )
    assert listed.status_code == 200
    lines = [
        {"ingredient_id": line["ingredient_id"], "qty": line["qty"]}
        for line in listed.json()["lines"]
        if not line["pantry"]
    ]
    assert lines
    request = {"lines": lines, "store_ids": list(NYUGATI_STORES)}
    response = client.post("/api/quote", json=request)
    assert response.status_code == 200, response.text
    quote = response.json()
    assert client.post("/api/quote", json=request).json() == quote  # deterministic

    date = stack.data_date.isoformat()
    assert quote["data_date"] == date
    assert quote["scope_note_hu"] == f"a kiválasztott boltok közül, a {date}-i GVH-adatok alapján"
    assert quote["attribution"]["gvh"]["text_hu"].startswith("Forrás: GVH Árfigyelő (arfigyelo.gvh.hu)")
    stores = {store["store_id"]: store for store in quote["stores"]}
    assert set(stores) == set(NYUGATI_STORES)
    requested = [line["ingredient_id"] for line in lines]
    for store in stores.values():
        assert store["chain"] == real[store["store_id"]]["chain"].lower()
        assert [line["ingredient_id"] for line in store["lines"]] == requested
        priced = [line for line in store["lines"] if line["status"] == "priced"]
        total = sum(Decimal(str(line["checkout_cost"])) for line in priced)
        assert abs(total - Decimal(str(store["checkout_total"]))) <= Decimal("0.01")
        ksh = sum(Decimal(str(line["ksh_estimate"] or 0)) for line in store["lines"])
        assert abs(ksh - Decimal(str(store["ksh_estimate_total"]))) <= Decimal("0.01")
        assert store["missing"] == [
            line["ingredient_id"] for line in store["lines"] if line["status"] == "unavailable"
        ]
        for line in store["lines"]:
            assert (line["status"] == "ksh_estimate") == (line["ksh_estimate"] is not None)
            if line["status"] == "ksh_estimate":
                assert ontology[line["ingredient_id"]]["priced_by"] == "ksh"
            for pick in line["picks"]:
                assert pick["option"]["price_scope"] in ("store", "chain")
    assert any(store["checkout_total"] > 0 for store in stores.values()), (
        "something is priced near Nyugati tér"
    )

    ranking = quote["ranking"]
    assert {entry["store_id"] for entry in ranking} == set(NYUGATI_STORES)
    assert [entry["rank"] for entry in ranking] == sorted(entry["rank"] for entry in ranking)
    for entry in ranking:
        store = stores[entry["store_id"]]
        assert entry["checkout_total"] == store["checkout_total"]
        assert entry["missing_count"] == len(store["missing"])
        assert entry["penalized_total"] >= entry["checkout_total"]
        # Competition ranking (1, 1, 3): rank r comes after exactly r - 1 stores.
        assert sum(other["rank"] < entry["rank"] for other in ranking) == entry["rank"] - 1
        for other in ranking:
            if other["rank"] == entry["rank"]:  # a tie: same whole-forint penalized total and missing count
                assert other["missing_count"] == entry["missing_count"]
                assert abs(other["penalized_total"] - entry["penalized_total"]) < 1
            elif other["rank"] < entry["rank"]:
                assert other["penalized_total"] <= entry["penalized_total"] + 0.01


def test_a_ksh_priced_line_is_a_labelled_estimate_outside_the_total(
    client: httpx.Client, ontology: dict[str, dict[str, Any]]
) -> None:
    """No recipe uses a KSH-priced ingredient, so the browser flow never meets one (docs/E2E.md); the API is
    asked directly: the estimate is the real KSH average (data/ksh) times the quantity, and stays out of the
    checkout total."""
    content = {
        row["id"]: row for row in json.loads(INGREDIENTS_JSON.read_text(encoding="utf-8"))["ingredients"]
    }
    with KSH_CSV.open(encoding="utf-8", newline="") as handle:
        ksh_rows = {row["code"]: row for row in csv.DictReader(handle)}
    ksh_ids = sorted(ingredient for ingredient, row in ontology.items() if row["priced_by"] == "ksh")
    assert ksh_ids, "the content has KSH-priced ingredients"
    gvh_ids = sorted(
        ingredient for ingredient, row in ontology.items() if row["priced_by"] == "gvh" and not row["pantry"]
    )[:8]
    qty = 0.5
    lines = [{"ingredient_id": ingredient, "qty": qty} for ingredient in (*ksh_ids, *gvh_ids)]
    response = client.post("/api/quote", json={"lines": lines, "store_ids": list(NYUGATI_STORES)})
    assert response.status_code == 200, response.text
    quote = response.json()
    assert quote["attribution"]["ksh"]["text_hu"] == "Forrás: KSH"
    assert quote["attribution"]["ksh"]["url"].startswith("https://www.ksh.hu/")
    assert quote["attribution"]["ksh"]["license"] == "CC BY 4.0"
    for store in quote["stores"]:
        by_id = {line["ingredient_id"]: line for line in store["lines"]}
        for ingredient in ksh_ids:
            line = by_id[ingredient]
            row = ksh_rows[content[ingredient]["ksh_code"]]
            assert row["unit"] == content[ingredient]["unit"], ingredient  # all kg today: no conversion
            expected = Decimal(str(qty)) * Decimal(row["price"]) / Decimal(row["unit_qty"])
            assert line["status"] == "ksh_estimate", line
            assert Decimal(str(line["ksh_estimate"])) == expected.quantize(Decimal("0.01")), ingredient
            assert line["checkout_cost"] is None
            assert line["picks"] == []
            assert ingredient not in store["missing"]
        ksh_total = sum(Decimal(str(by_id[ingredient]["ksh_estimate"])) for ingredient in ksh_ids)
        assert Decimal(str(store["ksh_estimate_total"])) == ksh_total
        priced = sum(
            Decimal(str(line["checkout_cost"])) for line in store["lines"] if line["status"] == "priced"
        )
        assert abs(Decimal(str(store["checkout_total"])) - priced) <= Decimal("0.01"), store["store_id"]


def test_the_api_takes_store_ids_never_coordinates(client: httpx.Client, ontology: dict[str, Any]) -> None:
    ingredient = next(iter(ontology))
    body = {
        "lines": [{"ingredient_id": ingredient, "qty": 1}],
        "store_ids": ["lidl-274"],
        "lat": 47.51,
        "lon": 19.05,
    }
    response = client.post("/api/quote", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert "47.51" not in response.text


def test_the_spa_html_carries_the_csp_header(client: httpx.Client) -> None:
    response = client.get("/lista")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    policy = response.headers["content-security-policy"]
    assert policy.endswith("; frame-ancestors 'none'")
    assert "default-src 'self'" in policy
    assert "unsafe-inline" not in policy
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
