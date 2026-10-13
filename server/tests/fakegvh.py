"""A deterministic fake GVH Árfigyelő: an ``httpx.MockTransport`` handler and a tiny threaded HTTP server.

What is REAL and what is SYNTHETIC
----------------------------------
* REAL reference data, read from ``research/`` (never modified):
  - stores: ``research/gvh-location/data/stores.csv`` (all 1,829 stores; ids, postal codes, addresses and
    coordinates are kept as they are) rendered in the documented ``/api/shops`` shape;
  - categories: ``research/gap-gvh-promo-and-stability/data/leaf_categories.csv`` (ids, names, tree) with the
    paths of ``research/recipe-coverage/out/gvh_leaf_categories.csv``.
  - Chain uuids are INVENTED (uuid5 of the chain name): stable, but not GVH's.
* SYNTHETIC: every product, product id, product name and price. They come from a seeded generator, so the
  same seed always gives the same world. Price magnitudes per leaf follow
  ``research/gap-healthy-plan-priceability/data/ingredient_reference_prices.csv`` (leaf ids via
  ``research/recipe-coverage/out/ingredient_mapping.csv``); other leaves use per-category defaults. Brand
  names are made up ("Mintafarm", "Próbakert"...). None of this is real GVH product or price data.

Shapes follow ``server/bpf/gvh/ASSUMPTIONS.md``. The world reproduces the traps of BUILD-BRIEF §4.1: mixed
db/kg units in some leaves, loose "lédig" items (``unitTitle`` "kg"), accent-less Tesco counter names, the
Spar single-store outlier (``prices[]`` NORMAL far below ``productMinAmount``), a Tesco Budapest-Expressz
price zone, products sold by more than 3 chains (the listing shows 3), ``PRODUCT-SHOP-PRICES-NOT-FOUND`` for
stores that do not carry a product, Budapest stores without any product, a product with the unknown unit
"csomag", and an XLSX with decimal-comma text numbers. Modes: stale XLSX, XLSX header changes, schema drift,
an ignored ``limit``, the SPA's HTML page for unknown API paths, injected 5xx / connection failures, and a
listing that still serves the previous day for a share of pairs (``listing_lag``, trap 10). The fake CDN
serves yesterday's file without a cache-buster and, like a real edge, keeps serving the first copy it cached
under a given ``v`` value (trap 4).

By default the listing and the XLSX agree exactly (both derive from the same per-store prices): the listing's
min(NORMAL, DISCOUNTED) per chain equals the XLSX "Minimum ár", and LOYALTY appears only in the listing and
the per-store answers.

Regenerate the synthetic fixtures with ``python -m tests.fakegvh --write-fixtures`` (from ``server/``).
"""

from __future__ import annotations

import argparse
import csv
import functools
import hashlib
import io
import json
import os
import random
import re
import threading
import unicodedata
import uuid
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
import openpyxl

from bpf.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH = REPO_ROOT / "research"
STORES_CSV = RESEARCH / "gvh-location" / "data" / "stores.csv"
LEAVES_CSV = RESEARCH / "gap-gvh-promo-and-stability" / "data" / "leaf_categories.csv"
PATHS_CSV = RESEARCH / "recipe-coverage" / "out" / "gvh_leaf_categories.csv"
MAPPING_CSV = RESEARCH / "recipe-coverage" / "out" / "ingredient_mapping.csv"
REF_PRICES_CSV = RESEARCH / "gap-healthy-plan-priceability" / "data" / "ingredient_reference_prices.csv"
SYNTHETIC_DIR = Path(__file__).resolve().parent / "fixtures" / "gvh" / "synthetic"
# Real samples (docs/QUESTIONS.md). BPF_GVH_RAW_DIR points the raw-sample tests at another folder.
RAW_DIR = Path(
    os.environ.get("BPF_GVH_RAW_DIR") or Path(__file__).resolve().parent / "fixtures" / "gvh" / "raw"
)

API_BASE = "https://fake-gvh.test/api"
XLSX_URL = "https://fake-cdn.test/excel/arfigyelo_napi_termekadatok.xlsx"
XLSX_PATH = "/excel/arfigyelo_napi_termekadatok.xlsx"
CONTACT = "ingest-tests@example.org"
DEFAULT_SEED = 20261013

FOOD_TOP_IDS = frozenset({1001, 1015, 1028, 1046, 1050, 1068})
GROCERY = ("Aldi", "Auchan", "Lidl", "Penny", "Spar", "Tesco")
DRUGSTORES = ("dm", "Müller", "Rossmann")
NATIONAL_PRICE_CHAINS = frozenset({"Aldi", "Lidl", "Penny"})  # carried in every store, one price
NO_DATA_STORES = frozenset({"spar-171", "spar-193", "tesco-1008"})  # real ids of Budapest stores w/o data
NOT_FOUND = "PRODUCT-SHOP-PRICES-NOT-FOUND"
HEADERS = (
    "Termék azonosító",
    "Termék név",
    "Kategória azonosító",
    "Kategória név",
    "Üzletlánc név",
    "Egység",
    "Kiszerelés",
    "Minimum ár",
    "Maximum ár",
    "Minimum egységár",
    "Maximum egységár",
    "Hány üzletláncban elérhető",
    "Hány boltban elérhető",
    "Üzletlánc összes boltja",
)

LITRE_LEAVES = frozenset({1, 2, 3, 4, 51, 61, 62, 67, 68, 69, 81, 82, 83, 120, 121})
PIECE_LEAVES = frozenset({14, 45, 94})
MIXED_LEAVES = frozenset({28, 31, 32, 35, 36, 37, 38, 39, 40, 81})  # db/kg (81: l/kg) within one leaf
PRODUCE_LEAVES = frozenset({28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 97})
COUNTER_LEAVES = frozenset({15, 16, 17, 18, 19, 20, 21, 64, 85, 86, 87, 91, 92, 93, 118, 119})
DRUGSTORE_LEAVES = frozenset({68, 79, 80, 99, 100, 101, 102})
TOP_DEFAULT_PRICE: Mapping[int, Mapping[str, int]] = {
    1001: {"kg": 2500, "l": 550, "db": 60},
    1015: {"kg": 3000, "l": 3000, "db": 900},
    1028: {"kg": 600, "l": 600, "db": 250},
    1046: {"kg": 900, "l": 900, "db": 60},
    1050: {"kg": 1200, "l": 900, "db": 300},
    1068: {"kg": 2500, "l": 900, "db": 300},
}
NONFOOD_PRICE = {"kg": 3000, "l": 1500, "db": 1200}
BRANDS = ("Mintafarm", "Próbakert", "Tesztmalom", "Példatej", "Kísérleti", "Szintetika", "Demóház")
PIECE_KG = Decimal("0.2")
CENT = Decimal("0.01")
VALID_UNITS = frozenset({"kg", "l", "db"})  # what the ingest keeps (others are skipped, trap 5)
PREVIOUS_DAY_RISE = Decimal("0.08")  # a lagged listing pair shows a price 8 % (>= 1 Ft) off today's


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).casefold().split())


