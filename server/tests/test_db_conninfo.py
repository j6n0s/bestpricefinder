"""bpf.db and the deploy scripts pin SCRAM: a server that asks for a cleartext or md5 password, or waves the
client through without authentication, is an impostor (deploy/local/db-init.sh's pg_hba.conf allows
scram-sha-256 only) and must never be sent a password.

No real PostgreSQL is needed: a fake server answers the startup packet with the authentication request under
test and records what the client sends next. The DB-backed suites (test_db_roles.py, test_ingest_db.py,
test_content_db.py, test_migrate.py) show that real SCRAM logins through bpf.db still work."""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from bpf import db
from bpf.config import Settings
from tests.pgcluster import SCRIPTS_DIR, PgUnavailable, find_pg_bin

PASSWORD = "c0ffee" * 10 + "beef"  # 64 hex characters, like db-init.sh's
SSL_REQUEST = 80877103
GSSENC_REQUEST = 80877104

AUTH_REQUESTS = {
    "cleartext": b"R" + struct.pack("!II", 8, 3),  # AuthenticationCleartextPassword
    "md5": b"R" + struct.pack("!II", 12, 5) + b"salt",  # AuthenticationMD5Password
    "trust": b"R" + struct.pack("!II", 8, 0),  # AuthenticationOk without any exchange
}


def _recv_exact(conn: socket.socket, n: int) -> bytes | None:
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


class FakePostgres:
    """Accepts connections, answers SSL/GSS requests with 'N', then sends ``auth`` after the startup packet.
    :attr:`replies` holds, per connection, what the client sent after that (b"" = it hung up)."""

    def __init__(self, family: socket.AddressFamily, address: str | tuple[str, int], auth: bytes) -> None:
        self.auth = auth
        self.replies: list[bytes] = []
        self._sock = socket.socket(family, socket.SOCK_STREAM)
        self._sock.bind(address)
        self._sock.listen(4)
        self._sock.settimeout(0.2)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return int(self._sock.getsockname()[1])

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)
        self._sock.close()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except TimeoutError:
                continue
            with conn:
                conn.settimeout(5)
                with contextlib.suppress(OSError):
                    self._handle(conn)

    def _handle(self, conn: socket.socket) -> None:
        while True:
            header = _recv_exact(conn, 8)
            if header is None:
                return
            length, code = struct.unpack("!II", header)
            if code in (SSL_REQUEST, GSSENC_REQUEST):
                conn.sendall(b"N")
                continue
            if _recv_exact(conn, length - 8) is None:  # the rest of the StartupMessage
                return
            break
        conn.sendall(self.auth)
        try:
            self.replies.append(conn.recv(4096))  # a PasswordMessage ('p') here is the leak
        except TimeoutError:
            self.replies.append(b"")


@pytest.fixture
def socket_dir() -> Iterator[Path]:
    # Short and private, like the /tmp/bpf-sock-<uid>-<port> fallback of deploy/local/_common.sh.
    path = Path(tempfile.mkdtemp(prefix="bpfsk-", dir="/tmp" if os.path.isdir("/tmp") else None))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _fake_server(transport: str, method: str, socket_dir: Path) -> tuple[FakePostgres, str, int]:
    if transport == "tcp":
        server = FakePostgres(socket.AF_INET, ("127.0.0.1", 0), AUTH_REQUESTS[method])
        return server, "127.0.0.1", server.port
    port = 5544
    server = FakePostgres(socket.AF_UNIX, str(socket_dir / f".s.PGSQL.{port}"), AUTH_REQUESTS[method])
    return server, str(socket_dir), port


def test_conninfo_requires_scram() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, api_password=PASSWORD, ingest_password=PASSWORD, migrator_password=PASSWORD
    )
    for role in db.ROLES:
        assert conninfo_to_dict(db.conninfo(role, settings))["require_auth"] == "scram-sha-256"


@pytest.mark.parametrize("method", sorted(AUTH_REQUESTS))
@pytest.mark.parametrize("transport", ["tcp", "unix"])
def test_connect_refuses_a_server_that_does_not_ask_for_scram(
    transport: str, method: str, socket_dir: Path
) -> None:
    server, host, port = _fake_server(transport, method, socket_dir)
    try:
        settings = Settings(_env_file=None, db_host=host, db_port=port, api_password=PASSWORD)  # type: ignore[call-arg]
        with pytest.raises(psycopg.OperationalError) as excinfo:
            db.connect("api", settings=settings).close()
    finally:
        server.close()
    assert server.replies, "the fake server never got as far as asking for authentication"
    assert all(not reply.startswith(b"p") for reply in server.replies), "a password was sent"
    assert all(PASSWORD.encode() not in reply for reply in server.replies)
    assert 'authentication method requirement "scram-sha-256" failed' in str(excinfo.value)
    assert PASSWORD not in str(excinfo.value)


def test_scripts_pin_scram_for_libpq_tools() -> None:
    # Also when the caller's environment asks for something weaker.
    proc = subprocess.run(
        ["bash", "-c", '. "$1"; printf "%s" "$PGREQUIREAUTH"', "pin", str(SCRIPTS_DIR / "_common.sh")],
        env={**os.environ, "PGREQUIREAUTH": "password"},
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert proc.stdout == "scram-sha-256"


@pytest.mark.parametrize("method", ["cleartext", "md5"])
def test_scripts_psql_never_sends_the_admin_password_to_an_impostor(method: str, socket_dir: Path) -> None:
    """psql as db-init.sh/db-backup.sh run it (bpf_admin, PGPASSWORD for one command) against an impostor
    socket: it must give up without a PasswordMessage."""
    try:
        find_pg_bin()
    except PgUnavailable as exc:
        pytest.skip(str(exc))
    server, host, port = _fake_server("unix", method, socket_dir)
    try:
        proc = subprocess.run(
            [
                "bash",
                "-c",
                'set -euo pipefail; . "$1"; bpf_find_pg_bin; '
                'PGPASSWORD=$2 "$PSQL" -X -q -w -h "$3" -p "$4" -U bpf_admin -d bpf -c "SELECT 1"',
                "impostor",
                str(SCRIPTS_DIR / "_common.sh"),
                PASSWORD,
                host,
                str(port),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    finally:
        server.close()
    assert proc.returncode != 0
    assert server.replies
    assert all(not reply.startswith(b"p") for reply in server.replies), "psql sent a password"
    assert 'authentication method requirement "scram-sha-256" failed' in proc.stderr
