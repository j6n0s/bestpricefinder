"""Reference data: chains, categories and stores (``python -m bpf.ingest reference``; step 1 of ``daily``).

Rules (BUILD-BRIEF §4.1 trap 8, docs/API.md):

* **Chain slug** from the chain name: folded to lower-case ASCII ("Müller" -> "muller"); a known chain word
  in the name wins ("PENNY Market" -> "penny"), else the folded words joined by ``-``. ``is_grocery`` is
  true for the 6 grocery chains; an unknown chain is stored as non-grocery with a warning.
* **Store format** from the id (there is no format field): ``tesco-1xxx`` hyper, ``tesco-4xxx`` express,
  any other Tesco id ``other``, non-Tesco NULL.
* **Stores that would violate a table CHECK** are never allowed to crash the run: an invalid id, no
  coordinates or coordinates outside Hungary's box skip the store; an invalid postal code, city, address or
  opening text is stored as NULL. Each case is one warning with a sample of store ids. Stores more than
  25 km from their city's median position (e.g. Rossmann Zalaegerszeg, about 111 km off) are kept and
  reported, since a radius search would place them wrongly.
* Categories: the tree is flattened (level 1 = top); ``is_food`` marks the 6 food top categories and
  everything under them. Category problems are not skippable (products reference them): they fail the run.
"""

from __future__ import annotations

import math
import re
import statistics
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import psycopg

from bpf.gvh import CategoryNode, ChainStore, GvhClient, Shop
from bpf.ingest.common import (
    Clock,
    IngestError,
    IngestOutcome,
    RunContext,
    RunLog,
    budapest_today,
    execute_run,
    sample,
    utc_now,
)

#: Chain slugs used across the app (docs/API.md), and whether the chain is a grocery chain.
KNOWN_CHAINS: Mapping[str, bool] = {
    "aldi": True,
    "auchan": True,
    "lidl": True,
    "penny": True,
    "spar": True,
    "tesco": True,
    "dm": False,
    "rossmann": False,
    "muller": False,
}
_SLUG_ALIASES = {"mueller": "muller"}

#: GVH's food top categories (BUILD-BRIEF §4.1); everything below them is food.
FOOD_TOP_CATEGORIES: tuple[str, ...] = (
    "Tejtermék, sajt, tojás",
    "Hús, hal, felvágott",
    "Zöldség, gyümölcs",
    "Pékáru",
    "Tartós élelmiszerek, italok",
    "Speciális étrend",
)

STORE_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
_POSTAL_RE = re.compile(r"[0-9]{4}")
LAT_RANGE = (45.0, 49.0)  # core.store CHECKs
LON_RANGE = (15.5, 23.5)
OUTLIER_KM = 25.0
_TEXT_LIMITS = {"city": 100, "address": 200, "opening_raw": 500}


