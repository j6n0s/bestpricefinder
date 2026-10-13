"""Security middlewares and static hosting, without a database (in-memory SYNTHETIC catalogue,
tests/fixtures/api/memory.py; a fake ``web/build`` made in a temporary directory).

Covers: security headers on every kind of response (incl. static files, 404, 405, 413, 415, 429, 500); the
SPA's CSP header = the HTML meta policy + ``frame-ancestors 'none'``; path traversal (dot segments, encoded
slashes and backslashes, absolute paths, NUL, symlinks) never leaving the build; static caching; the body
limit for declared, streamed and chunked bodies (also through a real uvicorn server); the rate limiter with
and without trusted proxy headers; the bounds on the heavy POST work (per-client share, bounded wait, no work
for a client that hung up); generic 500s that log no request body; WebSocket upgrades that log no client
address; the docs UI switch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from pydantic import ValidationError

import bpf.api.__main__ as api_main
from bpf.api import routes
from bpf.api.app import create_app
from bpf.api.repo import CatalogueProvider
from bpf.api.routes import HeavyRunner
from bpf.api.security import API_CSP
from bpf.config import Settings, get_settings
from tests.fixtures.api.asgi import JSON_HEADERS, raw_request, request_async
from tests.fixtures.api.memory import MemorySource, app_with, client_with, memory_provider
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


def test_service_worker_is_the_startup_snapshot_like_the_page(build: Path) -> None:
    """A new build written while the server runs (build-web.sh before the restart) must not pair the NEW
    worker (new precache list) with the OLD in-memory page: the worker would cache the old shell under the
    new version and keep it after the restart. Both are read at startup, so they come from one build."""
    (build / "service-worker.js").write_text("/* synthetic worker v1 */\n")
    client = client_with(web_build_dir=build)
    first = client.get("/service-worker.js")
    assert (first.status_code, first.text) == (200, "/* synthetic worker v1 */\n")
    assert first.headers["content-type"] == "text/javascript; charset=utf-8"
    assert first.headers["cache-control"] == "no-cache"
    assert first.headers["content-security-policy"] == HTML_POLICY
    assert_common_headers(first.headers)
    etag = first.headers["etag"]
    # a new build lands on disk (new content, size and mtime); the running server keeps its pair
    (build / "service-worker.js").write_text("/* synthetic worker v2, a longer file */\n")
    (build / "index.html").write_text(INDEX_HTML.replace("SPA-FALLBACK-PAGE", "NEW-BUILD-PAGE"))
    again = client.get("/service-worker.js")
    assert (again.status_code, again.text, again.headers["etag"]) == (
        200,
        "/* synthetic worker v1 */\n",
        etag,
    )
    cached = client.get("/service-worker.js", headers={"If-None-Match": etag})
    assert (cached.status_code, cached.content) == (304, b"")
    assert cached.headers["content-security-policy"] == HTML_POLICY
    head = client.head("/service-worker.js")
    assert (head.status_code, head.content, head.headers["etag"]) == (200, b"", etag)
    page = client.get("/")
    assert (page.text, page.headers["content-security-policy"]) == (INDEX_HTML, HTML_POLICY)
    # after the restart: the new pair
    restarted = client_with(web_build_dir=build)
    assert restarted.get("/service-worker.js").text == "/* synthetic worker v2, a longer file */\n"
    assert "NEW-BUILD-PAGE" in restarted.get("/").text


def test_build_without_a_service_worker(build: Path) -> None:
    (build / "service-worker.js").unlink()
    client = client_with(web_build_dir=build)
    response = client.get("/service-worker.js")  # a client-side route, like any other unknown path
    assert (response.status_code, response.text) == (200, INDEX_HTML)
    (build / "service-worker.js").write_text("/* appeared after startup */\n")
    assert client.get("/service-worker.js").text == "/* appeared after startup */\n"  # served from disk


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
    "path",
    [
        "/.",
        "/..",
        "/./index.html",
        "/terv/./x",
        "/icons/../index.html",
        "/.well-known/security.txt",
        "/terv\\x",
        "/terv\x00",
        "/" + "a" * 1024,  # 1,025 characters
    ],
)
def test_dot_segments_backslashes_nul_and_long_paths_are_404(build: Path, path: str) -> None:
    """docs/API.md implementation decisions: such paths are a JSON 404, never the SPA page."""
    status, headers, body = raw_request(app_with(web_build_dir=build), path)
    assert (status, json.loads(body)) == (404, {"error": "not_found", "fields": []})
    assert headers["content-security-policy"] == API_CSP


def test_a_path_of_exactly_1024_characters_still_gets_the_spa(build: Path) -> None:
    status, _, body = raw_request(app_with(web_build_dir=build), "/" + "a" * 1023)
    assert (status, body) == (200, INDEX_HTML.encode())


@pytest.mark.parametrize(
    "path",
    ["/api/health", "/api/stores", "/api/recipes/zz-porkolt", "/api/ingredients/rizs/history", "/api/quote"],
)
def test_head_on_api_endpoints_is_405(path: str) -> None:
    """docs/API.md implementation decisions: HEAD on API endpoints is 405 (static paths accept it)."""
    response = client_with().head(path)
    assert response.status_code == 405
    assert response.headers["allow"] == ("POST" if path == "/api/quote" else "GET")
    assert_common_headers(response.headers)


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
    proxy = "127.0.0.1"  # the local reverse proxy
    # the right-most entry (the one the trusted proxy appended) is the client, whatever the client put first
    for i in range(30):
        assert hit(app, peer=proxy, xff=[f"10.0.0.{i}, 203.0.113.5"]) == 200
    assert hit(app, peer=proxy, xff=["10.9.9.9, 203.0.113.5"]) == 429
    # several headers: the last value counts
    assert hit(app, peer=proxy, xff=["203.0.113.5", "203.0.113.6"]) == 200
    assert hit(app, peer=proxy, xff=["203.0.113.6"]) == 200
    # an unparsable entry falls back to the socket peer
    for _ in range(30):
        assert hit(app, peer="::1", xff=["not-an-ip"]) == 200
    assert hit(app, peer="::1", xff=["garbage"]) == 429


def test_forwarded_for_ignored_from_untrusted_peer_even_when_trusted() -> None:
    """BPF_TRUST_PROXY_HEADERS=true with the server bound to a LAN address: a client that is not the local
    proxy cannot get a fresh bucket per request by rotating X-Forwarded-For."""
    app, _ = limited(trust=True)
    for i in range(30):
        assert hit(app, peer="198.51.100.8", xff=[f"203.0.113.{i}"]) == 200
    assert hit(app, peer="198.51.100.8", xff=["203.0.113.200"]) == 429
    assert hit(app, peer="198.51.100.8", xff=["10.0.0.1, 203.0.113.201"]) == 429
    assert hit(app, peer="::ffff:198.51.100.8", xff=["203.0.113.202"]) == 429  # IPv4-mapped: the same client
    assert hit(app, peer="127.0.0.1", xff=["203.0.113.203"]) == 200  # the proxy's header still counts


def test_ipv6_clients_are_grouped_by_64() -> None:
    app, _ = limited()
    for i in range(30):
        assert hit(app, peer=f"2001:db8:1:2::{i:x}") == 200
    assert hit(app, peer="2001:db8:1:2:ffff::1") == 429
    assert hit(app, peer="2001:db8:1:3::1") == 200
    assert hit(app, peer="::ffff:198.51.100.99") == 200  # IPv4-mapped: the IPv4 address


# ───────────────────────────── heavy POST work ─────────────────────────────

RATE_LIMITED = {"error": "rate_limited", "fields": []}


class SlowQuotes:
    """Patches ``compute_quote``: a quote with ``include_loyalty: true`` blocks its worker thread until
    :attr:`release` is set (a stand-in for a maximum quote); every computation is counted."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.release = threading.Event()
        self._lock = threading.Lock()
        self._started = 0
        real = routes.compute_quote

        def compute(snap: Any, req: Any) -> bytes:
            with self._lock:
                self._started += 1
            if req.include_loyalty and not self.release.wait(30):
                raise RuntimeError("never released")
            return real(snap, req)

        monkeypatch.setattr(routes, "compute_quote", compute)

    @property
    def started(self) -> int:
        with self._lock:
            return self._started


