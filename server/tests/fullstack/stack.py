"""The REAL system on localhost, for end-to-end tests (docs/E2E.md).

:meth:`FullStack.start` brings up, all on 127.0.0.1 and on random free ports:

1. **PostgreSQL**: a throwaway cluster made by the real ``deploy/local/db-init.sh`` and ``db-start.sh``
   (:class:`tests.pgcluster.PgCluster`, which runs them as the ``bpfpg`` OS user when we are root),
   migrated with ``bpf.migrate``.
2. **The fake GVH Árfigyelő** (:mod:`tests.fakegvh`), served over real HTTP by its threaded server. Its
   stores are the REAL store list (``research/gvh-location/data/stores.csv``); its categories are the real
   leaves the ingredient ontology uses; every product and price is SYNTHETIC. It is test data only: never
   present it as real, never ship it.
3. **The real ingest CLI** as subprocesses: ``python -m bpf.ingest reference``, then (after the content)
   ``daily`` and ``availability``, with ``BPF_GVH_BASE_URL`` / ``BPF_GVH_XLSX_URL`` pointing at the fake
   and ``BPF_CONTACT_EMAIL=test@example.invalid``. The politeness throttle stays at its floor of one
   request per second (``gvh_min_interval_s`` cannot go lower), so the fake catalogue is kept small
   instead: the ontology's leaves only, ``per_leaf`` products each (with the default of 1: about 210
   requests, 3.5 minutes). Every run must end ``ok``.
4. **The real content loader**: ``python -m bpf.content`` (``data/ingredients.json``,
   ``data/recipes/*.json``, ``data/ksh/``), after the reference ingest (so the leaves are checked against
   ``core.category``) and before the daily ingest (which reads the ontology's leaves for its per-store and
   availability work).
5. **The real API**: ``python -m bpf.api`` on a free port, with the cluster's env file and, optionally,
   ``web/build`` (built beforehand by ``npm run build``).

Nothing inside our own system is mocked. :meth:`FullStack.close` stops the API, the fake GVH and the
cluster (``db-stop.sh``) and deletes the cluster directory; :meth:`FullStack.start` does that itself when
a step fails.

Secrets: the database passwords exist only in the cluster's env file written by ``db-init.sh`` (mode 600,
deleted with the cluster). Child processes get its *path* (``BPF_ENV_FILE``); no password is ever put on a
command line, in the state JSON or in a log.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import FrameType
from typing import Any

import httpx

from bpf.ingest.common import budapest_today
from tests.fakegvh import DEFAULT_SEED, FakeGvh, FakeServer, FakeWorld, build_world
from tests.pgcluster import PgCluster, free_port

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVER_DIR = REPO_ROOT / "server"
INGREDIENTS_JSON = REPO_ROOT / "data" / "ingredients.json"
DEFAULT_WEB_BUILD = REPO_ROOT / "web" / "build"
LOCALHOST = "127.0.0.1"
#: The User-Agent contact of the ingest under test (RFC 2606 ``.invalid``: never a real mailbox).
CONTACT_EMAIL = "test@example.invalid"
#: Synthetic products per ontology leaf. Each one costs about 2 requests at 1 request per second.
DEFAULT_PER_LEAF = 1
#: The API's per-IP rate limit for the run. The production default (120/min, burst 30) is sized for one phone;
#: the browser tests are several users' worth of requests from 127.0.0.1, in parallel.
API_RATE_LIMIT_PER_MINUTE = 6000
INGEST_STATUS = {0: "ok", 1: "failed", 2: "usage error", 3: "partial"}
INGEST_TIMEOUT_S = 1800.0
CONTENT_TIMEOUT_S = 300.0
API_READY_TIMEOUT_S = 60.0
API_STOP_TIMEOUT_S = 15.0
API_START_ATTEMPTS = 3
STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)

Logger = Callable[[str], None]


class StackError(RuntimeError):
    """A step of the stack failed. The message names the step and its log file."""


@dataclass(frozen=True, slots=True)
class StepResult:
    """One subprocess step (an ingest run or the content load)."""

    name: str
    argv: tuple[str, ...]  # never contains a secret
    exit_code: int
    status: str  # ok | partial | failed | usage error
    summary: str  # the command's last stdout line
    seconds: float
    requests: int  # requests the fake GVH received during the step
    min_request_gap_s: float | None  # smallest gap between two of those requests, as the fake received them
    request_span_s: float | None  # first to last request: >= (requests - 1) s at 1 request per second
    log: str

    def as_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "status": self.status,
            "summary": self.summary,
            "seconds": round(self.seconds, 2),
            "requests": self.requests,
            "min_request_gap_s": None if self.min_request_gap_s is None else round(self.min_request_gap_s, 3),
            "request_span_s": None if self.request_span_s is None else round(self.request_span_s, 3),
            "log": self.log,
        }


def ontology_leaves(path: Path = INGREDIENTS_JSON) -> frozenset[int]:
    """The GVH leaf ids that ``data/ingredients.json`` references (the fake serves exactly these leaves)."""
    document = json.loads(path.read_text(encoding="utf-8"))
    leaves = frozenset(int(leaf) for row in document["ingredients"] for leaf in row.get("leaf_ids") or ())
    if not leaves:
        raise StackError(f"{path}: no ingredient references a GVH leaf")
    return leaves


@contextlib.contextmanager
def _stop_signals_deferred() -> Iterator[None]:
    """Hold SIGTERM, SIGINT and SIGHUP back while the stack is torn down, so a stop signal can never cut a
    teardown short and leave a cluster behind. A held signal is raised again afterwards, under the handler
    that was in place before (so Ctrl-C still stops pytest, and SIGTERM still ends the process, once all is
    down).

    Python runs signal handlers in the main thread whichever thread receives the signal, so swapping the
    handlers (rather than masking signals) covers every thread. Off the main thread nothing can be swapped.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    held: list[int] = []

    def hold(signum: int, _frame: FrameType | None) -> None:
        held.append(signum)

    previous: dict[int, Any] = {}
    try:
        # A signal that arrives in this loop leaves before the body, so nothing has been torn down yet.
        for sig in STOP_SIGNALS:
            previous[sig] = signal.signal(sig, hold)
        yield
    finally:
        for sig, handler in previous.items():
            if handler is not None:  # None: a handler not set from Python, which cannot be restored
                signal.signal(sig, handler)
        for signum in dict.fromkeys(held):
            signal.raise_signal(signum)


