"""GvhClient against the fake GVH (httpx.MockTransport) with an injected clock: paging, throttle, User-Agent,
retries, chunking, NOT-FOUND handling, schema drift, budget and the cache-busted XLSX (BUILD-BRIEF §4.1)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import httpx
import pydantic
import pytest

from bpf.gvh import (
    LISTING_LIMIT,
    SHOP_IDS_PER_CALL,
    GvhBudgetExceeded,
    GvhClient,
    GvhConfigError,
    GvhHttpError,
    GvhSchemaError,
    StaleXlsxError,
    build_user_agent,
    random_buster_suffix,
    xlsx_cache_buster,
)
from bpf.gvh import client as client_module
from bpf.gvh.xlsx import parse_daily_xlsx
from tests.fakegvh import CONTACT, FakeClock, FakeGvh, FakeResponse, build_world, fake_settings

DAY = date(2026, 10, 13)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def fake(clock: FakeClock) -> FakeGvh:
    return FakeGvh(build_world(), data_date=DAY, clock=clock.monotonic)


def make_client(transport: httpx.BaseTransport, clock: FakeClock, **kwargs: object) -> GvhClient:
    settings = kwargs.pop("settings", None) or fake_settings()
    return GvhClient(
        settings,  # type: ignore[arg-type]
        transport=transport,
        clock=clock.monotonic,
        sleep=clock.sleep,
        **kwargs,  # type: ignore[arg-type]
    )


def json_handler(route: Callable[[httpx.Request], tuple[int, object]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        status, payload = route(request)
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.MockTransport(handler)


# ───────────────────────────── listing paging (trap: default page 12, max 48) ─────────────────────────────


def test_listing_sends_limit_48_and_walks_offset_until_count(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        listing = client.products_by_category(18)
    expected_ids = {p.id for p in build_world().leaf_products(18)}
    assert listing.count == len(expected_ids) == 101
    assert {p.id for p in listing.products} == expected_ids
    assert (listing.pages, listing.missing, listing.duplicates, listing.count_changed) == (3, 0, 0, False)
    assert [(r.path, dict(r.query)) for r in fake.requests] == [
        ("/api/products-by-category/18", {"limit": "48", "offset": "0"}),
        ("/api/products-by-category/18", {"limit": "48", "offset": "48"}),
        ("/api/products-by-category/18", {"limit": "48", "offset": "96"}),
    ]


@pytest.mark.parametrize(("generic", "pages"), [(47, 1), (48, 2), (95, 2), (96, 3)])
def test_listing_page_count_at_the_boundaries(clock: FakeClock, generic: int, pages: int) -> None:
    # leaf 18 always holds one extra special product, so the count is generic + 1 (48, 49, 96, 97)
    world = build_world(overrides=((18, generic),))
    fake = FakeGvh(world, data_date=DAY)
    with make_client(fake.transport(), clock) as client:
        listing = client.products_by_category(18)
    assert listing.count == generic + 1 == len(listing.products)
    assert listing.pages == pages == len(fake.requests)
    assert [r.query["offset"] for r in fake.requests] == [str(48 * i) for i in range(pages)]
    assert all(r.query["limit"] == "48" for r in fake.requests)


def test_listing_of_an_empty_category_is_one_request(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        listing = client.products_by_category(1001)  # a top-level id: the API answers count 0
    assert (listing.count, listing.products, listing.pages) == (0, (), 1)


def test_listing_never_relies_on_the_default_page_size(fake: FakeGvh, clock: FakeClock) -> None:
    """If the server ignored limit=48 (its default page is 12), walking offset by 48 would silently skip 36 of
    every 48 rows. The client must fail loudly instead."""
    fake.ignore_limit = True
    with make_client(fake.transport(), clock) as client, pytest.raises(GvhSchemaError, match="limit=48"):
        client.products_by_category(18)
    assert len(fake.requests) == 1


def test_listing_rejects_a_page_longer_than_the_limit(clock: FakeClock) -> None:
    page = json.loads(
        FakeGvh(build_world(), data_date=DAY).respond("/api/products-by-category/18?limit=48").body
    )
    longer = {"products": page["products"] + page["products"][:1], "count": 101}
    with (
        make_client(json_handler(lambda r: (200, longer)), clock) as client,
        pytest.raises(GvhSchemaError, match="49 rows"),
    ):
        client.products_by_category(18)


def test_listing_deduplicates_products_that_shift_between_pages(clock: FakeClock) -> None:
    fake = FakeGvh(build_world(), data_date=DAY)
    first = json.loads(fake.respond("/api/products-by-category/18?limit=48&offset=0").body)["products"]

    def route(request: httpx.Request) -> tuple[int, object]:
        if request.url.params["offset"] == "0":
            return 200, {"products": first, "count": 50}
        return 200, {"products": [first[0], dict(first[0], id="x-48")], "count": 50}  # first[0] shifted

    with make_client(json_handler(route), clock) as client:
        listing = client.products_by_category(18)
    assert listing.duplicates == 1
    assert len(listing.products) == 49
    assert listing.missing == 1


def test_listing_shop_ids_filter_is_comma_joined(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        listing = client.products_by_category(18, shop_ids=["tesco-4062", "lidl-274", "tesco-4062"])
    assert fake.requests[0].query == {"limit": "48", "shopIds": "tesco-4062,lidl-274", "offset": "0"}
    names = {chain.name for product in listing.products for chain in product.pricesOfChainStores}
    assert names <= {"Tesco", "Lidl"}
    assert names
    with make_client(fake.transport(), clock) as client, pytest.raises(ValueError, match="invalid store id"):
        client.products_by_category(18, shop_ids=["tesco-4062,lidl-274"])


# ───────────────────────────── throttle and User-Agent ─────────────────────────────


def test_throttle_spaces_requests_at_least_one_second_apart(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        client.chain_stores()
        client.categories()
        client.products_by_category(18)  # 3 pages
        client.shops()
    times = [r.at for r in fake.requests]
    assert len(times) == 6
    assert all(b - a >= 1.0 for a, b in zip(times, times[1:], strict=False))  # type: ignore[operator]
    assert clock.sleeps == [1.0] * 5  # no sleep before the first request


def test_throttle_does_not_sleep_when_time_already_passed(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        client.chain_stores()
        clock.advance(0.4)
        client.chain_stores()
        clock.advance(5.0)
        client.chain_stores()
    assert clock.sleeps == [pytest.approx(0.6)]


def test_throttle_honours_a_slower_configured_interval(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock, settings=fake_settings(gvh_min_interval_s=1.5)) as client:
        client.chain_stores()
        client.chain_stores()
    assert clock.sleeps == [1.5]


def test_settings_refuse_more_than_one_request_per_second() -> None:
    with pytest.raises(pydantic.ValidationError):
        fake_settings(gvh_min_interval_s=0.5)


def test_user_agent_is_descriptive_and_carries_the_contact(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        client.chain_stores()
        assert client.user_agent == f"bestpricefinder/0.1 (+contact: {CONTACT})"
    assert fake.requests[0].user_agent == f"bestpricefinder/0.1 (+contact: {CONTACT})"


def test_user_agent_without_a_contact_is_refused() -> None:
    with pytest.raises(GvhConfigError, match="BPF_CONTACT_EMAIL"):
        build_user_agent(fake_settings(contact_email=None))
    with pytest.raises(GvhConfigError, match="not a valid"):
        build_user_agent(fake_settings(contact_email="not-an-address"))
    with pytest.raises(GvhConfigError):
        GvhClient(fake_settings(contact_email=None))


def test_user_agent_variants() -> None:
    custom = fake_settings(gvh_user_agent="myapp/2 (ops@example.net)\r\nX-Evil: 1", contact_email=None)
    assert (
        build_user_agent(custom) == "myapp/2 (ops@example.net) X-Evil: 1"
    )  # CR/LF collapsed: no header split
    both = fake_settings(
        gvh_user_agent="myapp/2 (+contact: ops@example.net)", contact_email="ops@example.net"
    )
    assert build_user_agent(both) == "myapp/2 (+contact: ops@example.net)"
    added = fake_settings(gvh_user_agent="myapp/2", contact_email="a.b@example.hu")
    assert build_user_agent(added) == "myapp/2 (+contact: a.b@example.hu)"


# ───────────────────────────── retries ─────────────────────────────


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_is_retried_with_backoff(fake: FakeGvh, clock: FakeClock, status: int) -> None:
    fake.fail("/api/chain-stores", status, times=2)
    with make_client(fake.transport(), clock) as client:
        chains = client.chain_stores()
        assert client.stats.retries == 2
        assert client.stats.requests == 3
    assert len(chains) == 9
    assert clock.sleeps == [2.0, 4.0]  # backoff; the throttle needs no extra wait after it


def test_5xx_gives_up_after_three_retries(fake: FakeGvh, clock: FakeClock) -> None:
    fake.fail("/api/chain-stores", 503, times=10)
    with make_client(fake.transport(), clock) as client, pytest.raises(GvhHttpError) as err:
        client.chain_stores()
    assert err.value.status == 503
    assert len(fake.requests) == 4
    assert clock.sleeps == [2.0, 4.0, 8.0]


def test_connection_errors_are_retried(fake: FakeGvh, clock: FakeClock) -> None:
    fake.fail("/api/categories", "connect", times=3)
    with make_client(fake.transport(), clock) as client:
        assert len(client.categories()) == 9
    assert len(fake.requests) == 4


def test_connection_errors_give_up_after_three_retries(fake: FakeGvh, clock: FakeClock) -> None:
    fake.fail("/api/categories", "connect", times=10)
    with (
        make_client(fake.transport(), clock) as client,
        pytest.raises(GvhHttpError, match="ConnectError") as err,
    ):
        client.categories()
    assert err.value.status is None
    assert len(fake.requests) == 4


def test_timeouts_are_retried(clock: FakeClock) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json=[{"uuid": "c", "name": "Lidl", "imageUrl": None}])

    with make_client(httpx.MockTransport(handler), clock) as client:
        assert [c.name for c in client.chain_stores()] == ["Lidl"]
    assert len(calls) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 429])
def test_4xx_is_never_retried(fake: FakeGvh, clock: FakeClock, status: int) -> None:
    fake.fail("/api/shops", status, times=10)
    with make_client(fake.transport(), clock) as client, pytest.raises(GvhHttpError) as err:
        client.shops()
    assert err.value.status == status
    assert err.value.code == "INJECTED-FAULT"
    assert len(fake.requests) == 1
    assert clock.sleeps == []


def test_redirects_are_not_followed(clock: FakeClock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"location": "https://elsewhere.example/api/shops"})

    with make_client(httpx.MockTransport(handler), clock) as client, pytest.raises(GvhHttpError) as err:
        client.shops()
    assert err.value.status == 301


# ───────────────────────────── per-store prices ─────────────────────────────


def test_shop_prices_are_requested_in_chunks_of_200(fake: FakeGvh, clock: FakeClock) -> None:
    world = build_world()
    product = world.special["multichain"]
    ids = list(world.chains["Spar"].stores) + list(world.chains["Tesco"].stores)
    with make_client(fake.transport(), clock) as client:
        prices = client.product_shop_prices(product, ids + ids[:10])  # duplicates are sent once
    sent = [r.path.rsplit("/", 1)[1].split(",") for r in fake.requests]
    assert [len(chunk) for chunk in sent] == [200, 200, len(ids) - 400]
    assert [s for chunk in sent for s in chunk] == ids
    assert all("%2C" in r.raw_path and "," not in r.raw_path for r in fake.requests)
    assert SHOP_IDS_PER_CALL == 200
    offers = {o.chain: o for o in world.products[product].offers}
    assert set(prices) == set(offers["Spar"].stores) | set(offers["Tesco"].stores)
    assert prices[offers["Spar"].stores[0]][0].amount == Decimal(129)


def test_shop_prices_not_found_is_empty(fake: FakeGvh, clock: FakeClock) -> None:
    product = build_world().special["spar_outlier"]  # sold only by Spar
    with make_client(fake.transport(), clock) as client:
        assert client.product_shop_prices(product, ["tesco-4062", "lidl-274"]) == {}
        assert client.product_shop_prices(product, []) == {}
    assert len(fake.requests) == 1  # an empty id list sends nothing


def test_shop_prices_merges_found_and_not_found_chunks(fake: FakeGvh, clock: FakeClock) -> None:
    world = build_world()
    product = world.special["spar_outlier"]
    lidl = list(world.chains["Lidl"].stores)[:200]  # chunk 1: no Lidl store sells it -> NOT-FOUND (404)
    spar = list(world.budapest_stores("Spar"))[:3]
    with make_client(fake.transport(), clock) as client:
        prices = client.product_shop_prices(product, lidl + spar)
    assert len(fake.requests) == 2
    offer = world.products[product].offers[0]
    assert set(prices) == set(spar) & set(offer.stores)
    outliers = {s for s in prices if prices[s][0].amount == Decimal(294)}
    assert outliers == offer.special & set(spar)
    assert all(prices[s][0].amount == Decimal(699) for s in set(prices) - outliers)


def test_shop_prices_other_404_is_an_error(clock: FakeClock) -> None:
    transport = json_handler(lambda r: (404, {"message": "SOMETHING-ELSE"}))
    with make_client(transport, clock) as client, pytest.raises(GvhHttpError) as err:
        client.product_shop_prices("123", ["spar-110"])
    assert (err.value.status, err.value.code) == (404, "SOMETHING-ELSE")


def test_shop_prices_not_found_in_a_200_body(clock: FakeClock) -> None:
    transport = json_handler(lambda r: (200, {"error": "PRODUCT-SHOP-PRICES-NOT-FOUND"}))
    with make_client(transport, clock) as client:
        assert client.product_shop_prices("123", ["spar-110"]) == {}


def test_shop_prices_validates_ids_before_sending(clock: FakeClock, fake: FakeGvh) -> None:
    with make_client(fake.transport(), clock) as client:
        with pytest.raises(ValueError, match="store id"):
            client.product_shop_prices("123", ["spar-110", "x/../y"])
        with pytest.raises(ValueError, match="product id"):
            client.product_shop_prices("../shops", ["spar-110"])
    assert fake.requests == []


# ───────────────────────────── product detail ─────────────────────────────


def test_product_detail_lists_every_chain_with_availability(fake: FakeGvh, clock: FakeClock) -> None:
    world = build_world()
    product = world.products[world.special["multichain"]]
    with make_client(fake.transport(), clock) as client:
        detail = client.product(product.id)
    assert sorted(c.name or "" for c in detail.chainStores) == ["Aldi", "Auchan", "Penny", "Spar", "Tesco"]
    by_name = {c.name: c for c in detail.chainStores}
    assert by_name["Auchan"].availableInShops == list(
        next(o for o in product.offers if o.chain == "Auchan").stores
    )


def test_product_detail_404_is_an_http_error(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client, pytest.raises(GvhHttpError) as err:
        client.product("5990000000000")
    assert (err.value.status, err.value.code) == (404, "PRODUCT-NOT-FOUND")


# ───────────────────────────── schema validation ─────────────────────────────


def test_unknown_fields_are_accepted_and_recorded_as_drift(fake: FakeGvh, clock: FakeClock) -> None:
    fake.drift = "extra_field"
    with make_client(fake.transport(), clock) as client:
        listing = client.products_by_category(40)
        assert listing.products
        assert client.drift == {"ListingProduct.newField": 1}


@pytest.mark.parametrize(
    ("drift", "message"),
    [
        ("type_change", "productMinAmount: value_error"),
        ("missing_field", "pricesOfChainStores: missing"),
        ("count_string", "count: int_type"),
    ],
)
def test_schema_changes_fail_loudly(fake: FakeGvh, clock: FakeClock, drift: str, message: str) -> None:
    fake.drift = drift
    with make_client(fake.transport(), clock) as client, pytest.raises(GvhSchemaError, match=message):
        client.products_by_category(40)


def test_html_instead_of_json_is_a_schema_error(clock: FakeClock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # the real site answers unknown paths with its SPA
        return httpx.Response(
            200, content=b"<!doctype html><html></html>", headers={"content-type": "text/html"}
        )

    with (
        make_client(httpx.MockTransport(handler), clock) as client,
        pytest.raises(GvhSchemaError, match="text/html"),
    ):
        client.categories()


def test_responses_above_the_size_cap_are_refused(
    fake: FakeGvh, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client_module, "API_MAX_BYTES", 1000)
    with (
        make_client(fake.transport(), clock) as client,
        pytest.raises(GvhHttpError, match="larger than 1000"),
    ):
        client.shops()
    assert len(fake.requests) == 1  # not retried


def test_request_budget(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock, max_requests=2) as client:
        client.chain_stores()
        client.categories()
        with pytest.raises(GvhBudgetExceeded):
            client.shops()
        assert client.stats.requests == 2
    assert len(fake.requests) == 2


def test_retries_count_against_the_budget(fake: FakeGvh, clock: FakeClock) -> None:
    fake.fail("/api/shops", 503, times=5)
    with make_client(fake.transport(), clock, max_requests=2) as client, pytest.raises(GvhBudgetExceeded):
        client.shops()
    assert len(fake.requests) == 2


def test_stats_count_requests_and_bytes(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        client.chain_stores()
        assert client.stats.requests == 1
        assert client.stats.bytes == len(fake.respond("/api/chain-stores").body)


def test_constructor_validation() -> None:
    with pytest.raises(ValueError, match="max_requests"):
        GvhClient(fake_settings(), max_requests=0)
    with pytest.raises(ValueError, match="max_retries"):
        GvhClient(fake_settings(), max_retries=4)
    assert LISTING_LIMIT == 48


# ───────────────────────────── daily XLSX ─────────────────────────────


def test_xlsx_is_cache_busted_and_date_checked(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        sheet = client.daily_xlsx(DAY, run_id=42)
    assert fake.requests[0].path == "/excel/arfigyelo_napi_termekadatok.xlsx"
    assert fake.requests[0].query == {"v": "20261013-42"}  # data date + ops.ingest_run id
    assert sheet.data_date == DAY
    assert sheet.sheet_name == "Napi feltöltések - 2026-10-13"
    assert len(sheet.rows) > 500


def test_xlsx_cache_buster_is_unique_per_run_and_dated_by_the_data_date(
    fake: FakeGvh, clock: FakeClock
) -> None:
    with make_client(fake.transport(), clock) as client:
        client.daily_xlsx(DAY, run_id=7)
        client.daily_xlsx(DAY, run_id=8)
    assert fake.xlsx_busters() == ["20261013-7", "20261013-8"]
    assert xlsx_cache_buster(date(2026, 1, 5), "123") == "20260105-123"


def test_xlsx_cache_buster_outside_a_run_uses_the_injected_suffix(fake: FakeGvh, clock: FakeClock) -> None:
    suffixes = iter(["t1", "t2"])
    with make_client(fake.transport(), clock, buster_suffix=lambda: next(suffixes)) as client:
        client.daily_xlsx(DAY)
        client.daily_xlsx(DAY)
    assert fake.xlsx_busters() == ["20261013-t1", "20261013-t2"]


def test_xlsx_cache_buster_outside_a_run_is_random_by_default(fake: FakeGvh, clock: FakeClock) -> None:
    with make_client(fake.transport(), clock) as client:
        client.daily_xlsx(DAY)
        client.daily_xlsx(DAY)
    first, second = fake.xlsx_busters()
    assert first != second
    assert all(re.fullmatch(r"20261013-x[0-9a-f]{12}", value) for value in (first, second))
    assert random_buster_suffix() != random_buster_suffix()


@pytest.mark.parametrize("run_id", [0, -1, True, "5"])
def test_xlsx_rejects_an_invalid_run_id(fake: FakeGvh, clock: FakeClock, run_id: object) -> None:
    with make_client(fake.transport(), clock) as client, pytest.raises(ValueError, match="run id"):
        client.daily_xlsx(DAY, run_id=run_id)  # type: ignore[arg-type]
    assert fake.requests == []


@pytest.mark.parametrize("suffix", ["", "a&b=c", "x" * 33, "ü"])
def test_xlsx_rejects_an_unsafe_buster_suffix(fake: FakeGvh, clock: FakeClock, suffix: str) -> None:
    with (
        make_client(fake.transport(), clock, buster_suffix=lambda: suffix) as client,
        pytest.raises(ValueError, match="cache-buster"),
    ):
        client.daily_xlsx(DAY)
    assert fake.requests == []


def test_a_per_run_buster_gets_past_a_copy_cached_before_the_regeneration(
    fake: FakeGvh, clock: FakeClock
) -> None:
    """Trap 4: a run before GVH regenerated the file (about 02:00 UTC) makes the CDN edge cache yesterday's
    copy under that run's ``v``. Re-using the value (as a per-day buster would) keeps getting the stale copy;
    the scheduler's retry is a new run with a new value and gets the fresh file."""
    fake.xlsx_date = date(2026, 10, 12)  # the origin still holds yesterday's file
    with make_client(fake.transport(), clock) as client:
        with pytest.raises(StaleXlsxError):
            client.daily_xlsx(DAY, run_id=1)
        fake.xlsx_date = None  # regenerated at the origin
        with pytest.raises(StaleXlsxError):
            client.daily_xlsx(DAY, run_id=1)  # same cache key: the edge still serves the stale copy
        assert client.daily_xlsx(DAY, run_id=2).data_date == DAY
    assert fake.xlsx_busters() == ["20261013-1", "20261013-1", "20261013-2"]


