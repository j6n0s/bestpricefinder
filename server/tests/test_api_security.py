"""Security middlewares and static hosting, without a database (in-memory SYNTHETIC catalogue,
tests/fixtures/api/memory.py; a fake ``web/build`` made in a temporary directory).

Covers: security headers on every kind of response (incl. static files, 404, 405, 413, 415, 429, 500); the
SPA's CSP header = the HTML meta policy + ``frame-ancestors 'none'``; path traversal (dot segments, encoded
slashes and backslashes, absolute paths, NUL, symlinks) never leaving the build; static caching; the body
limit for declared, streamed and chunked bodies (also through a real uvicorn server); the rate limiter with
and without trusted proxy headers; generic 500s that log no request body; the docs UI switch.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from bpf.api.options import ApiOptions
from bpf.api.repo import CatalogueProvider
from bpf.api.security import API_CSP
from tests.fixtures.api.asgi import JSON_HEADERS, raw_request
from tests.fixtures.api.memory import MemorySource, app_with, client_with
from tests.fixtures.api.seed import FakeClock, TestClient
from tests.pgcluster import free_port

META_POLICY = (
    "default-src 'self'; worker-src 'self'; connect-src 'self'; img-src 'self' data:; manifest-src 'self'; "
    "object-src 'none'; script-src 'self' 'sha256-c3ludGhldGljLXRlc3QtaGFzaA=='; style-src 'self'; "
    "base-uri 'self'; form-action 'self'"
)
HTML_POLICY = META_POLICY + "; frame-ancestors 'none'"
INDEX_HTML = f"""<!doctype html>
<html lang="hu"><head><meta charset="utf-8">
<meta http-equiv="content-security-policy" content="{META_POLICY}">
<title>Synthetic test page</title></head><body><div id="app">SPA-FALLBACK-PAGE</div></body></html>
"""
SECRET = "TOPSECRET-do-not-serve"
COMMON_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "permissions-policy": "geolocation=(self), camera=(), microphone=(), payment=(), usb=()",
}


def make_build(root: Path, index_html: str = INDEX_HTML) -> Path:
    """A fake adapter-static build next to a secret file it must never serve."""
    (root / "secret.txt").write_text(SECRET)
    (root / "outside").mkdir()
    (root / "outside" / "secret.txt").write_text(SECRET)
    build = root / "build"
    (build / "_app" / "immutable" / "entry").mkdir(parents=True)
    (build / "icons").mkdir()
    (build / "index.html").write_text(index_html)
    (build / "_app" / "immutable" / "entry" / "app.Abc123.js").write_text("export const synthetic = 1;\n")
    (build / "_app" / "version.json").write_text('{"version":"synthetic"}')
    (build / "service-worker.js").write_text("self.addEventListener('fetch', () => {});\n")
    (build / "manifest.webmanifest").write_text('{"name":"Synthetic"}')
    (build / "icons" / "icon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (build / ".hidden").write_text(SECRET)
    (build / "leak.txt").symlink_to(root / "secret.txt")
    (build / "linkdir").symlink_to(root / "outside", target_is_directory=True)
    return build


def assert_common_headers(headers: Any) -> None:
    for name, value in COMMON_HEADERS.items():
        assert headers.get(name) == value, name
    assert "content-security-policy" in headers
    assert "server" not in headers


@pytest.fixture
def build(tmp_path: Path) -> Path:
    return make_build(tmp_path)


@pytest.fixture
def site(build: Path) -> TestClient:
    return client_with(web_build_dir=build)


@pytest.fixture
def live_server(tmp_path: Path) -> Iterator[str]:
    """A real uvicorn server (h11) on a free port, serving the app with a fake web build."""
    app = app_with(web_build_dir=make_build(tmp_path))
    port = free_port()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", lifespan="off", http="h11", server_header=False
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:  # pragma: no cover - environment problem
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


# ───────────────────────────── static hosting ─────────────────────────────


def test_spa_index_and_fallback(site: TestClient) -> None:
    for path in ("/", "/index.html", "/terv", "/receptek/zz-porkolt", "/beallitasok?x=1", "/icons"):
        response = site.get(path)
        assert response.status_code == 200, path
        assert response.text == INDEX_HTML
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["content-security-policy"] == HTML_POLICY
        assert_common_headers(response.headers)
    etag = site.get("/").headers["etag"]
    cached = site.get("/terv", headers={"If-None-Match": etag})
    assert (cached.status_code, cached.content) == (304, b"")
    assert cached.headers["content-security-policy"] == HTML_POLICY


def test_csp_header_is_the_meta_policy_plus_frame_ancestors(build: Path, tmp_path: Path) -> None:
    response = client_with(web_build_dir=build).get("/")
    assert response.headers["content-security-policy"] == f"{META_POLICY}; frame-ancestors 'none'"
    # a frame-ancestors in the meta tag (ignored by browsers there) is replaced, whitespace is normalised
    other = tmp_path / "other"
    other.mkdir()
    make_build(
        other, INDEX_HTML.replace(META_POLICY, "default-src  'self';\n frame-ancestors *; script-src 'self'")
    )
    policy = client_with(web_build_dir=other / "build").get("/").headers["content-security-policy"]
    assert policy == "default-src 'self'; script-src 'self'; frame-ancestors 'none'"


def test_build_without_csp_meta_fails_closed(tmp_path: Path) -> None:
    build = make_build(tmp_path, "<!doctype html><title>x</title><script>alert(1)</script>")
    response = client_with(web_build_dir=build).get("/")
    assert response.headers["content-security-policy"] == (
        "default-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )


@pytest.mark.parametrize(
    ("path", "cache", "content_type"),
    [
        (
            "/_app/immutable/entry/app.Abc123.js",
            "public, max-age=31536000, immutable",
            "text/javascript; charset=utf-8",
        ),
        ("/service-worker.js", "no-cache", "text/javascript; charset=utf-8"),
        ("/_app/version.json", "no-cache", "application/json"),
        ("/manifest.webmanifest", "no-cache", "application/manifest+json"),
        ("/icons/icon.svg", "no-cache", "image/svg+xml"),
    ],
)
def test_static_files(site: TestClient, path: str, cache: str, content_type: str) -> None:
    response = site.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == cache
    assert response.headers["content-type"] == content_type
    assert response.headers["content-security-policy"] == HTML_POLICY  # also the service worker's policy
    assert_common_headers(response.headers)
    cached = site.get(path, headers={"If-None-Match": response.headers["etag"]})
    assert (cached.status_code, cached.content) == (304, b"")
    head = site.head(path)
    assert (head.status_code, head.content) == (200, b"")


@pytest.mark.parametrize(
    "path", ["/_app/immutable/entry/missing.js", "/_app/nothing", "/.hidden", "/icons/.x"]
)
def test_missing_assets_and_dotfiles_are_404(site: TestClient, path: str) -> None:
    response = site.get(path)
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "fields": []}
    assert response.headers["content-security-policy"] == API_CSP
    assert_common_headers(response.headers)


def test_api_paths_never_fall_back_to_the_spa(site: TestClient) -> None:
    for path in ("/api", "/api/", "/api/nope", "/api/stores/"):
        response = site.get(path)
        assert (response.status_code, response.json()) == (404, {"error": "not_found", "fields": []}), path
    assert site.get("/api/stores").status_code == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def test_static_methods(site: TestClient, method: str) -> None:
    response = site.request(method, "/terv")
    assert response.status_code == 405
    assert response.headers["allow"] == "GET, HEAD"
    assert response.json() == {"error": "method_not_allowed", "fields": []}
    assert_common_headers(response.headers)


TRAVERSALS = [
    "/../secret.txt",
    "/../../../../../../etc/passwd",
    "/icons/../../secret.txt",
    "/_app/../../secret.txt",
    "/..",
    "/.",
    "/./index.html",
    "/..\\secret.txt",
    "/\\..\\secret.txt",
    "/icons/..\\..\\secret.txt",
    "/leak.txt",  # a symlink to a file outside the build
    "/linkdir/secret.txt",  # through a symlinked directory
    "/index.html\x00.js",
    "/\x00",
    "/" + "a/" * 600,
]


@pytest.mark.parametrize("path", TRAVERSALS)
def test_path_traversal_never_escapes_the_build(build: Path, path: str) -> None:
    app = app_with(web_build_dir=build)
    status, headers, body = raw_request(app, path)
    assert SECRET.encode() not in body
    assert b"root:" not in body
    assert status in (200, 404)
    if status == 200:  # only ever the SPA page itself
        assert body == INDEX_HTML.encode()
    assert headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "path", ["/leak.txt", "/linkdir/secret.txt", "/../secret.txt", "/..\\secret.txt", "/.hidden"]
)
def test_traversal_candidates_are_refused(build: Path, path: str) -> None:
    status, _, body = raw_request(app_with(web_build_dir=build), path)
    assert status == 404
    assert json.loads(body) == {"error": "not_found", "fields": []}


def test_absolute_paths_stay_inside(build: Path, tmp_path: Path) -> None:
    app = app_with(web_build_dir=build)
    for path in (f"/{tmp_path}/secret.txt", f"//{tmp_path}/secret.txt", "//etc/passwd", "///etc/passwd"):
        status, _, body = raw_request(app, path)
        assert SECRET.encode() not in body
        assert b"root:" not in body
        assert status in (200, 404)


@pytest.mark.parametrize(
    "raw",
    [
        "/..%2fsecret.txt",
        "/..%2F..%2F..%2Fetc%2Fpasswd",
        "/%2e%2e/secret.txt",
        "/%2e%2e%2fsecret.txt",
        "/..%5csecret.txt",
        "/%5c..%5csecret.txt",
        "/icons/%2e%2e/%2e%2e/secret.txt",
        "/%2fetc%2fpasswd",
        "/leak.txt",
        "/linkdir%2fsecret.txt",
        "/%00",
        "/%c0%ae%c0%ae/secret.txt",
    ],
)
def test_encoded_traversal_through_a_real_server(live_server: str, raw: str) -> None:
    with httpx.Client() as client:
        request = client.build_request("GET", live_server)
        request.url = request.url.copy_with(raw_path=raw.encode("ascii"))
        response = client.send(request)
    assert SECRET not in response.text
    assert "root:" not in response.text
    assert response.status_code in (200, 400, 404)
    if response.status_code == 200:
        assert response.text == INDEX_HTML


def test_no_web_build_serves_only_the_api() -> None:
    client = client_with()
    for path in ("/", "/index.html", "/terv", "/service-worker.js"):
        response = client.get(path)
        assert (response.status_code, response.json()) == (404, {"error": "not_found", "fields": []})
        assert response.headers["content-security-policy"] == API_CSP


# ───────────────────────────── body size and content type ─────────────────────────────


def test_chunked_oversized_body_is_refused_while_streaming() -> None:
    """No Content-Length: the body arrives in 1 KiB chunks; the request is refused at the chunk that crosses
    the limit, before anything is parsed (the remaining chunks are never read)."""
    app = app_with(api_max_body_bytes=4096)
    chunks = [b"[" + b" " * 1023] + [b" " * 1024] * 9
    status, headers, body = raw_request(app, "/api/quote", method="POST", headers=JSON_HEADERS, chunks=chunks)
    assert status == 413
    assert json.loads(body) == {"error": "payload_too_large", "fields": []}
    assert headers["x-frame-options"] == "DENY"


def test_lying_content_length_is_still_counted() -> None:
    app = app_with(api_max_body_bytes=4096)
    headers = [*JSON_HEADERS, (b"content-length", b"10")]
    status, _, _ = raw_request(app, "/api/quote", method="POST", headers=headers, chunks=[b"x" * 3000] * 2)
    assert status == 413


def test_declared_content_length_over_the_limit() -> None:
    app = app_with(api_max_body_bytes=4096)
    headers = [*JSON_HEADERS, (b"content-length", b"4097")]
    status, _, body = raw_request(app, "/api/quote", method="POST", headers=headers, chunks=[b"{}"])
    assert (status, json.loads(body)["error"]) == (413, "payload_too_large")


def test_body_limit_applies_to_every_method_and_path() -> None:
    app = app_with(api_max_body_bytes=100)
    for method, path in (("GET", "/api/stores"), ("POST", "/api/nope"), ("PUT", "/api/quote")):
        status, _, _ = raw_request(app, path, method=method, headers=JSON_HEADERS, chunks=[b"x" * 101])
        assert status == 413, (method, path)


def test_chunked_oversized_body_through_a_real_server(live_server: str) -> None:
    def generate() -> Iterator[bytes]:
        yield b'{"lines": ['
        for _ in range(100):
            yield b" " * 1024

    with httpx.Client() as client:
        response = client.post(
            f"{live_server}/api/quote", content=generate(), headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 413
    assert response.json() == {"error": "payload_too_large", "fields": []}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "server" not in response.headers


def test_small_chunked_body_is_accepted(live_server: str) -> None:
    def generate() -> Iterator[bytes]:
        yield b'{"days": [{"index": 0,'
        yield b' "meals": {}}]}'

    with httpx.Client() as client:
        response = client.post(
            f"{live_server}/api/plan/check", content=generate(), headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 200
    assert response.json()["checks"][0]["rule"] == "fish"


@pytest.mark.parametrize(
    "body",
    [
        b'{"lines": [], "lines": []}',  # duplicate keys
        b'{"days": NaN}',
        b'{"days": Infinity}',
        b'{"days": -Infinity}',
        b'{"seed": 1' + b"0" * 5000 + b"}",  # over the int digit limit
        b"[" * 30_000 + b"]" * 30_000,  # deep nesting
        b'{"days": 7',  # truncated
        '{"days": 7}'.encode("utf-16"),  # not UTF-8
        b"\xef\xbb\xbf{}",  # UTF-8 BOM
        b"\xff\xfe\xfd",
        b"",
        b"null",
        b"[]",
        b'"string"',
    ],
)
def test_malformed_json_is_422_body(body: bytes) -> None:
    client = client_with()
    response = client.post("/api/plan/suggest", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_request", "fields": ["body"]}


# ───────────────────────────── rate limiting ─────────────────────────────


def limited(trust: bool = False) -> tuple[FastAPI, FakeClock]:
    app = app_with(api_rate_limit_per_minute=120, trust_proxy_headers=trust)
    clock = FakeClock()
    app.state.rate_limiter.clock = clock
    return app, clock


def hit(
    app: FastAPI, *, peer: str = "198.51.100.7", xff: list[str] | None = None, path: str = "/api/meta"
) -> int:
    headers = [(b"host", b"testserver"), *((b"x-forwarded-for", v.encode()) for v in xff or [])]
    status, response_headers, _ = raw_request(app, path, headers=headers, client=(peer, 40000))
    if status == 429:
        assert response_headers["retry-after"].isdigit()
    return status


def test_token_bucket_burst_and_refill() -> None:
    app, clock = limited()
    assert [hit(app) for _ in range(30)] == [200] * 30
    assert hit(app) == 429
    status, headers, body = raw_request(app, "/api/meta", client=("198.51.100.7", 1))
    assert (status, headers["retry-after"], json.loads(body)) == (
        429,
        "1",
        {"error": "rate_limited", "fields": []},
    )
    clock.advance(15)  # 30 tokens back (2 per second), never more than the burst
    assert [hit(app) for _ in range(31)] == [200] * 30 + [429]
    assert hit(app, peer="198.51.100.8") == 200  # another client has its own bucket


def test_rate_limit_only_for_api_paths(build: Path) -> None:
    app = app_with(api_rate_limit_per_minute=120, web_build_dir=build)
    app.state.rate_limiter.clock = FakeClock()
    assert [hit(app, path="/api/nope") for _ in range(30)] == [404] * 30
    assert hit(app, path="/api/meta") == 429
    assert hit(app, path="/terv") == 200  # the SPA and its assets are not rate limited


def test_forwarded_for_ignored_unless_trusted() -> None:
    app, _ = limited(trust=False)
    for i in range(30):
        assert hit(app, xff=[f"203.0.113.{i}"]) == 200
    assert hit(app, xff=["203.0.113.200"]) == 429  # every request counted for the socket peer


def test_forwarded_for_rightmost_entry_when_trusted() -> None:
    app, _ = limited(trust=True)
    # the right-most entry (the one the trusted proxy appended) is the client, whatever the client put first
    for i in range(30):
        assert hit(app, xff=[f"10.0.0.{i}, 203.0.113.5"]) == 200
    assert hit(app, xff=["10.9.9.9, 203.0.113.5"]) == 429
    assert hit(app, xff=["203.0.113.5", "203.0.113.6"]) == 200  # several headers: the last value counts
    assert hit(app, xff=["203.0.113.6"]) == 200
    # an unparsable entry falls back to the socket peer
    for _ in range(30):
        assert hit(app, peer="198.51.100.50", xff=["not-an-ip"]) == 200
    assert hit(app, peer="198.51.100.50", xff=["garbage"]) == 429


def test_ipv6_clients_are_grouped_by_64() -> None:
    app, _ = limited()
    for i in range(30):
        assert hit(app, peer=f"2001:db8:1:2::{i:x}") == 200
    assert hit(app, peer="2001:db8:1:2:ffff::1") == 429
    assert hit(app, peer="2001:db8:1:3::1") == 200
    assert hit(app, peer="::ffff:198.51.100.99") == 200  # IPv4-mapped: the IPv4 address


# ───────────────────────────── errors ─────────────────────────────


class ExplodingProvider(CatalogueProvider):
    def snapshot(self):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom (synthetic failure)")


def test_unexpected_error_is_a_generic_500_without_body_logging(caplog: pytest.LogCaptureFixture) -> None:
    sentinel = "zzBODYSENTINEL91"
    client = client_with(provider=ExplodingProvider(MemorySource()))
    with caplog.at_level(logging.ERROR, logger="bpf.api"):
        get = client.get(f"/api/stores?{sentinel}=1")
        post = client.post(
            f"/api/quote?q={sentinel}",
            json={"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": [sentinel]},  # a valid body
            headers={"X-Debug": sentinel},
        )
    for response in (get, post):
        assert response.status_code == 500
        assert response.json() == {"error": "internal", "fields": []}
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-security-policy"] == API_CSP
        assert_common_headers(response.headers)
        assert "boom" not in response.text
    assert "unhandled error in GET /api/stores" in caplog.text
    assert "unhandled error in POST /api/quote" in caplog.text
    assert "boom (synthetic failure)" in caplog.text  # the exception itself is logged server-side
    assert sentinel not in caplog.text  # never the query string, the headers or the body


def test_docs_disabled_by_default() -> None:
    client = client_with()
    for path in ("/api/docs", "/api/redoc", "/api/openapi.json", "/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_docs_enabled_on_request() -> None:
    client = client_with(options=ApiOptions(_env_file=None, enable_docs=True))
    spec = client.get("/api/openapi.json")
    assert spec.status_code == 200
    assert "/api/quote" in spec.json()["paths"]
    docs = client.get("/api/docs")
    assert docs.status_code == 200
    assert "cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in docs.headers["content-security-policy"]
    assert client.get("/api/redoc").status_code == 200


def test_hsts_on_static_and_errors(build: Path) -> None:
    client = client_with(web_build_dir=build, options=ApiOptions(_env_file=None, hsts=True))
    for path in ("/", "/service-worker.js", "/api/meta", "/api/nope", "/_app/missing"):
        assert client.get(path).headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_lifespan_with_injected_provider_opens_no_pool() -> None:
    with TestClient(app_with()) as client:  # runs the lifespan
        assert client.get("/api/health").json()["status"] == "ok"


def test_rate_limit_applies_to_every_status() -> None:
    app, _ = limited()
    statuses = [hit(app, path="/api/recipes/nincs") for _ in range(30)]
    assert statuses == [404] * 30
    assert hit(app, path="/api/recipes/nincs") == 429
