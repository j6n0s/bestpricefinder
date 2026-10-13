"""Coverage rule (BUILD-BRIEF §5, docs/DATA.md): every recipe needs >= 90 % of its estimated ingredient cost
in GVH-mapped ingredients.

Per recipe, each **required, non-pantry** line (the lines the engine prices for a recipe page; optional and
pantry lines are left out exactly as in ``bpf.pricing.recipe_chain_costs``) gets an estimated cost =
quantity × a unit price in the ingredient's canonical unit:

* GVH-mapped ingredients (``leaf_ids``): the latest DB chain prices when the DB has any for the ingredient
  (median over the grocery chains of each chain's cheapest chain-typical unit price, the same basis as the
  research), else the research reference price;
* other ingredients: their KSH ara0044 row when they have one, else the research reference price.

The research reference prices (``ingredient_reference_prices.csv``) are joined on the ingredient id, or on
the research key in :data:`REFERENCE_ALIASES` where our id differs.

``share`` = GVH-mapped cost / total cost; a recipe passes when share >= 0.90. Lines whose ingredient has no
price from any source are reported, and:

* a GVH-mapped line without a price is left out of both sums. Adding a GVH cost can only raise the share,
  so the share is then a **lower bound**: a recipe that passes on it passes for any price of that line;
* a non-GVH line without a price makes the recipe fail, because its share cannot be known.
"""

from __future__ import annotations

import csv
import io
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

import psycopg

from bpf.content.errors import ContentError
from bpf.content.jsonio import display_path
from bpf.content.ksh_convert import format_decimal
from bpf.pricing import (
    Catalogue,
    Chain,
    ChainPrice,
    Ingredient,
    KshPrice,
    Product,
    Recipe,
    candidate_products,
)
from bpf.pricing.model import fold_name

COVERAGE_THRESHOLD = Decimal("0.90")

REFERENCE_ALIASES: dict[str, str] = {
    "csemegekukorica": "kukorica_konzerv",
    "kapor": "friss_fuszernoveny",
    "kifli": "zsemle_egyeb",
    "omlesztett_sajt": "kremsajt",
    "petrezselyemzold": "friss_fuszernoveny",
    "teszta_tojasos": "teszta",
    "tv_paprika": "zoldpaprika",
}
"""Our ingredient id -> the research key whose reference price applies (ids equal research keys otherwise)."""

PriceSource = Literal["db", "reference", "ksh"]
_REFERENCE_COLUMNS = ("key", "cls", "unit", "price", "basis")


@dataclass(frozen=True, slots=True)
class ReferencePrice:
    key: str
    unit: str
    price: Decimal  # HUF per one ``unit``
    basis: str


@dataclass(frozen=True, slots=True)
class UnitPrice:
    """HUF per one canonical unit of an ingredient, and where it came from."""

    price: Decimal
    source: PriceSource


@dataclass(frozen=True, slots=True)
class LineCost:
    line_no: int
    ingredient_id: str
    gvh: bool
    cost: Decimal | None  # None: no price from any source


@dataclass(frozen=True, slots=True)
class RecipeCoverage:
    recipe_id: str
    gvh_cost: Decimal  # priced GVH-mapped lines only
    total_cost: Decimal  # every priced counted line
    missing: tuple[str, ...]  # ingredient ids without any price, in line order
    lines: tuple[LineCost, ...]
    threshold: Decimal = COVERAGE_THRESHOLD

    @property
    def missing_gvh(self) -> tuple[str, ...]:
        """GVH-mapped ingredients without a price: left out, so :attr:`share` is a lower bound."""
        return _unique(ln.ingredient_id for ln in self.lines if ln.gvh and ln.cost is None)

    @property
    def missing_other(self) -> tuple[str, ...]:
        """Non-GVH ingredients without a price: the share cannot be known, so the recipe fails."""
        return _unique(ln.ingredient_id for ln in self.lines if not ln.gvh and ln.cost is None)

    @property
    def lower_bound(self) -> bool:
        return bool(self.missing_gvh)

    @property
    def share(self) -> Decimal | None:
        """GVH-mapped share of the priced lines' cost; None when no counted line has a cost."""
        return self.gvh_cost / self.total_cost if self.total_cost > 0 else None

    @property
    def ok(self) -> bool:
        """Passes the rule. With no priced cost, every counted line is GVH-mapped (or there is none)."""
        if self.missing_other:
            return False
        return self.total_cost == 0 or self.gvh_cost >= self.threshold * self.total_cost


