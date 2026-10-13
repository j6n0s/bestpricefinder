"""HTTP request/response models for /api — the CONTRACT between bpf.api and web/.

docs/API.md describes the same contract in prose. The web client's TypeScript types are generated from
the OpenAPI document produced from these models (``web/src/lib/api/schema.d.ts``); never hand-edit them.

Rules
-----
* Every request model forbids unknown fields and bounds every list, string and number.
* Quantities arrive as JSON numbers and are quantised to 0.001 (ROUND_HALF_UP); NaN/Infinity are rejected.
* Responses carry money as JSON numbers in HUF rounded to 2 decimals, and quantities rounded to 3 decimals.
  The UI rounds money to whole forints for display.
* Chains are identified by ``slug`` (e.g. "lidl") in every request and response.
* Nothing here accepts coordinates or any personal identifier.
"""

from __future__ import annotations

import math
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

# ───────────────────────────── shared types ─────────────────────────────

IngredientId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{2,40}$")]
RecipeId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{2,60}$")]
StoreId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,40}$")]
ChainSlug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,30}$")]
Slot = Literal["reggeli", "tizorai", "ebed", "uzsonna", "vacsora"]
Unit = Literal["kg", "l", "db"]
PriceType = Literal["NORMAL", "DISCOUNTED", "LOYALTY"]
PriceScope = Literal["store", "chain"]
AvailabilityKind = Literal["confirmed", "assumed"]
LineStatus = Literal["priced", "pantry", "unavailable", "ksh_estimate", "unpriced"]
RecipeTag = Literal[
    "leves", "fozelek", "foetel", "koret", "salata", "reggeli_hideg", "reggeli_meleg", "snack",
    "husmentes", "vegetarianus", "hal", "huvelyes", "baromfi", "sertes", "marha",
    "edes", "gyors", "ket_napos", "olcso", "gyerekbarat",
]
RuleName = Literal["fish", "legume", "meat_free_day", "red_meat", "potato", "sweets", "variety", "budget"]

_QTY_STEP = Decimal("0.001")


