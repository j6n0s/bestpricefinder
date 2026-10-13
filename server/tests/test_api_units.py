"""Pure unit tests of bpf.api helpers (no database, SYNTHETIC data only)."""

from __future__ import annotations

import contextlib
import json
import threading
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from starlette.datastructures import Headers

from bpf.api import present
from bpf.api.caching import etag_matches, make_etag
from bpf.api.errors import MAX_FIELDS, field_path, field_paths
from bpf.api.repo import (
    CatalogueProvider,
    DataUnavailable,
    RawData,
    assemble_snapshot,
    store_has_data,
    summarise_costs,
)
from bpf.api.routes import is_stale
from bpf.api.security import TokenBucketLimiter, client_key, declared_length, is_json_content_type
from bpf.api.static import STRICT_HTML_POLICY, header_policy, meta_csp
from bpf.api.strictjson import strict_json_loads
from bpf.api.texts import nutrition_attribution
from bpf.pricing import ChainRecipeCost, Ingredient, KshPrice
from tests.fixtures.api.asgi import JSON_HEADERS, raw_request
from tests.fixtures.api.memory import MemorySource, app_with, client_with, memory_raw
from tests.fixtures.api.seed import FakeClock, TestClient

D = Decimal
DAY = date(2026, 10, 12)


# ───────────────────────────── field paths ─────────────────────────────


@pytest.mark.parametrize(
    ("loc", "expected"),
    [
        (("body", "lines", 0, "qty"), "lines.0.qty"),
        (("body", "store_ids", 3), "store_ids.3"),
        (("body",), "body"),
        ((), "body"),
        (("body", "lines", 0, "zzSENTINEL"), "lines.0"),  # an unexpected key is never echoed
        (("body", "zzSENTINEL", "lines"), "body"),
        (("body", "days", 0, "meals", "zzsentinel", "[key]"), "days.0.meals"),
        (("body", "days", 0, "meals", "ebed"), "days.0.meals.ebed"),
        (("body", "days", 0, "meals", "ebed", "function-after[...]"), "days.0.meals.ebed"),
        (("query", "q"), "query.q"),
        (("query", "zzSENTINEL"), "query"),
        (("path", "id"), "path.id"),
        (("body", True, "lines"), "body"),  # a bool is not an index
        (("body", "lines", 10**6), "lines"),
        (("body", "lines", -1), "lines"),
    ],
)
def test_field_path(loc: tuple[Any, ...], expected: str) -> None:
    assert field_path(loc) == expected


def test_field_paths_dedupe_cap_and_json_errors() -> None:
    errors = [{"type": "json_invalid", "loc": ("body", 1234)}, {"type": "missing", "loc": ("body", "lines")}]
    errors += [{"type": "missing", "loc": ("body", "lines")}]
    assert field_paths(errors) == ["body", "lines"]
    many = [{"type": "x", "loc": ("body", "lines", i, "qty")} for i in range(500)]
    assert len(field_paths(many)) == MAX_FIELDS


# ───────────────────────────── strict JSON ─────────────────────────────


@pytest.mark.parametrize(
    "body",
    [
        b'{"a": 1, "a": 1}',
        b'{"a": {"b": 1, "b": 2}}',
        b"[NaN]",
        b"[Infinity]",
        b"[-Infinity]",
        b"[1" + b"0" * 4400 + b"]",
        b"\xef\xbb\xbf{}",
        '{"a": 1}'.encode("utf-16"),
        '{"a": 1}'.encode("utf-32"),
        b"\x80",
        b"{",
        b"",
        b"{'a': 1}",
    ],
)
def test_strict_json_rejects(body: bytes) -> None:
    with pytest.raises(json.JSONDecodeError) as caught:
        strict_json_loads(body)
    assert caught.value.doc == ""  # the body is never carried along


@pytest.mark.parametrize("depth", [1_000, 5_000, 32_767])
def test_strict_json_deep_nesting_never_escapes_as_another_error(depth: int) -> None:
    """32,767 levels is the deepest document that fits the default 64 KiB body limit. Depending on the C
    stack, Python either parses it or raises RecursionError; strict_json_loads must only ever return or raise
    JSONDecodeError (which FastAPI reports as 422)."""
    for opener, closer in ((b"[", b"]"), (b'{"a":', b"}")):
        body = opener * depth + b"1" + closer * depth
        with contextlib.suppress(json.JSONDecodeError):
            strict_json_loads(body)


