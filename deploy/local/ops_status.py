"""Operational status of the local bestpricefinder database, for the deploy/local scripts (not app code).

Run it through the server project's environment, from any directory::

    uv run --project server python deploy/local/ops_status.py daily-ok [--date YYYY-MM-DD]
    uv run --project server python deploy/local/ops_status.py report [--now 2026-10-13T06:00:00+02:00]

``daily-ok``
    Exit 0 when a ``daily`` ingest run finished with status ``ok`` for the date (default: today in
    Europe/Budapest), 1 when none did, 2 when the database cannot be queried. One line on stdout.
    ``run-ingest.sh --scheduled daily`` uses it so that the 05:30 run is a no-op after a good 04:30 run.
``report``
    The database checks of ``doctor.sh``: data freshness (``api.latest``), the last run of every ingest kind,
    runs stuck in ``running``, reference data and content. Lines start with ``[ ok ]``, ``[WARN]`` or
    ``[FAIL]``; a ``fix:`` line may follow. Exit 0 = no problems (warnings may be printed), 1 = problems,
    2 = the database cannot be queried. ``--now`` replaces the clock (for tests).

Connects as ``bpf_ingest`` with the settings of :mod:`bpf.config` (``BPF_ENV_FILE`` or ``<repo>/.env.local``).
Reads ``ops.ingest_run``, ``api.latest``, ``core.store`` and ``app.*`` counts; writes nothing. Never prints a
secret: database errors are reported through :func:`bpf.ingest.common.describe_error` (type and message,
no connection string).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import psycopg

from bpf import db
from bpf.ingest.common import BUDAPEST, budapest_today, describe_error, utc_now
from bpf.ingest.daily import HAS_DATA_WINDOW_DAYS

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_UNAVAILABLE = 2

#: A run still ``running`` after this long has almost certainly died (the process was killed).
STUCK_AFTER = timedelta(hours=3)
#: The scheduler runs the daily ingest at 04:30 and 05:30 Budapest time; after this, today's data is due.
DAILY_DUE = time(6, 0)
#: The second scheduled daily run (Budapest time).
DAILY_RETRY = time(5, 30)
FIX_STALE_XLSX = (
    "the GVH CDN still served an old XLSX (BUILD-BRIEF §4.1 trap 4). The scheduler runs the daily ingest at "
    "04:30 and 05:30 Budapest time; otherwise run deploy/local/run-ingest.sh daily again later"
)


@dataclass(frozen=True, slots=True)
class Run:
    id: int
    kind: str
    status: str
    data_date: date | None
    started_at: datetime
    finished_at: datetime | None
    requests: int
    warning_codes: tuple[str, ...]
    error: str | None


class Report:
    """Collects the ``[ ok ]`` / ``[WARN]`` / ``[FAIL]`` lines."""

    def __init__(self) -> None:
        self.problems = 0

    def ok(self, text: str) -> None:
        print(f"[ ok ] {text}")

    def warn(self, text: str, fix: str | None = None) -> None:
        print(f"[WARN] {text}")
        if fix:
            print(f"       fix: {fix}")

    def fail(self, text: str, fix: str | None = None) -> None:
        self.problems += 1
        print(f"[FAIL] {text}")
        if fix:
            print(f"       fix: {fix}")


def _local(moment: datetime | None) -> str:
    return moment.astimezone(BUDAPEST).strftime("%Y-%m-%d %H:%M") if moment else "-"


def _codes(warnings: Any) -> tuple[str, ...]:
    codes: list[str] = []
    if isinstance(warnings, list):
        for entry in warnings:
            code = entry.get("code") if isinstance(entry, dict) else None
            if isinstance(code, str) and code not in codes:
                codes.append(code)
    return tuple(codes)


def _connect() -> psycopg.Connection:
    return db.connect("ingest", autocommit=True)


def daily_ok(day: date) -> int:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT id, finished_at FROM ops.ingest_run "
                "WHERE kind = 'daily' AND status = 'ok' AND data_date = %s ORDER BY id DESC LIMIT 1",
                (day,),
            ).fetchone()
    except (db.MissingCredentialsError, psycopg.Error) as exc:
        print(f"cannot check the daily ingest of {day.isoformat()}: {describe_error(exc)}")
        return EXIT_UNAVAILABLE
    if row is None:
        print(f"no daily ingest run finished ok for {day.isoformat()} yet")
        return EXIT_PROBLEMS
    print(f"the daily ingest for {day.isoformat()} already finished ok (run {row[0]}, {_local(row[1])})")
    return EXIT_OK


_LAST_RUNS = (
    "SELECT DISTINCT ON (kind) id, kind, status, data_date, started_at, finished_at, requests, warnings, "
    "error "
    "FROM ops.ingest_run ORDER BY kind, id DESC"
)
_LAST_GOOD_RUNS = (
    "SELECT DISTINCT ON (kind) id, kind, status, data_date, started_at, finished_at, requests, warnings, "
    "error "
    "FROM ops.ingest_run WHERE status IN ('ok', 'partial') AND finished_at IS NOT NULL ORDER BY kind, id DESC"
)


def _last_runs(conn: psycopg.Connection, *, good: bool = False) -> dict[str, Run]:
    """The newest run of every kind; with ``good``, the newest finished ``ok`` or ``partial`` one (the runs
    that ``api.latest`` and ``api.ingest_latest`` count)."""
    rows = conn.execute(_LAST_GOOD_RUNS if good else _LAST_RUNS).fetchall()
    return {
        str(r[1]): Run(
            id=int(r[0]),
            kind=str(r[1]),
            status=str(r[2]),
            data_date=r[3],
            started_at=r[4],
            finished_at=r[5],
            requests=int(r[6]),
            warning_codes=_codes(r[7]),
            error=r[8],
        )
        for r in rows
    }


def _fix_for_error(error: str | None) -> str:
    text = error or ""
    if text.startswith("StaleXlsxError"):
        return FIX_STALE_XLSX
    if text.startswith("GvhConfigError"):
        return "set BPF_CONTACT_EMAIL=you@example.org in the env file (.env.local)"
    if text.startswith("GvhHttpError") or text.startswith("GvhBudgetExceeded"):
        return (
            "GVH or the network was unreachable; check the connection, then run the ingest again "
            "(deploy/local/run-ingest.sh)"
        )
    if text.startswith("GvhSchemaError"):
        return (
            "GVH changed its API or XLSX format: the ingest refuses to guess. See "
            "server/bpf/gvh/ASSUMPTIONS.md and the log in .data/logs/"
        )
    return "see the run's log in .data/logs/ and docs/RUNNING.md, Troubleshooting"


def _describe(run: Run) -> str:
    when = f"for {run.data_date.isoformat()}" if run.data_date else "(no data date)"
    return f"last {run.kind} run #{run.id} {when}: {run.status}"


def _freshness(rep: Report, latest: date | None, ingested_at: datetime | None, now: datetime) -> None:
    today = now.date()
    if latest is None:
        rep.fail(
            "no successful daily ingest yet: the app has no prices to show",
            "deploy/local/run-ingest.sh reference && deploy/local/run-ingest.sh daily",
        )
        return
    age = (today - latest).days
    stamp = f"latest data date {latest.isoformat()} (ingested {_local(ingested_at)})"
    if age <= 0:
        rep.ok(f"{stamp}: today")
    elif age == 1 and now.time() < DAILY_DUE:
        rep.ok(f"{stamp}: yesterday; today's daily ingest is due at 04:30-05:30 Budapest time")
    elif age == 1:
        rep.warn(
            f"{stamp}: yesterday; today's daily ingest has not succeeded yet",
            "see the last daily run below; then deploy/local/run-ingest.sh daily",
        )
    else:
        rep.fail(
            f"{stamp}: {age} days old; the app marks its prices as stale",
            "deploy/local/run-ingest.sh daily, and check the scheduler (docs/RUNNING.md)",
        )


def _daily(rep: Report, run: Run | None, latest: date | None, now: datetime) -> None:
    if run is None:
        return  # _freshness already reported "no successful daily ingest yet"
    # An earlier run for the same data date succeeded (or partly): its data are served.
    covered = latest is not None and run.data_date is not None and latest >= run.data_date
    # Today's first scheduled attempt failed, and the 05:30 retry is still to come.
    retry_due = run.data_date == now.date() and now.time() < DAILY_RETRY
    if run.status == "ok":
        rep.ok(f"{_describe(run)} (finished {_local(run.finished_at)}, {run.requests} requests)")
    elif run.status == "partial":
        codes = ", ".join(run.warning_codes[:6]) or "no warning codes"
        fix = (
            "data were written; the 05:30 run or a manual deploy/local/run-ingest.sh daily may complete them"
        )
        if "api_xlsx_date_mismatch" in run.warning_codes:
            fix = (
                "api_xlsx_date_mismatch: the GVH API had not switched to the XLSX's day yet (BUILD-BRIEF "
                "§4.1 trap 10); re-run deploy/local/run-ingest.sh daily later in the morning"
            )
        rep.warn(f"{_describe(run)} ({codes})", fix)
    elif run.status == "failed":
        text = f"{_describe(run)}: {run.error or 'no error recorded'}"
        if covered:
            served = " (an earlier run for that date succeeded; its data are served)"
            rep.warn(text + served, _fix_for_error(run.error))
        elif retry_due:
            rep.warn(text + " (the scheduler retries at 05:30)", _fix_for_error(run.error))
        else:
            rep.fail(text, _fix_for_error(run.error))
    elif run.status == "running":
        rep.ok(f"{_describe(run)} since {_local(run.started_at)}")


def _availability(rep: Report, run: Run | None, good: Run | None, now: datetime) -> None:
    """``run``: the newest availability run; ``good``: the newest ok/partial one (what the API counts)."""
    fix = "deploy/local/run-ingest.sh availability (the scheduler runs it on Sundays at 05:00)"
    if good is None or good.data_date is None:
        rep.warn("no availability ingest yet: every store counts as having data", fix)
    elif (now.date() - good.data_date).days > HAS_DATA_WINDOW_DAYS:
        rep.warn(
            f"the last good availability ingest is for {good.data_date.isoformat()}, more than "
            f"{HAS_DATA_WINDOW_DAYS} days ago: every store counts as having data again",
            fix,
        )
    elif "no_daily_data" in good.warning_codes:
        # Runs recorded before the ingest fix finished ok without refreshing anything, yet the API counts
        # them as recent: then only stores with per-store prices count as having data. Current runs that
        # refresh nothing fail instead, so this only flags old rows.
        rep.warn(
            f"the last availability run #{good.id} ({good.data_date.isoformat()}) refreshed nothing: no "
            "daily ingest had succeeded yet. Until a real one runs, most stores count as having no data",
            "deploy/local/run-ingest.sh availability (now that a daily ingest has succeeded)",
        )
    else:
        rep.ok(f"availability data as of {good.data_date.isoformat()} (run #{good.id})")
    if run is not None and run.status == "failed":
        rep.warn(f"{_describe(run)}: {run.error or 'no error recorded'}", _fix_for_error(run.error))
    elif run is not None and run.status == "partial":
        codes = ", ".join(run.warning_codes[:6]) or "no warning codes"
        rep.warn(f"{_describe(run)} ({codes}): some products were not refreshed", fix)


def report(now: datetime) -> int:
    rep = Report()
    try:
        with _connect() as conn:
            latest_row = conn.execute("SELECT data_date, ingested_at FROM api.latest").fetchone()
            runs = _last_runs(conn)
            good = _last_runs(conn, good=True)
            stuck = conn.execute(
                "SELECT id, kind, started_at FROM ops.ingest_run "
                "WHERE status = 'running' AND started_at < %s ORDER BY id",
                (now - STUCK_AFTER,),
            ).fetchall()
            counts = conn.execute(
                "SELECT (SELECT count(*) FROM core.store), (SELECT count(*) FROM core.chain), "
                "(SELECT count(*) FROM app.recipe), (SELECT count(*) FROM app.ingredient)"
            ).fetchone()
    except (db.MissingCredentialsError, psycopg.Error) as exc:
        rep.fail(
            f"cannot query the database as bpf_ingest: {describe_error(exc)}",
            "deploy/local/db-start.sh; check BPF_DB_* and BPF_INGEST_PASSWORD in the env file",
        )
        return EXIT_UNAVAILABLE
    stores, chains, recipes, ingredients = counts if counts else (0, 0, 0, 0)

    latest, ingested_at = latest_row if latest_row else (None, None)
    _freshness(rep, latest, ingested_at, now)
    _daily(rep, runs.get("daily"), latest, now)
    _availability(rep, runs.get("availability"), good.get("availability"), now)

    if stores and chains:
        rep.ok(f"reference data: {chains} chains, {stores} stores")
    else:
        rep.fail("no reference data (chains, stores) yet", "deploy/local/run-ingest.sh reference")
    reference = runs.get("reference")
    if reference is not None and reference.status == "failed":
        text = f"{_describe(reference)}: {reference.error or 'no error recorded'}"
        rep.warn(text, _fix_for_error(reference.error))

    content = runs.get("content")
    if recipes and ingredients:
        rep.ok(f"content: {ingredients} ingredients, {recipes} recipes")
    else:
        rep.fail("content (ingredients, recipes) not loaded", "deploy/local/load-content.sh")
    if content is not None and content.status == "failed":
        rep.warn(
            f"last content load #{content.id} failed: {content.error or 'no error recorded'}",
            "deploy/local/load-content.sh",
        )

    for run_id, kind, started_at in stuck:
        rep.warn(
            f"{kind} run #{run_id} has been 'running' since {_local(started_at)}: its process probably died "
            "(the next run of that kind is not blocked)",
        )
    return EXIT_PROBLEMS if rep.problems else EXIT_OK


def _iso_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from None


def _aware(text: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected an ISO 8601 date-time with a UTC offset") from None
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise argparse.ArgumentTypeError("the date-time needs a UTC offset, e.g. 2026-10-13T06:00:00+02:00")
    return moment


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ops_status.py", description="bestpricefinder operational status")
    sub = parser.add_subparsers(dest="command", required=True)
    p_ok = sub.add_parser("daily-ok", help="exit 0 if today's daily ingest already finished ok")
    p_ok.add_argument("--date", type=_iso_date, help="data date (default: today in Europe/Budapest)")
    p_report = sub.add_parser("report", help="doctor.sh's database checks")
    p_report.add_argument("--now", type=_aware, help="pretend it is this moment (tests)")
    args = parser.parse_args(argv)
    if args.command == "daily-ok":
        return daily_ok(args.date or budapest_today())
    now = (args.now or utc_now()).astimezone(BUDAPEST)
    return report(now)


if __name__ == "__main__":
    sys.exit(main())
