"""``suggest_plan``: a deterministic, seeded constraint search over the recipe library.

1. Pools: for each requested slot, the recipes whose ``slots`` include it, minus recipes with an excluded
   tag and recipes with an excluded ingredient on a non-optional line. Pools are sorted by recipe id, so
   the input order of ``recipes`` does not matter.
2. Construction: fill every slot day by day, preferring recipes not used within the no-repeat window.
3. Local search with a fixed iteration budget (never a clock, so results are reproducible): random
   reassignments, same-slot swaps between days, ``ket_napos`` next-day copies, targeted repairs of the
   failing rules (rules the pools make impossible are not targeted), and, after every ``DEEP_AFTER`` moves
   without progress, a steepest-descent step over one cell. A move is kept when it does not worsen the score
   ``VIOLATION x rule violations + GUIDE x distance-to-feasibility + distinct perishables per block``.
   Rules always dominate; within the rules, the score minimises the number of distinct perishable
   ingredients (``perishable_days <= 7``) in each 7-day block (leftover-aware grouping).
   It is a heuristic: with pools barely large enough for the no-repeat window it can miss a plan that
   meets every rule (another seed may find one).
4. The returned checks are computed from scratch with the same code as ``check_plan``.

Warnings (machine codes, in this order):
* ``slot_pool_empty:<slot>``: no eligible recipe; that slot's meals are ``None``.
* ``slot_pool_too_small:<slot>``: the variety rule cannot hold for this slot (alone, or with the other slots
  of its group that share recipes) within one no-repeat window.
* ``no_fish_recipe_available`` / ``no_legume_recipe_available``: no eligible recipe for that count rule.
* ``no_meat_free_recipe_available:<slot>``: this slot has recipes, but none is ``husmentes``.
* ``no_potato_free_recipe_available:<slot>``: every recipe of this main slot contains potato.
* ``red_meat_cap_unreachable``, ``sweets_cap_unreachable``, ``budget_unreachable``: even the lightest /
  least sweet / cheapest choice per slot breaks the rule in some block.
* ``recipe_cost_missing``: a weekly budget was given but there is no cost table, or the plan uses a recipe
  without a cost estimate (its block then fails the budget rule).
Pool-level warnings are only emitted when the rule is provably impossible; the search may still fail a
rule without a warning (the failing check says so).
"""

from __future__ import annotations

import random
from bisect import insort
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal

from bpf.pricing.model import SLOTS_5, Ingredient, Plan, PlanDay, PlanRequest, Recipe

from .facts import (
    MAIN_POS,
    MAX_DAYS,
    SLOT_POS,
    recipe_facts,
    validate_costs,
    validate_money,
    validate_non_negative_int,
    validate_people,
)
from .rules import (
    COUNT_RULE_MIN_DAYS,
    NO_MEAL,
    SWEETS_MAX,
    WEEK_DAYS,
    BlockTotals,
    Limits,
    Meal,
    block_failures,
    budget_ok,
    compile_meals,
    count_rules_apply,
    evaluate,
    make_limits,
    red_ok,
    repeat_flags,
)

VIOLATION = 10**13
GUIDE = 10**5
GUIDE_CAP = 10**6
# Score weights keep the order strict: guidance per block is at most 2 x GUIDE_CAP + 7, so all guidance of a
# 31-day plan (5 blocks) stays below one VIOLATION, and the distinct perishables of a block (a few dozen
# ingredients) stay far below one GUIDE.
ITERATIONS = 6000
"""Search moves per plan. About 6000 x 10 us keeps 31 days x 5 slots near 60 ms; small plans converge."""
PATIENCE = 2500
"""Stop early after this many moves without a strict improvement."""
DEEP_AFTER = 300
"""Moves without progress before each steepest-descent step."""
STEEPEST_MAX_RECIPES = 40
"""Reassignments a steepest-descent step evaluates at most (plus every same-slot swap)."""
REPAIR_SHARE = 0.4
SWAP_REPAIR_SHARE = 0.5
"""Share of variety and potato repairs that swap the cell with another day instead of replacing it."""

