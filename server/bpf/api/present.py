"""Domain objects -> response models. Money and quantities stay ``Decimal`` until here; at the edge money is
rounded half-up to 0.01 HUF, quantities half-up to 0.001, shares DOWN to 0.0001 (a share is never overstated)
and only then converted to JSON numbers (docs/API.md "Numbers")."""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Context, Decimal
from typing import Literal

from bpf.api.repo import Snapshot, StoreInfo
from bpf.api.schemas import (
    ChainCostOut,
    IngredientOut,
    NutritionOut,
    PackOptionOut,
    PickOut,
    QuoteLineOut,
    RankOut,
    RecipeDetail,
    RecipeLineOut,
    RecipeSummary,
    RuleCheckOut,
    SplitOut,
    StoreOut,
    StoreQuoteOut,
)
from bpf.pricing import (
    Catalogue,
    Ingredient,
    LinePick,
    NutritionPerServing,
    PackOption,
    QuoteLine,
    Recipe,
    RuleCheck,
    SplitSuggestion,
    StoreQuote,
    StoreRank,
    nutrition_per_serving,
)

_CTX = Context(prec=60)
MONEY_STEP = Decimal("0.01")
QTY_STEP = Decimal("0.001")
SHARE_STEP = Decimal("0.0001")
NUTRIENT_STEP = Decimal("0.01")
STORE_FORMATS = frozenset({"hyper", "express", "other"})


def money(value: Decimal) -> float:
    return float(value.quantize(MONEY_STEP, rounding=ROUND_HALF_UP, context=_CTX))


def money_or_none(value: Decimal | None) -> float | None:
    return None if value is None else money(value)


def qty(value: Decimal) -> float:
    return float(value.quantize(QTY_STEP, rounding=ROUND_HALF_UP, context=_CTX))


def qty_or_none(value: Decimal | None) -> float | None:
    return None if value is None else qty(value)


def share(value: Decimal) -> float:
    clamped = min(max(value, Decimal(0)), Decimal(1))
    return float(clamped.quantize(SHARE_STEP, rounding=ROUND_DOWN, context=_CTX))


# ───────────────────────────── reference data ─────────────────────────────


def priced_by(ing: Ingredient, cat: Catalogue) -> Literal["gvh", "ksh", "none"]:
    """``gvh`` when GVH-mapped; ``ksh`` for a non-pantry ingredient with a usable KSH row; else ``none``
    (a pantry ingredient without leaves is never priced, docs/DATA.md)."""
    if ing.leaf_ids:
        return "gvh"
    if not ing.pantry and ing.ksh_code is not None:
        row = cat.ksh.get(ing.ksh_code)
        if row is not None and row.price > 0 and row.unit_qty > 0:
            return "ksh"
    return "none"


def ingredient_out(ing: Ingredient, cat: Catalogue) -> IngredientOut:
    return IngredientOut(
        id=ing.id,
        name_hu=ing.name_hu,
        list_group=ing.list_group,
        unit=ing.unit,
        piece_weight_kg=None if ing.piece_weight_kg is None else float(ing.piece_weight_kg),
        pantry=ing.pantry,
        priced_by=priced_by(ing, cat),
        tags=list(ing.tags),
    )


def store_out(info: StoreInfo) -> StoreOut:
    return StoreOut(
        id=info.id,
        chain=info.chain_slug,
        postal_code=info.postal_code,
        city=info.city,
        address=info.address,
        lat=info.lat,
        lon=info.lon,
        format=info.format if info.format in STORE_FORMATS else None,  # type: ignore[arg-type]
        is_budapest=info.is_budapest,
        has_data=info.has_data,
    )


# ───────────────────────────── recipes ─────────────────────────────


def recipe_summary(recipe: Recipe, snap: Snapshot) -> RecipeSummary:
    summary = snap.recipe_summaries.get(recipe.id)
    cheapest: list[str] = []
    cost = None
    priced_share = 0.0
    if summary is not None and summary.cost_per_serving_from is not None:
        cost = money(summary.cost_per_serving_from)
        cheapest = sorted(
            slug for cid in summary.cheapest_chain_ids if (slug := snap.chain_slug(cid)) is not None
        )
        priced_share = share(summary.priced_share)
    return RecipeSummary(
        id=recipe.id,
        title=recipe.title,
        summary=recipe.summary,
        slots=list(recipe.slots),
        servings=recipe.servings,
        minutes=recipe.minutes,
        tags=list(recipe.tags),
        tested=recipe.tested,
        cost_per_serving_from=cost,
        cheapest_chains=cheapest,
        priced_share=priced_share,
    )


