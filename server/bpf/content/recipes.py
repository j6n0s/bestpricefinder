"""``data/recipes/*.json``: our original recipes, parsed into ``model.Recipe`` and validated (docs/DATA.md).

Rules, besides the column limits of ``app.recipe`` / ``app.recipe_line``:

* ids match ``^[a-z0-9-]{2,60}$`` and are unique across files; each file is sorted by id;
* ``slots`` is a non-empty subset of the five slots; ``servings`` 1..12; ``minutes`` 1..600;
* 1-60 lines (at least one not optional) and 1-20 steps of 10-600 characters;
* every line's ``ingredient_id`` exists; ``qty`` > 0 in the ingredient's canonical unit, with at most 3
  decimals (``numeric(10,3)`` would round anything finer); ``display`` 1-80 characters;
* tags come from the RecipeTag vocabulary and agree with the ingredients:
  - ``husmentes`` (and ``vegetarianus``): no line, optional or not, has a ``red_meat``, ``processed_meat``,
    ``poultry`` or ``fish`` ingredient; and conversely a recipe with no such line must be tagged
    ``husmentes`` (model.py: the tag is derived from the ingredients, and the planner's meat-free day needs
    every meal of the day tagged);
  - ``hal`` / ``huvelyes`` / ``baromfi``: at least one required line tagged ``fish`` / ``legume`` /
    ``poultry``; ``sertes`` and ``marha``: one tagged ``red_meat`` (the vocabulary has no pork or beef tag);
  - ``gyors``: ``minutes`` <= 25; ``olcso`` is computed by the app and never set by hand;
* no health-claim words in the title, summary, steps or line displays.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from bpf.content.errors import ContentError, Problems
from bpf.content.ingredients import as_decimal, check_keys, decimal_places, is_int, string_list
from bpf.content.jsonio import display_path, read_json
from bpf.content.vocab import (
    COMPUTED_RECIPE_TAGS,
    GYORS_MAX_MINUTES,
    MEAT_FISH_TAGS,
    RECIPE_ID_RE,
    RECIPE_TAGS,
    SLOTS,
    TAG_REQUIRES_LINE,
    health_claim_stems,
)
from bpf.pricing.model import Ingredient, Recipe, RecipeLine, Slot

RECIPE_KEYS: tuple[str, ...] = (
    "id",
    "title",
    "summary",
    "slots",
    "servings",
    "minutes",
    "tags",
    "lines",
    "steps",
    "tested",
)
LINE_KEYS: tuple[str, ...] = ("ingredient_id", "qty", "display", "optional")
TITLE_LENGTH = range(2, 121)  # app.recipe.title
MAX_SUMMARY_LENGTH = 400
SERVINGS_RANGE = range(1, 13)
MINUTES_RANGE = range(1, 601)
LINES_RANGE = range(1, 61)
STEPS_RANGE = range(1, 21)
STEP_LENGTH = range(10, 601)
MAX_DISPLAY_LENGTH = 80
QTY_MAX_PLACES = 3  # app.recipe_line.qty numeric(10,3)
QTY_LIMIT = Decimal(10_000_000)


def _text(value: object, lengths: range) -> str | None:
    """``value`` when it is a string within ``lengths`` and without surrounding whitespace, else None."""
    if isinstance(value, str) and value == value.strip() and len(value) in lengths:
        return value
    return None


def _length_rule(lengths: range) -> str:
    return f"must be a string of {lengths.start}-{lengths.stop - 1} characters without surrounding spaces"


def _claims(text: str, where: str, problems: Problems) -> None:
    if stems := health_claim_stems(text):
        problems.add(where, f"contains health-claim words ({', '.join(stems)}); none are allowed")


def _parse_line(
    obj: object, line_no: int, where: str, ingredients: Mapping[str, Ingredient], problems: Problems
) -> RecipeLine | None:
    if not check_keys(obj, LINE_KEYS, where, problems):
        return None
    line = cast(dict[str, Any], obj)
    before = len(problems)
    ingredient_id = line["ingredient_id"]
    if not isinstance(ingredient_id, str) or ingredient_id not in ingredients:
        problems.add(
            f"{where}.ingredient_id", f"{ingredient_id!r} is not an ingredient in data/ingredients.json"
        )
    qty = as_decimal(line["qty"])
    if qty is None or not 0 < qty < QTY_LIMIT:
        problems.add(f"{where}.qty", "must be a number greater than 0 (in the ingredient's canonical unit)")
    elif decimal_places(qty) > QTY_MAX_PLACES:
        problems.add(
            f"{where}.qty", f"{qty} has more than {QTY_MAX_PLACES} decimals (the database would round it)"
        )
    display = _text(line["display"], range(1, MAX_DISPLAY_LENGTH + 1))
    if display is None:
        problems.add(f"{where}.display", _length_rule(range(1, MAX_DISPLAY_LENGTH + 1)))
    else:
        _claims(display, f"{where}.display", problems)
    if not isinstance(line["optional"], bool):
        problems.add(f"{where}.optional", "must be true or false")
    if len(problems) > before or qty is None or display is None:
        return None
    return RecipeLine(
        line_no=line_no, ingredient_id=ingredient_id, qty=qty, display=display, optional=line["optional"]
    )


def _check_tags(
    tags: list[str],
    lines: list[RecipeLine],
    minutes: object,
    ingredients: Mapping[str, Ingredient],
    where: str,
    problems: Problems,
) -> None:
    meat_lines = [
        ln.ingredient_id for ln in lines if MEAT_FISH_TAGS.intersection(ingredients[ln.ingredient_id].tags)
    ]
    for tag in ("husmentes", "vegetarianus"):
        if tag in tags and meat_lines:
            problems.add(
                f"{where}.tags", f"{tag!r} but lines use meat or fish: {', '.join(sorted(set(meat_lines)))}"
            )
    if not meat_lines and "husmentes" not in tags:
        problems.add(f"{where}.tags", "no line uses meat or fish, so the recipe must be tagged 'husmentes'")
    required_tags = [set(ingredients[ln.ingredient_id].tags) for ln in lines if not ln.optional]
    for tag, ingredient_tag in TAG_REQUIRES_LINE.items():
        if tag in tags and not any(ingredient_tag in t for t in required_tags):
            problems.add(
                f"{where}.tags",
                f"{tag!r} needs a required line whose ingredient is tagged {ingredient_tag!r}",
            )
    if "gyors" in tags and is_int(minutes) and cast(int, minutes) > GYORS_MAX_MINUTES:
        problems.add(f"{where}.tags", f"'gyors' needs minutes <= {GYORS_MAX_MINUTES} (minutes is {minutes})")


def _parse_recipe(
    obj: dict[str, Any], where: str, ingredients: Mapping[str, Ingredient], problems: Problems
) -> Recipe | None:
    before = len(problems)
    recipe_id = obj["id"]
    if not isinstance(recipe_id, str) or not RECIPE_ID_RE.fullmatch(recipe_id):
        problems.add(f"{where}.id", f"{recipe_id!r} must match ^{RECIPE_ID_RE.pattern}$")
    title = _text(obj["title"], TITLE_LENGTH)
    if title is None:
        problems.add(f"{where}.title", _length_rule(TITLE_LENGTH))
    else:
        _claims(title, f"{where}.title", problems)
    summary = obj["summary"]
    if summary is not None:
        if _text(summary, range(1, MAX_SUMMARY_LENGTH + 1)) is None:
            problems.add(
                f"{where}.summary", "must be null or " + _length_rule(range(1, MAX_SUMMARY_LENGTH + 1))
            )
        else:
            _claims(summary, f"{where}.summary", problems)
    slots = string_list(obj["slots"], f"{where}.slots", problems) or []
    if not slots:
        problems.add(f"{where}.slots", f"must name at least one of {', '.join(SLOTS)}")
    for slot in slots:
        if slot not in SLOTS:
            problems.add(f"{where}.slots", f"{slot!r} is not one of {', '.join(SLOTS)}")
    servings = obj["servings"]
    if not is_int(servings) or servings not in SERVINGS_RANGE:
        problems.add(f"{where}.servings", "must be an integer from 1 to 12")
    minutes = obj["minutes"]
    if not is_int(minutes) or minutes not in MINUTES_RANGE:
        problems.add(f"{where}.minutes", "must be an integer from 1 to 600")
    tags = string_list(obj["tags"], f"{where}.tags", problems) or []
    for tag in tags:
        if tag not in RECIPE_TAGS:
            problems.add(f"{where}.tags", f"{tag!r} is not a recipe tag")
        elif tag in COMPUTED_RECIPE_TAGS:
            problems.add(f"{where}.tags", f"{tag!r} is computed by the app and must not be set by hand")

    raw_lines = obj["lines"]
    lines: list[RecipeLine] = []
    if not isinstance(raw_lines, list) or len(raw_lines) not in LINES_RANGE:
        problems.add(f"{where}.lines", "must be a list of 1-60 lines")
    else:
        for index, raw in enumerate(raw_lines):
            parsed = _parse_line(raw, index + 1, f"{where}.lines[{index}]", ingredients, problems)
            if parsed is not None:
                lines.append(parsed)
        if lines and len(lines) == len(raw_lines) and all(ln.optional for ln in lines):
            problems.add(f"{where}.lines", "at least one line must be required (optional: false)")
    raw_steps = obj["steps"]
    steps: list[str] = []
    if not isinstance(raw_steps, list) or len(raw_steps) not in STEPS_RANGE:
        problems.add(f"{where}.steps", "must be a list of 1-20 steps")
    else:
        for index, raw in enumerate(raw_steps):
            step = _text(raw, STEP_LENGTH)
            if step is None:
                problems.add(f"{where}.steps[{index}]", _length_rule(STEP_LENGTH))
                continue
            _claims(step, f"{where}.steps[{index}]", problems)
            steps.append(step)
    if not isinstance(obj["tested"], bool):
        problems.add(f"{where}.tested", "must be true or false")

    if len(problems) == before:  # tag consistency needs every line to be valid
        _check_tags(tags, lines, minutes, ingredients, where, problems)
    if len(problems) > before:
        return None
    ordered_slots = tuple(cast(Slot, s) for s in SLOTS if s in slots)
    return Recipe(
        id=recipe_id,
        title=cast(str, title),
        slots=ordered_slots,
        servings=servings,
        lines=tuple(lines),
        steps=tuple(steps),
        tags=tuple(tags),
        minutes=minutes,
        summary=summary,
        tested=obj["tested"],
    )


def parse_recipe_file(
    data: object, where: str, ingredients: Mapping[str, Ingredient], problems: Problems
) -> list[Recipe]:
    """Validate one parsed recipe file; problems are appended, valid recipes returned."""
    if not check_keys(data, ("version", "recipes"), where, problems):
        return []
    top = cast(dict[str, Any], data)
    if top["version"] != 1 or isinstance(top["version"], bool):
        problems.add(f"{where}.version", "must be 1")
    items = top["recipes"]
    if not isinstance(items, list):
        problems.add(f"{where}.recipes", "must be a list")
        return []
    recipes: list[Recipe] = []
    previous: str | None = None
    for index, obj in enumerate(items):
        label = obj.get("id") if isinstance(obj, dict) else None
        at = f"{where}.recipes[{index}]" + (f" ({label})" if isinstance(label, str) else "")
        if not check_keys(obj, RECIPE_KEYS, at, problems):
            continue
        recipe = _parse_recipe(cast(dict[str, Any], obj), at, ingredients, problems)
        if isinstance(label, str):
            if previous is not None and label < previous:
                problems.add(at, f"recipes must be sorted by id ({label!r} comes after {previous!r})")
            previous = label
        if recipe is not None:
            recipes.append(recipe)
    return recipes


def recipe_files(directory: Path) -> list[Path]:
    """``*.json`` files of the recipe directory in name order (dotfiles ignored)."""
    if not directory.is_dir():
        raise ContentError([f"{display_path(directory)}: recipe directory not found"])
    return sorted(
        (p for p in directory.iterdir() if p.suffix == ".json" and not p.name.startswith(".")),
        key=lambda p: p.name,
    )


def load_recipes(directory: Path, ingredients: Mapping[str, Ingredient]) -> dict[str, Recipe]:
    """Read and validate every recipe file: id -> Recipe in file order; raises :class:`ContentError`."""
    problems = Problems()
    result: dict[str, Recipe] = {}
    origin: dict[str, str] = {}
    for path in recipe_files(directory):
        where = display_path(path)
        if not path.is_file():
            problems.add(where, "is not a regular file")
            continue
        try:
            data = read_json(path)
        except ContentError as exc:
            for problem in exc.problems:
                problems.add("", problem)
            continue
        for recipe in parse_recipe_file(data, where, ingredients, problems):
            if recipe.id in result:
                problems.add(where, f"duplicate recipe id {recipe.id!r} (also in {origin[recipe.id]})")
                continue
            result[recipe.id] = recipe
            origin[recipe.id] = where
    problems.raise_if_any()
    return result
