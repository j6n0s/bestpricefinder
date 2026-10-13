"""Closed vocabularies and the text and regex checks shared by the content validators (docs/DATA.md)."""

from __future__ import annotations

import re
from typing import get_args

from bpf.pricing.model import SLOTS_5, IngredientTag, RecipeTag, fold_name

UNITS: tuple[str, ...] = ("kg", "l", "db")

LIST_GROUPS: tuple[str, ...] = (
    "zoldseg_gyumolcs",
    "pekaru",
    "tejtermek_tojas",
    "hus_hal",
    "szaraz_tartos",
    "fagyasztott",
    "fuszer_olaj",
    "egyeb",
)
"""Shopping-list sections in shopping-list order (docs/DATA.md)."""

INGREDIENT_TAGS: frozenset[str] = frozenset(get_args(IngredientTag))
RECIPE_TAGS: frozenset[str] = frozenset(get_args(RecipeTag))
SLOTS: tuple[str, ...] = SLOTS_5

MEAT_FISH_TAGS: frozenset[str] = frozenset({"red_meat", "processed_meat", "poultry", "fish"})
"""Ingredient tags that make a recipe not ``husmentes``."""

RED_MEAT_TAGS: frozenset[str] = frozenset({"red_meat", "processed_meat"})
"""Tags the planner's red-meat rule weighs (bpf.planner), so such an ingredient must be weighable in kg."""

TAG_REQUIRES_LINE: dict[str, str] = {
    "hal": "fish",
    "huvelyes": "legume",
    "baromfi": "poultry",
    "sertes": "red_meat",
    "marha": "red_meat",
}
"""Recipe tag -> ingredient tag that at least one required (non-optional) line must carry. The vocabulary
has no separate pork or beef tag, so ``sertes`` and ``marha`` both need a ``red_meat`` line."""

GYORS_MAX_MINUTES = 25
COMPUTED_RECIPE_TAGS: frozenset[str] = frozenset({"olcso"})
"""Recipe tags that are computed by the app and must never be set by hand."""

INGREDIENT_ID_RE = re.compile(r"[a-z0-9_]{2,40}")
RECIPE_ID_RE = re.compile(r"[a-z0-9-]{2,60}")
KSH_CODE_RE = re.compile(r"[0-9A-Za-z.-]{1,20}")
"""Use with ``fullmatch`` (``$`` would also accept a trailing newline)."""

MAX_PATTERN_LENGTH = 120

HEALTH_CLAIM_STEMS: tuple[str, ...] = (
    "egeszseg",  # egészséges (docs/DATA.md), and every other form of egészség
    "fogyaszt",
    "dieta",
    "meregtelenit",
    "immun",
    "gyogy",
    "betegseg",
)
"""Forbidden word stems, matched case- and accent-insensitively (on ``fold_name``) as substrings.

These are the words docs/DATA.md lists ("egészséges", "fogyaszt", "diéta", "méregtelenít", "immun", "gyógy",
"betegség"); "egészséges" is checked through its stem "egészség", which also catches "egészségre",
"egészséget" and the like (BUILD-BRIEF §8.7: no health claims)."""


def health_claim_stems(text: str) -> list[str]:
    """The forbidden stems that occur in ``text`` (empty list = no health claim words)."""
    folded = fold_name(text)
    return [stem for stem in HEALTH_CLAIM_STEMS if stem in folded]


def pattern_problems(pattern: object) -> list[str]:
    """Problems with one include/exclude regex (empty list = acceptable).

    Patterns run with ``re.search`` on ``fold_name(product name)``, which is lower-case ASCII without
    accents and with single spaces. A pattern with an upper-case letter, an accent, a tab or a double space
    can therefore never match as intended; one that matches the empty string matches every name."""
    if not isinstance(pattern, str) or not pattern:
        return ["must be a non-empty string"]
    problems: list[str] = []
    if len(pattern) > MAX_PATTERN_LENGTH:
        problems.append(f"is {len(pattern)} characters long (max {MAX_PATTERN_LENGTH})")
    if not pattern.isascii():
        problems.append("must be ASCII: product names are accent-folded (write 'file', not 'filé')")
    if pattern != pattern.lower():
        problems.append("must be lower case: product names are case-folded (use [^0-9] instead of \\D)")
    if any(ch in pattern for ch in "\t\n\r\f\v") or "  " in pattern:
        problems.append("must not contain tabs, newlines or double spaces: folded names have single spaces")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        problems.append(f"does not compile: {exc}")
    else:
        if compiled.search("") is not None:
            problems.append("matches the empty string, so it would match every product name")
    return problems
