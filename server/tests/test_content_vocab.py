"""bpf.content vocabularies, health-claim words, regex lint and strict JSON reading."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from bpf.content.errors import ContentError, Problems
from bpf.content.jsonio import read_json
from bpf.content.vocab import (
    HEALTH_CLAIM_STEMS,
    INGREDIENT_TAGS,
    LIST_GROUPS,
    RECIPE_TAGS,
    health_claim_stems,
    pattern_problems,
)


def test_vocabularies_match_the_contract() -> None:
    assert LIST_GROUPS == (
        "zoldseg_gyumolcs",
        "pekaru",
        "tejtermek_tojas",
        "hus_hal",
        "szaraz_tartos",
        "fagyasztott",
        "fuszer_olaj",
        "egyeb",
    )
    # mirrored by the CHECK constraint of db/migrations/0002_ingredient_attrs.sql
    migration = (Path(__file__).resolve().parents[2] / "db/migrations/0002_ingredient_attrs.sql").read_text()
    for tag in INGREDIENT_TAGS:
        assert f"'{tag}'" in migration
    assert len(INGREDIENT_TAGS) == 17
    assert {"husmentes", "olcso", "gyors", "hal", "huvelyes", "baromfi", "sertes", "marha"} <= RECIPE_TAGS


@pytest.mark.parametrize(
    "text",
    [
        "Egészséges vacsora",  # DATA.md: "egészséges"
        "EGÉSZSÉGES",
        "egeszseges, ekezet nelkul",
        "Az egészségre jó",  # every form of egészség
        "jól fogyasztható",  # "fogyaszt"
        "Fogyasztásra kész",
        "Diétás változat",  # "diéta"
        "méregtelenítő leves",  # "méregtelenít"
        "Erősíti az immunrendszert",  # "immun"
        "gyógyhatású",  # "gyógy"
        "GYÓGYNÖVÉNYES",
        "betegség esetén",  # "betegség"
    ],
)
def test_health_claim_words_are_found_case_and_accent_insensitively(text: str) -> None:
    assert health_claim_stems(text)


def test_every_documented_word_is_covered() -> None:
    for word in ("egészséges", "fogyaszt", "diéta", "méregtelenít", "immun", "gyógy", "betegség"):
        assert health_claim_stems(word), word
    assert len(HEALTH_CLAIM_STEMS) == 7


@pytest.mark.parametrize(
    "text",
    ["Sült lazac kaporral", "A hagymát párold üvegesre, majd add hozzá a lencsét.", "Fogd a tojást", ""],
)
def test_ordinary_text_has_no_health_claims(text: str) -> None:
    assert health_claim_stems(text) == []


@pytest.mark.parametrize(
    "pattern",
    ["csirkemell", "\\bpac", "tel(j)?\\.? ?kior", "extra ?szuz", "\\b[24] ?t\\b", "[^0-9]kg", "a" * 120],
)
def test_good_patterns_pass_the_lint(pattern: str) -> None:
    assert pattern_problems(pattern) == []


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("Csirke", "lower case"),
        ("\\D", "lower case"),  # upper-case escapes are rejected too: use [^0-9]
        ("filé", "ASCII"),
        ("panírozott", "ASCII"),
        ("a" * 121, "121 characters"),
        ("(abc", "does not compile"),
        ("[a-", "does not compile"),
        ("a?", "empty string"),
        ("x*", "empty string"),
        ("a|", "empty string"),
        ("extra  szuz", "double spaces"),
        ("extra\tszuz", "tabs"),
        ("", "non-empty string"),
        (5, "non-empty string"),
        (None, "non-empty string"),
    ],
)
def test_bad_patterns_are_rejected(pattern: object, expected: str) -> None:
    problems = pattern_problems(pattern)
    assert any(expected in p for p in problems), problems


def test_problems_collector_and_error_rendering() -> None:
    problems = Problems()
    assert not problems
    problems.raise_if_any()  # nothing to raise
    for i in range(60):
        problems.add(f"file.json[{i}]", "bad")
    with pytest.raises(ContentError) as info:
        problems.raise_if_any()
    assert len(info.value.problems) == 60
    text = str(info.value)
    assert text.startswith("60 content problem(s):")
    assert "and 10 more" in text
    with pytest.raises(ValueError, match="at least one problem"):
        ContentError([])


def _write(tmp_path: Path, raw: bytes) -> Path:
    path = tmp_path / "x.json"
    path.write_bytes(raw)
    return path


def test_read_json_parses_decimals_not_floats(tmp_path: Path) -> None:
    data = read_json(_write(tmp_path, b'{"a": 0.1, "b": 2, "c": [1e3]}'))
    assert data == {"a": Decimal("0.1"), "b": 2, "c": [Decimal("1E+3")]}
    assert isinstance(data["a"], Decimal)
    assert isinstance(data["b"], int)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b'{"a": 1, "a": 2}', "duplicate key 'a'"),
        (b'{"a": NaN}', "NaN is not allowed"),
        (b'{"a": Infinity}', "Infinity is not allowed"),
        (b'{"a": 1,}', "invalid JSON at line 1"),
        (b"\xef\xbb\xbf{}", "byte-order mark"),
        (b'{"a": "\xe9"}', "not valid UTF-8"),
    ],
)
def test_read_json_rejects_bad_files(tmp_path: Path, raw: bytes, expected: str) -> None:
    with pytest.raises(ContentError) as info:
        read_json(_write(tmp_path, raw))
    assert expected in str(info.value)


def test_read_json_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ContentError, match="cannot read"):
        read_json(tmp_path / "missing.json")
