"""``data/ksh/ara0044.csv``: KSH national average prices (CC BY 4.0, "Forrás: KSH"), read and validated.

Format (docs/DATA.md): UTF-8 CSV, header ``code,name,unit,unit_qty,price,period``, one row per code, sorted by
code. ``price`` is HUF for ``unit_qty`` × ``unit`` (eggs: unit ``db``, unit_qty 10); ``period`` is the first
day of the month (``YYYY-MM-01``). The converter that writes this file is :mod:`bpf.content.ksh_convert`.

Database note: ``app.ksh_price`` (migration 0001) has no ``unit_qty`` column, so the loader stores the
price **per one unit** (``price / unit_qty``; eggs 814 Ft / 10 db -> 81.40 Ft per db). That value must be
exact in ``numeric(12,2)``; a row where it is not is rejected here, before anything is written.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

from bpf.content.errors import ContentError, Problems
from bpf.content.jsonio import display_path
from bpf.content.vocab import KSH_CODE_RE, UNITS
from bpf.pricing.model import KshPrice, Unit

KSH_HEADER: tuple[str, ...] = ("code", "name", "unit", "unit_qty", "price", "period")
MAX_NAME_LENGTH = 200  # app.ksh_price.name
PRICE_SCALE = Decimal("0.01")  # app.ksh_price.price is numeric(12,2)
PRICE_LIMIT = Decimal(10) ** 10  # numeric(12,2): at most 10 integer digits

_PLAIN_DECIMAL = re.compile(r"[0-9]{1,12}(?:\.[0-9]{1,6})?")
_PERIOD = re.compile(r"([0-9]{4})-([0-9]{2})-01")


def parse_plain_decimal(text: str) -> Decimal | None:
    """``Decimal`` for an unsigned plain decimal such as ``814`` or ``81.4`` (no sign, exponent or comma)."""
    if not _PLAIN_DECIMAL.fullmatch(text):
        return None
    return Decimal(text)


def parse_period(text: str) -> date | None:
    """The date for ``YYYY-MM-01``, or None when ``text`` is not exactly that."""
    match = _PERIOD.fullmatch(text)
    if match is None:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12 or year < 1900:
        return None
    return date(year, month, 1)


def price_per_unit(row: KshPrice) -> Decimal:
    """HUF per one ``row.unit``: the value stored in ``app.ksh_price.price`` (see the module docstring)."""
    return row.price / row.unit_qty


def stored_price_problem(price: Decimal, unit_qty: Decimal) -> str | None:
    """Why ``price / unit_qty`` cannot be stored exactly in ``numeric(12,2)``, or None when it can."""
    per_unit = price / unit_qty
    if per_unit != per_unit.quantize(PRICE_SCALE) or per_unit >= PRICE_LIMIT:
        return (
            f"price {price} / unit_qty {unit_qty} = {per_unit} cannot be stored exactly as a per-unit price "
            "in app.ksh_price.price numeric(12,2) (the table has no unit_qty column)"
        )
    return None


@dataclass(frozen=True, slots=True)
class _Row:
    line: int
    cells: list[str]


def _read_rows(path: Path) -> list[_Row]:
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
        return [
            _Row(line, cells)
            for line, cells in enumerate(csv.reader(io.StringIO(text, newline=""), strict=True), start=1)
        ]
    except csv.Error as exc:
        raise ContentError([f"{where}: malformed CSV: {exc}"]) from exc


def _validate_row(row: _Row, where: str, problems: Problems) -> KshPrice | None:
    at = f"{where} line {row.line}"
    if len(row.cells) != len(KSH_HEADER):
        problems.add(at, f"expected {len(KSH_HEADER)} fields, found {len(row.cells)}")
        return None
    code, name, unit, unit_qty_text, price_text, period_text = row.cells
    ok = True
    if not KSH_CODE_RE.fullmatch(code):
        problems.add(at, f"code {code!r} must match {KSH_CODE_RE.pattern}")
        ok = False
    if not name.strip() or name != name.strip() or len(name) > MAX_NAME_LENGTH:
        problems.add(at, f"name must be 1-{MAX_NAME_LENGTH} characters without surrounding spaces")
        ok = False
    if unit not in UNITS:
        problems.add(at, f"unit {unit!r} must be one of {', '.join(UNITS)}")
        ok = False
    unit_qty = parse_plain_decimal(unit_qty_text)
    if unit_qty is None or unit_qty <= 0:
        problems.add(at, f"unit_qty {unit_qty_text!r} must be a positive plain decimal")
        ok = False
    price = parse_plain_decimal(price_text)
    if price is None or price <= 0:
        problems.add(at, f"price {price_text!r} must be a positive plain decimal (HUF)")
        ok = False
    period = parse_period(period_text)
    if period is None:
        problems.add(at, f"period {period_text!r} must be YYYY-MM-01")
        ok = False
    if not ok or unit_qty is None or price is None or period is None:
        return None
    storage = stored_price_problem(price, unit_qty)
    if storage is not None:
        problems.add(at, storage)
        return None
    return KshPrice(
        code=code, name=name, unit=cast(Unit, unit), unit_qty=unit_qty, price=price, period=period
    )


def load_ksh(path: Path) -> dict[str, KshPrice]:
    """Read and validate the KSH CSV. Returns code -> row in file order; raises :class:`ContentError`."""
    where = display_path(path)
    rows = _read_rows(path)
    problems = Problems()
    if not rows or tuple(rows[0].cells) != KSH_HEADER:
        found = ",".join(rows[0].cells) if rows else "an empty file"
        raise ContentError([f"{where}: header must be {','.join(KSH_HEADER)} (found {found})"])
    result: dict[str, KshPrice] = {}
    previous: str | None = None
    for row in rows[1:]:
        parsed = _validate_row(row, where, problems)
        if parsed is None:
            continue
        if parsed.code in result:
            problems.add(f"{where} line {row.line}", f"duplicate code {parsed.code}")
            continue
        if previous is not None and parsed.code <= previous:
            problems.add(
                f"{where} line {row.line}", f"rows must be sorted by code ({parsed.code} after {previous})"
            )
        previous = parsed.code
        result[parsed.code] = parsed
    if len(rows) == 1:
        problems.add(where, "no data rows")
    problems.raise_if_any()
    return result
