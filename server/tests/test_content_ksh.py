"""KSH ara0044: unit normalisation, the converters (research copy and raw STADAT table) and the CSV loader."""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bpf.content.errors import ContentError
from bpf.content.ksh import load_ksh, price_per_unit
from bpf.content.ksh_convert import (
    RawItem,
    convert_items,
    convert_ksh_file,
    decode_ksh_bytes,
    format_decimal,
    is_food_code,
    normalise_unit,
    parse_hu_number,
    parse_period_header,
    read_research,
    read_stadat,
)
from bpf.content.paths import KSH_PATH, KSH_RESEARCH_CSV, KSH_SOURCE_PATH

REPO = Path(__file__).resolve().parents[2]
GAP_KSH = REPO / "research/gap-healthy-plan-priceability/data/ksh_ara0044_latest.csv"
SEPT = date(2026, 9, 1)

# ───────────────────────────── unit normalisation ─────────────────────────────


@pytest.mark.parametrize(
    ("item", "name", "unit", "qty"),
    [
        ("Rövidkaraj, kg", "Rövidkaraj, kg", "kg", "1"),
        # footnote letters glued to the unit are stripped
        (
            "Marhahús, rostélyos, csontos vagy csont nélküli, kga",
            "Marhahús, rostélyos, csontos vagy csont nélküli, kg",
            "kg",
            "1",
        ),
        ("Akácméz, kgn", "Akácméz, kg", "kg", "1"),
        ("Pasztőrözött ESL tej, 2,8%, litere", "Pasztőrözött ESL tej, 2,8%, liter", "l", "1"),
        ("Jégkrém, dobozos, literm", "Jégkrém, dobozos, liter", "l", "1"),
        ("UHT tartós tej dobozban, 2,8% zsírtartalom, liter", None, "l", "1"),
        (
            "Vaj, legalább 80% zsírtartalom, 100–125 g-os csomagolásban, dbi",
            "Vaj, legalább 80% zsírtartalom, 100–125 g-os csomagolásban, db",
            "db",
            "1",
        ),
        (
            "Spagetti, 4 tojásos, gyári készítésű, 400–500 g-os, dbj",
            "Spagetti, 4 tojásos, gyári készítésű, 400–500 g-os, db",
            "db",
            "1",
        ),
        ("Tanuló havibérlet (Budapest nélkül), dbaz", "Tanuló havibérlet (Budapest nélkül), db", "db", "1"),
        ("Teljesárú menetjegy, busz, dbba", "Teljesárú menetjegy, busz, db", "db", "1"),
        # counts: "Tojás, 10 darab" -> db with unit_qty 10
        ("Tojás, 10 darab", "Tojás, 10 darab", "db", "10"),
        ("Zsemle, 1 db", "Zsemle, 1 db", "db", "1"),
        # per kg computed from small packs
        (
            "Fűszerpaprika, csemege, 75–100 g-os tasakból 1 kg-ra számítva",
            "Fűszerpaprika, csemege, 75–100 g-os tasakból 1 kg-ra számítva",
            "kg",
            "1",
        ),
        # no space after the last comma, and commas inside parentheses
        (
            "Tisztított dió, csomagolt is (nem darált, nem cukrozott),kg",
            "Tisztított dió, csomagolt is (nem darált, nem cukrozott),kg",
            "kg",
            "1",
        ),
        ("Só, étkezési, finomított, 1 kg (kivéve tengeri só), kg", None, "kg", "1"),
    ],
)
def test_normalise_unit(item: str, name: str | None, unit: str, qty: str) -> None:
    result = normalise_unit(item)
    assert result is not None
    assert result == (name if name is not None else item, unit, Decimal(qty))