Change = tuple[int, int, int]  # (day, slot position, meal index)
_Undo = tuple[list[Change], list[int], list[int], list[int], list[int]]


# ───────────────────────────── scoring ─────────────────────────────


def block_penalty(t: BlockTotals, lim: Limits) -> int:
    """Score of one block: rule violations, then distance to feasibility, then distinct perishables.

    The violation units mirror ``block_failures`` / ``week_checks`` exactly (zero units <=> all ok)."""
    units = 0
    guide = 0
    if count_rules_apply(t):
        units += (t.fish == 0) + (t.legume == 0)
        if t.free_days == 0:
            units += 1
            guide += min((t.day_meaty[o] for o in range(WEEK_DAYS) if t.day_meals[o] > 0), default=0)
    if t.sweets > SWEETS_MAX:
        units += t.sweets - SWEETS_MAX
    if not red_ok(t, lim):
        units += 1
        limit = lim.red_limit_g(t.days) * lim.red_den
        guide += min(GUIDE_CAP, (t.red - limit) * 1000 // max(limit, lim.red_den))
    if not budget_ok(t, lim):
        units += 1
        limit_ft = lim.budget_limit(t.days)
        excess = max(t.cost - limit_ft, Decimal(0))
        guide += min(GUIDE_CAP, t.unpriced * 1000 + int(excess * 1000 / max(limit_ft, Decimal(1))))
    return units * VIOLATION + guide * GUIDE + t.perish_distinct


class _Search:
    """Mutable search state over a ``days x 5`` grid of meal indexes (``NO_MEAL`` outside the plan)."""

    def __init__(
        self,
        n_days: int,
        positions: Sequence[int],
        pools: Mapping[int, tuple[int, ...]],
        meals: Sequence[Meal],
        lim: Limits,
        n_perish_bits: int,
        hopeless: Sequence[frozenset[str]] = (),
    ) -> None:
        self.n = n_days
        self.active = tuple(pos for pos in positions if pools[pos])
        self.multi = tuple(pos for pos in self.active if len(pools[pos]) > 1)
        self.pools = pools
        self.meals = meals
        self.lim = lim
        self.grid = [[NO_MEAL] * len(SLOTS_5) for _ in range(n_days)]
        n_weeks = (n_days + WEEK_DAYS - 1) // WEEK_DAYS
        self.blocks = [
            BlockTotals(min(WEEK_DAYS, n_days - WEEK_DAYS * w), n_perish_bits) for w in range(n_weeks)
        ]
        self.block_pen = [0] * n_weeks
        self.hopeless = list(hopeless) or [frozenset()] * n_weeks  # block rules no plan can satisfy
        self.occ: list[list[tuple[int, int]]] = [[] for _ in meals]
        self.repeats = [0] * len(meals)
        self.repeating: set[int] = set()  # meal indexes with repeats > 0
        self.potato = [0] * n_days  # main-slot potato meals per day
        self.total = 0
        self.has_two_day = any(meals[m].two_day for pos in self.active for m in pools[pos])

        def sub(pred: Callable[[Meal], bool]) -> dict[int, tuple[int, ...]]:
            return {pos: tuple(m for m in pools[pos] if pred(meals[m])) for pos in self.active}

        self.fish_pool = sub(lambda meal: meal.fish == 1)
        self.legume_pool = sub(lambda meal: meal.legume == 1)
        self.free_pool = sub(lambda meal: meal.meat_free)
        self.nonsweet_pool = sub(lambda meal: meal.sweet == 0)
        self.nopotato_pool = sub(lambda meal: not meal.potato)
        self.priced_pool = sub(lambda meal: meal.cost is not None)

    # ── state updates ──

    def _set(self, day: int, pos: int, new: int) -> int:
        row = self.grid[day]
        old = row[pos]
        if old == new:
            return old
        block = self.blocks[day // WEEK_DAYS]
        offset = day % WEEK_DAYS
        main = pos in MAIN_POS
        if old != NO_MEAL:
            meal = self.meals[old]
            block.add(offset, meal, -1)
            self.occ[old].remove((day, pos))
            if main and meal.potato:
                self.potato[day] -= 1
        if new != NO_MEAL:
            meal = self.meals[new]
            block.add(offset, meal, 1)
            insort(self.occ[new], (day, pos))
            if main and meal.potato:
                self.potato[day] += 1
        row[pos] = new
        return old

    def _repeat_count(self, m: int) -> int:
        return sum(
            repeat_flags(self.occ[m], self.meals[m].two_day, self.lim.main_window, self.lim.snack_window)
        )

    def _potato_pairs(self, pairs: Sequence[int]) -> int:
        """Number of potato day pairs ``(d - 1, d)`` among the given ``d``."""
        pot = self.potato
        return sum(1 for d in pairs if pot[d] and pot[d - 1])

    def recompute(self) -> None:
        self.block_pen = [block_penalty(block, self.lim) for block in self.blocks]
        self.repeats = [self._repeat_count(m) for m in range(len(self.meals))]
        self.repeating = {m for m, count in enumerate(self.repeats) if count}
        all_pairs = range(1, self.n)
        self.total = sum(self.block_pen) + VIOLATION * (sum(self.repeats) + self._potato_pairs(all_pairs))

    def _apply(self, changes: Sequence[Change]) -> tuple[int, _Undo]:
        """Apply ``changes`` and update the score. Returns the score delta and what ``_revert`` needs.

        Only the touched blocks, recipes and potato day pairs can change score, so only they are re-scored."""
        weeks: list[int] = []
        touched: list[int] = []
        pairs: list[int] = []  # d stands for the day pair (d - 1, d)
        for day, pos, new in changes:
            week = day // WEEK_DAYS
            if week not in weeks:
                weeks.append(week)
            for m in (self.grid[day][pos], new):
                if m != NO_MEAL and m not in touched:
                    touched.append(m)
            for d in (day, day + 1):
                if 1 <= d < self.n and d not in pairs:
                    pairs.append(d)
        block_pen = self.block_pen
        repeats = self.repeats
        saved_pen = [block_pen[w] for w in weeks]
        saved_rep = [repeats[m] for m in touched]
        before = sum(saved_pen) + VIOLATION * (sum(saved_rep) + self._potato_pairs(pairs))
        undo = [(day, pos, self._set(day, pos, new)) for day, pos, new in changes]
        for w in weeks:
            block_pen[w] = block_penalty(self.blocks[w], self.lim)
        for m in touched:
            repeats[m] = count = self._repeat_count(m)
            self._mark_repeating(m, count)
        after = sum(block_pen[w] for w in weeks) + VIOLATION * (
            sum(repeats[m] for m in touched) + self._potato_pairs(pairs)
        )
        self.total += after - before
        return after - before, (undo, weeks, saved_pen, touched, saved_rep)

    def _revert(self, delta: int, saved: _Undo) -> None:
        undo, weeks, saved_pen, touched, saved_rep = saved
        for day, pos, old in reversed(undo):
            self._set(day, pos, old)
        for w, pen in zip(weeks, saved_pen, strict=True):
            self.block_pen[w] = pen
        for m, rep in zip(touched, saved_rep, strict=True):
            self.repeats[m] = rep
            self._mark_repeating(m, rep)
        self.total -= delta

    def _mark_repeating(self, m: int, count: int) -> None:
        if count:
            self.repeating.add(m)
        else:
            self.repeating.discard(m)

    def _try(self, changes: Sequence[Change]) -> None:
        """Keep ``changes`` if the score does not get worse, else undo them."""
        delta, saved = self._apply(changes)
        if delta > 0:
            self._revert(delta, saved)

    # ── construction and search ──

    def construct(self, rng: random.Random) -> None:
        last_day = [-(10**9)] * len(self.meals)
        window = max(self.lim.main_window, 1)
        for day in range(self.n):
            for pos in self.active:
                pool = self.pools[pos]
                fresh = [m for m in pool if day - last_day[m] >= window]
                pick = rng.choice(fresh or pool)
                self._set(day, pos, pick)
                last_day[pick] = day
        self.recompute()

    def optimise(self, rng: random.Random) -> None:
        """Keep every move that does not worsen the score (so the current plan is always the best seen).
        Every ``DEEP_AFTER`` moves without progress, run a steepest-descent step on one cell (one involved
        in a violation while there are any); stop after ``PATIENCE`` moves without progress."""
        if not self.multi:  # every active slot has a single recipe: nothing to choose
            return
        idle = 0
        for _ in range(ITERATIONS):
            before = self.total
            changes = self._propose(rng)
            if changes:
                self._try(changes)
            if self.total < before:
                idle = 0
                continue
            idle += 1
            if idle > PATIENCE:
                break
            if idle % DEEP_AFTER == 0:
                self._steepest(rng)
                if self.total < before:
                    idle = 0

    def _steepest(self, rng: random.Random) -> None:
        """Try the reassignments and every same-slot swap of one cell (involved in a fixable violation if
        there is one, else any cell with a choice); apply the best (random among equals) unless it worsens
        the score."""
        cells = self._violation_cells() or [(day, pos) for day in range(self.n) for pos in self.multi]
        day, pos = cells[rng.randrange(len(cells))]
        current = self.grid[day][pos]
        others = [m for m in self.pools[pos] if m != current]
        if len(others) > STEEPEST_MAX_RECIPES:  # bound the cost on very large pools
            others = rng.sample(others, STEEPEST_MAX_RECIPES)
        options = [[(day, pos, m)] for m in others]
        options += [
            [(day, pos, self.grid[d][pos]), (d, pos, current)]
            for d in range(self.n)
            if self.grid[d][pos] != current
        ]
        best_delta: int | None = None
        best: list[list[Change]] = []
        for changes in options:
            delta, saved = self._apply(changes)
            self._revert(delta, saved)
            if best_delta is None or delta < best_delta:
                best_delta, best = delta, [changes]
            elif delta == best_delta:
                best.append(changes)
        if best_delta is not None and best_delta <= 0:
            self._apply(best[rng.randrange(len(best))])

    def _violation_cells(self) -> list[tuple[int, int]]:
        """Cells (with a choice) of repeated meals, potato day pairs and blocks that break a rule."""
        cells: list[tuple[int, int]] = []
        for m in sorted(self.repeating):
            flags = repeat_flags(
                self.occ[m], self.meals[m].two_day, self.lim.main_window, self.lim.snack_window
            )
            cells += [occ for occ, hit in zip(self.occ[m], flags, strict=True) if hit]
        for d in range(1, self.n):
            if self.potato[d] and self.potato[d - 1]:
                cells += [(day, pos) for day in (d - 1, d) for pos in self.active if pos in MAIN_POS]
        for w, pen in enumerate(self.block_pen):
            if pen >= VIOLATION and set(block_failures(self.blocks[w], self.lim)) - self.hopeless[w]:
                start = w * WEEK_DAYS
                cells += [
                    (day, pos) for day in range(start, min(start + WEEK_DAYS, self.n)) for pos in self.active
                ]
        return [(day, pos) for day, pos in cells if len(self.pools[pos]) > 1]

    def _propose(self, rng: random.Random) -> list[Change] | None:
        if self.total >= VIOLATION and rng.random() < REPAIR_SHARE:
            repair = self._repair(rng)
            if repair:
                return repair
        draw = rng.random()
        if draw < 0.5:
            return self._reassign(rng)
        if draw < 0.85 or not self.has_two_day:
            return self._swap(rng)
        return self._two_day_copy(rng)

    def _reassign(self, rng: random.Random) -> list[Change] | None:
        if not self.multi:
            return None
        pos = self.multi[rng.randrange(len(self.multi))]
        day = rng.randrange(self.n)
        return self._replace(day, pos, self.pools[pos], rng)

    def _replace(self, day: int, pos: int, choices: Sequence[int], rng: random.Random) -> list[Change] | None:
        """Change cell ``(day, pos)`` to a uniformly random member of ``choices`` (distinct recipe indexes)
        other than its current recipe; ``None`` when there is no other member."""
        current = self.grid[day][pos]
        size = len(choices)
        if size == 0 or (size == 1 and choices[0] == current):
            return None
        i = rng.randrange(size)
        if choices[i] == current:  # draw again among the other size - 1 members, still uniform
            j = rng.randrange(size - 1)
            i = j + 1 if j >= i else j
        return [(day, pos, choices[i])]

    def _swap(self, rng: random.Random) -> list[Change] | None:
        if self.n < 2 or not self.multi:
            return None
        pos = self.multi[rng.randrange(len(self.multi))]
        day1 = rng.randrange(self.n)
        day2 = rng.randrange(self.n - 1)
        if day2 >= day1:
            day2 += 1
        a, b = self.grid[day1][pos], self.grid[day2][pos]
        if a == b:
            return None
        return [(day1, pos, b), (day2, pos, a)]

    def _two_day_copy(self, rng: random.Random) -> list[Change] | None:
        if self.n < 2 or not self.multi:
            return None
        pos = self.multi[rng.randrange(len(self.multi))]
        day = rng.randrange(1, self.n)
        m = self.grid[day - 1][pos]
        if not self.meals[m].two_day or self.grid[day][pos] == m:
            return None
        return [(day, pos, m)]

    # ── targeted repairs ──

    def _repair(self, rng: random.Random) -> list[Change] | None:
        issues: list[tuple[str, int]] = []
        for w, block in enumerate(self.blocks):
            if self.block_pen[w] >= VIOLATION:
                issues.extend(
                    (rule, w) for rule in block_failures(block, self.lim) if rule not in self.hopeless[w]
                )
        issues.extend(("variety", m) for m in sorted(self.repeating))
        issues.extend(("potato", d) for d in range(1, self.n) if self.potato[d] and self.potato[d - 1])
        if not issues:
            return None
        rule, arg = issues[rng.randrange(len(issues))]
        if rule == "variety":
            return self._repair_variety(arg, rng)
        if rule == "potato":
            return self._repair_potato(arg, rng)
        return self._repair_block(rule, arg, rng)

    def _cells(self, week: int, pred: Callable[[Meal], bool]) -> list[tuple[int, int]]:
        start = week * WEEK_DAYS
        return [
            (day, pos)
            for day in range(start, min(start + WEEK_DAYS, self.n))
            for pos in self.active
            if pred(self.meals[self.grid[day][pos]])
        ]

    def _repair_block(self, rule: str, week: int, rng: random.Random) -> list[Change] | None:
        start = week * WEEK_DAYS
        if rule in ("fish", "legume"):
            sub = self.fish_pool if rule == "fish" else self.legume_pool
            positions = [pos for pos in self.active if sub[pos]]
            if not positions:
                return None
            day = start + rng.randrange(self.blocks[week].days)
            pos = positions[rng.randrange(len(positions))]
            return self._replace(day, pos, sub[pos], rng)
        if rule == "meat_free_day":
            block = self.blocks[week]
            meaty = [block.day_meaty[o] for o in range(block.days) if block.day_meals[o] > 0]
            if not meaty:
                return None
            fewest = min(meaty)
            offsets = [
                o for o in range(block.days) if block.day_meals[o] > 0 and block.day_meaty[o] == fewest
            ]
            day = start + offsets[rng.randrange(len(offsets))]
            cells = [pos for pos in self.active if not self.meals[self.grid[day][pos]].meat_free]
            cells = [pos for pos in cells if self.free_pool[pos]]
            if not cells:
                return None
            pos = cells[rng.randrange(len(cells))]
            return self._replace(day, pos, self.free_pool[pos], rng)
        if rule == "sweets":
            cells = [
                (d, p) for d, p in self._cells(week, lambda meal: meal.sweet == 1) if self.nonsweet_pool[p]
            ]
            if not cells:
                return None
            day, pos = cells[rng.randrange(len(cells))]
            return self._replace(day, pos, self.nonsweet_pool[pos], rng)
        if rule == "red_meat":
            cells = self._cells(week, lambda meal: meal.red_units > 0)
            if not cells:
                return None
            day, pos = cells[rng.randrange(len(cells))]
            current = self.meals[self.grid[day][pos]].red_units
            return self._replace(
                day, pos, [m for m in self.pools[pos] if self.meals[m].red_units < current], rng
            )
        # budget: replace an unpriced meal by a priced one, else a priced meal by a cheaper one
        unpriced = [
            (d, p) for d, p in self._cells(week, lambda meal: meal.cost is None) if self.priced_pool[p]
        ]
        if unpriced:
            day, pos = unpriced[rng.randrange(len(unpriced))]
            return self._replace(day, pos, self.priced_pool[pos], rng)
        priced = self._cells(week, lambda meal: meal.cost is not None)
        if not priced:
            return None
        day, pos = priced[rng.randrange(len(priced))]
        cost = self.meals[self.grid[day][pos]].cost
        cheaper = [
            m
            for m in self.priced_pool[pos]
            if (c := self.meals[m].cost) is not None and cost is not None and c < cost
        ]
        return self._replace(day, pos, cheaper, rng)

    def _swap_days(self, day: int, pos: int, rng: random.Random) -> list[Change] | None:
        """Swap cell ``(day, pos)`` with the same slot on a random other day."""
        if self.n < 2:
            return None
        other = rng.randrange(self.n - 1)
        if other >= day:
            other += 1
        a, b = self.grid[day][pos], self.grid[other][pos]
        if a == b:
            return None
        return [(day, pos, b), (other, pos, a)]

    def _repair_variety(self, m: int, rng: random.Random) -> list[Change] | None:
        occs = self.occ[m]
        flags = repeat_flags(occs, self.meals[m].two_day, self.lim.main_window, self.lim.snack_window)
        hits = [occ for occ, hit in zip(occs, flags, strict=True) if hit and len(self.pools[occ[1]]) > 1]
        if not hits:
            return None
        day, pos = hits[rng.randrange(len(hits))]
        if rng.random() < SWAP_REPAIR_SHARE:
            return self._swap_days(day, pos, rng)
        return self._replace(day, pos, self.pools[pos], rng)

    def _repair_potato(self, day: int, rng: random.Random) -> list[Change] | None:
        cells = [
            (d, pos)
            for d in (day - 1, day)
            for pos in self.active
            if pos in MAIN_POS and len(self.pools[pos]) > 1 and self.meals[self.grid[d][pos]].potato
        ]
        if not cells:
            return None
        d, pos = cells[rng.randrange(len(cells))]
        if rng.random() < SWAP_REPAIR_SHARE or not self.nopotato_pool[pos]:
            return self._swap_days(d, pos, rng)
        return self._replace(d, pos, self.nopotato_pool[pos], rng)


# ───────────────────────────── pool analysis (warnings) ─────────────────────────────


def _block_lengths(n_days: int) -> list[int]:
    return [min(WEEK_DAYS, n_days - start) for start in range(0, n_days, WEEK_DAYS)]


def _too_small_slots(
    group: Sequence[int],
    pools: Mapping[int, tuple[int, ...]],
    meals: Sequence[Meal],
    window: int,
    n_days: int,
) -> set[int]:
    """Slot positions of ``group`` that cannot avoid repeats within one window.

    Within ``span = min(window, days)`` consecutive days, the slots of a subset S need ``span x |S|`` meals
    and a recipe can fill at most one of them (two for a ``ket_napos`` recipe: same slot, next day). If the
    recipes available to S cannot cover that, every slot of S gets the warning (Hall's condition)."""
    span = min(window, n_days)
    active = [pos for pos in group if pools[pos]]
    flagged: set[int] = set()
    if span < 1:
        return flagged
    for mask in range(1, 1 << len(active)):
        subset = [pos for i, pos in enumerate(active) if mask >> i & 1]
        union = {m for pos in subset for m in pools[pos]}
        capacity = sum(2 if meals[m].two_day and span >= 2 else 1 for m in union)
        if capacity < span * len(subset):
            flagged.update(subset)
    return flagged


def analyse_pools(
    n_days: int,
    positions: Sequence[int],
    pools: Mapping[int, tuple[int, ...]],
    meals: Sequence[Meal],
    lim: Limits,
) -> tuple[list[str], list[frozenset[str]]]:
    """Warnings for rules the pools provably cannot satisfy, and per block the block rules that are hopeless
    (the search does not spend repairs on them)."""
    warnings = [f"slot_pool_empty:{SLOTS_5[pos]}" for pos in positions if not pools[pos]]
    active = [pos for pos in positions if pools[pos]]
    main = [pos for pos in active if pos in MAIN_POS]
    snack = [pos for pos in active if pos not in MAIN_POS]
    small = _too_small_slots(main, pools, meals, lim.main_window, n_days)
    small |= _too_small_slots(snack, pools, meals, lim.snack_window, n_days)
    warnings += [f"slot_pool_too_small:{SLOTS_5[pos]}" for pos in positions if pos in small]

    no_fish = not any(meals[m].fish for pos in active for m in pools[pos])
    no_legume = not any(meals[m].legume for pos in active for m in pools[pos])
    meaty_slots = [pos for pos in active if not any(meals[m].meat_free for m in pools[pos])]
    if n_days >= COUNT_RULE_MIN_DAYS:
        warnings += ["no_fish_recipe_available"] * no_fish + ["no_legume_recipe_available"] * no_legume
        warnings += [f"no_meat_free_recipe_available:{SLOTS_5[pos]}" for pos in meaty_slots]
    if n_days >= 2:
        warnings += [
            f"no_potato_free_recipe_available:{SLOTS_5[pos]}"
            for pos in main
            if all(meals[m].potato for m in pools[pos])
        ]

    red_per_day = sum(min(meals[m].red_units for m in pools[pos]) for pos in active)
    sweet_per_day = sum(1 for pos in active if all(meals[m].sweet for m in pools[pos]))
    cheapest = [[c for m in pools[pos] if (c := meals[m].cost) is not None] for pos in active]
    hopeless: list[frozenset[str]] = []
    for days in _block_lengths(n_days):
        rules: set[str] = set()
        if days >= COUNT_RULE_MIN_DAYS:
            rules.update(
                rule
                for rule, dead in (
                    ("fish", no_fish),
                    ("legume", no_legume),
                    ("meat_free_day", bool(meaty_slots) or not active),
                )
                if dead
            )
        if days * red_per_day > lim.red_limit_g(days) * lim.red_den:
            rules.add("red_meat")
        if days * sweet_per_day > SWEETS_MAX:
            rules.add("sweets")
        if (
            lim.budget is not None
            and active
            and (not all(cheapest) or sum(min(c) for c in cheapest) * days > lim.budget_limit(days))
        ):
            rules.add("budget")
        hopeless.append(frozenset(rules))
    for rule, code in (
        ("red_meat", "red_meat_cap_unreachable"),
        ("sweets", "sweets_cap_unreachable"),
        ("budget", "budget_unreachable"),
    ):
        if any(rule in rules for rules in hopeless):
            warnings.append(code)
    return warnings, hopeless


# ───────────────────────────── public: suggest_plan ─────────────────────────────


def _validate_request(req: PlanRequest) -> tuple[int, ...]:
    """Validate ``req`` and return the requested slot positions (ascending)."""
    if isinstance(req.days, bool) or not isinstance(req.days, int) or not 1 <= req.days <= MAX_DAYS:
        raise ValueError(f"days must be an int in 1..{MAX_DAYS}")
    if not req.slots:
        raise ValueError("slots must not be empty")
    positions: list[int] = []
    for slot in req.slots:
        pos = SLOT_POS.get(slot)
        if pos is None:
            raise ValueError(f"unknown slot {slot!r}")
        if positions and pos <= positions[-1]:
            raise ValueError("slots must be distinct and in SLOTS_5 order")
        positions.append(pos)
    validate_people(req.people)
    validate_non_negative_int(req.red_meat_g_per_person_week, "red_meat_g_per_person_week")
    validate_non_negative_int(req.no_repeat_days, "no_repeat_days")
    if isinstance(req.seed, bool) or not isinstance(req.seed, int):
        raise ValueError("seed must be an int")
    return tuple(positions)


def _excluded(recipe: Recipe, req: PlanRequest) -> bool:
    if req.exclude_tags.intersection(recipe.tags):
        return True
    return any(not line.optional and line.ingredient_id in req.exclude_ingredients for line in recipe.lines)


def suggest_plan(recipes: Sequence[Recipe], ingredients: Mapping[str, Ingredient], req: PlanRequest) -> Plan:
    """Suggest a plan for ``req`` (see the module docstring). Same input and seed -> identical plan.

    Raises ``ValueError`` for an invalid request or duplicate recipe ids, and ``KeyError`` when an eligible
    recipe uses an unknown ingredient."""
    positions = _validate_request(req)
    costs = validate_costs(req.recipe_cost_per_serving)
    budget = None if req.weekly_budget is None else validate_money(req.weekly_budget, "weekly_budget")
    by_id: dict[str, Recipe] = {}
    for recipe in recipes:
        if recipe.id in by_id:
            raise ValueError(f"duplicate recipe id {recipe.id!r}")
        by_id[recipe.id] = recipe
    wanted = {SLOTS_5[pos] for pos in positions}
    used = [
        by_id[rid]
        for rid in sorted(by_id)
        if wanted.intersection(by_id[rid].slots) and not _excluded(by_id[rid], req)
    ]
    facts = [recipe_facts(recipe, ingredients, people=req.people, costs=costs) for recipe in used]
    perishables = sorted({iid for f in facts for iid in f.perishables} - req.exclude_ingredients)
    meals, red_den = compile_meals(facts, {iid: bit for bit, iid in enumerate(perishables)})
    pools = {
        pos: tuple(i for i, recipe in enumerate(used) if SLOTS_5[pos] in recipe.slots) for pos in positions
    }
    lim = make_limits(req.red_meat_g_per_person_week, red_den, budget if costs else None, req.no_repeat_days)
    warnings, hopeless = analyse_pools(req.days, positions, pools, meals, lim)

    search = _Search(req.days, positions, pools, meals, lim, len(perishables), hopeless)
    rng = random.Random(req.seed)  # noqa: S311 - reproducible plan variety, not security
    search.construct(rng)
    search.optimise(rng)

    days = tuple(
        PlanDay(
            index=day,
            meals={
                SLOTS_5[pos]: None if (m := search.grid[day][pos]) == NO_MEAL else meals[m].recipe_id
                for pos in positions
            },
        )
        for day in range(req.days)
    )
    has_snacks = any(pos not in MAIN_POS for pos in positions)
    n_weeks = (req.days + WEEK_DAYS - 1) // WEEK_DAYS
    checks = evaluate(
        {day: search.grid[day] for day in range(req.days)},
        frozenset(range(n_weeks)) if has_snacks else frozenset(),
        meals,
        lim,
    )
    if budget is not None and (
        not costs or any(meals[m].cost is None for row in search.grid for m in row if m != NO_MEAL)
    ):
        warnings.append("recipe_cost_missing")
    return Plan(days=days, checks=checks, warnings=tuple(warnings))
