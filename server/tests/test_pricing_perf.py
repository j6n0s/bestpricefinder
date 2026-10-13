"""PERFORMANCE of a full /api/quote computation (quote_store per store + rank_stores + suggest_split) on a
SYNTHETIC catalogue of about 4,000 products (tests/fixtures/pricing/builders.py).

Targets: 40 lines x 15 stores < 300 ms; 200 lines x 25 stores < 2 s. The best of 3 runs is compared (the
first run also warms the per-ingredient matching memo, as a long-running API process would be). Timings are
printed; run with ``-s`` to see them."""

from __future__ import annotations

import time

import pytest

from bpf.pricing import Catalogue, quote_store, rank_stores, suggest_split
from tests.fixtures.pricing.builders import synthetic_catalogue, synthetic_lines


@pytest.fixture(scope="module")
def big_catalogue() -> Catalogue:
    cat = synthetic_catalogue(seed=7)
    assert len(cat.products) == 4_000
    return cat


def _full_quote_seconds(cat: Catalogue, n_lines: int, n_stores: int) -> tuple[float, int]:
    lines = synthetic_lines(cat, n_lines, seed=3)
    stores = sorted(cat.stores.values(), key=lambda s: s.id)[:n_stores]
    started = time.perf_counter()
    quotes = [quote_store(lines, s, cat) for s in stores]
    rank_stores(quotes)
    suggest_split(quotes)
    elapsed = time.perf_counter() - started
    priced = sum(1 for q in quotes for line in q.lines if line.status == "priced")
    return elapsed, priced


@pytest.mark.parametrize(("n_lines", "n_stores", "budget_s"), [(40, 15, 0.3), (200, 25, 2.0)])
def test_quote_performance(big_catalogue: Catalogue, n_lines: int, n_stores: int, budget_s: float) -> None:
    runs = [_full_quote_seconds(big_catalogue, n_lines, n_stores) for _ in range(3)]
    best = min(elapsed for elapsed, _ in runs)
    priced = runs[0][1]
    print(
        f"\nquote {n_lines} lines x {n_stores} stores: runs "
        + ", ".join(f"{elapsed * 1000:.0f} ms" for elapsed, _ in runs)
        + f" (best {best * 1000:.0f} ms, budget {budget_s * 1000:.0f} ms; {priced} priced line-store pairs)"
    )
    assert priced > n_lines * n_stores // 2  # the synthetic data really exercises the optimiser
    assert best < budget_s
