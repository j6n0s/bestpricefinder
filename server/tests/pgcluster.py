"""Throwaway PostgreSQL clusters for integration tests, built with the real ``deploy/local`` scripts.

A :class:`PgCluster` runs ``deploy/local/db-init.sh`` in a fresh temporary directory on a free port (through
the ``BPF_PGDATA`` / ``BPF_PG_PORT`` / ``BPF_ENV_FILE`` / ``BPF_SOCKET_DIR`` overrides, so the scripts under
test are exactly the ones developers run), starts it with ``db-start.sh``, applies ``db/migrations`` with
``bpf.migrate`` and, on :meth:`PgCluster.close`, stops it with ``db-stop.sh`` and deletes the directory.

Most tests should use the session-scoped ``pg`` fixture from ``tests/conftest.py``: one migrated cluster per
test session, skipped with a clear reason when no PostgreSQL >= 16 binaries are installed::

    import pytest
    from datetime import date

    pytestmark = pytest.mark.db          # every test in this module needs PostgreSQL

    def test_latest_is_readable(pg):
        with pg.connect("api") as conn:  # roles: "api", "ingest", "migrator", "admin" (superuser)
            conn.execute("SELECT data_date FROM api.latest").fetchone()

    def test_ingest_writes(pg):
        with pg.connect("ingest") as conn, conn.transaction(force_rollback=True):
            conn.execute("INSERT INTO ops.ingest_run (kind, status) VALUES ('daily', 'running')")

    def test_my_component(pg):
        settings = pg.settings()          # bpf.config.Settings for this cluster (never reads .env.local)
        with bpf.db.connect("ingest", settings=settings) as conn:
            ...

Need a cluster of your own (e.g. to test migrations from scratch)? Use the ``pg_factory`` fixture:
``cluster = pg_factory(migrate=False)``; it is closed at the end of the session (or call ``close()``).

Rules for tests that share the session cluster: leave it as you found it.

- Prefer ``conn.transaction(force_rollback=True)``: nothing is committed, so nothing needs cleaning up.
- Never commit price-history rows (``core.product_chain_day``, ``core.store_price_day``,
  ``core.product_availability``) for dates before yesterday (Budapest): the append-only trigger makes them
  impossible to update or delete afterwards, even for the superuser.
- Use distinctive ids (e.g. a ``zz_<test>_`` prefix) and drop any role you create.

Running as root (CI containers): initdb refuses to run as root, so when ``os.geteuid() == 0`` the scripts
run as the system user ``bpfpg`` (created on demand with ``useradd``) through ``runuser``, in a temp directory
that user owns. The test process itself keeps running as root and connects over the socket. On a developer
machine none of this happens. The scripts themselves simply refuse to run as root.
"""

from __future__ import annotations

import os
import pwd
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Literal

import psycopg
from dotenv import dotenv_values
from psycopg.conninfo import make_conninfo

from bpf import migrate as bpf_migrate
from bpf.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "deploy" / "local"
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
ROOT_RUN_AS = "bpfpg"  # unprivileged OS user that owns the cluster when the tests run as root
SOCKET_PATH_MAX = 103

ClusterRole = Literal["api", "ingest", "migrator", "admin"]
ROLE_USERS: dict[str, str] = {
    "api": "bpf_api",
    "ingest": "bpf_ingest",
    "migrator": "bpf_migrator",
    "admin": "bpf_admin",
}


class PgUnavailable(Exception):
    """No usable PostgreSQL >= 16 (or no way to run it): DB tests should be skipped with this message."""


