"""Weekly plan rules: ``check_plan`` and the rule arithmetic the search shares with it.

Rules are evaluated per 7-day block (week ``w`` = day indexes ``7w .. 7w+6``), from public healthy-eating
principles (docs/ENGINE.md "bpf.planner"):

* ``fish`` / ``legume``: >= 1 meal with a ``hal`` / ``huvelyes`` recipe.
* ``meat_free_day``: >= 1 day with at least one meal where every meal is ``husmentes``.
  These three count rules apply only to blocks of at least 4 days; shorter blocks report ``ok`` / ``"n/a"``.
* ``red_meat``: raw grams of ``red_meat`` + ``processed_meat`` lines per person (line kg x 1000 / servings per
  meal; optional lines count, since they may be eaten) <= the cap pro rata to the block length, rounded down
  to whole grams: ``cap x days // 7``.
* ``potato``: no two consecutive days with a ``potato`` ingredient in a main meal (reggeli, ebed, vacsora).
  Runs are followed across block boundaries; a run is reported in the block where it continues.
* ``sweets``: <= 2 meals with an ``edes`` recipe.
* ``variety``: a recipe never repeats within ``no_repeat_days`` days (``day2 - day1 < window`` is a repeat,
  so a window of 1 forbids only same-day repeats and 0 disables the rule). Snacks (tizorai, uzsonna) may
  repeat more often: any pair that involves a snack slot uses ``min(2, no_repeat_days)``. Exception: a
  ``ket_napos`` recipe may fill the same slot on the very next day (cook once, eat twice): consecutive
  same-slot occurrences are paired greedily from the first day, so a third consecutive day is a new
  cooking and is checked normally. A repeat is reported in the block of its later occurrence.
* ``budget`` (only when a weekly budget AND a non-empty cost table are given): every meal in the block has a
  cost estimate (cost per serving x people) and their sum <= the budget pro rata to the block length,
  rounded down to whole forints: ``budget x days // 7``. A meal without an estimate fails the rule, since the
  week's cost cannot then be estimated.

All comparisons are exact (integers, ``Fraction`` or ``Decimal``; never ``float``). Displayed values are
rounded up and limits rounded down to whole units, and limits are whole numbers, so a displayed value is
within its displayed limit exactly when the check is ok.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Literal

from bpf.pricing.model import Ingredient, PlanDay, Recipe, RuleCheck

from .facts import (
    MAIN_POS,
    SLOT_POS,
    RecipeFacts,
    recipe_facts,
    validate_costs,
    validate_money,
    validate_non_negative_int,
    validate_people,
)

WEEK_DAYS = 7
COUNT_RULE_MIN_DAYS = 4
SWEETS_MAX = 2
SNACK_WINDOW_DAYS = 2
DEFAULT_NO_REPEAT_DAYS = 5
"""``check_plan`` has no window parameter (contract v1); it uses ``PlanRequest.no_repeat_days``'s default."""

NO_MEAL = -1
"""Grid cell without a meal (slot not planned, or no eligible recipe)."""

NOT_APPLICABLE = "n/a"


@dataclass(frozen=True, slots=True)
class Meal:
    """``RecipeFacts`` compiled to plain ints for fast, exact accumulation."""

    recipe_id: str
    fish: int
    legume: int
    sweet: int
    meat_free: bool
    two_day: bool
    potato: bool
    red_units: int  # red_meat_g x Limits.red_den, exact
    cost: Decimal | None
    perish_bits: tuple[int, ...]