def _unique(ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(ids))


# ───────────────────────────── price sources ─────────────────────────────


def load_reference_prices(path: Path) -> dict[str, ReferencePrice]:
    """The research reference prices (key -> price per its unit). Raises :class:`ContentError`."""
    where = display_path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContentError([f"{where}: cannot read reference prices: {exc}"]) from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not set(_REFERENCE_COLUMNS) <= set(reader.fieldnames or ()):
        raise ContentError([f"{where}: expected columns {', '.join(_REFERENCE_COLUMNS)}"])
    result: dict[str, ReferencePrice] = {}
    for row in reader:
        try:
            price = Decimal(row["price"])
        except (ArithmeticError, TypeError) as exc:  # TypeError: a short row (missing price)
            raise ContentError([f"{where}: bad price {row['price']!r} for {row['key']!r}"]) from exc
        if row["unit"] not in ("kg", "l", "db") or not price.is_finite() or price < 0:
            raise ContentError([f"{where}: bad unit or price for {row['key']!r}"])
        result[row["key"]] = ReferencePrice(row["key"], row["unit"], price, row["basis"])
    return result


def per_canonical(price: Decimal, unit: str, unit_qty: Decimal, ing: Ingredient) -> Decimal | None:
    """HUF per canonical unit for ``price`` per ``unit_qty`` × ``unit``; None if not convertible.

    Same rules as the engine (db <-> kg through ``piece_weight_kg``, l <-> kg through ``density_kg_per_l``),
    arranged so that at most one division happens: kg prices for a db ingredient are multiplied by the
    piece weight (1200 Ft/kg × 0.06 kg = 72 Ft/db exactly)."""
    if unit_qty <= 0:
        return None
    weight, density = ing.piece_weight_kg, ing.density_kg_per_l
    if unit == ing.unit:
        return price / unit_qty
    if (ing.unit, unit) == ("db", "kg") and weight:
        return price * weight / unit_qty
    if (ing.unit, unit) == ("kg", "db") and weight:
        return price / (unit_qty * weight)
    if (ing.unit, unit) == ("l", "kg") and density:
        return price * density / unit_qty
    if (ing.unit, unit) == ("kg", "l") and density:
        return price / (unit_qty * density)
    return None


def reference_price(ing: Ingredient, refs: Mapping[str, ReferencePrice]) -> UnitPrice | None:
    ref = refs.get(REFERENCE_ALIASES.get(ing.id, ing.id))
    if ref is None or ref.price <= 0:
        return None
    value = per_canonical(ref.price, ref.unit, Decimal(1), ing)
    return UnitPrice(value, "reference") if value is not None else None


def ksh_price(ing: Ingredient, ksh: Mapping[str, KshPrice]) -> UnitPrice | None:
    row = ksh.get(ing.ksh_code) if ing.ksh_code else None
    if row is None:
        return None
    value = per_canonical(row.price, row.unit, row.unit_qty, ing)
    return UnitPrice(value, "ksh") if value is not None else None


def choose_prices(
    ingredients: Iterable[Ingredient],
    *,
    db_prices: Mapping[str, Decimal],
    refs: Mapping[str, ReferencePrice],
    ksh: Mapping[str, KshPrice],
) -> dict[str, UnitPrice]:
    """The unit price used for each ingredient (ingredients without any price are absent)."""
    chosen: dict[str, UnitPrice] = {}
    for ing in ingredients:
        price: UnitPrice | None
        if ing.leaf_ids:
            db = db_prices.get(ing.id)
            price = UnitPrice(db, "db") if db is not None else reference_price(ing, refs)
        else:
            price = ksh_price(ing, ksh) or reference_price(ing, refs)
        if price is not None:
            chosen[ing.id] = price
    return chosen