def test_strict_json_accepts_plain_json() -> None:
    assert strict_json_loads(b'{"a": [1, 2.5, "\\u00e9", null, true], "b": {"a": 1}}') == {
        "a": [1, 2.5, "é", None, True],
        "b": {"a": 1},
    }
    assert strict_json_loads('{"név": "ő"}'.encode()) == {"név": "ő"}
    assert strict_json_loads(b"1e400") == float("inf")  # syntactically fine; the models reject it


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"lines": [{"ingredient_id": "rizs", "qty": 1e308}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": -1e308}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": "1e100"}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": "9" * 20}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": "NaN"}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": "sNaN"}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": "-Infinity"}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": "abc"}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": 1e-30}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": True}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
        ({"lines": [{"ingredient_id": "rizs", "qty": 10**30}], "store_ids": ["alfa-1"]}, "lines.0.qty"),
    ],
)
def test_huge_and_odd_quantities_are_422_not_500(body: dict[str, Any], field: str) -> None:
    """Regression (found by the fuzz test): schemas._to_qty quantizes in the ambient decimal context, where
    1e308 raises decimal.InvalidOperation; validation must report it as an invalid field."""
    client = client_with()
    response = client.post("/api/quote", json=body)
    assert (response.status_code, response.json()) == (422, {"error": "invalid_request", "fields": [field]})
    servings = client.post("/api/list", json={"items": [{"recipe_id": "zz-porkolt", "servings": 1e300}]})
    assert servings.json() == {"error": "invalid_request", "fields": ["items.0.servings"]}
    ok = client.post(
        "/api/quote", json={"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": ["alfa-1"]}
    )
    assert ok.json()["stores"][0]["checkout_total"] == 499.0  # computing is unaffected


# ───────────────────────────── caching ─────────────────────────────


def test_etag() -> None:
    tag = make_etag(DAY, b"{}")
    assert tag == make_etag(DAY, b"{}")
    assert tag != make_etag(DAY + timedelta(days=1), b"{}")  # the data date is part of the tag
    assert tag != make_etag(DAY, b"{ }")
    assert make_etag(None, b"{}") != tag
    assert etag_matches(tag, tag)
    assert etag_matches(f"W/{tag}", tag)
    assert etag_matches(f'"a", W/"b",{tag}', tag)
    assert etag_matches("*", tag)
    assert not etag_matches(None, tag)
    assert not etag_matches(tag[:-2] + '"', tag)
    assert not etag_matches("", tag)


# ───────────────────────────── CSP ─────────────────────────────


def test_meta_csp_parsing() -> None:
    html = """<html><head><META HTTP-EQUIV='Content-Security-Policy' CONTENT="default-src 'self'">
    <meta http-equiv="content-security-policy" content="second"></head></html>"""
    assert meta_csp(html) == "default-src 'self'"
    assert meta_csp("<meta name='x' content='y'>") is None
    assert meta_csp("<meta http-equiv='refresh' content='0'>") is None
    assert meta_csp("<meta http-equiv='content-security-policy' content='a &amp; b'>") == "a & b"


@pytest.mark.parametrize(
    ("meta", "header"),
    [
        ("default-src 'self'", "default-src 'self'; frame-ancestors 'none'"),
        ("default-src 'self';", "default-src 'self'; frame-ancestors 'none'"),
        (
            "  default-src   'self' ;\n script-src 'self' ",
            "default-src 'self'; script-src 'self'; frame-ancestors 'none'",
        ),
        ("default-src 'self'; FRAME-ANCESTORS *", "default-src 'self'; frame-ancestors 'none'"),
        (None, STRICT_HTML_POLICY),
        ("", STRICT_HTML_POLICY),
        (";;", STRICT_HTML_POLICY),
        ("default-src 'self', script-src *", STRICT_HTML_POLICY),  # a comma would split the header
        ("default-src 'self' é", STRICT_HTML_POLICY),  # not header-safe
    ],
)
def test_header_policy(meta: str | None, header: str) -> None:
    assert header_policy(meta) == header