def _num(value: Decimal) -> int | float:
    """JSON number for a Decimal: int when whole, else float (2-4 decimals; repr round-trips exactly)."""
    return int(value) if value == value.to_integral_value() else float(value)


def _comma(value: Decimal | int, places: int = 4) -> str:
    """XLSX text number with a decimal comma, e.g. Decimal('1699') -> '1699,0000'."""
    return f"{Decimal(value):.{places}f}".replace(".", ",")


# ───────────────────────────── real reference data ─────────────────────────────


@dataclass(frozen=True, slots=True)
class FakeStore:
    id: str
    chain: str
    postal_code: str
    city: str
    address: str
    lat: float
    lon: float
    opening: str | None

    @property
    def budapest(self) -> bool:
        return self.postal_code.startswith("1")


@dataclass(frozen=True, slots=True)
class FakeChain:
    uuid: str
    name: str
    stores: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FakeLeaf:
    id: int
    name: str
    path: str
    l2_id: int
    l2_name: str
    top_id: int
    top_name: str

    @property
    def is_food(self) -> bool:
        return self.top_id in FOOD_TOP_IDS


def chain_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bestpricefinder-fake-gvh-chain:{name}"))


@functools.cache
def load_stores() -> tuple[FakeStore, ...]:
    with STORES_CSV.open(encoding="utf-8", newline="") as handle:
        return tuple(
            FakeStore(
                id=row["uuid"],
                chain=row["chain"],
                postal_code=row["postalCode"],
                city=row["city"],
                address=row["address"],
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                opening=row["openingTime"] or None,
            )
            for row in csv.DictReader(handle)
        )


@functools.cache
def load_leaves() -> tuple[FakeLeaf, ...]:
    with PATHS_CSV.open(encoding="utf-8", newline="") as handle:
        paths = {int(row["leaf_id"]): row["path"] for row in csv.DictReader(handle)}
    with LEAVES_CSV.open(encoding="utf-8", newline="") as handle:
        return tuple(
            sorted(
                (
                    FakeLeaf(
                        id=int(row["leaf_id"]),
                        name=row["leaf"],
                        path=paths[int(row["leaf_id"])],
                        l2_id=int(row["l2_id"]),
                        l2_name=row["l2"],
                        top_id=int(row["top_id"]),
                        top_name=row["top"],
                    )
                    for row in csv.DictReader(handle)
                ),
                key=lambda leaf: leaf.id,
            )
        )


@functools.cache
def leaf_magnitudes() -> Mapping[int, tuple[str, Decimal]]:
    """Leaf id -> (unit, typical HUF per unit) from the research reference prices (research medians)."""
    with REF_PRICES_CSV.open(encoding="utf-8", newline="") as handle:
        reference = {row["key"]: row for row in csv.DictReader(handle)}
    found: dict[int, tuple[str, Decimal]] = {}
    with MAPPING_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ref = reference.get(row["ingredient_key"])
            if ref and ref["unit"] == row["base_unit"] and ref["price"]:
                unit, price = ref["unit"], Decimal(ref["price"])
            elif row["gvh_min_unit_price_Ft_per_base"]:
                unit, price = row["base_unit"], Decimal(row["gvh_min_unit_price_Ft_per_base"])
            else:
                continue
            for leaf in re.findall(r"\d+", row["gvh_leaf_ids"]):
                found.setdefault(int(leaf), (unit, price))
    return found


def category_tree(leaves: Sequence[FakeLeaf]) -> list[dict[str, Any]]:
    """The documented /categories shape: an array of top nodes ``{id, name, path, categoryNodes}``."""
    tops: dict[int, dict[str, Any]] = {}
    l2s: dict[int, dict[str, Any]] = {}
    for leaf in leaves:
        top_path, l2_path = leaf.path.split("/")[0], "/".join(leaf.path.split("/")[:2])
        top = tops.setdefault(
            leaf.top_id, {"id": leaf.top_id, "name": leaf.top_name, "path": top_path, "categoryNodes": []}
        )
        if leaf.l2_id not in l2s:
            l2s[leaf.l2_id] = {"id": leaf.l2_id, "name": leaf.l2_name, "path": l2_path, "categoryNodes": []}
            top["categoryNodes"].append(l2s[leaf.l2_id])
        l2s[leaf.l2_id]["categoryNodes"].append(
            {"id": leaf.id, "name": leaf.name, "path": leaf.path, "categoryNodes": []}
        )
    return [tops[top_id] for top_id in sorted(tops)]


# ───────────────────────────── synthetic products and prices ─────────────────────────────


@dataclass(frozen=True, slots=True)
class Offer:
    """One product at one chain. ``pattern`` decides the per-store prices:

    uniform     every store NORMAL ``normal``
    zone        ``special`` stores (Budapest Tesco 4xxx) NORMAL ``alt`` (about +3.5 %), the rest ``normal``
    outlier     ``special`` stores (2) NORMAL ``alt`` (far below), the rest ``normal`` (the Spar pattern)
    split       ``special`` stores (52 %) NORMAL ``alt``: no price reaches 80 % (the Lidl banana)
    promo_all   every store NORMAL ``normal`` + DISCOUNTED ``alt``
    promo_some  ``special`` stores also DISCOUNTED ``alt`` (a promotion in a few stores)
    loyalty     every store NORMAL ``normal`` + LOYALTY ``alt``
    """

    chain: str
    stores: tuple[str, ...]
    normal: int
    pattern: str = "uniform"
    alt: int | None = None
    special: frozenset[str] = frozenset()

    def store_prices(self, store_id: str) -> list[tuple[str, int]]:
        special = store_id in self.special
        match self.pattern:
            case "zone" | "outlier" | "split" if special and self.alt is not None:
                return [("NORMAL", self.alt)]
            case "promo_all" if self.alt is not None:
                return [("NORMAL", self.normal), ("DISCOUNTED", self.alt)]
            case "promo_some" if special and self.alt is not None:
                return [("NORMAL", self.normal), ("DISCOUNTED", self.alt)]
            case "loyalty" if self.alt is not None:
                return [("NORMAL", self.normal), ("LOYALTY", self.alt)]
        return [("NORMAL", self.normal)]