@cache
def find_pg_bin() -> tuple[Path, int]:
    """``(bindir, major)`` as found by the scripts' own discovery (``bpf_find_pg_bin`` in ``_common.sh``)."""
    proc = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; . "$1"; bpf_find_pg_bin; printf "%s\\n%s\\n" "$PG_BIN" "$PG_MAJOR"',
            "find-pg-bin",
            str(SCRIPTS_DIR / "_common.sh"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise PgUnavailable(proc.stderr.strip() or f"PostgreSQL discovery failed (exit {proc.returncode})")
    bindir, major = proc.stdout.split()
    return Path(bindir), int(major)


def free_port() -> int:
    """A TCP port that is free on localhost right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _runuser() -> str:
    for candidate in (shutil.which("runuser"), "/usr/sbin/runuser", "/sbin/runuser"):
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    raise PgUnavailable("running as root requires runuser(1) to start PostgreSQL as an unprivileged user")


def _ensure_os_user(name: str) -> pwd.struct_passwd:
    try:
        return pwd.getpwnam(name)
    except KeyError:
        pass
    useradd = shutil.which("useradd") or "/usr/sbin/useradd"
    proc = subprocess.run(
        [useradd, "--system", "--user-group", "--no-create-home", "--shell", "/usr/sbin/nologin", name],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 9):  # 9 = already exists (created concurrently)
        raise PgUnavailable(f"cannot create OS user {name!r} to run PostgreSQL: {proc.stderr.strip()}")
    return pwd.getpwnam(name)


def _short_tmp_dir() -> str:
    """A temp base dir short enough for ``<base>/bpfpg-XXXXXXXX/sock/.s.PGSQL.NNNNN``."""
    base = tempfile.gettempdir()
    if len(os.fsencode(base)) + 40 >= SOCKET_PATH_MAX and os.path.isdir("/tmp"):
        return "/tmp"
    return base


class PgCluster:
    """One throwaway cluster. Create with :meth:`create`; use as a context manager or call :meth:`close`."""

    def __init__(self, *, port: int | None = None, base_dir: str | os.PathLike[str] | None = None) -> None:
        self.pg_bin, self.pg_major = find_pg_bin()
        self.run_as: pwd.struct_passwd | None = None
        if os.geteuid() == 0:
            self._runuser = _runuser()
            self.run_as = _ensure_os_user(ROOT_RUN_AS)
        self.root = Path(tempfile.mkdtemp(prefix="bpfpg-", dir=base_dir or _short_tmp_dir()))
        if self.run_as is not None:
            os.chown(self.root, self.run_as.pw_uid, self.run_as.pw_gid)
        self.port = port or free_port()
        self.pgdata = self.root / "pg"
        self.env_file = self.root / "env.local"
        self.admin_env_file = self.root / "pg-admin.env"
        self.socket_dir = self.root / "sock"
        self.log_file = self.root / "log" / "postgresql.log"
        self.backup_dir = self.root / "backups"
        self._closed = False

    # ── lifecycle ──────────────────────────────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        *,
        migrate: bool = True,
        migrations_dir: Path = MIGRATIONS_DIR,
        port: int | None = None,
        base_dir: str | os.PathLike[str] | None = None,
    ) -> PgCluster:
        """Init + start (+ apply ``migrations_dir`` unless ``migrate=False``). Cleans up if anything fails."""
        cluster = cls(port=port, base_dir=base_dir)
        try:
            cluster.script("db-init.sh")
            cluster.script("db-start.sh")  # a no-op when db-init.sh left it running; proves idempotence
            if migrate:
                cluster.migrate(migrations_dir)
        except BaseException:
            cluster.close()
            raise
        return cluster

    def migrate(self, migrations_dir: Path = MIGRATIONS_DIR) -> bpf_migrate.Result:
        """Apply pending migrations with ``bpf.migrate.run`` as bpf_migrator. Raises ``MigrationError``."""
        return bpf_migrate.run(migrations_dir, settings=self.settings())

    def close(self) -> None:
        """Stop the server (fast, then immediate if needed) and delete the cluster directory."""
        if self._closed:
            return
        self._closed = True
        try:
            if (self.pgdata / "PG_VERSION").exists():
                result = self.script("db-stop.sh", check=False)
                if result.returncode != 0:
                    self._as_cluster_user(
                        [
                            str(self.pg_bin / "pg_ctl"),
                            "-D",
                            str(self.pgdata),
                            "-m",
                            "immediate",
                            "-w",
                            "stop",
                        ],
                        check=False,
                    )
        finally:
            shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> PgCluster:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── running the deploy scripts ─────────────────────────────────────────────────────────────────

    def script_env(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        """Env for a deploy script: the caller's minus BPF_*/PG* (except BPF_PG_BIN), plus the overrides."""
        env = {
            k: v
            for k, v in os.environ.items()
            if not (k.startswith("BPF_") and k != "BPF_PG_BIN") and not k.startswith("PG")
        }
        env.update(
            BPF_PGDATA=str(self.pgdata),
            BPF_PG_PORT=str(self.port),
            BPF_ENV_FILE=str(self.env_file),
            BPF_SOCKET_DIR=str(self.socket_dir),
        )
        if extra:
            env.update(extra)
        return env

    def script(
        self, name: str, *args: str, env: Mapping[str, str] | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Run ``deploy/local/<name>`` against this cluster (as the cluster's OS user)."""
        result = self._as_cluster_user(
            ["bash", str(SCRIPTS_DIR / name), *args], env=self.script_env(env), check=False
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"{name} failed (exit {result.returncode})\n--- stdout\n{result.stdout}\n--- stderr\n"
                f"{result.stderr}\n--- server log (tail)\n{self.log_tail()}"
            )
        return result

    def _as_cluster_user(
        self, cmd: list[str], *, env: Mapping[str, str] | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        if self.run_as is not None:
            cmd = [self._runuser, "-u", self.run_as.pw_name, "--", *cmd]
        return subprocess.run(
            cmd,
            cwd=self.root,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            timeout=180,
            check=check,
        )

    def log_tail(self, lines: int = 40) -> str:
        try:
            return "\n".join(self.log_file.read_text(errors="replace").splitlines()[-lines:])
        except OSError:
            return "(no server log)"

    # ── credentials and connections ────────────────────────────────────────────────────────────────

    def env(self) -> dict[str, str]:
        """The app env file written by db-init.sh (contains passwords: do not print it)."""
        return {k: v for k, v in dotenv_values(self.env_file).items() if v is not None}

    def password(self, role: ClusterRole) -> str:
        if role == "admin":
            value = dotenv_values(self.admin_env_file).get("BPF_ADMIN_PASSWORD")
        else:
            value = self.env().get(f"BPF_{role.upper()}_PASSWORD")
        if not value:
            raise KeyError(f"no password for role {role!r}")
        return value

    def settings(self, **overrides: object) -> Settings:
        """``bpf.config.Settings`` for this cluster. Ignores ``.env.local`` and ``BPF_ENV_FILE``."""
        env = self.env()
        values: dict[str, object] = {
            "db_host": env["BPF_DB_HOST"],
            "db_port": int(env["BPF_DB_PORT"]),
            "db_name": env["BPF_DB_NAME"],
            "migrator_password": env["BPF_MIGRATOR_PASSWORD"],
            "ingest_password": env["BPF_INGEST_PASSWORD"],
            "api_password": env["BPF_API_PASSWORD"],
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)  # type: ignore[arg-type]

    @property
    def db_name(self) -> str:
        return self.env()["BPF_DB_NAME"]

    def conninfo(self, role: ClusterRole, *, dbname: str | None = None, host: str | None = None) -> str:
        """libpq conninfo for ``role`` over the unix socket (or ``host``, e.g. ``"127.0.0.1"``)."""
        return make_conninfo(
            host=host or str(self.socket_dir),
            port=self.port,
            dbname=dbname or self.db_name,
            user=ROLE_USERS[role],
            password=self.password(role),
            application_name=f"bpf-test-{role}",
            connect_timeout=5,
        )

    def connect(
        self,
        role: ClusterRole,
        *,
        dbname: str | None = None,
        host: str | None = None,
        autocommit: bool = False,
        **kwargs: object,
    ) -> psycopg.Connection:
        """A new psycopg connection as ``bpf_<role>`` (``admin`` = the ``bpf_admin`` superuser)."""
        return psycopg.connect(
            self.conninfo(role, dbname=dbname, host=host),
            autocommit=autocommit,
            **kwargs,  # type: ignore[arg-type]
        )

    def __repr__(self) -> str:
        return f"PgCluster(root={str(self.root)!r}, port={self.port}, pg_major={self.pg_major})"
