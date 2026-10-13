"""``python -m tests.fullstack``: run the REAL system on localhost until told to stop (docs/E2E.md).

Run from ``server/`` (``uv run python -m tests.fullstack --run-dir DIR``). Progress goes to stderr and to
``<run-dir>/launcher.log``. When everything is up, the stack's state (no secrets) is written to
``<run-dir>/stack.json`` and ONE line is printed on stdout::

    FULLSTACK-READY {"base_url": "http://127.0.0.1:PORT", "data_date": "YYYY-MM-DD", ...}

The launcher then waits, and tears everything down (API, fake GVH, PostgreSQL cluster and its directory) on
SIGTERM, SIGINT or SIGHUP, or when its stdin reaches end-of-file: the Playwright runner keeps a pipe open, so
the stack also goes away when the runner dies. ``--no-stdin-watch`` disables that (in a terminal, use Ctrl-C).
The teardown result is written to ``<run-dir>/teardown.json``.

Exit codes: 0 = clean teardown, 1 = the stack did not start or the teardown was not clean, 2 = usage error,
130 = interrupted while starting.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from types import FrameType

from tests.fullstack.stack import DEFAULT_PER_LEAF, DEFAULT_WEB_BUILD, FullStack, StackError
from tests.pgcluster import PgUnavailable

READY_PREFIX = "FULLSTACK-READY "
STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


class Interrupted(BaseException):  # noqa: N818 - a control-flow signal, like KeyboardInterrupt
    """A stop signal arrived."""


class _Signals:
    """Turns the FIRST stop signal into :class:`Interrupted`; any later one is only recorded, so a teardown
    that has begun always runs to the end."""

    def __init__(self) -> None:
        self.received: list[str] = []
        self.raised = False

    def install(self) -> None:
        for sig in STOP_SIGNALS:
            signal.signal(sig, self._handle)

    def _handle(self, signum: int, _frame: FrameType | None) -> None:
        self.received.append(signal.Signals(signum).name)
        if not self.raised:
            self.raised = True
            raise Interrupted(signal.Signals(signum).name)


def _wait_for_stop(watch_stdin: bool) -> str:
    """Block until stdin reaches end-of-file (when watched); a stop signal interrupts it with
    :class:`Interrupted`. Reads the raw file descriptor in this (main) thread: no reader thread, no buffered
    ``sys.stdin`` lock that could block the interpreter's shutdown."""
    fd: int | None = None
    if watch_stdin:
        try:
            fd = sys.stdin.fileno()
        except AttributeError, ValueError, OSError:
            fd = None  # no stdin at all: wait for a signal
    while True:
        if fd is None:
            time.sleep(0.5)
            continue
        readable, _, _ = select.select([fd], [], [], 0.5)
        if readable and not os.read(fd, 4096):
            return "stdin closed"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.fullstack", description="Run the real system on localhost (docs/E2E.md)."
    )
    parser.add_argument(
        "--run-dir", required=True, type=Path, help="logs, stack.json and teardown.json go here"
    )
    web = parser.add_mutually_exclusive_group()
    web.add_argument(
        "--web-build", type=Path, default=DEFAULT_WEB_BUILD, help="the SPA build to serve (default web/build)"
    )
    web.add_argument("--no-web", action="store_true", help="serve the API only")
    parser.add_argument(
        "--per-leaf",
        type=int,
        default=DEFAULT_PER_LEAF,
        help=f"synthetic products per ontology leaf (default {DEFAULT_PER_LEAF}; each adds ~2 s of ingest)",
    )
    parser.add_argument("--no-stdin-watch", action="store_true", help="do not stop when stdin closes")
    return parser


def _serve(stack: FullStack, run_dir: Path, *, watch_stdin: bool, log: Callable[[str], None]) -> int:
    try:
        stack.start()
    except Interrupted as exc:
        log(f"interrupted by {exc} while starting")
        return 130
    except (StackError, PgUnavailable, OSError, subprocess.SubprocessError) as exc:
        log(f"error: {type(exc).__name__}: {exc}")
        return 1
    state = stack.state()
    (run_dir / "stack.json").write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    print(READY_PREFIX + json.dumps(state, separators=(",", ":")), flush=True)
    try:
        log(f"{_wait_for_stop(watch_stdin)}: stopping")
    except Interrupted as exc:
        log(f"{exc}: stopping")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.per_leaf < 1:
        print("error: --per-leaf must be >= 1", file=sys.stderr)
        return 2
    run_dir: Path = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in ("stack.json", "teardown.json"):
        (run_dir / name).unlink(missing_ok=True)
    with (run_dir / "launcher.log").open("w", encoding="utf-8") as log_file:

        def log(message: str) -> None:
            line = f"[fullstack {time.strftime('%H:%M:%S')}] {message}"
            print(line, file=sys.stderr, flush=True)
            log_file.write(line + "\n")
            log_file.flush()

        signals = _Signals()
        signals.install()
        stack = FullStack(
            run_dir=run_dir,
            web_build=None if args.no_web else args.web_build,
            per_leaf=args.per_leaf,
            log=log,
        )
        code = 1
        try:
            code = _serve(stack, run_dir, watch_stdin=not args.no_stdin_watch, log=log)
        finally:
            # The first signal raises at most once in the whole run (_Signals), so if it lands here, before
            # the teardown started, the second attempt runs it in full.
            for _ in range(2):
                try:
                    signals.raised = True
                    stack.close()
                    break
                except Interrupted:
                    continue
            teardown = {
                "clean": stack.clean,
                "errors": stack.teardown_errors,
                "signals": signals.received,
                "timings": stack.timings,
            }
            (run_dir / "teardown.json").write_text(json.dumps(teardown, indent=1) + "\n", encoding="utf-8")
    if code == 0 and not stack.clean:
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