def compile_meals(
    facts: Sequence[RecipeFacts], perish_bit: Mapping[str, int] | None = None
) -> tuple[tuple[Meal, ...], int]:
    """Compile facts with a common denominator for red meat grams. Returns ``(meals, red_den)``."""
    red_den = math.lcm(1, *(f.red_meat_g.denominator for f in facts))
    bits = perish_bit or {}
    meals = tuple(
        Meal(
            recipe_id=f.recipe_id,
            fish=int(f.fish),
            legume=int(f.legume),
            sweet=int(f.sweet),
            meat_free=f.meat_free,
            two_day=f.two_day,
            potato=f.potato,
            red_units=f.red_meat_g.numerator * (red_den // f.red_meat_g.denominator),
            cost=f.cost,
            perish_bits=tuple(bits[i] for i in f.perishables if i in bits),
        )
        for f in facts
    )
    return meals, red_den


@dataclass(frozen=True, slots=True)
class Limits:
    red_cap_g: int  # per person per 7 days
    red_den: int  # denominator of Meal.red_units
    budget: Decimal | None  # per 7 days; None = budget rule not evaluated
    main_window: int  # no-repeat window for pairs of main meals, in days
    snack_window: int  # no-repeat window for pairs that involve a snack slot

    def red_limit_g(self, days: int) -> int:
        return self.red_cap_g * days // WEEK_DAYS

    def budget_limit(self, days: int) -> Decimal:
        if self.budget is None:
            raise ValueError("no budget")
        return (self.budget * days) // WEEK_DAYS


def make_limits(red_cap_g: int, red_den: int, budget: Decimal | None, no_repeat_days: int) -> Limits:
    return Limits(
        red_cap_g=red_cap_g,
        red_den=red_den,
        budget=budget,
        main_window=no_repeat_days,
        snack_window=min(SNACK_WINDOW_DAYS, no_repeat_days),
    )


class BlockTotals:
    """Running totals of one 7-day block. ``add`` with sign -1 exactly undoes sign +1."""

    __slots__ = (
        "cost", "day_meals", "day_meaty", "days", "fish", "free_days", "legume", "meals",
        "perish", "perish_distinct", "red", "sweets", "unpriced",
    )

    def __init__(self, days: int, n_perish_bits: int = 0) -> None:
        self.days = days  # plan days in this block (1..7)
        self.meals = 0
        self.fish = 0
        self.legume = 0
        self.sweets = 0
        self.red = 0
        self.cost = Decimal(0)
        self.unpriced = 0
        self.day_meals = [0] * WEEK_DAYS
        self.day_meaty = [0] * WEEK_DAYS  # meals that are not husmentes, per day offset
        self.free_days = 0
        self.perish = [0] * n_perish_bits
        self.perish_distinct = 0

    def add(self, offset: int, meal: Meal, sign: int) -> None:
        was_free = self.day_meals[offset] > 0 and self.day_meaty[offset] == 0
        self.day_meals[offset] += sign
        if not meal.meat_free:
            self.day_meaty[offset] += sign
        is_free = self.day_meals[offset] > 0 and self.day_meaty[offset] == 0
        self.free_days += int(is_free) - int(was_free)
        self.meals += sign
        self.fish += sign * meal.fish
        self.legume += sign * meal.legume
        self.sweets += sign * meal.sweet
        self.red += sign * meal.red_units
        if meal.cost is None:
            self.unpriced += sign
        elif sign > 0:
            self.cost += meal.cost
        else:
            self.cost -= meal.cost
        perish = self.perish
        for bit in meal.perish_bits:
            count = perish[bit] + sign
            perish[bit] = count
            if sign > 0 and count == 1:
                self.perish_distinct += 1
            elif sign < 0 and count == 0:
                self.perish_distinct -= 1


# ───────────────────────────── shared predicates ─────────────────────────────


def count_rules_apply(t: BlockTotals) -> bool:
    return t.days >= COUNT_RULE_MIN_DAYS


def red_ok(t: BlockTotals, lim: Limits) -> bool:
    return t.red <= lim.red_limit_g(t.days) * lim.red_den


def budget_ok(t: BlockTotals, lim: Limits) -> bool:
    return lim.budget is None or (t.unpriced == 0 and t.cost <= lim.budget_limit(t.days))


def block_failures(t: BlockTotals, lim: Limits) -> list[str]:
    """Names of the block-local rules (all but potato and variety) that fail, in RuleCheck order."""
    failed: list[str] = []
    if count_rules_apply(t):
        if t.fish == 0:
            failed.append("fish")
        if t.legume == 0:
            failed.append("legume")
        if t.free_days == 0:
            failed.append("meat_free_day")
    if not red_ok(t, lim):
        failed.append("red_meat")
    if t.sweets > SWEETS_MAX:
        failed.append("sweets")
    if not budget_ok(t, lim):
        failed.append("budget")
    return failed


def repeat_flags(
    occurrences: Sequence[tuple[int, int]], two_day: bool, main_window: int, snack_window: int
) -> list[bool]:
    """For one recipe's occurrences ``(day, slot position)``, sorted ascending, flag each occurrence that
    repeats an earlier one inside the no-repeat window (see the module docstring)."""
    partner: dict[int, int] = {}  # second-day occurrence -> its cooking-day occurrence (ket_napos)
    if two_day:
        index = {occ: i for i, occ in enumerate(occurrences)}
        for i, (day, pos) in enumerate(occurrences):
            j = index.get((day - 1, pos))
            if j is not None and j not in partner:  # j is a cooking day, not itself a second day
                partner[i] = j
    widest = max(main_window, snack_window)
    flags: list[bool] = []
    for i, (day, pos) in enumerate(occurrences):
        hit = False
        for j in range(i - 1, -1, -1):
            day0, pos0 = occurrences[j]
            gap = day - day0
            if gap >= widest:
                break
            window = main_window if pos in MAIN_POS and pos0 in MAIN_POS else snack_window
            if gap < window and partner.get(i) != j:
                hit = True
                break
        flags.append(hit)
    return flags


# ───────────────────────────── evaluation ─────────────────────────────


def evaluate(
    grid: Mapping[int, Sequence[int]], snack_weeks: frozenset[int], meals: Sequence[Meal], lim: Limits
) -> tuple[RuleCheck, ...]:
    """Rule checks for ``grid`` (day index -> 5 meal indexes in ``SLOTS_5`` order, ``NO_MEAL`` when empty).

    ``snack_weeks``: weeks where some day plans a snack slot (only changes the variety limit text)."""
    day_ids = sorted(grid)
    week_days: dict[int, int] = {}
    for day in day_ids:
        week_days[day // WEEK_DAYS] = week_days.get(day // WEEK_DAYS, 0) + 1
    totals = {week: BlockTotals(count) for week, count in week_days.items()}
    occurrences: dict[int, list[tuple[int, int]]] = {}
    potato_run = dict.fromkeys(week_days, 0)
    run_by_day: dict[int, int] = {}
    for day in day_ids:
        row = grid[day]
        block = totals[day // WEEK_DAYS]
        potato = False
        for pos, m in enumerate(row):
            if m == NO_MEAL:
                continue
            meal = meals[m]
            block.add(day % WEEK_DAYS, meal, 1)
            occurrences.setdefault(m, []).append((day, pos))
            potato = potato or (meal.potato and pos in MAIN_POS)
        run = run_by_day.get(day - 1, 0) + 1 if potato else 0
        run_by_day[day] = run
        potato_run[day // WEEK_DAYS] = max(potato_run[day // WEEK_DAYS], run)
    repeats = dict.fromkeys(week_days, 0)
    for m, occs in occurrences.items():  # occs are ascending: days ascending, slot positions ascending
        for (day, _pos), hit in zip(occs, repeat_flags(occs, meals[m].two_day, lim.main_window,
                                                       lim.snack_window), strict=True):
            if hit:
                repeats[day // WEEK_DAYS] += 1
    checks: list[RuleCheck] = []
    for week in sorted(week_days):
        checks.extend(
            week_checks(week, totals[week], repeats[week], potato_run[week], week in snack_weeks, lim)
        )
    return tuple(checks)


def _count_check(
    week: int, rule: Literal["fish", "legume", "meat_free_day"], count: int, noun: str, applies: bool
) -> RuleCheck:
    if not applies:
        return RuleCheck(week=week, rule=rule, ok=True, value=NOT_APPLICABLE, limit="≥ 1")
    return RuleCheck(week=week, rule=rule, ok=count >= 1, value=f"{count} {noun}", limit="≥ 1")


def week_checks(
    week: int, t: BlockTotals, repeats: int, potato_run: int, has_snacks: bool, lim: Limits
) -> list[RuleCheck]:
    applies = count_rules_apply(t)
    variety_limit = f"0 ismétlés {lim.main_window} napon belül"
    if has_snacks:
        variety_limit += f", tízórai/uzsonna {lim.snack_window} napon belül"
    checks = [
        _count_check(week, "fish", t.fish, "hal", applies),
        _count_check(week, "legume", t.legume, "hüvelyes", applies),
        _count_check(week, "meat_free_day", t.free_days, "húsmentes nap", applies),
        RuleCheck(
            week=week, rule="red_meat", ok=red_ok(t, lim),
            value=f"{math.ceil(Fraction(t.red, lim.red_den))} g/fő", limit=f"≤ {lim.red_limit_g(t.days)} g/fő",
        ),
        RuleCheck(
            week=week, rule="potato", ok=potato_run <= 1,
            value=f"{potato_run} nap egymás után", limit="≤ 1 nap egymás után",
        ),
        RuleCheck(week=week, rule="sweets", ok=t.sweets <= SWEETS_MAX, value=f"{t.sweets} édes",
                  limit=f"≤ {SWEETS_MAX}"),
        RuleCheck(week=week, rule="variety", ok=repeats == 0, value=f"{repeats} ismétlés", limit=variety_limit),
    ]
    if lim.budget is not None:
        value = f"{math.ceil(t.cost)} Ft"
        if t.unpriced:
            value += f" + {t.unpriced} ár nélküli étel"
        checks.append(
            RuleCheck(week=week, rule="budget", ok=budget_ok(t, lim), value=value,
                      limit=f"≤ {int(lim.budget_limit(t.days))} Ft")
        )
    return checks


# ───────────────────────────── public: check_plan ─────────────────────────────


def check_plan(
    days: Sequence[PlanDay],
    recipes: Mapping[str, Recipe],
    ingredients: Mapping[str, Ingredient],
    *,
    people: int,
    red_meat_g_per_person_week: int = 600,
    weekly_budget: Decimal | None = None,
    recipe_cost_per_serving: Mapping[str, Decimal] | None = None,
) -> tuple[RuleCheck, ...]:
    """Check a (possibly hand-edited) plan against the weekly rules; see the module docstring.

    Days are placed by ``PlanDay.index`` (week = index // 7; days may be unsorted or have gaps; a block's
    length is the number of days given in it). The variety window is ``DEFAULT_NO_REPEAT_DAYS``.
    Raises ``KeyError`` for an unknown recipe or ingredient id and ``ValueError`` for duplicate or negative
    day indexes, unknown slots or invalid parameters."""
    validate_people(people)
    red_cap = validate_non_negative_int(red_meat_g_per_person_week, "red_meat_g_per_person_week")
    budget = None if weekly_budget is None else validate_money(weekly_budget, "weekly_budget")
    costs = validate_costs(recipe_cost_per_serving)
    index: dict[str, int] = {}
    grid: dict[int, list[int]] = {}
    snack_weeks: set[int] = set()
    for plan_day in days:
        day = plan_day.index
        if isinstance(day, bool) or not isinstance(day, int) or day < 0:
            raise ValueError(f"day index must be an int >= 0, got {day!r}")
        if day in grid:
            raise ValueError(f"duplicate day index {day}")
        row = [NO_MEAL] * len(SLOT_POS)
        for slot, recipe_id in plan_day.meals.items():
            pos = SLOT_POS.get(slot)
            if pos is None:
                raise ValueError(f"unknown slot {slot!r}")
            if pos not in MAIN_POS:
                snack_weeks.add(day // WEEK_DAYS)
            if recipe_id is None:
                continue
            if recipe_id not in index:
                if recipe_id not in recipes:
                    raise KeyError(f"unknown recipe id {recipe_id!r}")
                index[recipe_id] = len(index)
            row[pos] = index[recipe_id]
        grid[day] = row
    facts = [recipe_facts(recipes[rid], ingredients, people=people, costs=costs) for rid in index]
    meals, red_den = compile_meals(facts)
    lim = make_limits(red_cap, red_den, budget if costs else None, DEFAULT_NO_REPEAT_DAYS)
    return evaluate(grid, frozenset(snack_weeks), meals, lim)