@dataclass(frozen=True, slots=True)
class FakeProduct:
    id: str
    name: str
    leaf_id: int
    unit: str
    unit_title: str
    packaging: Decimal
    offers: tuple[Offer, ...]

    def unit_amount(self, amount: int) -> Decimal:
        return (Decimal(amount) / self.packaging).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class OfferSummary:
    """What GVH derives from the per-store prices of one offer (in a store scope)."""

    chain: str
    stores: tuple[str, ...]
    per_store: Mapping[str, tuple[tuple[str, int], ...]]
    product_min_amount: int  # daily price (min NORMAL/DISCOUNTED) of >= 80 % of stores, else the minimum
    mins: Mapping[str, int]  # per type minimum (listing/detail prices[])
    maxs: Mapping[str, int]
    same_amount: Mapping[str, bool]
    listing_same: bool  # 80 % notion (BUILD-BRIEF §4.1 trap 3)
    detail_same: bool  # literal
    daily_min: int
    daily_max: int


@functools.cache
def summarise(offer: Offer, scope: frozenset[str] | None = None) -> OfferSummary | None:
    stores = tuple(s for s in offer.stores if scope is None or s in scope)
    if not stores:
        return None
    per_store = {store: tuple(offer.store_prices(store)) for store in stores}
    daily = {store: min(a for t, a in prices if t != "LOYALTY") for store, prices in per_store.items()}
    counts = Counter(daily.values())
    common, common_n = min(counts.items(), key=lambda item: (-item[1], item[0]))
    pma = common if common_n >= 0.8 * len(stores) else min(daily.values())
    by_type: dict[str, list[int]] = {}
    for prices in per_store.values():
        for price_type, amount in prices:
            by_type.setdefault(price_type, []).append(amount)
    lists = Counter(per_store.values())
    return OfferSummary(
        chain=offer.chain,
        stores=stores,
        per_store=per_store,
        product_min_amount=pma,
        mins={t: min(v) for t, v in by_type.items()},
        maxs={t: max(v) for t, v in by_type.items()},
        same_amount={t: len(set(v)) == 1 for t, v in by_type.items()},
        listing_same=max(lists.values()) >= 0.8 * len(stores),
        detail_same=len(lists) == 1,
        daily_min=min(daily.values()),
        daily_max=max(daily.values()),
    )


@functools.cache
def previous_day(offer: Offer) -> Offer:
    """The offer as the API showed it the day before (trap 10): one NORMAL price in every store, 8 % (at least
    1 Ft) above today's cheapest daily price, so its daily minimum differs from today's XLSX "Minimum ár" by
    more than the ingest's 0.5 Ft tolerance. Promotions and loyalty prices of today are not there yet."""
    today = summarise(offer)
    if today is None:
        return offer
    rise = max(1, int((today.daily_min * PREVIOUS_DAY_RISE).to_integral_value(ROUND_HALF_UP)))
    return Offer(offer.chain, offer.stores, today.daily_min + rise)


def shown_chains(summaries: Sequence[OfferSummary]) -> list[OfferSummary]:
    """The listing's 3-chain cap (trap 2): the chains with the most carrying stores, ties by name."""
    return sorted(summaries, key=lambda s: (-len(s.stores), s.chain))[:3]


@dataclass
class FakeWorld:
    """Chains, stores, categories and synthetic products. Build with :func:`build_world`."""

    seed: int
    chains: dict[str, FakeChain]
    stores: dict[str, FakeStore]
    leaves: dict[int, FakeLeaf]
    products: dict[str, FakeProduct]
    special: dict[str, str] = field(default_factory=dict)
    xlsx_cache: dict[tuple[date, str | None, int | None], bytes] = field(
        default_factory=dict, repr=False, compare=False
    )

    def leaf_products(self, leaf_id: int) -> list[FakeProduct]:
        return [p for p in self.products.values() if p.leaf_id == leaf_id]

    def budapest_stores(self, chain: str) -> tuple[str, ...]:
        return tuple(s for s in self.chains[chain].stores if self.stores[s].budapest)

    def chain_by_uuid(self, chain_uuid_: str) -> FakeChain:
        return next(c for c in self.chains.values() if c.uuid == chain_uuid_)


class _Ids:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.used: set[str] = set()

    def _unique(self, make: Callable[[], str]) -> str:
        while True:
            candidate = make()
            if candidate not in self.used:
                self.used.add(candidate)
                return candidate

    def ean(self) -> str:
        def make() -> str:
            body = "599" + "".join(self.rng.choice("0123456789") for _ in range(9))
            total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body))
            return body + str((10 - total % 10) % 10)

        return self._unique(make)

    def weighed(self) -> str:
        return self._unique(lambda: "2999" + "".join(self.rng.choice("0123456789") for _ in range(9)))

    def internal(self, chain: str) -> str:
        digits = {"Lidl": 7, "Aldi": 6, "Penny": 4}[chain]
        prefix = chain.lower()
        return self._unique(lambda: f"{prefix}-{self.rng.randrange(10 ** (digits - 1), 10**digits)}")


def _pack(rng: random.Random, leaf_id: int, unit: str) -> Decimal:
    if unit == "db":
        return Decimal(rng.choice((10, 30) if leaf_id == 14 else (1, 1, 1, 6)))
    if unit == "l":
        return Decimal(rng.choice(("0.2", "0.5", "1", "1", "1.5")))
    return Decimal(rng.choice(("0.2", "0.25", "0.4", "0.5", "0.5", "1", "1", "2")))


