"""Exceptions raised by :mod:`bpf.gvh`.

Messages never contain response bodies, credentials or connection strings: at most an HTTP status, a URL
path (all GVH URLs are public and carry no secrets), a GVH error code such as ``SEARCH-INPUT-ERROR`` and the
locations/types of schema violations.
"""

from __future__ import annotations

from datetime import date


class GvhError(Exception):
    """Base class for every error raised by the GVH client."""


class GvhConfigError(GvhError):
    """The client is misconfigured (e.g. the User-Agent has no contact address)."""


class GvhHttpError(GvhError):
    """A request failed for good: a non-retryable status (4xx, 3xx), or 5xx / connection errors after retries.

    ``status`` is None for connection-level failures. ``code`` is the GVH error code found in the body
    (e.g. ``"SEARCH-INPUT-ERROR"``) when there is one; the body itself is never kept.
    """

    def __init__(self, message: str, *, url: str, status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status = status
        self.code = code


class GvhBudgetExceeded(GvhError):
    """The run's request budget (``--max-requests``) is used up; no further request was sent."""


class GvhSchemaError(GvhError):
    """A response does not have the expected shape: not JSON/XLSX, a missing required field, a wrong type,
    an unknown enum value, an XLSX header change, or a paging behaviour that would silently lose rows.

    The GVH API is undocumented; this error is how the ingest "fails loudly" on schema changes."""


class StaleXlsxError(GvhError):
    """The daily XLSX is not the expected day's file; the CDN serves stale copies (BUILD-BRIEF §4.1, 4)."""

    def __init__(self, sheet_date: date, expected_date: date) -> None:
        super().__init__(
            f"stale daily XLSX: sheet date {sheet_date.isoformat()} != expected {expected_date.isoformat()}"
        )
        self.sheet_date = sheet_date
        self.expected_date = expected_date
