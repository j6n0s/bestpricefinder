"""Pure ASGI middlewares (docs/API.md "Common behaviour", docs/ARCHITECTURE.md "API security").

Order, outermost first (see :func:`bpf.api.app.create_app`)::

    SecurityHeadersMiddleware   headers on EVERY response (also 404/405/413/415/429/500), last-resort 500
    CORSMiddleware              only when BPF_ALLOWED_ORIGINS is set
    RateLimitMiddleware         /api only: per-client token bucket (120/min, burst 30) -> 429 + Retry-After
    JsonContentTypeMiddleware   POST endpoints only: application/json (UTF-8) or 415, before the body is read
    BodyLimitMiddleware         413 when Content-Length or the streamed body (chunked too) exceeds the limit,
                                before any parsing; the body is buffered (<= limit) and replayed to the app

They never log request bodies or query strings.
"""

from __future__ import annotations

import ipaddress
import logging
import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Collection, Mapping

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from bpf.api.errors import error_response

log = logging.getLogger("bpf.api")

API_CSP = "default-src 'none'; frame-ancestors 'none'"
HSTS_VALUE = "max-age=31536000; includeSubDomains"
SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("x-content-type-options", "nosniff"),
    ("referrer-policy", "no-referrer"),
    ("x-frame-options", "DENY"),
    ("cross-origin-opener-policy", "same-origin"),
    ("cross-origin-resource-policy", "same-origin"),
    ("permissions-policy", "geolocation=(self), camera=(), microphone=(), payment=(), usb=()"),
)
RATE_LIMIT_BURST = 30


def is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def _log_path(scope: Scope) -> str:
    """The request path for a log line: no query string, bounded, printable."""
    path = str(scope.get("path", ""))[:200]
    return path.encode("unicode_escape").decode("ascii")


class SecurityHeadersMiddleware:
    """Adds the security headers to every response and turns unhandled exceptions into a generic 500.

    ``Content-Security-Policy`` is set only when the response has none (the static site sends the SPA's
    policy); ``csp_overrides`` maps exact paths to a policy (the optional docs UI)."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False, csp_overrides: Mapping[str, str] | None = None):
        self.app = app
        self.hsts = hsts
        self.csp_overrides = dict(csp_overrides or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False
        default_csp = self.csp_overrides.get(scope.get("path", ""), API_CSP)

        async def send_with_headers(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = list(message.get("headers", []))
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS:
                    headers[name] = value
                if "content-security-policy" not in headers:
                    headers["content-security-policy"] = default_csp
                if self.hsts:
                    headers["strict-transport-security"] = HSTS_VALUE
                if "server" in headers:
                    del headers["server"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            log.exception("unhandled error in %s %s", scope.get("method", "?"), _log_path(scope))
            if started:
                raise
            await error_response(500, "internal")(scope, receive, send_with_headers)


# ───────────────────────────── rate limiting ─────────────────────────────


class TokenBucketLimiter:
    """Per-key token buckets: ``burst`` tokens, refilled at ``per_minute / 60`` tokens per second.

    Memory is bounded: at most ``max_keys`` buckets, least recently used evicted first (an evicted key simply
    starts again with a full bucket). Thread-safe."""

    def __init__(
        self,
        per_minute: int,
        burst: int = RATE_LIMIT_BURST,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 100_000,
    ) -> None:
        if per_minute <= 0 or burst <= 0:
            raise ValueError("per_minute and burst must be > 0")
        self.rate = per_minute / 60.0
        self.burst = float(burst)
        self.clock = clock
        self.max_keys = max_keys
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()
        self._lock = threading.Lock()

    def take(self, key: str) -> float | None:
        """Take one token: None when allowed, else the seconds until the next token."""
        with self._lock:
            now = self.clock()
            tokens, last = self._buckets.pop(key, (self.burst, now))
            tokens = min(self.burst, tokens + max(0.0, now - last) * self.rate)
            wait: float | None = None
            if tokens >= 1.0:
                tokens -= 1.0
            else:
                wait = (1.0 - tokens) / self.rate
            self._buckets[key] = (tokens, now)
            while len(self._buckets) > self.max_keys:
                self._buckets.popitem(last=False)
            return wait


def _parse_ip(text: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(text.strip())
    except ValueError:
        return None


def client_key(scope: Scope, *, trust_proxy_headers: bool) -> str:
    """Rate-limit key: the socket peer, or (behind a trusted proxy) the right-most X-Forwarded-For entry.

    IPv6 clients are grouped by /64 (one subscriber usually owns a whole /64); IPv4-mapped IPv6 is IPv4."""
    if trust_proxy_headers:
        values = [value for name, value in scope.get("headers", []) if name.lower() == b"x-forwarded-for"]
        if values:
            last = b",".join(values).decode("latin-1").split(",")[-1]
            ip = _parse_ip(last)
            if ip is not None:
                return _ip_key(ip)
    client = scope.get("client")
    host = str(client[0]) if client else "unknown"
    ip = _parse_ip(host)
    return _ip_key(ip) if ip is not None else host[:100]


def _ip_key(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)


class RateLimitMiddleware:
    """429 ``rate_limited`` + ``Retry-After`` (whole seconds) once a client's bucket is empty (/api only)."""

    def __init__(self, app: ASGIApp, *, limiter: TokenBucketLimiter, trust_proxy_headers: bool) -> None:
        self.app = app
        self.limiter = limiter
        self.trust_proxy_headers = trust_proxy_headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and is_api_path(scope.get("path", "")):
            wait = self.limiter.take(client_key(scope, trust_proxy_headers=self.trust_proxy_headers))
            if wait is not None:
                retry_after = str(max(1, math.ceil(wait)))
                await error_response(429, "rate_limited", headers={"Retry-After": retry_after})(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)


