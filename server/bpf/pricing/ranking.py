"""Rank stores and suggest an optional 2-store split (ENGINE.md ``rank_stores``, ``suggest_split``;
BUILD-BRIEF §6.3).

Missing-line penalty ("imputed cost"): for a line that is ``unavailable`` at a store, the median
``checkout_cost`` of that ingredient across the OTHER quotes that priced it; no penalty when no other
quote has it (the line still counts in ``missing_count``).

Split: for every pair of stores each line goes to the cheaper of the two (ties go to the better-ranked
store); lines unavailable at both are left out of the assignment and out of ``total``. So that a pair can
never look cheap merely because neither store sells something, the pair is judged on its *penalized*
total: ``total`` + the imputed cost (median over the quotes outside the pair) of the lines unavailable at
both, which is the same basis as the single stores' ``penalized_total``. The best pair (lowest penalized
total, then fewer lines missing at both, then store ids) is returned only when its penalized total is at
least ``threshold`` below the best single store's ``penalized_total``; ``saving`` is that difference.
A "pair" where one store gets no line is not a split and is skipped. ``store_ids`` lists the better-ranked
store first; ``assignment`` maps each assigned ingredient id to its store, in the quotes' line order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from bpf.pricing._num import ZERO, exact, median
from bpf.pricing.model import SplitSuggestion, StoreQuote, StoreRank

DEFAULT_SPLIT_THRESHOLD = Decimal(1500)


def _priced_costs(quote: StoreQuote) -> dict[str, Decimal]:
    """ingredient id -> checkout cost of the priced lines of one quote."""
    costs: dict[str, Decimal] = {}
    for line in quote.lines:
        if line.status == "priced" and line.checkout_cost is not None:
            costs.setdefault(line.ingredient_id, line.checkout_cost)
    return costs


def _imputed(
    ingredient_id: str, priced: Sequence[Mapping[str, Decimal]], excluded: set[int]
) -> Decimal | None:
    """Median checkout cost of the ingredient over the quotes not in ``excluded`` that priced it."""
    costs = [p[ingredient_id] for i, p in enumerate(priced) if i not in excluded and ingredient_id in p]
    return median(costs) if costs else None


@exact
def rank_stores(quotes: Sequence[StoreQuote]) -> tuple[StoreRank, ...]:
    """Rank 1 = lowest penalized total; ties: fewer missing lines, then store id."""
    priced = [_priced_costs(q) for q in quotes]
    rows: list[tuple[Decimal, int, str, StoreQuote]] = []
    for index, quote in enumerate(quotes):
        penalty = ZERO
        for ingredient_id in quote.missing:
            imputed = _imputed(ingredient_id, priced, {index})
            if imputed is not None:
                penalty += imputed
        rows.append((quote.checkout_total + penalty, len(quote.missing), quote.store_id, quote))
    rows.sort(key=lambda row: (row[0], row[1], row[2]))
    return tuple(
        StoreRank(
            store_id=quote.store_id,
            rank=position,
            checkout_total=quote.checkout_total,
            penalized_total=penalized,
            missing_count=missing_count,
        )
        for position, (penalized, missing_count, _, quote) in enumerate(rows, start=1)
    )


def _line_order(quotes: Sequence[StoreQuote]) -> list[str]:
    """Every ingredient id in first-seen order across the quotes."""
    seen: dict[str, None] = {}
    for quote in quotes:
        for line in quote.lines:
            seen.setdefault(line.ingredient_id, None)
    return list(seen)


@exact
def suggest_split(
    quotes: Sequence[StoreQuote], *, threshold: Decimal = DEFAULT_SPLIT_THRESHOLD
) -> SplitSuggestion | None:
    """The best 2-store split, or None when no pair saves at least ``threshold`` (see the module doc)."""
    if len(quotes) < 2:
        return None
    ranking = rank_stores(quotes)
    best_single = ranking[0].penalized_total
    position = {rank.store_id: rank.rank for rank in ranking}
    priced = [_priced_costs(q) for q in quotes]
    missing = [set(q.missing) for q in quotes]
    order = _line_order(quotes)

    best_key: tuple[Decimal, int, tuple[str, str]] | None = None
    best_split: SplitSuggestion | None = None
    for i in range(len(quotes)):
        for j in range(i + 1, len(quotes)):
            if quotes[i].store_id == quotes[j].store_id:
                continue
            first, second = (i, j) if position[quotes[i].store_id] <= position[quotes[j].store_id] else (j, i)
            total = ZERO
            penalty = ZERO
            missing_both = 0
            assignment: dict[str, str] = {}
            for ingredient_id in order:
                cost_a = priced[first].get(ingredient_id)
                cost_b = priced[second].get(ingredient_id)
                if cost_a is not None and (cost_b is None or cost_a <= cost_b):
                    assignment[ingredient_id] = quotes[first].store_id
                    total += cost_a
                elif cost_b is not None:
                    assignment[ingredient_id] = quotes[second].store_id
                    total += cost_b
                elif ingredient_id in missing[first] and ingredient_id in missing[second]:
                    missing_both += 1
                    imputed = _imputed(ingredient_id, priced, {i, j})
                    if imputed is not None:
                        penalty += imputed
            store_ids = (quotes[first].store_id, quotes[second].store_id)
            if not set(store_ids) <= set(assignment.values()):
                continue  # everything at one store: not a split
            penalized = total + penalty
            key = (penalized, missing_both, tuple(sorted(store_ids)))
            if best_key is None or key < best_key:
                best_key = key
                best_split = SplitSuggestion(
                    store_ids=store_ids, total=total, saving=best_single - penalized, assignment=assignment
                )
    if best_split is None or best_key is None or best_key[0] > best_single - threshold:
        return None
    return best_split