def _pack_label(unit: str, packaging: Decimal) -> str:
    if unit == "kg":
        grams = packaging * 1000
        return f"{int(grams)} g" if packaging < 1 else f"{_num(packaging)} kg"
    if unit == "l":
        return f"{int(packaging * 1000)} ml" if packaging < 1 else f"{_num(packaging)} l"
    return f"{int(packaging)} db"


def _carrying(rng: random.Random, chain: FakeChain) -> tuple[str, ...]:
    stores = [s for s in chain.stores if s not in NO_DATA_STORES]
    if chain.name in NATIONAL_PRICE_CHAINS:
        return tuple(stores)
    share = rng.uniform(0.6, 1.0) if chain.name == "Auchan" else rng.uniform(0.25, 0.95)
    return tuple(sorted(rng.sample(stores, max(1, round(len(stores) * share)))))


def _offer(rng: random.Random, chain: FakeChain, base: int, world_stores: Mapping[str, FakeStore]) -> Offer:
    stores = _carrying(rng, chain)
    normal = max(29, round(base * rng.uniform(0.9, 1.25)))
    roll = rng.random()
    if chain.name == "Tesco" and roll < 0.35:
        zone = frozenset(s for s in stores if world_stores[s].budapest and s.startswith("tesco-4"))
        if zone:
            return Offer(chain.name, stores, normal, "zone", round(normal * 1.035), zone)
    if chain.name == "Spar" and roll < 0.06 and len(stores) > 10:
        return Offer(
            chain.name, stores, normal, "outlier", round(normal * 0.45), frozenset(rng.sample(stores, 2))
        )
    if chain.name == "Spar" and roll < 0.1:
        return Offer(
            chain.name, stores, normal, "promo_some", round(normal * 0.6), frozenset(rng.sample(stores, 1))
        )
    if chain.name == "Penny" and roll < 0.1:
        return Offer(chain.name, stores, normal, "promo_all", round(normal * 0.75))
    if chain.name in ("Penny", "Auchan") and roll < 0.15:
        return Offer(chain.name, stores, normal, "loyalty", round(normal * 0.85))
    return Offer(chain.name, stores, normal)


def _magnitude(leaf: FakeLeaf, unit: str) -> Decimal:
    """Typical HUF per ``unit`` for a leaf: the research reference price when its unit matches (or per piece
    at 0.2 kg when the reference is per kg), else the category default."""
    ref_unit, ref_price = leaf_magnitudes().get(leaf.id, ("", Decimal(0)))
    if ref_price and ref_unit == unit:
        return ref_price
    if ref_price and ref_unit == "kg" and unit == "db":
        return ref_price * PIECE_KG
    return Decimal(TOP_DEFAULT_PRICE.get(leaf.top_id, NONFOOD_PRICE)[unit])


def _generic_product(
    rng: random.Random,
    ids: _Ids,
    leaf: FakeLeaf,
    index: int,
    world_chains: Mapping[str, FakeChain],
    world_stores: Mapping[str, FakeStore],
) -> FakeProduct:
    unit = "l" if leaf.id in LITRE_LEAVES else "db" if leaf.id in PIECE_LEAVES else "kg"
    if leaf.id in MIXED_LEAVES and index % 2 == 1:
        unit = "kg" if leaf.id == 81 else ("db" if unit == "kg" else "kg")
    magnitude = _magnitude(leaf, unit)
    loose = unit == "kg" and leaf.id in PRODUCE_LEAVES | COUNTER_LEAVES and rng.random() < 0.5
    packaging = Decimal(1) if loose else _pack(rng, leaf.id, unit)
    n_chains = rng.choices((1, 2, 3, 4), weights=(78, 12, 7, 3))[0] if leaf.is_food else 1
    pool = list(GROCERY + DRUGSTORES) if leaf.id in DRUGSTORE_LEAVES or not leaf.is_food else list(GROCERY)
    chain_names = sorted(rng.sample(pool, min(n_chains, len(pool))))
    first = chain_names[0]
    counter = loose and leaf.id in COUNTER_LEAVES and "Tesco" in chain_names
    if counter:
        product_id = ids.weighed()
        name = f"{10 + index}. FRISS {fold(leaf.name).upper()} PULTOS QQ"
    elif loose:
        product_id = ids.weighed() if rng.random() < 0.5 else ids.ean()
        name = f"{leaf.name} lédig"
    else:
        internal = len(chain_names) == 1 and first in ("Lidl", "Aldi", "Penny") and rng.random() < 0.6
        product_id = ids.internal(first) if internal else ids.ean()
        name = f"{rng.choice(BRANDS)} {leaf.name.lower()} {_pack_label(unit, packaging)}"
    base = int((magnitude * packaging).to_integral_value(ROUND_HALF_UP))
    offers = tuple(_offer(rng, world_chains[c], base, world_stores) for c in chain_names)
    return FakeProduct(product_id, name, leaf.id, unit, "kg" if loose else "csomag", packaging, offers)


def _all_stores(chain: FakeChain) -> tuple[str, ...]:
    return tuple(s for s in chain.stores if s not in NO_DATA_STORES)


