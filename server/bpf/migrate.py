"""Apply ``db/migrations/NNNN_name.sql`` in order, as ``bpf_migrator`` acting as ``bpf_owner``.

Usage::

    uv run bpf-migrate                 # apply everything pending
    uv run bpf-migrate --check         # report only; exit 2 if anything is pending
    python -m bpf.migrate --dir PATH   # another migrations directory (tests)

Exit codes: 0 = up to date (or everything applied), 1 = error (nothing further applied), 2 = ``--check`` found
pending migrations.

Rules enforced here:

- File names match ``^\\d{4}_[a-z0-9_]+\\.sql$``; versions are unique and start at 0001. Dotfiles and ``*.md``
  are ignored; anything else in the directory is an error, so a misnamed migration is never skipped silently.
- ``public.schema_migrations`` records version, file name and the sha256 of the exact file bytes. If an applied
  file changed, was renamed or is missing, nothing runs: never edit an applied migration, add a new one.
- A pending migration numbered below the latest applied one is an error (renumber it).
- Each migration runs in its own transaction: ``SET LOCAL ROLE bpf_owner``, the file as one multi-statement
  script, the bookkeeping row, ``COMMIT``. Files must not contain ``BEGIN``/``COMMIT``/``ROLLBACK`` or
  statements that cannot run in a transaction (``CREATE INDEX CONCURRENTLY``, ``VACUUM``...).
- A session-level advisory lock serialises concurrent runs (``lock_timeout`` of bpf_migrator is 10 s).

Logged: file names, checksums, durations, error codes and messages. Never logged: SQL text, conninfo, passwords.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from psycopg.pq import TransactionStatus

from bpf.config import REPO_ROOT, Settings
from bpf.db import MissingCredentialsError, connect

log = logging.getLogger("bpf.migrate")

DEFAULT_DIR: Path = REPO_ROOT / "db" / "migrations"
FILENAME_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
OWNER_ROLE = "bpf_owner"
#: pg_advisory_lock key: the ASCII bytes of "bpf-migr" as a big-endian bigint.
LOCK_KEY = int.from_bytes(b"bpf-migr", "big")

_SET_OWNER = b"SET LOCAL ROLE bpf_owner"
_TABLE_EXISTS = b"SELECT to_regclass('public.schema_migrations') IS NOT NULL"
_CREATE_TABLE = b"""
CREATE TABLE public.schema_migrations (
    version     integer PRIMARY KEY CHECK (version BETWEEN 1 AND 9999),
    filename    text NOT NULL UNIQUE CHECK (filename ~ '^[0-9]{4}_[a-z0-9_]+[.]sql$'),
    sha256      text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    applied_at  timestamptz NOT NULL DEFAULT now()
)
"""
_SELECT_APPLIED = b"SELECT version, filename, sha256 FROM public.schema_migrations ORDER BY version"
_INSERT_APPLIED = b"INSERT INTO public.schema_migrations (version, filename, sha256) VALUES (%s, %s, %s)"


class MigrationError(Exception):
    """A migration could not be planned or applied. The message is safe to log (no SQL text, no secrets)."""


@dataclass(frozen=True)
class Migration:
    version: int
    filename: str
    path: Path
    sha256: str
    sql: bytes = field(repr=False)


@dataclass(frozen=True)
class AppliedRow:
    version: int
    filename: str
    sha256: str


@dataclass(frozen=True)
class Result:
    applied: list[Migration]
    """Migrations applied by this run (empty with ``check=True``)."""
    pending: list[Migration]
    """Migrations still pending after this run (only non-empty with ``check=True``)."""
    version: int
    """Highest applied version after this run (0 = none)."""


def discover(directory: Path) -> list[Migration]:
    """Read and validate every migration file in ``directory``, sorted by version."""
    if not directory.is_dir():
        raise MigrationError(f"migrations directory not found: {directory}")
    by_version: dict[int, Migration] = {}
    for entry in sorted(directory.iterdir()):
        name = entry.name
        if name.startswith(".") or name.endswith(".md"):
            continue
        match = FILENAME_RE.fullmatch(name)
        if match is None or not entry.is_file():
            raise MigrationError(
                f"invalid migration file name {name!r} in {directory}: expected NNNN_lowercase_name.sql"
            )
        version = int(match.group(1))
        if version == 0:
            raise MigrationError(f"{name}: migration versions start at 0001")
        if version in by_version:
            raise MigrationError(f"duplicate migration version {version:04d}: {by_version[version].filename}, {name}")
        data = entry.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MigrationError(f"{name} is not valid UTF-8") from exc
        if not text.strip():
            raise MigrationError(f"{name} is empty")
        by_version[version] = Migration(version, name, entry, hashlib.sha256(data).hexdigest(), data)
    return [by_version[v] for v in sorted(by_version)]


def plan(migrations: Sequence[Migration], applied: Sequence[AppliedRow]) -> tuple[list[Migration], list[str]]:
    """Return ``(pending, problems)``. Any problem means nothing may be applied."""
    files = {m.version: m for m in migrations}
    done = {row.version: row for row in applied}
    problems: list[str] = []
    for row in applied:
        m = files.get(row.version)
        if m is None:
            problems.append(f"applied migration {row.filename} (version {row.version:04d}) is missing from disk")
        elif m.filename != row.filename:
            problems.append(f"applied migration {row.filename} was renamed to {m.filename}; restore its name")
        elif m.sha256 != row.sha256:
            problems.append(
                f"{m.filename} changed after it was applied (recorded sha256 {row.sha256}, file sha256 "
                f"{m.sha256}). Never edit an applied migration: restore it and add a new migration instead"
            )
    latest = max(done, default=0)
    pending = [m for m in migrations if m.version not in done]
    problems.extend(
        f"pending migration {m.filename} is numbered below the latest applied version {latest:04d}; renumber it"
        for m in pending
        if m.version < latest
    )
    return pending, problems


def _describe_db_error(exc: psycopg.Error, migration: Migration | None = None) -> str:
    """SQLSTATE, primary message and (for a migration) the line number. Never the SQL text."""
    diag = exc.diag
    text = diag.message_primary or type(exc).__name__
    where = ""
    if migration is not None and diag.statement_position:
        # statement_position is a 1-based character offset into the script that was sent.
        offset = int(diag.statement_position)
        line = migration.sql.decode("utf-8")[:offset].count("\n") + 1
        where = f" at line {line}"
    return f"[{diag.sqlstate or '?????'}] {text}{where}"


def _read_applied(conn: psycopg.Connection, *, create: bool) -> list[AppliedRow]:
    conn.execute(_SET_OWNER)
    row = conn.execute(_TABLE_EXISTS).fetchone()
    if not (row and row[0]):
        if not create:
            conn.rollback()
            return []
        conn.execute(_CREATE_TABLE)
        log.info("created public.schema_migrations")
    rows = conn.execute(_SELECT_APPLIED).fetchall()
    conn.commit()
    return [AppliedRow(int(v), str(f), str(s)) for v, f, s in rows]


def _apply_one(conn: psycopg.Connection, m: Migration) -> float:
    started = time.monotonic()
    try:
        conn.execute(_SET_OWNER)
        conn.execute(m.sql)  # no parameters: sent as one simple-protocol script, so several statements are fine
        if conn.info.transaction_status != TransactionStatus.INTRANS:
            raise MigrationError(
                f"{m.filename} ended the migration transaction itself; remove BEGIN/COMMIT/ROLLBACK from it"
            )
        conn.execute(_SET_OWNER)  # in case the script changed role
        conn.execute(_INSERT_APPLIED, (m.version, m.filename, m.sha256))
        conn.commit()
    except psycopg.Error as exc:
        conn.rollback()
        raise MigrationError(f"{m.filename} failed and was rolled back: {_describe_db_error(exc, m)}") from None
    except BaseException:
        conn.rollback()
        raise
    # Give the next file a clean session, as if it ran on its own connection.
    conn.execute(b"RESET ALL")
    conn.execute(b"RESET ROLE")
    conn.commit()
    return time.monotonic() - started


def run(directory: Path = DEFAULT_DIR, *, settings: Settings | None = None, check: bool = False) -> Result:
    """Apply (or with ``check=True`` only list) pending migrations. Raises :class:`MigrationError`."""
    migrations = discover(directory)
    try:
        conn = connect("migrator", settings=settings, autocommit=False)
    except psycopg.Error as exc:
        raise MigrationError(f"cannot connect as bpf_migrator: {exc}") from None
    with conn:
        try:
            conn.execute(b"SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
            conn.commit()  # the advisory lock is session-level: it survives the commit
        except psycopg.errors.LockNotAvailable:
            raise MigrationError("another bpf-migrate run holds the migration lock; try again later") from None
        try:
            applied = _read_applied(conn, create=not check)
        except psycopg.Error as exc:
            raise MigrationError(f"cannot read public.schema_migrations: {_describe_db_error(exc)}") from None
        pending, problems = plan(migrations, applied)
        if problems:
            raise MigrationError("; ".join(problems))
        version = max((row.version for row in applied), default=0)
        if check:
            return Result(applied=[], pending=pending, version=version)
        done: list[Migration] = []
        for m in pending:
            seconds = _apply_one(conn, m)
            done.append(m)
            version = m.version
            log.info("applied %s sha256=%s in %.0f ms", m.filename, m.sha256, seconds * 1000)
        return Result(applied=done, pending=[], version=version)


def main(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bpf-migrate", description="Apply db/migrations/*.sql as bpf_migrator (SET ROLE bpf_owner)."
    )
    parser.add_argument(
        "--dir", type=Path, default=DEFAULT_DIR, help=f"migrations directory (default: {DEFAULT_DIR})"
    )
    parser.add_argument(
        "--check", action="store_true", help="apply nothing; exit 2 if migrations are pending, 1 on mismatch"
    )
    args = parser.parse_args(argv)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        result = run(args.dir, settings=settings, check=args.check)
    except (MigrationError, MissingCredentialsError) as exc:
        log.error("%s", exc)
        return 1
    if args.check:
        for m in result.pending:
            log.warning("pending %s sha256=%s", m.filename, m.sha256)
        if result.pending:
            log.warning("%d migration(s) pending; database at version %04d", len(result.pending), result.version)
            return 2
        log.info("up to date at version %04d", result.version)
        return 0
    if result.applied:
        log.info("applied %d migration(s); database at version %04d", len(result.applied), result.version)
    else:
        log.info("nothing to do; database at version %04d", result.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
