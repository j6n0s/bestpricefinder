"""Convert KSH STADAT ara0044 to ``data/ksh/ara0044.csv`` and record the input in ``data/ksh/SOURCE.md``.

Run as ``python -m bpf.content --convert-ksh RAW [--ksh-format stadat|research] [--ksh-fetched YYYY-MM-DD]``.

Inputs
------
``stadat`` (default): the original table file downloaded from ksh.hu, a delimited text table (``;``, tab or
``,``) with a header row ``Kód | Megnevezés | <one column per month, e.g. "2026. szeptember">`` and one row
per item (code = 5 digits). Numbers use a decimal comma and space/no-break-space thousand separators; ``..``,
``–``, ``-``, ``x`` or an empty cell mean "no value". The file is declared ISO-8859-2; KSH files also use the
Windows-1250 punctuation in 0x80–0x9F (0x96 = "–", seen in the research copy), which is decoded as such. A
UTF-8 file is accepted too (and recorded as such). The exact layout of the raw file has not been seen yet
(ksh.hu is unreachable from the build environment), so every structural surprise stops the conversion
with an error that says what was expected.

``research``: ``research/alt-price-sources/data/ksh_ara0044_latest_avg_prices.csv`` (UTF-8, columns
``ksh_code,item,avg_price_huf,month``), the research copy that seeds the repository until a raw file can be
fetched.

Rules
-----
* Food rows only: codes 10000–15999 (food products). 16xxx (catering), 17xxx (drinks, coffee), 18xxx
  (alcohol), 19xxx (tobacco) and all non-food groups are dropped.
* The unit is the last comma-separated part of the item text: ``kg``; ``liter``/``l`` -> ``l``; ``db``,
  ``darab`` -> ``db``; an optional leading count gives ``unit_qty`` ("Tojás, 10 darab" -> db, 10;
  "Zsemle, 1 db" -> db, 1); "... 1 kg-ra számítva" -> kg. A footnote marker glued to the unit is stripped
  ("kga" -> kg, "litere" -> liter, "dbaz" -> db): KSH numbers its footnotes a, b, …, z, aa, ab, …, so a
  marker is one letter or two letters starting with a or b. Anything else (``csomag``, ``doboz``, ``pár``,
  ``adag``, ``m²``, a bare "400–500 g") cannot be normalised and the row is dropped.
* The name is the item text exactly as published, minus the footnote marker.
* The value is the latest month with a value (the period is that month's first day).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from bpf.content.errors import ContentError
from bpf.content.jsonio import display_path
from bpf.content.ksh import KSH_HEADER, MAX_NAME_LENGTH, stored_price_problem
from bpf.content.paths import KSH_PATH, KSH_SOURCE_PATH
from bpf.pricing.model import fold_name

KshFormat = Literal["stadat", "research"]

KSH_TABLE_URL = "https://www.ksh.hu/stadat_files/ara/hu/ara0044.html"
KSH_TABLE_TITLE = "Egyes termékek és szolgáltatások fogyasztói átlagára (nyers adatok), havonta"
KSH_LICENCE_URL = "https://www.ksh.hu/copyright"
FOOD_CODES = range(10000, 16000)
MIN_FOOD_ROWS = 50
"""A real ara0044 table has about 80 convertible food rows; fewer than this means the format changed."""

RESEARCH_HEADER = ("ksh_code", "item", "avg_price_huf", "month")

_FOOTNOTE = r"(?P<fn>[a-z]|[ab][a-z])?"
_UNIT_TOKEN = re.compile(r"(?:(?P<qty>[0-9]+(?:,[0-9]+)?) )?(?P<unit>kg|liter|l|db|darab)" + _FOOTNOTE)
_PER_KG = re.compile(r"(?:^|\s)(?P<qty>[0-9]+(?:,[0-9]+)?) (?P<unit>kg)-ra számítva" + _FOOTNOTE + r"$")
_UNIT_MAP = {"kg": "kg", "liter": "l", "l": "l", "db": "db", "darab": "db"}

_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "januar",
            "februar",
            "marcius",
            "aprilis",
            "majus",
            "junius",
            "julius",
            "augusztus",
            "szeptember",
            "oktober",
            "november",
            "december",
        ),
        start=1,
    )
}
_PERIOD_NAMED = re.compile(r"([0-9]{4})\.? ?([a-z]+)\.?")
_PERIOD_NUMERIC = re.compile(r"([0-9]{4})[.-] ?([0-9]{1,2})\.?")
_MISSING = frozenset({"", "..", "...", "…", "-", "–", "—", "x"})
_SPACES = dict.fromkeys(map(ord, "     "), None)
_NUMBER = re.compile(r"[0-9]+(?:,[0-9]+)?")


@dataclass(frozen=True, slots=True)
class RawItem:
    """One item of the input table: its latest value and that value's month."""

    code: str
    item: str
    price: Decimal
    period: date