@pytest.mark.parametrize(
    "item",
    [
        "Sertészsír, 400–500 g (kivéve mangalica)",  # no unit at all
        "Háztartási keksz, csomagolt 800–1000 g, csomag",
        "Csemegekukorica-konzerv, dobozp",  # doboz + footnote p
        "Bors, fekete, őrölt, 16–25 g, csomagr",
        "Dobozos narancslé, 100%-os gyümölcstartalom, 1 l, doboz",
        "Férfi félcipő, bőr, ragasztott műtalp, pár",
        "Napi menü, 2 fogásos, adag",
        "Csempe, falburkoló, fehér és egyszínű színes, m²",
        "Ásványvíz, 1,5 literes",  # "literes" is a word, not liter + footnote "es"
        "Valami, 2 kg-ra számítva",  # only "1 kg-ra számítva" has been seen
        "kg",  # no comma: no item name
        "Tojás, 0 darab",
    ],
)
def test_units_that_cannot_be_normalised(item: str) -> None:
    assert normalise_unit(item) is None


@pytest.mark.parametrize(
    ("code", "food"),
    [
        ("10001", True),
        ("15999", True),
        ("15204", True),
        ("16041", False),
        ("17305", False),
        ("09999", False),
        ("1000", False),
        ("1000a", False),
        ("31071", False),
    ],
)
def test_food_code_range(code: str, food: bool) -> None:
    assert is_food_code(code) is food


def _item(code: str, text: str, price: str = "100", period: date = SEPT) -> RawItem:
    return RawItem(code, text, Decimal(price), period)


def test_convert_items_filters_food_and_units() -> None:
    items = [
        _item("14111", "Gomba, kg", "1900"),
        _item("11001", "Tojás, 10 darab", "814"),
        _item("10502", "Téliszalámi, kgb", "10060"),
        _item("13801", "Háztartási keksz, csomagolt 800–1000 g, csomag", "1370"),
        _item("16041", "Napi menü, 2 fogásos, adag", "2490"),
        _item("17309", "Coca Cola vagy Pepsi 1–2,5 l-es palackban, litert", "430"),
    ]
    conv = convert_items(items, encoding="utf-8", min_food_rows=1)
    assert [(r.code, r.name, r.unit, r.unit_qty, r.price) for r in conv.rows] == [
        ("10502", "Téliszalámi, kg", "kg", Decimal(1), Decimal(10060)),
        ("11001", "Tojás, 10 darab", "db", Decimal(10), Decimal(814)),
        ("14111", "Gomba, kg", "kg", Decimal(1), Decimal(1900)),
    ]  # sorted by code
    assert [d.code for d in conv.dropped_food] == ["13801"]
    assert conv.non_food == 2


def test_convert_items_errors() -> None:
    with pytest.raises(ContentError, match="appears twice"):
        convert_items(
            [_item("14111", "Gomba, kg"), _item("14111", "Gomba, kg")], encoding="x", min_food_rows=1
        )
    with pytest.raises(ContentError, match="cannot be stored exactly"):
        convert_items([_item("11001", "Tojás, 3 darab", "100")], encoding="x", min_food_rows=1)
    with pytest.raises(ContentError, match="only 1 convertible food rows"):
        convert_items([_item("14111", "Gomba, kg")], encoding="x")  # default minimum is 50


# ───────────────────────────── raw-file decoding and parsing ─────────────────────────────


def test_decode_ksh_bytes_windows_1250_dash_in_an_iso_8859_2_file() -> None:
    raw = "Gyümölcsjoghurt, 125–150 g-os, db; Fűszerpaprika".encode("cp1250")
    assert b"\x96" in raw  # the en dash byte the research copy shows as U+0096
    text, encoding = decode_ksh_bytes(raw)
    assert text == "Gyümölcsjoghurt, 125–150 g-os, db; Fűszerpaprika"
    assert encoding == "iso-8859-2 (with windows-1250 punctuation)"


def test_decode_ksh_bytes_plain_iso_8859_2_and_utf8() -> None:
    assert decode_ksh_bytes("Fűszerpaprika, kg".encode("iso-8859-2")) == ("Fűszerpaprika, kg", "iso-8859-2")
    assert decode_ksh_bytes("Fűszerpaprika – kg".encode()) == ("Fűszerpaprika – kg", "utf-8")
    assert decode_ksh_bytes(b"\xef\xbb\xbfKod") == ("Kod", "utf-8")
    with pytest.raises(ContentError, match="0x81"):
        decode_ksh_bytes(b"ab\xf5\x81")  # 0x81 is undefined in Windows-1250


