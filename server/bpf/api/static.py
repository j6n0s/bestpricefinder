"""Serve the SPA build (``web/build``, adapter-static) next to /api (docs/API.md "Static hosting").

* Only GET and HEAD, only for paths outside ``/api`` (an unknown /api path stays a JSON 404).
* A request path maps to a file only after it is resolved (symlinks included) and checked to lie inside the
  build directory; ``..``, ``.``-prefixed segments, backslashes and NUL bytes are refused outright (404), so
  path traversal (``/..%2f..``, encoded backslashes, absolute paths) can never leave the build directory.
* An existing file is served with ``Cache-Control: public, max-age=31536000, immutable`` under
  ``/_app/immutable/`` and ``no-cache`` otherwise (``index.html``, ``service-worker.js``, the manifest, ...).
* Any other path is a client-side route: the fallback page ``index.html`` (read once at startup, so the page
  and its CSP header always match) with ``no-cache``. A missing file under ``/_app/`` is a 404 instead, so a
  stale client never receives HTML for a JavaScript chunk.
* CSP: SvelteKit writes the policy (with the hash of its inline bootstrap script) into a ``<meta
  http-equiv="content-security-policy">`` of the HTML. At startup that policy is read from the fallback page
  and sent as the ``Content-Security-Policy`` header with ``frame-ancestors 'none'`` added (a meta tag cannot
  carry it). Every static response carries it, which also makes it the policy of the service worker script.
  Without a usable meta policy a strict fallback policy is used (fail closed).
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Final

import anyio.to_thread
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import BaseRoute, Match, NoMatchFound
from starlette.types import Receive, Scope, Send

from bpf.api.caching import etag_matches
from bpf.api.errors import error_response
from bpf.api.security import is_api_path

log = logging.getLogger("bpf.api")

FRAME_ANCESTORS: Final = "frame-ancestors 'none'"
STRICT_HTML_POLICY: Final = (
    "default-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
CACHE_IMMUTABLE: Final = "public, max-age=31536000, immutable"
CACHE_REVALIDATE: Final = "no-cache"
IMMUTABLE_PREFIX: Final = "_app/immutable/"
APP_PREFIX: Final = "_app/"
MAX_PATH_LENGTH: Final = 1024

CONTENT_TYPES: Final[dict[str, str]] = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".txt": "text/plain; charset=utf-8",
    ".map": "application/json",
}


class _CspMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.policies: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        values = {name.lower(): value for name, value in attrs if value is not None}
        if values.get("http-equiv", "").strip().lower() == "content-security-policy" and "content" in values:
            self.policies.append(values["content"])


def meta_csp(html: str) -> str | None:
    """The first ``<meta http-equiv="content-security-policy">`` policy of the page, or None."""
    parser = _CspMetaParser()
    parser.feed(html)
    parser.close()
    return parser.policies[0] if parser.policies else None


def header_policy(meta_policy: str | None) -> str:
    """The header value: the meta policy (whitespace collapsed, any frame-ancestors dropped) plus
    ``frame-ancestors 'none'``; the strict fallback when the meta policy is missing or not header-safe."""
    if meta_policy is None:
        return STRICT_HTML_POLICY
    directives = [" ".join(part.split()) for part in meta_policy.split(";")]
    kept = [d for d in directives if d and d.split()[0].lower() != "frame-ancestors"]
    if not kept:
        return STRICT_HTML_POLICY
    policy = "; ".join([*kept, FRAME_ANCESTORS])
    if not all(0x20 <= ord(ch) <= 0x7E for ch in policy) or "," in policy:
        return STRICT_HTML_POLICY
    return policy


@dataclass(frozen=True, slots=True)
class StaticFile:
    path: Path
    cache_control: str
    content_type: str


FALLBACK: Final = "fallback"
NOT_FOUND: Final = "not_found"
type Lookup = StaticFile | str


class StaticSite:
    """A loaded ``web/build``: its resolved root, the fallback page and the header policy."""

    def __init__(self, root: Path, index_html: bytes, policy: str) -> None:
        self.root = root
        self.index_html = index_html
        self.index_etag = '"' + hashlib.sha256(index_html).hexdigest() + '"'
        self.policy = policy

    @classmethod
    def load(cls, build_dir: Path) -> StaticSite | None:
        """The site, or None (API only) when the directory or its ``index.html`` does not exist."""
        try:
            root = build_dir.resolve(strict=True)
            index = (root / "index.html").read_bytes()
        except OSError:
            return None
        if not root.is_dir():
            return None
        meta = meta_csp(index.decode("utf-8", errors="replace"))
        policy = header_policy(meta)
        if meta is None or policy == STRICT_HTML_POLICY:
            log.warning("web build: no usable CSP meta tag in index.html; serving a strict fallback policy")
        return cls(root, index, policy)

    def lookup(self, url_path: str) -> Lookup:
        """Map a decoded request path to a file, the fallback page or NOT_FOUND (see the module doc)."""
        if len(url_path) > MAX_PATH_LENGTH or "\x00" in url_path or "\\" in url_path:
            return NOT_FOUND
        relative = url_path.lstrip("/")
        parts = [part for part in relative.split("/") if part]
        if any(part.startswith(".") for part in parts):
            return NOT_FOUND
        if not parts or parts == ["index.html"]:
            return FALLBACK
        try:
            candidate = self.root.joinpath(*parts).resolve()
            if not candidate.is_relative_to(self.root):
                return NOT_FOUND
            if candidate.is_file():
                rel = PurePosixPath(*parts).as_posix()
                cache = CACHE_IMMUTABLE if rel.startswith(IMMUTABLE_PREFIX) else CACHE_REVALIDATE
                return StaticFile(candidate, cache, _content_type(candidate))
        except OSError, ValueError:
            return NOT_FOUND
        if relative.startswith(APP_PREFIX):
            return NOT_FOUND
        return FALLBACK

    def response(self, request: Request, found: Lookup) -> Response:
        if isinstance(found, StaticFile):
            return self._file_response(request, found)
        if found == FALLBACK:
            headers = {
                "Cache-Control": CACHE_REVALIDATE,
                "ETag": self.index_etag,
                "Content-Security-Policy": self.policy,
            }
            if etag_matches(request.headers.get("if-none-match"), self.index_etag):
                return Response(status_code=304, headers=headers)
            return Response(self.index_html, media_type=CONTENT_TYPES[".html"], headers=headers)
        return error_response(404, "not_found")

    def _file_response(self, request: Request, found: StaticFile) -> Response:
        try:
            stat = found.path.stat()
        except OSError:
            return error_response(404, "not_found")
        etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
        headers = {"Cache-Control": found.cache_control, "ETag": etag, "Content-Security-Policy": self.policy}
        if etag_matches(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=headers)
        return FileResponse(found.path, headers=headers, media_type=found.content_type, stat_result=stat)


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in CONTENT_TYPES:
        return CONTENT_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


class SpaRoute(BaseRoute):
    """Catch-all route for every non-/api path: GET/HEAD are served by the site, other methods get 405."""

    def __init__(self, site: StaticSite) -> None:
        self.site = site

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope["type"] != "http" or is_api_path(scope.get("path", "")):
            return Match.NONE, {}
        if scope.get("method") in ("GET", "HEAD"):
            return Match.FULL, {}
        return Match.PARTIAL, {}

    def url_path_for(self, name: str, /, **path_params: object) -> object:
        raise NoMatchFound(name, path_params)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("method") not in ("GET", "HEAD"):
            raise HTTPException(status_code=405, headers={"Allow": "GET, HEAD"})
        request = Request(scope, receive)
        found = await anyio.to_thread.run_sync(self.site.lookup, scope.get("path", "/"))
        response = self.site.response(request, found)
        await response(scope, receive, send)
