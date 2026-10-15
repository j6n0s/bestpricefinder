"""suggest_plan on the REAL recipe library in data/ (loaded and validated with bpf.content), default rules.

The sweep: days 7, 14, 28 and 31, slots SLOTS_3 and SLOTS_5, 2 people, seeds 0-99 (800 plans). A plan passes
when every rule passes that the pool analysis does not prove impossible (each impossible rule has a warning,
see bpf/planner/search.py). At least 99 % of the plans must pass; with the library of 2026-10-13 all 800
pass and no rule is impossible. Every plan is also re-checked with check_plan.

If the content of data/ changes so that a weekly rule becomes impossible (for example the last fish recipe is
removed), ``test_real_library_supports_every_rule`` says which warning appeared.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import pytest

from bpf.content import load_ingredients, load_recipes
from bpf.content.paths import RECIPES_DIR
from bpf.planner import check_plan, suggest_plan
from bpf.pricing.model import SLOTS_3, SLOTS_5, Ingredient, Plan, PlanRequest, Recipe, Slot

SERVER_DIR = Path(__file__).resolve().parents[1]
SWEEP_DAYS = (7, 14, 28, 31)
SWEEP_SLOTS = (SLOTS_3, SLOTS_5)
SWEEP_SEEDS = range(100)
REQUIRED_PASS_RATE = 0.99

EXCUSED_BY: dict[str, str] = {
    "slot_pool_too_small": "variety",
    "no_fish_recipe_available": "fish",
    "no_legume_recipe_available": "legume",
    "no_meat_free_recipe_available": "meat_free_day",
    "no_potato_free_recipe_available": "potato",
    "red_meat_cap_unreachable": "red_meat",
    "budget_unreachable": "budget",
    "recipe_cost_missing": "budget",
}
"""Warning code (without its ``:<slot>`` part) -> the rule it proves impossible."""


def excused(plan: Plan) -> set[str]:
    return {EXCUSED_BY[code] for w in plan.warnings if (code := w.split(":", 1)[0]) in EXCUSED_BY}


def failing(plan: Plan) -> set[str]:
    return {c.rule for c in plan.checks if not c.ok}


Library = tuple[dict[str, Ingredient], list[Recipe]]


@pytest.fixture(scope="module")
def library() -> Library:
    ingredients = load_ingredients()
    recipes = load_recipes(RECIPES_DIR, ingredients)
    return ingredients, list(recipes.values())


def request(days: int, slots: tuple[Slot, ...], seed: int) -> PlanRequest:
    return PlanRequest(days=days, slots=slots, people=2, seed=seed)


def test_real_library_supports_every_rule(library: Library) -> None:
    """The pool analysis finds no impossible rule for any sweep request (a pass means every rule passes)."""
    ingredients, recipes = library
    for days in SWEEP_DAYS:
        for slots in SWEEP_SLOTS:
            plan = suggest_plan(recipes, ingredients, request(days, slots, 0))
            assert plan.warnings == (), (days, slots, plan.warnings)


def test_real_library_sweep_meets_every_satisfiable_rule(library: Library) -> None:
    ingredients, recipes = library
    by_id = {r.id: r for r in recipes}
    total = passed = all_ok = 0
    failures: Counter[str] = Counter()
    misses: list[tuple[int, int, int, list[str]]] = []
    slowest = 0.0
    start = time.perf_counter()
    for days in SWEEP_DAYS:
        for slots in SWEEP_SLOTS:
            for seed in SWEEP_SEEDS:
                began = time.perf_counter()
                plan = suggest_plan(recipes, ingredients, request(days, slots, seed))
                slowest = max(slowest, time.perf_counter() - began)
                assert plan.checks == check_plan(plan.days, by_id, ingredients, people=2)
                total += 1
                bad = failing(plan)
                failures.update(bad)
                all_ok += not bad
                if bad <= excused(plan):
                    passed += 1
                else:
                    misses.append((days, len(slots), seed, sorted(bad - excused(plan))))
    print(
        f"\nreal library sweep: {passed}/{total} plans pass every satisfiable rule, {all_ok}/{total} pass"
        f" every rule; failing rules {dict(failures)}; slowest plan {slowest * 1000:.1f} ms;"
        f" sweep {time.perf_counter() - start:.1f} s"
    )
    assert passed >= REQUIRED_PASS_RATE * total, misses[:20]


@pytest.mark.parametrize("slots", [SLOTS_3, SLOTS_5], ids=["3-slots", "5-slots"])
def test_real_library_31_days_under_200_ms(library: Library, slots: tuple[Slot, ...]) -> None:
    ingredients, recipes = library
    timings = []
    for seed in range(5):
        began = time.perf_counter()
        plan = suggest_plan(recipes, ingredients, request(31, slots, seed))
        timings.append(time.perf_counter() - began)
        assert len(plan.days) == 31
    print(
        f"\nreal library, 31 days x {len(slots)} slots: " + ", ".join(f"{t * 1000:.1f} ms" for t in timings)
    )
    assert max(timings) < 0.2, timings


def test_real_library_plan_is_reproducible(library: Library) -> None:
    ingredients, recipes = library
    req = request(31, SLOTS_5, 7)
    first = suggest_plan(recipes, ingredients, req)
    assert suggest_plan(recipes, ingredients, req) == first
    assert suggest_plan(list(reversed(recipes)), ingredients, req) == first  # input order does not matter
    assert (
        len({repr(suggest_plan(recipes, ingredients, request(14, SLOTS_3, s)).days) for s in range(10)}) == 10
    )


def test_real_library_plan_does_not_depend_on_string_hash_randomisation(library: Library) -> None:
    script = (
        "from bpf.content import load_ingredients, load_recipes\n"
        "from bpf.content.paths import RECIPES_DIR\n"
        "from bpf.planner import suggest_plan\n"
        "from bpf.pricing.model import PlanRequest, SLOTS_5\n"
        "ingredients = load_ingredients()\n"
        "recipes = list(load_recipes(RECIPES_DIR, ingredients).values())\n"
        "plan = suggest_plan(recipes, ingredients, PlanRequest(days=12, slots=SLOTS_5, people=3, seed=5))\n"
        "print(repr(plan))\n"
    )
    outputs: list[str] = []
    for hash_seed in ("0", "4242"):
        done = subprocess.run(
            [sys.executable, "-c", script],
            cwd=SERVER_DIR,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        outputs.append(done.stdout.strip())
    ingredients, recipes = library
    here = suggest_plan(recipes, ingredients, PlanRequest(days=12, slots=SLOTS_5, people=3, seed=5))
    assert outputs[0] == outputs[1] == repr(here)


def _used(plans: Sequence[Plan]) -> Counter[str]:
    return Counter(
        rid for plan in plans for day in plan.days for rid in day.meals.values() if rid is not None
    )


def test_real_library_plans_use_the_whole_main_pool(library: Library) -> None:
    """Leftover-aware grouping must not collapse the plans onto a few recipes: over 20 four-week plans every
    lunch/dinner recipe appears."""
    ingredients, recipes = library
    plans = [suggest_plan(recipes, ingredients, request(28, SLOTS_3, seed)) for seed in range(20)]
    mains = {r.id for r in recipes if "ebed" in r.slots or "vacsora" in r.slots}
    assert mains <= set(_used(plans))
