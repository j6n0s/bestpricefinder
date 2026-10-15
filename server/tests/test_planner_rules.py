"""check_plan: every rule pass and fail, on hand-made plans over a SYNTHETIC recipe library."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

import pytest

from bpf.planner import check_plan
from bpf.planner.rules import repeat_flags
from bpf.pricing.model import Ingredient, PlanDay, Recipe, RecipeLine, RuleCheck, Slot
from tests.test_planner_synth import INGREDIENTS, by_id, plan_days, recipe

FILLERS = [
    recipe(
        f"veg-{i}",
        ("reggeli", "tizorai", "ebed", "uzsonna", "vacsora"),
        [("teszta", "0.4"), ("paradicsom", "0.3")],
    )
    for i in range(1, 15)
]
RECIPES = by_id(
    [
        *FILLERS,
        recipe("hal-rizs", ("ebed", "vacsora"), [("hal", "0.6"), ("rizs", "0.3")]),
        recipe("lencse", ("ebed", "vacsora"), [("lencse", "0.4"), ("paradicsom", "0.3")]),
        recipe(
            "marha-400", ("ebed", "vacsora"), [("marha", "0.4"), ("rizs", "0.3")]
        ),  # 100 g red meat / serving
        recipe("marha-third", ("ebed", "vacsora"), [("marha", "0.5")], servings=3),  # 500/3 g / serving
        recipe(
            "sertes-krumpli", ("ebed", "vacsora"), [("sertes", "0.8"), ("burgonya", "1")]
        ),  # 200 g, potato
        recipe("csirke", ("ebed", "vacsora"), [("csirke", "0.6"), ("teszta", "0.3")]),
        recipe("csirke-2", ("ebed", "vacsora"), [("csirke", "0.6"), ("rizs", "0.3")]),
        recipe("rakott-krumpli", ("ebed", "vacsora"), [("burgonya", "1"), ("tojas", "4"), ("tejfol", "0.2")]),
        recipe(
            "virslis-kenyer", ("reggeli",), [("kenyer", "0.2"), ("virsli", "4")]
        ),  # 4 x 0.05 kg / 4 = 50 g
        recipe(
            "kolbaszos-opcio", ("reggeli",), [("kenyer", "0.2"), ("kolbasz", "0.2")], optional=["kolbasz"]
        ),
        recipe("turos-kenyer", ("reggeli", "uzsonna"), [("kenyer", "0.2"), ("turo", "0.2")]),
        recipe("alma", ("tizorai", "uzsonna"), [("alma", "0.4")]),
        recipe("palacsinta", ("tizorai", "uzsonna"), [("tej", "0.5"), ("cukor", "0.1")], extra_tags=["edes"]),
        recipe("muffin", ("tizorai", "uzsonna"), [("cukor", "0.1"), ("alma", "0.2")], extra_tags=["edes"]),
        recipe("piskota", ("tizorai", "uzsonna"), [("cukor", "0.1"), ("tojas", "2")], extra_tags=["edes"]),
        recipe("krumplis-snack", ("uzsonna",), [("burgonya", "0.4")]),
        recipe(
            "toltott-kaposzta",
            ("ebed", "vacsora"),
            [("sertes", "0.6"), ("kaposzta", "1")],
            extra_tags=["ket_napos"],
        ),
        recipe(
            "babgulyas",
            ("ebed", "vacsora"),
            [("lencse", "0.3"), ("paprika", "0.3")],
            extra_tags=["ket_napos"],
        ),
    ]
)
RULES = ("fish", "legume", "meat_free_day", "red_meat", "potato", "variety")


def check(
    rows: Sequence[Mapping[Slot, str | None]],
    *,
    start: int = 0,
    people: int = 2,
    cap: int = 600,
    budget: Decimal | None = None,
    costs: Mapping[str, Decimal] | None = None,
) -> tuple[RuleCheck, ...]:
    return check_plan(
        plan_days(rows, start),
        RECIPES,
        INGREDIENTS,
        people=people,
        red_meat_g_per_person_week=cap,
        weekly_budget=budget,
        recipe_cost_per_serving=costs,
    )


def rule(checks: Sequence[RuleCheck], name: str, week: int = 0) -> RuleCheck:
    found = [c for c in checks if c.rule == name and c.week == week]
    assert len(found) == 1, (name, week, checks)
    return found[0]


def ebed(*ids: str | None) -> list[dict[Slot, str | None]]:
    return [{"ebed": rid} for rid in ids]


# A week that passes every rule (two main slots, all filler days meat-free).
PASS_WEEK: list[dict[Slot, str | None]] = [
    {"ebed": "hal-rizs", "vacsora": "veg-1"},
    {"ebed": "lencse", "vacsora": "veg-2"},
    {"ebed": "marha-400", "vacsora": "veg-3"},
    {"ebed": "csirke", "vacsora": "veg-4"},
    {"ebed": "veg-5", "vacsora": "veg-6"},
    {"ebed": "veg-7", "vacsora": "veg-8"},
    {"ebed": "veg-9", "vacsora": "veg-1"},
]


def test_hand_made_plan_full_result() -> None:
    assert check(PASS_WEEK) == (
        RuleCheck(0, "fish", True, "1 hal", "≥ 1"),
        RuleCheck(0, "legume", True, "1 hüvelyes", "≥ 1"),
        RuleCheck(0, "meat_free_day", True, "4 húsmentes nap", "≥ 1"),
        RuleCheck(0, "red_meat", True, "100 g/fő", "≤ 600 g/fő"),
        RuleCheck(0, "potato", True, "0 nap egymás után", "≤ 1 nap egymás után"),
        RuleCheck(0, "variety", True, "0 ismétlés", "0 ismétlés 5 napon belül"),
    )


def test_hand_made_two_week_plan_with_snacks_and_budget() -> None:
    week2: list[dict[Slot, str | None]] = [
        {"ebed": "hal-rizs", "vacsora": "veg-11", "tizorai": "alma"},
        {"ebed": "lencse", "vacsora": "veg-12", "tizorai": "veg-10"},
        {"ebed": "marha-400", "vacsora": "veg-13", "tizorai": "alma"},  # alma 2 days later: snack window ok
    ]
    costs = {rid: Decimal(1000) for rid in RECIPES}
    checks = check(PASS_WEEK + week2, budget=Decimal(30000), costs=costs)
    assert [(c.week, c.rule) for c in checks] == [(w, r) for w in (0, 1) for r in (*RULES, "budget")]
    assert rule(checks, "variety", 1) == RuleCheck(
        1, "variety", True, "0 ismétlés", "0 ismétlés 5 napon belül, tízórai/uzsonna 2 napon belül"
    )
    # week 0: 14 meals x 1000 x 2 people; week 1 (3 days): 9 meals x 2000 against 30000 x 3 // 7
    assert rule(checks, "budget", 0) == RuleCheck(0, "budget", True, "28000 Ft", "≤ 30000 Ft")
    assert rule(checks, "budget", 1) == RuleCheck(1, "budget", False, "18000 Ft", "≤ 12857 Ft")
    for name in ("fish", "legume", "meat_free_day"):  # 3-day block: count rules do not apply
        assert rule(checks, name, 1) == RuleCheck(1, name, True, "n/a", "≥ 1")  # type: ignore[arg-type]
    assert rule(checks, "red_meat", 1) == RuleCheck(1, "red_meat", True, "100 g/fő", "≤ 257 g/fő")


# ───────────────────────────── count rules ─────────────────────────────


def test_fish_and_legume_fail_without_such_meal() -> None:
    week = [dict(day) for day in PASS_WEEK]
    week[0]["ebed"] = "veg-10"
    week[1]["ebed"] = "veg-11"
    checks = check(week)
    assert rule(checks, "fish") == RuleCheck(0, "fish", False, "0 hal", "≥ 1")
    assert rule(checks, "legume") == RuleCheck(0, "legume", False, "0 hüvelyes", "≥ 1")


def test_fish_counts_meals_in_any_slot_and_repeats() -> None:
    week = [dict(day) for day in PASS_WEEK]
    week[5]["vacsora"] = "hal-rizs"
    assert rule(check(week), "fish") == RuleCheck(0, "fish", True, "2 hal", "≥ 1")


def test_meat_free_day_fails_when_every_day_has_meat() -> None:
    meaty = ["hal-rizs", "marha-400", "csirke", "csirke-2", "sertes-krumpli", "toltott-kaposzta", "hal-rizs"]
    week = [{"ebed": m, "vacsora": f"veg-{i + 1}"} for i, m in enumerate(meaty)]
    assert rule(check(week), "meat_free_day") == RuleCheck(
        0, "meat_free_day", False, "0 húsmentes nap", "≥ 1"
    )


def test_meat_free_day_needs_at_least_one_meal() -> None:
    rows = (
        [{"ebed": "csirke", "vacsora": None}] * 3
        + [{"ebed": None, "vacsora": None}]
        + [{"ebed": "csirke"}] * 3
    )
    assert rule(check(rows), "meat_free_day").ok is False
    rows[3] = {"ebed": None, "vacsora": "veg-1"}  # empty slots are ignored: one meat-free meal is enough
    assert rule(check(rows), "meat_free_day") == RuleCheck(0, "meat_free_day", True, "1 húsmentes nap", "≥ 1")


@pytest.mark.parametrize(("days", "applies"), [(1, False), (3, False), (4, True), (7, True)])
def test_count_rules_apply_only_to_blocks_of_at_least_4_days(days: int, applies: bool) -> None:
    checks = check([{"ebed": f"veg-{i + 1}"} for i in range(days)])
    for name in ("fish", "legume"):
        expected = RuleCheck(0, name, False, f"0 {'hal' if name == 'fish' else 'hüvelyes'}", "≥ 1")
        assert rule(checks, name) == (expected if applies else RuleCheck(0, name, True, "n/a", "≥ 1"))  # type: ignore[arg-type]
    assert rule(checks, "meat_free_day").value == (f"{days} húsmentes nap" if applies else "n/a")


def test_partial_last_block_of_10_days() -> None:
    rows = [{"ebed": f"veg-{i + 1}"} for i in range(10)]
    checks = check(rows)
    assert [c.week for c in checks] == [0] * 6 + [1] * 6
    assert rule(checks, "fish", 0).ok is False
    assert rule(checks, "fish", 1) == RuleCheck(1, "fish", True, "n/a", "≥ 1")


# ───────────────────────────── red meat ─────────────────────────────


def test_red_meat_at_cap_passes_and_over_cap_fails() -> None:
    six = ebed(*["marha-400"] * 6, "veg-1")
    assert rule(check(six), "red_meat") == RuleCheck(0, "red_meat", True, "600 g/fő", "≤ 600 g/fő")
    seven = ebed(*["marha-400"] * 7)
    assert rule(check(seven), "red_meat") == RuleCheck(0, "red_meat", False, "700 g/fő", "≤ 600 g/fő")


def test_red_meat_grams_are_exact_fractions() -> None:
    # 0.5 kg / 3 servings = 166.66... g; three meals are exactly 500 g (a Decimal sum would exceed 500).
    rows = ebed("marha-third", "veg-1", "marha-third", "veg-2", "marha-third", "veg-3", "veg-4")
    assert rule(check(rows, cap=500), "red_meat") == RuleCheck(0, "red_meat", True, "500 g/fő", "≤ 500 g/fő")
    assert rule(check(rows, cap=499), "red_meat") == RuleCheck(0, "red_meat", False, "500 g/fő", "≤ 499 g/fő")
    two = ebed("marha-third", "veg-1", "marha-third", "veg-2", "veg-3", "veg-4", "veg-5")
    # 333.33 g is shown rounded up, so a passing value never displays above its limit
    assert rule(check(two, cap=334), "red_meat") == RuleCheck(0, "red_meat", True, "334 g/fő", "≤ 334 g/fő")
    assert rule(check(two, cap=333), "red_meat") == RuleCheck(0, "red_meat", False, "334 g/fő", "≤ 333 g/fő")


def test_processed_meat_in_pieces_and_optional_lines_count() -> None:
    rows = [{"reggeli": "virslis-kenyer", "ebed": "veg-1"}, {"reggeli": "kolbaszos-opcio", "ebed": "veg-2"}]
    # virsli: 4 db x 0.05 kg / 4 servings = 50 g; optional kolbasz line: 0.2 kg / 4 = 50 g
    assert rule(check(rows), "red_meat").value == "100 g/fő"


def test_red_meat_ignores_people() -> None:
    rows = ebed("marha-400", "veg-1")
    assert rule(check(rows, people=1), "red_meat").value == rule(check(rows, people=12), "red_meat").value


def test_red_meat_cap_is_pro_rata_for_partial_blocks() -> None:
    # days 7..9 form a 3-day block: 600 x 3 // 7 = 257 g
    week0 = [{"ebed": f"veg-{i + 1}"} for i in range(7)]
    ok_block = week0 + ebed("marha-400", "marha-400") + [{"ebed": "veg-8", "reggeli": "virslis-kenyer"}]
    assert rule(check(ok_block), "red_meat", 1) == RuleCheck(1, "red_meat", True, "250 g/fő", "≤ 257 g/fő")
    over = week0 + ebed("marha-400", "marha-400") + [{"ebed": "marha-third"}]
    assert rule(check(over), "red_meat", 1) == RuleCheck(1, "red_meat", False, "367 g/fő", "≤ 257 g/fő")
    one_day = check([{"ebed": "virslis-kenyer"}], cap=600)
    assert rule(one_day, "red_meat") == RuleCheck(0, "red_meat", True, "50 g/fő", "≤ 85 g/fő")


def test_red_meat_cap_zero() -> None:
    assert rule(check(ebed("veg-1", "csirke", "hal-rizs"), cap=0), "red_meat") == RuleCheck(
        0, "red_meat", True, "0 g/fő", "≤ 0 g/fő"
    )
    assert rule(check(ebed("veg-1", "virslis-kenyer"), cap=0), "red_meat").ok is False


def test_red_meat_volume_needs_density() -> None:
    weird = {**INGREDIENTS, "hus_l": Ingredient("hus_l", "x", "egyeb", "l", tags=("red_meat",))}
    r = recipe("folyekony", ("ebed",), [("hus_l", "0.4")], ingredients=weird)
    with pytest.raises(ValueError, match="cannot convert"):
        check_plan(plan_days([{"ebed": "folyekony"}]), {"folyekony": r}, weird, people=1)
    dense = {
        **weird,
        "hus_l": Ingredient("hus_l", "x", "egyeb", "l", tags=("red_meat",), density_kg_per_l=Decimal("1.5")),
    }
    checks = check_plan(plan_days([{"ebed": "folyekony"}]), {"folyekony": r}, dense, people=1)
    assert rule(checks, "red_meat").value == "150 g/fő"  # 0.4 l x 1.5 kg/l / 4 servings


# ───────────────────────────── potato ─────────────────────────────


def test_potato_every_second_day_passes() -> None:
    rows = ebed("rakott-krumpli", "veg-1", "sertes-krumpli", "veg-2", "rakott-krumpli", "veg-3", "veg-4")
    assert rule(check(rows), "potato") == RuleCheck(
        0, "potato", True, "1 nap egymás után", "≤ 1 nap egymás után"
    )


def test_potato_on_consecutive_days_fails() -> None:
    rows = ebed("rakott-krumpli", "sertes-krumpli", "veg-1")
    assert rule(check(rows), "potato") == RuleCheck(
        0, "potato", False, "2 nap egymás után", "≤ 1 nap egymás után"
    )
    three = [
        {"ebed": "rakott-krumpli"},
        {"vacsora": "sertes-krumpli"},
        {"reggeli": "veg-1", "ebed": "rakott-krumpli"},
    ]
    assert rule(check(three), "potato").value == "3 nap egymás után"


def test_potato_in_a_snack_does_not_count() -> None:
    rows = [
        {"ebed": "rakott-krumpli"},
        {"ebed": "veg-1", "uzsonna": "krumplis-snack"},
        {"uzsonna": "krumplis-snack"},
    ]
    assert rule(check(rows), "potato").ok is True


def test_potato_run_across_week_boundary_is_reported_in_the_later_week() -> None:
    rows = [{"ebed": f"veg-{i + 1}"} for i in range(6)] + ebed("rakott-krumpli", "sertes-krumpli", "veg-9")
    checks = check(rows)
    assert rule(checks, "potato", 0) == RuleCheck(
        0, "potato", True, "1 nap egymás után", "≤ 1 nap egymás után"
    )
    assert rule(checks, "potato", 1) == RuleCheck(
        1, "potato", False, "2 nap egymás után", "≤ 1 nap egymás után"
    )


def test_potato_days_with_a_gap_in_the_plan_are_not_consecutive() -> None:
    days = (PlanDay(0, {"ebed": "rakott-krumpli"}), PlanDay(2, {"ebed": "sertes-krumpli"}))
    assert rule(check_plan(days, RECIPES, INGREDIENTS, people=1), "potato").ok is True


# ───────────────────────────── no sweets rule ─────────────────────────────


def test_sweet_meals_are_not_capped() -> None:
    """The sweets cap was removed (2026-10-15): any number of sweet (``edes``) meals passes every rule."""
    rows = [{"uzsonna": "palacsinta", "tizorai": "muffin"}, {"uzsonna": "piskota"}, {"tizorai": "palacsinta"}]
    checks = check(rows)
    assert "sweets" not in {c.rule for c in checks}
    assert all(c.ok for c in checks if c.rule != "variety")


# ───────────────────────────── variety ─────────────────────────────


def test_repeat_inside_window_fails_and_at_window_passes() -> None:
    inside = ebed("csirke", "veg-1", "veg-2", "veg-3", "csirke")  # gap 4 < 5
    assert rule(check(inside), "variety") == RuleCheck(
        0, "variety", False, "1 ismétlés", "0 ismétlés 5 napon belül"
    )
    at_window = ebed("csirke", "veg-1", "veg-2", "veg-3", "veg-4", "csirke")  # gap 5
    assert rule(check(at_window), "variety").ok is True


def test_check_plan_uses_the_given_no_repeat_window() -> None:
    inside = ebed("csirke", "veg-1", "veg-2", "veg-3", "csirke")  # gap 4
    narrow = check_plan(plan_days(inside), RECIPES, INGREDIENTS, people=2, no_repeat_days=3)
    assert rule(narrow, "variety").ok is True
    wide = check_plan(plan_days(inside), RECIPES, INGREDIENTS, people=2, no_repeat_days=7)
    assert rule(wide, "variety").ok is False
    assert rule(wide, "variety").limit.startswith("0 ismétlés 7 napon belül")
    with pytest.raises(ValueError, match="no_repeat_days"):
        check_plan(plan_days(inside), RECIPES, INGREDIENTS, people=2, no_repeat_days=-1)


def test_same_recipe_twice_on_one_day_fails() -> None:
    assert rule(check([{"ebed": "csirke", "vacsora": "csirke"}]), "variety").value == "1 ismétlés"


def test_repeat_counts_each_repeating_meal_once() -> None:
    rows = ebed("csirke", "csirke", "csirke")
    assert rule(check(rows), "variety").value == "2 ismétlés"


def test_ket_napos_same_slot_next_day_is_allowed() -> None:
    rows = ebed("toltott-kaposzta", "toltott-kaposzta", "veg-1")
    assert rule(check(rows), "variety").ok is True
    rows = [{"vacsora": "babgulyas"}, {"vacsora": "babgulyas"}]
    assert rule(check(rows), "variety").ok is True


def test_ket_napos_other_slot_or_later_day_or_third_day_fails() -> None:
    other_slot = [{"ebed": "toltott-kaposzta"}, {"vacsora": "toltott-kaposzta"}]
    assert rule(check(other_slot), "variety").value == "1 ismétlés"
    two_days_later = ebed("toltott-kaposzta", "veg-1", "toltott-kaposzta")
    assert rule(check(two_days_later), "variety").value == "1 ismétlés"
    three_in_a_row = ebed("toltott-kaposzta", "toltott-kaposzta", "toltott-kaposzta")
    assert rule(check(three_in_a_row), "variety").value == "1 ismétlés"
    same_day = [{"ebed": "toltott-kaposzta", "vacsora": "toltott-kaposzta"}]
    assert rule(check(same_day), "variety").ok is False


def test_without_ket_napos_tag_next_day_fails() -> None:
    assert rule(check(ebed("csirke", "csirke")), "variety").ok is False


def test_snacks_use_a_two_day_window() -> None:
    assert rule(check([{"uzsonna": "alma"}, {"uzsonna": "veg-1"}, {"uzsonna": "alma"}]), "variety").ok is True
    next_day = check([{"uzsonna": "alma"}, {"uzsonna": "alma"}])
    assert rule(next_day, "variety") == RuleCheck(
        0, "variety", False, "1 ismétlés", "0 ismétlés 5 napon belül, tízórai/uzsonna 2 napon belül"
    )
    assert rule(check([{"tizorai": "alma", "uzsonna": "alma"}]), "variety").ok is False
    assert rule(check([{"tizorai": "alma"}, {"uzsonna": "alma"}]), "variety").ok is False


def test_a_pair_involving_a_snack_slot_uses_the_snack_window() -> None:
    assert rule(check([{"reggeli": "turos-kenyer"}, {}, {"uzsonna": "turos-kenyer"}]), "variety").ok is True
    assert rule(check([{"reggeli": "turos-kenyer"}, {"uzsonna": "turos-kenyer"}]), "variety").ok is False
    assert rule(check([{"reggeli": "turos-kenyer"}, {}, {"reggeli": "turos-kenyer"}]), "variety").ok is False


def test_repeat_across_week_boundary_is_reported_in_the_later_week() -> None:
    rows = ebed("veg-1", "veg-2", "veg-3", "veg-4", "veg-5", "csirke", "veg-6", "veg-7", "csirke")
    checks = check(rows)
    assert rule(checks, "variety", 0).ok is True
    assert rule(checks, "variety", 1).value == "1 ismétlés"


def test_repeat_flags_greedy_pairing_and_small_windows() -> None:
    ebed_pos = 2
    run = [(d, ebed_pos) for d in range(4)]
    # window 5: day 2 repeats day 0; day 3 is day 2's second day but repeats days 0 and 1
    assert repeat_flags(run, True, 5, 2) == [False, False, True, True]
    # window 2: pairs (0, 1) and (2, 3); day 2 is a new cooking one day after day 1
    assert repeat_flags(run, True, 2, 2) == [False, False, True, False]
    assert repeat_flags(run, False, 2, 2) == [False, True, True, True]
    # window 1 forbids only same-day repeats; window 0 disables the rule
    assert repeat_flags(run, False, 1, 1) == [False] * 4
    assert repeat_flags([(0, 0), (0, 2)], False, 1, 1) == [False, True]
    assert repeat_flags([(0, 0), (0, 2)], False, 0, 0) == [False, False]


# ───────────────────────────── budget ─────────────────────────────

COSTS = {rid: Decimal(1000) for rid in RECIPES}


def test_budget_pass_at_limit_and_fail_above() -> None:
    rows = ebed(*[f"veg-{i + 1}" for i in range(7)])  # 7 meals x 1000 x 2 people = 14000
    assert rule(check(rows, budget=Decimal(14000), costs=COSTS), "budget") == RuleCheck(
        0, "budget", True, "14000 Ft", "≤ 14000 Ft"
    )
    assert rule(check(rows, budget=Decimal(13999), costs=COSTS), "budget") == RuleCheck(
        0, "budget", False, "14000 Ft", "≤ 13999 Ft"
    )


def test_budget_multiplies_by_people() -> None:
    rows = ebed("veg-1", "veg-2")
    assert rule(check(rows, people=1, budget=Decimal(70000), costs=COSTS), "budget").value == "2000 Ft"
    assert rule(check(rows, people=12, budget=Decimal(70000), costs=COSTS), "budget").value == "24000 Ft"


def test_budget_value_rounds_up_and_limit_rounds_down() -> None:
    # one day: limit 7000 x 1 // 7 = 1000 Ft
    costs = {**COSTS, "veg-1": Decimal("1000.40")}
    assert rule(check(ebed("veg-1"), people=1, budget=Decimal(7000), costs=costs), "budget") == RuleCheck(
        0, "budget", False, "1001 Ft", "≤ 1000 Ft"
    )
    costs = {**COSTS, "veg-1": Decimal("999.01")}
    assert rule(check(ebed("veg-1"), people=1, budget=Decimal(7000), costs=costs), "budget") == RuleCheck(
        0, "budget", True, "1000 Ft", "≤ 1000 Ft"
    )
    # 6999 x 1 // 7 = 999: the fractional pro-rata limit (999.857) is rounded down
    costs = {**COSTS, "veg-1": Decimal("999.50")}
    assert rule(check(ebed("veg-1"), people=1, budget=Decimal(6999), costs=costs), "budget") == RuleCheck(
        0, "budget", False, "1000 Ft", "≤ 999 Ft"
    )


def test_budget_is_pro_rata_for_partial_blocks() -> None:
    rows = ebed(*[f"veg-{i + 1}" for i in range(10)])  # block 1 = days 7..9
    checks = check(rows, budget=Decimal(14000), costs=COSTS)  # 14000 x 3 // 7 = 6000
    assert rule(checks, "budget", 1) == RuleCheck(1, "budget", True, "6000 Ft", "≤ 6000 Ft")
    checks = check(rows, budget=Decimal(13999), costs=COSTS)  # 13999 x 3 // 7 = 5999
    assert rule(checks, "budget", 1) == RuleCheck(1, "budget", False, "6000 Ft", "≤ 5999 Ft")


def test_budget_fails_when_a_meal_has_no_cost_estimate() -> None:
    costs = {rid: c for rid, c in COSTS.items() if rid != "veg-2"}
    checks = check(ebed("veg-1", "veg-2", None), budget=Decimal(100000), costs=costs)
    assert rule(checks, "budget") == RuleCheck(
        0, "budget", False, "2000 Ft + 1 ár nélküli étel", "≤ 42857 Ft"
    )


@pytest.mark.parametrize(
    ("budget", "costs"),
    [(None, COSTS), (Decimal(1), None), (Decimal(1), {})],
    ids=["no-budget", "None", "empty"],
)
def test_budget_rule_needs_budget_and_cost_table(
    budget: Decimal | None, costs: dict[str, Decimal] | None
) -> None:
    checks = check(PASS_WEEK, budget=budget, costs=costs)
    assert [c.rule for c in checks] == list(RULES)


def test_budget_accepts_int_amount() -> None:
    rows = ebed("veg-1")
    assert rule(check(rows, budget=7000, costs=COSTS), "budget").limit == "≤ 1000 Ft"  # type: ignore[arg-type]


# ───────────────────────────── input handling ─────────────────────────────


def test_unsorted_days_give_the_same_result_as_sorted() -> None:
    days = plan_days(PASS_WEEK + PASS_WEEK[:2])
    assert check_plan(tuple(reversed(days)), RECIPES, INGREDIENTS, people=2) == check_plan(
        days, RECIPES, INGREDIENTS, people=2
    )


def test_plan_starting_in_a_later_week_reports_only_present_weeks() -> None:
    checks = check(ebed("veg-1", "veg-2"), start=14)
    assert {c.week for c in checks} == {2}


def test_empty_plan_has_no_checks() -> None:
    assert check_plan((), RECIPES, INGREDIENTS, people=2) == ()


def test_unknown_recipe_raises_key_error() -> None:
    with pytest.raises(KeyError, match="nincs-ilyen"):
        check(ebed("nincs-ilyen"))


def test_unknown_ingredient_raises_key_error() -> None:
    broken = Recipe(
        id="rossz",
        title="rossz",
        slots=("ebed",),
        servings=1,
        lines=(RecipeLine(1, "nincs_ilyen", Decimal(1), "1"),),
    )
    with pytest.raises(KeyError, match="nincs_ilyen"):
        check_plan(plan_days([{"ebed": "rossz"}]), {"rossz": broken}, INGREDIENTS, people=1)


@pytest.mark.parametrize(
    ("days", "message"),
    [
        ((PlanDay(0, {"ebed": "veg-1"}), PlanDay(0, {"ebed": "veg-2"})), "duplicate day index"),
        ((PlanDay(-1, {"ebed": "veg-1"}),), "day index must be"),
        ((PlanDay(0, {"brunch": "veg-1"}),), "unknown slot"),  # type: ignore[dict-item]
    ],
    ids=["duplicate-index", "negative-index", "unknown-slot"],
)
def test_bad_days_raise_value_error(days: tuple[PlanDay, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_plan(days, RECIPES, INGREDIENTS, people=2)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"people": 0}, "people"),
        ({"people": 13}, "people"),
        ({"people": 2, "red_meat_g_per_person_week": -1}, "red_meat_g_per_person_week"),
        ({"people": 2, "weekly_budget": Decimal(-1)}, "weekly_budget"),
        ({"people": 2, "weekly_budget": Decimal("NaN")}, "weekly_budget"),
        ({"people": 2, "recipe_cost_per_serving": {"veg-1": Decimal("-0.01")}}, "cost per serving"),
        ({"people": 2, "recipe_cost_per_serving": {"veg-1": Decimal("Infinity")}}, "cost per serving"),
    ],
)
def test_bad_parameters_raise_value_error(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_plan(plan_days(ebed("veg-1")), RECIPES, INGREDIENTS, **kwargs)  # type: ignore[arg-type]


def test_zero_servings_raise_value_error() -> None:
    zero = recipe("nulla", ("ebed",), [("alma", "0.2")], servings=0)
    with pytest.raises(ValueError, match="servings"):
        check_plan(plan_days([{"ebed": "nulla"}]), {"nulla": zero}, INGREDIENTS, people=1)
