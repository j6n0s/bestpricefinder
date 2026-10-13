"""``python -m bpf.content`` without a database: dry run, report fallback, KSH conversion, exit codes."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bpf.config import Settings
from bpf.content.__main__ import main
from bpf.content.paths import KSH_RESEARCH_CSV, ContentPaths

FIXTURES = Path(__file__).parent / "fixtures" / "content"
SERVER = Path(__file__).resolve().parents[1]


def fixture_paths(root: Path) -> ContentPaths:
    """A writable copy of the synthetic fixture set under ``root``."""
    shutil.copytree(FIXTURES / "recipes", root / "recipes")
    for name in ("ingredients.json", "ksh.csv", "reference_prices.csv"):
        shutil.copy(FIXTURES / name, root / name)
    return ContentPaths(
        ingredients=root / "ingredients.json",
        recipes_dir=root / "recipes",
        ksh=root / "ksh.csv",
        nutrition=root / "nutrition.json",  # absent: no composition data
        reference_prices=root / "reference_prices.csv",
    )


NO_DB = Settings(_env_file=None, ingest_password=None)  # type: ignore[call-arg]


def test_dry_run_on_valid_content(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--dry-run"], paths=fixture_paths(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "content valid: 10 ingredients, 3 recipes, 2 KSH rows, 0 nutrition rows" in out
    assert "3 recipe(s), 0 failing." in out


def test_dry_run_reports_every_problem_and_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = fixture_paths(tmp_path)
    data = json.loads(paths.ingredients.read_text())
    data["ingredients"][0]["include_patterns"] = ["Csirke"]
    data["ingredients"][1]["leaf_ids"] = [999]
    paths.ingredients.write_text(json.dumps(data))
    assert main(["--dry-run"], paths=paths) == 1
    err = capsys.readouterr().err
    assert "2 content problem(s); nothing was written" in err
    assert "lower case" in err
    assert "999 is not a GVH food leaf" in err


def _lower_coverage(paths: ContentPaths) -> None:
    text = (paths.recipes_dir / "a.json").read_text()
    (paths.recipes_dir / "a.json").write_text(text.replace('"qty": 0.05', '"qty": 0.5'))  # more KSH gomba


def test_low_coverage_blocks_unless_allowed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = fixture_paths(tmp_path)
    _lower_coverage(paths)
    assert main(["--dry-run"], paths=paths) == 1
    captured = capsys.readouterr()
    assert "FAIL csirke-gombaval: 50.5% < 90.0%" in captured.out  # 1020 / (1020 + 1000)
    assert "1 recipe(s) fail the coverage rule; nothing was written" in captured.err
    assert main(["--dry-run", "--allow-low-coverage"], paths=paths) == 0


def test_coverage_report_falls_back_to_reference_prices_without_a_database(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--coverage-report"], paths=fixture_paths(tmp_path), settings=NO_DB) == 0
    captured = capsys.readouterr()
    assert "database not used for prices (no credentials)" in captured.err
    assert "csirke-gombaval    91.1%" in captured.out


def test_load_without_credentials_fails_cleanly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], paths=fixture_paths(tmp_path), settings=NO_DB) == 1
    assert "BPF_INGEST_PASSWORD is not set" in capsys.readouterr().err


def test_load_with_an_unreachable_database_fails_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, ingest_password="s3cr3t-test-pw", db_host="127.0.0.1", db_port=free_port()
    )
    assert main([], paths=fixture_paths(tmp_path), settings=settings) == 1
    err = capsys.readouterr().err
    assert "database error, nothing was written: OperationalError" in err
    assert "s3cr3t-test-pw" not in err


def free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_convert_ksh(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = fixture_paths(tmp_path)
    argv = ["--convert-ksh", str(KSH_RESEARCH_CSV), "--ksh-format", "research", "--ksh-fetched", "2026-10-12"]
    assert main(argv, paths=paths) == 0
    out = capsys.readouterr().out
    assert "61 food rows; 6 food rows and 108 non-food rows dropped" in out
    assert (tmp_path / "SOURCE.md").exists()
    assert paths.ksh.read_text(encoding="utf-8").startswith("code,name,unit,unit_qty,price,period\n10001,")


def test_convert_ksh_bad_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    raw = tmp_path / "raw.csv"
    raw.write_text("garbage\n")
    assert main(["--convert-ksh", str(raw)], paths=fixture_paths(tmp_path)) == 1
    assert "no header row found" in capsys.readouterr().err


def test_bad_command_line() -> None:
    with pytest.raises(SystemExit) as info:
        main(["--ksh-fetched", "yesterday", "--convert-ksh", "x"])
    assert info.value.code == 2


def test_module_entry_point_dry_run_on_the_real_data() -> None:
    proc = subprocess.run(  # the real data/ files, no database
        [sys.executable, "-m", "bpf.content", "--dry-run"],
        cwd=SERVER,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "content valid: 159 ingredients" in proc.stdout
