"""``python -m bpf.content``: validate the content files, check recipe coverage and load them as bpf_ingest.

Modes::

    python -m bpf.content                      # validate, coverage check, write (one transaction)
    python -m bpf.content --dry-run            # validate + coverage check; no database at all
    python -m bpf.content --coverage-report    # validate + full per-recipe coverage report; never writes
    python -m bpf.content --allow-low-coverage # load even when recipes are below 90 % (recorded as warnings)
    python -m bpf.content --convert-ksh RAW [--ksh-format stadat|research] [--ksh-fetched YYYY-MM-DD]
                                               # rewrite data/ksh/ara0044.csv and SOURCE.md from a KSH file

Coverage prices: the latest DB chain prices when a database is reachable and has them, else the research
reference prices, else KSH (see :mod:`bpf.content.coverage`). ``--dry-run`` never connects, so it always uses
the reference prices. ``--coverage-report`` uses the database when it can and says so when it cannot.

Exit codes: 0 = success; 1 = invalid content, recipes below the coverage rule (without
``--allow-low-coverage``) or a database error (nothing written); 2 = bad command line.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path

import psycopg

from bpf.config import Settings
from bpf.content.coverage import (
    choose_prices,
    compute_coverage,
    db_prices,
    load_reference_prices,
    render_report,
)
from bpf.content.errors import ContentError
from bpf.content.jsonio import display_path
from bpf.content.ksh_convert import KSH_TABLE_URL, convert_ksh_file
from bpf.content.leaves import FoodLeaves, food_leaves_from_db
from bpf.content.load import Content, load_content
from bpf.content.paths import ContentPaths
from bpf.content.writer import fail_run, start_run, write_content
from bpf.db import MissingCredentialsError, connect


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bpf.content",
        description="Validate data/ (ingredients, recipes, KSH prices), check recipe coverage and load it.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="validate and check coverage only; no database"
    )
    parser.add_argument(
        "--coverage-report", action="store_true", help="print the per-recipe coverage report; never writes"
    )
    parser.add_argument(
        "--allow-low-coverage", action="store_true", help="load even if recipes fail the 90 %% coverage rule"
    )
    parser.add_argument("--convert-ksh", metavar="RAW", help="convert a KSH ara0044 file and exit")
    parser.add_argument("--ksh-format", choices=("stadat", "research"), default="stadat")
    parser.add_argument("--ksh-fetched", metavar="YYYY-MM-DD", type=date.fromisoformat, default=None)
    parser.add_argument("--ksh-url", default=KSH_TABLE_URL)
    return parser


def _print_problems(error: ContentError) -> None:
    print(f"error: {len(error.problems)} content problem(s); nothing was written:", file=sys.stderr)
    for problem in error.problems:
        print(f"  - {problem}", file=sys.stderr)


def _convert(args: argparse.Namespace, paths: ContentPaths) -> int:
    try:
        result = convert_ksh_file(
            Path(args.convert_ksh),
            raw_format=args.ksh_format,
            fetched=args.ksh_fetched,
            url=args.ksh_url,
            csv_path=paths.ksh,
            source_path=paths.ksh.parent / "SOURCE.md",
        )
    except ContentError as exc:
        _print_problems(exc)
        return 1
    conv = result.conversion
    print(
        f"wrote {display_path(result.csv_path)} ({len(conv.rows)} food rows; "
        f"{len(conv.dropped_food)} food rows "
        f"and {conv.non_food} non-food rows dropped) and {display_path(result.source_path)} "
        f"(input sha256 {result.sha256}, {conv.encoding})"
    )
    for dropped in conv.dropped_food:
        print(f"  dropped {dropped.code} {dropped.item!r}: {dropped.reason}")
    return 0


@contextlib.contextmanager
def _maybe_connect(settings: Settings | None, *, required: bool) -> Iterator[psycopg.Connection | None]:
    """An autocommit ``bpf_ingest`` connection, or None when optional and unavailable."""
    conn: psycopg.Connection | None = None
    try:
        conn = connect("ingest", settings=settings, autocommit=True)
    except (MissingCredentialsError, psycopg.OperationalError) as exc:
        if required:
            raise
        reason = "no credentials" if isinstance(exc, MissingCredentialsError) else "connection failed"
        print(f"note: database not used for prices ({reason}); using the reference prices", file=sys.stderr)
    if conn is None:
        yield None
        return
    with conn:
        yield conn


def _coverage(
    content: Content, paths: ContentPaths, conn: psycopg.Connection | None, *, full: bool
) -> tuple[list[str], str]:
    """(ids of failing recipes, report text)."""
    ingredients = content.ingredient_map()
    data_date, from_db = db_prices(conn, list(ingredients.values())) if conn is not None else (None, {})
    refs = load_reference_prices(paths.reference_prices)
    prices = choose_prices(ingredients.values(), db_prices=from_db, refs=refs, ksh=content.ksh)
    results = compute_coverage(content.recipes.values(), ingredients, prices)
    if data_date is not None:
        note = (
            f"DB chain prices of {data_date} ({len(from_db)} ingredients), "
            f"else {display_path(paths.reference_prices)}"
        )
    else:
        note = f"{display_path(paths.reference_prices)} (no DB prices), KSH for non-GVH ingredients"
    report = render_report(results, price_note=note, full=full)
    return [r.recipe_id for r in results if not r.ok], report


def _run(args: argparse.Namespace, paths: ContentPaths, conn: psycopg.Connection | None) -> int:
    leaves: FoodLeaves | None = food_leaves_from_db(conn) if conn is not None else None
    try:
        content = load_content(paths, leaves=leaves)
        failing, report = _coverage(content, paths, conn, full=args.coverage_report)
    except ContentError as exc:
        _print_problems(exc)
        return 1
    print(
        f"content valid: {len(content.ingredients)} ingredients, {len(content.recipes)} recipes, "
        f"{len(content.ksh)} KSH rows, {len(content.nutrition)} nutrition rows "
        f"(leaves: {content.leaves_source})"
    )
    print(report)
    if failing and not args.allow_low_coverage:
        print(
            f"error: {len(failing)} recipe(s) fail the coverage rule; nothing was written "
            "(pass --allow-low-coverage to load anyway)",
            file=sys.stderr,
        )
        return 1
    if args.dry_run or args.coverage_report or conn is None:
        return 0
    warnings = [f"recipe below the coverage rule, loaded with --allow-low-coverage: {rid}" for rid in failing]
    run_id = start_run(conn)
    try:
        stats = write_content(conn, content, run_id=run_id, warnings=warnings)
    except Exception as exc:
        try:
            fail_run(conn, run_id, f"{type(exc).__name__}: {exc}")
        except psycopg.Error as mark_error:
            print(f"note: could not mark ingest_run {run_id} failed: {mark_error}", file=sys.stderr)
        if not isinstance(exc, psycopg.Error):
            raise
        print(
            f"error: database write failed, nothing was written (ingest_run {run_id}): {exc}", file=sys.stderr
        )
        return 1
    changes = ", ".join(f"{k}={v}" for k, v in stats.items() if v and not k.endswith("_unchanged"))
    print(f"loaded (ingest_run {run_id}): {changes or 'no changes'}")
    return 0


def main(
    argv: Sequence[str] | None = None, *, paths: ContentPaths | None = None, settings: Settings | None = None
) -> int:
    args = _parser().parse_args(argv)
    paths = paths if paths is not None else ContentPaths()
    if args.convert_ksh:
        return _convert(args, paths)
    if args.dry_run:
        return _run(args, paths, None)
    try:
        with _maybe_connect(settings, required=not args.coverage_report) as conn:
            return _run(args, paths, conn)
    except MissingCredentialsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except psycopg.Error as exc:
        print(f"error: database error, nothing was written: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