def test_the_fake_cdn_serves_a_stale_copy_without_the_cache_buster(fake: FakeGvh) -> None:
    """Documents why the buster matters: the CDN keeps serving yesterday's file to a plain GET."""
    result = fake.respond("/excel/arfigyelo_napi_termekadatok.xlsx")
    assert isinstance(result, FakeResponse)
    with pytest.raises(StaleXlsxError):
        parse_daily_xlsx(result.body, DAY)


def test_stale_xlsx_raises(fake: FakeGvh, clock: FakeClock) -> None:
    fake.xlsx_date = date(2026, 10, 12)
    with make_client(fake.transport(), clock) as client, pytest.raises(StaleXlsxError) as err:
        client.daily_xlsx(DAY)
    assert (err.value.sheet_date, err.value.expected_date) == (date(2026, 10, 12), DAY)
    assert "2026-10-12 != expected 2026-10-13" in str(err.value)


def test_xlsx_http_error(fake: FakeGvh, clock: FakeClock) -> None:
    fake.fail("/excel/", 404)
    with make_client(fake.transport(), clock) as client, pytest.raises(GvhHttpError) as err:
        client.daily_xlsx(DAY)
    assert err.value.status == 404


def test_xlsx_drift_is_recorded(fake: FakeGvh, clock: FakeClock) -> None:
    fake.xlsx_mode = "extra_column"
    with make_client(fake.transport(), clock) as client:
        client.daily_xlsx(DAY)
        assert client.drift == {"xlsx.header:Új oszlop": 1}


