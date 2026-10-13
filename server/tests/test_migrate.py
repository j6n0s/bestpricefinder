"""bpf.migrate: file-name rules, checksums, ordering, --check exit codes and transactional apply."""

from __future__ import annotations

import hashlib
import logging
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from bpf import migrate
from bpf.config import Settings
from tests.pgcluster import MIGRATIONS_DIR, PgCluster

# Settings that cannot reach any server: the file checks must fail before a connection is attempted.
UNREACHABLE = Settings(
    _env_file=None, db_host="/nonexistent-bpf-socket-dir", db_port=1, migrator_password="unused"
)


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def run_main(args: list[str], settings: Settings) -> tuple[int, str]:
    """Run the CLI entry point; return (exit code, everything it logged)."""
    handler = _Collect()
    logger = logging.getLogger("bpf.migrate")
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        code = migrate.main(args, settings=settings)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    return code, "\n".join(handler.messages)


def copy_migrations(dest: Path) -> Path:
    shutil.copytree(MIGRATIONS_DIR, dest)
    return dest


def applied_rows(cluster: PgCluster) -> list[tuple]:
    with cluster.connect("admin", autocommit=True) as conn:
        return conn.execute(
            "SELECT version, filename, sha256, applied_at FROM public.schema_migrations ORDER BY version"
        ).fetchall()


def regclass(cluster: PgCluster, name: str) -> str | None:
    with cluster.connect("admin", autocommit=True) as conn:
        row = conn.execute("SELECT to_regclass(%s)::text", (name,)).fetchone()
        return row[0] if row else None


def expected_rows() -> list[tuple[int, str, str]]:
    return [
        (int(p.name[:4]), p.name, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(MIGRATIONS_DIR.glob("*.sql"))
    ]


# ── file checks (no database needed) ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_name",
    [
        "1_init.sql",
        "00002_init.sql",
        "0002-init.sql",
        "0002_Init.sql",
        "0002_init.SQL",
        "0002_init.sql.bak",
        "0002_.sql",
        "0002_init",
        "0002_in it.sql",
        "init.sql",
    ],
)
def test_bad_file_name_is_rejected(tmp_path: Path, bad_name: str) -> None:
    (tmp_path / "0001_ok.sql").write_text("SELECT 1;\n")
    (tmp_path / bad_name).write_text("SELECT 1;\n")
    code, logged = run_main(["--dir", str(tmp_path)], UNREACHABLE)
    assert code == 1
    assert "invalid migration file name" in logged
    assert bad_name in logged
    assert "cannot connect" not in logged


def test_duplicate_version_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "0001_first.sql").write_text("SELECT 1;\n")
    (tmp_path / "0001_second.sql").write_text("SELECT 2;\n")
    code, logged = run_main(["--dir", str(tmp_path)], UNREACHABLE)
    assert code == 1
    assert "duplicate migration version 0001" in logged


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("0000_zero.sql", b"SELECT 1;\n", "start at 0001"),
        ("0001_empty.sql", b"  \n\n", "is empty"),
        ("0001_latin2.sql", "SELECT 'árvíztűrő';\n".encode("iso-8859-2"), "not valid UTF-8"),
    ],
)
def test_unusable_file_is_rejected(tmp_path: Path, name: str, content: bytes, message: str) -> None:
    (tmp_path / name).write_bytes(content)
    code, logged = run_main(["--dir", str(tmp_path)], UNREACHABLE)
    assert code == 1
    assert message in logged


def test_dotfiles_and_markdown_are_ignored(tmp_path: Path) -> None:
    (tmp_path / ".DS_Store").write_bytes(b"\x00\x01")
    (tmp_path / "README.md").write_text("# notes\n")
    (tmp_path / "0001_ok.sql").write_text("SELECT 1;\n")
    assert [m.filename for m in migrate.discover(tmp_path)] == ["0001_ok.sql"]


def test_missing_directory_is_an_error(tmp_path: Path) -> None:
    code, logged = run_main(["--dir", str(tmp_path / "nope")], UNREACHABLE)
    assert code == 1
    assert "migrations directory not found" in logged


def test_repo_migrations_are_well_formed() -> None:
    found = migrate.discover(MIGRATIONS_DIR)
    assert [(m.version, m.filename, m.sha256) for m in found] == expected_rows()
    assert found[0].filename == "0001_init.sql"


# ── against a real cluster ──────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def migrated(pg_factory: Callable[..., PgCluster]) -> Iterator[tuple[PgCluster, int, str]]:
    """A fresh cluster migrated from scratch by the CLI, with the run's exit code and log."""
    cluster = pg_factory(migrate=False)
    code, logged = run_main(["--dir", str(MIGRATIONS_DIR)], cluster.settings())
    yield cluster, code, logged
    cluster.close()