@dataclass(frozen=True, slots=True)
class KshRow:
    """One output row of ``data/ksh/ara0044.csv``."""

    code: str
    name: str
    unit: str
    unit_qty: Decimal
    price: Decimal
    period: date


@dataclass(frozen=True, slots=True)
class Dropped:
    code: str
    item: str
    reason: str


@dataclass(frozen=True, slots=True)
class Conversion:
    rows: tuple[KshRow, ...]
    dropped_food: tuple[Dropped, ...]  # food rows that could not be converted (listed in SOURCE.md)
    non_food: int  # rows outside the food code range
    encoding: str
    warnings: tuple[str, ...] = field(default=())


# ───────────────────────────── normalisation ─────────────────────────────


def normalise_unit(item: str) -> tuple[str, str, Decimal] | None:
    """``(name, unit, unit_qty)`` for an item text, or None when its unit cannot be normalised.

    ``name`` is ``item`` without a footnote marker on the unit; ``unit`` is kg, l or db."""
    text = item.rstrip()
    head, sep, tail = text.rpartition(",")
    if not sep or not head.strip():
        return None
    token = tail.strip()
    match = _UNIT_TOKEN.fullmatch(token) or _PER_KG.search(token)
    if match is None:
        return None
    qty_text = match.group("qty")
    unit_qty = Decimal(qty_text.replace(",", ".")) if qty_text else Decimal(1)
    if unit_qty <= 0:
        return None
    if match.re is _PER_KG and unit_qty != 1:
        return None  # "N kg-ra számítva" with N != 1 has not been seen; refuse rather than guess
    footnote = match.group("fn") or ""
    name = text[: len(text) - len(footnote)] if footnote else text
    return name, _UNIT_MAP[match.group("unit")], unit_qty


def is_food_code(code: str) -> bool:
    return code.isdigit() and len(code) == 5 and int(code) in FOOD_CODES


def convert_items(
    items: Sequence[RawItem], *, encoding: str, min_food_rows: int = MIN_FOOD_ROWS
) -> Conversion:
    """Apply the food filter and the unit normalisation. Raises :class:`ContentError` on bad input."""
    problems: list[str] = []
    seen: set[str] = set()
    rows: list[KshRow] = []
    dropped: list[Dropped] = []
    non_food = 0
    for item in items:
        if item.code in seen:
            problems.append(f"code {item.code} appears twice")
            continue
        seen.add(item.code)
        if not is_food_code(item.code):
            non_food += 1
            continue
        normalised = normalise_unit(item.item)
        if normalised is None:
            dropped.append(Dropped(item.code, item.item, "unit cannot be normalised to kg, l or db"))
            continue
        name, unit, unit_qty = normalised
        if len(name) > MAX_NAME_LENGTH:
            problems.append(f"code {item.code}: name longer than {MAX_NAME_LENGTH} characters")
            continue
        storage = stored_price_problem(item.price, unit_qty)
        if storage is not None:
            problems.append(f"code {item.code}: {storage}")
            continue
        rows.append(KshRow(item.code, name, unit, unit_qty, item.price, item.period))
    if not problems and len(rows) < min_food_rows:
        problems.append(
            f"only {len(rows)} convertible food rows (expected at least {min_food_rows}): "
            "the table layout or "
            "the unit notation has probably changed; check the raw file"
        )
    if problems:
        raise ContentError(problems)
    rows.sort(key=lambda r: r.code)
    return Conversion(tuple(rows), tuple(dropped), non_food, encoding)


