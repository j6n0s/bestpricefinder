"""data/recipes/*.json: every validation rule (good and bad fixtures), tag consistency and health claims."""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bpf.content.errors import ContentError, Problems
from bpf.content.ksh import load_ksh
from bpf.content.load import load_ingredients
from bpf.content.recipes import load_recipes, parse_recipe_file
from bpf.pricing import Recipe, RecipeLine

FIXTURES = Path(__file__).parent / "fixtures" / "content"
INGREDIENTS = load_ingredients(
    FIXTURES / "ingredients.json", ksh=load_ksh(FIXTURES / "ksh.csv"), nutrition_codes=()
)
STEP = "A hagymát vágd apróra, és párold üvegesre."


def line(
    ingredient_id: str = "lencse", qty: Any = Decimal("0.4"), *, optional: bool = False
) -> dict[str, Any]:
    return {"ingredient_id": ingredient_id, "qty": qty, "display": "40 dkg", "optional": optional}


def recipe(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "lencse-teszt",
        "title": "Lencse teszt",
        "summary": "Rövid leírás.",
        "slots": ["ebed"],
        "servings": 4,
        "minutes": 40,
        "tags": ["fozelek", "huvelyes", "husmentes"],
        "lines": [line(), line("so", Decimal("0.005"))],
        "steps": [STEP],
        "tested": False,
    }
    item.update(overrides)
    return item


def problems_of(*recipes: Any, top: Any = None) -> list[str]:
    problems = Problems()
    data = top if top is not None else {"version": 1, "recipes": list(recipes)}
    parse_recipe_file(data, "r.json", INGREDIENTS, problems)
    return list(problems.items)


def assert_problem(expected: str, *recipes: Any, top: Any = None) -> None:
    found = problems_of(*recipes, top=top)
    assert any(expected in p for p in found), found


# ───────────────────────────── good fixtures ─────────────────────────────


def test_fixture_recipes_load_into_domain_objects() -> None:
    recipes = load_recipes(FIXTURES / "recipes", INGREDIENTS)
    assert list(recipes) == ["csirke-gombaval", "lencse-tojassal", "sult-lazac"]  # files in name order
    lencse = recipes["lencse-tojassal"]
    assert isinstance(lencse, Recipe)
    assert lencse.lines[2] == RecipeLine(line_no=3, ingredient_id="tojas", qty=Decimal(4), display="4 db")
    assert lencse.lines[0].qty == Decimal("0.4")
    assert recipes["sult-lazac"].lines[3].optional
    assert recipes["csirke-gombaval"].slots == ("ebed", "vacsora")


@pytest.mark.parametrize(
    "item",
    [
        recipe(),
        recipe(slots=["vacsora", "reggeli"]),  # stored in canonical slot order
        recipe(summary=None, minutes=600, servings=12),
        recipe(tags=["husmentes", "vegetarianus", "gyors", "edes"], minutes=25),
        recipe(tags=["foetel", "baromfi"], lines=[line("csirkemell", Decimal("0.5"))]),
        recipe(tags=["foetel", "hal"], lines=[line("lazac"), line("kapor", Decimal("0.01"), optional=True)]),
        recipe(tags=["foetel", "sertes"], lines=[line("sertescomb")]),
        recipe(tags=["foetel", "marha"], lines=[line("sertescomb")]),  # no beef tag: needs a red_meat line
        recipe(tags=["foetel"], lines=[line("csirkemell"), line("lencse")]),  # meat without husmentes: fine
        recipe(lines=[line("lencse", 1), line("tojas", 4)]),
        recipe(lines=[line("lencse", Decimal("0.001"))]),
        recipe(steps=["x" * 10, "y" * 600] + [STEP] * 18),
        recipe(lines=[line()] * 60),
        recipe(title="Ab", summary="x" * 400),
    ],
)
def test_good_recipes(item: dict[str, Any]) -> None:
    assert problems_of(item) == []


def test_slots_are_stored_in_canonical_order() -> None:
    problems = Problems()
    [parsed] = parse_recipe_file(
        {"version": 1, "recipes": [recipe(slots=["vacsora", "reggeli"])]}, "r", INGREDIENTS, problems
    )
    assert parsed.slots == ("reggeli", "vacsora")