# ───────────────────────────── DB prices ─────────────────────────────


def _chain_typical(cp: ChainPrice) -> Decimal | None:
    """``product_min_amount``, else the XLSX price when min == max (the engine's chain-typical rule)."""
    if cp.product_min_amount is not None and cp.product_min_amount > 0:
        return cp.product_min_amount
    if cp.xlsx_min is not None and cp.xlsx_min > 0 and cp.xlsx_min == cp.xlsx_max:
        return cp.xlsx_min
    return None


def product_unit_price(product: Product, amount: Decimal, ing: Ingredient) -> Decimal | None:
    """HUF per canonical unit of a product priced ``amount`` (per pack, or per unit if sold by weight)."""
    packaging = product.packaging
    by_weight = product.unit_title is not None and fold_name(product.unit_title) == "kg"
    if packaging is None or packaging <= 0 or by_weight:
        return per_canonical(amount, product.unit, Decimal(1), ing)
    return per_canonical(amount, product.unit, packaging, ing)


def gvh_reference_prices(ingredients: Iterable[Ingredient], cat: Catalogue) -> dict[str, Decimal]:
    """Per GVH-mapped ingredient: median over grocery chains of the chain's cheapest canonical unit price."""
    chains = [c for c in cat.chains.values() if c.is_grocery]
    result: dict[str, Decimal] = {}
    for ing in ingredients:
        if not ing.leaf_ids:
            continue
        best: dict[str, Decimal] = {}
        for product in candidate_products(ing, cat):
            for chain in chains:
                cp = cat.chain_prices.get((product.id, chain.id))
                amount = _chain_typical(cp) if cp is not None else None
                unit_price = product_unit_price(product, amount, ing) if amount is not None else None
                if unit_price is not None and (chain.id not in best or unit_price < best[chain.id]):
                    best[chain.id] = unit_price
        if best:
            result[ing.id] = statistics.median(sorted(best.values()))
    return result


def db_prices(
    conn: psycopg.Connection, ingredients: Sequence[Ingredient]
) -> tuple[date | None, dict[str, Decimal]]:
    """Latest-data-date chain prices from the DB (as ``bpf_ingest``): (data date, ingredient -> unit price).

    Returns (None, {}) when no daily ingest has succeeded yet."""
    row = conn.execute("SELECT data_date FROM api.latest").fetchone()
    data_date = row[0] if row else None
    if data_date is None:
        return None, {}
    leaves = sorted({leaf for ing in ingredients for leaf in ing.leaf_ids})
    chains = {
        cid: Chain(id=cid, slug=slug, name=name, is_grocery=grocery)
        for cid, slug, name, grocery in conn.execute("SELECT id, slug, name, is_grocery FROM core.chain")
    }
    products: dict[str, Product] = {}
    by_leaf: dict[int, list[str]] = {}
    for pid, name, category_id, unit, unit_title, packaging in conn.execute(
        "SELECT id, name, category_id, unit, unit_title, packaging FROM core.product "
        "WHERE category_id = ANY(%s::integer[])",
        (leaves,),
    ):
        products[pid] = Product(pid, name, category_id, unit, unit_title, packaging)
        by_leaf.setdefault(category_id, []).append(pid)
    prices: dict[tuple[str, str], ChainPrice] = {}
    for pid, chain_id, pma, xmin, xmax in conn.execute(
        "SELECT product_id, chain_id, product_min_amount, xlsx_min, xlsx_max FROM core.product_chain_day "
        "WHERE data_date = %s AND product_id = ANY(%s::text[])",
        (data_date, sorted(products)),
    ):
        prices[(pid, chain_id)] = ChainPrice(
            pid, chain_id, product_min_amount=pma, xlsx_min=xmin, xlsx_max=xmax
        )
    cat = Catalogue(
        data_date=data_date,
        ingredients={ing.id: ing for ing in ingredients},
        products=products,
        chains=chains,
        stores={},
        chain_prices=prices,
        store_prices={},
        availability={},
        products_by_leaf={leaf: tuple(sorted(ids)) for leaf, ids in by_leaf.items()},
    )
    return data_date, gvh_reference_prices(ingredients, cat)


