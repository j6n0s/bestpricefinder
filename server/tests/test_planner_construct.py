"""bpf.planner.construct (the feasibility-first search) and the joint pool analysis, on SYNTHETIC data only
(tests/test_planner_synth.py builders; no file under data/ is read).

The property tests compare against brute force: every possible plan of a tiny random request is checked with
``check_plan``. With an unlimited node budget the construction must find a plan exactly when one meets every
rule (so no propagation step ever removes a valid choice), and every ``slot_pool_too_small`` warning must be
right (no plan keeps the variety rule together with the sweets cap and the potato rule).
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

import pytest

from bpf.planner import check_plan, suggest_plan
from bpf.planner.construct import Construct, mask_values
from bpf.planner.facts import recipe_facts, validate_costs
from bpf.planner.rules import Limits, Meal, compile_meals, make_limits
from bpf.planner.facts import MAIN_POS
from bpf.planner.search import PoolAnalysis, _potato_free_slots, _sweets_floor, _too_small_slots, analyse_pools
from bpf.pricing.model import SLOTS_5, PlanDay, PlanRequest, Recipe, RuleCheck, Slot
from tests.test_planner_synth import INGREDIENTS, by_id, random_costs, recipe, seeded

UNLIMITED = 10**7


@dataclass
class Setup:
    """What ``suggest_plan`` derives from a request, built the same way (pools sorted by recipe id)."""

    req: PlanRequest
    used: list[Recipe]
    positions: tuple[int, ...]
    pools: dict[int, tuple[int, ...]]
    meals: tuple[Meal, ...]
    lim: Limits
    analysis: PoolAnalysis

    @property
    def active(self) -> list[int]:
        return [pos for pos in self.positions if self.pools[pos]]

    def construct(self) -> Construct:
        """A construction that enforces every rule (nothing hopeless, nothing relaxed), whatever the analysis
        says."""
        return Construct(
            self.req.days,
            self.active,
            self.pools,
            self.meals,
            self.lim,
            hopeless=[frozenset()] * ((self.req.days + 6) // 7),
            relaxed=frozenset(),
            enforce_potato=True,
        )

    def hall_slots(self) -> set[int]:
        """Slots the plain variety check (Hall's condition, no other rule) flags."""
        main = [pos for pos in self.active if pos in MAIN_POS]
        flagged = _too_small_slots(main, self.pools, self.meals, self.lim.main_window, self.req.days)
        return flagged | _too_small_slots(self.active, self.pools, self.meals, self.lim.snack_window, self.req.days)

    def plan_days(self, cells: Sequence[int]) -> tuple[PlanDay, ...]:
        """The plan of ``cells`` (day-major over the active slots; a prefix gives the first days only)."""
        width = len(self.active)
        n_days = len(cells) // width if width else self.req.days
        return tuple(
            PlanDay(
                index=day,
                meals={
                    SLOTS_5[pos]: (
                        self.used[cells[day * width + self.active.index(pos)]].id if self.pools[pos] else None
                    )
                    for pos in self.positions
                },
            )
            for day in range(n_days)
        )

    def checks(self, days: Sequence[PlanDay]) -> tuple[RuleCheck, ...]:
        return check_plan(
            days,
            by_id(self.used),
            INGREDIENTS,
            people=self.req.people,
            red_meat_g_per_person_week=self.req.red_meat_g_per_person_week,
            weekly_budget=self.req.weekly_budget,
            recipe_cost_per_serving=self.req.recipe_cost_per_serving,
            no_repeat_days=self.req.no_repeat_days,
        )

    def too_small_warnings(self) -> tuple[str, ...]:
        return tuple(w for w in self.analysis.warnings if w.startswith("slot_pool_too_small"))


def setup(recipes: Sequence[Recipe], req: PlanRequest) -> Setup:
    positions = tuple(SLOTS_5.index(slot) for slot in req.slots)
    costs = validate_costs(req.recipe_cost_per_serving)
    used = sorted((r for r in recipes if set(req.slots) & set(r.slots)), key=lambda r: r.id)
    facts = [recipe_facts(r, INGREDIENTS, people=req.people, costs=costs) for r in used]
    perishables = sorted({iid for f in facts for iid in f.perishables})
    meals, red_den = compile_meals(facts, {iid: bit for bit, iid in enumerate(perishables)})
    pools = {pos: tuple(i for i, r in enumerate(used) if SLOTS_5[pos] in r.slots) for pos in positions}
    budget = req.weekly_budget if costs else None
    lim = make_limits(req.red_meat_g_per_person_week, red_den, budget, req.no_repeat_days)
    analysis = analyse_pools(req.days, positions, pools, meals, lim)
    return Setup(req, used, positions, pools, meals, lim, analysis)


def request(days: int, slots: tuple[Slot, ...], **kwargs: object) -> PlanRequest:
    base: dict[str, object] = {"days": days, "slots": slots, "people": 2, "seed": 0}
    base.update(kwargs)
    return PlanRequest(**base)  # type: ignore[arg-type]


def two_day_runs(days: Sequence[PlanDay], slot: Slot) -> int:
    """Longest run of the same recipe in ``slot`` on consecutive days."""
    longest = run = 0
    previous: str | None = None
    for day in days:
        rid = day.meals[slot]
        run = run + 1 if rid is not None and rid == previous else 1
        longest = max(longest, run)
        previous = rid
    return longest


# ───────────────────────────── unit tests ─────────────────────────────


def test_mask_values_lists_set_bits_in_order() -> None:
    assert mask_values(0) == []
    assert mask_values(0b101001) == [0, 3, 5]
    assert mask_values(1 << 70) == [70]


def test_two_day_meals_are_paired_when_the_pool_needs_it() -> None:
    lib = [
        recipe(f"ket-{i}", ("ebed",), [(p, "0.4")], extra_tags=["ket_napos"])
        for i, p in enumerate(("hal", "lencse", "kaposzta"))
    ]
    s = setup(lib, request(14, ("ebed",)))
    assert s.analysis.warnings == ()
    for seed in range(10):
        cells = s.construct().solve(random.Random(seed), UNLIMITED)
        assert cells is not None
        days = s.plan_days(cells)
        assert all(c.ok for c in s.checks(days))
        assert two_day_runs(days, "ebed") == 2  # three meals in a 5-day window: pairs are needed, no triples


def test_a_two_day_meal_never_fills_three_days_in_a_row() -> None:
    # window 2 (snacks): a ket_napos snack could follow itself every day; the rule allows only pairs
    lib = [
        recipe("suti", ("uzsonna",), [("banan", "0.2"), ("joghurt", "0.1")], extra_tags=["ket_napos"]),
        recipe("alma", ("uzsonna",), [("alma", "0.3")]),
        recipe("halas", ("uzsonna",), [("hal", "0.1"), ("lencse", "0.1")]),
    ]
    s = setup(lib, request(7, ("uzsonna",)))
    for seed in range(10):
        cells = s.construct().solve(random.Random(seed), UNLIMITED)
        assert cells is not None
        days = s.plan_days(cells)
        assert all(c.ok for c in s.checks(days))
        assert two_day_runs(days, "uzsonna") <= 2


def test_no_potato_on_consecutive_days() -> None:
    potato = [recipe(f"krumpli-{i}", ("ebed", "vacsora"), [("burgonya", "0.5")]) for i in range(8)]
    other = [recipe(f"rizs-{i}", ("ebed", "vacsora"), [("rizs", "0.3"), ("hal", "0.2")]) for i in range(8)]
    lentil = [recipe("lencse", ("ebed", "vacsora"), [("lencse", "0.4")])]
    s = setup(potato + other + lentil, request(14, ("ebed", "vacsora")))
    for seed in range(5):
        cells = s.construct().solve(random.Random(seed), UNLIMITED)
        assert cells is not None
        assert all(c.ok for c in s.checks(s.plan_days(cells)))


def test_hall_infeasible_pool_is_proved_by_exhausting_the_search() -> None:
    lib = [recipe(f"fo-{i}", ("ebed",), [(p, "0.4")]) for i, p in enumerate(("hal", "lencse", "tejfol", "rizs"))]
    s = setup(lib, request(7, ("ebed",)))
    assert s.analysis.warnings == ("slot_pool_too_small:ebed",)
    builder = s.construct()
    assert builder.solve(random.Random(0), UNLIMITED) is None
    assert builder.nodes < builder.node_limit  # the tree was exhausted, not cut off


def test_out_of_nodes_returns_none_and_respects_the_budget() -> None:
    lib = [recipe(f"fo-{i}", ("ebed",), [(p, "0.4")]) for i, p in enumerate(("hal", "lencse", "tejfol", "rizs"))]
    builder = setup(lib, request(28, ("ebed",))).construct()
    assert builder.solve(random.Random(0), 10) is None
    assert builder.nodes <= 10


def test_construction_is_deterministic() -> None:
    proteins = ("hal", "lencse", "tojas", "csirke", "marha", "tejfol", "kaposzta", "rizs", "turo", "teszta")
    lib = [
        recipe(f"r-{i}", ("ebed", "vacsora"), [(p, "2" if p == "tojas" else "0.3"), (side, "0.2")])
        for i, (p, side) in enumerate(itertools.product(proteins, ("paradicsom", "paprika")))
    ] + [recipe(f"b-{i}", ("reggeli",), [("kenyer", "0.2"), (p, "0.1")]) for i, p in enumerate(("turo", "tej"))]
    lib += [recipe(f"b-x{i}", ("reggeli",), [("kenyer", "0.2"), ("tojas", str(i + 1))]) for i in range(4)]
    s = setup(lib, request(21, ("reggeli", "ebed", "vacsora")))
    first = s.construct().solve(random.Random(42), UNLIMITED)
    assert first is not None
    assert s.construct().solve(random.Random(42), UNLIMITED) == first
    assert all(c.ok for c in s.checks(s.plan_days(first)))


def test_budget_and_red_meat_bounds_are_propagated() -> None:
    meaty = recipe("marha", ("ebed",), [("marha", "0.4")])  # 100 g a serving
    plain = recipe("lencse", ("ebed",), [("lencse", "0.4")])
    costs = {"marha": Decimal(500), "lencse": Decimal("1000.50")}  # 1000 and 2001 Ft a meal for 2 people
    # 3 days (no count rules, no variety): red meat <= 300 x 3 // 7 = 128 g allows one meaty meal, so the
    # cheapest plan is 1000 + 2 x 2001 = 5002 Ft; a weekly budget of 11672 allows 11672 x 3 // 7 = 5002 Ft
    req = request(
        3,
        ("ebed",),
        red_meat_g_per_person_week=300,
        weekly_budget=Decimal(11672),
        recipe_cost_per_serving=costs,
        no_repeat_days=0,
    )
    s = setup([meaty, plain], req)
    assert s.analysis.warnings == ()
    for seed in range(5):
        cells = s.construct().solve(random.Random(seed), UNLIMITED)
        assert cells is not None
        days = s.plan_days(cells)
        assert all(c.ok for c in s.checks(days))
        assert sorted(day.meals["ebed"] or "" for day in days) == ["lencse", "lencse", "marha"]
    tighter = setup([meaty, plain], replace(req, weekly_budget=Decimal(11671)))  # 5001 Ft for 3 days
    assert tighter.analysis.warnings == ()  # each rule alone is satisfiable, the pair is not
    builder = tighter.construct()
    assert builder.solve(random.Random(0), UNLIMITED) is None
    assert builder.nodes < builder.node_limit


# ───────────────────────────── joint pool analysis ─────────────────────────────


def test_sweets_floor_counts_the_sweets_variety_forces() -> None:
    snacks = [recipe(f"sima-{i}", ("tizorai", "uzsonna"), [("alma", "0.2")]) for i in range(3)]
    sweets = [
        recipe(f"edes-{i}", ("tizorai", "uzsonna"), [("cukor", "0.1"), ("alma", "0.1")], extra_tags=["edes"])
        for i in range(3)
    ]
    s = setup(snacks + sweets, request(7, ("tizorai", "uzsonna")))
    # any 2 days hold 4 snack cells and 3 plain snacks: >= 1 sweet per 2 days, 3 per 7-day block
    floor, slots = _sweets_floor(list(s.active), s.pools, s.meals, 2, 7)
    assert (floor, slots) == (3, {1, 3})
    assert _sweets_floor(list(s.active), s.pools, s.meals, 2, 3) == (1, {1, 3})
    assert s.too_small_warnings() == ("slot_pool_too_small:tizorai", "slot_pool_too_small:uzsonna")
    # a fourth plain snack is enough
    more = setup([*snacks, *sweets, recipe("sima-3", ("tizorai", "uzsonna"), [("banan", "0.2")])], s.req)
    assert more.too_small_warnings() == ()


def test_potato_free_slots_need_half_the_window_without_potato() -> None:
    potato = [recipe(f"krumpli-{i}", ("ebed",), [("burgonya", "0.5")]) for i in range(4)]
    plain = [recipe(f"rizs-{i}", ("ebed",), [("rizs", "0.3")]) for i in range(2)]
    s = setup(potato + plain, request(7, ("ebed",)))
    # 6 recipes cover a 5-day window, but 7 days without two potato days in a row have some 5-day window with
    # 3 potato-free days, and only 2 recipes are potato-free
    assert _potato_free_slots([2], s.pools, s.meals, 5, 7) == {2}
    assert _potato_free_slots([2], s.pools, s.meals, 5, 5) == set()  # 5 days: P N P N P needs only 2
    assert s.too_small_warnings() == ("slot_pool_too_small:ebed",)
    assert setup(potato + plain, request(5, ("ebed",))).too_small_warnings() == ()


def test_variety_is_given_up_before_the_sweets_cap() -> None:
    snacks = [recipe(f"sima-{i}", ("tizorai", "uzsonna"), [("alma", "0.2")]) for i in range(3)]
    sweets = [
        recipe(f"edes-{i}", ("tizorai", "uzsonna"), [("cukor", "0.1"), ("alma", "0.1")], extra_tags=["edes"])
        for i in range(3)
    ]
    for seed in range(5):
        plan = suggest_plan(snacks + sweets, INGREDIENTS, request(14, ("tizorai", "uzsonna"), seed=seed))
        assert plan.warnings == (
            "slot_pool_too_small:tizorai",
            "slot_pool_too_small:uzsonna",
            "no_fish_recipe_available",
            "no_legume_recipe_available",
        )
        assert {c.rule for c in plan.checks if not c.ok} == {"variety", "fish", "legume"}
        assert all(c.ok for c in plan.checks if c.rule == "sweets")


# ───────────────────────────── brute force ─────────────────────────────


def tiny_request(rng: random.Random, recipes_out: list[Recipe]) -> PlanRequest:
    """A random request small enough to enumerate every plan (at most 3^6 plans)."""
    if rng.random() < 0.5:
        slots: tuple[Slot, ...] = (rng.choice(SLOTS_5),)
        days = rng.randint(1, 6)
    else:
        slots = tuple(sorted(rng.sample(SLOTS_5, 2), key=SLOTS_5.index))
        days = rng.randint(1, 3)
    ids = sorted(INGREDIENTS)
    for i in range(rng.randint(1, 3 * len(slots))):
        own = tuple(s for s in slots if rng.random() < 0.6) or (rng.choice(slots),)
        chosen = rng.sample(ids, rng.randint(1, 3))
        lines = [
            (iid, "2" if INGREDIENTS[iid].unit == "db" else rng.choice(("0.1", "0.3", "0.6"))) for iid in chosen
        ]
        extra = [tag for tag, p in (("edes", 0.25), ("ket_napos", 0.3)) if rng.random() < p]
        recipes_out.append(recipe(f"t-{i}", own, lines, extra_tags=extra, servings=rng.randint(1, 4)))
    # keep every pool at <= 3 recipes so that the enumeration stays small
    for slot in slots:
        pool = [r for r in recipes_out if slot in r.slots]
        for extra_recipe in pool[3:]:
            recipes_out.remove(extra_recipe)
    with_costs = rng.random() < 0.3
    return request(
        days,
        slots,
        people=rng.randint(1, 3),
        seed=rng.randint(0, 999),
        no_repeat_days=rng.choice((0, 1, 2, 2, 3, 3, 5)),
        red_meat_g_per_person_week=rng.choice((0, 150, 600, 3000)),
        weekly_budget=Decimal(rng.randint(500, 8000)) if with_costs else None,
        recipe_cost_per_serving=random_costs(rng, recipes_out, share=0.9) if with_costs else {},
    )


PREFIX_RULES = frozenset({"variety", "sweets", "potato"})
"""Rules that can only get worse as days are added: a failing prefix rules out every plan that extends it."""


def brute_force(s: Setup, rules: frozenset[str] | None = None) -> bool:
    """Is there a plan whose checks pass (for ``rules``, or for every rule)? Every plan is tried, day by day;
    prefixes that already break a prefix rule are skipped, the other rules are checked on whole plans."""
    day_choices = list(itertools.product(*(s.pools[pos] for pos in s.active)))
    pruning = PREFIX_RULES if rules is None else PREFIX_RULES & rules

    def ok(cells: tuple[int, ...], wanted: frozenset[str] | None) -> bool:
        return all(c.ok for c in s.checks(s.plan_days(cells)) if wanted is None or c.rule in wanted)

    def extend(cells: tuple[int, ...]) -> bool:
        if len(cells) == len(s.active) * s.req.days:
            return ok(cells, rules)
        return any(ok(cells + choice, pruning) and extend(cells + choice) for choice in day_choices)

    return extend(())


@pytest.mark.parametrize("seed", range(160))
def test_construction_finds_a_plan_exactly_when_one_exists(seed: int) -> None:
    rng = seeded(50_000 + seed)
    recipes: list[Recipe] = []
    req = tiny_request(rng, recipes)
    s = setup(recipes, req)
    cells = s.construct().solve(random.Random(seed), UNLIMITED)
    exists = brute_force(s)
    assert (cells is not None) == exists, (req, [r.id for r in recipes])
    if cells is not None:
        assert all(c.ok for c in s.checks(s.plan_days(cells)))


@pytest.mark.parametrize("seed", range(160))
def test_too_small_warnings_are_right(seed: int) -> None:
    """A slot_pool_too_small warning claims that no plan keeps the variety rule together with the sweets cap and
    the potato rule (each counted only where the analysis does not already call it impossible)."""
    rng = seeded(60_000 + seed)
    recipes: list[Recipe] = []
    req = tiny_request(rng, recipes)
    s = setup(recipes, req)
    if not s.analysis.too_small:
        return
    rules = {"variety"}
    if not any("sweets" in dead for dead in s.analysis.hopeless):
        rules.add("sweets")
    if not s.analysis.potato_hopeless:
        rules.add("potato")
    assert not brute_force(s, frozenset(rules)), (req, [r.id for r in recipes], s.analysis.warnings)


def near_floor_request(rng: random.Random, recipes_out: list[Recipe]) -> PlanRequest:
    """A one-slot request near the sweets floor (a snack slot, a few plain and some sweet recipes) or the potato
    floor (a main slot, a few potato-free and some potato recipes)."""
    days = rng.randint(4, 7)
    if rng.random() < 0.5:
        slot: Slot = rng.choice(("tizorai", "uzsonna"))
        marked, marked_tags, window = [("cukor", "0.1")], ["edes"], rng.choice((2, 3, 5))
    else:
        slot = rng.choice(("reggeli", "ebed", "vacsora"))
        marked, marked_tags, window = [("burgonya", "0.4")], [], rng.choice((3, 4, 5))
    bases = ("hal", "lencse", "turo", "rizs", "tejfol")
    for i in range(rng.randint(1, 2)):
        extra = ["ket_napos"] if rng.random() < 0.3 else []
        recipes_out.append(recipe(f"sima-{i}", (slot,), [(rng.choice(bases), "0.2")], extra_tags=extra))
    for i in range(rng.randint(1, 3)):
        extra = marked_tags + (["ket_napos"] if rng.random() < 0.3 else [])
        lines = [*marked, (rng.choice(bases), "0.1")]
        recipes_out.append(recipe(f"jelolt-{i}", (slot,), lines, extra_tags=extra))
    return request(days, (slot,), no_repeat_days=window, seed=rng.randint(0, 999))


@pytest.mark.parametrize("seed", range(120))
def test_too_small_warnings_near_the_joint_floors_are_right(seed: int) -> None:
    rng = seeded(70_000 + seed)
    recipes: list[Recipe] = []
    s = setup(recipes, near_floor_request(rng, recipes))
    exists = brute_force(s, PREFIX_RULES)
    assert not (s.analysis.too_small and exists), (s.req, [r.id for r in recipes], s.analysis.warnings)


def test_brute_force_cases_cover_the_joint_warnings() -> None:
    """The near-floor requests do reach the sweets and potato floors, not only the plain Hall check, and most of
    the plans the floors rule out are ruled out by them alone."""
    joint = 0
    for seed in range(120):
        rng = seeded(70_000 + seed)
        recipes: list[Recipe] = []
        s = setup(recipes, near_floor_request(rng, recipes))
        joint += bool(s.analysis.too_small - s.hall_slots())
    assert joint >= 20