# ───────────────────────────── bad fixtures ─────────────────────────────


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"id": "Lencse"}, "must match"),
        ({"id": "lencse_teszt"}, "must match"),
        ({"id": "l"}, "must match"),
        ({"id": "x" * 61}, "must match"),
        ({"title": "L"}, "title: must be a string of 2-120"),
        ({"title": "x" * 121}, "title: must be a string of 2-120"),
        ({"title": " Lencse"}, "title: must be a string of 2-120"),
        ({"summary": "x" * 401}, "summary: must be null or"),
        ({"summary": ""}, "summary: must be null or"),
        ({"slots": []}, "must name at least one of"),
        ({"slots": ["brunch"]}, "'brunch' is not one of"),
        ({"slots": ["ebed", "ebed"]}, "slots: contains duplicates"),
        ({"slots": "ebed"}, "slots: must be a list of strings"),
        ({"servings": 0}, "servings: must be an integer from 1 to 12"),
        ({"servings": 13}, "servings: must be an integer from 1 to 12"),
        ({"servings": Decimal("2.5")}, "servings: must be an integer"),
        ({"servings": True}, "servings: must be an integer"),
        ({"minutes": 0}, "minutes: must be an integer from 1 to 600"),
        ({"minutes": 601}, "minutes: must be an integer from 1 to 600"),
        ({"minutes": None}, "minutes: must be an integer"),
        ({"tags": ["finom"]}, "'finom' is not a recipe tag"),
        ({"tags": ["husmentes", "husmentes"]}, "tags: contains duplicates"),
        ({"tags": ["husmentes", "olcso"]}, "'olcso' is computed by the app"),
        ({"lines": []}, "must be a list of 1-60 lines"),
        ({"lines": [line()] * 61}, "must be a list of 1-60 lines"),
        ({"lines": [line(optional=True)]}, "at least one line must be required"),
        ({"lines": [line("unicorn")]}, "'unicorn' is not an ingredient"),
        ({"lines": [line(qty=0)]}, "qty: must be a number greater than 0"),
        ({"lines": [line(qty=Decimal("-1"))]}, "qty: must be a number greater than 0"),
        ({"lines": [line(qty="0.4")]}, "qty: must be a number greater than 0"),
        ({"lines": [line(qty=True)]}, "qty: must be a number greater than 0"),
        ({"lines": [line(qty=Decimal("0.0005"))]}, "more than 3 decimals"),
        ({"lines": [line(qty=Decimal("10000000"))]}, "qty: must be a number greater than 0"),
        ({"lines": [{**line(), "display": ""}]}, "display: must be a string of 1-80"),
        ({"lines": [{**line(), "display": "x" * 81}]}, "display: must be a string of 1-80"),
        ({"lines": [{**line(), "optional": "no"}]}, "optional: must be true or false"),
        ({"lines": [{"ingredient_id": "lencse", "qty": 1, "display": "x"}]}, "missing keys: optional"),
        ({"lines": [{**line(), "unit": "kg"}]}, "unknown keys: unit"),
        ({"steps": []}, "must be a list of 1-20 steps"),
        ({"steps": [STEP] * 21}, "must be a list of 1-20 steps"),
        ({"steps": ["Főzd meg."]}, "steps[0]: must be a string of 10-600"),  # 9 characters
        ({"steps": ["x" * 601]}, "steps[0]: must be a string of 10-600"),
        ({"steps": [STEP + " "]}, "steps[0]: must be a string of 10-600"),
        ({"steps": [5]}, "steps[0]: must be a string of 10-600"),
        ({"tested": "false"}, "tested: must be true or false"),
    ],
)
def test_bad_recipe(overrides: dict[str, Any], expected: str) -> None:
    assert_problem(expected, recipe(**overrides))


