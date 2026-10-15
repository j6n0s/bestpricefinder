"""suggest_plan on tight SYNTHETIC libraries (tests/test_planner_synth.py builders; nothing in data/ is read).

"M0-sized" = ``rich_library(lib_seed, mains=16, breakfasts=6, snacks=6)``: slot pools only just large enough
for the 5-day no-repeat window, the size of the first real library milestone. On these the planner used to
miss plans that meet every rule. Now, for lib_seed 0-5, SLOTS_5 x 7 days, SLOTS_5 x 31 days and SLOTS_3 x 31
days, seeds 0-11: every plan meets every rule, with no warning (libs 1 and 5, whose snacks are half sweet,
used to give up snack variety for the sweets cap, removed on 2026-10-15). Where the pool analysis proves a
rule impossible (the potato-heavy library below), the proof is checked by exhausting the search on the
sub-problem, and each rule alone is shown satisfiable.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from bpf.planner import suggest_plan
from bpf.planner.construct import Construct
from bpf.pricing.model import SLOTS_3, SLOTS_5, Plan, PlanRequest, Recipe, Slot
from tests.test_planner_construct import Setup, setup
from tests.test_planner_real import excused, failing
from tests.test_planner_synth import INGREDIENTS, rich_library, seeded

M0_CONFIGS: list[tuple[tuple[Slot, ...], int]] = [(SLOTS_5, 7), (SLOTS_5, 31), (SLOTS_3, 31)]
M0_SEEDS = range(12)
BLOCK_RULES = frozenset({"fish", "legume", "meat_free_day", "red_meat", "budget"})
UNLIMITED = 10**7


def m0_library(lib_seed: int) -> list[Recipe]:
    return rich_library(lib_seed, mains=16, breakfasts=6, snacks=6)


def plan_for(recipes: Sequence[Recipe], slots: tuple[Slot, ...], days: int, seed: int) -> Plan:
    return suggest_plan(recipes, INGREDIENTS, PlanRequest(days=days, slots=slots, people=2, seed=seed))


@pytest.mark.parametrize(("slots", "days"), M0_CONFIGS, ids=["5x7", "5x31", "3x31"])
@pytest.mark.parametrize("lib_seed", range(6))
def test_m0_library_meets_every_satisfiable_rule(lib_seed: int, slots: tuple[Slot, ...], days: int) -> None:
    lib = m0_library(lib_seed)
    for seed in M0_SEEDS:
        plan = plan_for(lib, slots, days, seed)
        assert plan.warnings == (), seed
        assert failing(plan) <= excused(plan), (seed, [c for c in plan.checks if not c.ok])


def prove(
    recipes: Sequence[Recipe], slots: tuple[Slot, ...], days: int, rules: frozenset[str]
) -> tuple[bool, Setup]:
    """Exhaust the search for a plan of ``slots`` that meets ``rules`` only (every other rule is dropped).
    Returns (a plan exists, the setup)."""
    s = setup(recipes, PlanRequest(days=days, slots=slots, people=2, seed=0))
    builder = Construct(
        days,
        s.active,
        s.pools,
        s.meals,
        s.lim,
        hopeless=[BLOCK_RULES - rules] * ((days + 6) // 7),
        relaxed=frozenset() if "variety" in rules else frozenset(s.active),
        enforce_potato="potato" in rules,
    )
    found = builder.solve(seeded(0), UNLIMITED)
    assert builder.nodes < UNLIMITED  # a complete search, not a budget cut
    return found is not None, s


# 12 mains, 5 breakfasts and 5 snacks (lib_seed 8): 7 of the 12 lunch/dinner recipes contain potato. With no
# two potato days in a row, some 5-day window has 3 potato-free days, i.e. 6 lunch/dinner cells for the 5
# potato-free recipes: variety and the potato rule cannot both hold.
POTATO_HEAVY = {"mains": 12, "breakfasts": 5, "snacks": 5}
POTATO_HEAVY_SEED = 8


def test_potato_heavy_library_cannot_keep_variety_and_the_potato_rule() -> None:
    lib = rich_library(POTATO_HEAVY_SEED, **POTATO_HEAVY)
    mains: tuple[Slot, ...] = ("ebed", "vacsora")
    exists, s = prove(lib, mains, 7, frozenset({"variety", "potato"}))
    assert not exists
    assert s.too_small_warnings() == ("slot_pool_too_small:ebed", "slot_pool_too_small:vacsora")
    assert prove(lib, mains, 7, frozenset({"variety"}))[0]
    assert prove(lib, mains, 7, frozenset({"potato"}))[0]


@pytest.mark.parametrize(
    ("slots", "days"), [(SLOTS_3, 7), (SLOTS_3, 31), (SLOTS_5, 31)], ids=["3x7", "3x31", "5x31"]
)
def test_potato_heavy_library_keeps_the_potato_rule(slots: tuple[Slot, ...], days: int) -> None:
    lib = rich_library(POTATO_HEAVY_SEED, **POTATO_HEAVY)
    for seed in range(4):
        plan = plan_for(lib, slots, days, seed)
        assert {"slot_pool_too_small:ebed", "slot_pool_too_small:vacsora"} <= set(plan.warnings)
        assert failing(plan) <= excused(plan), (seed, [c for c in plan.checks if not c.ok])
        assert "potato" not in failing(plan)


@pytest.mark.parametrize("lib_seed", range(20))
def test_smaller_libraries_meet_every_satisfiable_rule(lib_seed: int) -> None:
    """Tighter than M0 (12 mains, 5 breakfasts, 5 snacks): breakfasts and snacks must rotate strictly."""
    lib = rich_library(lib_seed, **POTATO_HEAVY)
    for slots, days in ((SLOTS_5, 7), (SLOTS_3, 31)):
        plan = plan_for(lib, slots, days, lib_seed)
        assert failing(plan) <= excused(plan), (slots, days, [c for c in plan.checks if not c.ok])