# ───────────────────────────── costs, has_data, staleness ─────────────────────────────


def _cost(chain: str, value: str | None, share: str = "1") -> ChainRecipeCost:
    return ChainRecipeCost(chain, None if value is None else D(value), D(share), ())


def test_summarise_costs_keeps_every_whole_forint_tie() -> None:
    summary = summarise_costs(
        [
            _cost("a", "412.45", "0.9"),
            _cost("b", "412.40", "1"),
            _cost("c", "412.49", "0.8"),
            _cost("d", "412.50"),
        ]
    )
    # 412.40 is the minimum; 412.45 and 412.49 round to 412 as well (tied); 412.50 rounds to 413
    assert summary.cost_per_serving_from == D("412.40")
    assert summary.cheapest_chain_ids == ("a", "b", "c")
    assert summary.priced_share == D("0.8")  # the lowest share of the tie group
    assert summarise_costs([_cost("a", None), _cost("b", None)]).cost_per_serving_from is None
    assert summarise_costs([]).cheapest_chain_ids == ()


def test_store_has_data_rule() -> None:
    fresh = DAY - timedelta(days=2)
    assert store_has_data(DAY, None, fresh) is False  # no data date at all
    assert store_has_data(None, DAY, None) is True  # no availability refresh ever
    assert store_has_data(None, DAY, DAY - timedelta(days=9)) is True  # the last refresh is too old
    assert store_has_data(None, DAY, DAY - timedelta(days=8)) is False  # a refresh 8 days ago still counts
    assert store_has_data(DAY - timedelta(days=8), DAY, fresh) is True
    assert store_has_data(DAY - timedelta(days=9), DAY, fresh) is False
    assert store_has_data(DAY + timedelta(days=1), DAY, fresh) is True  # marked by a newer run


def test_is_stale() -> None:
    today = date(2026, 10, 13)
    assert not is_stale(date(2026, 10, 13), today)
    assert not is_stale(date(2026, 10, 12), today)
    assert is_stale(date(2026, 10, 11), today)
    assert is_stale(None, today)


def test_provider_today_is_budapest_time() -> None:
    late = CatalogueProvider(MemorySource(), now=lambda: datetime(2026, 10, 12, 22, 30, tzinfo=UTC))
    assert late.today() == date(2026, 10, 13)  # 00:30 in Budapest (CEST)
    winter = CatalogueProvider(MemorySource(), now=lambda: datetime(2026, 12, 31, 23, 0, tzinfo=UTC))
    assert winter.today() == date(2027, 1, 1)  # midnight in Budapest (CET)


# ───────────────────────────── client keys and the limiter ─────────────────────────────


def scope(peer: str | None, *xff: str) -> dict[str, Any]:
    return {
        "headers": [(b"x-forwarded-for", v.encode()) for v in xff],
        "client": None if peer is None else (peer, 1234),
    }


def test_client_key() -> None:
    assert client_key(scope("198.51.100.7"), trust_proxy_headers=False) == "198.51.100.7"
    assert client_key(scope("198.51.100.7", "203.0.113.1"), trust_proxy_headers=False) == "198.51.100.7"
    assert (
        client_key(scope("198.51.100.7", "1.1.1.1, 203.0.113.1"), trust_proxy_headers=True) == "203.0.113.1"
    )
    assert (
        client_key(scope("198.51.100.7", "1.1.1.1", " 203.0.113.2 "), trust_proxy_headers=True)
        == "203.0.113.2"
    )
    assert client_key(scope("198.51.100.7", "1.1.1.1, bogus"), trust_proxy_headers=True) == "198.51.100.7"
    assert client_key(scope("2001:db8::1"), trust_proxy_headers=False) == "2001:db8::/64"
    assert client_key(scope("::ffff:203.0.113.3"), trust_proxy_headers=False) == "203.0.113.3"
    assert client_key(scope(None), trust_proxy_headers=False) == "unknown"
    assert client_key(scope("testclient"), trust_proxy_headers=False) == "testclient"


