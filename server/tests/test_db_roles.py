"""Least-privilege and hardening checks for the cluster built by deploy/local/db-init.sh + db/migrations.

Automates everything docs/PROGRESS.md lists as tested by hand, plus the deploy-level guarantees of
docs/ARCHITECTURE.md ("Database security model"). Nothing here leaves data behind: writes happen inside
transactions that are always rolled back, and temporary roles are dropped.
"""

from __future__ import annotations

import contextlib
import ipaddress
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
from collections.abc import Callable, Iterator, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg import errors as pgerr
from psycopg import sql

from tests.pgcluster import PgCluster

pytestmark = pytest.mark.db

Connect = Callable[..., psycopg.Connection]

APP_ROLES = {"bpf_migrator", "bpf_ingest", "bpf_api"}
DATA_SCHEMAS = ("core", "app", "ops")
HISTORY_TABLES = ("core.product_chain_day", "core.store_price_day", "core.product_availability")
EXPECTED_API_VIEWS = {  # from 0001_init.sql; later migrations may add more
    "latest", "chain", "store", "category", "product", "product_chain_latest", "product_chain_history",
    "store_price_latest", "product_availability_latest", "ingredient", "recipe", "recipe_line", "ksh_latest",
    "nutrition",
}  # fmt: skip

CHAIN = "zz-rolecheck-chain"
CATEGORY = 999_901
PRODUCT = "zz-rolecheck-product"
STORE = "zz-rolecheck-store"


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────


def qualified(name: str) -> sql.Identifier:
    schema, _, rel = name.partition(".")
    return sql.Identifier(schema, rel)


def fails(
    conn: psycopg.Connection,
    query: Any,
    params: Sequence[Any] | None = None,
    *,
    error: type[Exception] | tuple[type[Exception], ...] = pgerr.InsufficientPrivilege,
    match: str | None = None,
) -> None:
    """Assert ``query`` raises ``error``. Runs in a (sub)transaction that is rolled back either way."""
    with pytest.raises(error, match=match), conn.transaction(force_rollback=True):
        conn.execute(query, params)


def relations(admin: psycopg.Connection, schemas: Sequence[str], kinds: str) -> list[tuple[str, str]]:
    """``(schema, name)`` of every relation of the given relkinds in ``schemas``."""
    rows = admin.execute(
        """
        SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(%s) AND c.relkind = ANY(%s) ORDER BY 1, 2
        """,
        (list(schemas), list(kinds)),
    ).fetchall()
    return [(str(s), str(r)) for s, r in rows]


def budapest_today(conn: psycopg.Connection) -> date:
    row = conn.execute("SELECT (now() AT TIME ZONE 'Europe/Budapest')::date").fetchone()
    assert row is not None
    return row[0]


def seed_reference(conn: psycopg.Connection, day: date) -> None:
    conn.execute(
        "INSERT INTO core.chain (id, name, slug, is_grocery) VALUES (%s, 'Role check', 'zz-rolecheck', true)",
        (CHAIN,),
    )
    conn.execute(
        "INSERT INTO core.category (id, parent_id, name, path, level, is_leaf, is_food) "
        "VALUES (%s, NULL, 'Role check', 'Role check', 1, true, true)",
        (CATEGORY,),
    )
    conn.execute(
        "INSERT INTO core.product (id, name, category_id, unit, first_seen, last_seen) "
        "VALUES (%s, 'Role check product', %s, 'kg', %s, %s)",
        (PRODUCT, CATEGORY, day, day),
    )
    conn.execute(
        "INSERT INTO core.store (id, chain_id, postal_code, first_seen, last_seen) "
        "VALUES (%s, %s, '1051', %s, %s)",
        (STORE, CHAIN, day, day),
    )


def seed_prices(conn: psycopg.Connection, day: date, amount: int = 100) -> None:
    conn.execute(
        "INSERT INTO core.product_chain_day (data_date, product_id, chain_id, product_min_amount) "
        "VALUES (%s, %s, %s, %s)",
        (day, PRODUCT, CHAIN, amount),
    )
    conn.execute(
        "INSERT INTO core.store_price_day (data_date, product_id, store_id, normal_amount) "
        "VALUES (%s, %s, %s, %s)",
        (day, PRODUCT, STORE, amount),
    )
    conn.execute(
        "INSERT INTO core.product_availability (product_id, as_of, chain_id, store_ids) "
        "VALUES (%s, %s, %s, %s)",
        (PRODUCT, day, CHAIN, [STORE]),
    )


