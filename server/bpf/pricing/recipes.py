"""Chain-typical recipe cost (ENGINE.md ``recipe_chain_costs``; the recipe pages, BUILD-BRIEF §6).

For every grocery chain (sorted by slug): each required line (pantry and optional lines excluded) is priced
at the cheapest canonical unit price among the ingredient's candidate products at that chain, using the
chain-typical price (``product_min_amount``; the XLSX price only when min == max; never LOYALTY), times the
line's quantity ("used cost"). No store or availability is involved: it is the typical chain price.

``priced_share`` = priced cost / (priced cost + estimated cost of the lines missing at this chain), where a
missing line's estimate is the median of the other grocery chains' cost for that line, else its KSH
estimate, else 0. It is 0 when both sums are 0.
"""

from __future__ import annotations

from decimal import Decimal

from bpf.pricing._num import ZERO, div, exact, median
from bpf.pricing.matching import candidate_products
from bpf.pricing.model import Catalogue, Chain, ChainRecipeCost, Ingredient, Recipe, RecipeLine
from bpf.pricing.packs import canonical_unit_price
from bpf.pricing.prices import chain_typical_amount
from bpf.pricing.quote import ksh_estimate


def chain_unit_prices(ing: Ingredient, cat: Catalogue, chains: list[Chain]) -> dict[str, Decimal]:
    """chain id -> cheapest chain-typical canonical unit price among the ingredient's candidates."""
    best: dict[str, Decimal] = {}
    if not ing.leaf_ids:
        return best
    for product in candidate_products(ing, cat):
        for chain in chains:
            cp = cat.chain_prices.get((product.id, chain.id))
            if cp is None:
                continue
            amount = chain_typical_amount(cp)
            if amount is None:
                continue
            unit_price = canonical_unit_price(product, amount, ing)
            if unit_price is None:
                continue
            current = best.get(chain.id)
            if current is None or unit_price < current:
                best[chain.id] = unit_price
    return best


def _required_lines(recipe: Recipe, cat: Catalogue) -> list[tuple[RecipeLine, Ingredient]]:
    lines = []
    for line in recipe.lines:
        ing = cat.ingredients[line.ingredient_id]  # KeyError: a recipe references an unknown ingredient
        if not line.optional and not ing.pantry:
            lines.append((line, ing))
    return lines


@exact
def recipe_chain_costs(recipe: Recipe, cat: Catalogue) -> tuple[ChainRecipeCost, ...]:
    """One ``ChainRecipeCost`` per grocery chain, sorted by chain slug."""
    if recipe.servings <= 0:
        raise ValueError(f"recipe {recipe.id!r} has servings {recipe.servings}")
    chains = sorted((c for c in cat.chains.values() if c.is_grocery), key=lambda c: (c.slug, c.id))
    lines = _required_lines(recipe, cat)
    line_costs: list[dict[str, Decimal]] = []
    estimates: list[Decimal | None] = []
    for line, ing in lines:
        prices = chain_unit_prices(ing, cat, chains)
        line_costs.append({chain_id: line.qty * price for chain_id, price in prices.items()})
        estimates.append(ksh_estimate(ing, line.qty, cat))

    results: list[ChainRecipeCost] = []
    for chain in chains:
        priced = ZERO
        any_priced = False
        estimated = ZERO
        missing: dict[str, None] = {}
        for (line, _), costs, ksh in zip(lines, line_costs, estimates, strict=True):
            cost = costs.get(chain.id)
            if cost is not None:
                priced += cost
                any_priced = True
                continue
            missing.setdefault(line.ingredient_id, None)
            others = [value for chain_id, value in costs.items() if chain_id != chain.id]
            if others:
                estimated += median(others)
            elif ksh is not None:
                estimated += ksh
        denominator = priced + estimated
        share = div(priced, denominator) if denominator > 0 else ZERO
        results.append(
            ChainRecipeCost(
                chain_id=chain.id,
                cost_per_serving=div(priced, recipe.servings) if any_priced else None,
                priced_share=share,
                missing=tuple(missing),
            )
        )
    return tuple(results)