# ───────────────────────────── content type and body size ─────────────────────────────


def is_json_content_type(headers: Headers) -> bool:
    """Exactly one Content-Type, ``application/json``, with no charset or charset UTF-8."""
    values = headers.getlist("content-type")
    if len(values) != 1:
        return False
    media_type, *params = values[0].split(";")
    if media_type.strip().lower() != "application/json":
        return False
    for param in params:
        name, _, value = param.partition("=")
        if name.strip().lower() == "charset" and value.strip().strip('"').lower() not in ("utf-8", "utf8"):
            return False
    return True


class JsonContentTypeMiddleware:
    """415 ``unsupported_media_type`` for a POST to a JSON endpoint without a JSON content type.

    Only the given paths are checked, so a POST to a path that does not take one still gets 404/405."""

    def __init__(self, app: ASGIApp, *, json_paths: Collection[str]) -> None:
        self.app = app
        self.json_paths = frozenset(json_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") in self.json_paths
            and not is_json_content_type(Headers(scope=scope))
        ):
            await error_response(415, "unsupported_media_type")(scope, receive, send)
            return
        await self.app(scope, receive, send)


def declared_length(value: str | None) -> int | None:
    """A Content-Length header as an int (capped at 10**18), or None when absent or not ASCII digits."""
    if value is None:
        return None
    text = value.strip()
    if not text or not text.isascii() or not text.isdigit():
        return None
    return int(text) if len(text) <= 18 else 10**18


class BodyLimitMiddleware:
    """413 ``payload_too_large`` before parsing: a declared Content-Length above the limit is refused
    without reading; otherwise the body is read as it streams (chunked bodies too) and refused as soon as
    it exceeds the limit. An accepted body is replayed to the app in one message."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = declared_length(Headers(scope=scope).get("content-length"))
        if declared is not None and declared > self.max_bytes:
            await error_response(413, "payload_too_large")(scope, receive, send)
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return  # the client went away; nothing to answer
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await error_response(413, "payload_too_large")(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