def test_listing_tolerates_a_category_that_changes_while_paging(clock: FakeClock) -> None:
    """A shrinking category gives a short page before the first count: a data change, not an ignored limit."""
    fake = FakeGvh(build_world(), data_date=DAY)
    first = json.loads(fake.respond("/api/products-by-category/18?limit=48&offset=0").body)["products"]  # type: ignore[union-attr]

    def route(request: httpx.Request) -> tuple[int, object]:
        if request.url.params["offset"] == "0":
            return 200, {"products": first, "count": 101}
        return 200, {"products": [dict(p, id=f"x-{i}") for i, p in enumerate(first[:40])], "count": 95}

    with make_client(json_handler(route), clock) as client:
        listing = client.products_by_category(18)
    assert listing.count_changed
    assert listing.count == 95
    assert listing.pages == 2
    assert len(listing.products) == 88
    assert listing.missing == 7


def test_listing_count_change_on_the_last_page_is_flagged(clock: FakeClock) -> None:
    fake = FakeGvh(build_world(), data_date=DAY)
    first = json.loads(fake.respond("/api/products-by-category/18?limit=48&offset=0").body)["products"]  # type: ignore[union-attr]

    def route(request: httpx.Request) -> tuple[int, object]:
        if request.url.params["offset"] == "0":
            return 200, {"products": first, "count": 60}
        return 200, {"products": [dict(first[0], id="x-1")], "count": 49}

    with make_client(json_handler(route), clock) as client:
        listing = client.products_by_category(18)
    assert listing.count_changed
    assert (listing.count, len(listing.products), listing.missing) == (49, 49, 0)