def _stderr_logger(prefix: str = "fullstack") -> Logger:
    def log(message: str) -> None:
        print(f"[{prefix} {time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)

    return log


class FullStack:
    """The whole system on localhost. Call :meth:`start`, use :attr:`base_url`, then :meth:`close` (or use
    ``with FullStack(...) as stack:``, which starts and closes it)."""

    def __init__(
        self,
        *,
        run_dir: str | os.PathLike[str],
        web_build: str | os.PathLike[str] | None = DEFAULT_WEB_BUILD,
        per_leaf: int = DEFAULT_PER_LEAF,
        seed: int = DEFAULT_SEED,
        data_date: date | None = None,
        api_rate_limit_per_minute: int = API_RATE_LIMIT_PER_MINUTE,
        python: str = sys.executable,
        log: Logger | None = None,
    ) -> None:
        if per_leaf < 1:
            raise ValueError("per_leaf must be >= 1")
        self.run_dir = Path(run_dir).resolve()
        self.log_dir = self.run_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        for stale in (*self.log_dir.glob("[0-9][0-9]-*.log"), *self.log_dir.glob("api-*.log")):
            stale.unlink()  # an earlier run's logs in a reused run directory
        self.web_build = Path(web_build).resolve() if web_build is not None else None
        self.per_leaf = per_leaf
        self.seed = seed
        self.data_date = data_date or budapest_today()
        self.api_rate_limit_per_minute = api_rate_limit_per_minute
        self.python = python
        self.log = log or _stderr_logger()
        self.cluster: PgCluster | None = None
        self.world: FakeWorld | None = None
        self.fake: FakeGvh | None = None
        self.gvh: FakeServer | None = None
        self.api_port: int | None = None
        self.steps: list[StepResult] = []
        self.runs: list[dict[str, Any]] = []  # ops.ingest_run rows (no secrets: kind, status, codes)
        self.timings: dict[str, float] = {}
        self.teardown_errors: list[str] = []
        self._exit = contextlib.ExitStack()
        self._api: subprocess.Popen[bytes] | None = None
        self._cluster_root: Path | None = None
        self._started = False
        self._closed = False
        self._step_no = 0

    # ── lifecycle ──────────────────────────────────────────────────────────────────────────────────

    def __enter__(self) -> FullStack:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def base_url(self) -> str:
        if self.api_port is None:
            raise StackError("the API is not running")
        return f"http://{LOCALHOST}:{self.api_port}"

    def start(self) -> FullStack:
        """Bring everything up. On any failure (or interruption) everything started so far is torn down."""
        if self._started:
            raise StackError("already started")
        self._started = True
        began = time.monotonic()
        try:
            self._start()
        except BaseException:
            self.log("start failed: tearing down")
            self.close()
            raise
        self.timings["total_start"] = round(time.monotonic() - began, 2)
        self.log(
            f"ready in {self.timings['total_start']:.0f} s: {self.base_url} (data date {self.data_date})"
        )
        return self

    def close(self) -> None:
        """Stop the API, the fake GVH and the cluster, and delete the cluster directory. Idempotent; errors
        are collected in :attr:`teardown_errors` (and :attr:`clean` is then False)."""
        if self._closed:
            return
        # Stop signals are held from here on. One that arrives before the hold is in place leaves this method
        # with nothing done and _closed still False, so the caller can simply call close() again.
        with _stop_signals_deferred():
            self._closed = True
            began = time.monotonic()
            try:
                self._exit.close()  # LIFO: API, fake GVH, cluster; every callback runs even if one fails
            except BaseException as exc:  # noqa: BLE001 - report, never leave the rest running
                self.teardown_errors.append(f"{type(exc).__name__}: {exc}")
            self.timings["teardown"] = round(time.monotonic() - began, 2)
            if self.clean:
                self.log(f"torn down in {self.timings['teardown']:.1f} s")
            else:
                self.log(f"teardown NOT clean: {self.teardown_errors or 'cluster directory still exists'}")

    @property
    def clean(self) -> bool:
        """True after :meth:`close` when nothing is left: no API process, no cluster directory, no errors."""
        api_gone = self._api is None or self._api.poll() is not None
        cluster_gone = self._cluster_root is None or not self._cluster_root.exists()
        return self._closed and api_gone and cluster_gone and not self.teardown_errors

    # ── the steps ──────────────────────────────────────────────────────────────────────────────────

    def _start(self) -> None:
        if self.web_build is not None and not (self.web_build / "index.html").is_file():
            raise StackError(f"{self.web_build}/index.html is missing: run `npm run build` in web/ first")
        self.log(f"data date {self.data_date}; run directory {self.run_dir}")

        with self._timed("postgres"):
            self.cluster = PgCluster.create()  # db-init.sh + db-start.sh + bpf.migrate; cleans up on failure
        self._cluster_root = self.cluster.root
        self._exit.callback(self._close_cluster)
        self.log(f"PostgreSQL {self.cluster.pg_major} on port {self.cluster.port} (throwaway, migrated)")

        with self._timed("fake_gvh"):
            leaves = ontology_leaves()
            self.world = build_world(seed=self.seed, per_leaf=self.per_leaf, overrides=(), leaf_subset=leaves)
            self.fake = FakeGvh(self.world, data_date=self.data_date, clock=time.monotonic)
            self.gvh = self._exit.enter_context(self.fake.serve())
        self.log(
            f"fake GVH (SYNTHETIC products, real store list) at {self.gvh.base}: "
            f"{len(self.world.stores)} stores, {len(self.world.leaves)} leaves, "
            f"{len(self.world.products)} products"
        )

        self._ingest("reference")
        self._content()
        self._ingest("daily")
        self._ingest("availability")
        self._check_runs()
        self._start_api()

    def _ingest(self, kind: str) -> StepResult:
        assert self.gvh is not None
        argv = (self.python, "-m", "bpf.ingest", kind, "--date", self.data_date.isoformat())
        env = self._env(
            BPF_GVH_BASE_URL=self.gvh.api_base,
            BPF_GVH_XLSX_URL=self.gvh.xlsx_url,
            BPF_CONTACT_EMAIL=CONTACT_EMAIL,
        )
        result = self._run(f"ingest-{kind}", argv, env, timeout=INGEST_TIMEOUT_S)
        if result.status != "ok":
            raise StackError(
                f"python -m bpf.ingest {kind} ended {result.status} (exit {result.exit_code}): "
                f"{result.summary or '(no summary)'}; see {result.log}"
            )
        return result

    def _content(self) -> StepResult:
        argv = (self.python, "-m", "bpf.content")
        result = self._run("content", argv, self._env(), timeout=CONTENT_TIMEOUT_S, ingest=False)
        if result.exit_code != 0:
            raise StackError(f"python -m bpf.content failed (exit {result.exit_code}); see {result.log}")
        return result

    def _check_runs(self) -> None:
        """Every recorded run (reference, content, daily, availability) must have ended ``ok``."""
        assert self.cluster is not None
        with self.cluster.connect("admin") as conn:
            rows = conn.execute(
                "SELECT id, kind, status, data_date, requests, warnings, error "
                "FROM ops.ingest_run ORDER BY id"
            ).fetchall()
        self.runs = [
            {
                "id": run_id,
                "kind": kind,
                "status": status,
                "data_date": data_date.isoformat() if data_date else None,
                "requests": requests,
                "warnings": sorted({str(w.get("code")) for w in warnings if isinstance(w, Mapping)}),
                "error": error,
            }
            for run_id, kind, status, data_date, requests, warnings, error in rows
        ]
        kinds = [run["kind"] for run in self.runs]
        if kinds != ["reference", "content", "daily", "availability"]:
            raise StackError(f"unexpected ops.ingest_run history: {kinds}")
        bad = [run for run in self.runs if run["status"] != "ok"]
        if bad:
            raise StackError(f"runs not ok: {bad}")
        self.log("ops.ingest_run: " + ", ".join(f"{r['kind']} {r['status']}" for r in self.runs))

    def _start_api(self) -> None:
        with self._timed("api"):
            self._launch_api()

    def _launch_api(self) -> None:
        build = self.web_build if self.web_build is not None else self.run_dir / "no-web-build"  # API only
        for attempt in range(1, API_START_ATTEMPTS + 1):
            port = free_port()
            argv = (self.python, "-m", "bpf.api", "--host", LOCALHOST, "--port", str(port))
            env = self._env(
                BPF_WEB_BUILD_DIR=str(build),
                BPF_API_RATE_LIMIT_PER_MINUTE=str(self.api_rate_limit_per_minute),
            )
            log_path = self.log_dir / f"api-{attempt}.log"
            with log_path.open("wb") as log_file:
                log_file.write(f"$ {' '.join(argv)}\n".encode())
                log_file.flush()
                self._api = subprocess.Popen(  # noqa: S603 - our own module, fixed argv
                    list(argv),
                    cwd=SERVER_DIR,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
            api = self._api
            self._exit.callback(self._stop_api, api)
            if self._wait_for_api(api, port, log_path):
                self.api_port = port
                self.log(f"API (python -m bpf.api) on {self.base_url}, web build: {self.web_build or 'none'}")
                return
            if attempt < API_START_ATTEMPTS and "address already in use" in log_path.read_text(
                errors="replace"
            ):
                self.log(f"port {port} was taken meanwhile; trying another")
                continue
            raise StackError(f"the API did not become ready; see {log_path}")
        raise StackError("the API did not start")  # pragma: no cover - the loop returns or raises

    def _wait_for_api(self, api: subprocess.Popen[bytes], port: int, log_path: Path) -> bool:
        """True once /api/health answers 200 ``ok`` for our data date; False if the process exited."""
        deadline = time.monotonic() + API_READY_TIMEOUT_S
        url = f"http://{LOCALHOST}:{port}/api/health"
        with httpx.Client(trust_env=False, timeout=2.0) as client:
            while time.monotonic() < deadline:
                if api.poll() is not None:
                    return False
                try:
                    response = client.get(url)
                except httpx.TransportError:
                    time.sleep(0.2)
                    continue
                try:
                    body = response.json() if response.status_code == 200 else None
                except ValueError:
                    body = None
                if (
                    body
                    and body.get("status") == "ok"
                    and body.get("data_date") == self.data_date.isoformat()
                ):
                    return True
                if response.status_code == 200:
                    raise StackError(
                        f"/api/health is not ok for {self.data_date}: {body or response.text[:200]!r}; "
                        f"see {log_path}"
                    )
                time.sleep(0.2)
        raise StackError(f"/api/health did not answer within {API_READY_TIMEOUT_S:.0f} s; see {log_path}")

    # ── teardown callbacks ─────────────────────────────────────────────────────────────────────────

    def _stop_api(self, api: subprocess.Popen[bytes]) -> None:
        if api.poll() is None:
            api.send_signal(signal.SIGTERM)
            try:
                api.wait(timeout=API_STOP_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                api.kill()
                api.wait(timeout=API_STOP_TIMEOUT_S)
                self.teardown_errors.append("the API did not stop on SIGTERM and was killed")

    def _close_cluster(self) -> None:
        if self.cluster is not None:
            self.cluster.close()  # db-stop.sh (pg_ctl -m immediate as a fallback), then rm -rf
        if self._cluster_root is not None and self._cluster_root.exists():
            self.teardown_errors.append(f"cluster directory {self._cluster_root} still exists")

    # ── helpers ────────────────────────────────────────────────────────────────────────────────────

    @contextlib.contextmanager
    def _timed(self, name: str) -> Iterator[None]:
        began = time.monotonic()
        try:
            yield
        finally:
            self.timings[name] = round(self.timings.get(name, 0.0) + time.monotonic() - began, 2)

    def _env(self, **extra: str) -> dict[str, str]:
        """A child's environment: ours without BPF_* / PG* variables, plus the cluster's env file (its path,
        not its contents), no proxy for localhost, and ``extra``."""
        assert self.cluster is not None
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BPF_", "PG"))}
        hosts = [
            h.strip() for h in (env.get("NO_PROXY") or env.get("no_proxy") or "").split(",") if h.strip()
        ]
        hosts += [h for h in (LOCALHOST, "localhost") if h not in hosts]
        env["NO_PROXY"] = env["no_proxy"] = ",".join(hosts)
        env["BPF_ENV_FILE"] = str(self.cluster.env_file)
        env["PYTHONUNBUFFERED"] = "1"
        env.update(extra)
        return env

    def _run(
        self,
        name: str,
        argv: tuple[str, ...],
        env: Mapping[str, str],
        *,
        timeout: float,
        ingest: bool = True,
    ) -> StepResult:
        """Run one step to completion; stdout and stderr go to ``logs/NN-<name>.log``."""
        assert self.fake is not None
        self._step_no += 1
        log_path = self.log_dir / f"{self._step_no:02d}-{name}.log"
        first_request = len(self.fake.requests)
        self.log(f"{name}: {' '.join(argv[1:])}")
        began = time.monotonic()
        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(f"$ {' '.join(argv)}\n")
            log_file.flush()
            proc = subprocess.run(  # noqa: S603 - our own modules, fixed argv
                list(argv),
                cwd=SERVER_DIR,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=log_file,
                text=True,
                timeout=timeout,
                check=False,
            )
            log_file.write("--- stdout\n" + proc.stdout)
        seconds = time.monotonic() - began
        self.timings[name] = round(seconds, 2)
        received = self.fake.requests[first_request:]
        stamps = [r.at for r in received if r.at is not None]
        gaps = [later - earlier for earlier, later in zip(stamps, stamps[1:], strict=False)]
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        if ingest:
            status = INGEST_STATUS.get(proc.returncode, "failed")
        else:
            status = "ok" if proc.returncode == 0 else "failed"
        result = StepResult(
            name=name,
            argv=argv,
            exit_code=proc.returncode,
            status=status,
            summary=lines[-1] if lines else "",
            seconds=seconds,
            requests=len(received),
            min_request_gap_s=min(gaps) if gaps else None,
            request_span_s=stamps[-1] - stamps[0] if len(stamps) > 1 else None,
            log=str(log_path),
        )
        self.steps.append(result)
        self.log(
            f"{name}: exit {proc.returncode}, {seconds:.1f} s, {len(received)} requests: {result.summary}"
        )
        return result

    def state(self) -> dict[str, Any]:
        """What the browser tests need, as JSON. No secrets (no passwords, no env file contents)."""
        assert self.world is not None
        assert self.gvh is not None
        assert self.cluster is not None
        return {
            "base_url": self.base_url,
            "api_port": self.api_port,
            "data_date": self.data_date.isoformat(),
            "launcher_pid": os.getpid(),
            "run_dir": str(self.run_dir),
            "web_build": str(self.web_build) if self.web_build else None,
            "postgres": {"major": self.cluster.pg_major, "port": self.cluster.port},
            "fake_gvh": {
                "synthetic": True,
                "base": self.gvh.base,
                "seed": self.seed,
                "per_leaf": self.per_leaf,
                "leaves": len(self.world.leaves),
                "products": len(self.world.products),
                "stores": len(self.world.stores),
                "requests": len(self.fake.requests) if self.fake else 0,
            },
            "steps": [step.as_json() for step in self.steps],
            "runs": self.runs,
            "timings": dict(self.timings),
        }
