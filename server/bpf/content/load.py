"""Load and validate every content file together (the loader validates everything before writing).

Public helpers for other packages and tests: :func:`load_ingredients`, :func:`load_recipes` (re-exported
from :mod:`bpf.content.recipes`), :func:`load_ksh` (from :mod:`bpf.content.ksh`) and :func:`load_content`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from bpf.content.errors import ContentError, Problems
from bpf.content.ingredients import IngredientRecord, read_ingredient_records
from bpf.content.ksh import load_ksh
from bpf.content.leaves import FoodLeaves, food_leaves_from_csv
from bpf.content.nutrition import load_nutrition
from bpf.content.paths import INGREDIENTS_PATH, KSH_PATH, LEAF_CATEGORIES_CSV, NUTRITION_PATH, ContentPaths
from bpf.content.recipes import load_recipes
from bpf.pricing.model import Ingredient, KshPrice, NutritionRow, Recipe


@dataclass(frozen=True, slots=True)
class Content:
    """Everything one load writes: validated and cross-checked."""

    ingredients: dict[str, IngredientRecord]  # id -> record, in file order (sorted by id)
    recipes: dict[str, Recipe]
    ksh: dict[str, KshPrice]
    nutrition: dict[str, NutritionRow]
    leaves_source: str

    def ingredient_map(self) -> dict[str, Ingredient]:
        return {ing_id: record.ingredient for ing_id, record in self.ingredients.items()}


def _collect(problems: Problems, error: ContentError) -> None:
    for problem in error.problems:
        problems.add("", problem)


def load_content(paths: ContentPaths | None = None, *, leaves: FoodLeaves | None = None) -> Content:
    """Read and validate the KSH file, the nutrition file, the ingredients and the recipes.

    ``leaves`` defaults to the research leaf list (the CLI passes ``core.category`` when the DB has it).
    Raises :class:`ContentError` with every problem found; stages that depend on a failed stage are
    skipped (their messages would only repeat the first failure)."""
    paths = paths if paths is not None else ContentPaths()
    problems = Problems()
    ksh: dict[str, KshPrice] = {}
    nutrition: dict[str, NutritionRow] = {}
    try:
        ksh = load_ksh(paths.ksh)
    except ContentError as exc:
        _collect(problems, exc)
    try:
        nutrition = load_nutrition(paths.nutrition, problems)
    except ContentError as exc:
        _collect(problems, exc)
    leaf_set = leaves
    if leaf_set is None:
        try:
            leaf_set = food_leaves_from_csv(paths.leaf_csv)
        except ContentError as exc:
            _collect(problems, exc)
    problems.raise_if_any()
    if leaf_set is None:  # pragma: no cover - raise_if_any() has raised the reason already
        raise ContentError(["no GVH leaf list"])

    records = read_ingredient_records(
        paths.ingredients, leaves=leaf_set, ksh=ksh, nutrition_codes=nutrition.keys()
    )
    ingredients = {record.ingredient.id: record for record in records}
    recipes = load_recipes(paths.recipes_dir, {k: r.ingredient for k, r in ingredients.items()})
    return Content(ingredients, recipes, ksh, nutrition, leaf_set.source)


def load_ingredients(
    path: Path = INGREDIENTS_PATH,
    *,
    leaves: FoodLeaves | None = None,
    ksh: Mapping[str, KshPrice] | None = None,
    nutrition_codes: Collection[str] | None = None,
) -> dict[str, Ingredient]:
    """Read and validate an ingredients file; returns id -> Ingredient (sorted by id).

    Cross-checks use the repository's own files unless given: the research leaf list, ``data/ksh/ara0044.csv``
    and ``data/nutrition/nutrition.json`` (absent = no nutrition codes)."""
    leaf_set = leaves if leaves is not None else food_leaves_from_csv(LEAF_CATEGORIES_CSV)
    ksh_rows = ksh if ksh is not None else load_ksh(KSH_PATH)
    if nutrition_codes is None:
        problems = Problems()
        codes: Collection[str] = load_nutrition(NUTRITION_PATH, problems).keys()
        problems.raise_if_any()
    else:
        codes = nutrition_codes
    records = read_ingredient_records(path, leaves=leaf_set, ksh=ksh_rows, nutrition_codes=codes)
    return {record.ingredient.id: record.ingredient for record in records}


__all__ = ["Content", "load_content", "load_ingredients", "load_ksh", "load_recipes"]
