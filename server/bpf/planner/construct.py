"""Feasibility-first construction for ``suggest_plan``: a randomised depth-first search with constraint
propagation and restarts (a small CSP solver). Pure: no I/O, no clock; randomness only from the ``rng`` given.

Variables are the plan cells (day x requested slot); a cell's domain is a bit mask over meal indexes.
Assigning a meal propagates every enforced rule (see ``Construct.assign``):

* ``variety``: the meal leaves the domains of the cells inside the no-repeat window. A ``ket_napos`` meal may
  stay in the same slot on the next day; runs of three are cut (the rule pairs days greedily).
* ``potato``: the first main potato meal of a day removes potato meals from the main cells of both neighbours.
* ``red_meat`` / ``budget``: per-block bounds; values that cannot fit any more are removed.
* ``fish`` / ``legume`` / ``meat_free_day``: a block fails as soon as no cell (no day) can still satisfy the
  rule; when exactly one cell (day) can, its domain is restricted (unit propagation).

The next cell is the one with the fewest values left (ties: earliest day, then slot order). Values are tried
in a seeded random order (plus the caller's per-plan ``preference`` per meal) biased towards the rules the
block still needs, towards ``ket_napos`` next-day pairs and towards meals that add no new perishable
ingredient to the block (leftover-aware, docs/ENGINE.md). Each attempt has a node budget; a failed attempt
restarts with a larger budget and fresh random choices from the same generator, so the result depends only
on the input and the seed.

Rules that the pool analysis proved impossible are not enforced (the local search minimises them later), and
the variety rule is not enforced for slots marked ``relaxed``: there the value order only avoids repeats.
With ``enforce=False`` nothing is enforced: one pass, never failing, guided only by the value order (avoid
repeats, prefer light, cheap and potato-free meals and the fish / legume meals a block lacks); it
starts the local search when the enforcing constructions run out of nodes.
"""

from __future__ import annotations

import random
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence
from decimal import Decimal

from .facts import MAIN_POS
from .rules import COUNT_RULE_MIN_DAYS, WEEK_DAYS, Limits, Meal

NEED_BONUS = 0.5
"""Order bonus for a meal that gives the block a fish / legume meal it still lacks."""
PAIR_BONUS = 0.5
"""Order bonus for the second day of a ``ket_napos`` meal (cook once, eat twice)."""
PERISHABLE_PENALTY = 0.25
"""Order penalty per perishable ingredient the meal would add to its block, plus the same penalty over the
number of meals that use the ingredient (of two new perishables, the one more meals share is preferred, since
later cells of the block can reuse it). A mild bias: the random part keeps every recipe in use across seeds,
and the local search's leftover moves do the rest (with 1.0, five of the 25 real lunch/dinner recipes never
appeared in 20 four-week plans)."""
REPEAT_PENALTY = 4.0
"""Order penalty per repeat, in slots where the variety rule is relaxed."""
HOPELESS_PENALTY = 4.0
"""For a rule not enforced in the block (proved impossible, or ``enforce=False``): order penalty for a
main-slot potato meal (``potato``) and, scaled by the meal's rank from lightest / cheapest (0) to heaviest /
most expensive or unpriced (1), for red meat (``red_meat``) and cost (``budget``).
The plan then breaks those rules as little as it can; the local search finishes the job."""
GUIDED_RULES = frozenset({"red_meat", "budget"})
"""The bounded block rules, which ``enforce=False`` only follows through the value order."""
CONSTRAINING_PENALTY = 1.0
"""From the second attempt on: order penalty per open neighbour cell that still has the meal, weighted by one
over that cell's number of values (least-constraining value first; helps where the first attempt failed)."""
FIRST_ATTEMPT_NODES_PER_CELL = 2
"""Node budget of the first attempt per cell (an attempt without backtracking uses one node per cell)."""
ATTEMPT_GROWTH = 1.5


class _OutOfNodes(Exception):
    """The node budget of one attempt is used up."""


def mask_values(mask: int) -> list[int]:
    """Meal indexes of the set bits of ``mask``, ascending."""
    values: list[int] = []
    while mask:
        low = mask & -mask
        values.append(low.bit_length() - 1)
        mask ^= low
    return values