# ───────────────────────────── tag consistency ─────────────────────────────


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"tags": ["husmentes"], "lines": [line("csirkemell")]},
            "'husmentes' but lines use meat or fish: csirkemell",
        ),
        (
            {"tags": ["husmentes"], "lines": [line(), line("sertescomb", optional=True)]},
            "lines use meat or fish",
        ),
        ({"tags": ["husmentes"], "lines": [line(), line("lazac")]}, "lines use meat or fish: lazac"),
        (
            {"tags": ["husmentes", "vegetarianus"], "lines": [line("lazac")]},
            "'vegetarianus' but lines use meat",
        ),
        ({"tags": ["fozelek"]}, "must be tagged 'husmentes'"),  # derived: no meat or fish line
        (
            {"tags": ["hal"], "lines": [line("csirkemell")]},
            "'hal' needs a required line whose ingredient is tagged 'fish'",
        ),
        (
            {"tags": ["hal"], "lines": [line("csirkemell"), line("lazac", optional=True)]},
            "'hal' needs a required line",
        ),
        (
            {"tags": ["husmentes", "huvelyes"], "lines": [line("tojas", 2)]},
            "'huvelyes' needs a required line",
        ),
        ({"tags": ["baromfi"], "lines": [line("sertescomb")]}, "'baromfi' needs a required line"),
        (
            {"tags": ["sertes"], "lines": [line("csirkemell")]},
            "'sertes' needs a required line whose ingredient is tagged 'red_meat'",
        ),
        ({"tags": ["marha"], "lines": [line("lazac")]}, "'marha' needs a required line"),
        ({"tags": ["husmentes", "gyors"], "minutes": 26}, "'gyors' needs minutes <= 25 (minutes is 26)"),
    ],
)
def test_tag_consistency(overrides: dict[str, Any], expected: str) -> None:
    assert_problem(expected, recipe(**overrides))


# ───────────────────────────── health claims ─────────────────────────────

CLAIMS = ["egészséges", "Fogyaszt", "diétás", "méregtelenítő", "immunerősítő", "gyógyhatású", "betegség"]


@pytest.mark.parametrize("word", CLAIMS)
@pytest.mark.parametrize("field", ["title", "summary", "step", "display"])
def test_health_claim_words_are_rejected_everywhere(word: str, field: str) -> None:
    text = f"Lencse {word} módon"
    if field == "title":
        item = recipe(title=text)
    elif field == "summary":
        item = recipe(summary=text)
    elif field == "step":
        item = recipe(steps=[STEP, f"{text}, tálald melegen."])
    else:
        item = recipe(lines=[{**line(), "display": text}])
    assert_problem("health-claim words", item)


# ───────────────────────────── files ─────────────────────────────


@pytest.mark.parametrize(
    ("top", "expected"),
    [
        ({"version": 2, "recipes": []}, "version: must be 1"),
        ({"version": 1, "recipes": {}}, "recipes: must be a list"),
        ({"version": 1}, "missing keys: recipes"),
        ([], "must be a JSON object"),
        ({"version": 1, "recipes": ["x"]}, "must be a JSON object"),
    ],
)
def test_bad_recipe_file(top: Any, expected: str) -> None:
    assert_problem(expected, top=top)


def test_recipes_sorted_by_id_within_a_file() -> None:
    assert_problem("recipes must be sorted by id", recipe(id="b-recept"), recipe(id="a-recept"))
    assert problems_of(recipe(id="a-recept"), recipe(id="b-recept")) == []


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "recipes"
    shutil.copytree(FIXTURES / "recipes", target)
    return target


def test_duplicate_ids_across_files(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    (folder / "c.json").write_text(
        json.dumps({"version": 1, "recipes": [recipe(id="sult-lazac")]}, default=float)
    )
    with pytest.raises(ContentError, match="duplicate recipe id 'sult-lazac' \\(also in .*b.json\\)"):
        load_recipes(folder, INGREDIENTS)


def test_problems_from_several_files_are_reported_together(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    (folder / "c.json").write_bytes(b'{"version": 1, "recipes": [], "recipes": []}')
    (folder / "d.json").write_text(json.dumps({"version": 2, "recipes": []}))
    with pytest.raises(ContentError) as info:
        load_recipes(folder, INGREDIENTS)
    text = str(info.value)
    assert "c.json: invalid JSON: duplicate key 'recipes'" in text
    assert "d.json.version: must be 1" in text


def test_dotfiles_and_other_files_are_ignored(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    (folder / ".draft.json").write_text("not json")
    (folder / "notes.md").write_text("not json")
    (folder / ".gitkeep").write_text("")
    assert len(load_recipes(folder, INGREDIENTS)) == 3


def test_empty_and_missing_recipe_directories(tmp_path: Path) -> None:
    assert load_recipes(tmp_path, INGREDIENTS) == {}
    with pytest.raises(ContentError, match="recipe directory not found"):
        load_recipes(tmp_path / "missing", INGREDIENTS)


def test_real_recipe_directory_exists_and_validates() -> None:
    """data/recipes/ is filled by other work streams; whatever is there must validate against the ontology."""
    real_dir = Path(__file__).resolve().parents[2] / "data" / "recipes"
    assert real_dir.is_dir()
    load_recipes(real_dir, load_ingredients())  # raises ContentError listing every problem