async def post_quote(
    app: FastAPI, peer: str, *, slow: bool, disconnect: bool = False
) -> tuple[int, dict[str, str], bytes]:
    body = {"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": ["alfa-1"], "include_loyalty": slow}
    return await request_async(
        app,
        "/api/quote",
        method="POST",
        headers=JSON_HEADERS,
        chunks=[json.dumps(body).encode()],
        client=(peer, 40000),
        disconnect=disconnect,
    )


async def until(condition: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached in time")
        await asyncio.sleep(0.01)


def test_one_client_cannot_take_every_heavy_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """One client floods maximum quotes (well inside the rate limit's burst): it gets at most 2 of the 4
    workers, 6 more of its requests wait in its own line, the rest are refused at once, and another
    client's quote is answered straight away while the flood is still computing."""
    slow = SlowQuotes(monkeypatch)
    app = app_with()
    flooder, other = "198.51.100.20", "198.51.100.21"

    async def scenario() -> None:
        flood = [asyncio.create_task(post_quote(app, flooder, slow=True)) for _ in range(12)]
        await until(lambda: slow.started >= 2 and sum(task.done() for task in flood) >= 4)
        await asyncio.sleep(0.1)  # nothing else of the flood starts or finishes
        assert (slow.started, sum(task.done() for task in flood)) == (2, 4)
        for task in flood:
            if task.done():
                status, headers, body = task.result()
                assert (status, headers["retry-after"], json.loads(body)) == (429, "1", RATE_LIMITED)
        started = time.monotonic()
        status, _, body = await asyncio.wait_for(post_quote(app, other, slow=False), 5)
        assert status == 200
        assert json.loads(body)["stores"][0]["store_id"] == "alfa-1"
        assert time.monotonic() - started < 3
        assert app.state.heavy.pending() == {flooder: 8}
        slow.release.set()
        results = await asyncio.wait_for(asyncio.gather(*flood), 30)
        assert sorted(status for status, _, _ in results) == [200] * 8 + [429] * 4
        assert slow.started == 2 + 1 + 6
        assert app.state.heavy.pending() == {}

    asyncio.run(scenario())


def test_a_request_whose_client_hung_up_is_dropped_before_the_work(monkeypatch: pytest.MonkeyPatch) -> None:
    slow = SlowQuotes(monkeypatch)
    app = app_with()

    async def scenario() -> None:
        peers = ["198.51.100.30", "198.51.100.30", "198.51.100.31", "198.51.100.31"]
        holders = [asyncio.create_task(post_quote(app, peer, slow=True)) for peer in peers]
        await until(lambda: slow.started == 4)  # every worker is busy
        gone = asyncio.create_task(post_quote(app, "198.51.100.32", slow=False, disconnect=True))
        await until(lambda: app.state.heavy.pending().get("198.51.100.32") == 1)
        slow.release.set()
        results = await asyncio.wait_for(asyncio.gather(*holders), 30)
        assert [status for status, _, _ in results] == [200] * 4
        status, _, body = await asyncio.wait_for(gone, 30)
        assert (status, body) == (499, b"")
        assert slow.started == 4  # nothing was computed for the client that hung up
        assert app.state.heavy.pending() == {}

    asyncio.run(scenario())


def test_the_wait_for_a_worker_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Many clients (say, many IPv6 /64s) keep every worker busy: a request waits at most ``wait_s`` and is
    then refused with Retry-After instead of queueing without end."""
    slow = SlowQuotes(monkeypatch)
    app = app_with()
    app.state.heavy = HeavyRunner(wait_s=0.3)

    async def scenario() -> None:
        peers = ["198.51.100.40", "198.51.100.40", "198.51.100.41", "198.51.100.41"]
        holders = [asyncio.create_task(post_quote(app, peer, slow=True)) for peer in peers]
        await until(lambda: slow.started == 4)
        started = time.monotonic()
        status, headers, body = await asyncio.wait_for(post_quote(app, "198.51.100.42", slow=False), 5)
        waited = time.monotonic() - started
        assert (status, headers["retry-after"], json.loads(body)) == (429, "1", RATE_LIMITED)
        assert headers["cache-control"] == "no-store"
        assert 0.25 <= waited < 3
        slow.release.set()
        results = await asyncio.wait_for(asyncio.gather(*holders), 30)
        assert [status for status, _, _ in results] == [200] * 4
        assert slow.started == 4
        assert app.state.heavy.pending() == {}
        status, _, _ = await asyncio.wait_for(post_quote(app, "198.51.100.42", slow=False), 5)
        assert status == 200  # served again once a worker is free

    asyncio.run(scenario())


def test_heavy_runner_shares_the_rate_limit_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Behind the local proxy the share is per forwarded client, not one share for the proxy."""
    assert app_with().state.heavy.trust_proxy_headers is False
    app = app_with(trust_proxy_headers=True)
    assert app.state.heavy.trust_proxy_headers is True
    slow = SlowQuotes(monkeypatch)

    async def via_proxy(client: str) -> tuple[int, dict[str, str], bytes]:
        body = {
            "lines": [{"ingredient_id": "rizs", "qty": 1}],
            "store_ids": ["alfa-1"],
            "include_loyalty": True,
        }
        return await request_async(
            app,
            "/api/quote",
            method="POST",
            headers=[*JSON_HEADERS, (b"x-forwarded-for", client.encode())],
            chunks=[json.dumps(body).encode()],
            client=("127.0.0.1", 50000),
        )

    async def scenario() -> None:
        tasks = [asyncio.create_task(via_proxy(c)) for c in ("203.0.113.1", "203.0.113.1", "203.0.113.2")]
        await until(lambda: slow.started == 3)  # three running: two clients, not one proxy
        assert app.state.heavy.pending() == {"203.0.113.1": 2, "203.0.113.2": 1}
        slow.release.set()
        assert [r[0] for r in await asyncio.wait_for(asyncio.gather(*tasks), 30)] == [200] * 3

    asyncio.run(scenario())


def test_heavy_runner_rejects_inconsistent_bounds() -> None:
    for kwargs in ({"per_client": 0}, {"per_client": 5}, {"per_client_pending": 1}, {"wait_s": 0}):
        with pytest.raises(ValueError, match="per_client"):
            HeavyRunner(**kwargs)  # type: ignore[arg-type]


def test_hung_up_client_through_a_real_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """uvicorn does not cancel the app when the client hangs up; the runner sees the disconnect through
    ``receive`` once its turn comes, and skips the work."""
    slow = SlowQuotes(monkeypatch)
    app = app_with()
    runner = HeavyRunner(per_client=4)  # every request here comes from 127.0.0.1
    app.state.heavy = runner
    port = free_port()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", lifespan="off", server_header=False
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_for(lambda: server.started, "uvicorn did not start")
    quote = {"lines": [{"ingredient_id": "rizs", "qty": 1}], "store_ids": ["alfa-1"]}
    statuses: list[int] = []

    def hold() -> None:
        response = httpx.post(
            f"http://127.0.0.1:{port}/api/quote", json={**quote, "include_loyalty": True}, timeout=30
        )
        statuses.append(response.status_code)

    def pending() -> int:
        # read from this thread while the server's loop updates it: retry a torn read
        for _ in range(100):
            try:
                return sum(runner.pending().values())
            except RuntimeError:  # pragma: no cover - dictionary changed size during iteration
                continue
        raise AssertionError("could not read the runner's state")

    holders = [threading.Thread(target=hold) for _ in range(4)]
    try:
        for holder in holders:
            holder.start()
        wait_for(lambda: slow.started == 4, "the holders did not start")
        body = json.dumps(quote).encode()
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            sock.sendall(
                b"POST /api/quote HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode()
                + body
            )
            wait_for(lambda: pending() == 5, "the request did not reach the runner")
        time.sleep(0.5)  # the server notices the closed connection
        slow.release.set()
        for holder in holders:
            holder.join(30)
        wait_for(lambda: pending() == 0, "the dropped request did not finish")
        assert statuses == [200] * 4
        assert slow.started == 4  # the request of the client that hung up was never computed
    finally:
        slow.release.set()
        server.should_exit = True
        thread.join(timeout=10)


def wait_for(condition: Any, message: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError(message)
        time.sleep(0.02)


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


def main_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *argv: str) -> dict[str, Any]:
    """The keyword arguments ``python -m bpf.api`` passes to ``uvicorn.run`` (with proxy headers trusted)."""
    captured: dict[str, Any] = {}

    def run(target: str, **kwargs: Any) -> None:
        captured.update(kwargs, target=target)

    env_file = tmp_path / "env"
    env_file.write_text("BPF_TRUST_PROXY_HEADERS=true\n", encoding="utf-8")
    monkeypatch.delenv("BPF_TRUST_PROXY_HEADERS", raising=False)
    monkeypatch.setenv("BPF_ENV_FILE", str(env_file))
    monkeypatch.setattr(api_main.uvicorn, "run", run)
    get_settings.cache_clear()
    try:
        assert api_main.main(list(argv)) == 0
    finally:
        get_settings.cache_clear()
    return captured


def test_main_turns_websockets_and_the_access_log_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    options = main_options(monkeypatch, tmp_path)
    assert (options["target"], options["factory"]) == ("bpf.api.app:create_app", True)
    assert (options["host"], options["port"]) == ("127.0.0.1", 8000)
    assert options["ws"] == "none"
    assert options["access_log"] is False
    assert options["server_header"] is False
    assert options["proxy_headers"] is True
    assert main_options(monkeypatch, tmp_path, "--access-log")["access_log"] is True


def test_websocket_upgrades_log_no_client_address(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """With the options of ``python -m bpf.api`` (access log off, proxy headers trusted, log level info), an
    ``Upgrade: websocket`` request must not make uvicorn log the client's address or the query string: it is
    served as plain HTTP, with the security headers (uvicorn's own WebSocket rejection logs both at INFO)."""
    port = free_port()
    options = main_options(monkeypatch, tmp_path, "--port", str(port))
    del options["target"], options["factory"]
    config = uvicorn.Config(app_with(trust_proxy_headers=True), log_config=None, **options)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    with caplog.at_level(logging.DEBUG):
        thread.start()
        try:
            wait_for(lambda: server.started, "uvicorn did not start")
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
        finally:
            server.should_exit = True
            thread.join(timeout=10)
    server_lines = [r.getMessage() for r in caplog.records if r.name.startswith(("uvicorn", "bpf"))]
    assert any("Uvicorn running" in line for line in server_lines)  # INFO lines were captured
    for line in server_lines:
        assert "203.0.113.77" not in line, line
        assert "zz9wsmarker" not in line, line
        assert "WebSocket /" not in line, line
    assert response.status_code == 200  # plain HTTP, not a 101 or uvicorn's bare 403
    assert_common_headers(response.headers)


def test_docs_disabled_by_default() -> None:
    client = client_with()
    for path in ("/api/docs", "/api/redoc", "/api/openapi.json", "/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_docs_enabled_on_request() -> None:
    client = client_with(enable_docs=True)
    spec = client.get("/api/openapi.json")
    assert spec.status_code == 200
    assert "/api/quote" in spec.json()["paths"]
    docs = client.get("/api/docs")
    assert docs.status_code == 200
    assert "cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in docs.headers["content-security-policy"]
    assert client.get("/api/redoc").status_code == 200


def test_switches_are_settings_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """BPF_HSTS and BPF_ENABLE_DOCS are bpf.config.Settings fields: off by default, read from the env file
    with the real environment winning, validated without echoing the input, frozen; create_app() without
    settings takes them from get_settings()."""
    for name in ("BPF_HSTS", "BPF_ENABLE_DOCS"):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (defaults.hsts, defaults.enable_docs) == (False, False)
    env_file = tmp_path / "env"
    env_file.write_text("BPF_HSTS=true\nBPF_ENABLE_DOCS=1\n", encoding="utf-8")
    from_file = Settings(_env_file=env_file)  # type: ignore[call-arg]
    assert (from_file.hsts, from_file.enable_docs) == (True, True)
    monkeypatch.setenv("BPF_HSTS", "false")
    assert Settings(_env_file=env_file).hsts is False  # type: ignore[call-arg]  # the environment wins
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, enable_docs="zzSENTINEL")  # type: ignore[call-arg]
    assert "zzSENTINEL" not in str(caught.value)
    with pytest.raises(ValidationError):
        from_file.hsts = False  # type: ignore[misc]  # frozen
    monkeypatch.delenv("BPF_HSTS")
    monkeypatch.setenv("BPF_ENV_FILE", str(env_file))
    monkeypatch.setenv("BPF_WEB_BUILD_DIR", str(tmp_path / "no-build"))
    get_settings.cache_clear()
    try:
        client = TestClient(create_app(catalogue_provider=memory_provider()))
        assert client.get("/api/openapi.json").status_code == 200
        hsts = client.get("/api/health").headers["strict-transport-security"]
        assert hsts == "max-age=31536000; includeSubDomains"
    finally:
        get_settings.cache_clear()


def test_hsts_on_static_and_errors(build: Path) -> None:
    client = client_with(web_build_dir=build, hsts=True)
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