@pytest.mark.parametrize(
    ("cell", "value"),
    [
        ("2 070", "2070"),
        ("1 234,5", "1234.5"),
        ("814", "814"),
        ("0,5", "0.5"),
        ("10 060", "10060"),
        ("..", None),
        ("–", None),
        ("-", None),
        ("", None),
        (" x ", None),
    ],
)
def test_parse_hu_number(cell: str, value: str | None) -> None:
    assert parse_hu_number(cell) == (Decimal(value) if value is not None else None)


@pytest.mark.parametrize("cell", ["abc", "1.234", "12,", "-5", "1e3"])
def test_parse_hu_number_rejects_garbage(cell: str) -> None:
    with pytest.raises(ValueError, match="not a number"):
        parse_hu_number(cell)


@pytest.mark.parametrize(
    ("cell", "period"),
    [
        ("2026. szeptember", date(2026, 9, 1)),
        ("2026. szept.", date(2026, 9, 1)),
        ("2026.09.", date(2026, 9, 1)),
        ("2026-09", date(2026, 9, 1)),
        ("2026. Június", date(2026, 6, 1)),
        ("2025. március", date(2025, 3, 1)),
        ("Megnevezés", None),
        ("2026. ju", None),
        ("2026.13.", None),
        ("2026. foo", None),
    ],
)
def test_parse_period_header(cell: str, period: date | None) -> None:
    assert parse_period_header(cell) == period


SYNTHETIC_STADAT = (
    "20.1.1.44. Egyes termékek átlagára (SYNTHETIC test table)\r\n"
    "Kód;Megnevezés;2026. augusztus;2026. szeptember\r\n"
    "11001;Tojás, 10 darab;800;814\r\n"
    "14001;Korai burgonya, kg;439;..\r\n"
    "11306;Gyümölcsjoghurt, 125–150 g-os, db;145;148\r\n"
    "14310;Dobozos narancslé, 100%-os gyümölcstartalom, 1 l, doboz;1 000;1 050\r\n"
    "10103;Marhahús, rostélyos, csontos vagy csont nélküli, kga;5 800;5 900\r\n"
    "16041;Napi menü, 2 fogásos, adag;2 400;2 490\r\n"
    ";;;\r\n"
    "a) Lábjegyzet szövege.\r\n"
)


def test_read_stadat_takes_the_latest_value_per_item() -> None:
    items, encoding = read_stadat(SYNTHETIC_STADAT.encode("cp1250"))
    assert encoding == "iso-8859-2 (with windows-1250 punctuation)"
    by_code = {i.code: i for i in items}
    assert (by_code["11001"].price, by_code["11001"].period) == (Decimal(814), SEPT)
    assert (by_code["14001"].price, by_code["14001"].period) == (Decimal(439), date(2026, 8, 1))
    assert by_code["11306"].item == "Gyümölcsjoghurt, 125–150 g-os, db"
    conv = convert_items(items, encoding=encoding, min_food_rows=1)
    assert [r.code for r in conv.rows] == ["10103", "11001", "11306", "14001"]
    assert conv.rows[0].name == "Marhahús, rostélyos, csontos vagy csont nélküli, kg"
    assert [d.code for d in conv.dropped_food] == ["14310"]
    assert conv.non_food == 1


def test_read_stadat_other_delimiters() -> None:
    tab = SYNTHETIC_STADAT.replace(";", "\t")
    items, _ = read_stadat(tab.encode("utf-8"))
    assert len(items) == 6


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Megnevezés;2026. szeptember\r\nTojás;814\r\n", "no header row found"),
        (
            "Kód;Megnevezés;2026. szeptember;Megjegyzés\r\n11001;Tojás, 10 darab;814;\r\n",
            "not recognised as months",
        ),
        ("Kód;Megnevezés;2026. szeptember\r\n11001;Tojás, 10 darab;8l4\r\n", "not a number"),
        ("Kód;Megnevezés;2026. szeptember\r\n11001;Tojás, 10 darab;..\r\n", "no value in any month"),
        ("Kód;Megnevezés;2026. szeptember\r\nsemmi\r\n", "no item rows"),
    ],
)
def test_read_stadat_fails_loudly_on_unexpected_layouts(text: str, expected: str) -> None:
    with pytest.raises(ContentError) as info:
        read_stadat(text.encode("cp1250"))
    assert expected in str(info.value)


