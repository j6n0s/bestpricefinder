"""Default locations of the content files and of the research files the loader falls back on."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bpf.config import REPO_ROOT

DATA_DIR: Path = REPO_ROOT / "data"
INGREDIENTS_PATH: Path = DATA_DIR / "ingredients.json"
RECIPES_DIR: Path = DATA_DIR / "recipes"
KSH_PATH: Path = DATA_DIR / "ksh" / "ara0044.csv"
KSH_SOURCE_PATH: Path = DATA_DIR / "ksh" / "SOURCE.md"
#: The original ara0044 file from ksh.hu (fetched 2026-10-14 by a local session), the seed's input.
KSH_RAW_PATH: Path = DATA_DIR / "ksh" / "raw" / "ara0044.csv"
NUTRITION_PATH: Path = DATA_DIR / "nutrition" / "nutrition.json"

#: GVH leaf list of 2026-10-12, used to check ``leaf_ids`` when the DB has no categories (docs/DATA.md).
LEAF_CATEGORIES_CSV: Path = (
    REPO_ROOT / "research" / "gap-gvh-promo-and-stability" / "data" / "leaf_categories.csv"
)
#: Research reference prices per canonical ingredient key, the coverage report's fallback price source.
REFERENCE_PRICES_CSV: Path = (
    REPO_ROOT / "research" / "gap-healthy-plan-priceability" / "data" / "ingredient_reference_prices.csv"
)
#: The KSH ara0044 copy made by the research (seed of data/ksh/ara0044.csv while ksh.hu is unreachable).
KSH_RESEARCH_CSV: Path = (
    REPO_ROOT / "research" / "alt-price-sources" / "data" / "ksh_ara0044_latest_avg_prices.csv"
)


@dataclass(frozen=True, slots=True)
class ContentPaths:
    """Every input of one content load. The defaults are the repository's own files."""

    ingredients: Path = INGREDIENTS_PATH
    recipes_dir: Path = RECIPES_DIR
    ksh: Path = KSH_PATH
    nutrition: Path = NUTRITION_PATH  # optional: a missing file means "no composition data yet"
    leaf_csv: Path = LEAF_CATEGORIES_CSV
    reference_prices: Path = REFERENCE_PRICES_CSV
