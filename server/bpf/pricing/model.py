"""Domain model shared by ``bpf.pricing``, ``bpf.planner``, ``bpf.content`` and ``bpf.api``.

This module is the CONTRACT between those packages. Change it only together with every user.

Conventions
-----------
* Money is ``Decimal`` HUF (gross, as GVH publishes it). Never ``float`` inside the engine; the API layer
  converts to JSON numbers at the edge.
* Quantities are ``Decimal`` in the stated unit. A recipe line's ``qty`` is in its ingredient's canonical
  unit (``Ingredient.unit``), for the recipe's own ``servings``.
* Everything here is pure data: no I/O, no clock, no globals. Functions in ``bpf.pricing`` / ``bpf.planner``
  take these objects and return these objects, so they are unit-testable without a database.
* Product-name matching works on ``fold_name(name)``: lower-case, accents stripped (Tesco names arrive
  accent-less and upper-case, e.g. "FRISS CSIRKEMELL FILE PULTOS QQ"). Ingredient include/exclude regexes are
  therefore written in lower-case ASCII and matched with ``re.search`` against the folded name.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

Unit = Literal["kg", "l", "db"]
PriceType = Literal["NORMAL", "DISCOUNTED", "LOYALTY"]
PriceScope = Literal["store", "chain"]
Availability = Literal["confirmed", "assumed"]
"""``confirmed``: the store is in the product's latest ``availableInShops`` list or has a store price row.
``assumed``: no availability data for this product × chain; the chain sells it, so we assume the store
does."""

Slot = Literal["reggeli", "tizorai", "ebed", "uzsonna", "vacsora"]
SLOTS_3: tuple[Slot, ...] = ("reggeli", "ebed", "vacsora")
SLOTS_5: tuple[Slot, ...] = ("reggeli", "tizorai", "ebed", "uzsonna", "vacsora")

IngredientTag = Literal[
    "red_meat",
    "processed_meat",
    "poultry",
    "fish",
    "egg",
    "dairy",
    "legume",
    "vegetable",
    "fruit",
    "potato",
    "grain",
    "wholegrain",
    "nut_seed",
    "fat_oil",
    "sweet",
    "spice",
    "condiment",
]
"""Closed vocabulary, mirrored by the CHECK constraint in db/migrations/0002_ingredient_attrs.sql."""

RecipeTag = Literal[
    "leves",
    "fozelek",
    "foetel",
    "koret",
    "salata",
    "reggeli_hideg",
    "reggeli_meleg",
    "snack",
    "husmentes",
    "vegetarianus",
    "hal",
    "huvelyes",
    "baromfi",
    "sertes",
    "marha",
    "edes",
    "gyors",
    "ket_napos",
    "olcso",
    "gyerekbarat",
]
"""Closed vocabulary for ``Recipe.tags`` (validated by bpf.content). Descriptive only — never health claims.
``husmentes`` = contains no meat or fish ingredient (derived and checked by the content loader).
``ket_napos`` = intended to be cooked once and eaten on two consecutive days (the planner may repeat it).
``gyors`` = ``minutes <= 25``. ``olcso`` is computed, never hand-set."""

LineStatus = Literal["priced", "pantry", "unavailable", "ksh_estimate", "unpriced"]
"""Status of one shopping-list line at one store:
* ``priced``       — at least one matching product with a price at this store (``picks`` non-empty).
* ``pantry``       — ``Ingredient.pantry`` is true AND it has no GVH mapping (spices, salt…): never priced.
                     A pantry ingredient WITH ``leaf_ids`` (oil, flour…) is priced like any other line
                     whenever the client sends it; the client leaves pantry lines out of a quote unless
                     the user says they are not at home.
* ``unavailable``  — the ingredient is GVH-mapped, but no matching product is carried/priced at this store.
* ``ksh_estimate`` — the ingredient is not GVH-mapped (no ``leaf_ids``); a KSH national average exists.
* ``unpriced``     — not GVH-mapped and no KSH price ("nincs ár")."""


def fold_name(name: str) -> str:
    """Lower-case, strip accents (NFKD minus combining marks), collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


# ───────────────────────────── reference data ─────────────────────────────


@dataclass(frozen=True, slots=True)
class Ingredient:
    """Row of ``api.ingredient`` (app.ingredient). Canonical unit is ``unit``."""

    id: str
    name_hu: str
    list_group: str
    unit: Unit
    piece_weight_kg: Decimal | None = None
    pantry: bool = False
    leaf_ids: tuple[int, ...] = ()
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    product_units: tuple[str, ...] = ()
    ksh_code: str | None = None
    nutrition_code: str | None = None
    tags: tuple[str, ...] = ()
    perishable_days: int | None = None
    density_kg_per_l: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Product:
    """Row of ``api.product``. ``packaging`` is the pack size in ``unit`` (None when GVH gives none).

    ``unit_title`` is GVH's ``unitTitle``: ``"kg"`` marks loose goods sold by weight ("lédig", counter
    products; the price is per kg and the shopper buys the exact weight), ``"csomag"`` marks fixed packs."""

    id: str
    name: str
    category_id: int
    unit: str
    unit_title: str | None = None
    packaging: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Chain:
    id: str
    slug: str
    name: str
    is_grocery: bool


