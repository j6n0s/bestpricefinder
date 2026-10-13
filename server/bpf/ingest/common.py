"""Shared ingest plumbing: the data date, run bookkeeping in ``ops.ingest_run``, warnings and DB helpers.

Connections: every run takes a psycopg connection in **autocommit** mode as ``bpf_ingest``. Reads run outside
transactions and every write is an explicit ``with conn.transaction():`` block, so the ingest never holds a
transaction open across HTTP requests (the cluster kills sessions idle in a transaction after 60 s).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

from bpf.gvh import GvhClient, GvhError

log = logging.getLogger("bpf.ingest")

BUDAPEST = ZoneInfo("Europe/Budapest")
Clock = Callable[[], datetime]
RunKind = Literal["reference", "daily", "availability"]
RunStatus = Literal["ok", "partial", "failed"]

MAX_WARNINGS = 200
MAX_SAMPLE = 25
MAX_ERROR_CHARS = 500
_LOCK_NAMESPACE = 727_100  # advisory-lock namespace of bpf.ingest; the second key is the kind
_LOCK_KINDS: dict[str, int] = {"reference": 1, "daily": 2, "availability": 3}

#: Units the ingest accepts (core.product.unit, model.Unit). Anything else is skipped with a warning.
VALID_UNITS = frozenset({"kg", "l", "db"})


def utc_now() -> datetime:
    return datetime.now(UTC)


def budapest_today(clock: Clock = utc_now) -> date:
    """Today in Europe/Budapest from an aware clock: the data date of a run (BUILD-BRIEF §4.1 trap 10)."""
    now = clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("the ingest clock must return a timezone-aware datetime")
    return now.astimezone(BUDAPEST).date()


class IngestError(Exception):
    """A run cannot proceed: missing prerequisites or inconsistent reference data."""


class IngestBusyError(IngestError):
    """Another run of the same kind is in progress (advisory lock held)."""


def sample(items: Iterable[Any], limit: int = MAX_SAMPLE) -> list[Any]:
    """The first ``limit`` items of a sorted copy (JSON-safe), for warning details."""
    return [_json_safe(item) for item in sorted(items, key=str)[:limit]]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, set | frozenset):
        return sample(value)
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value


@dataclass
class RunLog:
    """Warnings and stats of one run, JSON-safe, bounded in size.

    ``degrade=True`` marks something the run could not do (a failed request, an exhausted budget...): the
    run then ends ``partial`` instead of ``ok``."""

    warnings: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    degraded: bool = False
    dropped: int = 0

    def warn(self, code: str, message: str, *, degrade: bool = False, **detail: Any) -> None:
        log.warning("%s: %s", code, message)
        if degrade:
            self.degraded = True
        if len(self.warnings) >= MAX_WARNINGS:
            self.dropped += 1
            return
        entry: dict[str, Any] = {"code": code, "message": message}
        entry.update({key: _json_safe(value) for key, value in detail.items()})
        self.warnings.append(entry)

    def stat(self, name: str, value: Any) -> None:
        self.stats[name] = _json_safe(value)

    def warnings_json(self) -> list[dict[str, Any]]:
        if not self.dropped:
            return list(self.warnings)
        return [*self.warnings, {"code": "warnings_truncated", "message": f"{self.dropped} more warnings"}]


@dataclass
class RunContext:
    conn: psycopg.Connection
    client: GvhClient
    kind: RunKind
    data_date: date
    log: RunLog


@dataclass(frozen=True, slots=True)
class IngestOutcome:
    run_id: int | None
    kind: RunKind
    status: RunStatus
    data_date: date
    requests: int
    bytes: int
    warnings: tuple[dict[str, Any], ...]
    stats: Mapping[str, Any]
    error: str | None


def describe_error(exc: BaseException) -> str:
    """A short, secret-free description for ops.ingest_run.error (no bodies: GVH errors never carry them)."""
    text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    return " ".join(text.split())[:MAX_ERROR_CHARS]


def require_autocommit(conn: psycopg.Connection) -> None:
    if not conn.autocommit:
        raise ValueError(
            "the ingest needs an autocommit connection (bpf.db.connect('ingest', autocommit=True)); it opens "
            "explicit transactions only for writes"
        )


def history_writable(conn: psycopg.Connection, data_date: date) -> bool:
    """Whether rows of ``data_date`` may still be updated: the append-only trigger
    (core.forbid_history_rewrite) allows today and yesterday in Budapest time, by the DATABASE clock."""
    row = conn.execute(
        "SELECT %s::date >= ((now() AT TIME ZONE 'Europe/Budapest')::date - 1)", (data_date,)
    ).fetchone()
    return bool(row and row[0])


def fetch_ingredient_leaves(conn: psycopg.Connection) -> frozenset[int]:
    """GVH leaf ids referenced by the ingredient ontology (app.ingredient.leaf_ids).

    docs/ENGINE.md names ``api.ingredient``; bpf_ingest has no SELECT on that view, so the same column is read
    from the table behind it."""
    rows = conn.execute("SELECT DISTINCT unnest(leaf_ids) FROM app.ingredient").fetchall()
    return frozenset(int(row[0]) for row in rows if row[0] is not None)


def fetch_food_leaves(conn: psycopg.Connection) -> frozenset[int]:
    rows = conn.execute("SELECT id FROM core.category WHERE is_leaf AND is_food").fetchall()
    return frozenset(int(row[0]) for row in rows)


def mark_stores_with_data(conn: psycopg.Connection, store_ids: Iterable[str], data_date: date) -> int:
    """``has_data_date = greatest(has_data_date, data_date)`` for known stores; never moves it backwards.
    Call inside a transaction. Returns the number of stores updated."""
    ids = sorted(set(store_ids))
    if not ids:
        return 0
    cur = conn.execute(
        "UPDATE core.store SET has_data_date = GREATEST(has_data_date, %s::date) "
        "WHERE id = ANY(%s) AND has_data_date IS DISTINCT FROM GREATEST(has_data_date, %s::date)",
        (data_date, ids, data_date),
    )
    return cur.rowcount


def _start_run(conn: psycopg.Connection, kind: RunKind, data_date: date) -> int:
    row = conn.execute(
        "INSERT INTO ops.ingest_run (kind, status, data_date) VALUES (%s, 'running', %s) RETURNING id",
        (kind, data_date),
    ).fetchone()
    if row is None:  # pragma: no cover - INSERT ... RETURNING always returns the row
        raise IngestError("could not record the run")
    return int(row[0])


def _finish_run(
    conn: psycopg.Connection,
    run_id: int,
    *,
    status: RunStatus,
    requests: int,
    bytes_: int,
    warnings: list[dict[str, Any]],
    stats: Mapping[str, Any],
    error: str | None,
) -> None:
    conn.execute(
        "UPDATE ops.ingest_run SET status = %s, finished_at = now(), requests = %s, bytes = %s, "
        "warnings = %s, stats = %s, error = %s WHERE id = %s",
        (status, requests, bytes_, Jsonb(warnings), Jsonb(dict(stats)), error, run_id),
    )


def _try_lock(conn: psycopg.Connection, kind: RunKind) -> bool:
    row = conn.execute("SELECT pg_try_advisory_lock(%s, %s)", (_LOCK_NAMESPACE, _LOCK_KINDS[kind])).fetchone()
    return bool(row and row[0])


def _unlock(conn: psycopg.Connection, kind: RunKind) -> None:
    try:
        conn.execute("SELECT pg_advisory_unlock(%s, %s)", (_LOCK_NAMESPACE, _LOCK_KINDS[kind]))
    except psycopg.Error as exc:  # the session may be gone; its locks went with it
        log.warning("could not release the %s ingest lock: %s", kind, type(exc).__name__)


def execute_run(
    conn: psycopg.Connection,
    client: GvhClient,
    *,
    kind: RunKind,
    data_date: date,
    body: Callable[[RunContext], None],
) -> IngestOutcome:
    """Run ``body`` as one recorded ingest run: ``running`` -> ``ok`` | ``partial`` | ``failed``.

    ``body`` raises to fail the run; it calls ``ctx.log.warn(..., degrade=True)`` for things it could not do
    (status ``partial``). Unknown response fields seen by the client during the run are recorded as one
    ``schema_drift`` warning. Requests and bytes are this run's share of the client's counters."""
    require_autocommit(conn)
    if not _try_lock(conn, kind):
        raise IngestBusyError(f"another {kind} ingest run is in progress")
    try:
        requests_before = client.stats.requests
        bytes_before = client.stats.bytes
        drift_before = dict(client.drift)
        run_id = _start_run(conn, kind, data_date)
        ctx = RunContext(conn=conn, client=client, kind=kind, data_date=data_date, log=RunLog())
        log.info("%s ingest run %d started for %s", kind, run_id, data_date.isoformat())
        error: str | None = None
        interrupt: BaseException | None = None
        try:
            body(ctx)
            status: RunStatus = "partial" if ctx.log.degraded else "ok"
        except Exception as exc:
            status, error = "failed", describe_error(exc)
            expected = isinstance(exc, GvhError | IngestError)
            log.error("%s ingest run %d failed: %s", kind, run_id, error, exc_info=not expected)
        except BaseException as exc:  # KeyboardInterrupt / SystemExit: record, then re-raise
            status, error, interrupt = "failed", describe_error(exc) or "interrupted", exc
        new_drift = sorted(path for path, n in client.drift.items() if n > drift_before.get(path, 0))
        if new_drift:
            ctx.log.warn(
                "schema_drift",
                f"{len(new_drift)} unknown field(s) in GVH responses (accepted, check ASSUMPTIONS.md)",
                fields=new_drift,
            )
        outcome = IngestOutcome(
            run_id=run_id,
            kind=kind,
            status=status,
            data_date=data_date,
            requests=client.stats.requests - requests_before,
            bytes=client.stats.bytes - bytes_before,
            warnings=tuple(ctx.log.warnings_json()),
            stats=dict(ctx.log.stats),
            error=error,
        )
        try:
            _finish_run(
                conn,
                run_id,
                status=outcome.status,
                requests=outcome.requests,
                bytes_=outcome.bytes,
                warnings=list(outcome.warnings),
                stats=outcome.stats,
                error=outcome.error,
            )
        except psycopg.Error as exc:
            log.error("could not record the end of %s run %d: %s", kind, run_id, describe_error(exc))
            if outcome.status != "failed":
                outcome = replace(outcome, status="failed", error=describe_error(exc))
        log.info(
            "%s ingest run %d finished: %s (%d requests, %d bytes, %d warnings)",
            kind,
            run_id,
            outcome.status,
            outcome.requests,
            outcome.bytes,
            len(outcome.warnings),
        )
        if interrupt is not None:
            raise interrupt
        return outcome
    finally:
        _unlock(conn, kind)
