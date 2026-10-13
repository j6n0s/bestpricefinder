"""Pure pricing engine (docs/ENGINE.md ``bpf.pricing``): no I/O, no DB, no clock, no randomness.

Re-exports every domain type from :mod:`bpf.pricing.model` and every engine function named in ENGINE.md.
"""

from bpf.pricing.history import ingredient_history
from bpf.pricing.listing import build_list
from bpf.pricing.matching import candidate_products
from bpf.pricing.model import (
    SLOTS_3,
    SLOTS_5,
    Availability,
    Catalogue,
    Chain,
    ChainPrice,
    ChainRecipeCost,
    Ingredient,
    IngredientTag,
    KshPrice,
    LinePick,
    LineStatus,
    ListLine,
    NutritionPerServing,
    NutritionRow,
    PackOption,
    Plan,
    PlanDay,
    PlanRequest,
    PriceScope,
    PriceType,
    Product,
    QuoteLine,
    Recipe,
    RecipeLine,
    RecipeTag,
    ResolvedPrice,
    RuleCheck,
    Slot,
    SplitSuggestion,
    Store,
    StorePrice,
    StoreQuote,
    StoreRank,
    Unit,
    fold_name,
)
from bpf.pricing.nutrition import nutrition_per_serving
from bpf.pricing.packs import optimise_packs, pack_options
from bpf.pricing.prices import resolve_price
from bpf.pricing.quote import quote_store
from bpf.pricing.ranking import rank_stores, suggest_split, whole_forints
from bpf.pricing.recipes import recipe_chain_costs
from bpf.pricing.units import to_canonical

__all__ = [
    # engine functions (docs/ENGINE.md)
    "build_list",
    "candidate_products",
    "fold_name",
    "ingredient_history",
    "nutrition_per_serving",
    "optimise_packs",
    "pack_options",
    "quote_store",
    "rank_stores",
    "recipe_chain_costs",
    "resolve_price",
    "suggest_split",
    "to_canonical",
    "whole_forints",
    # domain types and vocabularies (bpf/pricing/model.py)
    "SLOTS_3",
    "SLOTS_5",
    "Availability",
    "Catalogue",
    "Chain",
    "ChainPrice",
    "ChainRecipeCost",
    "Ingredient",
    "IngredientTag",
    "KshPrice",
    "LinePick",
    "LineStatus",
    "ListLine",
    "NutritionPerServing",
    "NutritionRow",
    "PackOption",
    "Plan",
    "PlanDay",
    "PlanRequest",
    "PriceScope",
    "PriceType",
    "Product",
    "QuoteLine",
    "Recipe",
    "RecipeLine",
    "RecipeTag",
    "ResolvedPrice",
    "RuleCheck",
    "Slot",
    "SplitSuggestion",
    "Store",
    "StorePrice",
    "StoreQuote",
    "StoreRank",
    "Unit",
]
