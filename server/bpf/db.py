"""Database connections, one PostgreSQL role per component (docs/ARCHITECTURE.md, least privilege).

==========  ===============  =========================================================================
role        login role       used by
==========  ===============  =========================================================================
api         ``bpf_api``      the public API: SELECT on ``api.*`` views only, read-only transactions
ingest      ``bpf_ingest``   the daily ingest and the content loader: INSERT/UPDATE on data tables
migrator    ``bpf_migrator`` ``bpf.migrate`` only; it must ``SET ROLE bpf_owner`` to change anything
==========  ===============  =========================================================================

Usage::

    from bpf.db import connect, open_pool

    with connect("ingest") as conn:          # one-off job; commits on clean exit of the with-block
        conn.execute("INSERT INTO ops.ingest_run (kind, status) VALUES ('daily', 'running')")

    pool = open_pool("api", min_size=1, max_size=8)   # long-lived; close it on shutdown
    with pool.connection() as conn:
        conn.execute("SELECT data_date FROM api.latest").fetchone()

A conninfo string contains a password: never log it, put it in an exception message or return it to a client.

Every connection pins ``require_auth=scram-sha-256`` (libpq >= 16; psycopg[binary] ships 18). The cluster's
pg_hba.conf accepts nothing else, so a server asking for any other method (a cleartext or md5 password, trust,
peer) is an impostor, e.g. a process that bound the port or pre-created the socket while the cluster was
down: libpq then refuses without sending the password. An impostor that does ask for SCRAM only sees a salted
proof (useless against the 256-bit random passwords db-init.sh generates), and SCRAM makes the server prove it
holds the role's verifier, so an impostor cannot complete the login and serve fake rows either.
"""

from __future__ import annotations

from typing import Any, Literal, get_args

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

from bpf.config import Settings, get_settings

Role = Literal["api", "ingest", "migrator"]
ROLES: tuple[Role, ...] = get_args(Role)
REQUIRE_AUTH = "scram-sha-256"  # the only method deploy/local/db-init.sh's pg_hba.conf allows


class MissingCredentialsError(RuntimeError):
    """The password for a database role is not configured."""


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise ValueError(f"unknown database role {role!r}; expected one of {', '.join(ROLES)}")


def conninfo(role: Role, settings: Settings | None = None) -> str:
    """libpq connection string for app role ``role``. Contains the password: never log it."""
    _check_role(role)
    s = settings if settings is not None else get_settings()
    password = s.password_for(role)
    if password is None or not password.get_secret_value():
        raise MissingCredentialsError(
            f"BPF_{role.upper()}_PASSWORD is not set. Run deploy/local/db-init.sh, or point BPF_ENV_FILE at "
            "the env file it wrote."
        )
    return make_conninfo(
        host=s.db_host,
        port=s.db_port,
        dbname=s.db_name,
        user=f"bpf_{role}",
        password=password.get_secret_value(),
        require_auth=REQUIRE_AUTH,  # never answer a cleartext/md5 request with the password
        application_name=f"bpf-{role}",
        connect_timeout=5,
    )


def connect(
    role: Role, *, settings: Settings | None = None, autocommit: bool = False, **kwargs: Any
) -> psycopg.Connection:
    """Open a single connection as ``bpf_<role>``. Extra keyword arguments go to ``psycopg.connect``."""
    return psycopg.connect(conninfo(role, settings), autocommit=autocommit, **kwargs)


def open_pool(
    role: Role,
    min_size: int = 1,
    max_size: int = 4,
    *,
    settings: Settings | None = None,
    timeout: float = 10.0,
    max_lifetime: float = 30 * 60.0,
    max_idle: float = 10 * 60.0,
    kwargs: dict[str, Any] | None = None,
) -> ConnectionPool:
    """Open a connection pool for ``bpf_<role>``.

    Connections are health-checked when handed out (``ConnectionPool.check_connection``), recycled after
    ``max_lifetime`` seconds, and ``getconn``/``connection()`` give up after ``timeout`` seconds. ``kwargs``
    are passed to every ``psycopg.connect`` (e.g. ``{"autocommit": True}``). The pool is opened without
    waiting for ``min_size`` connections; call ``pool.wait()`` to fail fast at startup. Close it on shutdown.
    """
    return ConnectionPool(
        conninfo(role, settings),
        min_size=min_size,
        max_size=max_size,
        kwargs=kwargs,
        open=True,
        check=ConnectionPool.check_connection,
        name=f"bpf-{role}",
        timeout=timeout,
        max_lifetime=max_lifetime,
        max_idle=max_idle,
    )