@pytest.mark.db
def test_applies_cleanly_from_scratch(migrated: tuple[PgCluster, int, str]) -> None:
    cluster, code, logged = migrated
    assert code == 0, logged
    assert [row[:3] for row in applied_rows(cluster)] == expected_rows()
    for _, filename, sha in expected_rows():
        assert f"applied {filename} sha256={sha} in " in logged
    assert f"database at version {expected_rows()[-1][0]:04d}" in logged

    with cluster.connect("admin", autocommit=True) as conn:
        foreign_owned = conn.execute(
            """
            SELECT n.nspname || '.' || c.relname, pg_get_userbyid(c.relowner)
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname IN ('core', 'app', 'ops', 'api', 'public')
              AND pg_get_userbyid(c.relowner) <> 'bpf_owner'
            UNION ALL
            SELECT nspname, pg_get_userbyid(nspowner) FROM pg_namespace
            WHERE nspname IN ('core', 'app', 'ops', 'api', 'public')
              AND pg_get_userbyid(nspowner) <> 'bpf_owner'
            UNION ALL
            SELECT p.oid::regprocedure::text, pg_get_userbyid(p.proowner)
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname IN ('core', 'app', 'ops', 'api', 'public')
              AND pg_get_userbyid(p.proowner) <> 'bpf_owner'
            """
        ).fetchall()
    assert foreign_owned == [], "every object must be owned by bpf_owner"


@pytest.mark.db
def test_rerun_is_a_noop(migrated: tuple[PgCluster, int, str]) -> None:
    cluster, _, _ = migrated
    before = applied_rows(cluster)
    code, logged = run_main(["--dir", str(MIGRATIONS_DIR)], cluster.settings())
    assert code == 0, logged
    assert "nothing to do" in logged
    assert "applied 0" not in logged
    assert applied_rows(cluster) == before  # including applied_at


@pytest.mark.db
def test_check_when_up_to_date_exits_0(migrated: tuple[PgCluster, int, str]) -> None:
    cluster, _, _ = migrated
    code, logged = run_main(["--check"], cluster.settings())  # default --dir: the repo's db/migrations
    assert code == 0, logged
    assert "up to date" in logged


@pytest.mark.db
def test_check_with_pending_exits_2_and_applies_nothing(
    migrated: tuple[PgCluster, int, str], tmp_path: Path
) -> None:
    cluster, _, _ = migrated
    mdir = copy_migrations(tmp_path / "m")
    (mdir / "9999_probe.sql").write_text("CREATE TABLE ops.zz_check_probe (id integer);\n")
    before = applied_rows(cluster)
    code, logged = run_main(["--dir", str(mdir), "--check"], cluster.settings())
    assert code == 2, logged
    assert "pending 9999_probe.sql sha256=" in logged
    assert regclass(cluster, "ops.zz_check_probe") is None
    assert applied_rows(cluster) == before


@pytest.mark.db
@pytest.mark.parametrize("check", [False, True], ids=["apply", "check"])
def test_edited_applied_migration_is_refused(
    migrated: tuple[PgCluster, int, str], tmp_path: Path, check: bool
) -> None:
    cluster, _, _ = migrated
    mdir = copy_migrations(tmp_path / "m")
    with (mdir / "0001_init.sql").open("a") as fh:
        fh.write("\n-- an innocent-looking edit\n")
    (mdir / "9999_probe.sql").write_text("CREATE TABLE ops.zz_tamper_probe (id integer);\n")
    before = applied_rows(cluster)
    code, logged = run_main(["--dir", str(mdir), *(["--check"] if check else [])], cluster.settings())
    assert code == 1, logged
    assert "0001_init.sql changed after it was applied" in logged
    assert "Never edit an applied migration" in logged
    assert regclass(cluster, "ops.zz_tamper_probe") is None  # nothing else ran either
    assert applied_rows(cluster) == before


@pytest.mark.db
def test_renamed_applied_migration_is_refused(migrated: tuple[PgCluster, int, str], tmp_path: Path) -> None:
    cluster, _, _ = migrated
    mdir = copy_migrations(tmp_path / "m")
    (mdir / "0001_init.sql").rename(mdir / "0001_base.sql")
    code, logged = run_main(["--dir", str(mdir)], cluster.settings())
    assert code == 1, logged
    assert "0001_init.sql was renamed to 0001_base.sql" in logged