@dataclass(frozen=True, slots=True)
class Store:
    """Row of ``api.store`` plus the derived ``has_data`` (see docs/ENGINE.md for the rule)."""

    id: str
    chain_id: str
    lat: float | None = None
    lon: float | None = None
    format: str | None = None
    has_data: bool = True


@dataclass(frozen=True, slots=True)
class ChainPrice:
    """Row of ``api.product_chain_latest``: one product at one chain on the latest data date.

    ``product_min_amount`` is the daily price charged by ≥80 % of the chain's carrying stores (DISCOUNTED
    included, LOYALTY excluded) — the "typical chain price" GVH displays. ``normal_amount`` etc. are the
    MINIMUM across the chain's stores per price type and must NOT be used as the typical price (BUILD-BRIEF
    §4.1 trap 1)."""

    product_id: str
    chain_id: str
    product_min_amount: Decimal | None = None
    price_same_everywhere: bool | None = None
    normal_amount: Decimal | None = None
    discounted_amount: Decimal | None = None
    loyalty_amount: Decimal | None = None
    xlsx_min: Decimal | None = None
    xlsx_max: Decimal | None = None
    stores_carrying: int | None = None
    chain_store_count: int | None = None


@dataclass(frozen=True, slots=True)
class StorePrice:
    """Row of ``api.store_price_latest``: the real per-store price (fetched only where the chain varies)."""

    product_id: str
    store_id: str
    normal_amount: Decimal | None = None
    discounted_amount: Decimal | None = None
    loyalty_amount: Decimal | None = None


@dataclass(frozen=True, slots=True)
class KshPrice:
    """Row of ``api.ksh_latest`` normalised by the content loader: ``price`` HUF per ``unit_qty`` × ``unit``
    (e.g. eggs: unit ``db``, unit_qty 10). ``period`` is the first day of the month."""

    code: str
    name: str
    unit: Unit
    unit_qty: Decimal
    price: Decimal
    period: date


@dataclass(frozen=True, slots=True)
class NutritionRow:
    """Row of ``api.nutrition``: composition per 100 g edible part (CIQUAL / Frida / USDA)."""

    code: str
    source: Literal["ciqual", "frida", "usda"]
    name: str
    kcal: Decimal | None = None
    protein_g: Decimal | None = None
    carb_g: Decimal | None = None
    sugar_g: Decimal | None = None
    fat_g: Decimal | None = None
    satfat_g: Decimal | None = None
    fiber_g: Decimal | None = None
    salt_g: Decimal | None = None


@dataclass(frozen=True, slots=True)
class RecipeLine:
    line_no: int
    ingredient_id: str
    qty: Decimal
    display: str
    optional: bool = False


@dataclass(frozen=True, slots=True)
class Recipe:
    id: str
    title: str
    slots: tuple[Slot, ...]
    servings: int
    lines: tuple[RecipeLine, ...]
    steps: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    minutes: int | None = None
    summary: str | None = None
    tested: bool = False


@dataclass(frozen=True, slots=True)
class Catalogue:
    """Everything the engine needs for one data date, loaded once per data date by ``bpf.api.repo``.

    Only products in leaves referenced by some ingredient need to be present."""

    data_date: date | None
    ingredients: Mapping[str, Ingredient]
    products: Mapping[str, Product]
    chains: Mapping[str, Chain]
    stores: Mapping[str, Store]
    chain_prices: Mapping[tuple[str, str], ChainPrice]  # (product_id, chain_id)
    store_prices: Mapping[tuple[str, str], StorePrice]  # (product_id, store_id)
    availability: Mapping[tuple[str, str], frozenset[str]]  # (product_id, chain_id) -> store ids
    products_by_leaf: Mapping[int, tuple[str, ...]]
    ksh: Mapping[str, KshPrice] = field(default_factory=dict)
    recipes: Mapping[str, Recipe] = field(default_factory=dict)
    nutrition: Mapping[str, NutritionRow] = field(default_factory=dict)


# ───────────────────────────── engine outputs ─────────────────────────────


@dataclass(frozen=True, slots=True)
class ResolvedPrice:
    """The price of one product at one store, after the store-vs-chain rule (bpf.pricing.prices)."""

    product_id: str
    store_id: str
    amount: Decimal  # per pack; for variable-weight products: per product unit (e.g. Ft/kg)
    price_type: PriceType
    scope: PriceScope
    availability: Availability


