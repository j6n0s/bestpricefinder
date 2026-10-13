"""Ingest CLI: ``python -m bpf.ingest {reference|daily|availability} [--date YYYY-MM-DD] [--budapest-only]
[--max-requests N]`` (plus ``--all-stores``, ``--all-food``, ``-v``).

Connects as ``bpf_ingest`` (settings from the environment / ``.env.local``; BPF_CONTACT_EMAIL is required for
the User-Agent). Prints a one-line summary on stdout; logs go to stderr and never contain secrets or response
bodies.

Exit codes: 0 ok, 1 failed (or could not start), 2 usage error, 3 partial (data written, something missing).
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections.abc import Callable, Sequence
from datetime import date

import psycopg

from bpf import db
from bpf.config import Settings, get_settings
from bpf.gvh import GvhClient, GvhError
from bpf.ingest.availability import run_availability
from bpf.ingest.common import Clock, IngestError, IngestOutcome, describe_error, utc_now
from bpf.ingest.daily import run_daily
from bpf.ingest.reference import run_reference

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_PARTIAL = 3
_EXIT = {"ok": EXIT_OK, "partial": EXIT_PARTIAL, "failed": EXIT_FAILED}


def _iso_date(text: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _positive(text: str) -> int:
    if not re.fullmatch(r"[0-9]{1,9}", text) or int(text) < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return int(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bpf.ingest",
        description="GVH Árfigyelő ingest (polite: <= 1 request/s, descriptive User-Agent).",
        epilog="exit codes: 0 ok, 1 failed, 2 usage error, 3 partial (data written, something missing). "
        "Requires BPF_CONTACT_EMAIL (User-Agent contact) and the bpf_ingest database credentials.",
    )
    parser.add_argument("kind", choices=("reference", "daily", "availability"), help="what to ingest")
    parser.add_argument(
        "--date", type=_iso_date, help="data date (default: today in Europe/Budapest); the XLSX must carry it"
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--budapest-only",
        dest="budapest_only",
        action="store_true",
        default=True,
        help="daily: per-store prices for Budapest stores only (the default in M0)",
    )
    scope.add_argument(
        "--all-stores",
        dest="budapest_only",
        action="store_false",
        help="daily: per-store prices for every store of the varying chains (many more requests)",
    )
    parser.add_argument(
        "--all-food",
        action="store_true",
        help="availability: refresh every food product, not only the ingredient ontology's leaves",
    )
    parser.add_argument(
        "--max-requests", type=_positive, help="stop after N HTTP requests (run becomes partial)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging (one line per request)")
    return parser


def _run(
    args: argparse.Namespace, conn: psycopg.Connection, client: GvhClient, clock: Clock
) -> IngestOutcome:
    if args.kind == "reference":
        return run_reference(conn, client, data_date=args.date, clock=clock)
    if args.kind == "daily":
        return run_daily(conn, client, data_date=args.date, clock=clock, budapest_only=args.budapest_only)
    return run_availability(conn, client, data_date=args.date, clock=clock, all_food=args.all_food)


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    client_factory: Callable[[Settings, int | None], GvhClient] | None = None,
    connect: Callable[[Settings], psycopg.Connection] | None = None,
    clock: Clock = utc_now,
) -> int:
    """CLI entry point. The keyword arguments let tests inject settings, the GVH transport and the clock."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines would duplicate ours
    cfg = settings or get_settings()
    try:
        client = (client_factory or (lambda s, n: GvhClient(s, max_requests=n)))(cfg, args.max_requests)
    except GvhError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    try:
        with client:
            try:
                conn = (connect or (lambda s: db.connect("ingest", settings=s, autocommit=True)))(cfg)
            except (db.MissingCredentialsError, psycopg.Error) as exc:
                print(f"error: cannot connect to the database: {describe_error(exc)}", file=sys.stderr)
                return EXIT_FAILED
            with conn:
                outcome = _run(args, conn, client, clock)
    except IngestError as exc:  # e.g. another run of the same kind holds the lock
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    except psycopg.Error as exc:  # the database failed before the run could be recorded
        print(f"error: database: {describe_error(exc)}", file=sys.stderr)
        return EXIT_FAILED
    print(
        f"{outcome.kind} {outcome.data_date.isoformat()}: {outcome.status} (run {outcome.run_id}, "
        f"{outcome.requests} requests, {outcome.bytes} bytes, {len(outcome.warnings)} warnings)"
        + (f" error: {outcome.error}" if outcome.error else "")
    )
    return _EXIT[outcome.status]


if __name__ == "__main__":
    sys.exit(main())