def _to_qty(value: object, *, low: Decimal, high: Decimal) -> Decimal:
    """Number -> Decimal quantised to 0.001; rejects bool, NaN, Infinity and out-of-range values."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        raise ValueError("must be a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("must be finite")
    if isinstance(value, str) and len(value) > 20:
        raise ValueError("too long")
    try:
        dec = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("must be a number") from exc
    if not dec.is_finite():
        raise ValueError("must be finite")
    dec = dec.quantize(_QTY_STEP, rounding=ROUND_HALF_UP)
    if not (low < dec <= high):
        raise ValueError(f"must be > {low} and <= {high}")
    return dec


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


# ───────────────────────────── errors ─────────────────────────────

ErrorCode = Literal[
    "invalid_request", "not_found", "payload_too_large", "unsupported_media_type",
    "rate_limited", "no_data", "internal", "method_not_allowed",
]


class ErrorResponse(_Out):
    """Generic error body. Never echoes input values or internals."""

    error: ErrorCode
    fields: list[str] = Field(default_factory=list, description="dotted paths of invalid fields (422 only)")


# ───────────────────────────── /api/health, /api/meta ─────────────────────────────


class HealthResponse(_Out):
    status: Literal["ok", "degraded", "down"]
    db: bool
    data_date: dt.date | None


class ChainOut(_Out):
    id: str
    slug: ChainSlug
    name: str
    is_grocery: bool


class AttributionOut(_Out):
    text_hu: str
    text_en: str
    url: str
    license: str | None = None


class AttributionSet(_Out):
    gvh: AttributionOut
    ksh: AttributionOut
    nutrition: AttributionOut | None = None


class MetaResponse(_Out):
    data_date: dt.date | None
    ingested_at: dt.datetime | None
    stale: bool = Field(description="true when data_date is older than yesterday (Europe/Budapest)")
    ksh_period: dt.date | None
    chains: list[ChainOut]
    attribution: AttributionSet
    disclaimer_hu: str
    disclaimer_en: str


# ───────────────────────────── /api/stores ─────────────────────────────


class StoreOut(_Out):
    id: StoreId
    chain: ChainSlug
    postal_code: str | None
    city: str | None
    address: str | None
    lat: float | None
    lon: float | None
    format: Literal["hyper", "express", "other"] | None
    is_budapest: bool
    has_data: bool = Field(description="false when the store had no product on the latest data date")


class StoresResponse(_Out):
    data_date: dt.date | None
    stores: list[StoreOut]


# ───────────────────────────── /api/ingredients ─────────────────────────────


class IngredientOut(_Out):
    id: IngredientId
    name_hu: str
    list_group: str
    unit: Unit
    piece_weight_kg: float | None
    pantry: bool
    priced_by: Literal["gvh", "ksh", "none"]
    tags: list[str]


class IngredientsResponse(_Out):
    ingredients: list[IngredientOut]


# ───────────────────────────── /api/recipes ─────────────────────────────


class RecipeSummary(_Out):
    id: RecipeId
    title: str
    summary: str | None
    slots: list[Slot]
    servings: int
    minutes: int | None
    tags: list[str]
    tested: bool
    cost_per_serving_from: float | None = Field(
        description="cheapest chain-typical used cost per serving across grocery chains (HUF); null if unpriced"
    )
    cheapest_chain: ChainSlug | None
    priced_share: float = Field(ge=0, le=1, description="share of cost covered by priced lines at cheapest_chain")


class RecipesResponse(_Out):
    data_date: dt.date | None
    recipes: list[RecipeSummary]


class RecipeLineOut(_Out):
    line_no: int
    ingredient_id: IngredientId
    ingredient_name: str
    qty: float
    unit: Unit
    display: str
    optional: bool
    pantry: bool


class ChainCostOut(_Out):
    chain: ChainSlug
    cost_per_serving: float | None
    priced_share: float = Field(ge=0, le=1)
    missing: list[IngredientId]


class NutritionOut(_Out):
    kcal: float
    protein_g: float
    carb_g: float
    sugar_g: float
    fat_g: float
    satfat_g: float
    fiber_g: float
    salt_g: float
    coverage: float = Field(ge=0, le=1)


class RecipeDetail(RecipeSummary):
    data_date: dt.date | None
    steps: list[str]
    lines: list[RecipeLineOut]
    chain_costs: list[ChainCostOut]
    nutrition: NutritionOut | None = Field(description="per serving; null until composition data is imported")


# ───────────────────────────── /api/list ─────────────────────────────


class ListItemIn(_In):
    recipe_id: RecipeId
    servings: Decimal = Field(description="servings wanted (e.g. people × meals), 0 < servings <= 100")

    @field_validator("servings", mode="before")
    @classmethod
    def _servings(cls, v: object) -> Decimal:
        return _to_qty(v, low=Decimal(0), high=Decimal(100))


class QtyLineIn(_In):
    ingredient_id: IngredientId
    qty: Decimal = Field(description="in the ingredient's canonical unit, 0 < qty <= 1000")

    @field_validator("qty", mode="before")
    @classmethod
    def _qty(cls, v: object) -> Decimal:
        return _to_qty(v, low=Decimal(0), high=Decimal(1000))


class ListRequest(_In):
    items: list[ListItemIn] = Field(min_length=1, max_length=200)
    on_hand: list[QtyLineIn] = Field(default_factory=list, max_length=200)
    include_optional: bool = True


class ListLineOut(_Out):
    ingredient_id: IngredientId
    name_hu: str
    qty: float
    unit: Unit
    list_group: str
    pantry: bool
    recipe_ids: list[RecipeId]


class ListResponse(_Out):
    lines: list[ListLineOut]


# ───────────────────────────── /api/quote ─────────────────────────────


class QuoteRequest(_In):
    lines: list[QtyLineIn] = Field(min_length=1, max_length=200)
    store_ids: list[StoreId] = Field(min_length=1, max_length=25)
    include_loyalty: bool = False

    @model_validator(mode="after")
    def _unique(self) -> QuoteRequest:
        if len({line.ingredient_id for line in self.lines}) != len(self.lines):
            raise ValueError("duplicate ingredient_id in lines")
        if len(set(self.store_ids)) != len(self.store_ids):
            raise ValueError("duplicate store id")
        return self


class PackOptionOut(_Out):
    product_id: str
    product_name: str
    pack_size: float | None = Field(description="canonical units per pack; null = sold by weight")
    pack_price: float = Field(description="HUF per pack; for sold-by-weight items HUF per canonical unit")
    unit_price: float = Field(description="HUF per canonical unit")
    price_type: PriceType
    price_scope: PriceScope
    availability: AvailabilityKind


class PickOut(_Out):
    option: PackOptionOut
    count: int
    qty: float
    cost: float


class QuoteLineOut(_Out):
    ingredient_id: IngredientId
    qty: float
    unit: Unit
    status: LineStatus
    picks: list[PickOut]
    checkout_cost: float | None
    used_cost: float | None
    leftover_qty: float | None
    ksh_estimate: float | None
    alternatives: list[PackOptionOut]


class StoreQuoteOut(_Out):
    store_id: StoreId
    chain: ChainSlug
    checkout_total: float
    used_total: float
    missing: list[IngredientId]
    assumed_count: int
    ksh_estimate_total: float
    lines: list[QuoteLineOut]


class RankOut(_Out):
    store_id: StoreId
    rank: int
    checkout_total: float
    penalized_total: float
    missing_count: int


class SplitOut(_Out):
    store_ids: list[StoreId] = Field(min_length=2, max_length=2)
    total: float
    saving: float
    assignment: dict[str, StoreId]


class QuoteResponse(_Out):
    data_date: dt.date
    stores: list[StoreQuoteOut]
    ranking: list[RankOut]
    split: SplitOut | None
    scope_note_hu: str = Field(description='e.g. "a kiválasztott boltok közül, a 2026-10-13-i GVH-adatok alapján"')
    scope_note_en: str
    attribution: AttributionSet


# ───────────────────────────── /api/plan ─────────────────────────────


class PlanSuggestRequest(_In):
    days: int = Field(default=7, ge=1, le=31)
    slots: Literal[3, 5] = 3
    people: int = Field(default=2, ge=1, le=12)
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    exclude_tags: list[RecipeTag] = Field(default_factory=list, max_length=20)
    exclude_ingredients: list[IngredientId] = Field(default_factory=list, max_length=50)
    red_meat_g_per_person_week: int = Field(default=600, ge=0, le=3000)
    no_repeat_days: int = Field(default=5, ge=0, le=14)
    weekly_budget: int | None = Field(default=None, ge=0, le=1_000_000)


class PlanDayIO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0, le=30)
    meals: dict[Slot, RecipeId | None]


class PlanCheckRequest(_In):
    days: list[PlanDayIO] = Field(min_length=1, max_length=31)
    people: int = Field(default=2, ge=1, le=12)
    red_meat_g_per_person_week: int = Field(default=600, ge=0, le=3000)
    weekly_budget: int | None = Field(default=None, ge=0, le=1_000_000)


class RuleCheckOut(_Out):
    week: int
    rule: RuleName
    ok: bool
    value: str
    limit: str


class PlanResponse(_Out):
    days: list[PlanDayIO]
    checks: list[RuleCheckOut]
    warnings: list[str]


class PlanCheckResponse(_Out):
    checks: list[RuleCheckOut]


# ───────────────────────────── /api/ingredients/{id}/history ─────────────────────────────


class HistoryPoint(_Out):
    date: dt.date
    unit_price: float


class HistorySeries(_Out):
    chain: ChainSlug
    points: list[HistoryPoint]


class HistoryResponse(_Out):
    ingredient_id: IngredientId
    unit: Unit
    days: int
    series: list[HistorySeries]