# ───────────────────────────── readers ─────────────────────────────


def decode_ksh_bytes(data: bytes) -> tuple[str, str]:
    """Decode a KSH file: UTF-8 when it is valid UTF-8, else ISO-8859-2 with Windows-1250 in 0x80–0x9F."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    text = data.decode("iso-8859-2")
    out: list[str] = []
    replaced = False
    for index, ch in enumerate(text):
        if 0x80 <= ord(ch) <= 0x9F:
            try:
                out.append(bytes([ord(ch)]).decode("cp1250"))
            except UnicodeDecodeError:
                raise ContentError(
                    [
                        f"byte 0x{ord(ch):02X} at offset {index} is a control code "
                        "in ISO-8859-2 and Windows-1250"
                    ]
                ) from None
            replaced = True
        else:
            out.append(ch)
    return "".join(out), ("iso-8859-2 (with windows-1250 punctuation)" if replaced else "iso-8859-2")


def parse_hu_number(cell: str) -> Decimal | None:
    """``Decimal`` for "2 070", "1 234,5" or "814"; None for a missing-value marker. Raises ValueError."""
    text = cell.strip()
    if text.casefold() in _MISSING:
        return None
    compact = text.translate(_SPACES)
    if not _NUMBER.fullmatch(compact):
        raise ValueError(f"not a number: {cell!r}")
    try:
        return Decimal(compact.replace(",", "."))
    except InvalidOperation as exc:  # pragma: no cover - the regex admits only valid decimals
        raise ValueError(f"not a number: {cell!r}") from exc


def parse_period_header(cell: str) -> date | None:
    """The month of a header cell such as "2026. szeptember", "2026. szept.", "2026.09." or "2026-09"."""
    folded = fold_name(cell)
    match = _PERIOD_NUMERIC.fullmatch(folded)
    if match:
        month = int(match.group(2))
        return date(int(match.group(1)), month, 1) if 1 <= month <= 12 else None
    match = _PERIOD_NAMED.fullmatch(folded)
    if match:
        word = match.group(2)
        candidates = [n for name, n in _MONTHS.items() if name.startswith(word) and len(word) >= 3]
        if len(candidates) == 1:
            return date(int(match.group(1)), candidates[0], 1)
    return None


def _sniff_rows(text: str) -> list[list[str]]:
    """Rows of the table, split on the delimiter that yields the recognisable header row."""
    for delimiter in (";", "\t", ","):
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
        if any(_header_index(row) is not None for row in rows[:50]):
            return rows
    raise ContentError(
        [
            "no header row found: expected a row whose first cells are 'Kód' and 'Megnevezés' followed by "
            "month columns such as '2026. szeptember' (delimiter ';', tab or ',')"
        ]
    )


def _header_index(row: list[str]) -> list[tuple[int, date]] | None:
    if len(row) < 3:
        return None
    if not fold_name(row[0]).startswith("kod") or not fold_name(row[1]).startswith("megnevez"):
        return None
    periods = [(i, p) for i, cell in enumerate(row[2:], start=2) if (p := parse_period_header(cell))]
    return periods or None


def read_stadat(data: bytes) -> tuple[list[RawItem], str]:
    """Parse the original ara0044 table (see the module docstring). Returns the items and the encoding."""
    text, encoding = decode_ksh_bytes(data)
    rows = _sniff_rows(text)
    header_at = next(i for i, row in enumerate(rows) if _header_index(row) is not None)
    columns = _header_index(rows[header_at]) or []
    unrecognised = [
        cell for cell in rows[header_at][2:] if cell.strip() and parse_period_header(cell) is None
    ]
    if unrecognised:
        raise ContentError([f"header cells not recognised as months: {unrecognised[:5]}"])
    problems: list[str] = []
    items: list[RawItem] = []
    for line, row in enumerate(rows[header_at + 1 :], start=header_at + 2):
        code = row[0].strip() if row else ""
        if not (code.isdigit() and len(code) == 5):
            continue  # notes, footnotes, blank lines
        if len(row) < 3:
            problems.append(f"row {line} (code {code}): too few cells")
            continue
        latest: tuple[date, Decimal] | None = None
        for index, period in columns:
            if index >= len(row):
                continue
            try:
                value = parse_hu_number(row[index])
            except ValueError as exc:
                problems.append(f"row {line} (code {code}): {exc}")
                continue
            if value is not None and value > 0 and (latest is None or period > latest[0]):
                latest = (period, value)
        if latest is None:
            problems.append(f"row {line} (code {code}): no value in any month")
            continue
        items.append(RawItem(code, row[1].strip(), latest[1], latest[0]))
    if problems:
        raise ContentError(problems)
    if not items:
        raise ContentError(["no item rows (5-digit codes) after the header row"])
    return items, encoding


def read_research(data: bytes) -> tuple[list[RawItem], str]:
    """Parse the research copy (UTF-8, ``ksh_code,item,avg_price_huf,month``)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContentError([f"research KSH file is not UTF-8 (byte {exc.start})"]) from exc
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows or tuple(rows[0]) != RESEARCH_HEADER:
        raise ContentError([f"research KSH file: header must be {','.join(RESEARCH_HEADER)}"])
    problems: list[str] = []
    items: list[RawItem] = []
    for line, row in enumerate(rows[1:], start=2):
        if len(row) != len(RESEARCH_HEADER):
            problems.append(f"line {line}: expected {len(RESEARCH_HEADER)} fields")
            continue
        code, item, price_text, month = (cell.strip() for cell in row)
        match = re.fullmatch(r"([0-9]{4})-([0-9]{2})", month)
        try:
            price = parse_hu_number(price_text)
        except ValueError as exc:
            problems.append(f"line {line}: {exc}")
            continue
        if price is None or price <= 0 or match is None or not 1 <= int(match.group(2)) <= 12:
            problems.append(f"line {line}: bad price {price_text!r} or month {month!r}")
            continue
        items.append(RawItem(code, item, price, date(int(match.group(1)), int(match.group(2)), 1)))
    if problems:
        raise ContentError(problems)
    return items, "utf-8"