def _specials(world: FakeWorld, ids: _Ids) -> None:
    """Products that pin each trap to a known leaf, so tests can find them via ``world.special``."""
    chains, stores = world.chains, world.stores

    def add(key: str, product: FakeProduct) -> None:
        if product.leaf_id in world.leaves:
            world.products[product.id] = product
            world.special[key] = product.id

    tesco = _all_stores(chains["Tesco"])
    zone = frozenset(s for s in tesco if stores[s].budapest and s.startswith("tesco-4"))
    add(
        "tesco_zone",
        FakeProduct(
            ids.weighed(),
            "31. FRISS CSIRKEMELL FILE PULTOS QQ",
            18,
            "kg",
            "kg",
            Decimal(1),
            (Offer("Tesco", tesco, 2030, "zone", 2101, zone),),
        ),
    )
    spar = _all_stores(chains["Spar"])
    budapest_spar = [s for s in spar if stores[s].budapest]
    add(
        "spar_outlier",
        FakeProduct(
            ids.ean(),
            "Próbakert spagetti 500 g",
            50,
            "kg",
            "csomag",
            Decimal("0.5"),
            (Offer("Spar", spar, 699, "outlier", 294, frozenset(budapest_spar[:2])),),
        ),
    )
    lidl = _all_stores(chains["Lidl"])
    split = frozenset(lidl[: round(len(lidl) * 0.52)])
    add(
        "lidl_split",
        FakeProduct(
            ids.internal("Lidl"),
            "Banán",
            31,
            "kg",
            "kg",
            Decimal(1),
            (Offer("Lidl", lidl, 379, "split", 699, split),),
        ),
    )
    outside = [s for s in spar if not stores[s].budapest][:1]
    add(
        "spar_promo_some",
        FakeProduct(
            ids.ean(),
            "Étkezési paprika lédig",
            35,
            "kg",
            "kg",
            Decimal(1),
            (Offer("Spar", spar, 853, "promo_some", 399, frozenset(outside)),),
        ),
    )
    penny = _all_stores(chains["Penny"])
    add(
        "penny_promo_all",
        FakeProduct(
            ids.internal("Penny"),
            "Kígyóuborka",
            38,
            "db",
            "csomag",
            Decimal(1),
            (Offer("Penny", penny, 379, "promo_all", 219),),
        ),
    )
    add(
        "penny_loyalty",
        FakeProduct(
            ids.internal("Penny"),
            "Mintafarm friss tojás 10 db M",
            14,
            "db",
            "csomag",
            Decimal(10),
            (Offer("Penny", penny, 899, "loyalty", 799),),
        ),
    )
    auchan = _all_stores(chains["Auchan"])
    aldi = _all_stores(chains["Aldi"])
    add(
        "multichain",
        FakeProduct(
            ids.ean(),
            "Példatej natúr joghurt 150 g",
            7,
            "kg",
            "csomag",
            Decimal("0.15"),
            (
                Offer("Aldi", aldi, 139),
                Offer("Auchan", auchan[:4], 119),  # sold in few stores: hidden by the 3-chain listing cap
                Offer("Penny", penny, 145),
                Offer("Spar", spar[:40], 129),  # hidden too, and cheaper than two of the listed chains
                Offer("Tesco", tesco, 149, "zone", 155, zone),
            ),
        ),
    )
    add(
        "unknown_unit",
        FakeProduct(
            ids.ean(),
            "Mintafarm vöröshagyma 3 db-os háló",
            40,
            "csomag",
            "csomag",
            Decimal(1),
            (Offer("Aldi", aldi, 299),),
        ),
    )
    add(
        "carrot_db_kg",
        FakeProduct(ids.ean(), "Sárgarépa csomós", 36, "db", "kg", Decimal(1), (Offer("Spar", spar, 349),)),
    )


@functools.cache
def build_world(
    *,
    seed: int = DEFAULT_SEED,
    per_leaf: int = 3,
    overrides: tuple[tuple[int, int], ...] = ((18, 100), (40, 12)),
    leaf_subset: frozenset[int] | None = None,
    nonfood_per_leaf: int = 1,
) -> FakeWorld:
    """A deterministic world. ``overrides`` = ((leaf id, products), ...); ``leaf_subset`` keeps only those
    leaves in the category tree (for fast end-to-end runs). Cached: treat the result as read-only."""
    rng = random.Random(seed)  # noqa: S311 - deterministic synthetic data, not security
    all_stores = load_stores()
    stores = {s.id: s for s in all_stores}
    chains = {
        name: FakeChain(chain_uuid(name), name, tuple(sorted(s.id for s in all_stores if s.chain == name)))
        for name in sorted({s.chain for s in all_stores})
    }
    leaves = {leaf.id: leaf for leaf in load_leaves() if leaf_subset is None or leaf.id in leaf_subset}
    world = FakeWorld(seed=seed, chains=chains, stores=stores, leaves=leaves, products={})
    ids = _Ids(rng)
    counts = dict(overrides)
    for leaf in leaves.values():
        n = counts.get(leaf.id, per_leaf) if leaf.is_food else nonfood_per_leaf
        for index in range(n):
            product = _generic_product(rng, ids, leaf, index, chains, stores)
            world.products[product.id] = product
    _specials(world, ids)
    return world


# ───────────────────────────── JSON / XLSX rendering ─────────────────────────────


def shops_json(world: FakeWorld) -> list[dict[str, Any]]:
    return [
        {
            "uuid": s.id,
            "postalCode": s.postal_code,
            "city": s.city,
            "address": s.address,
            "chainStoreUuid": world.chains[s.chain].uuid,
            "location": {"latitude": s.lat, "longitude": s.lon},
            "openingTime": s.opening,
        }
        for s in world.stores.values()
    ]


def chain_stores_json(world: FakeWorld) -> list[dict[str, Any]]:
    # imageUrl would be a retailer logo on the real API: the fake uses a placeholder, the client ignores it.
    return [
        {"uuid": c.uuid, "name": c.name, "imageUrl": "https://cdn.example.invalid/chain.png"}
        for c in world.chains.values()
    ]


def _price_list(
    product: FakeProduct, amounts: Mapping[str, int], same: Mapping[str, bool] | None
) -> list[dict[str, Any]]:
    order = ("NORMAL", "DISCOUNTED", "LOYALTY")
    out = []
    for price_type in sorted(amounts, key=order.index):
        entry: dict[str, Any] = {
            "type": price_type,
            "amount": amounts[price_type],
            "unitAmount": _num(product.unit_amount(amounts[price_type])),
        }
        if same is not None:
            entry["sameAmountEverywhere"] = same[price_type]
        out.append(entry)
    return out


def _path_of(world: FakeWorld, leaf_id: int) -> str:
    return world.leaves[leaf_id].path if leaf_id in world.leaves else ""


