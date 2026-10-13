"""Error responses (docs/API.md "Errors"): every failure becomes ``{"error": <code>, "fields": [...]}``.

* Validation errors are 422 ``invalid_request`` with dotted field paths only. A path never contains input:
  list indexes and the names of known request fields are kept, and the path is cut at the first component
  that is anything else (an unexpected key, a dict key sent by the client), so an unknown field ``"x"``
  inside ``lines[0]`` is reported as ``lines.0``. Messages, inputs and contexts are never returned.
* Unexpected exceptions are 500 ``internal`` without details; they are logged server-side (path only, never
  the query string or the body) by :class:`bpf.api.security.SecurityHeadersMiddleware`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, get_args

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import Response

from bpf.api.schemas import (
    ErrorCode,
    ErrorResponse,
    ListRequest,
    PlanCheckRequest,
    PlanSuggestRequest,
    QuoteRequest,
    Slot,
)

log = logging.getLogger("bpf.api")

JSON_MEDIA_TYPE = "application/json; charset=utf-8"
NO_STORE = "no-store"
MAX_FIELDS = 100

STATUS_ERROR_CODES: Mapping[int, ErrorCode] = {
    400: "invalid_request",  # FastAPI's "error parsing the body"; reported as 422 like every bad input
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "invalid_request",
    429: "rate_limited",
    500: "internal",
    503: "no_data",
}


class ApiError(Exception):
    """An error the API reports on purpose (never carries input values)."""

    status_code: int = 500
    code: ErrorCode = "internal"

    def __init__(self, fields: Iterable[str] = (), headers: Mapping[str, str] | None = None) -> None:
        super().__init__(self.code)
        self.fields = tuple(fields)
        self.headers = dict(headers or {})


class InvalidRequest(ApiError):
    status_code = 422
    code = "invalid_request"


class NotFound(ApiError):
    status_code = 404
    code = "not_found"


class NoData(ApiError):
    """503: no successful daily ingest yet, or the database cannot be reached and nothing is cached."""

    status_code = 503
    code = "no_data"


def error_response(
    status_code: int, code: ErrorCode, fields: Sequence[str] = (), headers: Mapping[str, str] | None = None
) -> Response:
    """The JSON error body with ``Cache-Control: no-store`` (security headers are added by the middleware)."""
    body = ErrorResponse(error=code, fields=list(fields)).model_dump_json().encode("utf-8")
    all_headers = {"Cache-Control": NO_STORE, **(headers or {})}
    return Response(body, status_code=status_code, media_type=JSON_MEDIA_TYPE, headers=all_headers)


# ───────────────────────────── field paths without values ─────────────────────────────


def _model_field_names(model: type[BaseModel], seen: set[type[BaseModel]]) -> set[str]:
    """Field names of ``model`` and of every model nested in its annotations."""
    if model in seen:
        return set()
    seen.add(model)
    names: set[str] = set()
    for name, info in model.model_fields.items():
        names.add(name)
        names |= _annotation_names(info.annotation, seen)
    return names


def _annotation_names(annotation: Any, seen: set[type[BaseModel]]) -> set[str]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _model_field_names(annotation, seen)
    names: set[str] = set()
    for arg in get_args(annotation):
        names |= _annotation_names(arg, seen)
    return names


def _known_names() -> frozenset[str]:
    seen: set[type[BaseModel]] = set()
    names: set[str] = set()
    for model in (ListRequest, QuoteRequest, PlanSuggestRequest, PlanCheckRequest):
        names |= _model_field_names(model, seen)
    names |= set(get_args(Slot))  # PlanDayIO.meals keys are reported when they are valid slots
    names |= {"slot", "tag", "q", "chain", "days", "id"}  # query and path parameters
    return frozenset(names)


KNOWN_FIELD_NAMES: frozenset[str] = _known_names()
_LOCATIONS = frozenset({"query", "path", "header", "cookie"})


def field_path(loc: Sequence[Any]) -> str:
    """Dotted path for a pydantic ``loc``; body paths are relative to the body (``lines.0.qty``), parameter
    paths keep their location (``query.q``). Cut at the first component that is not a list index or a known
    field name, so client-chosen keys never appear. An empty path is ``body``."""
    parts = list(loc)
    out: list[str] = []
    if parts and parts[0] == "body":
        parts = parts[1:]
    elif parts and parts[0] in _LOCATIONS:
        out.append(str(parts[0]))
        parts = parts[1:]
    for part in parts:
        if isinstance(part, int) and not isinstance(part, bool) and 0 <= part < 10_000:
            out.append(str(part))
        elif isinstance(part, str) and part in KNOWN_FIELD_NAMES:
            out.append(part)
        else:
            break
    return ".".join(out) if out else "body"


def field_paths(errors: Iterable[Mapping[str, Any]]) -> list[str]:
    """Unique paths (first-seen order, at most ``MAX_FIELDS``); a JSON syntax error is just ``body``."""
    paths: dict[str, None] = {}
    for error in errors:
        if error.get("type") == "json_invalid":
            paths.setdefault("body", None)
        else:
            paths.setdefault(field_path(error.get("loc", ())), None)
        if len(paths) >= MAX_FIELDS:
            break
    return list(paths)


# ───────────────────────────── exception handlers ─────────────────────────────


async def validation_error_handler(request: Request, exc: Exception) -> Response:
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    return error_response(422, "invalid_request", field_paths(errors))


async def api_error_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, ApiError):  # pragma: no cover - registered for ApiError only
        return error_response(500, "internal")
    return error_response(exc.status_code, exc.code, exc.fields, exc.headers)


async def http_error_handler(request: Request, exc: Exception) -> Response:
    """Starlette/FastAPI HTTP errors (router 404/405, FastAPI's 400 for an unparsable body)."""
    status = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
    code = STATUS_ERROR_CODES.get(status)
    if code is None or status == 500:
        log.error("unexpected HTTP error status %d for %s %s", status, request.method, request.url.path[:200])
        return error_response(500, "internal")
    headers: dict[str, str] = {}
    if status == 405 and isinstance(exc, StarletteHTTPException) and exc.headers:
        allow = exc.headers.get("Allow") or exc.headers.get("allow")
        if allow:
            headers["Allow"] = allow
    if status == 400:
        return error_response(422, code, ["body"])
    return error_response(status, code, [], headers)