def test_read_research_rejects_a_wrong_header_and_bad_rows() -> None:
    with pytest.raises(ContentError, match="header must be"):
        read_research(b"code,item,price,month\n")
    with pytest.raises(ContentError, match="bad price"):
        read_research(b'ksh_code,item,avg_price_huf,month\n14111,"Gomba, kg",1900,2026-13\n')


# ───────────────────────────── the committed seed ─────────────────────────────


def test_committed_seed_is_reproducible_from_the_research_copy(tmp_path: Path) -> None:
    out_csv, out_md = tmp_path / "ara0044.csv", tmp_path / "SOURCE.md"
    result = convert_ksh_file(
        KSH_RESEARCH_CSV,
        raw_format="research",
        fetched=date(2026, 10, 12),
        csv_path=out_csv,
        source_path=out_md,
    )
    assert out_csv.read_bytes() == KSH_PATH.read_bytes()
    assert out_md.read_bytes() == KSH_SOURCE_PATH.read_bytes()
    assert result.sha256 == hashlib.sha256(KSH_RESEARCH_CSV.read_bytes()).hexdigest()


def test_source_md_states_origin_licence_and_checksum() -> None:
    text = KSH_SOURCE_PATH.read_text(encoding="utf-8")
    sha = hashlib.sha256(KSH_RESEARCH_CSV.read_bytes()).hexdigest()
    assert sha in text
    assert "CC BY 4.0" in text
    assert '"Forrás: KSH"' in text
    assert "research/alt-price-sources/data/ksh_ara0044_latest_avg_prices.csv" in text
    assert "not re-fetched" in text
    assert "blocked" in text
    assert "https://www.ksh.hu/stadat_files/ara/hu/ara0044.html" in text


def test_seed_names_match_the_independently_decoded_research_table() -> None:
    """The second research copy was decoded from the raw table (footnotes removed, 0x96 left as U+0096):
    every name of the seed must equal it, which checks the footnote stripping row by row."""
    with GAP_KSH.open(encoding="utf-8", newline="") as fh:
        gap = {row["kod"]: row for row in csv.DictReader(fh)}
    seed = load_ksh(KSH_PATH)
    assert len(seed) == 61
    for code, row in seed.items():
        expected = gap[code]["megnevezes"].replace("\x96", "–")
        assert row.name == expected, code
        gap_price = gap[code]["ar_ft"].replace(" ", "")
        if gap_price != "..":  # that copy only has the 2026-09 column
            assert row.price == Decimal(gap_price), code
            assert row.period == SEPT, code


def test_seed_contents() -> None:
    seed = load_ksh(KSH_PATH)
    eggs = seed["11001"]
    assert (eggs.unit, eggs.unit_qty, eggs.price) == ("db", Decimal(10), Decimal(814))
    assert price_per_unit(eggs) == Decimal("81.4")
    assert seed["15202"].unit == "kg"  # ground paprika, per kg
    assert seed["14001"].period == date(2026, 7, 1)  # its latest value is from July
    for code in ("14111", "14601", "14701", "13910", "15204"):  # mushrooms, dry beans, walnuts, honey, salt
        assert seed[code].unit == "kg"
    assert all(10000 <= int(code) <= 15999 for code in seed)
    for dropped in ("12101", "13801", "14310", "14425", "15101", "15201", "16041", "17309"):
        assert dropped not in seed


def test_format_decimal() -> None:
    assert format_decimal(Decimal("10")) == "10"
    assert format_decimal(Decimal("10.00")) == "10"
    assert format_decimal(Decimal("81.40")) == "81.4"
    assert format_decimal(Decimal("1E+3")) == "1000"


