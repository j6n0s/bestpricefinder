"""The catalogue the API computes with, loaded from the ``api.*`` views as ``bpf_api`` (docs/ENGINE.md
``bpf.api``).

``CatalogueProvider`` keeps one immutable :class:`Snapshot` (a ``bpf.pricing.Catalogue`` plus everything
precomputed from it) and is the only way the request handlers reach the database:

* **Cache key and refresh.** A snapshot is valid for a key made of ``api.latest`` (data date and ingest time,
  so a re-run of the same day's ingest is picked up too), the latest successful ``availability`` run from
  ``api.ingest_latest`` (data date and finish time), and a fingerprint of the content and store views
  (ingredients, recipes, recipe lines, KSH, nutrition, stores, chains; a few thousand rows hashed by
  PostgreSQL).
  The key is re-checked at most once every ``recheck_interval_s`` (60 s); the catalogue is reloaded only when
  it changed. Loading runs in ONE ``REPEATABLE READ, READ ONLY`` transaction, so a daily ingest committing
  meanwhile can never mix two data dates.
* **Thread safety.** Handlers run in worker threads. One thread re-checks/reloads under a lock while the
  others keep using the current snapshot; only the very first load makes them wait.
* **Database down.** A failed re-check or reload keeps serving the cached snapshot (and retries after the
  interval). Without a snapshot, :class:`DataUnavailable` is raised (the API answers 503), and for
  ``FAILURE_BACKOFF_S`` after a failed first load it is raised at once, so queued requests do not retry a
  dead database one after another.
* **Scope.** Only products in GVH leaves referenced by some ingredient are loaded, with their latest chain
  prices, per-store prices and latest availability lists.
* **``Store.has_data``** (docs/ENGINE.md): with no data date at all, no store has data. Otherwise, while no
  ``availability`` run (status ok or partial) has finished within the last 8 days of the data date, every
  store has data; else a store has data when its ``has_data_date`` is at most 8 days before the data date.
  The finish time comes from ``api.ingest_latest`` (migration 0003) and is compared as a Europe/Budapest
  calendar date, so the rule depends on the data, never on the wall clock.
* **Recipe costs** (``recipe_chain_costs``) are precomputed per snapshot, with the summary used by the recipe
  list (``cost_per_serving_from`` / ``cheapest_chains`` / ``priced_share``, see :func:`summarise_costs`).
* **KSH rows**: ``api.ksh_latest.price`` is HUF per ONE ``unit`` (the content loader stores the CSV price
  divided by ``unit_qty``), so every row becomes ``KshPrice(unit_qty=1, price=row.price)``.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, localcontext
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import psycopg
from psycopg_pool import ConnectionPool, PoolClosed, PoolTimeout

from bpf.pricing import (
    Catalogue,
    Chain,
    ChainPrice,
    ChainRecipeCost,
    Ingredient,
    KshPrice,
    NutritionRow,
    Product,
    Recipe,
    RecipeLine,
    Store,
    StorePrice,
    recipe_chain_costs,
    whole_forints,
)

log = logging.getLogger("bpf.api")

BUDAPEST = ZoneInfo("Europe/Budapest")
HAS_DATA_WINDOW = timedelta(days=8)
MIN_CHEAPEST_SHARE = Decimal("0.9")  # docs/ENGINE.md: only chains pricing >= 90 % can be "the cheapest"
RECHECK_INTERVAL_S = 60.0
FIRST_LOAD_WAIT_S = 60.0
FAILURE_BACKOFF_S = 5.0
CONNECTION_TIMEOUT_S = 5.0
HEALTH_TIMEOUT_S = 2.0
UNITS = frozenset({"kg", "l", "db"})

type Key = tuple[object, ...]
type HistoryRow = tuple[date, str, str, Decimal | None]


class DataUnavailable(Exception):
    """The database cannot be reached (or failed) and no snapshot is cached."""


# ───────────────────────────── raw rows and the snapshot ─────────────────────────────


@dataclass(frozen=True, slots=True)
class StoreRow:
    """Row of ``api.store`` (what /api/stores shows besides ``has_data``)."""

    id: str
    chain_id: str
    postal_code: str | None
    city: str | None
    address: str | None
    lat: float | None
    lon: float | None
    format: str | None
    is_budapest: bool
    has_data_date: date | None


@dataclass(frozen=True, slots=True)
class AvailabilityRow:
    product_id: str
    chain_id: str
    as_of: date
    store_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RawData:
    """Everything read from the views in one transaction (the input of :func:`assemble_snapshot`)."""

    key: Key
    data_date: date | None
    ingested_at: datetime | None
    availability_finished_at: datetime | None
    """Finish time of the latest ``availability`` run with status ok or partial (``api.ingest_latest``)."""
    chains: Sequence[Chain]
    stores: Sequence[StoreRow]
    ingredients: Sequence[Ingredient]
    products: Sequence[Product]
    chain_prices: Sequence[ChainPrice]
    store_prices: Sequence[StorePrice]
    availability: Sequence[AvailabilityRow]
    ksh: Sequence[KshPrice]
    recipes: Sequence[Recipe]
    nutrition: Sequence[NutritionRow]


@dataclass(frozen=True, slots=True)
class StoreInfo:
    id: str
    chain_slug: str
    postal_code: str | None
    city: str | None
    address: str | None
    lat: float | None
    lon: float | None
    format: str | None
    is_budapest: bool
    has_data: bool


@dataclass(frozen=True, slots=True)
class RecipeCostSummary:
    """Cheapest chain-typical cost per serving of one recipe among the well-covered chains, with every chain
    tied at it (docs/API.md ``GET /api/recipes``, docs/ENGINE.md "Cheapest chain of a recipe")."""

    cost_per_serving_from: Decimal | None
    cheapest_chain_ids: tuple[str, ...]
    priced_share: Decimal


@dataclass(frozen=True)
class Snapshot:
    key: Key
    catalogue: Catalogue
    ingested_at: datetime | None
    ksh_period: date | None
    stores: tuple[StoreInfo, ...]  # sorted by id
    recipe_costs: Mapping[str, tuple[ChainRecipeCost, ...]]
    recipe_summaries: Mapping[str, RecipeCostSummary]
    nutrition_sources: frozenset[str]
    memo: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    """Per-snapshot cache of serialised responses (filled lazily by the routes)."""

    @property
    def data_date(self) -> date | None:
        return self.catalogue.data_date

    def chain_slug(self, chain_id: str) -> str | None:
        chain = self.catalogue.chains.get(chain_id)
        return chain.slug if chain is not None else None

    def planner_costs(self) -> dict[str, Decimal]:
        """Recipe id -> estimated cost per serving (cheapest chain-typical cost), for the planner budget."""
        return {
            recipe_id: summary.cost_per_serving_from
            for recipe_id, summary in self.recipe_summaries.items()
            if summary.cost_per_serving_from is not None
        }


_CONTEXT = Context(prec=60)  # ordinary traps; whole forints of any stored amount fit easily


def _comparable(costs: Sequence[ChainRecipeCost]) -> list[ChainRecipeCost]:
    """The chains that may be called cheapest: priced, with ``priced_share >= 0.9``, or (when none reaches
    it) the priced chains with the highest share."""
    priced = [c for c in costs if c.cost_per_serving is not None]
    candidates = [c for c in priced if c.priced_share >= MIN_CHEAPEST_SHARE]
    if not candidates and priced:
        top = max(c.priced_share for c in priced)
        candidates = [c for c in priced if c.priced_share == top]
    return candidates


def chain_cost_ranks(costs: Sequence[ChainRecipeCost]) -> dict[str, int]:
    """Competition rank (1, 1, 3) by whole-forint cost per serving among the comparable chains; chains that
    are not comparable are absent. Rank 1 is exactly the ``cheapest_chains`` group of
    :func:`summarise_costs`."""
    comparable = _comparable(costs)
    wholes = {
        c.chain_id: whole_forints(c.cost_per_serving) for c in comparable if c.cost_per_serving is not None
    }
    return {chain: 1 + sum(1 for other in wholes.values() if other < own) for chain, own in wholes.items()}


def summarise_costs(costs: Sequence[ChainRecipeCost]) -> RecipeCostSummary:
    """docs/ENGINE.md "Cheapest chain of a recipe".

    The candidates are the chains with ``priced_share >= 0.9`` or, when none reaches it, the chains with the
    highest share (so a chain that prices only a cheap subset of the lines is never "the cheapest").
    ``cost_per_serving_from`` is the lowest cost per serving among the candidates; the tie group is EVERY
    candidate at that cost in whole forints (never broken by name); ``priced_share`` is the lowest share in
    the group. Chains without a cost (nothing priced, share 0) are never candidates."""
    candidates = _comparable(costs)
    if not candidates:
        return RecipeCostSummary(None, (), Decimal(0))
    best = min(c.cost_per_serving for c in candidates if c.cost_per_serving is not None)
    target = whole_forints(best)
    tied = [
        c
        for c in candidates
        if c.cost_per_serving is not None and whole_forints(c.cost_per_serving) == target
    ]
    return RecipeCostSummary(best, tuple(c.chain_id for c in tied), min(c.priced_share for c in tied))


def availability_recent(data_date: date, availability_finished_at: datetime | None) -> bool:
    """Whether an ``availability`` run finished within the last 8 days of ``data_date`` (or after it); the
    finish time is compared as a Europe/Budapest calendar date, the data-date calendar."""
    if availability_finished_at is None:
        return False
    finished = availability_finished_at
    if finished.tzinfo is None:  # timestamptz always carries a zone; be safe with a naive value
        finished = finished.replace(tzinfo=UTC)
    return data_date - finished.astimezone(BUDAPEST).date() <= HAS_DATA_WINDOW


def store_has_data(
    has_data_date: date | None, data_date: date | None, availability_finished_at: datetime | None
) -> bool:
    """The ``Store.has_data`` rule of docs/ENGINE.md: with no data date, False; while no availability run is
    recent (:func:`availability_recent`), True; else ``has_data_date`` at most 8 days before the data date."""
    if data_date is None:
        return False
    if not availability_recent(data_date, availability_finished_at):
        return True
    return has_data_date is not None and data_date - has_data_date <= HAS_DATA_WINDOW


def assemble_snapshot(raw: RawData) -> Snapshot:
    """Build the immutable snapshot (catalogue, store list, recipe costs) from the rows of one transaction."""
    with localcontext(_CONTEXT):  # independent of whatever context the calling thread has
        return _assemble(raw)


def _assemble(raw: RawData) -> Snapshot:
    chains = {c.id: c for c in raw.chains}
    stores: dict[str, Store] = {}
    infos: list[StoreInfo] = []
    for row in sorted(raw.stores, key=lambda s: s.id):
        chain = chains.get(row.chain_id)
        if chain is None:  # pragma: no cover - api.store joins core.chain
            continue
        has_data = store_has_data(row.has_data_date, raw.data_date, raw.availability_finished_at)
        stores[row.id] = Store(row.id, row.chain_id, row.lat, row.lon, row.format, has_data)
        infos.append(
            StoreInfo(
                id=row.id,
                chain_slug=chain.slug,
                postal_code=row.postal_code,
                city=row.city,
                address=row.address,
                lat=row.lat,
                lon=row.lon,
                format=row.format,
                is_budapest=row.is_budapest,
                has_data=has_data,
            )
        )
    products = {p.id: p for p in raw.products}
    by_leaf: dict[int, list[str]] = {}
    for product in raw.products:
        by_leaf.setdefault(product.category_id, []).append(product.id)
    availability = {
        (row.product_id, row.chain_id): frozenset(row.store_ids)
        for row in raw.availability
        if row.product_id in products
    }
    catalogue = Catalogue(
        data_date=raw.data_date,
        ingredients={i.id: i for i in raw.ingredients},
        products=products,
        chains=chains,
        stores=stores,
        chain_prices={
            (cp.product_id, cp.chain_id): cp for cp in raw.chain_prices if cp.product_id in products
        },
        store_prices={
            (sp.product_id, sp.store_id): sp for sp in raw.store_prices if sp.product_id in products
        },
        availability=availability,
        products_by_leaf={leaf: tuple(sorted(ids)) for leaf, ids in by_leaf.items()},
        ksh={k.code: k for k in raw.ksh},
        recipes={r.id: r for r in raw.recipes},
        nutrition={n.code: n for n in raw.nutrition},
    )
    recipe_costs: dict[str, tuple[ChainRecipeCost, ...]] = {}
    summaries: dict[str, RecipeCostSummary] = {}
    for recipe in raw.recipes:
        try:
            costs = recipe_chain_costs(recipe, catalogue)
        except Exception:  # one broken content row must not take every recipe page down
            log.exception("recipe %s: chain costs could not be computed", recipe.id)
            costs = ()
        recipe_costs[recipe.id] = costs
        summaries[recipe.id] = summarise_costs(costs)
    return Snapshot(
        key=raw.key,
        catalogue=catalogue,
        ingested_at=raw.ingested_at,
        ksh_period=max((k.period for k in raw.ksh), default=None),
        stores=tuple(infos),
        recipe_costs=recipe_costs,
        recipe_summaries=summaries,
        nutrition_sources=frozenset(n.source for n in raw.nutrition),
    )


# ───────────────────────────── the database side ─────────────────────────────


class SourceUnavailable(Exception):
    """The data source failed (connection, pool timeout, statement error)."""


class CatalogueSource(Protocol):
    def fetch_key(self) -> Key: ...
    def load(self) -> RawData: ...
    def latest(self) -> tuple[date | None, datetime | None]: ...
    def history(
        self, product_ids: Sequence[str], chain_ids: Sequence[str] | None, first: date, last: date
    ) -> list[HistoryRow]: ...
    def session_info(self) -> tuple[str, str]: ...
    def close(self) -> None: ...


# The cache key: api.latest, the latest successful availability run, and an md5 fingerprint of every
# content/store view (a few thousand rows).
KEY_SQL = (
    "SELECT l.data_date, l.ingested_at, "
    "(SELECT a.data_date FROM api.ingest_latest a WHERE a.kind = 'availability'), "
    "(SELECT a.finished_at FROM api.ingest_latest a WHERE a.kind = 'availability'), "
    "(SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM api.ingredient t), "
    "(SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM api.recipe t), "
    "(SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM api.recipe_line t), "
    "(SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM api.ksh_latest t), "
    "(SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM api.nutrition t), "
    "(SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM api.store t), "
    "(SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM api.chain t) "
    "FROM api.latest l"
)
LATEST_SQL = "SELECT data_date, ingested_at FROM api.latest"
AVAILABILITY_RUN_SQL = "SELECT finished_at FROM api.ingest_latest WHERE kind = 'availability'"
CHAINS_SQL = "SELECT id, slug, name, is_grocery FROM api.chain"
STORES_SQL = (
    "SELECT id, chain_id, postal_code, city, address, lat, lon, format, is_budapest, has_data_date "
    "FROM api.store"
)
INGREDIENTS_SQL = (
    "SELECT id, name_hu, list_group, unit, piece_weight_kg, pantry, leaf_ids, include_patterns, "
    "exclude_patterns, product_units, ksh_code, nutrition_code, tags, perishable_days, density_kg_per_l "
    "FROM api.ingredient"
)
PRODUCTS_SQL = (
    "SELECT id, name, category_id, unit, unit_title, packaging FROM api.product "
    "WHERE category_id = ANY(%(leaves)s)"
)
CHAIN_PRICES_SQL = (
    "SELECT c.product_id, c.chain_id, c.product_min_amount, c.price_same_everywhere, c.normal_amount, "
    "c.discounted_amount, c.loyalty_amount, c.xlsx_min, c.xlsx_max, c.stores_carrying, c.chain_store_count "
    "FROM api.product_chain_latest c JOIN api.product p ON p.id = c.product_id "
    "WHERE p.category_id = ANY(%(leaves)s)"
)
STORE_PRICES_SQL = (
    "SELECT s.product_id, s.store_id, s.normal_amount, s.discounted_amount, s.loyalty_amount "
    "FROM api.store_price_latest s JOIN api.product p ON p.id = s.product_id "
    "WHERE p.category_id = ANY(%(leaves)s)"
)
AVAILABILITY_SQL = (
    "SELECT a.product_id, a.chain_id, a.as_of, a.store_ids FROM api.product_availability_latest a "
    "WHERE a.product_id IN (SELECT id FROM api.product WHERE category_id = ANY(%(leaves)s))"
)
KSH_SQL = "SELECT period, code, name, unit, price FROM api.ksh_latest"
RECIPES_SQL = "SELECT id, title, summary, slots, servings, minutes, tags, steps, tested FROM api.recipe"
LINES_SQL = (
    "SELECT recipe_id, line_no, ingredient_id, qty, display, optional FROM api.recipe_line "
    "ORDER BY recipe_id, line_no"
)
NUTRITION_SQL = (
    "SELECT code, source, name, kcal, protein_g, carb_g, sugar_g, fat_g, satfat_g, fiber_g, salt_g "
    "FROM api.nutrition"
)
HISTORY_SQL = (
    "SELECT data_date, product_id, chain_id, product_min_amount FROM api.product_chain_history "
    "WHERE product_id = ANY(%(products)s) AND data_date BETWEEN %(first)s AND %(last)s "
    "ORDER BY data_date, product_id, chain_id"
)
HISTORY_CHAIN_SQL = (
    "SELECT data_date, product_id, chain_id, product_min_amount FROM api.product_chain_history "
    "WHERE product_id = ANY(%(products)s) AND chain_id = ANY(%(chains)s) "
    "AND data_date BETWEEN %(first)s AND %(last)s ORDER BY data_date, product_id, chain_id"
)
SNAPSHOT_TX_SQL = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
READ_ONLY_TX_SQL = "SET TRANSACTION READ ONLY"

_DB_ERRORS: tuple[type[Exception], ...] = (psycopg.Error, PoolTimeout, PoolClosed)


def _dec(value: object) -> Decimal | None:
    """numeric columns arrive as Decimal already; anything else is converted through its exact text."""
    if value is None or isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _key(row: Sequence[object] | None) -> Key:
    if row is None:  # pragma: no cover - api.latest is an aggregate: always one row
        raise SourceUnavailable("api.latest returned no row")
    return tuple(row)


class ViewSource:
    """Reads the ``api.*`` views through a ``bpf_api`` connection pool (``bpf.db.open_pool("api")``)."""

    def __init__(
        self,
        pool: ConnectionPool,
        *,
        timeout_s: float = CONNECTION_TIMEOUT_S,
        health_timeout_s: float = HEALTH_TIMEOUT_S,
        owns_pool: bool = False,
    ) -> None:
        self.pool = pool
        self.timeout_s = timeout_s
        self.health_timeout_s = health_timeout_s
        self.owns_pool = owns_pool

    def _run[T](
        self, body: Callable[[psycopg.Connection], T], *, timeout: float, snapshot: bool = False
    ) -> T:
        try:
            with self.pool.connection(timeout=timeout) as conn:
                conn.execute(SNAPSHOT_TX_SQL if snapshot else READ_ONLY_TX_SQL)
                return body(conn)
        except _DB_ERRORS as exc:
            raise SourceUnavailable(f"{type(exc).__name__}: {str(exc)[:300]}") from exc

    def fetch_key(self) -> Key:
        return self._run(lambda conn: _key(conn.execute(KEY_SQL).fetchone()), timeout=self.timeout_s)

    def latest(self) -> tuple[date | None, datetime | None]:
        def body(conn: psycopg.Connection) -> tuple[date | None, datetime | None]:
            row = conn.execute(LATEST_SQL).fetchone()
            return (None, None) if row is None else (row[0], row[1])

        return self._run(body, timeout=self.health_timeout_s)

    def session_info(self) -> tuple[str, str]:
        """``current_user`` and ``transaction_read_only`` of a pooled connection, as the role configures it
        (no explicit ``SET TRANSACTION`` here: this checks the role's own defaults)."""
        try:
            with self.pool.connection(timeout=self.timeout_s) as conn:
                user = conn.execute("SELECT current_user").fetchone()
                read_only = conn.execute("SHOW transaction_read_only").fetchone()
        except _DB_ERRORS as exc:
            raise SourceUnavailable(type(exc).__name__) from exc
        return str(user[0] if user else ""), str(read_only[0] if read_only else "")

    def history(
        self, product_ids: Sequence[str], chain_ids: Sequence[str] | None, first: date, last: date
    ) -> list[HistoryRow]:
        params: dict[str, object] = {"products": list(product_ids), "first": first, "last": last}
        sql = HISTORY_SQL
        if chain_ids is not None:
            sql = HISTORY_CHAIN_SQL
            params["chains"] = list(chain_ids)

        def body(conn: psycopg.Connection) -> list[HistoryRow]:
            return [(r[0], str(r[1]), str(r[2]), _dec(r[3])) for r in conn.execute(sql, params).fetchall()]

        return self._run(body, timeout=self.timeout_s)

    def load(self) -> RawData:
        return self._run(_load_raw, timeout=self.timeout_s, snapshot=True)

    def close(self) -> None:
        if self.owns_pool:
            self.pool.close()


def _load_raw(conn: psycopg.Connection) -> RawData:
    key = _key(conn.execute(KEY_SQL).fetchone())
    data_date = key[0]
    ingested_at = key[1].astimezone(UTC) if isinstance(key[1], datetime) else None
    run = conn.execute(AVAILABILITY_RUN_SQL).fetchone()  # one row per kind at most (GROUP BY kind)
    availability_finished_at = run[0].astimezone(UTC) if run and isinstance(run[0], datetime) else None
    chains = [Chain(str(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in conn.execute(CHAINS_SQL)]
    stores = [
        StoreRow(
            id=str(r[0]),
            chain_id=str(r[1]),
            postal_code=r[2],
            city=r[3],
            address=r[4],
            lat=r[5],
            lon=r[6],
            format=r[7],
            is_budapest=bool(r[8]),
            has_data_date=r[9],
        )
        for r in conn.execute(STORES_SQL)
    ]
    ingredients = [_ingredient(r) for r in conn.execute(INGREDIENTS_SQL)]
    leaves = sorted({leaf for ing in ingredients for leaf in ing.leaf_ids})
    params = {"leaves": leaves}
    products = [
        Product(str(r[0]), str(r[1]), int(r[2]), str(r[3]), r[4], _dec(r[5]))
        for r in conn.execute(PRODUCTS_SQL, params)
    ]
    chain_prices = [
        ChainPrice(
            product_id=str(r[0]),
            chain_id=str(r[1]),
            product_min_amount=_dec(r[2]),
            price_same_everywhere=r[3],
            normal_amount=_dec(r[4]),
            discounted_amount=_dec(r[5]),
            loyalty_amount=_dec(r[6]),
            xlsx_min=_dec(r[7]),
            xlsx_max=_dec(r[8]),
            stores_carrying=r[9],
            chain_store_count=r[10],
        )
        for r in conn.execute(CHAIN_PRICES_SQL, params)
    ]
    store_prices = [
        StorePrice(str(r[0]), str(r[1]), _dec(r[2]), _dec(r[3]), _dec(r[4]))
        for r in conn.execute(STORE_PRICES_SQL, params)
    ]
    availability = [
        AvailabilityRow(str(r[0]), str(r[1]), r[2], tuple(str(s) for s in r[3] or ()))
        for r in conn.execute(AVAILABILITY_SQL, params)
    ]
    ksh = [k for k in (_ksh(r) for r in conn.execute(KSH_SQL)) if k is not None]
    lines: dict[str, list[RecipeLine]] = {}
    for r in conn.execute(LINES_SQL):
        lines.setdefault(str(r[0]), []).append(
            RecipeLine(int(r[1]), str(r[2]), Decimal(r[3]), str(r[4]), bool(r[5]))
        )
    recipes = [
        Recipe(
            id=str(r[0]),
            title=str(r[1]),
            summary=r[2],
            slots=tuple(r[3] or ()),
            servings=int(r[4]),
            minutes=r[5],
            tags=tuple(r[6] or ()),
            steps=tuple(r[7] or ()),
            tested=bool(r[8]),
            lines=tuple(lines.get(str(r[0]), ())),
        )
        for r in conn.execute(RECIPES_SQL)
    ]
    nutrition = [
        NutritionRow(str(r[0]), r[1], str(r[2]), *(_dec(v) for v in r[3:11]))
        for r in conn.execute(NUTRITION_SQL)
    ]
    return RawData(
        key=key,
        data_date=data_date,
        ingested_at=ingested_at,
        availability_finished_at=availability_finished_at,
        chains=chains,
        stores=stores,
        ingredients=ingredients,
        products=products,
        chain_prices=chain_prices,
        store_prices=store_prices,
        availability=availability,
        ksh=ksh,
        recipes=recipes,
        nutrition=nutrition,
    )


def _ingredient(r: Sequence[Any]) -> Ingredient:
    return Ingredient(
        id=str(r[0]),
        name_hu=str(r[1]),
        list_group=str(r[2]),
        unit=r[3],
        piece_weight_kg=_dec(r[4]),
        pantry=bool(r[5]),
        leaf_ids=tuple(int(x) for x in r[6] or ()),
        include_patterns=tuple(r[7] or ()),
        exclude_patterns=tuple(r[8] or ()),
        product_units=tuple(r[9] or ()),
        ksh_code=r[10],
        nutrition_code=r[11],
        tags=tuple(r[12] or ()),
        perishable_days=r[13],
        density_kg_per_l=_dec(r[14]),
    )


def _ksh(r: Sequence[Any]) -> KshPrice | None:
    """``app.ksh_price`` stores the price per ONE unit (bpf.content.ksh), so ``unit_qty`` is 1."""
    period, code, name, unit, price = r
    if unit not in UNITS:
        log.warning("KSH row %s has unit %r (not kg/l/db); ignored", code, unit)
        return None
    return KshPrice(
        code=str(code), name=str(name), unit=unit, unit_qty=Decimal(1), price=Decimal(price), period=period
    )


# ───────────────────────────── the provider ─────────────────────────────


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CatalogueProvider:
    """Cached, thread-safe access to the catalogue (see the module docstring)."""

    def __init__(
        self,
        source: CatalogueSource,
        *,
        recheck_interval_s: float = RECHECK_INTERVAL_S,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.source = source
        self.recheck_interval_s = recheck_interval_s
        self._monotonic = monotonic
        self._now = now
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._checked_at = 0.0
        self._failed_at: float | None = None

    @classmethod
    def from_pool(cls, pool: ConnectionPool, *, owns_pool: bool = False, **kwargs: Any) -> CatalogueProvider:
        return cls(ViewSource(pool, owns_pool=owns_pool), **kwargs)

    def today(self) -> date:
        """Today in Europe/Budapest (the data-date calendar)."""
        return self._now().astimezone(BUDAPEST).date()

    def _fresh(self) -> bool:
        return self._monotonic() - self._checked_at < self.recheck_interval_s

    def _raise_if_backing_off(self) -> None:
        failed = self._failed_at
        if failed is not None and self._monotonic() - failed < FAILURE_BACKOFF_S:
            raise DataUnavailable("the catalogue could not be loaded moments ago")

    def snapshot(self) -> Snapshot:
        """The current snapshot; re-checks the key when the interval has passed. Raises DataUnavailable."""
        current = self._snapshot
        if current is not None and self._fresh():
            return current
        if current is None:
            self._raise_if_backing_off()
            if not self._lock.acquire(timeout=FIRST_LOAD_WAIT_S):
                raise DataUnavailable("timed out waiting for the first catalogue load")
        elif not self._lock.acquire(blocking=False):
            return current  # another thread is re-checking; keep serving the cached snapshot
        try:
            current = self._snapshot
            if current is not None and self._fresh():
                return current  # refreshed by another thread while this one waited
            if current is None:
                self._raise_if_backing_off()
            return self._refresh(current)
        finally:
            self._lock.release()

    def _refresh(self, current: Snapshot | None) -> Snapshot:
        try:
            if current is not None and self.source.fetch_key() == current.key:
                self._checked_at = self._monotonic()
                return current
            fresh = assemble_snapshot(self.source.load())
        except SourceUnavailable as exc:
            if current is None:
                self._failed_at = self._monotonic()
                log.error("catalogue unavailable: %s", exc)
                raise DataUnavailable(str(exc)) from None
            log.warning("catalogue re-check failed, serving the cached snapshot: %s", exc)
            self._checked_at = self._monotonic()
            return current
        except Exception:
            if current is None:
                self._failed_at = self._monotonic()
                raise
            log.exception("catalogue reload failed, serving the cached snapshot")
            self._checked_at = self._monotonic()
            return current
        self._snapshot = fresh
        self._checked_at = self._monotonic()
        self._failed_at = None
        log.info("catalogue loaded for data date %s", fresh.data_date)
        return fresh

    def latest(self) -> tuple[date | None, datetime | None]:
        """``api.latest`` read now (for /api/health). Raises DataUnavailable when the DB is unreachable."""
        try:
            return self.source.latest()
        except SourceUnavailable as exc:
            raise DataUnavailable(str(exc)) from None

    def history(
        self, product_ids: Iterable[str], chain_ids: Iterable[str] | None, first: date, last: date
    ) -> list[HistoryRow]:
        ids = sorted(set(product_ids))
        if not ids:
            return []
        chains = None if chain_ids is None else sorted(set(chain_ids))
        try:
            return self.source.history(ids, chains, first, last)
        except SourceUnavailable as exc:
            raise DataUnavailable(str(exc)) from None

    def session_info(self) -> tuple[str, str]:
        try:
            return self.source.session_info()
        except SourceUnavailable as exc:
            raise DataUnavailable(str(exc)) from None

    def close(self) -> None:
        self.source.close()