def listing_item(
    world: FakeWorld,
    product: FakeProduct,
    scope: frozenset[str] | None = None,
    lagged: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    """One listing product. Chains named in ``lagged`` show :func:`previous_day` prices (same stores, so the
    3-chain cap picks the same chains)."""
    offers = [previous_day(offer) if offer.chain in lagged else offer for offer in product.offers]
    summaries = [s for offer in offers if (s := summarise(offer, scope)) is not None]
    if not summaries:
        return None
    shown = shown_chains(summaries)
    return {
        "id": product.id,
        "name": product.name,
        "imageUrl": None,
        "unit": product.unit,
        "unitTitle": product.unit_title,
        "bulk": False,
        "packaging": _num(product.packaging),
        "categoryPath": _path_of(world, product.leaf_id),
        "minUnitPrice": _num(min(product.unit_amount(s.product_min_amount) for s in shown)),
        "pricesOfChainStores": [
            {
                "id": world.chains[s.chain].uuid,
                "name": s.chain,
                "priceSameEverywhere": s.listing_same,
                "productMinAmount": s.product_min_amount,
                "prices": _price_list(product, s.mins, s.same_amount),
            }
            for s in sorted(shown, key=lambda s: s.chain)
        ],
    }


def detail_json(world: FakeWorld, product: FakeProduct) -> dict[str, Any]:
    summaries = [s for offer in product.offers if (s := summarise(offer)) is not None]
    return {
        "id": product.id,
        "name": product.name,
        "imageUrl": None,
        "unit": product.unit,
        "unitTitle": product.unit_title,
        "bulk": True,  # differs from the listing on the real API too (research/gvh-location §1)
        "packaging": _num(product.packaging),
        "categoryPath": _path_of(world, product.leaf_id),
        "minUnitPrice": _num(min(product.unit_amount(s.product_min_amount) for s in summaries)),
        "chainStores": [
            {
                "id": world.chains[s.chain].uuid,
                "name": s.chain,
                "prices": _price_list(product, s.mins, None),
                "pricesMax": _price_list(product, s.maxs, None),
                "priceSameEverywhere": s.detail_same,
                "productMinAmount": s.product_min_amount,
                "availableInShops": list(s.stores),
            }
            for s in summaries
        ],
    }


def shop_prices_json(product: FakeProduct, store_ids: Sequence[str]) -> dict[str, Any] | None:
    carrying = {store: offer for offer in product.offers for store in offer.stores}
    shops = []
    for store in dict.fromkeys(store_ids):
        offer = carrying.get(store)
        if offer is not None:
            prices = offer.store_prices(store)
            shops.append(
                {
                    "shopUuid": store,
                    "prices": [
                        {"type": t, "amount": a, "unitAmount": _num(product.unit_amount(a))}
                        for t, a in prices
                    ],
                }
            )
    return {"shops": shops} if shops else None


def xlsx_rows(world: FakeWorld) -> list[list[str]]:
    rows = []
    for product in sorted(world.products.values(), key=lambda p: (p.leaf_id, p.id)):
        leaf = world.leaves.get(product.leaf_id)
        for offer in product.offers:
            s = summarise(offer)
            if s is None:
                continue
            rows.append(
                [
                    product.id,
                    product.name,
                    str(product.leaf_id),
                    leaf.name if leaf else "",
                    offer.chain,
                    product.unit,
                    _comma(product.packaging),
                    _comma(s.daily_min),
                    _comma(s.daily_max),
                    _comma(product.unit_amount(s.daily_min)),
                    _comma(product.unit_amount(s.daily_max)),
                    str(len(product.offers)),
                    str(len(s.stores)),
                    str(len(world.chains[offer.chain].stores)),
                ]
            )
    return rows


def compared_pairs(world: FakeWorld) -> list[tuple[str, str]]:
    """(product id, chain name) pairs the daily ingest compares in its date agreement check: food leaves,
    units kg/l/db, chains shown in the (unscoped) listing. Every one of them is in the XLSX too. Sorted."""
    pairs = []
    for product in world.products.values():
        leaf = world.leaves.get(product.leaf_id)
        if leaf is None or not leaf.is_food or product.unit not in VALID_UNITS:
            continue
        summaries = [s for offer in product.offers if (s := summarise(offer)) is not None]
        pairs.extend((product.id, s.chain) for s in shown_chains(summaries))
    return sorted(pairs)


def lagged_pairs(world: FakeWorld, share: float) -> dict[str, frozenset[str]]:
    """Product id -> chains whose listing entry still shows the previous day: exactly ``round(share * N)`` of
    the N :func:`compared_pairs`, picked by a seeded hash (stable across runs and processes)."""
    pool = compared_pairs(world)
    count = round(share * len(pool))
    pool.sort(key=lambda pair: hashlib.sha256(f"{world.seed}|{pair[0]}|{pair[1]}".encode()).digest())
    chosen: dict[str, set[str]] = {}
    for product_id, chain in pool[:count]:
        chosen.setdefault(product_id, set()).add(chain)
    return {product_id: frozenset(chains) for product_id, chains in chosen.items()}


def xlsx_bytes(
    world: FakeWorld, sheet_date: date, *, mode: str | None = None, row_limit: int | None = None
) -> bytes:
    """The daily XLSX: one sheet ``Napi feltöltések - YYYY-MM-DD``, every value as text, decimal commas.

    ``mode``: None, ``"bad_header"`` (renames "Minimum ár"), ``"extra_column"``, ``"reordered"``.
    Cached on the world per (date, mode, row_limit)."""
    key = (sheet_date, mode, row_limit)
    if key not in world.xlsx_cache:
        world.xlsx_cache[key] = _render_xlsx(world, sheet_date, mode=mode, row_limit=row_limit)
    return world.xlsx_cache[key]


def _render_xlsx(world: FakeWorld, sheet_date: date, *, mode: str | None, row_limit: int | None) -> bytes:
    headers = list(HEADERS)
    rows = xlsx_rows(world)[:row_limit]
    if mode == "bad_header":
        headers[7] = "Min. ár"
    elif mode == "extra_column":
        headers.append("Új oszlop")
        rows = [[*row, "x"] for row in rows]
    elif mode == "reordered":
        headers[0], headers[1] = headers[1], headers[0]
        rows = [[row[1], row[0], *row[2:]] for row in rows]
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = f"Napi feltöltések - {sheet_date.isoformat()}"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ───────────────────────────── the HTTP surface ─────────────────────────────


@dataclass(frozen=True, slots=True)
class FakeResponse:
    status: int
    body: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class Recorded:
    method: str
    path: str  # decoded path (e.g. "/api/products-by-category/18")
    raw_path: str  # as sent, percent-encoding kept
    query: Mapping[str, str]
    user_agent: str | None
    at: float | None  # the fake's clock at receipt, when a clock was given


@dataclass
class Fault:
    prefix: str  # path prefix the fault applies to
    kind: int | str  # an HTTP status, or "connect" (MockTransport only)
    times: int


def _json(status: int, payload: Any) -> FakeResponse:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return FakeResponse(status, body, "application/json; charset=utf-8")


_SPA = b"<!doctype html><html><head><title>SPA</title></head><body><div id=app></div></body></html>"


class FakeGvh:
    """The fake API + CDN for one data date. Mutate the mode attributes before (or between) requests."""

    def __init__(
        self,
        world: FakeWorld,
        *,
        data_date: date,
        api_prefix: str = "/api",
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.world = world
        self.data_date = data_date
        self.api_prefix = api_prefix
        self.clock = clock
        self.xlsx_date: date | None = None  # sheet date of the fresh file (default: data_date)
        self.xlsx_mode: str | None = None  # see xlsx_bytes
        self.drift: str | None = None  # "extra_field" | "type_change" | "missing_field"
        self.ignore_limit = False  # behave as if limit were not sent: 12 rows per page
        # Share of compared pairs whose listing entry still shows the previous day's prices: the API has not
        # switched day yet (trap 10). 0.0 (the default): the listing and the XLSX agree exactly.
        self.listing_lag = 0.0
        self.cdn_cache: dict[str, date] = {}  # cache-buster value -> sheet date of the copy cached under it
        self.faults: list[Fault] = []
        self.requests: list[Recorded] = []
        self._lock = threading.Lock()
        self._lagged: tuple[float, Mapping[str, frozenset[str]]] = (0.0, {})

    # ── helpers for tests ──
    def fail(self, prefix: str, kind: int | str, times: int = 1) -> None:
        """The next ``times`` requests whose path starts with ``prefix`` fail with ``kind``."""
        self.faults.append(Fault(prefix, kind, times))

    def paths(self, prefix: str = "") -> list[str]:
        return [r.path for r in self.requests if r.path.startswith(prefix)]

    def lagged(self) -> Mapping[str, frozenset[str]]:
        """Product id -> chain names whose listing entry shows the previous day (see ``listing_lag``)."""
        with self._lock:
            if self._lagged[0] != self.listing_lag:
                self._lagged = (self.listing_lag, lagged_pairs(self.world, self.listing_lag))
            return self._lagged[1]

    def xlsx_busters(self) -> list[str]:
        """The ``v`` values of the XLSX requests, in order."""
        return [r.query.get("v", "") for r in self.requests if r.path == XLSX_PATH]

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    # ── dispatch ──
    def _take_fault(self, path: str) -> int | str | None:
        with self._lock:
            for fault in self.faults:
                if fault.times > 0 and path.startswith(fault.prefix):
                    fault.times -= 1
                    return fault.kind
        return None

    def _record(self, raw_target: str, user_agent: str | None) -> tuple[str, str, dict[str, str]]:
        parts = urlsplit(raw_target)
        path = unquote(parts.path)
        query = {k: v[-1] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        with self._lock:
            self.requests.append(
                Recorded("GET", path, parts.path, query, user_agent, self.clock() if self.clock else None)
            )
        return path, parts.path, query

    def respond(self, raw_target: str, user_agent: str | None = None) -> FakeResponse | str:
        """Answer one GET (``raw_target`` = path + query as sent); ``"connect"`` = a connection fault."""
        path, raw_path, query = self._record(raw_target, user_agent)
        fault = self._take_fault(path)
        if fault == "connect":
            return "connect"
        if isinstance(fault, int):
            return _json(fault, {"statusCode": fault, "message": "INJECTED-FAULT"})
        if path == XLSX_PATH:
            return self._xlsx(query)
        if not path.startswith(self.api_prefix + "/"):
            return FakeResponse(404, b"not found", "text/plain")
        return self._api(path[len(self.api_prefix) :], raw_path[len(self.api_prefix) :], query)

    def _xlsx(self, query: Mapping[str, str]) -> FakeResponse:
        fresh = self.xlsx_date or self.data_date
        buster = query.get("v")
        if buster:
            # Like a real CDN edge: the first copy fetched under a cache key is served again for that key,
            # even after the origin file changed (the real one kept copies for 6-30+ h despite max-age=3600).
            with self._lock:
                sheet = self.cdn_cache.setdefault(buster, fresh)
        else:
            sheet = self.data_date - timedelta(days=1)  # the plain URL: the edge serves yesterday's copy
        body = xlsx_bytes(self.world, sheet, mode=self.xlsx_mode)
        return FakeResponse(200, body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def _api(self, path: str, raw_path: str, query: Mapping[str, str]) -> FakeResponse:
        world = self.world
        if path == "/categories":
            return _json(200, category_tree(list(world.leaves.values())))
        if path == "/chain-stores":
            return _json(200, chain_stores_json(world))
        if path == "/shops":
            return _json(200, shops_json(world))
        if match := re.fullmatch(r"/products-by-category/(\d+)", path):
            return self._listing(int(match.group(1)), query)
        if path == "/search" and len(fold(query.get("q", ""))) < 3:
            # research/gvh-location/notes.md §1: a 2-character q is HTTP 400 SEARCH-INPUT-ERROR (longer
            # queries are not modelled: the app never searches; they get the SPA page like any unknown path)
            return _json(400, {"statusCode": 400, "message": "SEARCH-INPUT-ERROR"})
        if match := re.fullmatch(r"/product/([^/]+)/shop/([^/]+)", raw_path):
            product = world.products.get(unquote(match.group(1)))
            ids = [s for s in unquote(match.group(2)).split(",") if s]
            payload = shop_prices_json(product, ids) if product else None
            if payload is None:
                return _json(404, {"statusCode": 404, "message": NOT_FOUND})
            return _json(200, payload)
        if match := re.fullmatch(r"/product/([^/]+)", raw_path):
            product = world.products.get(unquote(match.group(1)))
            if product is None:
                return _json(404, {"statusCode": 404, "message": "PRODUCT-NOT-FOUND"})
            return _json(200, detail_json(world, product))
        return FakeResponse(200, _SPA, "text/html; charset=utf-8")  # the real site's SPA fallback

    def _listing(self, category_id: int, query: Mapping[str, str]) -> FakeResponse:
        world = self.world
        try:
            limit = 12 if self.ignore_limit or "limit" not in query else min(int(query["limit"]), 48)
            offset = int(query.get("offset", "0"))
        except ValueError:
            return _json(400, {"statusCode": 400, "message": "VALIDATION-ERROR"})
        leaf_ids = (
            [category_id]
            if category_id in world.leaves
            else [leaf.id for leaf in world.leaves.values() if leaf.l2_id == category_id]
        )
        scope = frozenset(query["shopIds"].split(",")) if query.get("shopIds") else None
        lagged = self.lagged()
        items = []
        for leaf_id in leaf_ids:
            for product in world.leaf_products(leaf_id):
                item = listing_item(world, product, scope, lagged.get(product.id, frozenset()))
                if item is not None:
                    items.append(item)
        items.sort(key=lambda item: (item["minUnitPrice"], item["id"]))
        page = [self._drifted(item) for item in items[offset : offset + limit]]
        count: Any = str(len(items)) if self.drift == "count_string" else len(items)
        return _json(200, {"products": page, "count": count})

    def _drifted(self, item: dict[str, Any]) -> dict[str, Any]:
        if self.drift == "extra_field":
            return {**item, "newField": "x"}
        if self.drift == "type_change":
            chains = [
                {**c, "productMinAmount": str(c["productMinAmount"])} for c in item["pricesOfChainStores"]
            ]
            return {**item, "pricesOfChainStores": chains}
        if self.drift == "missing_field":
            return {k: v for k, v in item.items() if k != "pricesOfChainStores"}
        return item

    # ── httpx.MockTransport ──
    def handler(self, request: httpx.Request) -> httpx.Response:
        target = request.url.raw_path.decode("ascii")
        result = self.respond(target, request.headers.get("user-agent"))
        if result == "connect":
            raise httpx.ConnectError("injected connection failure", request=request)
        assert isinstance(result, FakeResponse)
        return httpx.Response(
            result.status, content=result.body, headers={"content-type": result.content_type}
        )

    # ── threaded server ──
    @contextmanager
    def serve(self) -> Iterator[FakeServer]:
        """Serve on 127.0.0.1 (a free port) in a background thread for end-to-end runs."""
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server API
                result = fake.respond(self.path, self.headers.get("User-Agent"))
                if result == "connect":
                    self.close_connection = True
                    return
                assert isinstance(result, FakeResponse)
                self.send_response(result.status)
                self.send_header("Content-Type", result.content_type)
                self.send_header("Content-Length", str(len(result.body)))
                self.end_headers()
                self.wfile.write(result.body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - quiet test output
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            yield FakeServer(base=base, api_base=base + self.api_prefix, xlsx_url=base + XLSX_PATH)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@dataclass(frozen=True, slots=True)
class FakeServer:
    base: str
    api_base: str
    xlsx_url: str


# ───────────────────────────── test helpers ─────────────────────────────


class FakeClock:
    """Monotonic clock that only moves when :meth:`sleep` is called (or :meth:`advance`)."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


def fake_settings(*, api_base: str = API_BASE, xlsx_url: str = XLSX_URL, **overrides: Any) -> Settings:
    values: dict[str, Any] = {"gvh_base_url": api_base, "gvh_xlsx_url": xlsx_url, "contact_email": CONTACT}
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


# ───────────────────────────── synthetic fixtures ─────────────────────────────


def synthetic_fixtures(data_date: date = date(2026, 10, 13)) -> dict[str, tuple[int, bytes]]:
    """``{file name: (HTTP status, body)}`` mirroring the raw sample names requested in docs/QUESTIONS.md."""
    world = build_world()
    fake = FakeGvh(world, data_date=data_date)

    def get(target: str) -> tuple[int, bytes]:
        result = fake.respond(target)
        assert isinstance(result, FakeResponse)
        return result.status, result.body

    multi = world.special["multichain"]
    tesco_budapest = world.budapest_stores("Tesco")[:5]
    out = {
        "categories.json": get("/api/categories"),
        "chain-stores.json": get("/api/chain-stores"),
        "pbc-18-o0.json": get("/api/products-by-category/18?limit=48&offset=0"),
        "pbc-18-last.json": get("/api/products-by-category/18?limit=48&offset=96"),
        "pbc-18-default.json": get("/api/products-by-category/18"),
        "pbc-18-shops.json": get(
            "/api/products-by-category/18?limit=48&offset=0&shopIds=tesco-4062,lidl-274"
        ),
        "pbc-40-o0.json": get("/api/products-by-category/40?limit=48&offset=0"),
        "pbc-7-o0.json": get("/api/products-by-category/7?limit=48&offset=0"),
        f"product-{world.special['spar_outlier']}.json": get(f"/api/product/{world.special['spar_outlier']}"),
        "product-multichain.json": get(f"/api/product/{multi}"),
        "product-shop-ok.json": get(
            f"/api/product/{world.special['tesco_zone']}/shop/{'%2C'.join(tesco_budapest)}"
        ),
        "product-shop-notfound.json": get(f"/api/product/{world.special['spar_outlier']}/shop/tesco-4062"),
    }
    status, shops = get("/api/shops")
    out["shops-head.json"] = (
        status,
        json.dumps(json.loads(shops)[:40], ensure_ascii=False, separators=(",", ":")).encode(),
    )
    return out


def write_synthetic_fixtures(directory: Path = SYNTHETIC_DIR, data_date: date = date(2026, 10, 13)) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, (status, body) in synthetic_fixtures(data_date).items():
        pretty = json.dumps(json.loads(body), ensure_ascii=False, indent=1) + "\n"
        (directory / name).write_text(pretty, encoding="utf-8")
        meta = {"synthetic": True, "status": status, "content_type": "application/json"}
        (directory / name.replace(".json", ".meta.json")).write_text(
            json.dumps(meta, indent=1) + "\n", encoding="utf-8"
        )
    world = build_world()
    (directory / "xlsx-sample.xlsx").write_bytes(xlsx_bytes(world, data_date, row_limit=150))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tests.fakegvh")
    parser.add_argument("--write-fixtures", action="store_true", help=f"(re)write {SYNTHETIC_DIR}")
    args = parser.parse_args(argv)
    if args.write_fixtures:
        write_synthetic_fixtures()
        print(f"wrote {SYNTHETIC_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