def _prefix_masks[K: (int, Decimal)](items: Sequence[tuple[K, int]]) -> tuple[list[K], list[int]]:
    """For ``(key, meal)`` pairs sorted by key: the distinct keys and, per key, the mask of meals <= key."""
    keys: list[K] = []
    masks: list[int] = []
    acc = 0
    for key, m in items:
        acc |= 1 << m
        if keys and keys[-1] == key:
            masks[-1] = acc
        else:
            keys.append(key)
            masks.append(acc)
    return keys, masks


class Construct:
    """CSP over ``n_days x active`` cells; ``solve`` returns one meal index per cell (day-major) or None."""

    def __init__(
        self,
        n_days: int,
        active: Sequence[int],
        pools: Mapping[int, tuple[int, ...]],
        meals: Sequence[Meal],
        lim: Limits,
        *,
        hopeless: Sequence[frozenset[str]],
        relaxed: frozenset[int],
        enforce_potato: bool,
        enforce: bool = True,
        preference: Sequence[float] = (),
    ) -> None:
        width = len(active)
        cells = n_days * width
        self.n = n_days
        self.width = width
        self.cells = cells
        self.meals = meals
        self.pos = [active[i % width] for i in range(cells)]
        self.day = [i // width for i in range(cells)]
        self.block = [i // width // WEEK_DAYS for i in range(cells)]
        self.is_main = [pos in MAIN_POS for pos in self.pos]
        n_blocks = (n_days + WEEK_DAYS - 1) // WEEK_DAYS
        self.n_blocks = n_blocks
        self.block_days = [range(b * WEEK_DAYS, min(n_days, (b + 1) * WEEK_DAYS)) for b in range(n_blocks)]
        self.block_cells = [range(r.start * width, r.stop * width) for r in self.block_days]
        self.day_cells = [range(d * width, (d + 1) * width) for d in range(n_days)]
        self.main_day_cells = [[i for i in self.day_cells[d] if self.is_main[i]] for d in range(n_days)]
        self.pool_mask = {pos: sum(1 << m for m in pools[pos]) for pos in active}

        def mask(pred: str) -> int:
            return sum(1 << m for m, meal in enumerate(meals) if getattr(meal, pred))

        self.fish_mask = mask("fish")
        self.legume_mask = mask("legume")
        self.free_mask = mask("meat_free")
        self.potato_mask = mask("potato")
        self.priced_mask = sum(1 << m for m, meal in enumerate(meals) if meal.cost is not None)
        self.enforce = enforce
        self.enforce_potato = enforce and enforce_potato
        self.no_preference = [0.0] * len(meals)
        self.preference = list(preference) or self.no_preference  # first attempt only: then feasibility first
        self.retry = False  # set by ``solve`` from the second attempt on
        self.nodes = 0
        self.node_limit = 0
        users: dict[int, int] = {}
        for m in sorted({m for pos in active for m in pools[pos]}):
            for x in meals[m].perish_bits:
                users[x] = users.get(x, 0) + 1
        self.new_perishable_cost = {x: PERISHABLE_PENALTY * (1 + 1 / count) for x, count in users.items()}
        unenforced = [dead if enforce else dead | GUIDED_RULES for dead in hopeless]
        self._build_penalties(meals, lim, unenforced)

        self.need_fish: list[bool] = []
        self.need_legume: list[bool] = []
        self.need_free: list[bool] = []
        self.cap_red: list[bool] = []
        self.cap_budget: list[bool] = []
        for b, days in enumerate(self.block_days):
            dead = unenforced[b]
            counted = len(days) >= COUNT_RULE_MIN_DAYS
            self.need_fish.append(counted and "fish" not in dead)
            self.need_legume.append(counted and "legume" not in dead)
            self.need_free.append(counted and "meat_free_day" not in dead)
            self.cap_red.append("red_meat" not in dead)
            self.cap_budget.append(lim.budget is not None and "budget" not in dead)
        self.red_limit = [lim.red_limit_g(len(days)) * lim.red_den for days in self.block_days]
        self.budget_limit = [
            Decimal(0) if lim.budget is None else lim.budget_limit(len(days)) for days in self.block_days
        ]
        self.red_min: dict[int, int] = {}
        self.red_steps: dict[int, tuple[list[int], list[int]]] = {}
        self.cost_min: dict[int, Decimal | None] = {}
        self.cost_steps: dict[int, tuple[list[Decimal], list[int]]] = {}
        for pos in active:
            reds = sorted((meals[m].red_units, m) for m in pools[pos])
            self.red_min[pos] = reds[0][0]
            self.red_steps[pos] = _prefix_masks(reds)
            costs = sorted((c, m) for m in pools[pos] if (c := meals[m].cost) is not None)
            self.cost_min[pos] = costs[0][0] if costs else None
            self.cost_steps[pos] = _prefix_masks(costs)
        self._build_neighbours(active, lim, relaxed if enforce else frozenset(active))
        self._reset()

    def _build_penalties(
        self, meals: Sequence[Meal], lim: Limits, unenforced: Sequence[frozenset[str]]
    ) -> None:
        """Per block: the order penalty of each meal for the bounded rules not enforced in that block (see
        ``HOPELESS_PENALTY``), as ``(any cell, extra in a main cell)``; ``None`` when there is nothing to
        prefer. Ranks, not amounts, keep money out of float arithmetic."""
        count = len(meals)

        def rank(keys: list[tuple[int, Decimal]]) -> list[float]:
            """Share of the meals with a strictly smaller key (equal keys share a rank)."""
            ordered = sorted(keys)
            return [bisect_left(ordered, key) / count for key in keys]

        red_rank = rank([(0, Decimal(meal.red_units)) for meal in meals])
        cost_rank = rank([(0, meal.cost) if meal.cost is not None else (1, Decimal(0)) for meal in meals])
        self.penalty: list[tuple[list[float], list[float]] | None] = []
        for b in range(self.n_blocks):
            dead = unenforced[b]
            anywhere = [0.0] * count
            in_main = [0.0] * count
            for m, meal in enumerate(meals):
                if "red_meat" in dead:
                    anywhere[m] += HOPELESS_PENALTY * red_rank[m]
                if "budget" in dead and lim.budget is not None:
                    anywhere[m] += HOPELESS_PENALTY * cost_rank[m]
                if not self.enforce_potato and meal.potato:
                    in_main[m] += HOPELESS_PENALTY
            useful = any(anywhere) or any(in_main)
            self.penalty.append((anywhere, in_main) if useful else None)

    def _build_neighbours(self, active: Sequence[int], lim: Limits, relaxed: frozenset[int]) -> None:
        """Per cell: the cells it may not share a meal with (``hard``; the same slot on the previous / next
        day is ``left`` / ``right`` instead, because ``ket_napos`` meals may pair there) and, for relaxed
        slots, the cells whose repeats only the value order avoids (``soft``)."""
        width = self.width
        hard: list[tuple[int, ...]] = []
        soft: list[tuple[int, ...]] = []
        self.left = [-1] * self.cells
        self.right = [-1] * self.cells
        for i in range(self.cells):
            day, pos = self.day[i], self.pos[i]
            near: list[int] = []
            loose: list[int] = []
            for k, pos2 in enumerate(active):
                window = lim.main_window if pos in MAIN_POS and pos2 in MAIN_POS else lim.snack_window
                is_relaxed = pos in relaxed or pos2 in relaxed
                for day2 in range(max(0, day - window + 1), min(self.n, day + window)):
                    j = day2 * width + k
                    if j == i:
                        continue
                    if is_relaxed:
                        loose.append(j)
                    elif pos2 == pos and day2 == day - 1:
                        self.left[i] = j
                    elif pos2 == pos and day2 == day + 1:
                        self.right[i] = j
                    else:
                        near.append(j)
            hard.append(tuple(near))
            soft.append(tuple(loose))
        self.hard = hard
        self.soft = soft

    # ───────────────────────────── state ─────────────────────────────

    def _reset(self) -> None:
        """Empty assignment: every cell open with its slot's whole pool, all counters zero."""
        self.val = [-1] * self.cells
        self.dom = [self.pool_mask[pos] for pos in self.pos]
        n_blocks = self.n_blocks
        self.b_fish = [0] * n_blocks
        self.b_legume = [0] * n_blocks
        self.b_red = [0] * n_blocks
        self.b_red_rest = [sum(self.red_min[self.pos[i]] for i in cells) for cells in self.block_cells]
        self.b_cost = [Decimal(0)] * n_blocks
        self.b_cost_rest = [
            sum((self.cost_min[self.pos[i]] or Decimal(0) for i in cells), Decimal(0))
            for cells in self.block_cells
        ]
        self.b_perish: list[dict[int, int]] = [{} for _ in range(n_blocks)]
        self.d_potato = [0] * self.n
        self.d_meaty = [0] * self.n
        self.trail: list[tuple[int, int]] = []

    def _restrict(self, j: int, keep: int, touched: list[int] | None = None) -> bool:
        """Intersect the domain of unassigned cell ``j`` with ``keep``; ``False`` if it becomes empty."""
        old = self.dom[j]
        new = old & keep
        if new != old:
            if not new:
                return False
            self.trail.append((j, old))
            self.dom[j] = new
            if touched is not None and self.block[j] not in touched:
                touched.append(self.block[j])
        return True

    def _initial(self) -> bool:
        """Prune the domains before the first assignment (budget needs priced meals; per-block bounds)."""
        for b, cells in enumerate(self.block_cells):
            if self.cap_budget[b]:
                for j in cells:
                    if not self._restrict(j, self.priced_mask):
                        return False
                if not self._fit_budget(b):
                    return False
            if self.cap_red[b] and not self._fit_red(b):
                return False
            if not self._block_feasible(b):
                return False
        return True

    def _fit_red(self, b: int) -> bool:
        """Red meat: the block's assigned grams plus the lightest choice of every open cell must fit; remove
        the values that no longer fit."""
        slack = self.red_limit[b] - self.b_red[b] - self.b_red_rest[b]
        if slack < 0:
            return False
        for j in self.block_cells[b]:
            if self.val[j] < 0:
                pos = self.pos[j]
                keys, masks = self.red_steps[pos]
                k = bisect_right(keys, slack + self.red_min[pos]) - 1
                if not self._restrict(j, masks[k]):  # k >= 0: the lightest value always fits
                    return False
        return True

    def _fit_budget(self, b: int) -> bool:
        """Budget: like ``_fit_red`` with the cost of each meal (every open cell is priced here)."""
        slack = self.budget_limit[b] - self.b_cost[b] - self.b_cost_rest[b]
        if slack < 0:
            return False
        for j in self.block_cells[b]:
            if self.val[j] < 0:
                pos = self.pos[j]
                cheapest = self.cost_min[pos]
                if cheapest is None:
                    return False
                keys, masks = self.cost_steps[pos]
                k = bisect_right(keys, slack + cheapest) - 1
                if not self._restrict(j, masks[k]):
                    return False
        return True

    def _block_feasible(self, b: int) -> bool:
        """Count rules of block ``b``: some cell (day) must still be able to satisfy each; force the last."""
        if not self.enforce:
            return True
        val, dom = self.val, self.dom
        for needed, have, rule_mask in (
            (self.need_fish[b], self.b_fish[b], self.fish_mask),
            (self.need_legume[b], self.b_legume[b], self.legume_mask),
        ):
            if needed and not have:
                able = [j for j in self.block_cells[b] if val[j] < 0 and dom[j] & rule_mask]
                if not able:
                    return False
                if len(able) == 1 and not self._restrict(able[0], rule_mask):
                    return False
        if not self.need_free[b]:
            return True
        free = self.free_mask
        possible: list[int] = []
        for day in self.block_days[b]:
            if self.d_meaty[day]:
                continue
            complete = True
            for j in self.day_cells[day]:
                if val[j] < 0:
                    complete = False
                    if not dom[j] & free:
                        break
            else:
                if complete:
                    return True
                possible.append(day)
        if not possible:
            return False
        if len(possible) == 1:
            for j in self.day_cells[possible[0]]:
                if val[j] < 0 and not self._restrict(j, free):
                    return False
        return True

    def assign(self, i: int, m: int) -> bool:
        """Put meal ``m`` in cell ``i`` and propagate. ``False`` = a dead end (the caller undoes with
        ``unassign``, which also reverts the partial propagation)."""
        meal = self.meals[m]
        b = self.block[i]
        day = self.day[i]
        pos = self.pos[i]
        val, dom, trail = self.val, self.dom, self.trail
        val[i] = m
        trail.append((i, dom[i]))
        bit = 1 << m
        dom[i] = bit
        self.b_fish[b] += meal.fish
        self.b_legume[b] += meal.legume
        self.b_red[b] += meal.red_units
        self.b_red_rest[b] -= self.red_min[pos]
        if meal.cost is not None:
            self.b_cost[b] += meal.cost
        cheapest = self.cost_min[pos]
        if cheapest is not None:
            self.b_cost_rest[b] -= cheapest
        perish = self.b_perish[b]
        for x in meal.perish_bits:
            perish[x] = perish.get(x, 0) + 1
        first_potato = False
        if self.is_main[i] and meal.potato:
            self.d_potato[day] += 1
            first_potato = self.d_potato[day] == 1
        if not meal.meat_free:
            self.d_meaty[day] += 1

        touched = [b]
        for j in self.hard[i]:
            if dom[j] & bit and (val[j] >= 0 or not self._restrict(j, ~bit, touched)):
                return False
        if not self._propagate_pairs(i, m, bit, touched):
            return False
        if first_potato and self.enforce_potato:
            for day2 in (day - 1, day + 1):
                if 0 <= day2 < self.n:
                    if self.d_potato[day2]:
                        return False
                    for j in self.main_day_cells[day2]:
                        if val[j] < 0 and not self._restrict(j, ~self.potato_mask, touched):
                            return False
        if self.cap_red[b] and meal.red_units > self.red_min[pos] and not self._fit_red(b):
            return False
        if self.cap_budget[b]:
            if meal.cost is None or cheapest is None:
                return False
            if meal.cost > cheapest and not self._fit_budget(b):
                return False
        return all(self._block_feasible(tb) for tb in sorted(touched))

    def _propagate_pairs(self, i: int, m: int, bit: int, touched: list[int]) -> bool:
        """The same slot on the neighbouring days. Plain meals leave both. A ``ket_napos`` meal may form one
        next-day pair: a run of three is a dead end, a completed pair blocks the days around it, and a free
        neighbour that would complete a run of three loses the meal."""
        left, right, val, dom = self.left, self.right, self.val, self.dom
        if left[i] < 0 and right[i] < 0:
            return True
        if not self.meals[m].two_day:
            for j in (left[i], right[i]):
                if j >= 0 and dom[j] & bit and (val[j] >= 0 or not self._restrict(j, ~bit, touched)):
                    return False
            return True
        before = 0
        start = left[i]
        while start >= 0 and val[start] == m:
            before += 1
            start = left[start]
        after = 0
        end = right[i]
        while end >= 0 and val[end] == m:
            after += 1
            end = right[end]
        run = before + 1 + after
        if run >= 3:
            return False
        if run == 2:  # start / end are the cells just outside the pair
            return all(
                j < 0 or not dom[j] & bit or (val[j] < 0 and self._restrict(j, ~bit, touched))
                for j in (start, end)
            )
        for j, side in ((left[i], left), (right[i], right)):
            beyond = side[j] if j >= 0 else -1
            if (
                j >= 0
                and val[j] < 0
                and dom[j] & bit
                and beyond >= 0
                and val[beyond] == m
                and not self._restrict(j, ~bit, touched)
            ):
                return False
        return True

    def unassign(self, i: int, m: int, mark: int) -> None:
        """Undo ``assign(i, m)`` (complete or not): counters, then every domain change after ``mark``."""
        meal = self.meals[m]
        b = self.block[i]
        day = self.day[i]
        pos = self.pos[i]
        self.val[i] = -1
        self.b_fish[b] -= meal.fish
        self.b_legume[b] -= meal.legume
        self.b_red[b] -= meal.red_units
        self.b_red_rest[b] += self.red_min[pos]
        if meal.cost is not None:
            self.b_cost[b] -= meal.cost
        cheapest = self.cost_min[pos]
        if cheapest is not None:
            self.b_cost_rest[b] += cheapest
        perish = self.b_perish[b]
        for x in meal.perish_bits:
            perish[x] -= 1
        if self.is_main[i] and meal.potato:
            self.d_potato[day] -= 1
        if not meal.meat_free:
            self.d_meaty[day] -= 1
        trail, dom = self.trail, self.dom
        while len(trail) > mark:
            j, old = trail.pop()
            dom[j] = old

    # ───────────────────────────── search ─────────────────────────────

    def _order(self, i: int, rng: random.Random) -> list[int]:
        """Values of cell ``i`` in try order: random, biased by the block's needs, pairs and perishables (and,
        after a failed attempt, by how much the value constrains the open neighbours)."""
        b = self.block[i]
        need_fish = self.need_fish[b] and not self.b_fish[b]
        need_legume = self.need_legume[b] and not self.b_legume[b]
        perish = self.b_perish[b]
        left = self.left[i]
        previous = self.val[left] if left >= 0 else -1
        soft = self.soft[i]
        val, dom = self.val, self.dom
        new_cost = self.new_perishable_cost
        sizes = [(dom[j], dom[j].bit_count()) for j in self.hard[i] if val[j] < 0] if self.retry else []
        penalty = self.penalty[b]
        keyed: list[tuple[float, int]] = []
        preference = self.no_preference if self.retry else self.preference
        for m in mask_values(dom[i]):
            meal = self.meals[m]
            key = rng.random() + preference[m]
            if penalty is not None:
                key += penalty[0][m] + (penalty[1][m] if self.is_main[i] else 0.0)
            if (need_fish and meal.fish) or (need_legume and meal.legume):
                key -= NEED_BONUS
            if m == previous and meal.two_day:
                key -= PAIR_BONUS
            key += sum(new_cost[x] for x in meal.perish_bits if not perish.get(x))
            if soft:
                key += REPEAT_PENALTY * sum(1 for j in soft if val[j] == m)
            if sizes:
                bit = 1 << m
                key += CONSTRAINING_PENALTY * sum(1 / size for mask, size in sizes if mask & bit)
            keyed.append((key, m))
        keyed.sort()
        return [m for _, m in keyed]

    def _select(self) -> int:
        """The open cell with the fewest values (first in day-major order on ties); -1 when all are set."""
        best = -1
        fewest = 1 << 30
        val, dom = self.val, self.dom
        for i in range(self.cells):
            if val[i] < 0:
                count = dom[i].bit_count()
                if count < fewest:
                    best, fewest = i, count
                    if count == 1:
                        break
        return best

    def _search(self, rng: random.Random) -> bool:
        i = self._select()
        if i < 0:
            return True
        for m in self._order(i, rng):
            if self.nodes >= self.node_limit:
                raise _OutOfNodes
            self.nodes += 1
            mark = len(self.trail)
            if self.assign(i, m) and self._search(rng):
                return True
            self.unassign(i, m, mark)
        return False

    def solve(self, rng: random.Random, max_nodes: int) -> list[int] | None:
        """Run attempts with growing node budgets until one succeeds or ``max_nodes`` are used in total.
        Returns the meal index of every cell (day-major), or ``None``."""
        used = 0
        budget = FIRST_ATTEMPT_NODES_PER_CELL * self.cells
        self.retry = False
        while used < max_nodes:
            self._reset()
            if not self._initial():
                return None  # infeasible before any choice: more attempts cannot help
            self.nodes = 0
            self.node_limit = min(budget, max_nodes - used)
            try:
                found = self._search(rng)
            except _OutOfNodes:
                found = False
            used += self.nodes
            if found:
                return list(self.val)
            if self.nodes < self.node_limit:
                return None  # the whole tree was searched: no solution under these rules
            budget = int(budget * ATTEMPT_GROWTH)
            self.retry = True
        return None