@dataclass(frozen=True, slots=True)
class PackOption:
    """One buyable option for an ingredient at a store, in the ingredient's canonical unit."""

    product_id: str
    product_name: str
    size: Decimal | None  # canonical units per pack; None for variable weight (buy any quantity)
    price: Decimal  # per pack; for variable weight: per canonical unit
    unit_price: Decimal  # per canonical unit (for comparison and "used cost")
    price_type: PriceType
    scope: PriceScope
    availability: Availability

    @property
    def variable_weight(self) -> bool:
        return self.size is None


@dataclass(frozen=True, slots=True)
class LinePick:
    """``count`` packs of one option (variable weight: ``count`` is 1 and ``qty`` is the weight bought)."""

    option: PackOption
    count: int
    qty: Decimal  # canonical units bought with this pick
    cost: Decimal


@dataclass(frozen=True, slots=True)
class QuoteLine:
    ingredient_id: str
    qty: Decimal  # canonical units required
    status: LineStatus
    picks: tuple[LinePick, ...] = ()
    checkout_cost: Decimal | None = None  # whole packs actually paid at the till
    used_cost: Decimal | None = None  # qty × unit price of the chosen option(s)
    leftover_qty: Decimal | None = None  # canonical units bought beyond qty
    ksh_estimate: Decimal | None = None  # qty × KSH national average; ONLY for status ksh_estimate
    alternatives: tuple[PackOption, ...] = ()  # up to 3 other options at this store, cheapest checkout first


@dataclass(frozen=True, slots=True)
class StoreQuote:
    store_id: str
    lines: tuple[QuoteLine, ...]
    checkout_total: Decimal  # sum over priced lines
    used_total: Decimal
    missing: tuple[str, ...]  # ingredient ids with status unavailable
    assumed_count: int  # priced lines with at least one pick whose availability is only "assumed"
    ksh_estimate_total: Decimal  # sum of KSH estimates (labelled separately, never added to checkout_total)


@dataclass(frozen=True, slots=True)
class StoreRank:
    store_id: str
    rank: int  # 1 = best
    checkout_total: Decimal
    penalized_total: Decimal  # checkout_total + imputed cost of missing lines (median of other stores)
    missing_count: int


@dataclass(frozen=True, slots=True)
class SplitSuggestion:
    """Optional 2-store split, offered only when it saves at least the threshold vs the best single store."""

    store_ids: tuple[str, str]
    total: Decimal
    saving: Decimal
    assignment: Mapping[str, str]  # ingredient_id -> store_id


@dataclass(frozen=True, slots=True)
class ChainRecipeCost:
    """Chain-typical cost of one recipe (used quantities at ``product_min_amount``), for the recipe pages."""

    chain_id: str
    cost_per_serving: Decimal | None  # None when no line could be priced at this chain
    priced_share: Decimal  # 0..1, share of the recipe's estimated cost covered by priced lines
    missing: tuple[str, ...]  # ingredient ids (non-pantry) with no price at this chain


@dataclass(frozen=True, slots=True)
class ListLine:
    """Aggregated shopping-list line (bpf.pricing.listing.build_list)."""

    ingredient_id: str
    qty: Decimal  # canonical units, after subtracting on-hand quantities; > 0
    unit: Unit
    list_group: str
    pantry: bool
    recipe_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlanRequest:
    days: int  # 1..31
    slots: tuple[Slot, ...]  # SLOTS_3 or SLOTS_5 (any non-empty subset in this order is accepted)
    people: int  # 1..12
    seed: int
    exclude_tags: frozenset[str] = frozenset()
    exclude_ingredients: frozenset[str] = frozenset()
    red_meat_g_per_person_week: int = 600  # OKOSTÁNYÉR-style public principle (raw weight)
    no_repeat_days: int = 5
    weekly_budget: Decimal | None = None
    recipe_cost_per_serving: Mapping[str, Decimal] = field(default_factory=dict)  # for budget/olcsó bias


@dataclass(frozen=True, slots=True)
class RuleCheck:
    week: int  # 0-based week index (7-day blocks from day 0)
    rule: Literal["fish", "legume", "meat_free_day", "red_meat", "potato", "sweets", "variety", "budget"]
    ok: bool
    value: str  # human-readable measured value, e.g. "2 hal", "420 g/fő"
    limit: str  # e.g. "≥ 1", "≤ 600 g/fő"


@dataclass(frozen=True, slots=True)
class PlanDay:
    index: int
    meals: Mapping[Slot, str | None]  # slot -> recipe id (None when no eligible recipe exists)


@dataclass(frozen=True, slots=True)
class Plan:
    days: tuple[PlanDay, ...]
    checks: tuple[RuleCheck, ...]
    warnings: tuple[str, ...]  # machine codes, e.g. "no_fish_recipe_available", "slot_pool_too_small:tizorai"


@dataclass(frozen=True, slots=True)
class NutritionPerServing:
    kcal: Decimal
    protein_g: Decimal
    carb_g: Decimal
    sugar_g: Decimal
    fat_g: Decimal
    satfat_g: Decimal
    fiber_g: Decimal
    salt_g: Decimal
    coverage: Decimal  # 0..1 share of the recipe's non-pantry mass with composition data
