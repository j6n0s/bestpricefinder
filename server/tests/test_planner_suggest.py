"""suggest_plan on SYNTHETIC recipe libraries (see tests/test_planner_synth.py): determinism, rules,
warnings, exclusions, leftover-aware grouping, budget, timing and termination."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from bpf.planner import check_plan, suggest_plan
from bpf.pricing.model import SLOTS_3, SLOTS_5, Ingredient, Plan, PlanRequest, Recipe, RuleCheck, Slot
from tests.test_planner_synth import INGREDIENTS, by_id, recipe, rich_library, seeded

LIB = rich_library()
SERVER_DIR = Path(__file__).resolve().parents[1]


def request(**kwargs: object) -> PlanRequest:
    base: dict[str, object] = {"days": 7, "slots": SLOTS_3, "people": 2, "seed": 0}
    base.update(kwargs)
    return PlanRequest(**base)  # type: ignore[arg-type]


def suggest(
    recipes: Sequence[Recipe] = LIB, ingredients: Mapping[str, Ingredient] = INGREDIENTS, **kwargs: object
) -> Plan:
    return suggest_plan(recipes, ingredients, request(**kwargs))


def recheck(
    plan: Plan,
    recipes: Iterable[Recipe],
    req: PlanRequest,
    ingredients: Mapping[str, Ingredient] = INGREDIENTS,
) -> tuple[RuleCheck, ...]:
    return check_plan(
        plan.days,
        by_id(recipes),
        ingredients,
        people=req.people,
        red_meat_g_per_person_week=req.red_meat_g_per_person_week,
        weekly_budget=req.weekly_budget,
        recipe_cost_per_serving=req.recipe_cost_per_serving,
    )


def failing(plan: Plan) -> set[str]:
    return {c.rule for c in plan.checks if not c.ok}


def meals(plan: Plan) -> list[str]:
    return [rid for day in plan.days for rid in day.meals.values() if rid is not None]


def cheap_costs(recipes: Iterable[Recipe]) -> dict[str, Decimal]:
    """Synthetic costs: every second recipe (by id) costs 100 Ft per serving, the others 5000 Ft."""
    return {
        r.id: Decimal(100 if i % 2 == 0 else 5000) for i, r in enumerate(sorted(recipes, key=lambda r: r.id))
    }


# ───────────────────────────── determinism ─────────────────────────────


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {
            "days": 31,
            "slots": SLOTS_5,
            "seed": 7,
            "weekly_budget": Decimal(40000),
            "recipe_cost_per_serving": cheap_costs(LIB),
        },
    ],
    ids=["7x3", "31x5-budget"],
)
def test_same_seed_and_input_give_identical_plan(kwargs: dict[str, object]) -> None:
    assert suggest(**kwargs) == suggest(**kwargs)


def test_recipe_input_order_does_not_matter() -> None:
    shuffled = list(LIB)
    seeded(3).shuffle(shuffled)
    assert suggest(shuffled, slots=SLOTS_5, days=14, seed=5) == suggest(LIB, slots=SLOTS_5, days=14, seed=5)


def test_plan_does_not_depend_on_string_hash_randomisation() -> None:
    script = (
        "from bpf.planner import suggest_plan\n"
        "from bpf.pricing.model import PlanRequest, SLOTS_5\n"
        "from tests.test_planner_synth import INGREDIENTS, rich_library\n"
        "request = PlanRequest(days=10, slots=SLOTS_5, people=3, seed=11,"
        " exclude_ingredients=frozenset({'virsli', 'turo'}))\n"
        "print(repr(suggest_plan(rich_library(), INGREDIENTS, request)))\n"
    )
    outputs = []
    for hash_seed in ("0", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        done = subprocess.run(
            [sys.executable, "-c", script],
            cwd=SERVER_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        outputs.append(done.stdout.strip())
    here = suggest(
        days=10, slots=SLOTS_5, people=3, seed=11, exclude_ingredients=frozenset({"virsli", "turo"})
    )
    assert outputs[0] == outputs[1] == repr(here)


def test_different_seeds_usually_give_different_plans() -> None:
    plans = {repr(suggest(seed=seed).days) for seed in range(20)}
    assert len(plans) >= 18


# ───────────────────────────── shape ─────────────────────────────


@pytest.mark.parametrize(("days", "slots"), [(1, SLOTS_3), (10, SLOTS_5), (31, ("reggeli", "vacsora"))])
def test_plan_shape(days: int, slots: tuple[Slot, ...]) -> None:
    plan = suggest(days=days, slots=slots)
    assert [day.index for day in plan.days] == list(range(days))
    for day in plan.days:
        assert tuple(day.meals) == slots
        for slot, rid in day.meals.items():
            assert rid is not None
            assert slot in by_id(LIB)[rid].slots
    weeks = (days + 6) // 7
    assert [c.week for c in plan.checks] == [w for w in range(weeks) for _ in range(7)]


def test_checks_equal_an_independent_check_plan() -> None:
    req = request(
        days=12, slots=SLOTS_5, seed=4, weekly_budget=Decimal(30000), recipe_cost_per_serving=cheap_costs(LIB)
    )
    plan = suggest_plan(LIB, INGREDIENTS, req)
    assert plan.checks == recheck(plan, LIB, req)


# ───────────────────────────── rules satisfied when possible ─────────────────────────────


@pytest.mark.parametrize(
    ("slots", "days"), [(SLOTS_3, 7), (SLOTS_5, 7), (SLOTS_3, 31), (SLOTS_5, 31), (SLOTS_5, 10)]
)
@pytest.mark.parametrize("seed", range(4))
def test_rich_library_meets_every_rule(slots: tuple[Slot, ...], days: int, seed: int) -> None:
    plan = suggest(slots=slots, days=days, seed=seed)
    assert failing(plan) == set()
    assert plan.warnings == ()


def test_lower_red_meat_cap_is_met_pro_rata() -> None:
    plan = suggest(days=10, slots=SLOTS_5, red_meat_g_per_person_week=150, seed=2)
    assert failing(plan) == set()
    reds = [c for c in plan.checks if c.rule == "red_meat"]
    assert [c.limit for c in reds] == ["≤ 150 g/fő", "≤ 64 g/fő"]


def test_two_day_recipes_are_paired_when_variety_needs_it() -> None:
    lib = [
        recipe("hal-2", ("ebed",), [("hal", "0.5"), ("rizs", "0.3")], extra_tags=["ket_napos"]),
        recipe("lencse-2", ("ebed",), [("lencse", "0.4")], extra_tags=["ket_napos"]),
        recipe("kaposzta-2", ("ebed",), [("kaposzta", "1"), ("teszta", "0.3")], extra_tags=["ket_napos"]),
    ]
    for seed in range(5):
        plan = suggest(lib, slots=("ebed",), days=7, seed=seed)
        assert failing(plan) == set(), plan
        assert plan.warnings == ()
        ids = meals(plan)
        assert any(a == b for a, b in zip(ids, ids[1:], strict=False))  # cook once, eat twice


def test_two_day_recipes_still_too_few() -> None:
    lib = [
        recipe("lencse-2", ("ebed",), [("lencse", "0.4")], extra_tags=["ket_napos"]),
        recipe("kaposzta-2", ("ebed",), [("kaposzta", "1")], extra_tags=["ket_napos"]),
    ]
    plan = suggest(lib, slots=("ebed",), days=7)
    assert "slot_pool_too_small:ebed" in plan.warnings
    assert "variety" in failing(plan)


def test_snacks_may_alternate_two_recipes() -> None:
    snacks = [
        recipe("alma", ("uzsonna",), [("alma", "0.3")]),
        recipe("banan", ("uzsonna",), [("banan", "0.3")]),
    ]
    plan = suggest(LIB + snacks, slots=("ebed", "uzsonna", "vacsora"), days=14, seed=1)
    assert failing(plan) == set()
    assert plan.warnings == ()


def test_a_single_snack_recipe_is_too_few_but_main_slots_are_unaffected() -> None:
    snacks = [recipe("alma", ("uzsonna",), [("alma", "0.3")])]
    plan = suggest(
        [r for r in LIB if "uzsonna" not in r.slots] + snacks, slots=("ebed", "uzsonna", "vacsora")
    )
    assert plan.warnings == ("slot_pool_too_small:uzsonna",)
    assert failing(plan) == {"variety"}
    assert [c.value for c in plan.checks if c.rule == "variety"] == ["6 ismétlés"]


def test_no_repeat_days_zero_allows_any_repeat() -> None:
    lib = [recipe("csak-ez", ("ebed",), [("lencse", "0.4"), ("hal", "0.2")])]
    plan = suggest(lib, slots=("ebed",), no_repeat_days=0)
    assert failing(plan) == {"meat_free_day"}
    assert plan.warnings == ("no_meat_free_recipe_available:ebed",)


# ───────────────────────────── impossible rules: failing check + warning ─────────────────────────────


RED_MEAT_LUNCHES = [
    r
    for r in LIB
    if "ebed" in r.slots and any("red_meat" in INGREDIENTS[line.ingredient_id].tags for line in r.lines)
]


@pytest.mark.parametrize(
    ("recipes", "kwargs", "rule", "warning"),
    [
        (LIB, {"exclude_tags": frozenset({"hal"})}, "fish", "no_fish_recipe_available"),
        (LIB, {"exclude_ingredients": frozenset({"lencse"})}, "legume", "no_legume_recipe_available"),
        (
            RED_MEAT_LUNCHES,
            {"red_meat_g_per_person_week": 0, "slots": ("ebed",)},
            "red_meat",
            "red_meat_cap_unreachable",
        ),
    ],
    ids=["fish", "legume", "red-meat"],
)
def test_impossible_rule_fails_with_warning(
    recipes: list[Recipe], kwargs: dict[str, object], rule: str, warning: str
) -> None:
    plan = suggest(recipes, **kwargs)
    assert warning in plan.warnings
    assert rule in failing(plan)


def test_fish_impossible_other_rules_still_met() -> None:
    plan = suggest(exclude_tags=frozenset({"hal"}), days=14, slots=SLOTS_5)
    assert plan.warnings == ("no_fish_recipe_available",)
    assert failing(plan) == {"fish"}
    assert not any(by_id(LIB)[rid].tags.count("hal") for rid in meals(plan))


def test_meat_free_day_impossible() -> None:
    meaty_breakfasts = [r for r in LIB if r.slots == ("reggeli",) and "husmentes" not in r.tags]
    assert meaty_breakfasts
    lib = (
        [r for r in LIB if r.slots != ("reggeli",)]
        + meaty_breakfasts[:1]
        + [recipe(f"virslis-{i}", ("reggeli",), [("kenyer", "0.2"), ("virsli", "2")]) for i in range(6)]
    )
    plan = suggest(lib, slots=SLOTS_3, red_meat_g_per_person_week=3000)
    assert plan.warnings == ("no_meat_free_recipe_available:reggeli",)
    assert failing(plan) == {"meat_free_day"}


def test_potato_impossible() -> None:
    lib = (
        [r for r in LIB if "ebed" not in r.slots]
        + [
            recipe(f"krumpli-{i}", ("ebed",), [("burgonya", "1"), ("lencse" if i == 0 else "tejfol", "0.2")])
            for i in range(6)
        ]
        + [recipe("hal-vacsora", ("vacsora",), [("hal", "0.5")])]
    )
    plan = suggest(lib, slots=("ebed", "vacsora"))
    assert plan.warnings == ("no_potato_free_recipe_available:ebed",)
    assert failing(plan) == {"potato"}


def test_sweets_impossible() -> None:
    sweets = [
        recipe(f"edes-{i}", ("uzsonna",), [("cukor", "0.1"), ("alma", "0.2")], extra_tags=["edes"])
        for i in range(4)
    ]
    lib = [r for r in LIB if "uzsonna" not in r.slots] + sweets
    plan = suggest(lib, slots=("ebed", "uzsonna", "vacsora"))
    assert plan.warnings == ("sweets_cap_unreachable",)
    assert failing(plan) == {"sweets"}
    assert [c.value for c in plan.checks if c.rule == "sweets"] == ["7 édes"]


def test_sweets_kept_to_two_when_possible() -> None:
    sweets = [
        recipe(f"edes-{i}", ("uzsonna",), [("cukor", "0.1"), ("alma", "0.2")], extra_tags=["edes"])
        for i in range(10)
    ]
    plain = [recipe(f"sima-{i}", ("uzsonna",), [("alma", "0.2"), ("joghurt", "0.1")]) for i in range(3)]
    lib = [r for r in LIB if "uzsonna" not in r.slots] + sweets + plain
    plan = suggest(lib, slots=("ebed", "uzsonna", "vacsora"), days=14, seed=3)
    assert failing(plan) == set()
    assert all(int(c.value.split()[0]) <= 2 for c in plan.checks if c.rule == "sweets")


# ───────────────────────────── pools, exclusions ─────────────────────────────


def test_empty_slot_pool_gives_none_meals_and_warning() -> None:
    lib = [replace(r, slots=("uzsonna",)) if "tizorai" in r.slots else r for r in LIB]
    plan = suggest(lib, slots=SLOTS_5, days=7)
    assert plan.warnings == ("slot_pool_empty:tizorai",)
    assert all(day.meals["tizorai"] is None for day in plan.days)
    assert all(
        day.meals[slot] is not None for day in plan.days for slot in ("reggeli", "ebed", "uzsonna", "vacsora")
    )
    assert failing(plan) == set()


def test_shared_pool_too_small_for_two_slots() -> None:
    # five recipes for both ebed and vacsora: each slot alone could rotate them, together they cannot
    lib = [r for r in LIB if "ebed" not in r.slots and "vacsora" not in r.slots] + [
        recipe(f"fo-{i}", ("ebed", "vacsora"), [(p, "0.4")])
        for i, p in enumerate(("hal", "lencse", "tejfol", "kaposzta", "rizs"))
    ]
    plan = suggest(lib, slots=SLOTS_3)
    assert plan.warnings == ("slot_pool_too_small:ebed", "slot_pool_too_small:vacsora")
    assert "variety" in failing(plan)


def test_exclusion_by_tag() -> None:
    plan = suggest(exclude_tags=frozenset({"edes"}), slots=SLOTS_5, days=14)
    assert meals(plan)
    assert not any("edes" in by_id(LIB)[rid].tags for rid in meals(plan))


def test_exclusion_by_ingredient_ignores_optional_lines() -> None:
    with_optional = recipe("turo-opcio", ("uzsonna",), [("alma", "0.2"), ("turo", "0.1")], optional=["turo"])
    with_required = recipe("turo-kell", ("uzsonna",), [("banan", "0.2"), ("turo", "0.1")])
    lib = [r for r in LIB if "uzsonna" not in r.slots] + [with_optional, with_required]
    plan = suggest(lib, slots=("ebed", "uzsonna"), days=7, exclude_ingredients=frozenset({"turo", "virsli"}))
    used = meals(plan)
    assert "turo-opcio" in used
    assert "turo-kell" not in used
    for rid in used:
        assert not any(
            line.ingredient_id in ("turo", "virsli") and not line.optional for line in by_id(lib)[rid].lines
        )
    assert plan.warnings == ("slot_pool_too_small:uzsonna",)


def test_everything_excluded_gives_empty_plan_with_warnings() -> None:
    plan = suggest(
        exclude_tags=frozenset({"husmentes", "hal", "huvelyes"}),
        exclude_ingredients=frozenset({"marha", "sertes", "csirke", "virsli", "tojas"}),
        slots=SLOTS_3,
    )
    assert meals(plan) == []
    assert plan.warnings == (
        "slot_pool_empty:reggeli",
        "slot_pool_empty:ebed",
        "slot_pool_empty:vacsora",
        "no_fish_recipe_available",
        "no_legume_recipe_available",
    )
    assert failing(plan) == {"fish", "legume", "meat_free_day"}


# ───────────────────────────── leftover-aware grouping ─────────────────────────────

_LEFTOVER_INGREDIENTS: dict[str, Ingredient] = {
    "kozos": Ingredient("kozos", "kozos", "egyeb", "kg", tags=("dairy",), perishable_days=5),
    "tartos": Ingredient("tartos", "tartos", "egyeb", "kg", tags=("grain",)),
    "hosszu": Ingredient("hosszu", "hosszu", "egyeb", "kg", tags=("vegetable",), perishable_days=8),
    **{
        f"egyedi{i}": Ingredient(f"egyedi{i}", "x", "egyeb", "kg", tags=("vegetable",), perishable_days=4)
        for i in range(12)
    },
}


def _distinct_perishables(plan: Plan, lib: Sequence[Recipe], days: range) -> int:
    lookup = by_id(lib)
    found = {
        line.ingredient_id
        for day in plan.days
        if day.index in days
        for rid in day.meals.values()
        if rid is not None
        for line in lookup[rid].lines
        if (p := _LEFTOVER_INGREDIENTS[line.ingredient_id].perishable_days) is not None and p <= 7
    }
    return len(found)


@pytest.mark.parametrize("seed", range(5))
def test_plan_reuses_perishables_within_a_week(seed: int) -> None:
    ing = _LEFTOVER_INGREDIENTS
    shared = [
        recipe(f"kozos-{i:02d}", ("ebed", "vacsora"), [("kozos", "0.2"), ("tartos", "0.3")], ingredients=ing)
        for i in range(14)
    ]
    unique = [
        recipe(
            f"egyedi-{i:02d}",
            ("ebed", "vacsora"),
            [(f"egyedi{i}", "0.2"), ("hosszu", "0.3")],
            ingredients=ing,
        )
        for i in range(12)
    ]
    lib = shared + unique
    plan = suggest(lib, ing, slots=("ebed", "vacsora"), days=14, seed=seed)
    assert failing(plan) == {"fish", "legume"}  # this library has neither (both blocks are 7 days)
    # 14 recipes share one perishable (a 5-day window of 2 slots needs 10 distinct recipes); the 12 others
    # each bring their own. The best plan uses only the shared ones: 1 distinct perishable a week.
    assert _distinct_perishables(plan, lib, range(0, 7)) == 1
    assert _distinct_perishables(plan, lib, range(7, 14)) == 1


# ───────────────────────────── budget ─────────────────────────────


def test_budget_met_by_choosing_cheap_recipes() -> None:
    costs = cheap_costs(LIB)
    # 3 meals a day x 7 days x 2 people x 100 Ft = 4200; a single 5000 Ft meal would break it
    plan = suggest(slots=SLOTS_3, days=14, weekly_budget=Decimal(4200), recipe_cost_per_serving=costs, seed=2)
    assert failing(plan) == set(), [c for c in plan.checks if not c.ok]
    assert plan.warnings == ()
    assert all(costs[rid] == 100 for rid in meals(plan))
    assert [c.value for c in plan.checks if c.rule == "budget"] == ["4200 Ft", "4200 Ft"]


def test_budget_below_cheapest_plan_fails_with_warning() -> None:
    plan = suggest(weekly_budget=Decimal(4199), recipe_cost_per_serving=cheap_costs(LIB))
    assert plan.warnings == ("budget_unreachable",)
    assert failing(plan) == {"budget"}


def test_budget_avoids_recipes_without_cost_estimate() -> None:
    costs = {rid: c for rid, c in cheap_costs(LIB).items() if c == 100 or rid.startswith("main")}
    plan = suggest(
        slots=SLOTS_3, days=7, weekly_budget=Decimal(100000), recipe_cost_per_serving=costs, seed=1
    )
    assert failing(plan) == set()
    assert all(rid in costs for rid in meals(plan))
    assert plan.warnings == ()


def test_budget_with_an_unpriced_slot() -> None:
    costs = {r.id: Decimal(100) for r in LIB if "reggeli" not in r.slots}
    plan = suggest(slots=SLOTS_3, weekly_budget=Decimal(100000), recipe_cost_per_serving=costs)
    assert plan.warnings == ("budget_unreachable", "recipe_cost_missing")
    assert failing(plan) == {"budget"}


def test_budget_without_cost_table_is_not_checked_but_warned() -> None:
    plan = suggest(weekly_budget=Decimal(1))
    assert plan.warnings == ("recipe_cost_missing",)
    assert "budget" not in {c.rule for c in plan.checks}


def test_costs_without_budget_add_no_budget_check() -> None:
    plan = suggest(recipe_cost_per_serving=cheap_costs(LIB))
    assert "budget" not in {c.rule for c in plan.checks}


# ───────────────────────────── performance and termination ─────────────────────────────


def test_31_days_5_slots_under_200_ms() -> None:
    costs = cheap_costs(LIB)
    timings = []
    for seed in range(3):
        req = request(
            days=31, slots=SLOTS_5, seed=seed, weekly_budget=Decimal(60000), recipe_cost_per_serving=costs
        )
        start = time.perf_counter()
        plan = suggest_plan(LIB, INGREDIENTS, req)
        timings.append(time.perf_counter() - start)
        assert len(plan.days) == 31
    print(
        f"\nsuggest_plan 31 days x 5 slots, {len(LIB)} recipes: "
        + ", ".join(f"{t * 1000:.1f} ms" for t in timings)
    )
    assert max(timings) < 0.2, timings


@pytest.mark.parametrize(
    "recipes",
    [
        [],
        [recipe("egy", ("ebed",), [("marha", "2")], extra_tags=["edes"])],
        [recipe("krumpli", SLOTS_5, [("burgonya", "1"), ("virsli", "8")], extra_tags=["edes", "ket_napos"])],
    ],
    ids=["no-recipes", "one-bad-recipe", "one-recipe-for-all-slots"],
)
def test_impossible_inputs_terminate_quickly(recipes: list[Recipe]) -> None:
    start = time.perf_counter()
    plan = suggest(
        recipes,
        days=31,
        slots=SLOTS_5,
        red_meat_g_per_person_week=0,
        weekly_budget=Decimal(0),
        recipe_cost_per_serving={r.id: Decimal(1) for r in recipes},
    )
    assert time.perf_counter() - start < 1.0
    assert len(plan.days) == 31
    assert plan.checks == recheck(
        plan,
        recipes,
        request(
            days=31,
            slots=SLOTS_5,
            red_meat_g_per_person_week=0,
            weekly_budget=Decimal(0),
            recipe_cost_per_serving={r.id: Decimal(1) for r in recipes},
        ),
    )


def test_no_recipes_warnings() -> None:
    plan = suggest([], slots=("ebed", "vacsora"), days=3)
    assert plan.warnings == (
        "slot_pool_empty:ebed",
        "slot_pool_empty:vacsora",
    )  # count rules n/a under 4 days
    assert failing(plan) == set()
    assert all(rid is None for day in plan.days for rid in day.meals.values())


# ───────────────────────────── validation ─────────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"days": 0}, "days must be"),
        ({"days": 32}, "days must be"),
        ({"slots": ()}, "slots must not be empty"),
        ({"slots": ("vacsora", "ebed")}, "SLOTS_5 order"),
        ({"slots": ("ebed", "ebed")}, "SLOTS_5 order"),
        ({"slots": ("brunch",)}, "unknown slot"),
        ({"people": 0}, "people"),
        ({"people": 13}, "people"),
        ({"no_repeat_days": -1}, "no_repeat_days"),
        ({"red_meat_g_per_person_week": -5}, "red_meat_g_per_person_week"),
        ({"weekly_budget": Decimal("-1")}, "weekly_budget"),
        ({"weekly_budget": Decimal("NaN")}, "weekly_budget"),
        ({"recipe_cost_per_serving": {"x": Decimal("-1")}}, "cost per serving"),
    ],
)
def test_invalid_request_raises_value_error(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        suggest(**kwargs)


def test_duplicate_recipe_ids_raise_value_error() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        suggest([*LIB, LIB[0]])


def test_unknown_ingredient_in_eligible_recipe_raises_key_error() -> None:
    bad = replace(LIB[0], lines=(replace(LIB[0].lines[0], ingredient_id="nincs_ilyen"),))
    with pytest.raises(KeyError, match="nincs_ilyen"):
        suggest([bad])