def nutrition_out(value: NutritionPerServing | None) -> NutritionOut | None:
    if value is None:
        return None

    def n(amount: Decimal) -> float:
        return float(amount.quantize(NUTRIENT_STEP, rounding=ROUND_HALF_UP, context=_CTX))

    return NutritionOut(
        kcal=n(value.kcal),
        protein_g=n(value.protein_g),
        carb_g=n(value.carb_g),
        sugar_g=n(value.sugar_g),
        fat_g=n(value.fat_g),
        satfat_g=n(value.satfat_g),
        fiber_g=n(value.fiber_g),
        salt_g=n(value.salt_g),
        coverage=share(value.coverage),
    )


def recipe_detail(recipe: Recipe, snap: Snapshot) -> RecipeDetail:
    cat = snap.catalogue
    base = recipe_summary(recipe, snap)
    lines = []
    for line in sorted(recipe.lines, key=lambda line: line.line_no):
        ing = cat.ingredients[line.ingredient_id]
        lines.append(
            RecipeLineOut(
                line_no=line.line_no,
                ingredient_id=line.ingredient_id,
                ingredient_name=ing.name_hu,
                qty=qty(line.qty),
                unit=ing.unit,
                display=line.display,
                optional=line.optional,
                pantry=ing.pantry,
            )
        )
    chain_costs = []
    for cost in snap.recipe_costs.get(recipe.id, ()):
        slug = snap.chain_slug(cost.chain_id)
        if slug is None:  # pragma: no cover - costs are computed from the catalogue's chains
            continue
        chain_costs.append(
            ChainCostOut(
                chain=slug,
                cost_per_serving=money_or_none(cost.cost_per_serving),
                priced_share=share(cost.priced_share),
                missing=list(cost.missing),
            )
        )
    chain_costs.sort(key=lambda c: c.chain)
    return RecipeDetail(
        **base.model_dump(),
        data_date=snap.data_date,
        steps=list(recipe.steps),
        lines=lines,
        chain_costs=chain_costs,
        nutrition=nutrition_out(nutrition_per_serving(recipe, cat)),
    )


# ───────────────────────────── quote ─────────────────────────────


def pack_option_out(option: PackOption) -> PackOptionOut:
    return PackOptionOut(
        product_id=option.product_id,
        product_name=option.product_name,
        pack_size=qty_or_none(option.size),
        pack_price=money(option.price),
        unit_price=money(option.unit_price),
        price_type=option.price_type,
        price_scope=option.scope,
        availability=option.availability,
    )


def pick_out(pick: LinePick) -> PickOut:
    return PickOut(
        option=pack_option_out(pick.option), count=pick.count, qty=qty(pick.qty), cost=money(pick.cost)
    )


def quote_line_out(line: QuoteLine, ing: Ingredient) -> QuoteLineOut:
    return QuoteLineOut(
        ingredient_id=line.ingredient_id,
        qty=qty(line.qty),
        unit=ing.unit,
        status=line.status,
        picks=[pick_out(p) for p in line.picks],
        checkout_cost=money_or_none(line.checkout_cost),
        used_cost=money_or_none(line.used_cost),
        leftover_qty=qty_or_none(line.leftover_qty),
        ksh_estimate=money_or_none(line.ksh_estimate),
        alternatives=[pack_option_out(o) for o in line.alternatives],
    )


def store_quote_out(quote: StoreQuote, chain_slug: str, cat: Catalogue) -> StoreQuoteOut:
    return StoreQuoteOut(
        store_id=quote.store_id,
        chain=chain_slug,
        checkout_total=money(quote.checkout_total),
        used_total=money(quote.used_total),
        missing=list(quote.missing),
        assumed_count=quote.assumed_count,
        ksh_estimate_total=money(quote.ksh_estimate_total),
        lines=[quote_line_out(line, cat.ingredients[line.ingredient_id]) for line in quote.lines],
    )


def rank_out(rank: StoreRank) -> RankOut:
    return RankOut(
        store_id=rank.store_id,
        rank=rank.rank,
        checkout_total=money(rank.checkout_total),
        penalized_total=money(rank.penalized_total),
        missing_count=rank.missing_count,
    )


def split_out(split: SplitSuggestion | None) -> SplitOut | None:
    if split is None:
        return None
    return SplitOut(
        store_ids=list(split.store_ids),
        total=money(split.total),
        saving=money(split.saving),
        assignment=dict(split.assignment),
    )


# ───────────────────────────── plan ─────────────────────────────


def rule_check_out(check: RuleCheck) -> RuleCheckOut:
    return RuleCheckOut(week=check.week, rule=check.rule, ok=check.ok, value=check.value, limit=check.limit)
