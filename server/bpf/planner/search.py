"""``suggest_plan``: a deterministic, seeded constraint search over the recipe library.

1. Pools: for each requested slot, the recipes whose ``slots`` include it, minus recipes with an excluded
   tag and recipes with an excluded ingredient on a non-optional line. Pools are sorted by recipe id, so
   the input order of ``recipes`` does not matter.
2. Pool analysis (``analyse_pools``): the rules the pools provably cannot satisfy become warnings (below).
3. Construction, feasibility first (``bpf.planner.construct``): a depth-first search with constraint
   propagation and seeded restarts fills every cell so that every rule not proven impossible holds (the
   fish, legume and meat-free-day rules are propagated per block, so their cells are placed as soon as a
   block runs out of alternatives). If its node budget runs out, a second search drops the variety rule
   (the value order still avoids repeats), and if that fails too, one pass that enforces nothing (guided by
   the same value order) starts the local search.
4. Local search with a move budget proportional to the plan size (never a clock, so results are
   reproducible): random reassignments, same-slot swaps between days, ``ket_napos`` next-day copies,
   leftover-aware reassignments, targeted repairs of failing rules (rules the pools make impossible are not
   targeted), and, after every ``DEEP_AFTER`` moves without progress, a steepest-descent step over one cell.
   A move is kept when it does not worsen the score, which is lexicographic: violations of the rules other
   than variety, then variety repeats, then the distance to feasibility, then the number of distinct
   perishable ingredients (``perishable_days <= 7``) per 7-day block (leftover-aware grouping). So the plan
   never trades another rule for variety, and leftovers only count among plans that are equal on the rules.
   Budgets: a plan that meets every rule gets a short leftover polish (``POLISH_MOVES_PER_CELL``); one that
   breaks only rules the analysis proved impossible gets ``SETTLE_MOVES_PER_CELL`` to break them as little as
   possible (both at least ``MIN_MOVES``); one whose feasibility-first construction failed gets the repair
   budget. A per-plan random preference per recipe (``PREFERENCE``) steers the construction, so that each
   plan reuses its own favourites and different seeds use different recipes.
5. The returned checks are computed from scratch with the same code as ``check_plan``.

Warnings (machine codes, in this order):
* ``slot_pool_empty:<slot>``: no eligible recipe; that slot's meals are ``None``.
* ``slot_pool_too_small:<slot>``: the variety rule cannot hold for this slot (alone, or with the other slots
  that share its recipes) within one no-repeat window, or it can hold only with potato on two days in a row.
  The planner then keeps the other rules and lets this slot repeat (variety is the lowest-priority rule).
* ``no_fish_recipe_available`` / ``no_legume_recipe_available``: no eligible recipe for that count rule.
* ``no_meat_free_recipe_available:<slot>``: this slot has recipes, but none is ``husmentes``.
* ``no_potato_free_recipe_available:<slot>``: every recipe of this main slot contains potato.
* ``red_meat_cap_unreachable``, ``budget_unreachable``: even the lightest / cheapest choice per slot breaks
  the rule in some block.
* ``recipe_cost_missing``: a weekly budget was given but there is no cost table, or the plan uses a recipe
  without a cost estimate (its block then fails the budget rule).
Pool-level warnings are only emitted when the rule is provably impossible; the search may still fail a
rule without a warning (the failing check says so).
"""

from __future__ import annotations

import random
from bisect import insort
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from bpf.pricing.model import SLOTS_5, Ingredient, Plan, PlanDay, PlanRequest, Recipe

from .construct import Construct
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
"""Weight of one variety repeat, the lowest-priority rule: every rule violation weighs at least this."""
HARD = 1000 * VIOLATION
"""Weight of one violation unit of any other rule. A plan has at most 31 x 5 = 155 repeats, so repeats
never outweigh one such unit."""
GUIDE = 10**5
GUIDE_CAP = 10**6
# The order stays strict: guidance per block is at most 2 x GUIDE_CAP + 7, so all guidance of a 31-day plan
# (5 blocks) stays below one VIOLATION, and the distinct perishables of a block stay far below one GUIDE.

