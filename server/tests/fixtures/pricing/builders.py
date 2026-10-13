"""Builders for SYNTHETIC pricing-engine test data (see README.md in this folder: nothing here is real)."""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal

from bpf.pricing.model import (
    Catalogue,
    Chain,
    ChainPrice,
    Ingredient,
    KshPrice,
    NutritionRow,
    Product,
    Recipe,
    RecipeLine,
    Store,
    StorePrice,
    Unit,
)

D = Decimal
DATA_DATE = date(2026, 10, 13)


def dec(value: str | int | Decimal | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def ingredient(
    ing_id: str,
    *,
    unit: Unit = "kg",
    leaf_ids: Sequence[int] = (),
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    product_units: Sequence[str] = (),
    piece_weight: str | None = None,
    density: str | None = None,
    pantry: bool = False,
    ksh_code: str | None = None,
    nutrition_code: str | None = None,
    list_group: str = "egyeb",
    name_hu: str | None = None,
    tags: Sequence[str] = (),
) -> Ingredient:
    return Ingredient(
        id=ing_id,
        name_hu=name_hu or ing_id,
        list_group=list_group,
        unit=unit,
        piece_weight_kg=dec(piece_weight),
        pantry=pantry,
        leaf_ids=tuple(leaf_ids),
        include_patterns=tuple(include),
        exclude_patterns=tuple(exclude),
        product_units=tuple(product_units),
        ksh_code=ksh_code,
        nutrition_code=nutrition_code,
        tags=tuple(tags),
        density_kg_per_l=dec(density),
    )


def product(
    product_id: str,
    name: str,
    leaf: int,
    *,
    unit: str = "kg",
    unit_title: str | None = "csomag",
    packaging: str | None = "1",
) -> Product:
    return Product(product_id, name, leaf, unit, unit_title, dec(packaging))


def chain(slug: str, *, grocery: bool = True) -> Chain:
    return Chain(id=f"chain-{slug}", slug=slug, name=slug.capitalize(), is_grocery=grocery)


def store(store_id: str, chain_slug: str, *, has_data: bool = True) -> Store:
    return Store(id=store_id, chain_id=f"chain-{chain_slug}", has_data=has_data)


def chain_price(
    product_id: str,
    chain_slug: str,
    pma: str | int | None = None,
    *,
    normal: str | int | None = None,
    discounted: str | int | None = None,
    loyalty: str | int | None = None,
    same: bool | None = None,
    xlsx_min: str | int | None = None,
    xlsx_max: str | int | None = None,
) -> ChainPrice:
    return ChainPrice(
        product_id=product_id,
        chain_id=f"chain-{chain_slug}",
        product_min_amount=dec(pma),
        price_same_everywhere=same,
        normal_amount=dec(normal),
        discounted_amount=dec(discounted),
        loyalty_amount=dec(loyalty),
        xlsx_min=dec(xlsx_min),
        xlsx_max=dec(xlsx_max),
    )


def store_price(
    product_id: str,
    store_id: str,
    *,
    normal: str | int | None = None,
    discounted: str | int | None = None,
    loyalty: str | int | None = None,
) -> StorePrice:
    return StorePrice(product_id, store_id, dec(normal), dec(discounted), dec(loyalty))


def recipe(recipe_id: str, servings: int, lines: Iterable[tuple[str, str] | tuple[str, str, bool]]) -> Recipe:
    built = []
    for number, spec in enumerate(lines, start=1):
        optional = len(spec) == 3 and bool(spec[2])
        built.append(RecipeLine(number, spec[0], Decimal(spec[1]), display=spec[1], optional=optional))
    return Recipe(id=recipe_id, title=recipe_id, slots=("ebed",), servings=servings, lines=tuple(built))


def catalogue(
    *,
    ingredients: Iterable[Ingredient] = (),
    products: Iterable[Product] = (),
    chains: Iterable[Chain] = (),
    stores: Iterable[Store] = (),
    chain_prices: Iterable[ChainPrice] = (),
    store_prices: Iterable[StorePrice] = (),
    availability: Mapping[tuple[str, str], Iterable[str]] | None = None,
    ksh: Iterable[KshPrice] = (),
    recipes: Iterable[Recipe] = (),
    nutrition: Iterable[NutritionRow] = (),
) -> Catalogue:
    product_map = {p.id: p for p in products}
    by_leaf: dict[int, list[str]] = {}
    for p in product_map.values():
        by_leaf.setdefault(p.category_id, []).append(p.id)
    return Catalogue(
        data_date=DATA_DATE,
        ingredients={i.id: i for i in ingredients},
        products=product_map,
        chains={c.id: c for c in chains},
        stores={s.id: s for s in stores},
        chain_prices={(cp.product_id, cp.chain_id): cp for cp in chain_prices},
        store_prices={(sp.product_id, sp.store_id): sp for sp in store_prices},
        availability={key: frozenset(ids) for key, ids in (availability or {}).items()},
        products_by_leaf={leaf: tuple(sorted(ids)) for leaf, ids in by_leaf.items()},
        ksh={row.code: row for row in ksh},
        recipes={r.id: r for r in recipes},
        nutrition={row.code: row for row in nutrition},
    )


# ───────────────────────────── large synthetic catalogue (performance tests) ─────────────────────────────

SYNTHETIC_CHAINS = ("alfa", "beta", "gamma", "delta", "epszilon", "zeta")
_PACK_SIZES_KG = (
    "0.1",
    "0.125",
    "0.175",
    "0.2",
    "0.25",
    "0.3",
    "0.33",
    "0.4",
    "0.45",
    "0.5",
    "0.75",
    "1",
    "2",
)
_PACK_SIZES_DB = ("1", "4", "6", "10", "12", "15", "30")
_WORDS = ("alma", "korte", "tejfol", "joghurt", "sajt", "csirkemell", "teszta", "rizs", "liszt", "hagyma")


def synthetic_catalogue(
    seed: int, *, n_products: int = 4_000, n_leaves: int = 120, n_ingredients: int = 220, n_stores: int = 25
) -> Catalogue:
    """A made-up catalogue shaped like the GVH food data (BUILD-BRIEF §3): many single-chain SKUs, mixed
    units per leaf, ~1/3 loose goods, store-level prices for two chains, availability lists for some."""
    rng = random.Random(seed)  # noqa: S311 - seeded synthetic test data, not security
    chains = [chain(slug) for slug in SYNTHETIC_CHAINS]
    stores = [store(f"s{n:02d}", SYNTHETIC_CHAINS[n % len(SYNTHETIC_CHAINS)]) for n in range(n_stores)]
    leaf_unit: dict[int, str] = {
        leaf: rng.choice(("kg", "kg", "kg", "l", "db")) for leaf in range(1, n_leaves + 1)
    }

    products: list[Product] = []
    chain_prices: list[ChainPrice] = []
    store_prices: list[StorePrice] = []
    availability: dict[tuple[str, str], list[str]] = {}
    for n in range(n_products):
        leaf = rng.randint(1, n_leaves)
        unit = leaf_unit[leaf] if rng.random() < 0.8 else rng.choice(("kg", "db"))
        loose = unit == "kg" and rng.random() < 0.35
        if unit == "db":
            packaging: str | None = rng.choice(_PACK_SIZES_DB)
        else:
            packaging = None if loose and rng.random() < 0.5 else rng.choice(_PACK_SIZES_KG)
        word = _WORDS[leaf % len(_WORDS)]
        name = f"{word.upper()} SZINTETIKUS {n} QQ" if rng.random() < 0.15 else f"Szintetikus {word} {n}"
        pid = f"syn{n:05d}"
        products.append(
            product(pid, name, leaf, unit=unit, unit_title="kg" if loose else "csomag", packaging=packaging)
        )
        n_chains = 1 if rng.random() < 0.84 else rng.randint(2, 4)
        for slug in rng.sample(SYNTHETIC_CHAINS, n_chains):
            base = rng.randint(80, 4000)
            chain_prices.append(
                chain_price(pid, slug, base, normal=base - rng.randint(0, 50), same=rng.random() < 0.9)
            )
            chain_stores = [s for s in stores if s.chain_id == f"chain-{slug}"]
            if slug in ("alfa", "beta") and rng.random() < 0.3:
                for s in chain_stores:
                    store_prices.append(store_price(pid, s.id, normal=base + rng.randint(-30, 60)))
            elif rng.random() < 0.25:
                availability[(pid, f"chain-{slug}")] = [s.id for s in chain_stores if rng.random() < 0.6]

    ingredients: list[Ingredient] = []
    for n in range(n_ingredients):
        leaves = rng.sample(range(1, n_leaves + 1), rng.choice((1, 1, 1, 2)))
        unit = leaf_unit[leaves[0]]
        canonical: Unit = "kg" if unit == "kg" else ("l" if unit == "l" else "db")
        exclude = ("panir",) if rng.random() < 0.3 else ()
        include = (r"\d",) if rng.random() < 0.2 else ()
        ingredients.append(
            ingredient(
                f"ing{n:03d}",
                unit=canonical,
                leaf_ids=leaves,
                include=include,
                exclude=exclude,
                piece_weight="0.12" if canonical in ("kg", "db") else None,
                density="1.03" if canonical == "l" else None,
            )
        )
    return catalogue(
        ingredients=ingredients,
        products=products,
        chains=chains,
        stores=stores,
        chain_prices=chain_prices,
        store_prices=store_prices,
        availability=availability,
    )


def synthetic_lines(cat: Catalogue, count: int, seed: int) -> list[tuple[str, Decimal]]:
    """``count`` quote lines over the catalogue's ingredients with plausible weekly quantities."""
    rng = random.Random(seed)  # noqa: S311 - seeded synthetic test data, not security
    ids = sorted(cat.ingredients)[:count]
    lines = []
    for ing_id in ids:
        unit = cat.ingredients[ing_id].unit
        qty = Decimal(rng.randint(1, 12)) if unit == "db" else Decimal(rng.randint(50, 3000)) / 1000
        lines.append((ing_id, qty))
    return lines