# ───────────────────────────── writers ─────────────────────────────


def format_decimal(value: Decimal) -> str:
    """Plain decimal text without exponent or trailing zeros ("10", "81.4")."""
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def render_csv(rows: Sequence[KshRow]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(KSH_HEADER)
    for r in rows:
        writer.writerow(
            [
                r.code,
                r.name,
                r.unit,
                format_decimal(r.unit_qty),
                format_decimal(r.price),
                r.period.isoformat(),
            ]
        )
    return buffer.getvalue()


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_source_md(
    conversion: Conversion,
    *,
    raw_display: str,
    raw_sha256: str,
    raw_format: KshFormat,
    fetched: date,
    url: str,
    command: str,
) -> str:
    """The text of ``data/ksh/SOURCE.md`` (deterministic: no clock, so it can be regenerated in a test)."""
    periods = sorted({r.period for r in conversion.rows})
    lines = [
        "# Source of `ara0044.csv` (KSH national average prices)",
        "",
        f'- **Table:** KSH STADAT ara0044, "{KSH_TABLE_TITLE}", <{KSH_TABLE_URL}>.',
        f"- **Licence:** CC BY 4.0 (<{KSH_LICENCE_URL}>). Attribution, required wherever a value is shown: "
        f'"Forrás: KSH" with a link to <{KSH_TABLE_URL}>.',
        '- **Use in the app:** "becsült országos átlagár (KSH)", a monthly national average. Never show it '
        "as a store price.",
    ]
    if raw_format == "research":
        lines += [
            f"- **Converted from:** `{raw_display}`, the copy of the table made by the research stream "
            "`alt-price-sources` on 2026-10-12 (latest month 2026-09; the table was last updated by KSH on "
            "2026-10-07). **It was not re-fetched from ksh.hu**, because ksh.hu is blocked from the build "
            "environment. Replace this seed by converting the original file once it is available: "
            "`python -m bpf.content --convert-ksh <raw file>`.",
        ]
    else:
        lines += [f"- **Converted from:** `{raw_display}`, the original file downloaded from <{url}>."]
    lines += [
        f"- **Input sha256:** `{raw_sha256}`",
        f"- **Input format:** {raw_format} ({conversion.encoding})",
        f"- **Fetched:** {fetched.isoformat()}",
        f"- **Command:** `{command}`",
        f"- **Rows:** {len(conversion.rows)} food rows kept; "
        f"{len(conversion.dropped_food)} food rows dropped "
        f"(listed below); {conversion.non_food} non-food rows dropped.",
        f"- **Periods:** {', '.join(p.isoformat() for p in periods)} (each row carries the month of its "
        "latest published value).",
        "",
        "## Conversion rules",
        "",
        "- Food rows only: codes 10000–15999. Catering (16xxx), drinks and coffee (17xxx), alcohol (18xxx), "
        "tobacco (19xxx) and every non-food group are dropped.",
        "- The unit is the last comma-separated part of the item text: `kg`; `liter` → `l`; `db`/`darab` → "
        '`db`, with an optional leading count as `unit_qty` ("Tojás, 10 darab" → `db`, 10); '
        '"1 kg-ra számítva" → `kg`. A footnote marker glued to the unit is stripped ("kga" → `kg`, '
        '"dbj" → `db`). Rows whose unit is a package (`csomag`, `doboz`, `palack`…) or missing are dropped.',
        "- `price` is HUF for `unit_qty` × `unit`. The database table `app.ksh_price` has no `unit_qty` "
        "column, so the loader stores `price / unit_qty` per one unit (eggs: 814 Ft / 10 db → 81.40 Ft/db).",
        "",
        "## Dropped food rows",
        "",
        "| code | item | reason |",
        "|---|---|---|",
    ]
    lines += [f"| {d.code} | {_md_cell(d.item)} | {d.reason} |" for d in conversion.dropped_food]
    if not conversion.dropped_food:
        lines.append("| – | – | none |")
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class ConvertResult:
    conversion: Conversion
    csv_path: Path
    source_path: Path
    sha256: str


def convert_ksh_file(
    raw_path: Path,
    *,
    raw_format: KshFormat = "stadat",
    fetched: date | None = None,
    url: str = KSH_TABLE_URL,
    csv_path: Path = KSH_PATH,
    source_path: Path = KSH_SOURCE_PATH,
    min_food_rows: int = MIN_FOOD_ROWS,
) -> ConvertResult:
    """Convert ``raw_path`` and write the CSV and SOURCE.md. Nothing is written when the input is invalid.

    ``fetched`` defaults to the input file's modification date (UTC)."""
    try:
        data = raw_path.read_bytes()
        mtime = raw_path.stat().st_mtime
    except OSError as exc:
        raise ContentError([f"{display_path(raw_path)}: cannot read: {exc.strerror or exc}"]) from exc
    items, encoding = read_research(data) if raw_format == "research" else read_stadat(data)
    conversion = convert_items(items, encoding=encoding, min_food_rows=min_food_rows)
    sha = hashlib.sha256(data).hexdigest()
    when = fetched if fetched is not None else datetime.fromtimestamp(mtime, tz=UTC).date()
    raw_display = display_path(raw_path)
    command = (
        f"python -m bpf.content --convert-ksh {raw_display} --ksh-format {raw_format} --ksh-fetched {when}"
    )
    source = render_source_md(
        conversion,
        raw_display=raw_display,
        raw_sha256=sha,
        raw_format=raw_format,
        fetched=when,
        url=url,
        command=command,
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(render_csv(conversion.rows), encoding="utf-8", newline="")
    source_path.write_text(source, encoding="utf-8", newline="")
    return ConvertResult(conversion, csv_path, source_path, sha)