def fold(text: str) -> str:
    """Lower-case, accents stripped, whitespace collapsed (same rule as ``bpf.pricing.model.fold_name``)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


def chain_slug(name: str) -> str:
    """Stable slug from a chain name: "Müller" -> "muller", "SPAR" -> "spar", "PENNY Market" -> "penny"."""
    words = [_SLUG_ALIASES.get(word, word) for word in re.findall(r"[a-z0-9]+", fold(name))]
    for word in words:
        if word in KNOWN_CHAINS:
            return word
    slug = "-".join(words)[:30].strip("-")
    if not slug:
        raise ValueError(f"cannot derive a slug from chain name {name!r}")
    return slug


def store_format(store_id: str, chain_slug_: str) -> str | None:
    """Tesco format from the id: ``tesco-1xxx`` hyper, ``tesco-4xxx`` express, any other Tesco ``other``."""
    if chain_slug_ != "tesco":
        return None
    match = re.fullmatch(r"tesco-([0-9]{4})", store_id)
    if match is None:
        return "other"
    return {"1": "hyper", "4": "express"}.get(match.group(1)[0], "other")


@dataclass(frozen=True, slots=True)
class ChainRow:
    id: str
    name: str
    slug: str
    is_grocery: bool


@dataclass(frozen=True, slots=True)
class CategoryRow:
    id: int
    parent_id: int | None
    name: str
    path: str
    level: int
    is_leaf: bool
    is_food: bool


@dataclass(frozen=True, slots=True)
class StoreRow:
    id: str
    chain_id: str
    postal_code: str | None
    city: str | None
    address: str | None
    lat: float
    lon: float
    opening_raw: str | None
    format: str | None


def chain_rows(chains: Sequence[ChainStore], log: RunLog) -> list[ChainRow]:
    """Validate chains and derive slugs. Chains are few and everything hangs off them: errors fail the run."""
    rows: list[ChainRow] = []
    seen_ids: set[str] = set()
    seen_slugs: dict[str, str] = {}
    unknown: list[str] = []
    for chain in chains:
        name = " ".join(chain.name.split())
        if not 1 <= len(chain.uuid) <= 64 or not 1 <= len(name) <= 100:
            raise IngestError(f"chain {chain.uuid[:64]!r}: id or name length out of range")
        if chain.uuid in seen_ids:
            raise IngestError(f"chain id {chain.uuid!r} listed twice")
        slug = chain_slug(name)
        if slug in seen_slugs:
            raise IngestError(f"chains {seen_slugs[slug]!r} and {name!r} both map to slug {slug!r}")
        seen_ids.add(chain.uuid)
        seen_slugs[slug] = name
        if slug not in KNOWN_CHAINS:
            unknown.append(name)
        rows.append(ChainRow(id=chain.uuid, name=name, slug=slug, is_grocery=KNOWN_CHAINS.get(slug, False)))
    if not rows:
        raise IngestError("GVH returned no chains")
    if unknown:
        log.warn(
            "unknown_chain",
            f"{len(unknown)} chain(s) not in the known list; stored as non-grocery",
            chains=sample(unknown),
        )
    return rows


def category_rows(nodes: Sequence[CategoryNode], log: RunLog) -> list[CategoryRow]:
    """Flatten the category tree, parents first. Fails the run on duplicate ids or CHECK violations."""
    food_names = {fold(name) for name in FOOD_TOP_CATEGORIES}
    rows: list[CategoryRow] = []
    seen: set[int] = set()
    stack: list[tuple[CategoryNode, int | None, int, bool]] = [
        (node, None, 1, fold(node.name) in food_names) for node in reversed(nodes)
    ]
    while stack:
        node, parent_id, level, is_food = stack.pop()
        name = " ".join(node.name.split())
        if node.id in seen:
            raise IngestError(f"category id {node.id} appears twice in the tree")
        if not 1 <= len(name) <= 200 or len(node.path) > 300 or level > 5:
            raise IngestError(f"category {node.id}: name/path length or depth out of range")
        seen.add(node.id)
        children = node.categoryNodes or []
        rows.append(CategoryRow(node.id, parent_id, name, node.path, level, not children, is_food))
        stack.extend((child, node.id, level + 1, is_food) for child in reversed(children))
    rows.sort(key=lambda row: (row.level, row.id))
    found = {fold(row.name) for row in rows if row.level == 1}
    missing = [name for name in FOOD_TOP_CATEGORIES if fold(name) not in found]
    if len(missing) == len(FOOD_TOP_CATEGORIES):
        raise IngestError("none of the food top categories is in the GVH category tree")
    if missing:
        log.warn("food_category_missing", f"{len(missing)} food top category(ies) not found", names=missing)
    return rows


def _clean_text(value: str | None, limit: int) -> tuple[str | None, bool]:
    """(cleaned text or None, ok). Too long -> (None, False)."""
    if value is None:
        return None, True
    text = " ".join(value.split())
    if not text:
        return None, True
    if len(text) > limit:
        return None, False
    return text, True


def store_rows(shops: Sequence[Shop], chains: Mapping[str, ChainRow], log: RunLog) -> list[StoreRow]:
    """Validate stores against the core.store CHECKs. Never raises for a bad store: skip or NULL + warning."""
    rows: list[StoreRow] = []
    seen: set[str] = set()
    skipped: dict[str, list[str]] = defaultdict(list)
    nulled: dict[str, list[str]] = defaultdict(list)
    for shop in shops:
        store_id = shop.uuid
        label = store_id[:40]
        if not STORE_ID_RE.fullmatch(store_id):
            skipped["invalid id"].append(repr(store_id[:40]))
            continue
        if store_id in seen:
            skipped["duplicate id"].append(label)
            continue
        chain = chains.get(shop.chainStoreUuid)
        if chain is None:
            skipped["unknown chain"].append(label)
            continue
        if shop.location is None:
            skipped["no coordinates"].append(label)
            continue
        lat, lon = float(shop.location.latitude), float(shop.location.longitude)
        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and LAT_RANGE[0] <= lat <= LAT_RANGE[1]
            and LON_RANGE[0] <= lon <= LON_RANGE[1]
        ):
            skipped["coordinates outside the allowed range"].append(label)
            continue
        postal = (shop.postalCode or "").strip() or None
        if postal is not None and not _POSTAL_RE.fullmatch(postal):
            nulled["postal_code"].append(label)
            postal = None
        texts: dict[str, str | None] = {}
        for field_name, raw in (
            ("city", shop.city),
            ("address", shop.address),
            ("opening_raw", shop.openingTime),
        ):
            texts[field_name], ok = _clean_text(raw, _TEXT_LIMITS[field_name])
            if not ok:
                nulled[field_name].append(label)
        seen.add(store_id)
        rows.append(
            StoreRow(
                id=store_id,
                chain_id=chain.id,
                postal_code=postal,
                city=texts["city"],
                address=texts["address"],
                lat=lat,
                lon=lon,
                opening_raw=texts["opening_raw"],
                format=store_format(store_id, chain.slug),
            )
        )
    for reason, ids in sorted(skipped.items()):
        log.warn(
            "store_skipped",
            f"{len(ids)} store(s) skipped: {reason}",
            reason=reason,
            count=len(ids),
            stores=sample(ids),
        )
    for field_name, ids in sorted(nulled.items()):
        log.warn(
            "store_field_nulled",
            f"{len(ids)} store(s) with an invalid {field_name}; stored as NULL",
            field=field_name,
            count=len(ids),
            stores=sample(ids),
        )
    return rows


def _city_key(city: str | None) -> str | None:
    if city is None:
        return None
    key = fold(city)
    return "budapest" if key.startswith("budapest") else key


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine), in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def coordinate_outliers(
    rows: Sequence[StoreRow], *, max_km: float = OUTLIER_KM, min_group: int = 3
) -> list[tuple[str, float]]:
    """Stores more than ``max_km`` from the median position of their city's stores (cities with at least
    ``min_group`` stores): ``[(store id, km)]`` sorted by id. Pure; the caller only warns."""
    groups: dict[str, list[StoreRow]] = defaultdict(list)
    for row in rows:
        key = _city_key(row.city)
        if key:
            groups[key].append(row)
    found: list[tuple[str, float]] = []
    for members in groups.values():
        if len(members) < min_group:
            continue
        lat = statistics.median(row.lat for row in members)
        lon = statistics.median(row.lon for row in members)
        for row in members:
            km = _distance_km(lat, lon, row.lat, row.lon)
            if km > max_km:
                found.append((row.id, round(km, 1)))
    return sorted(found)


@dataclass(frozen=True, slots=True)
class Reference:
    chains: tuple[ChainRow, ...]
    categories: tuple[CategoryRow, ...]
    stores: tuple[StoreRow, ...]


def fetch_reference(client: GvhClient, log: RunLog) -> Reference:
    """GET /chain-stores, /categories, /shops (3 requests) and validate them."""
    chains = chain_rows(client.chain_stores(), log)
    categories = category_rows(client.categories(), log)
    stores = store_rows(client.shops(), {chain.id: chain for chain in chains}, log)
    outliers = coordinate_outliers(stores)
    if outliers:
        log.warn(
            "store_coordinate_outlier",
            f"{len(outliers)} store(s) more than {OUTLIER_KM:g} km from their city's other stores (kept)",
            stores=[f"{store_id} ({km} km)" for store_id, km in outliers[:25]],
        )
    return Reference(tuple(chains), tuple(categories), tuple(stores))


def write_reference(conn: psycopg.Connection, ref: Reference, data_date: date) -> None:
    """Upsert chains, categories (parents first) and stores in one transaction."""
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO core.chain (id, name, slug, is_grocery) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, slug = EXCLUDED.slug, "
            "is_grocery = EXCLUDED.is_grocery",
            [(c.id, c.name, c.slug, c.is_grocery) for c in ref.chains],
        )
        cur.executemany(
            "INSERT INTO core.category (id, parent_id, name, path, level, is_leaf, is_food) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET parent_id = EXCLUDED.parent_id, name = EXCLUDED.name, "
            "path = EXCLUDED.path, level = EXCLUDED.level, is_leaf = EXCLUDED.is_leaf, "
            "is_food = EXCLUDED.is_food",
            [(c.id, c.parent_id, c.name, c.path, c.level, c.is_leaf, c.is_food) for c in ref.categories],
        )
        cur.executemany(
            "INSERT INTO core.store (id, chain_id, postal_code, city, address, lat, lon, opening_raw, "
            "format, "
            "first_seen, last_seen) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET chain_id = EXCLUDED.chain_id, "
            "postal_code = EXCLUDED.postal_code, "
            "city = EXCLUDED.city, address = EXCLUDED.address, lat = EXCLUDED.lat, lon = EXCLUDED.lon, "
            "opening_raw = EXCLUDED.opening_raw, format = EXCLUDED.format, "
            "first_seen = LEAST(core.store.first_seen, EXCLUDED.first_seen), "
            "last_seen = GREATEST(core.store.last_seen, EXCLUDED.last_seen)",
            [
                (s.id, s.chain_id, s.postal_code, s.city, s.address, s.lat, s.lon, s.opening_raw, s.format)
                + (data_date, data_date)
                for s in ref.stores
            ],
        )


def reference_step(ctx: RunContext) -> Reference:
    """Fetch, validate and upsert the reference data; record stats."""
    ref = fetch_reference(ctx.client, ctx.log)
    write_reference(ctx.conn, ref, ctx.data_date)
    ctx.log.stat("chains", len(ref.chains))
    ctx.log.stat("categories", len(ref.categories))
    ctx.log.stat("food_leaves", sum(1 for c in ref.categories if c.is_leaf and c.is_food))
    ctx.log.stat("stores", len(ref.stores))
    ctx.log.stat(
        "stores_budapest", sum(1 for s in ref.stores if s.postal_code and s.postal_code.startswith("1"))
    )
    return ref


def run_reference(
    conn: psycopg.Connection, client: GvhClient, *, data_date: date | None = None, clock: Clock = utc_now
) -> IngestOutcome:
    """``python -m bpf.ingest reference``: refresh chains, categories and stores (3 requests)."""
    day = data_date or budapest_today(clock)
    return execute_run(conn, client, kind="reference", data_date=day, body=reference_step)