def test_convert_ksh_file_from_a_raw_table(tmp_path: Path) -> None:
    raw = tmp_path / "ara0044.csv.raw"
    raw.write_bytes(SYNTHETIC_STADAT.encode("cp1250"))
    out_csv, out_md = tmp_path / "out.csv", tmp_path / "SOURCE.md"
    result = convert_ksh_file(
        raw, fetched=date(2026, 10, 20), csv_path=out_csv, source_path=out_md, min_food_rows=1
    )
    assert len(result.conversion.rows) == 4
    rows = load_ksh(out_csv)
    assert rows["11001"].price == Decimal(814)
    text = out_md.read_text(encoding="utf-8")
    assert hashlib.sha256(raw.read_bytes()).hexdigest() in text
    assert "the original file downloaded from" in text
    assert "2026-10-20" in text
    assert "| 14310 |" in text  # dropped food row listed


def test_convert_ksh_file_writes_nothing_when_the_input_is_bad(tmp_path: Path) -> None:
    raw = tmp_path / "bad.csv"
    raw.write_bytes(b"nothing here\n")
    out_csv = tmp_path / "out.csv"
    with pytest.raises(ContentError):
        convert_ksh_file(raw, csv_path=out_csv, source_path=tmp_path / "SOURCE.md")
    assert not out_csv.exists()


# ───────────────────────────── loader validation ─────────────────────────────

HEADER = "code,name,unit,unit_qty,price,period\n"


def _load(tmp_path: Path, body: str, header: str = HEADER) -> dict[str, object]:
    path = tmp_path / "ksh.csv"
    path.write_text(header + body, encoding="utf-8")
    return dict(load_ksh(path))


def test_load_ksh_accepts_a_good_file(tmp_path: Path) -> None:
    rows = _load(
        tmp_path, '11001,"Tojás, 10 darab",db,10,814,2026-09-01\n14111,"Gomba, kg",kg,1,1900,2026-09-01\n'
    )
    assert list(rows) == ["11001", "14111"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('11001,"Tojás",g,10,814,2026-09-01\n', "unit 'g'"),
        ('11001,"Tojás",db,0,814,2026-09-01\n', "unit_qty"),
        ('11001,"Tojás",db,10,0,2026-09-01\n', "price '0'"),
        ('11001,"Tojás",db,10,-5,2026-09-01\n', "price '-5'"),
        ('11001,"Tojás",db,10,8 14,2026-09-01\n', "price '8 14'"),
        ('11001,"Tojás",db,10,814,2026-09-02\n', "YYYY-MM-01"),
        ('11001,"Tojás",db,10,814,2026-13-01\n', "YYYY-MM-01"),
        ('11001,"Tojás",db,3,100,2026-09-01\n', "cannot be stored exactly"),
        ('11001,"",db,10,814,2026-09-01\n', "name must be"),
        ('11001," Tojás",db,10,814,2026-09-01\n', "name must be"),
        ('110 01,"Tojás",db,10,814,2026-09-01\n', "code '110 01'"),
        ('11001,"Tojás",db,10,814\n', "expected 6 fields"),
        ('14111,"Gomba",kg,1,1900,2026-09-01\n11001,"Tojás",db,10,814,2026-09-01\n', "sorted by code"),
        ('11001,"Tojás",db,10,814,2026-09-01\n11001,"Tojás",db,10,814,2026-09-01\n', "duplicate code"),
        ("", "no data rows"),
    ],
)
def test_load_ksh_rejects_bad_rows(tmp_path: Path, body: str, expected: str) -> None:
    with pytest.raises(ContentError) as info:
        _load(tmp_path, body)
    assert expected in str(info.value)


def test_load_ksh_rejects_bad_files(tmp_path: Path) -> None:
    with pytest.raises(ContentError, match="header must be"):
        _load(tmp_path, '11001,"Tojás",db,10,814,2026-09-01\n', header="kod,nev,egyseg,menny,ar,honap\n")
    path = tmp_path / "bom.csv"
    path.write_bytes(b"\xef\xbb\xbf" + HEADER.encode())
    with pytest.raises(ContentError, match="byte-order mark"):
        load_ksh(path)
    with pytest.raises(ContentError, match="cannot read"):
        load_ksh(tmp_path / "missing.csv")