def test_a_corrupt_compressed_body_is_an_http_error_without_retry(clock: FakeClock) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"not gzip at all", headers={"content-encoding": "gzip"})

    with (
        make_client(httpx.MockTransport(handler), clock) as client,
        pytest.raises(GvhHttpError, match="undecodable"),
    ):
        client.shops()
    assert len(calls) == 1


@pytest.mark.parametrize("status", [404, 400, 500])
def test_shop_prices_not_found_with_any_error_status_is_final(clock: FakeClock, status: int) -> None:
    calls = []

    def route(request: httpx.Request) -> tuple[int, object]:
        calls.append(request)
        return status, {"statusCode": status, "message": "PRODUCT-SHOP-PRICES-NOT-FOUND"}

    with make_client(json_handler(route), clock) as client:
        assert client.product_shop_prices("123", ["spar-110"]) == {}
    assert len(calls) == 1  # never retried, even as a 5xx
    assert clock.sleeps == []


def test_other_5xx_on_shop_prices_are_retried(fake: FakeGvh, clock: FakeClock) -> None:
    product = build_world().special["spar_outlier"]
    fake.fail(f"/api/product/{product}/shop/", 502, times=2)
    with make_client(fake.transport(), clock) as client:
        assert client.product_shop_prices(product, ["spar-110"]) != {}
    assert len(fake.requests) == 3