# ───────────────────────────── coverage ─────────────────────────────


def recipe_coverage(
    recipe: Recipe,
    ingredients: Mapping[str, Ingredient],
    prices: Mapping[str, UnitPrice],
    *,
    threshold: Decimal = COVERAGE_THRESHOLD,
) -> RecipeCoverage:
    gvh_cost = Decimal(0)
    total = Decimal(0)
    missing: dict[str, None] = {}
    lines: list[LineCost] = []
    for line in recipe.lines:
        ing = ingredients[line.ingredient_id]
        if line.optional or ing.pantry:
            continue
        price = prices.get(ing.id)
        cost = line.qty * price.price if price is not None else None
        gvh = bool(ing.leaf_ids)
        lines.append(LineCost(line.line_no, ing.id, gvh, cost))
        if cost is None:
            missing.setdefault(ing.id, None)
            continue
        total += cost
        if gvh:
            gvh_cost += cost
    return RecipeCoverage(recipe.id, gvh_cost, total, tuple(missing), tuple(lines), threshold)


def compute_coverage(
    recipes: Iterable[Recipe],
    ingredients: Mapping[str, Ingredient],
    prices: Mapping[str, UnitPrice],
    *,
    threshold: Decimal = COVERAGE_THRESHOLD,
) -> tuple[RecipeCoverage, ...]:
    """Coverage of every recipe, in the given order."""
    return tuple(recipe_coverage(r, ingredients, prices, threshold=threshold) for r in recipes)


def _percent(value: Decimal | None) -> str:
    return "n/a" if value is None else f"{(value * 100).quantize(Decimal('0.1'))}%"


def _ft(value: Decimal) -> str:
    return format_decimal(value.quantize(Decimal(1)))


def render_report(results: Sequence[RecipeCoverage], *, price_note: str, full: bool) -> str:
    """Text report: every recipe when ``full``, then the failing recipes and the unpriced ingredients."""
    out = [
        f"Coverage rule: >= {_percent(COVERAGE_THRESHOLD)} of each recipe's estimated cost in GVH-mapped "
        f"ingredients (required, non-pantry lines). Prices: {price_note}."
    ]
    if full:
        width = max([len(r.recipe_id) for r in results] + [6])
        out.append(f"{'recipe':<{width}}  {'share':>7}  {'GVH Ft':>8}  {'total Ft':>8}  status")
        for r in results:
            out.append(
                f"{r.recipe_id:<{width}}  {_percent(r.share):>7}  {_ft(r.gvh_cost):>8}  "
                f"{_ft(r.total_cost):>8}  {_status(r)}"
            )
    failing = [r for r in results if not r.ok]
    out.append(f"{len(results)} recipe(s), {len(failing)} failing.")
    out.extend(f"FAIL {r.recipe_id}: {_reason(r)}" for r in failing)
    gvh_unpriced = sorted({ing_id for r in results for ing_id in r.missing_gvh})
    other_unpriced = sorted({ing_id for r in results for ing_id in r.missing_other})
    if gvh_unpriced:
        out.append(
            "GVH-mapped ingredients without a price in the DB or the reference CSV (left out; the share is a "
            f"lower bound): {', '.join(gvh_unpriced)}"
        )
    if other_unpriced:
        out.append(
            "Non-GVH ingredients without a price in KSH or the reference CSV (their recipes fail): "
            f"{', '.join(other_unpriced)}"
        )
    return "\n".join(out)


def _status(r: RecipeCoverage) -> str:
    if r.missing_other:
        return "MISSING PRICE"
    status = "ok" if r.ok else "LOW"
    return f"{status} (lower bound)" if r.lower_bound else status


def _reason(r: RecipeCoverage) -> str:
    if r.missing_other:
        return f"no price for {', '.join(r.missing_other)} (not GVH-mapped, so the share is unknown)"
    reason = f"{_percent(r.share)} < {_percent(r.threshold)}"
    if r.lower_bound:
        reason += f" (lower bound: no price for {', '.join(r.missing_gvh)})"
    return reason
