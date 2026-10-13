"""Strict JSON reading for content files.

* UTF-8 only (a byte-order mark is rejected);
* duplicate object keys are an error (``json`` would silently keep the last one);
* ``NaN``/``Infinity`` are an error;
* JSON numbers with a fraction or exponent become ``Decimal`` (never ``float``), integers stay ``int``.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from bpf.config import REPO_ROOT
from bpf.content.errors import ContentError


def display_path(path: Path) -> str:
    """``path`` relative to the repository root when it is inside it (for messages), else as given."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


class _DuplicateKeyError(ValueError):
    pass


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not allowed")


def loads_strict(text: str) -> Any:
    """Parse ``text`` with the strict rules above (raises ``ValueError``)."""
    return json.loads(
        text, parse_float=Decimal, parse_constant=_reject_constant, object_pairs_hook=_no_duplicates
    )


def read_json(path: Path) -> Any:
    """Read and parse one content file; any problem raises :class:`ContentError` naming the file."""
    where = display_path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContentError([f"{where}: cannot read: {exc.strerror or exc}"]) from exc
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ContentError([f"{where}: starts with a UTF-8 byte-order mark; save it without one"])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContentError([f"{where}: not valid UTF-8 (byte {exc.start})"]) from exc
    try:
        return loads_strict(text)
    except json.JSONDecodeError as exc:
        raise ContentError(
            [f"{where}: invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}"]
        ) from exc
    except ValueError as exc:
        raise ContentError([f"{where}: invalid JSON: {exc}"]) from exc
