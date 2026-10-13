"""JSON responses with ETag / If-None-Match and Cache-Control (docs/API.md "Caching").

The ETag is a strong validator: the SHA-256 of the data date and the exact response body, so it changes
whenever either does. ``If-None-Match`` is compared with the weak comparison RFC 9110 prescribes for it
(``W/`` prefixes ignored); ``*`` matches any current representation.
"""

from __future__ import annotations

import hashlib
from datetime import date

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

from bpf.api.errors import JSON_MEDIA_TYPE, NO_STORE

CACHE_STATIC_DATA = "public, max-age=3600"  # /api/stores, /api/ingredients
CACHE_SHORT = "public, max-age=300"  # /api/meta, /api/recipes*, history
CACHE_NONE = NO_STORE  # /api/health and every POST


def make_etag(data_date: date | None, body: bytes) -> str:
    digest = hashlib.sha256()
    digest.update((data_date.isoformat() if data_date is not None else "none").encode("ascii"))
    digest.update(b"\n")
    digest.update(body)
    return f'"{digest.hexdigest()}"'


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    if if_none_match is None:
        return False
    for candidate in if_none_match.split(","):
        tag = candidate.strip()
        if tag == "*":
            return True
        if tag.startswith("W/"):
            tag = tag[2:]
        if tag == etag:
            return True
    return False


def model_body(model: BaseModel) -> bytes:
    """Compact, deterministic JSON (field order = model order)."""
    return model.model_dump_json().encode("utf-8")


def cached_json(request: Request, body: bytes, *, data_date: date | None, cache_control: str) -> Response:
    """200 with ETag + Cache-Control, or 304 Not Modified when ``If-None-Match`` matches."""
    etag = make_etag(data_date, body)
    headers = {"ETag": etag, "Cache-Control": cache_control}
    if etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(body, media_type=JSON_MEDIA_TYPE, headers=headers)


def no_store_json(body: bytes, *, status_code: int = 200) -> Response:
    return Response(
        body, status_code=status_code, media_type=JSON_MEDIA_TYPE, headers={"Cache-Control": NO_STORE}
    )