STRICT_NODES_PER_CELL = 20
"""Node budget of the feasibility-first construction per plan cell (no backtracking = one node per cell)."""
RELAXED_NODES_PER_CELL = 8
"""Node budget of the construction without the variety rule, per plan cell."""
POLISH_MOVES_PER_CELL = 8
"""Local-search moves per plan cell after a construction that meets every rule (leftover polish only)."""
SETTLE_MOVES_PER_CELL = 12
"""Local-search moves per plan cell after a construction that meets every rule the pool analysis did not rule
out: only the degree of the impossible rules (repeats in too-small slots, red meat, cost...) is left to
reduce."""
MIN_MOVES = 600
"""Floor of the polish and settle budgets, so that short plans also get enough leftover moves."""
REPAIR_MOVES_PER_CELL = 20
REPAIR_MIN_MOVES = 1000
ITERATIONS = 6000
"""Local-search moves when the start still breaks a rule: ``REPAIR_MOVES_PER_CELL`` per cell, at least
``REPAIR_MIN_MOVES`` and at most ``ITERATIONS`` (31 days x 5 slots: 3100 moves of about 10-25 us)."""
PATIENCE = 2500
"""Stop early after this many moves without a strict improvement."""
DEEP_AFTER = 300
"""Moves without progress before each steepest-descent step."""
STEEPEST_MAX_RECIPES = 40
"""Reassignments a steepest-descent step evaluates at most (plus every same-slot swap)."""
REPAIR_SHARE = 0.4
SWAP_REPAIR_SHARE = 0.5
"""Share of variety and potato repairs that swap the cell with another day instead of replacing it."""
PREFERENCE = 0.6
"""Spread of the per-plan random preference for each recipe in the construction's value order: within a plan
the same recipes are favoured (good for leftovers), across seeds different ones, so every recipe gets used.
On the real library, 200 four-week plans have about one distinct perishable a week fewer than with the
previous planner, and their rarest lunch/dinner recipe appears at least as often."""
LEFTOVER_SHARE = 0.25
"""Share of plain moves that reassign a cell to a meal adding no perishable ingredient to its block."""

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
    if not red_ok(t, lim):
        units += 1
        limit = lim.red_limit_g(t.days) * lim.red_den
        guide += min(GUIDE_CAP, (t.red - limit) * 1000 // max(limit, lim.red_den))
    if not budget_ok(t, lim):
        units += 1
        limit_ft = lim.budget_limit(t.days)
        excess = max(t.cost - limit_ft, Decimal(0))
        guide += min(GUIDE_CAP, t.unpriced * 1000 + int(excess * 1000 / max(limit_ft, Decimal(1))))
    return units * HARD + guide * GUIDE + t.perish_distinct


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
        self.total = (
            sum(self.block_pen) + HARD * self._potato_pairs(all_pairs) + VIOLATION * sum(self.repeats)
        )

    def load(self, cells: Sequence[int]) -> None:
        """Fill the active slots from a construction (one meal index per cell, day-major) and score it."""
        width = len(self.active)
        for day in range(self.n):
            for k, pos in enumerate(self.active):
                self._set(day, pos, cells[day * width + k])
        self.recompute()

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
        before = sum(saved_pen) + HARD * self._potato_pairs(pairs) + VIOLATION * sum(saved_rep)
        undo = [(day, pos, self._set(day, pos, new)) for day, pos, new in changes]
        for w in weeks:
            block_pen[w] = block_penalty(self.blocks[w], self.lim)
        for m in touched:
            repeats[m] = count = self._repeat_count(m)
            self._mark_repeating(m, count)
        after = (
            sum(block_pen[w] for w in weeks)
            + HARD * self._potato_pairs(pairs)
            + VIOLATION * sum(repeats[m] for m in touched)
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

    def optimise(self, rng: random.Random, iterations: int = ITERATIONS, patience: int = PATIENCE) -> None:
        """Keep every move that does not worsen the score (so the current plan is always the best seen).
        Every ``DEEP_AFTER`` moves without progress, run a steepest-descent step on one cell (one involved
        in a violation while there are any); stop after ``patience`` moves without progress."""
        if not self.multi:  # every active slot has a single recipe: nothing to choose
            return
        idle = 0
        for _ in range(iterations):
            before = self.total
            changes = self._propose(rng)
            if changes:
                self._try(changes)
            if self.total < before:
                idle = 0
                continue
            idle += 1
            if idle > patience:
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
            if pen >= HARD and set(block_failures(self.blocks[w], self.lim)) - self.hopeless[w]:
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
        if draw < LEFTOVER_SHARE:
            return self._leftover(rng)
        if draw < 0.6:
            return self._reassign(rng)
        if draw < 0.9 or not self.has_two_day:
            return self._swap(rng)
        return self._two_day_copy(rng)

    def _reassign(self, rng: random.Random) -> list[Change] | None:
        if not self.multi:
            return None
        pos = self.multi[rng.randrange(len(self.multi))]
        day = rng.randrange(self.n)
        return self._replace(day, pos, self.pools[pos], rng)

    def _leftover(self, rng: random.Random) -> list[Change] | None:
        """In a random block, take a meal whose cells alone bring some perishable ingredient into the block,
        and reassign each of those cells to a meal whose perishable ingredients the rest of the block already
        uses (the move never adds a distinct perishable and removes at least one)."""
        if not self.multi:
            return None
        week = rng.randrange(len(self.blocks))
        block = self.blocks[week]
        perish = block.perish
        start = week * WEEK_DAYS
        cells_of: dict[int, list[tuple[int, int]]] = {}
        for day in range(start, start + block.days):
            for pos in self.multi:
                cells_of.setdefault(self.grid[day][pos], []).append((day, pos))
        lonely = [
            m
            for m, cells in cells_of.items()
            if any(perish[x] == len(cells) for x in self.meals[m].perish_bits)
        ]
        if not lonely:
            return None
        current = lonely[rng.randrange(len(lonely))]
        own = self.meals[current].perish_bits
        cells = cells_of[current]
        changes: list[Change] = []
        for day, pos in cells:
            covered = [
                m
                for m in self.pools[pos]
                if m != current
                and all(perish[x] - (len(cells) if x in own else 0) > 0 for x in self.meals[m].perish_bits)
            ]
            if not covered:
                return None
            changes.append((day, pos, covered[rng.randrange(len(covered))]))
        return changes

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
            if self.block_pen[w] >= HARD:
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


@dataclass(frozen=True, slots=True)
class PoolAnalysis:
    """What the pools alone prove about a request (``analyse_pools``)."""

    warnings: tuple[str, ...]
    hopeless: tuple[frozenset[str], ...]  # per block: block rules no plan can satisfy
    too_small: frozenset[int]  # slot positions whose variety rule is given up (slot_pool_too_small)
    potato_hopeless: bool  # some main slot only has potato recipes (and the plan has >= 2 days)


def _block_lengths(n_days: int) -> list[int]:
    return [min(WEEK_DAYS, n_days - start) for start in range(0, n_days, WEEK_DAYS)]


def _subsets(group: Sequence[int]) -> list[list[int]]:
    return [[pos for i, pos in enumerate(group) if mask >> i & 1] for mask in range(1, 1 << len(group))]


def _capacity(recipes: set[int], meals: Sequence[Meal], span: int) -> int:
    """Cells that ``recipes`` can fill in ``span`` consecutive days without a repeat: one each, or two for a
    ``ket_napos`` recipe (the same slot on the next day)."""
    return sum(2 if meals[m].two_day and span >= 2 else 1 for m in recipes)


def _too_small_slots(
    group: Sequence[int],
    pools: Mapping[int, tuple[int, ...]],
    meals: Sequence[Meal],
    window: int,
    n_days: int,
) -> set[int]:
    """Slot positions of ``group`` that cannot avoid repeats within one window.

    Within ``span = min(window, days)`` consecutive days, the slots of a subset S need ``span x |S|`` meals,
    and no two of them may share a recipe (every pair of ``group`` repeats within ``window``) except a
    ``ket_napos`` next-day pair. If the recipes available to S cannot cover that, every slot of S gets the
    warning (Hall's condition)."""
    span = min(window, n_days)
    flagged: set[int] = set()
    if span < 1:
        return flagged
    for subset in _subsets([pos for pos in group if pools[pos]]):
        union = {m for pos in subset for m in pools[pos]}
        if _capacity(union, meals, span) < span * len(subset):
            flagged.update(subset)
    return flagged


def _potato_free_slots(
    group: Sequence[int],
    pools: Mapping[int, tuple[int, ...]],
    meals: Sequence[Meal],
    window: int,
    n_days: int,
) -> set[int]:
    """Main slots of ``group`` that cannot avoid repeats on the potato-free days the potato rule forces.

    With no two potato days in a row, a plan of ``n <= window`` days has at least ``n // 2`` potato-free
    days, and a longer plan has some ``window`` consecutive days with at least ``ceil(window / 2)`` of them
    (of ``window + 1`` days at least half are potato-free, and if both ``window``-day parts had fewer, the
    days between their ends would hold two potato days in a row). On a potato-free day every main slot
    needs a recipe without potato, and no two of them may share a recipe within the window: if the
    potato-free recipes of a subset S cannot cover ``free_days x |S|`` cells, every slot of S is flagged."""
    span = min(window, n_days)
    flagged: set[int] = set()
    if span < 1 or n_days < 2:
        return flagged
    free_days = (window + 1) // 2 if n_days > window else n_days // 2
    for subset in _subsets(group):
        plain = {m for pos in subset for m in pools[pos] if not meals[m].potato}
        if _capacity(plain, meals, span) < free_days * len(subset):
            flagged.update(subset)
    return flagged


def analyse_pools(
    n_days: int,
    positions: Sequence[int],
    pools: Mapping[int, tuple[int, ...]],
    meals: Sequence[Meal],
    lim: Limits,
) -> PoolAnalysis:
    """Warnings for rules the pools provably cannot satisfy, per block the block rules that are hopeless (the
    search neither enforces nor repairs them), and the slots whose variety rule is given up."""
    active = [pos for pos in positions if pools[pos]]
    main = [pos for pos in active if pos in MAIN_POS]

    no_fish = not any(meals[m].fish for pos in active for m in pools[pos])
    no_legume = not any(meals[m].legume for pos in active for m in pools[pos])
    meaty_slots = [pos for pos in active if not any(meals[m].meat_free for m in pools[pos])]
    red_per_day = sum(min(meals[m].red_units for m in pools[pos]) for pos in active)
    cheapest = [[c for m in pools[pos] if (c := meals[m].cost) is not None] for pos in active]
    lengths = _block_lengths(n_days)
    hopeless: list[frozenset[str]] = []
    for days in lengths:
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
        if (
            lim.budget is not None
            and active
            and (not all(cheapest) or sum(min(c) for c in cheapest) * days > lim.budget_limit(days))
        ):
            rules.add("budget")
        hopeless.append(frozenset(rules))

    potato_free_missing = [pos for pos in main if all(meals[m].potato for m in pools[pos])]
    potato_hopeless = n_days >= 2 and bool(potato_free_missing)

    # variety: within the main window every pair of main slots repeats; within the snack window every pair
    small = _too_small_slots(main, pools, meals, lim.main_window, n_days)
    small |= _too_small_slots(active, pools, meals, lim.snack_window, n_days)
    # variety together with another rule: when avoiding repeats is only possible by breaking the potato rule,
    # the slot repeats instead (variety is the lowest-priority rule)
    if not potato_hopeless:
        open_main = [pos for pos in main if pos not in small]
        small |= _potato_free_slots(open_main, pools, meals, lim.main_window, n_days)

    warnings = [f"slot_pool_empty:{SLOTS_5[pos]}" for pos in positions if not pools[pos]]
    warnings += [f"slot_pool_too_small:{SLOTS_5[pos]}" for pos in positions if pos in small]
    if n_days >= COUNT_RULE_MIN_DAYS:
        warnings += ["no_fish_recipe_available"] * no_fish + ["no_legume_recipe_available"] * no_legume
        warnings += [f"no_meat_free_recipe_available:{SLOTS_5[pos]}" for pos in meaty_slots]
    if n_days >= 2:
        warnings += [f"no_potato_free_recipe_available:{SLOTS_5[pos]}" for pos in potato_free_missing]
    for rule, code in (
        ("red_meat", "red_meat_cap_unreachable"),
        ("budget", "budget_unreachable"),
    ):
        if any(rule in rules for rules in hopeless):
            warnings.append(code)
    return PoolAnalysis(
        warnings=tuple(warnings),
        hopeless=tuple(hopeless),
        too_small=frozenset(small),
        potato_hopeless=potato_hopeless,
    )


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


def build_plan(
    search: _Search,
    pools: Mapping[int, tuple[int, ...]],
    meals: Sequence[Meal],
    lim: Limits,
    analysis: PoolAnalysis,
    rng: random.Random,
) -> None:
    """Construct ``search``'s plan (feasibility first; then without the variety rule; then guided only) and
    optimise it with the move budget that fits the start (see the module docstring)."""
    if not search.active:
        search.recompute()
        return
    cells = search.n * len(search.active)
    preference = [PREFERENCE * rng.random() for _ in meals]

    def construction(relaxed: frozenset[int], *, enforce: bool = True) -> Construct:
        return Construct(
            search.n,
            search.active,
            pools,
            meals,
            lim,
            hopeless=analysis.hopeless,
            relaxed=relaxed,
            enforce_potato=not analysis.potato_hopeless,
            enforce=enforce,
            preference=preference,
        )

    found = construction(analysis.too_small).solve(rng, STRICT_NODES_PER_CELL * cells)
    settled = found is not None
    if found is None:
        found = construction(frozenset(search.active)).solve(rng, RELAXED_NODES_PER_CELL * cells)
    if found is None:
        found = construction(frozenset(search.active), enforce=False).solve(rng, cells)
    if found is None:  # pragma: no cover - a construction that enforces nothing cannot fail
        raise AssertionError("the guided construction failed")
    search.load(found)
    if search.total < VIOLATION:  # every rule holds: only the leftover score can improve
        moves = max(MIN_MOVES, POLISH_MOVES_PER_CELL * cells)
        search.optimise(rng, moves, moves)
    elif settled:  # only rules the analysis proved impossible fail: reduce how much they fail
        search.optimise(rng, max(MIN_MOVES, SETTLE_MOVES_PER_CELL * cells), PATIENCE)
    else:
        search.optimise(rng, min(ITERATIONS, max(REPAIR_MIN_MOVES, REPAIR_MOVES_PER_CELL * cells)), PATIENCE)


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
    analysis = analyse_pools(req.days, positions, pools, meals, lim)

    search = _Search(req.days, positions, pools, meals, lim, len(perishables), analysis.hopeless)
    rng = random.Random(req.seed)  # noqa: S311 - reproducible plan variety, not security
    build_plan(search, pools, meals, lim, analysis, rng)

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
    warnings = list(analysis.warnings)
    if budget is not None and (
        not costs or any(meals[m].cost is None for row in search.grid for m in row if m != NO_MEAL)
    ):
        warnings.append("recipe_cost_missing")
    return Plan(days=days, checks=checks, warnings=tuple(warnings))