def test_limiter_refill_is_capped_and_memory_bounded() -> None:
    clock = FakeClock()
    limiter = TokenBucketLimiter(60, burst=2, clock=clock, max_keys=3)
    assert [limiter.take("a") for _ in range(3)] == [None, None, 1.0]
    clock.advance(3600)  # an hour idle: still only the burst
    assert [limiter.take("a") is None for _ in range(3)] == [True, True, False]
    for key in ("b", "c", "d", "e"):
        limiter.take(key)
    assert len(limiter._buckets) == 3  # least recently used keys evicted
    with pytest.raises(ValueError, match="must be > 0"):
        TokenBucketLimiter(0)


@pytest.mark.parametrize(
    ("values", "ok"),
    [
        (["application/json"], True),
        (["application/json; charset=utf-8"], True),
        (['application/json; charset="UTF-8"'], True),
        (["application/json; boundary=x"], True),
        (["application/json; charset=iso-8859-2"], False),
        (["text/json"], False),
        (["application/json", "application/json"], False),
        ([], False),
    ],
)
def test_is_json_content_type(values: list[str], ok: bool) -> None:
    assert is_json_content_type(Headers(raw=[(b"content-type", v.encode()) for v in values])) is ok


# ───────────────────────────── presentation ─────────────────────────────


def test_rounding_at_the_edge() -> None:
    assert present.money(D("0.005")) == 0.01  # half-up
    assert present.money(D("2.675")) == 2.68  # exact decimal, not binary float rounding
    assert present.money(D("1078.8")) == 1078.8
    assert present.qty(D("0.0025")) == 0.003
    assert present.share(D("0.99999")) == 0.9999  # never overstated
    assert present.share(D("1.5")) == 1.0
    assert present.share(D("-0.1")) == 0.0
    assert present.money_or_none(None) is None


def test_priced_by() -> None:
    cat = assemble_snapshot(memory_raw()).catalogue
    ksh = cat.ksh["zz-paprika"]
    mapped = Ingredient("x", "x", "egyeb", "kg", leaf_ids=(1,), ksh_code="zz-paprika")
    assert present.priced_by(mapped, cat) == "gvh"
    assert present.priced_by(Ingredient("x", "x", "egyeb", "kg", ksh_code="zz-paprika"), cat) == "ksh"
    pantry = Ingredient("x", "x", "egyeb", "kg", pantry=True, ksh_code="zz-paprika")
    assert present.priced_by(pantry, cat) == "none"  # docs/DATA.md: a pantry ingredient without leaves
    assert present.priced_by(Ingredient("x", "x", "egyeb", "kg", ksh_code="zz-missing"), cat) == "none"
    assert ksh == KshPrice("zz-paprika", ksh.name, "kg", D(1), D(4000), ksh.period)


def test_nutrition_attribution() -> None:
    assert nutrition_attribution([]) is None
    assert nutrition_attribution(["other"]) is None
    both = nutrition_attribution(["usda", "ciqual", "ciqual"])
    assert both is not None
    assert both.text_hu == "Tápérték-adatok forrása: ANSES-CIQUAL, USDA FoodData Central"
    assert both.license == "Licence Ouverte / Etalab 2.0; CC0 1.0"


# ───────────────────────────── the provider ─────────────────────────────


class SlowSource(MemorySource):
    def __init__(self, raw: RawData | None = None) -> None:
        super().__init__(raw)
        self.delay = 0.2
        self.lock = threading.Lock()
        self.concurrent = 0
        self.max_concurrent = 0

    def load(self) -> RawData:
        with self.lock:
            self.concurrent += 1
            self.max_concurrent = max(self.max_concurrent, self.concurrent)
        time.sleep(self.delay)
        try:
            return super().load()
        finally:
            with self.lock:
                self.concurrent -= 1


