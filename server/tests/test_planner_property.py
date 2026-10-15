"""Property tests over random SYNTHETIC libraries and requests (tests/test_planner_synth.py).

For 200 seeds: the plan returned by suggest_plan is well-formed, its checks equal an independent re-check via
check_plan, and both agree with a deliberately naive oracle written here from the rule text (docs/ENGINE.md
plus the documented choices in bpf/planner/rules.py), which shares no code with the planner.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

import bpf.planner.search as search_module
from bpf.planner import check_plan, suggest_plan
from bpf.pricing.model import SLOTS_5, Ingredient, Plan, PlanDay, PlanRequest, Recipe
from tests.test_planner_synth import INGREDIENTS, by_id, random_costs, random_library, random_slots, seeded

MAIN = ("reggeli", "ebed", "vacsora")
RULE_ORDER = ("fish", "legume", "meat_free_day", "red_meat", "potato", "variety", "budget")


def _kg(qty: Decimal, ing: Ingredient) -> Fraction:
    factor = {"kg": Decimal(1), "db": ing.piece_weight_kg, "l": ing.density_kg_per_l}[ing.unit]
    assert factor is not None
    return Fraction(qty) * Fraction(factor)


def oracle(
    days: Sequence[PlanDay],
    recipes: Mapping[str, Recipe],
    ingredients: Mapping[str, Ingredient],
    *,
    people: int,
    cap: int,
    budget: Decimal | None,
    costs: Mapping[str, Decimal],
    window: int,
) -> dict[tuple[int, str], bool]:
    """Naive re-implementation of the weekly rules: (week, rule) -> ok."""
    plan = {d.index: {s: r for s, r in d.meals.items() if r is not None} for d in days}
    snack_window = min(2, window)

    def potato_day(day: int) -> bool:
        return day in plan and any(
            "potato" in ingredients[line.ingredient_id].tags
            for slot, rid in plan[day].items()
            if slot in MAIN
            for line in recipes[rid].lines
        )

    # variety: all (earlier, later) pairs of the same recipe, with greedy ket_napos pairing per slot
    occurrences: dict[str, list[tuple[int, int]]] = {}
    for day in sorted(plan):
        for slot in SLOTS_5:
            if slot in plan[day]:
                occurrences.setdefault(plan[day][slot], []).append((day, SLOTS_5.index(slot)))
    exempt: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for rid, occs in occurrences.items():
        if "ket_napos" not in recipes[rid].tags:
            continue
        for pos in range(5):
            slot_days = [d for d, p in occs if p == pos]
            i = 0
            while i < len(slot_days):
                if i + 1 < len(slot_days) and slot_days[i + 1] == slot_days[i] + 1:
                    exempt.add(((slot_days[i], pos), (slot_days[i + 1], pos)))
                    i += 2
                else:
                    i += 1
    repeats_by_week: dict[int, int] = {}
    for occs in occurrences.values():
        for b in occs:
            for a in occs:
                if a >= b:
                    continue
                both_main = SLOTS_5[a[1]] in MAIN and SLOTS_5[b[1]] in MAIN
                limit = window if both_main else snack_window
                if b[0] - a[0] < limit and (a, b) not in exempt:
                    repeats_by_week[b[0] // 7] = repeats_by_week.get(b[0] // 7, 0) + 1
                    break

    result: dict[tuple[int, str], bool] = {}
    for week in sorted({d // 7 for d in plan}):
        week_days = sorted(d for d in plan if d // 7 == week)
        week_meals = [rid for d in week_days for rid in plan[d].values()]
        long_block = len(week_days) >= 4
        result[(week, "fish")] = not long_block or any("hal" in recipes[r].tags for r in week_meals)
        result[(week, "legume")] = not long_block or any("huvelyes" in recipes[r].tags for r in week_meals)
        result[(week, "meat_free_day")] = not long_block or any(
            plan[d] and all("husmentes" in recipes[r].tags for r in plan[d].values()) for d in week_days
        )
        grams = sum(
            (
                _kg(line.qty, ingredients[line.ingredient_id]) * 1000 / recipes[r].servings
                for r in week_meals
                for line in recipes[r].lines
                if {"red_meat", "processed_meat"} & set(ingredients[line.ingredient_id].tags)
            ),
            Fraction(0),
        )
        result[(week, "red_meat")] = grams <= math.floor(Fraction(cap * len(week_days), 7))
        result[(week, "potato")] = not any(potato_day(d) and potato_day(d - 1) for d in week_days)
        result[(week, "variety")] = repeats_by_week.get(week, 0) == 0
        if budget is not None and costs:
            known = [costs[r] * people for r in week_meals if r in costs]
            limit = math.floor(Fraction(budget) * len(week_days) / 7)
            result[(week, "budget")] = len(known) == len(week_meals) and sum(known, Decimal(0)) <= limit
    return result


def random_request(rng: random.Random, recipes: Sequence[Recipe], *, no_repeat_days: int = 5) -> PlanRequest:
    ids = sorted(INGREDIENTS)
    budget = rng.choice((None, Decimal(rng.randint(0, 80000)), Decimal(rng.randint(0, 8000000)) / 100))
    return PlanRequest(
        days=rng.randint(1, 31),
        slots=random_slots(rng),
        people=rng.randint(1, 12),
        seed=rng.randint(0, 2**31 - 1),
        exclude_tags=frozenset(t for t in ("edes", "hal", "husmentes", "gyors") if rng.random() < 0.1),
        exclude_ingredients=frozenset(i for i in ids if rng.random() < 0.05),
        red_meat_g_per_person_week=rng.choice((0, 100, 350, 600, 3000)),
        no_repeat_days=no_repeat_days,
        weekly_budget=budget,
        recipe_cost_per_serving=rng.choice(({}, random_costs(rng, recipes))),
    )


def eligible(recipe: Recipe, req: PlanRequest, slot: str) -> bool:
    return (
        slot in recipe.slots
        and not req.exclude_tags & set(recipe.tags)
        and not any(
            not line.optional and line.ingredient_id in req.exclude_ingredients for line in recipe.lines
        )
    )


def assert_well_formed(plan: Plan, recipes: Sequence[Recipe], req: PlanRequest) -> None:
    lookup = by_id(recipes)
    assert [d.index for d in plan.days] == list(range(req.days))
    for slot in req.slots:
        pool = [r for r in recipes if eligible(r, req, slot)]
        assert (f"slot_pool_empty:{slot}" in plan.warnings) == (not pool)
        for day in plan.days:
            rid = day.meals[slot]
            if pool:
                assert rid is not None
                assert eligible(lookup[rid], req, slot)
            else:
                assert rid is None
    for day in plan.days:
        assert tuple(day.meals) == req.slots
    expected_rules = [
        r
        for r in RULE_ORDER
        if r != "budget" or (req.weekly_budget is not None and req.recipe_cost_per_serving)
    ]
    weeks = (req.days + 6) // 7
    assert [(c.week, c.rule) for c in plan.checks] == [(w, r) for w in range(weeks) for r in expected_rules]
    assert len(set(plan.warnings)) == len(plan.warnings)


def assert_matches_oracle(plan: Plan, recipes: Sequence[Recipe], req: PlanRequest) -> None:
    expected = oracle(
        plan.days,
        by_id(recipes),
        INGREDIENTS,
        people=req.people,
        cap=req.red_meat_g_per_person_week,
        budget=req.weekly_budget,
        costs=req.recipe_cost_per_serving,
        window=req.no_repeat_days,
    )
    assert {(c.week, c.rule): c.ok for c in plan.checks} == expected


@pytest.mark.parametrize("seed", range(200))
def test_plan_checks_match_independent_recheck(seed: int) -> None:
    rng = seeded(seed)
    recipes = random_library(rng)
    req = random_request(rng, recipes)  # the default 5-day window, which check_plan uses (contract v1)
    plan = suggest_plan(recipes, INGREDIENTS, req)
    assert_well_formed(plan, recipes, req)
    rechecked = check_plan(
        plan.days,
        by_id(recipes),
        INGREDIENTS,
        people=req.people,
        red_meat_g_per_person_week=req.red_meat_g_per_person_week,
        weekly_budget=req.weekly_budget,
        recipe_cost_per_serving=req.recipe_cost_per_serving,
    )
    assert rechecked == plan.checks
    assert_matches_oracle(plan, recipes, req)


@pytest.mark.parametrize("window", [0, 1, 2, 3, 7, 14])
@pytest.mark.parametrize("seed", range(15))
def test_plan_checks_match_oracle_for_other_windows(seed: int, window: int) -> None:
    rng = seeded(30_000 + seed)
    recipes = random_library(rng)
    req = random_request(rng, recipes, no_repeat_days=window)
    plan = suggest_plan(recipes, INGREDIENTS, req)
    assert_well_formed(plan, recipes, req)
    assert_matches_oracle(plan, recipes, req)


@pytest.mark.parametrize("seed", range(40))
def test_check_plan_matches_oracle_on_random_hand_made_plans(seed: int) -> None:
    rng = seeded(10_000 + seed)
    recipes = random_library(rng, max_recipes=12)  # may be empty: then every meal is None
    days = []
    for index in sorted(rng.sample(range(31), rng.randint(1, 31))):  # day indexes with gaps
        meals = {s: rng.choice([*(r.id for r in recipes), None]) for s in SLOTS_5 if rng.random() < 0.6}
        days.append(PlanDay(index=index, meals=meals))
    rng.shuffle(days)  # check_plan places days by index, not by position
    costs = random_costs(rng, recipes, share=0.9)
    budget = rng.choice((None, Decimal(rng.randint(0, 200000))))
    people = rng.randint(1, 12)
    cap = rng.choice((0, 300, 600))
    checks = check_plan(
        days,
        by_id(recipes),
        INGREDIENTS,
        people=people,
        red_meat_g_per_person_week=cap,
        weekly_budget=budget,
        recipe_cost_per_serving=costs,
    )
    expected = oracle(
        days, by_id(recipes), INGREDIENTS, people=people, cap=cap, budget=budget, costs=costs, window=5
    )
    assert {(c.week, c.rule): c.ok for c in checks} == expected


@pytest.mark.parametrize("seed", range(40))
def test_incremental_search_state_matches_a_fresh_rebuild(seed: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """After the search, the incrementally maintained totals equal totals rebuilt from the final grid, and the
    search's own score says "no violation" exactly when every returned check is ok."""
    states: list[search_module._Search] = []
    original = search_module.build_plan

    def spy(search: search_module._Search, *args: Any) -> None:
        original(search, *args)
        states.append(search)

    monkeypatch.setattr(search_module, "build_plan", spy)
    rng = seeded(20_000 + seed)
    recipes = random_library(rng)
    req = random_request(rng, recipes, no_repeat_days=seeded(seed).choice((0, 2, 5, 5, 7)))
    plan = suggest_plan(recipes, INGREDIENTS, req)
    (state,) = states
    fresh = search_module._Search(
        state.n, tuple(state.pools), state.pools, state.meals, state.lim, len(state.blocks[0].perish)
    )
    for day in range(state.n):
        for pos in fresh.active:
            fresh._set(day, pos, state.grid[day][pos])
    fresh.recompute()
    assert fresh.grid == state.grid
    assert fresh.total == state.total
    assert fresh.block_pen == state.block_pen
    assert fresh.repeats == state.repeats
    assert fresh.potato == state.potato
    for a, b in zip(fresh.blocks, state.blocks, strict=True):
        assert {k: getattr(a, k) for k in a.__slots__} == {k: getattr(b, k) for k in b.__slots__}
    assert (state.total < search_module.VIOLATION) == all(c.ok for c in plan.checks)
