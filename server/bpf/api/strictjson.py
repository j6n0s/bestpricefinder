"""Strict JSON request bodies for the POST endpoints.

Python's ``json`` module accepts ``NaN``/``Infinity``, silently keeps the last of duplicate keys, decodes
UTF-16/32 bodies, and raises ``ValueError`` (int digit limit) or ``RecursionError`` (deep nesting), which
FastAPI would report as a 400 or a 500. :class:`StrictJsonRoute` parses every JSON body with
:func:`strict_json_loads` instead, which turns every one of those cases into ``json.JSONDecodeError``; FastAPI
then reports a ``json_invalid`` validation error, which the error handler maps to 422 ``invalid_request``
with the single field ``body``. The body itself is never logged or echoed.

Request models are validated in the ordinary decimal context: ``schemas._to_qty`` (contract v1.2) accepts only
JSON numbers and rejects huge magnitudes before it quantizes, so no quantity can raise an ``ArithmeticError``
(which pydantic would not turn into a 422). A trap-free validation context therefore adds no protection, and
it is not used: it would also silence decimal errors in everything that runs inside the request.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import Response


def _reject_constant(name: str) -> Any:
    raise ValueError("non-finite number")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def strict_json_loads(body: bytes) -> Any:
    """Parse a UTF-8 JSON document strictly (RFC 8259 + unique keys); every failure is a JSONDecodeError."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise json.JSONDecodeError("body is not valid UTF-8", "", 0) from None
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(exc.msg, "", exc.pos) from None
    except ValueError, RecursionError, MemoryError:
        raise json.JSONDecodeError("invalid JSON", "", 0) from None


class StrictJsonRequest(Request):
    """A request whose ``json()`` is :func:`strict_json_loads`."""

    async def json(self) -> Any:
        if not hasattr(self, "_json"):
            self._json = strict_json_loads(await self.body())
        return self._json


class StrictJsonRoute(APIRoute):
    """``APIRoute`` that hands FastAPI a :class:`StrictJsonRequest` (OpenAPI generation is unchanged)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def strict_handler(request: Request) -> Response:
            return await handler(StrictJsonRequest(request.scope, request.receive))

        return strict_handler