def test_provider_first_load_is_shared_by_concurrent_requests() -> None:
    source = SlowSource()
    provider = CatalogueProvider(source, monotonic=FakeClock())
    results: list[object] = []
    threads = [threading.Thread(target=lambda: results.append(provider.snapshot())) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert source.loads == 1
    assert len({id(r) for r in results}) == 1


def test_provider_serves_the_cached_snapshot_while_reloading() -> None:
    class GatedSource(MemorySource):
        def __init__(self) -> None:
            super().__init__()
            self.loading = threading.Event()
            self.release = threading.Event()

        def load(self) -> RawData:
            if self.loads:  # the reload: signal, then wait until the test lets it finish
                self.loading.set()
                assert self.release.wait(10)
            return super().load()

    source = GatedSource()
    clock = FakeClock()
    provider = CatalogueProvider(source, monotonic=clock)
    first = provider.snapshot()
    source.raw = memory_raw(key=("v2",))
    clock.advance(61)
    reloader = threading.Thread(target=provider.snapshot)
    reloader.start()
    assert source.loading.wait(10)  # the reload holds the lock now
    assert provider.snapshot() is first  # served from the cache, not blocked by the reload
    source.release.set()
    reloader.join(10)
    assert provider.snapshot().key == ("v2",)
    assert source.loads == 2


def test_provider_recheck_interval_and_failures() -> None:
    source = MemorySource()
    clock = FakeClock()
    provider = CatalogueProvider(source, monotonic=clock)
    first = provider.snapshot()
    source.raw = memory_raw(key=("v2",))
    clock.advance(59.9)
    assert provider.snapshot() is first  # within 60 s: not even re-checked
    source.down = True
    clock.advance(1)
    assert provider.snapshot() is first  # the re-check fails: keep serving
    source.down = False
    assert provider.snapshot() is first  # and do not retry before the interval
    clock.advance(60)
    assert provider.snapshot().key == ("v2",)
    assert source.loads == 2


def test_provider_without_any_snapshot_raises() -> None:
    source = MemorySource()
    source.down = True
    provider = CatalogueProvider(source)
    with pytest.raises(DataUnavailable):
        provider.snapshot()
    with pytest.raises(DataUnavailable):
        provider.latest()
    with pytest.raises(DataUnavailable):
        provider.history(["x"], None, DAY, DAY)
    assert provider.history([], None, DAY, DAY) == []  # nothing to ask


def test_provider_keeps_serving_after_a_broken_reload() -> None:
    class Broken(MemorySource):
        def load(self) -> RawData:
            if self.loads:
                raise ValueError("synthetic broken content")
            return super().load()

    source = Broken()
    clock = FakeClock()
    provider = CatalogueProvider(source, monotonic=clock)
    first = provider.snapshot()
    source.raw = memory_raw(key=("v2",))
    clock.advance(61)
    assert provider.snapshot() is first


def test_source_unavailable_is_mapped_by_the_routes() -> None:
    source = MemorySource()
    source.down = True
    client = TestClient(app_with(provider=CatalogueProvider(source)))
    assert client.get("/api/health").status_code == 503
    assert client.get("/api/meta").json() == {"error": "no_data", "fields": []}
    assert client.post("/api/plan/check", json={"days": [{"index": 0, "meals": {}}]}).status_code == 503


def test_provider_backs_off_after_a_failed_first_load() -> None:
    class Counting(MemorySource):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def load(self) -> RawData:
            self.attempts += 1
            return super().load()

    source = Counting()
    source.down = True
    clock = FakeClock()
    provider = CatalogueProvider(source, monotonic=clock)
    for _ in range(5):
        with pytest.raises(DataUnavailable):
            provider.snapshot()
    assert source.attempts == 1  # the dead database is not hammered by every queued request
    source.down = False
    clock.advance(4.9)
    with pytest.raises(DataUnavailable):
        provider.snapshot()
    clock.advance(0.2)
    assert provider.snapshot().key == ("memory",)
    assert source.attempts == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("12", 12),
        (" 12 ", 12),
        ("²", None),  # a Unicode digit: str.isdigit() is True, int() would fail
        ("١٢", None),  # Arabic-Indic digits
        ("-1", None),
        ("1e3", None),
        ("9" * 5000, 10**18),  # over Python's int digit limit: capped, not parsed
    ],
)
def test_declared_length(value: str | None, expected: int | None) -> None:
    assert declared_length(value) == expected


def test_odd_content_length_headers_never_500() -> None:
    app = app_with(api_max_body_bytes=100)
    for value in ("²".encode("latin-1"), b"9" * 5000, b"-5", b"abc"):
        status, _, _ = raw_request(
            app, "/api/plan/check", method="POST", headers=[*JSON_HEADERS, (b"content-length", value)]
        )
        assert status in (413, 422), value
