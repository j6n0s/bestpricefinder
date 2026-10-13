"""Shared pytest fixtures.

Database fixtures (all skip with a clear reason when no PostgreSQL >= 16 binaries are installed):

- ``pg``          session-scoped :class:`tests.pgcluster.PgCluster` with every migration applied. Shared by
                  all DB tests: leave it as you found it (see the rules in ``tests/pgcluster.py``).
- ``pg_factory``  ``pg_factory(migrate=False)`` makes an extra throwaway cluster, closed at session end.
- ``connect_as``  ``connect_as("api")`` returns a psycopg connection to ``pg`` as ``bpf_api`` (also "ingest",
                  "migrator" and "admin" = the ``bpf_admin`` superuser), closed after the test. Keyword
                  arguments go to :meth:`PgCluster.connect` (``autocommit``, ``dbname``, ``host``...).

Mark DB tests with ``pytest.mark.db`` (``pytestmark = pytest.mark.db`` at module level); run only the fast
tests with ``pytest -m "not db"``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest

from tests.pgcluster import MIGRATIONS_DIR, ClusterRole, PgCluster, PgUnavailable


@pytest.fixture(scope="session")
def pg_factory() -> Iterator[Callable[..., PgCluster]]:
    clusters: list[PgCluster] = []

    def make(*, migrate: bool = True, migrations_dir: Path = MIGRATIONS_DIR) -> PgCluster:
        try:
            cluster = PgCluster.create(migrate=migrate, migrations_dir=migrations_dir)
        except PgUnavailable as exc:
            pytest.skip(f"needs PostgreSQL >= 16: {exc}")
        clusters.append(cluster)
        return cluster

    yield make
    for cluster in clusters:
        cluster.close()


@pytest.fixture(scope="session")
def pg(pg_factory: Callable[..., PgCluster]) -> PgCluster:
    return pg_factory()


@pytest.fixture
def connect_as(pg: PgCluster) -> Iterator[Callable[..., psycopg.Connection]]:
    opened: list[psycopg.Connection] = []

    def _connect(role: ClusterRole, **kwargs: object) -> psycopg.Connection:
        conn = pg.connect(role, **kwargs)  # type: ignore[arg-type]
        opened.append(conn)
        return conn

    yield _connect
    for conn in opened:
        conn.close()