HISTORY_UPDATES = (
    "UPDATE core.product_chain_day SET product_min_amount = product_min_amount + 1 WHERE data_date = %s",
    "UPDATE core.store_price_day SET normal_amount = normal_amount + 1 WHERE data_date = %s",
    "UPDATE core.product_availability SET store_ids = store_ids WHERE as_of = %s",
)


def setting(conn: psycopg.Connection, name: str) -> str:
    row = conn.execute("SELECT current_setting(%s)", (name,)).fetchone()
    assert row is not None
    return str(row[0])


@contextlib.contextmanager
def temporary_login_role(admin: psycopg.Connection) -> Iterator[tuple[str, str]]:
    """A throwaway LOGIN role with a random password, dropped afterwards. ``admin`` must be autocommit."""
    name = f"zz_probe_{secrets.token_hex(4)}"
    password = secrets.token_hex(16)
    admin.execute("SET log_statement = 'none'")  # keep the probe password out of the server log
    admin.execute(
        sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(name), sql.Literal(password))
    )
    admin.execute("RESET log_statement")
    try:
        yield name, password
    finally:
        admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(name)))
        admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


# ── bpf_api ─────────────────────────────────────────────────────────────────────────────────────────


def test_api_can_select_every_api_view(connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    api_rels = relations(admin, ["api"], "rvmpfS")
    kinds = dict(
        admin.execute(
            "SELECT c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'api'"
        ).fetchall()
    )
    assert {name for _, name in api_rels} >= EXPECTED_API_VIEWS
    assert set(kinds.values()) <= {"v", "m"}, f"the api schema must hold views only: {kinds}"

    api = connect_as("api", autocommit=True)
    for schema, name in api_rels:
        api.execute(sql.SQL("SELECT * FROM {} LIMIT 1").format(sql.Identifier(schema, name))).fetchall()
        # search_path = api: unqualified names resolve to the views
        api.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()


def test_api_is_denied_on_data_schemas(connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    hidden = relations(admin, [*DATA_SCHEMAS, "public"], "rvmpS")
    assert ("core", "product_chain_day") in hidden
    assert ("public", "schema_migrations") in hidden
    api = connect_as("api", autocommit=True)
    for schema, name in hidden:
        fails(
            api,
            sql.SQL("SELECT * FROM {} LIMIT 1").format(sql.Identifier(schema, name)),
            match=f"permission denied for schema {schema}",
        )
    fails(api, "SELECT core.forbid_history_rewrite()", match="permission denied for schema core")


def test_api_transactions_are_read_only(connect_as: Connect) -> None:
    api = connect_as("api", autocommit=True)
    assert setting(api, "default_transaction_read_only") == "on"
    with api.transaction(force_rollback=True):
        assert setting(api, "transaction_read_only") == "on"
    # DDL is stopped by read-only mode before privileges are even looked at.
    for query in (
        "CREATE TABLE api.zz_probe (id integer)",
        "CREATE TABLE public.zz_probe (id integer)",
        "CREATE TABLE core.zz_probe (id integer)",
        "CREATE SCHEMA zz_probe",
        "CREATE VIEW api.zz_probe AS SELECT 1 AS x",
        "ALTER VIEW api.chain RENAME TO zz_probe",
        "DROP VIEW api.chain",
    ):
        fails(api, query, error=pgerr.ReadOnlySqlTransaction, match="read-only transaction")
    # DML hits the missing privilege first; read-only mode is the second wall (see the next test).
    for query in (
        "INSERT INTO api.chain (id, name, slug, is_grocery) VALUES ('x', 'x', 'x', true)",
        "UPDATE api.chain SET name = name",
        "DELETE FROM api.chain",
        "INSERT INTO core.chain (id, name, slug, is_grocery) VALUES ('x', 'x', 'x', true)",
        "UPDATE core.product_chain_day SET product_min_amount = 0",
        "DELETE FROM core.product_chain_day",
    ):
        fails(api, query, error=(pgerr.ReadOnlySqlTransaction, pgerr.InsufficientPrivilege))


def test_api_writes_fail_even_in_a_read_write_transaction(connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    api = connect_as("api", autocommit=True)
    api.execute("SET default_transaction_read_only = off")  # a compromised API process could do this
    denied = (pgerr.InsufficientPrivilege, pgerr.FeatureNotSupported, pgerr.ObjectNotInPrerequisiteState)
    for schema, name in relations(admin, ["api"], "vm"):
        view = sql.Identifier(schema, name)
        fails(api, sql.SQL("INSERT INTO {} DEFAULT VALUES").format(view), error=denied)
        fails(api, sql.SQL("DELETE FROM {}").format(view), error=denied)
        column = admin.execute(
            "SELECT attname FROM pg_attribute WHERE attrelid = %s::regclass AND attnum = 1",
            (f"{schema}.{name}",),
        ).fetchone()
        assert column is not None
        col = sql.Identifier(column[0])
        fails(api, sql.SQL("UPDATE {} SET {} = {}").format(view, col, col), error=denied)
    for schema, name in relations(admin, DATA_SCHEMAS, "r"):
        fails(api, sql.SQL("DELETE FROM {}").format(sql.Identifier(schema, name)), match="permission denied")
    for schema in ("api", "public", *DATA_SCHEMAS):
        fails(api, sql.SQL("CREATE TABLE {} (id integer)").format(sql.Identifier(schema, "zz_probe")))
        fails(api, sql.SQL("CREATE VIEW {} AS SELECT 1 AS x").format(sql.Identifier(schema, "zz_probe")))
        fails(
            api,
            sql.SQL("CREATE FUNCTION {}() RETURNS integer LANGUAGE sql AS 'SELECT 1'").format(
                sql.Identifier(schema, "zz_probe")
            ),
        )
    fails(api, "CREATE TEMP TABLE zz_probe (id integer)", match="temporary tables")
    fails(api, "CREATE SCHEMA zz_probe", match="permission denied for database")


def test_api_cannot_switch_role(connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    others = [
        r for (r,) in admin.execute("SELECT rolname FROM pg_roles WHERE rolname <> 'bpf_api' ORDER BY 1")
    ]
    assert {"bpf_admin", "bpf_owner", "bpf_migrator", "bpf_ingest", "pg_read_all_data"} <= set(others)
    memberships = admin.execute(
        "SELECT count(*) FROM pg_auth_members WHERE member = 'bpf_api'::regrole"
    ).fetchone()
    assert memberships == (0,)

    api = connect_as("api", autocommit=True)
    for role in others:
        fails(api, sql.SQL("SET ROLE {}").format(sql.Identifier(role)), match="permission denied to set role")
    fails(api, "SET SESSION AUTHORIZATION bpf_admin", match="permission denied to set session authorization")


def test_api_role_limits_and_session_defaults(connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    flags = admin.execute(
        "SELECT rolconnlimit, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit "
        "FROM pg_roles WHERE rolname = 'bpf_api'"
    ).fetchone()
    assert flags == (20, False, False, False, False, False, True)
    api = connect_as("api", autocommit=True)
    assert setting(api, "default_transaction_read_only") == "on"
    assert setting(api, "statement_timeout") == "3s"
    assert setting(api, "lock_timeout") == "1s"
    assert setting(api, "idle_in_transaction_session_timeout") == "10s"
    assert setting(api, "search_path") == "api"
    fails(api, "SELECT pg_sleep(5)", error=pgerr.QueryCanceled, match="statement timeout")


def test_api_session_defaults_are_not_the_only_barrier(connect_as: Connect) -> None:
    """read_only and statement_timeout are user-settable session defaults, so they are not enforcement.
    deploy/local/sql/harden-functions.sql closes what table GRANTs do not cover: large objects (writes no
    GRANT controls), advisory locks (bpf_api could block the ingest's lock) and temp files."""
    api = connect_as("api", autocommit=True)
    api.execute("SET default_transaction_read_only = off")
    api.execute("SET statement_timeout = 0")
    for statement in (
        "SELECT lo_from_bytea(0, '\\x00'::bytea)",
        "SELECT lo_creat(-1)",
        "SELECT lo_create(0)",
        "SELECT pg_try_advisory_lock(727100, 2)",
        "SELECT pg_advisory_lock(1::bigint)",
        "SELECT pg_try_advisory_xact_lock(1::bigint)",
        "SELECT pg_advisory_lock_shared(1::bigint)",
    ):
        fails(api, statement, error=pgerr.InsufficientPrivilege, match="permission denied for function")
    assert setting(api, "temp_file_limit") == "64MB"
    fails(api, "SET temp_file_limit = '1GB'", error=pgerr.InsufficientPrivilege, match="temp_file_limit")


def test_only_the_advisory_locks_the_code_uses_are_granted(connect_as: Connect) -> None:
    ingest = connect_as("ingest", autocommit=True)
    assert ingest.execute("SELECT pg_try_advisory_lock(727199, 9)").fetchone() == (True,)
    assert ingest.execute("SELECT pg_advisory_unlock(727199, 9)").fetchone() == (True,)
    with ingest.transaction():
        ingest.execute("SELECT pg_advisory_xact_lock(727199::bigint)")
    fails(ingest, "SELECT pg_advisory_lock(727199::bigint)", error=pgerr.InsufficientPrivilege)
    fails(ingest, "SELECT lo_from_bytea(0, '\\x00'::bytea)", error=pgerr.InsufficientPrivilege)
    migrator = connect_as("migrator", autocommit=True)
    migrator.execute("SELECT pg_advisory_lock(727198::bigint)")
    assert migrator.execute("SELECT pg_advisory_unlock(727198::bigint)").fetchone() == (True,)
    fails(migrator, "SELECT pg_try_advisory_lock(727100, 2)", error=pgerr.InsufficientPrivilege)
    fails(migrator, "SELECT lo_from_bytea(0, '\\x00'::bytea)", error=pgerr.InsufficientPrivilege)


def test_db_harden_script_is_idempotent(pg: PgCluster, connect_as: Connect) -> None:
    pg.script("db-harden.sh")
    pg.script("db-harden.sh")
    api = connect_as("api", autocommit=True)
    fails(api, "SELECT pg_try_advisory_lock(727100, 2)", error=pgerr.InsufficientPrivilege)


# ── bpf_ingest ──────────────────────────────────────────────────────────────────────────────────────


def test_ingest_session_defaults(connect_as: Connect) -> None:
    ingest = connect_as("ingest", autocommit=True)
    assert setting(ingest, "statement_timeout") == "10min"
    assert setting(ingest, "lock_timeout") == "10s"
    assert setting(ingest, "search_path") == "core, app, ops, api"
    assert setting(ingest, "default_transaction_read_only") == "off"


def test_ingest_can_insert_and_update_data(connect_as: Connect) -> None:
    ingest = connect_as("ingest", autocommit=True)
    with ingest.transaction(force_rollback=True):
        today = budapest_today(ingest)
        seed_reference(ingest, today)
        seed_prices(ingest, today)
        for query, params in (
            ("UPDATE core.chain SET name = 'Renamed' WHERE id = %s", (CHAIN,)),
            ("UPDATE core.category SET name = 'Renamed' WHERE id = %s", (CATEGORY,)),
            ("UPDATE core.product SET last_seen = %s WHERE id = %s", (today, PRODUCT)),
            ("UPDATE core.store SET has_data_date = %s WHERE id = %s", (today, STORE)),
            *((q, (today,)) for q in HISTORY_UPDATES),
        ):
            assert ingest.execute(query, params).rowcount == 1, query

        run = ingest.execute(
            "INSERT INTO ops.ingest_run (kind, status, data_date) VALUES ('daily', 'running', %s) "
            "RETURNING id",
            (today,),
        ).fetchone()
        assert run is not None
        updated = ingest.execute(
            "UPDATE ops.ingest_run SET status = 'ok', finished_at = now() WHERE id = %s", (run[0],)
        )
        assert updated.rowcount == 1
        ingest.execute("SELECT data_date, ingested_at FROM api.latest").fetchone()

        ingest.execute(
            "INSERT INTO app.nutrition (code, source, name, kcal) "
            "VALUES ('zz-rolecheck', 'ciqual', 'Probe', 1)"
        )
        ingest.execute(
            "INSERT INTO app.ingredient (id, name_hu, list_group, unit, nutrition_code) "
            "VALUES ('zz_rolecheck', 'Próba', 'egyeb', 'kg', 'zz-rolecheck')"
        )
        ingest.execute(
            "INSERT INTO app.recipe (id, title, slots, servings, steps) "
            "VALUES ('zz-rolecheck', 'Próba', ARRAY['ebed'], 2, ARRAY['Főzd meg.'])"
        )
        ingest.execute(
            "INSERT INTO app.recipe_line (recipe_id, line_no, ingredient_id, qty, display) "
            "VALUES ('zz-rolecheck', 1, 'zz_rolecheck', 0.5, '50 dkg')"
        )
        ingest.execute(
            "INSERT INTO app.ksh_price (period, code, name, unit, price) "
            "VALUES ('2999-01-01', 'zz.1', 'Probe', 'kg', 1)"
        )
        assert ingest.execute("UPDATE app.recipe SET tested = true WHERE id = 'zz-rolecheck'").rowcount == 1
        assert ingest.execute("DELETE FROM app.recipe_line WHERE recipe_id = 'zz-rolecheck'").rowcount == 1


def test_ingest_cannot_create_or_alter_anything(connect_as: Connect) -> None:
    ingest = connect_as("ingest", autocommit=True)
    for schema in ("core", "app", "ops", "api", "public"):
        fails(ingest, sql.SQL("CREATE TABLE {} (id integer)").format(sql.Identifier(schema, "zz_probe")))
        fails(ingest, sql.SQL("CREATE VIEW {} AS SELECT 1 AS x").format(sql.Identifier(schema, "zz_probe")))
        fails(
            ingest,
            sql.SQL("CREATE FUNCTION {}() RETURNS integer LANGUAGE sql AS 'SELECT 1'").format(
                sql.Identifier(schema, "zz_probe")
            ),
        )
    fails(ingest, "CREATE TABLE zz_probe (id integer)")  # unqualified: first schema on the search_path
    fails(ingest, "CREATE TEMP TABLE zz_probe (id integer)", match="temporary tables")
    fails(ingest, "CREATE SCHEMA zz_probe", match="permission denied for database")
    fails(ingest, "ALTER TABLE core.chain ADD COLUMN zz integer", match="must be owner")
    fails(ingest, "DROP TABLE core.product_chain_day", match="must be owner")
    fails(ingest, "ALTER TABLE core.product_chain_day DISABLE TRIGGER pcd_append_only", match="must be owner")
    fails(ingest, "SET ROLE bpf_owner", match="permission denied to set role")
    fails(ingest, "SELECT * FROM public.schema_migrations", match="permission denied for schema public")


@pytest.mark.parametrize(
    "table", [*HISTORY_TABLES, "core.chain", "core.store", "core.category", "core.product", "ops.ingest_run"]
)
def test_ingest_cannot_delete_or_truncate(connect_as: Connect, table: str) -> None:
    ingest = connect_as("ingest", autocommit=True)
    fails(ingest, sql.SQL("DELETE FROM {}").format(qualified(table)), match="permission denied for table")
    fails(ingest, sql.SQL("TRUNCATE {}").format(qualified(table)), match="permission denied for table")


def test_price_history_is_append_only(connect_as: Connect) -> None:
    ingest = connect_as("ingest", autocommit=True)
    with ingest.transaction(force_rollback=True):
        today = budapest_today(ingest)
        seed_reference(ingest, today)
        for days_ago in (0, 1, 2, 30):
            seed_prices(ingest, today - timedelta(days=days_ago))  # INSERT of any day is fine (backfill)
        for query in HISTORY_UPDATES:
            # today and yesterday stay correctable so a re-run of the daily ingest is idempotent
            for days_ago in (0, 1):
                assert ingest.execute(query, (today - timedelta(days=days_ago),)).rowcount == 1
            for days_ago in (2, 30):
                fails(ingest, query, (today - timedelta(days=days_ago),), match="history is append-only")

    # The trigger binds the superuser too: past rows cannot be deleted by anyone.
    admin = connect_as("admin", autocommit=True)
    with admin.transaction(force_rollback=True):
        today = budapest_today(admin)
        seed_reference(admin, today)
        seed_prices(admin, today - timedelta(days=2))
        for table in HISTORY_TABLES:
            column = "as_of" if table.endswith("availability") else "data_date"
            fails(
                admin,
                sql.SQL("DELETE FROM {} WHERE {} = %s").format(qualified(table), sql.Identifier(column)),
                (today - timedelta(days=2),),
                match="history is append-only",
            )


# ── views: latest successful daily run ─────────────────────────────────────────────────────────────


def test_latest_views_follow_the_latest_successful_daily_run(connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    base = date(2999, 1, 10)  # far future: wins over anything other tests may have committed

    def as_api() -> tuple[date | None, list[tuple[date, Any]]]:
        admin.execute("SET LOCAL ROLE bpf_api")
        latest = admin.execute("SELECT data_date FROM api.latest").fetchone()
        rows = admin.execute(
            "SELECT data_date, product_min_amount FROM api.product_chain_latest WHERE product_id = %s",
            (PRODUCT,),
        ).fetchall()
        admin.execute("RESET ROLE")
        assert latest is not None
        return latest[0], rows

    with admin.transaction(force_rollback=True):
        seed_reference(admin, base)
        for offset, amount in ((-2, 100), (-1, 200), (0, 300)):
            seed_prices(admin, base + timedelta(days=offset), amount)
        admin.execute(
            """
            INSERT INTO ops.ingest_run (kind, status, data_date, finished_at) VALUES
                ('daily', 'ok', %(d2)s, now()),
                ('daily', 'partial', %(d1)s, now()),
                ('daily', 'failed', %(d0)s, now()),
                ('daily', 'running', %(d0)s, NULL),
                ('availability', 'ok', %(future)s, now()),
                ('reference', 'ok', %(future)s, now())
            """,
            {
                "d2": base - timedelta(days=2),
                "d1": base - timedelta(days=1),
                "d0": base,
                "future": base + timedelta(days=5),
            },
        )
        latest, rows = as_api()
        assert latest == base - timedelta(days=1)  # 'partial' counts, 'failed'/'running'/other kinds do not
        assert [(d, int(a)) for d, a in rows] == [(base - timedelta(days=1), 200)]

        admin.execute(
            "INSERT INTO ops.ingest_run (kind, status, data_date, finished_at) "
            "VALUES ('daily', 'ok', %s, now())",
            (base,),
        )
        latest, rows = as_api()
        assert latest == base
        assert [(d, int(a)) for d, a in rows] == [(base, 300)]


# ── bpf_migrator ────────────────────────────────────────────────────────────────────────────────────


def test_migrator_has_owner_rights_only_after_set_role(connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    membership = admin.execute(
        "SELECT inherit_option, set_option, admin_option FROM pg_auth_members "
        "WHERE roleid = 'bpf_owner'::regrole AND member = 'bpf_migrator'::regrole"
    ).fetchall()
    assert membership == [(False, True, False)]

    migrator = connect_as("migrator", autocommit=True)
    assert setting(migrator, "lock_timeout") == "10s"
    assert setting(migrator, "search_path") == "public"
    fails(migrator, "SELECT count(*) FROM core.chain", match="permission denied for schema core")
    fails(migrator, "CREATE TABLE public.zz_probe (id integer)", match="permission denied for schema public")
    for role in ("bpf_admin", "bpf_api", "bpf_ingest"):
        fails(
            migrator,
            sql.SQL("SET ROLE {}").format(sql.Identifier(role)),
            match="permission denied to set role",
        )
    with migrator.transaction(force_rollback=True):
        migrator.execute("SET LOCAL ROLE bpf_owner")
        migrator.execute("SELECT count(*) FROM core.chain").fetchone()


# ── connecting: PUBLIC, pg_hba.conf, authentication ─────────────────────────────────────────────────


def test_public_has_no_database_privileges(pg: PgCluster, connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    db = pg.db_name
    acl = admin.execute("SELECT datacl::text[] FROM pg_database WHERE datname = %s", (db,)).fetchone()
    assert acl is not None
    assert not [entry for entry in acl[0] if entry.startswith("=")], (
        f"PUBLIC has privileges on {db}: {acl[0]}"
    )
    for role in ("public", *APP_ROLES):
        assert admin.execute(
            "SELECT has_database_privilege(%s, %s, 'TEMPORARY') OR has_database_privilege(%s, %s, 'CREATE')",
            (role, db, role, db),
        ).fetchone() == (False,), role
        assert admin.execute(
            "SELECT has_schema_privilege(%s, 'public', 'USAGE') "
            "OR has_schema_privilege(%s, 'public', 'CREATE')",
            (role, role),
        ).fetchone() == (False,), role

    with temporary_login_role(admin) as (role, password):
        for database in (db, "postgres", "template1"):
            assert admin.execute(
                "SELECT has_database_privilege(%s, %s, 'CONNECT')", (role, database)
            ).fetchone() == (False,), database
        with pytest.raises(psycopg.OperationalError):
            psycopg.connect(
                host=str(pg.socket_dir),
                port=pg.port,
                dbname=db,
                user=role,
                password=password,
                connect_timeout=5,
            )

    # CONNECT really is the gate (not only pg_hba.conf): without its explicit grant, bpf_api is refused.
    admin.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM bpf_api").format(sql.Identifier(db)))
    try:
        with pytest.raises(psycopg.OperationalError, match="permission denied for database"):
            pg.connect("api").close()
    finally:
        admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO bpf_api").format(sql.Identifier(db)))
    pg.connect("api").close()


def test_pg_hba_refuses_other_roles_and_databases(pg: PgCluster, connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    db = pg.db_name
    with temporary_login_role(admin) as (role, password):
        admin.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db), sql.Identifier(role))
        )
        try:
            for host in (str(pg.socket_dir), "127.0.0.1"):
                with pytest.raises(psycopg.OperationalError, match="pg_hba.conf rejects connection"):
                    psycopg.connect(
                        host=host, port=pg.port, dbname=db, user=role, password=password, connect_timeout=5
                    )
        finally:
            admin.execute(
                sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(
                    sql.Identifier(db), sql.Identifier(role)
                )
            )
    # The app roles reach the app database only.
    for app_role in ("api", "ingest", "migrator"):
        for other_db in ("postgres", "template1"):
            with pytest.raises(psycopg.OperationalError, match="pg_hba.conf rejects connection"):
                pg.connect(app_role, dbname=other_db)
    # TCP on 127.0.0.1 works for the app roles (SCRAM), and a wrong password is refused.
    pg.connect("api", host="127.0.0.1").close()
    with pytest.raises(psycopg.OperationalError, match="password authentication failed"):
        psycopg.connect(
            host="127.0.0.1", port=pg.port, dbname=db, user="bpf_api", password="wrong", connect_timeout=5
        )


def test_pg_hba_is_scram_only_and_rejects_the_rest(pg: PgCluster, connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    rules = admin.execute(
        "SELECT type, database, user_name, address, auth_method, error "
        "FROM pg_hba_file_rules ORDER BY rule_number"
    ).fetchall()
    assert rules
    for type_, databases, users, address, method, error in rules:
        assert error is None
        assert type_ in ("local", "host")
        assert method in ("scram-sha-256", "reject"), f"forbidden auth method {method}"
        if method == "scram-sha-256":
            assert set(users) <= APP_ROLES | {"bpf_admin"}
            if set(users) & APP_ROLES:
                assert "bpf_admin" not in users
                assert databases == [pg.db_name]
            if type_ == "host":
                assert address in ("127.0.0.1", "::1")
    rejects = {(t, tuple(d), a) for t, d, u, a, m, _ in rules if m == "reject" and u == ["all"]}
    any_v4 = "0.0.0.0"  # noqa: S104 - an address in a pg_hba rule, not a bind
    assert {("local", ("all",), None), ("host", ("all",), any_v4), ("host", ("all",), "::")} <= rejects
    assert rules[-1][4] == "reject"


def test_passwords_are_scram_and_roles_minimal(connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    rows = admin.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, "
        "rolpassword FROM pg_authid WHERE rolname LIKE 'bpf\\_%' ORDER BY rolname"
    ).fetchall()
    by_name = {r[0]: r for r in rows}
    assert set(by_name) == {"bpf_admin", "bpf_owner", "bpf_migrator", "bpf_ingest", "bpf_api"}
    for name, can_login, superuser, createdb, createrole, replication, bypassrls, password in rows:
        if name == "bpf_owner":
            assert not can_login
            assert password is None
        else:
            assert can_login
            assert password.startswith("SCRAM-SHA-256$"), name
        if name != "bpf_admin":
            assert [superuser, createdb, createrole, replication, bypassrls] == [False] * 5, name
    assert setting(admin, "password_encryption") == "scram-sha-256"


def test_server_log_never_contains_passwords(pg: PgCluster) -> None:
    log = pg.log_file.read_text(errors="replace")
    assert "connection authorized" in log  # log_connections is on
    for role in ("api", "ingest", "migrator", "admin"):
        assert pg.password(role) not in log, f"the {role} password leaked into the server log"


# ── files, sockets, listening addresses, server settings ───────────────────────────────────────────


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_credentials_files_are_private(pg: PgCluster) -> None:
    for path in (pg.env_file, pg.admin_env_file):
        assert mode(path) == 0o600, path
    env = pg.env()
    assert set(env) == {
        "BPF_DB_HOST",
        "BPF_DB_PORT",
        "BPF_DB_NAME",
        "BPF_MIGRATOR_PASSWORD",
        "BPF_INGEST_PASSWORD",
        "BPF_API_PASSWORD",
    }
    for key in ("BPF_MIGRATOR_PASSWORD", "BPF_INGEST_PASSWORD", "BPF_API_PASSWORD"):
        assert re.fullmatch(r"[0-9a-f]{64}", env[key]), f"{key} is not 32 random bytes in hex"
    assert len({env[k] for k in env if k.endswith("_PASSWORD")} | {pg.password("admin")}) == 4
    assert "BPF_ADMIN_PASSWORD" not in pg.env_file.read_text()  # the app never gets the superuser


def test_socket_dir_is_private(pg: PgCluster) -> None:
    assert mode(pg.socket_dir) == 0o700
    sock = pg.socket_dir / f".s.PGSQL.{pg.port}"
    assert stat.S_ISSOCK(sock.lstat().st_mode)
    assert mode(sock) == 0o700
    assert mode(pg.pgdata) == 0o700


def test_server_settings(pg: PgCluster, connect_as: Connect) -> None:
    admin = connect_as("admin", autocommit=True)
    expected = {
        "listen_addresses": "localhost",
        "port": str(pg.port),
        "unix_socket_directories": str(pg.socket_dir),
        "unix_socket_permissions": "0700",
        "password_encryption": "scram-sha-256",
        "ssl": "off",
        "log_connections": "on",
        "log_disconnections": "on",
        "log_statement": "ddl",
        "log_min_duration_statement": "500ms",
        "max_connections": "50",
        "idle_in_transaction_session_timeout": "1min",
        "server_encoding": "UTF8",
    }
    assert {name: setting(admin, name) for name in expected} == expected
    major = int(setting(admin, "server_version_num")) // 10000
    assert major == pg.pg_major >= 16
    row = admin.execute(
        "SELECT datlocprovider::text, datcollate FROM pg_database WHERE datname = current_database()"
    ).fetchone()
    assert row is not None
    if major >= 17:
        assert row[0] == "b"  # builtin C.UTF-8 provider


def _non_loopback_addresses() -> set[str]:
    found: set[str] = set()
    with contextlib.suppress(OSError):
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(str(info[4][0]))
    with contextlib.suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("192.0.2.1", 9))  # UDP connect sends nothing; it only picks the outbound address
        found.add(str(probe.getsockname()[0]))
    return {
        a
        for a in found
        if not (ipaddress.ip_address(a).is_loopback or ipaddress.ip_address(a).is_unspecified)
    }


def test_nothing_listens_beyond_localhost(pg: PgCluster) -> None:
    with socket.create_connection(("127.0.0.1", pg.port), timeout=5):
        pass
    for address in sorted(_non_loopback_addresses()):
        with pytest.raises(OSError), socket.create_connection((address, pg.port), timeout=2):  # noqa: PT011
            pass


# ── deploy scripts ──────────────────────────────────────────────────────────────────────────────────


def _written(result: subprocess.CompletedProcess[str]) -> Path:
    match = re.search(r"Backup written: (.+)$", result.stdout, re.MULTILINE)
    assert match, result.stdout
    return Path(match.group(1).strip())


def test_backup_is_private_and_can_be_encrypted(pg: PgCluster, tmp_path: Path) -> None:
    secrets_ = [pg.password(r) for r in ("api", "ingest", "migrator", "admin")]
    result = pg.script("db-backup.sh")
    assert not any(s in result.stdout + result.stderr for s in secrets_)
    dump = _written(result)
    assert dump.parent == pg.backup_dir
    assert re.fullmatch(rf"{pg.db_name}-\d{{8}}T\d{{6}}Z\.dump", dump.name)
    assert mode(pg.backup_dir) == 0o700
    assert mode(dump) == 0o600
    assert dump.read_bytes()[:5] == b"PGDMP"

    if not (shutil.which("age") and shutil.which("age-keygen")):
        pytest.skip("age is not installed; the encrypted-backup half of this test needs it")
    identity = subprocess.run(["age-keygen"], capture_output=True, text=True, check=True).stdout
    recipient = re.search(r"public key: (age1[0-9a-z]+)", identity)
    assert recipient
    key_file = tmp_path / "backup.key"
    key_file.write_text(identity)
    os.chmod(key_file, 0o600)

    plain_before = set(pg.backup_dir.glob("*.dump"))
    encrypted = _written(pg.script("db-backup.sh", env={"BPF_BACKUP_AGE_RECIPIENT": recipient.group(1)}))
    assert encrypted.name.endswith(".dump.age")
    assert mode(encrypted) == 0o600
    assert set(pg.backup_dir.glob("*.dump")) == plain_before, "no plaintext dump may be written"
    assert encrypted.read_bytes().startswith(b"age-encryption.org/v1")
    decrypted = subprocess.run(
        ["age", "--decrypt", "-i", str(key_file), str(encrypted)], capture_output=True, check=True
    ).stdout
    assert decrypted[:5] == b"PGDMP"

    # An unusable recipient fails loudly and leaves nothing behind.
    failed = pg.script("db-backup.sh", env={"BPF_BACKUP_AGE_RECIPIENT": "age1notakey"}, check=False)
    assert failed.returncode != 0
    assert set(pg.backup_dir.iterdir()) == {dump, encrypted}


def test_start_and_stop_are_idempotent(pg_factory: Callable[..., PgCluster]) -> None:
    cluster = pg_factory(
        migrate=False
    )  # not the shared cluster: other tests may hold pooled connections to it
    try:
        assert "already running" in cluster.script("db-start.sh").stdout
        assert "stopped" in cluster.script("db-stop.sh").stdout
        assert "not running" in cluster.script("db-stop.sh").stdout
        with pytest.raises(psycopg.OperationalError):
            cluster.connect("api", connect_timeout=2)
        assert "started" in cluster.script("db-start.sh").stdout
        cluster.connect("api").close()
    finally:
        cluster.close()


def test_init_refuses_to_clobber(pg: PgCluster) -> None:
    before = pg.env_file.read_bytes()
    result = pg.script("db-init.sh", check=False)
    assert result.returncode == 1
    assert "refusing" in result.stderr
    assert "To start over" in result.stderr
    assert pg.env_file.read_bytes() == before