@pytest.mark.db
def test_missing_applied_migration_is_refused(migrated: tuple[PgCluster, int, str], tmp_path: Path) -> None:
    cluster, _, _ = migrated
    mdir = copy_migrations(tmp_path / "m")
    (mdir / "0001_init.sql").unlink()
    code, logged = run_main(["--dir", str(mdir)], cluster.settings())
    assert code == 1, logged
    assert "0001_init.sql (version 0001) is missing from disk" in logged


@pytest.mark.db
def test_apply_lifecycle_on_a_scratch_cluster(pg_factory: Callable[..., PgCluster], tmp_path: Path) -> None:
    cluster = pg_factory(migrate=False)
    try:
        settings = cluster.settings()
        mdir = copy_migrations(tmp_path / "m")
        latest = expected_rows()[-1][0]

        # --check on an empty database: everything is pending and nothing is created, not even the table.
        code, logged = run_main(["--dir", str(mdir), "--check"], settings)
        assert code == 2, logged
        assert regclass(cluster, "public.schema_migrations") is None

        code, logged = run_main(["--dir", str(mdir)], settings)
        assert code == 0, logged

        # A new migration is applied as bpf_owner and recorded.
        (mdir / "9001_add_probe.sql").write_text(
            "CREATE TABLE ops.zz_probe (id integer PRIMARY KEY);\nCOMMENT ON TABLE ops.zz_probe IS 'probe';\n"
        )
        code, logged = run_main(["--dir", str(mdir)], settings)
        assert code == 0, logged
        assert "applied 9001_add_probe.sql" in logged
        with cluster.connect("admin", autocommit=True) as conn:
            owner = conn.execute(
                "SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = 'ops.zz_probe'::regclass"
            )
            assert owner.fetchone() == ("bpf_owner",)
        assert [row[0] for row in applied_rows(cluster)][-1] == 9001

        # A migration failing half-way is rolled back completely and not recorded.
        (mdir / "9002_fails.sql").write_text(
            "CREATE TABLE ops.zz_half (id integer);\nINSERT INTO ops.zz_half VALUES (1);\nSELECT 1 / 0;\n"
        )
        code, logged = run_main(["--dir", str(mdir)], settings)
        assert code == 1, logged
        assert "9002_fails.sql failed and was rolled back: [22012]" in logged
        assert regclass(cluster, "ops.zz_half") is None
        assert 9002 not in [row[0] for row in applied_rows(cluster)]

        # A syntax error names the line (and the server quotes the offending token), but the statement text
        # itself is never echoed.
        (mdir / "9002_fails.sql").write_text(
            "CREATE TABLE ops.zz_half (id integer);\n\nSELEC 'secret-ish';\n"
        )
        code, logged = run_main(["--dir", str(mdir)], settings)
        assert code == 1, logged
        assert "[42601]" in logged
        assert "at line 3" in logged
        assert "secret-ish" not in logged
        assert "CREATE TABLE" not in logged
        (mdir / "9002_fails.sql").unlink()

        # A pending migration numbered below the latest applied one is refused.
        (mdir / "9000_late.sql").write_text("SELECT 1;\n")
        code, logged = run_main(["--dir", str(mdir)], settings)
        assert code == 1, logged
        assert "9000_late.sql is numbered below the latest applied version 9001" in logged
        (mdir / "9000_late.sql").unlink()

        # A migration that ends the transaction itself is detected and not recorded.
        (mdir / "9003_commits.sql").write_text("CREATE TABLE ops.zz_commits (id integer);\nCOMMIT;\n")
        code, logged = run_main(["--dir", str(mdir)], settings)
        assert code == 1, logged
        assert "ended the migration transaction itself" in logged
        assert 9003 not in [row[0] for row in applied_rows(cluster)]
        (mdir / "9003_commits.sql").unlink()

        # Concurrent runs are serialised by the advisory lock (lock_timeout shortened for the test).
        with cluster.connect("admin", autocommit=True) as admin:
            admin.execute(f"ALTER ROLE bpf_migrator IN DATABASE {cluster.db_name} SET lock_timeout = '300ms'")
            try:
                with cluster.connect("migrator", autocommit=True) as holder:
                    holder.execute("SELECT pg_advisory_lock(%s)", (migrate.LOCK_KEY,))
                    code, logged = run_main(["--dir", str(mdir)], settings)
                    assert code == 1, logged
                    assert "holds the migration lock" in logged
            finally:
                admin.execute(
                    f"ALTER ROLE bpf_migrator IN DATABASE {cluster.db_name} SET lock_timeout = '10s'"
                )

        code, logged = run_main(["--dir", str(mdir), "--check"], settings)
        assert code == 0, logged
        assert f"up to date at version {max(latest, 9001):04d}" in logged
    finally:
        cluster.close()
