"""SYNTHETIC planner test data, built in code (no files under data/ are read).

Every ingredient, recipe, quantity and cost here is invented for tests: none of it is real product data,
real prices, or recipe text. Recipe "titles" are just their ids. Other planner tests import these builders;
the tests at the bottom check that the builders keep the recipe tag rules of docs/DATA.md.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal

from bpf.pricing.model import SLOTS_3, SLOTS_5, Ingredient, PlanDay, Recipe, RecipeLine, Slot

MEAT_TAGS = frozenset(("red_meat", "processed_meat", "poultry", "fish"))


def seeded(seed: int) -> random.Random:
    """Deterministic generator for synthetic test data."""
    return random.Random(seed)  # noqa: S311 - reproducible test data, not security


def _ing(
    iid: str,
    unit: str,
    tags: tuple[str, ...],
    perishable_days: int | None,
    *,
    piece: str | None = None,
    density: str | None = None,
) -> Ingredient:
    return Ingredient(
        id=iid,
        name_hu=iid,
        list_group="egyeb",
        unit=unit,  # type: ignore[arg-type]
        piece_weight_kg=None if piece is None else Decimal(piece),
        tags=tags,
        perishable_days=perishable_days,
        density_kg_per_l=None if density is None else Decimal(density),
    )


INGREDIENTS: Mapping[str, Ingredient] = {
    ing.id: ing
    for ing in (
        _ing("marha", "kg", ("red_meat",), 2),
        _ing("sertes", "kg", ("red_meat",), 3),
        _ing("kolbasz", "kg", ("processed_meat",), 30),
        _ing("virsli", "db", ("processed_meat",), 7, piece="0.05"),
        _ing("csirke", "kg", ("poultry",), 2),
        _ing("hal", "kg", ("fish",), 2),
        _ing("tojas", "db", ("egg",), 21, piece="0.06"),
        _ing("tejfol", "kg", ("dairy",), 7),
        _ing("turo", "kg", ("dairy",), 5),
        _ing("joghurt", "kg", ("dairy",), 6),
        _ing("tej", "l", ("dairy",), 8, density="1.03"),
        _ing("lencse", "kg", ("legume",), None),
        _ing("burgonya", "kg", ("potato", "vegetable"), 30),
        _ing("rizs", "kg", ("grain",), None),
        _ing("teszta", "kg", ("grain",), None),
        _ing("kenyer", "kg", ("wholegrain",), 3),
        _ing("paradicsom", "kg", ("vegetable",), 5),
        _ing("paprika", "kg", ("vegetable",), 5),
        _ing("uborka", "kg", ("vegetable",), 4),
        _ing("kaposzta", "kg", ("vegetable",), 14),
        _ing("alma", "kg", ("fruit",), 21),
        _ing("banan", "kg", ("fruit",), 5),
        _ing("cukor", "kg", ("sweet",), None),
        _ing("olaj", "l", ("fat_oil",), None),
    )
}


def recipe(
    rid: str,
    slots: Sequence[Slot],
    lines: Iterable[tuple[str, str]],
    *,
    extra_tags: Iterable[str] = (),
    servings: int = 4,
    optional: Iterable[str] = (),
    ingredients: Mapping[str, Ingredient] = INGREDIENTS,
) -> Recipe:
    """A synthetic recipe. ``lines`` = (ingredient id, qty in canonical unit). ``husmentes``, ``hal`` and
    ``huvelyes`` are derived from the ingredients like bpf.content does; ``extra_tags`` adds e.g. ``edes``."""
    optional_ids = set(optional)
    built = tuple(
        RecipeLine(line_no=n, ingredient_id=iid, qty=Decimal(qty), display=qty, optional=iid in optional_ids)
        for n, (iid, qty) in enumerate(lines, start=1)
    )
    ing_tags = {tag for line in built for tag in ingredients[line.ingredient_id].tags}
    tags = set(extra_tags)
    if not ing_tags & MEAT_TAGS:
        tags.add("husmentes")
    if "fish" in ing_tags:
        tags.add("hal")
    if "legume" in ing_tags:
        tags.add("huvelyes")
    return Recipe(
        id=rid, title=rid, slots=tuple(slots), servings=servings, lines=built, tags=tuple(sorted(tags))
    )


def plan_days(rows: Sequence[Mapping[Slot, str | None]], start: int = 0) -> tuple[PlanDay, ...]:
    """Hand-made plan: one mapping per day, indexes from ``start``."""
    return tuple(PlanDay(index=start + i, meals=dict(row)) for i, row in enumerate(rows))


def by_id(recipes: Iterable[Recipe]) -> dict[str, Recipe]:
    return {r.id: r for r in recipes}


# ───────────────────────────── libraries ─────────────────────────────

_MAIN_PROTEINS = ("marha", "sertes", "csirke", "hal", "lencse", "tojas", "virsli")
_SIDES = ("paradicsom", "paprika", "uborka", "burgonya", "rizs", "teszta", "tejfol", "kaposzta")


def rich_library(seed: int = 1, *, mains: int = 70, breakfasts: int = 30, snacks: int = 30) -> list[Recipe]:
    """A varied synthetic library in which every rule is satisfiable for 3 or 5 slots."""
    rng = seeded(seed)
    out: list[Recipe] = []
    for i in range(mains):
        protein = _MAIN_PROTEINS[i % len(_MAIN_PROTEINS)]
        qty = "4" if protein in ("tojas", "virsli") else rng.choice(("0.4", "0.5", "0.6"))
        sides = rng.sample(_SIDES, 2)
        slots: tuple[Slot, ...] = rng.choice((("ebed", "vacsora"), ("ebed",), ("vacsora",)))
        extra = ("ket_napos",) if rng.random() < 0.2 else ()
        out.append(
            recipe(f"main-{i:03d}", slots, [(protein, qty)] + [(s, "0.3") for s in sides], extra_tags=extra)
        )
    for i in range(breakfasts):
        topping = rng.sample(("tojas", "turo", "joghurt", "paradicsom", "paprika", "virsli", "tej"), 2)
        lines = [("kenyer", "0.2")] + [(t, "2" if t in ("tojas", "virsli") else "0.1") for t in topping]
        out.append(recipe(f"reggeli-{i:03d}", ("reggeli",), lines))
    for i in range(snacks):
        parts = rng.sample(("alma", "banan", "joghurt", "turo", "cukor", "kenyer"), 2)
        extra = ("edes",) if "cukor" in parts else ()
        out.append(
            recipe(f"snack-{i:03d}", ("tizorai", "uzsonna"), [(p, "0.2") for p in parts], extra_tags=extra)
        )
    return out


def random_library(rng: random.Random, max_recipes: int = 30) -> list[Recipe]:
    """A random synthetic library (possibly empty, possibly with tiny or one-sided pools)."""
    ids = sorted(INGREDIENTS)
    out: list[Recipe] = []
    for i in range(rng.randint(0, max_recipes)):
        slots = tuple(s for s in SLOTS_5 if rng.random() < 0.4) or (rng.choice(SLOTS_5),)
        chosen = rng.sample(ids, rng.randint(1, 4))
        lines = [
            (
                iid,
                str(rng.choice((1, 2, 3, 5, 8)))
                if INGREDIENTS[iid].unit == "db"
                else rng.choice(("0.05", "0.1", "0.25", "0.333", "0.5", "1")),
            )
            for iid in chosen
        ]
        optional = [iid for iid in chosen if rng.random() < 0.15]
        extra = [tag for tag, p in (("edes", 0.15), ("ket_napos", 0.2), ("gyors", 0.2)) if rng.random() < p]
        out.append(
            recipe(
                f"r-{i:03d}", slots, lines, extra_tags=extra, servings=rng.randint(1, 12), optional=optional
            )
        )
    return out


def random_costs(rng: random.Random, recipes: Iterable[Recipe], share: float = 0.85) -> dict[str, Decimal]:
    """Synthetic cost per serving (HUF, 2 decimals) for about ``share`` of the recipes."""
    return {r.id: Decimal(rng.randint(5000, 250000)) / 100 for r in recipes if rng.random() < share}


def random_slots(rng: random.Random) -> tuple[Slot, ...]:
    draw = rng.random()
    if draw < 0.4:
        return SLOTS_3
    if draw < 0.8:
        return SLOTS_5
    return tuple(s for s in SLOTS_5 if rng.random() < 0.5) or ("ebed",)


# ───────────────────────────── self-tests of the builders ─────────────────────────────


def _assert_tag_rules(r: Recipe) -> None:
    ing_tags = {tag for line in r.lines for tag in INGREDIENTS[line.ingredient_id].tags}
    assert ("husmentes" in r.tags) == (not ing_tags & MEAT_TAGS), r.id
    assert ("hal" in r.tags) == ("fish" in ing_tags), r.id
    assert ("huvelyes" in r.tags) == ("legume" in ing_tags), r.id
    assert 1 <= r.servings <= 12
    assert r.slots
    assert set(r.slots) <= set(SLOTS_5)


def test_rich_library_keeps_tag_rules() -> None:
    lib = rich_library()
    assert len({r.id for r in lib}) == len(lib) == 130
    for r in lib:
        _assert_tag_rules(r)


def test_random_libraries_keep_tag_rules() -> None:
    for seed in range(50):
        lib = random_library(seeded(seed))
        assert len({r.id for r in lib}) == len(lib)
        for r in lib:
            _assert_tag_rules(r)


def test_ingredient_units_are_convertible() -> None:
    for ing in INGREDIENTS.values():
        assert ing.unit in ("kg", "db", "l")
        if ing.unit == "db":
            assert ing.piece_weight_kg is not None
