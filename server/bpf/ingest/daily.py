"""The daily price ingest: ``python -m bpf.ingest daily`` (docs/ARCHITECTURE.md "Data flow", ENGINE.md).

Order (about 1,000-1,700 requests at <= 1 req/s):

1. **Reference** (3 requests): chains, categories, stores (``bpf.ingest.reference``). If GVH cannot be reached
   but reference data is already stored, the run goes on with it (``partial``).
2. **Daily XLSX** (1 request), cache-busted with ``?v=YYYYMMDD-<run id>`` (unique per run, trap 4) and
   checked to be the data date's file. A stale, unreadable or unreachable XLSX fails the run before anything
   is written: nothing else proves the data date.
3. **Listing** of every food leaf with ``limit=48`` paging (about 160 requests): ``productMinAmount`` (the
   price GVH displays) goes to ``product_min_amount``; the ``prices[]`` per-type MINIMA across stores go to
   ``normal_*`` / ``discounted_*`` / ``loyalty_*`` (trap 1). The listing shows at most 3 chains per product
   (trap 2): every product × chain row of the XLSX in a food leaf also gets a ``product_chain_day`` row, so
   the missing chains are completed (their listing columns stay NULL). Products with a unit outside
   {kg, l, db} are skipped with one warning naming the units (trap 5). **Loyalty prices** come only from the
   listing's ``prices[]`` LOYALTY entries (and, in step 5, the per-store endpoint): the XLSX and
   ``productMinAmount`` exclude them, so neither ever fills ``loyalty_*`` (trap 4).
   **Date agreement (trap 10).** The API has no date field and switches day at about 00:00 UTC, so the
   listing is checked against the dated XLSX: on every product × chain pair present in both, the XLSX
   ``Minimum ár`` must equal the listing's daily minimum, min(NORMAL, DISCOUNTED) of ``prices[]`` (not
   ``productMinAmount``, which is the 80 % price; not LOYALTY, which the XLSX excludes). Both are the
   cheapest store's daily price, so on the same day they agree on about 99.9 % of pairs, while consecutive
   days differ on 1.2-2.6 %. The agreeing share is always recorded (stat ``api_xlsx_agreement``); above
   ``API_XLSX_MISMATCH_MAX_SHARE`` (0.6 %) of pairs disagreeing (by more than 0.5 Ft) the run records
   ``api_xlsx_date_mismatch`` and ends ``partial``. The data are still written (the XLSX is the data date's
   by its sheet name); a later re-run overwrites the listing columns.
4. **Write** products and ``product_chain_day`` in one transaction (the archive).
5. **Per-store prices** (best effort): ``/product/{id}/shop/{ids}`` only for (product, chain) pairs whose
   XLSX ``min < max``, only for products in leaves referenced by the ingredient ontology, and only for the
   chain's Budapest stores (``budapest_only``, the M0 default). Stores of all varying chains of one product
   share one call (chunks of <= 200 ids). Rows go to ``store_price_day``; every store with a price gets
   ``has_data_date`` = the data date.

Idempotency: re-running a data date upserts the same rows. Listing columns are only overwritten by a run that
has listing data for the pair, XLSX columns only by a run that has XLSX data for it, so a later partial run
never erases good data. Rows of days the append-only trigger protects (older than yesterday in Budapest, by
the database clock) are never updated: new rows are inserted, existing ones are kept and counted in a
``history_append_only`` warning.

Status: ``failed`` when the run cannot produce a dated chain-level snapshot (reference data unavailable with
none stored, or malformed; the XLSX stale, invalid or unreachable; a listing schema error; no listing at all)
or on any unexpected error. Whatever valid data was already fetched is still archived, but a failed day is
never served (``api.latest`` ignores it).
``partial`` when something best-effort is missing (a listing leaf or per-store call failed after retries,
the request budget ran out, a per-store schema error) or when the listing and the XLSX disagree on the day
(``api_xlsx_date_mismatch``, or ``api_xlsx_date_unchecked`` when no pair could be compared). ``ok``
otherwise.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import psycopg

from bpf.gvh import (
    CategoryListing,
    DailyXlsx,
    GvhBudgetExceeded,
    GvhClient,
    GvhHttpError,
    GvhSchemaError,
    ListingProduct,
    PriceEntry,
    XlsxRow,
)
from bpf.gvh.models import min_prices
from bpf.ingest.common import (
    VALID_UNITS,
    Clock,
    IngestError,
    IngestOutcome,
    RunContext,
    RunLog,
    budapest_today,
    describe_error,
    execute_run,
    fetch_food_leaves,
    fetch_ingredient_leaves,
    history_writable,
    mark_stores_with_data,
    sample,
    utc_now,
)
from bpf.ingest.reference import chain_slug, reference_step

PRODUCT_ID_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
AMOUNT_MAX = Decimal("9999999999.99")  # numeric(12,2)
UNIT_AMOUNT_MAX = Decimal("9999999999.9999")  # numeric(14,4)
PACKAGING_MAX = Decimal("99999999.9999")  # numeric(12,4)
INT4_MAX = 2**31 - 1
UNIT_PRICE_TOLERANCE = Decimal("0.05")  # |unitAmount - amount/packaging| above 5 % is reported (trap 5)
HAS_DATA_WINDOW_DAYS = 8  # docs/ENGINE.md Store.has_data rule
#: Date agreement check (trap 10): the largest share of compared product × chain pairs that may disagree
#: before the listing is taken to serve another day than the XLSX. Same-day noise is about 0.1 %
#: (research/gvh-location/notes.md §5: 23 of 22,870 pairs; gap-gvh-promo-and-stability/verify.md (d): 0 of
#: 1,925); one day of price changes is 1.2-2.6 % of pairs (BUILD-BRIEF §3 "Stability").
API_XLSX_MISMATCH_MAX_SHARE = Decimal("0.006")
API_XLSX_TOLERANCE = Decimal("0.5")  # HUF; a larger |XLSX min - listing daily min| is a disagreement
API_XLSX_MAX_EXAMPLES = 10


# ───────────────────────────── rows ─────────────────────────────


@dataclass(slots=True)
class ProductRow:
    id: str
    name: str
    category_id: int
    unit: str
    unit_title: str | None
    packaging: Decimal | None
    bulk: bool | None
    from_listing: bool


@dataclass(slots=True)
class ChainDayRow:
    """One ``core.product_chain_day`` row. ``has_listing`` / ``has_xlsx`` say which column group this run
    knows; the other group is left untouched on re-runs."""

    product_id: str
    chain_id: str
    has_listing: bool = False
    product_min_amount: Decimal | None = None
    price_same_everywhere: bool | None = None
    normal_amount: Decimal | None = None
    normal_unit: Decimal | None = None
    discounted_amount: Decimal | None = None
    discounted_unit: Decimal | None = None
    loyalty_amount: Decimal | None = None
    loyalty_unit: Decimal | None = None
    has_xlsx: bool = False
    xlsx_min: Decimal | None = None
    xlsx_max: Decimal | None = None
    xlsx_min_unit: Decimal | None = None
    xlsx_max_unit: Decimal | None = None
    stores_carrying: int | None = None
    chain_store_count: int | None = None

    @property
    def varies_by_store(self) -> bool:
        """The XLSX says the chain's stores charge different daily prices (min < max)."""
        return self.xlsx_min is not None and self.xlsx_max is not None and self.xlsx_min < self.xlsx_max


@dataclass(frozen=True, slots=True)
class StorePriceRow:
    product_id: str
    store_id: str
    normal_amount: Decimal | None
    normal_unit: Decimal | None
    discounted_amount: Decimal | None
    discounted_unit: Decimal | None
    loyalty_amount: Decimal | None
    loyalty_unit: Decimal | None


@dataclass(frozen=True, slots=True)
class ChainRef:
    id: str
    slug: str


@dataclass
class Issues:
    """Data problems collected while building rows; reported as one warning per kind (with samples)."""

    samples: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    unknown_units: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def add(self, kind: str, item: str) -> None:
        self.samples[kind].add(item)

    def report(self, log: RunLog) -> None:
        if self.unknown_units:
            units = sorted(self.unknown_units)
            log.warn(
                "unknown_unit",
                f"skipped products with unit(s) outside kg/l/db: {', '.join(units)}",
                units={unit: sample(ids) for unit, ids in sorted(self.unknown_units.items())},
                counts={unit: len(ids) for unit, ids in sorted(self.unknown_units.items())},
            )
        for kind, items in sorted(self.samples.items()):
            log.warn(
                kind,
                f"{len(items)} item(s): {_ISSUE_TEXT.get(kind, kind)}",
                count=len(items),
                items=sample(items),
            )


_ISSUE_TEXT = {
    "invalid_product": "product skipped (id or name violates the core.product CHECKs)",
    "product_in_several_leaves": "product listed in more than one leaf (first leaf kept)",
    "unknown_chain": "price entry for a chain that is not in core.chain (skipped)",
    "chain_matched_by_name": "chain id unknown, matched by its name",
    "duplicate_chain_entry": "the same chain listed twice for a product (first kept)",
    "value_out_of_range": "price, packaging or count outside the column range (stored as NULL)",
    "unit_title_too_long": "unitTitle longer than 20 characters (stored as NULL)",
    "unit_price_inconsistent": "unitAmount differs from amount/packaging by over 5 % (kept as published)",
    "xlsx_listing_mismatch": "XLSX category or unit differs from the listing (listing kept)",
    "xlsx_duplicate_row": "the XLSX lists the same product x chain twice (first kept)",
    "xlsx_min_above_max": "XLSX minimum price above its maximum",
    "unexpected_shop": "per-store answer for a store that was not requested (ignored)",
    "detail_id_mismatch": "product detail answered with another product id",
    "invalid_store_id": "store id in availableInShops violates the store id format (dropped)",
}


class ChainResolver:
    """Maps GVH chain uuids (listing) and chain names (XLSX) to ``core.chain.id``."""

    def __init__(self, chains: Iterable[ChainRef]) -> None:
        refs = list(chains)  # iterated more than once below: never consume a one-shot iterator
        self._ids = {chain.id for chain in refs}
        self._by_slug = {chain.slug: chain.id for chain in refs}
        self._slug_of = {chain.id: chain.slug for chain in refs}

    def slug_of(self, chain_id: str) -> str:
        """The slug of a known chain id (the id itself when unknown): for readable warnings."""
        return self._slug_of.get(chain_id, chain_id)

    def by_uuid(self, uuid: str, name: str, issues: Issues) -> str | None:
        if uuid in self._ids:
            return uuid
        chain_id = self.by_name(name)
        if chain_id is not None:
            issues.add("chain_matched_by_name", f"{uuid[:64]} -> {name[:40]}")
        else:
            issues.add("unknown_chain", f"{uuid[:64]} {name[:40]}")
        return chain_id

    def by_name(self, name: str) -> str | None:
        try:
            return self._by_slug.get(chain_slug(name))
        except ValueError:
            return None


# ───────────────────────────── pure transforms ─────────────────────────────


def _checked(value: Decimal | None, limit: Decimal, issues: Issues, label: str) -> Decimal | None:
    if value is None:
        return None
    if value < 0 or value > limit:
        issues.add("value_out_of_range", label)
        return None
    return value


def _checked_int(value: int | None, issues: Issues, label: str) -> int | None:
    if value is None:
        return None
    if not 0 <= value <= INT4_MAX:
        issues.add("value_out_of_range", label)
        return None
    return value


def _valid_product(product_id: str, name: str, unit: str, issues: Issues) -> tuple[str, str] | None:
    """(clean name, normalised unit) or None (skipped and recorded)."""
    clean = " ".join(name.split())
    if not PRODUCT_ID_RE.fullmatch(product_id) or not 1 <= len(clean) <= 300:
        issues.add("invalid_product", product_id[:64])
        return None
    norm_unit = unit.strip().lower()
    if norm_unit not in VALID_UNITS:
        issues.unknown_units[unit.strip()[:20] or "<empty>"].add(product_id)
        return None
    return clean, norm_unit


def product_from_listing(product: ListingProduct, leaf_id: int, issues: Issues) -> ProductRow | None:
    valid = _valid_product(product.id, product.name, product.unit, issues)
    if valid is None:
        return None
    name, unit = valid
    unit_title = (product.unitTitle or "").strip() or None
    if unit_title is not None and len(unit_title) > 20:
        issues.add("unit_title_too_long", product.id)
        unit_title = None
    packaging = product.packaging
    if packaging is not None and not 0 < packaging <= PACKAGING_MAX:
        issues.add("value_out_of_range", f"{product.id} packaging")
        packaging = None
    return ProductRow(product.id, name, leaf_id, unit, unit_title, packaging, product.bulk, from_listing=True)


def _check_unit_price(product: ProductRow, entry: PriceEntry, issues: Issues) -> None:
    if product.packaging is None or entry.unitAmount is None or entry.amount <= 0:
        return
    expected = entry.amount / product.packaging
    if abs(entry.unitAmount - expected) > expected * UNIT_PRICE_TOLERANCE:
        issues.add("unit_price_inconsistent", product.id)


def _apply_listing_prices(
    row: ChainDayRow, product: ProductRow, entries: Sequence[PriceEntry], issues: Issues
) -> None:
    best = min_prices(entries)
    for price_type, entry in best.items():
        _check_unit_price(product, entry, issues)
        amount = _checked(entry.amount, AMOUNT_MAX, issues, f"{product.id} {price_type}")
        unit = _checked(entry.unitAmount, UNIT_AMOUNT_MAX, issues, f"{product.id} {price_type} unit")
        if price_type == "NORMAL":
            row.normal_amount, row.normal_unit = amount, unit
        elif price_type == "DISCOUNTED":
            row.discounted_amount, row.discounted_unit = amount, unit
        else:
            row.loyalty_amount, row.loyalty_unit = amount, unit


@dataclass
class Snapshot:
    """The chain-level picture of one data date: products and product × chain rows."""

    products: dict[str, ProductRow] = field(default_factory=dict)
    rows: dict[tuple[str, str], ChainDayRow] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def _add_listing(
    snap: Snapshot, listings: Mapping[int, CategoryListing], chains: ChainResolver, issues: Issues
) -> None:
    for leaf_id in sorted(listings):
        for item in listings[leaf_id].products:
            snap.stats["listing_products"] += 1
            product = product_from_listing(item, leaf_id, issues)
            if product is None:
                continue
            if product.id in snap.products:
                issues.add("product_in_several_leaves", product.id)
                continue
            snap.products[product.id] = product
            for entry in item.pricesOfChainStores:
                chain_id = chains.by_uuid(entry.id, entry.name, issues)
                if chain_id is None:
                    continue
                row = snap.rows.setdefault((product.id, chain_id), ChainDayRow(product.id, chain_id))
                if row.has_listing:
                    issues.add("duplicate_chain_entry", f"{product.id} {chain_id}")
                    continue
                row.has_listing = True
                row.product_min_amount = _checked(
                    entry.productMinAmount, AMOUNT_MAX, issues, f"{product.id} pma"
                )
                row.price_same_everywhere = entry.priceSameEverywhere
                _apply_listing_prices(row, product, entry.prices, issues)


def _add_xlsx_row(
    snap: Snapshot, xr: XlsxRow, chains: ChainResolver, food_leaves: frozenset[int], issues: Issues
) -> None:
    """Attach one XLSX row. A product already known from the listing keeps the listing's leaf and unit (a
    mismatch is reported); any other product must be in a food leaf and pass the product checks."""
    product = snap.products.get(xr.product_id)
    if product is None and xr.category_id not in food_leaves:
        snap.stats["xlsx_rows_not_food"] += 1
        return
    snap.stats["xlsx_rows_food"] += 1
    chain_id = chains.by_name(xr.chain_name)
    if chain_id is None:
        issues.add("unknown_chain", f"xlsx {xr.chain_name[:40]}")
        return
    if product is None:
        valid = _valid_product(xr.product_id, xr.product_name, xr.unit, issues)
        if valid is None:
            return
        name, unit = valid
        packaging = xr.packaging
        if packaging is not None and not 0 < packaging <= PACKAGING_MAX:
            issues.add("value_out_of_range", f"{xr.product_id} packaging")
            packaging = None
        product = ProductRow(
            xr.product_id, name, xr.category_id, unit, None, packaging, None, from_listing=False
        )
        snap.products[product.id] = product
    elif product.category_id != xr.category_id or product.unit != xr.unit.strip().lower():
        issues.add("xlsx_listing_mismatch", product.id)
    row = snap.rows.setdefault((product.id, chain_id), ChainDayRow(product.id, chain_id))
    if row.has_xlsx:
        issues.add("xlsx_duplicate_row", f"{product.id} {chain_id}")
        return
    row.has_xlsx = True
    label = f"{product.id} {chain_id}"
    row.xlsx_min = _checked(xr.min_price, AMOUNT_MAX, issues, f"{label} xlsx min")
    row.xlsx_max = _checked(xr.max_price, AMOUNT_MAX, issues, f"{label} xlsx max")
    row.xlsx_min_unit = _checked(xr.min_unit_price, UNIT_AMOUNT_MAX, issues, f"{label} xlsx min unit")
    row.xlsx_max_unit = _checked(xr.max_unit_price, UNIT_AMOUNT_MAX, issues, f"{label} xlsx max unit")
    row.stores_carrying = _checked_int(xr.stores_carrying, issues, f"{label} stores")
    row.chain_store_count = _checked_int(xr.chain_store_count, issues, f"{label} chain stores")
    if row.xlsx_min is not None and row.xlsx_max is not None and row.xlsx_min > row.xlsx_max:
        issues.add("xlsx_min_above_max", label)


def build_snapshot(
    listings: Mapping[int, CategoryListing],
    xlsx: DailyXlsx | None,
    *,
    chains: ChainResolver,
    food_leaves: frozenset[int],
    log: RunLog,
) -> Snapshot:
    """Merge the listing and the XLSX into products and product × chain rows (pure; warnings into ``log``)."""
    snap = Snapshot()
    issues = Issues()
    _add_listing(snap, listings, chains, issues)
    for xr in xlsx.rows if xlsx is not None else ():
        _add_xlsx_row(snap, xr, chains, food_leaves, issues)
    issues.report(log)
    snap.stats["products"] = len(snap.products)
    snap.stats["products_from_xlsx_only"] = sum(1 for p in snap.products.values() if not p.from_listing)
    snap.stats["chain_day_rows"] = len(snap.rows)
    snap.stats["pairs_xlsx_only"] = sum(1 for r in snap.rows.values() if r.has_xlsx and not r.has_listing)
    snap.stats["pairs_listing_only"] = sum(1 for r in snap.rows.values() if r.has_listing and not r.has_xlsx)
    snap.stats["pairs_varying"] = sum(1 for r in snap.rows.values() if r.varies_by_store)
    return snap


def listing_daily_min(row: ChainDayRow) -> Decimal | None:
    """The listing's daily minimum for one chain: the lower of the ``prices[]`` NORMAL and DISCOUNTED minima.

    This is what the XLSX ``Minimum ár`` reports: the cheapest store's daily price, DISCOUNTED included and
    LOYALTY excluded (research/gvh-location/notes.md §5; verify.md (d)). ``productMinAmount`` is NOT
    comparable (it is the price of >= 80 % of stores), and neither is LOYALTY (the XLSX omits it)."""
    values = [value for value in (row.normal_amount, row.discounted_amount) if value is not None]
    return min(values) if values else None


@dataclass(frozen=True, slots=True)
class DatePair:
    """One compared product × chain pair."""

    product_id: str
    chain_id: str
    xlsx_min: Decimal
    listing_min: Decimal


@dataclass(frozen=True, slots=True)
class DateAgreement:
    """The listing compared with the XLSX on every pair present in both with a price on each side."""

    pairs: int
    disagreeing: tuple[DatePair, ...]  # sorted by (product id, chain id)

    @property
    def agreement_share(self) -> float | None:
        """Share of compared pairs that agree (6 decimals); None when nothing could be compared."""
        return round((self.pairs - len(self.disagreeing)) / self.pairs, 6) if self.pairs else None

    @property
    def mismatch_share(self) -> float | None:
        return round(len(self.disagreeing) / self.pairs, 6) if self.pairs else None

    def exceeds(self, max_share: Decimal) -> bool:
        """More than ``max_share`` of the compared pairs disagree (exact arithmetic)."""
        return self.pairs > 0 and Decimal(len(self.disagreeing)) > max_share * self.pairs


def date_agreement(snap: Snapshot) -> DateAgreement:
    """Compare the XLSX minimum with :func:`listing_daily_min` on every product × chain pair that both the
    listing and the XLSX carry (pure). Pairs from only one source, and pairs without a price on one side, are
    not counted. A difference above ``API_XLSX_TOLERANCE`` (0.5 Ft) is a disagreement."""
    pairs = 0
    disagreeing: list[DatePair] = []
    for key in sorted(snap.rows):
        row = snap.rows[key]
        if not (row.has_listing and row.has_xlsx) or row.xlsx_min is None:
            continue
        listing_min = listing_daily_min(row)
        if listing_min is None:
            continue
        pairs += 1
        if abs(row.xlsx_min - listing_min) > API_XLSX_TOLERANCE:
            disagreeing.append(DatePair(row.product_id, row.chain_id, row.xlsx_min, listing_min))
    return DateAgreement(pairs=pairs, disagreeing=tuple(disagreeing))


def check_date_agreement(
    snap: Snapshot,
    log: RunLog,
    *,
    chains: ChainResolver,
    max_share: Decimal = API_XLSX_MISMATCH_MAX_SHARE,
) -> DateAgreement:
    """Trap 10: record the agreement stats and, when the listing looks like another day than the XLSX, the
    ``api_xlsx_date_mismatch`` warning (the run becomes ``partial``; nothing is withheld)."""
    agreement = date_agreement(snap)
    log.stat("api_xlsx_agreement", agreement.agreement_share)
    log.stat("api_xlsx_pairs_compared", agreement.pairs)
    log.stat("api_xlsx_pairs_disagreeing", len(agreement.disagreeing))
    if agreement.pairs == 0:
        log.warn(
            "api_xlsx_date_unchecked",
            "no product x chain pair could be compared between the listing and the XLSX: the listing's day "
            "is not verified",
            degrade=True,
        )
    elif agreement.exceeds(max_share):
        log.warn(
            "api_xlsx_date_mismatch",
            f"{len(agreement.disagreeing)} of {agreement.pairs} product x chain pairs "
            f"({agreement.mismatch_share:.2%}) differ between the listing and the XLSX by more than "
            f"{API_XLSX_TOLERANCE} Ft (threshold {max_share:.1%}): the API may still serve another day than "
            "the XLSX. The data are kept; re-run the daily ingest later to refresh the listing columns",
            degrade=True,
            share=agreement.mismatch_share,
            threshold=float(max_share),
            pairs=agreement.pairs,
            disagreeing=len(agreement.disagreeing),
            examples=[
                {
                    "product": pair.product_id,
                    "chain": chains.slug_of(pair.chain_id),
                    "xlsx_min": pair.xlsx_min,
                    "listing_min": pair.listing_min,
                }
                for pair in agreement.disagreeing[:API_XLSX_MAX_EXAMPLES]
            ],
        )
    return agreement


def per_store_targets(
    snap: Snapshot, ingredient_leaves: frozenset[int], stores_by_chain: Mapping[str, Sequence[str]]
) -> dict[str, tuple[str, ...]]:
    """Product id -> store ids to query: pairs with XLSX min < max, in ingredient leaves, at the given stores.
    Stores of every varying chain of a product are merged into one request list. Sorted, deterministic."""
    targets: dict[str, set[str]] = defaultdict(set)
    for (product_id, chain_id), row in snap.rows.items():
        if not row.varies_by_store or snap.products[product_id].category_id not in ingredient_leaves:
            continue
        stores = stores_by_chain.get(chain_id, ())
        if stores:
            targets[product_id].update(stores)
    return {product_id: tuple(sorted(targets[product_id])) for product_id in sorted(targets)}


def store_price_rows(
    product_id: str, prices: Mapping[str, Sequence[PriceEntry]], requested: frozenset[str], issues: Issues
) -> list[StorePriceRow]:
    """Per-store rows (minimum per price type); stores that were not requested are ignored."""
    rows: list[StorePriceRow] = []
    for store_id in sorted(prices):
        if store_id not in requested:
            issues.add("unexpected_shop", f"{product_id} {store_id[:40]}")
            continue
        best = min_prices(prices[store_id])
        values: dict[str, tuple[Decimal | None, Decimal | None]] = {}
        for price_type in ("NORMAL", "DISCOUNTED", "LOYALTY"):
            entry = best.get(price_type)
            if entry is None:
                values[price_type] = (None, None)
                continue
            label = f"{product_id} {store_id} {price_type}"
            values[price_type] = (
                _checked(entry.amount, AMOUNT_MAX, issues, label),
                _checked(entry.unitAmount, UNIT_AMOUNT_MAX, issues, f"{label} unit"),
            )
        if all(amount is None for amount, _ in values.values()):
            continue
        rows.append(
            StorePriceRow(
                product_id,
                store_id,
                *values["NORMAL"],
                *values["DISCOUNTED"],
                *values["LOYALTY"],
            )
        )
    return rows


# ───────────────────────────── database ─────────────────────────────

_PRODUCT_FROM_LISTING = """
INSERT INTO core.product AS p
    (id, name, category_id, unit, unit_title, packaging, bulk, first_seen, last_seen)
VALUES (%(id)s, %(name)s, %(category_id)s, %(unit)s, %(unit_title)s, %(packaging)s, %(bulk)s, %(d)s, %(d)s)
ON CONFLICT (id) DO UPDATE SET
    name = CASE WHEN EXCLUDED.last_seen >= p.last_seen THEN EXCLUDED.name ELSE p.name END,
    category_id = CASE WHEN EXCLUDED.last_seen >= p.last_seen
                       THEN EXCLUDED.category_id ELSE p.category_id END,
    unit = CASE WHEN EXCLUDED.last_seen >= p.last_seen THEN EXCLUDED.unit ELSE p.unit END,
    unit_title = CASE WHEN EXCLUDED.last_seen >= p.last_seen THEN EXCLUDED.unit_title ELSE p.unit_title END,
    packaging = CASE WHEN EXCLUDED.last_seen >= p.last_seen THEN EXCLUDED.packaging ELSE p.packaging END,
    bulk = CASE WHEN EXCLUDED.last_seen >= p.last_seen THEN EXCLUDED.bulk ELSE p.bulk END,
    first_seen = LEAST(p.first_seen, EXCLUDED.first_seen),
    last_seen = GREATEST(p.last_seen, EXCLUDED.last_seen)
"""

# A product known only from the XLSX never overwrites listing-only attributes (unit_title, bulk), and only a
# strictly newer day may change the others (a same-day re-run must not flip listing values to XLSX ones).
_PRODUCT_FROM_XLSX = """
INSERT INTO core.product AS p
    (id, name, category_id, unit, unit_title, packaging, bulk, first_seen, last_seen)
VALUES (%(id)s, %(name)s, %(category_id)s, %(unit)s, NULL, %(packaging)s, NULL, %(d)s, %(d)s)
ON CONFLICT (id) DO UPDATE SET
    name = CASE WHEN EXCLUDED.last_seen > p.last_seen THEN EXCLUDED.name ELSE p.name END,
    category_id = CASE WHEN EXCLUDED.last_seen > p.last_seen THEN EXCLUDED.category_id ELSE p.category_id END,
    unit = CASE WHEN EXCLUDED.last_seen > p.last_seen THEN EXCLUDED.unit ELSE p.unit END,
    packaging = CASE WHEN EXCLUDED.last_seen > p.last_seen THEN EXCLUDED.packaging ELSE p.packaging END,
    first_seen = LEAST(p.first_seen, EXCLUDED.first_seen),
    last_seen = GREATEST(p.last_seen, EXCLUDED.last_seen)
"""

_LISTING_COLS = (
    "product_min_amount",
    "price_same_everywhere",
    "normal_amount",
    "normal_unit",
    "discounted_amount",
    "discounted_unit",
    "loyalty_amount",
    "loyalty_unit",
)
_XLSX_COLS = (
    "xlsx_min",
    "xlsx_max",
    "xlsx_min_unit",
    "xlsx_max_unit",
    "stores_carrying",
    "chain_store_count",
)
_PCD_COLS = ("data_date", "product_id", "chain_id", *_LISTING_COLS, *_XLSX_COLS)
_PCD_INSERT = (
    # Column names are module constants (no input reaches the SQL text); values are bound parameters.
    f"INSERT INTO core.product_chain_day AS t ({', '.join(_PCD_COLS)}) "  # noqa: S608
    f"VALUES ({', '.join(f'%({col})s' for col in _PCD_COLS)}) "
    "ON CONFLICT (data_date, product_id, chain_id) "
)
_PCD_UPSERT = (
    _PCD_INSERT
    + "DO UPDATE SET "
    + ", ".join(
        [f"{col} = CASE WHEN %(has_listing)s THEN EXCLUDED.{col} ELSE t.{col} END" for col in _LISTING_COLS]
        + [f"{col} = CASE WHEN %(has_xlsx)s THEN EXCLUDED.{col} ELSE t.{col} END" for col in _XLSX_COLS]
    )
)
_PCD_INSERT_ONLY = _PCD_INSERT + "DO NOTHING"

_SPD_COLS = (
    "data_date",
    "product_id",
    "store_id",
    "normal_amount",
    "normal_unit",
    "discounted_amount",
    "discounted_unit",
    "loyalty_amount",
    "loyalty_unit",
)
_SPD_INSERT = (
    f"INSERT INTO core.store_price_day ({', '.join(_SPD_COLS)}) "  # noqa: S608 - constant column names
    f"VALUES ({', '.join(['%s'] * len(_SPD_COLS))}) ON CONFLICT (data_date, product_id, store_id) "
)
_SPD_UPSERT = _SPD_INSERT + "DO UPDATE SET " + ", ".join(f"{col} = EXCLUDED.{col}" for col in _SPD_COLS[3:])
_SPD_INSERT_ONLY = _SPD_INSERT + "DO NOTHING"


def _pcd_params(row: ChainDayRow, data_date: date) -> dict[str, Any]:
    params: dict[str, Any] = {col: getattr(row, col) for col in _LISTING_COLS + _XLSX_COLS}
    params.update(
        data_date=data_date,
        product_id=row.product_id,
        chain_id=row.chain_id,
        has_listing=row.has_listing,
        has_xlsx=row.has_xlsx,
    )
    return params


_EXISTING_KEYS = {
    "product_chain_day": "SELECT product_id, chain_id FROM core.product_chain_day WHERE data_date = %s",
    "store_price_day": "SELECT product_id, store_id FROM core.store_price_day WHERE data_date = %s",
}


def _existing_keys(conn: psycopg.Connection, table: str, data_date: date) -> set[tuple[str, str]]:
    """Keys already archived for ``data_date`` (used when the day is protected by the trigger)."""
    return {(str(a), str(b)) for a, b in conn.execute(_EXISTING_KEYS[table], (data_date,)).fetchall()}


def write_snapshot(
    conn: psycopg.Connection, snap: Snapshot, data_date: date, *, writable: bool, log: RunLog
) -> None:
    """Products + product_chain_day in one transaction. ``writable=False`` (a protected past day): insert
    only the missing rows and keep the archived ones unchanged."""
    listing_products = [p for p in snap.products.values() if p.from_listing]
    xlsx_products = [p for p in snap.products.values() if not p.from_listing]
    rows = sorted(snap.rows.values(), key=lambda r: (r.product_id, r.chain_id))
    with conn.transaction():
        existing = set() if writable else _existing_keys(conn, "product_chain_day", data_date)
        new_rows = [r for r in rows if (r.product_id, r.chain_id) not in existing]
        with conn.cursor() as cur:
            cur.executemany(
                _PRODUCT_FROM_LISTING,
                [
                    {
                        "id": p.id,
                        "name": p.name,
                        "category_id": p.category_id,
                        "unit": p.unit,
                        "unit_title": p.unit_title,
                        "packaging": p.packaging,
                        "bulk": p.bulk,
                        "d": data_date,
                    }
                    for p in sorted(listing_products, key=lambda p: p.id)
                ],
            )
            cur.executemany(
                _PRODUCT_FROM_XLSX,
                [
                    {
                        "id": p.id,
                        "name": p.name,
                        "category_id": p.category_id,
                        "unit": p.unit,
                        "packaging": p.packaging,
                        "d": data_date,
                    }
                    for p in sorted(xlsx_products, key=lambda p: p.id)
                ],
            )
            cur.executemany(
                _PCD_UPSERT if writable else _PCD_INSERT_ONLY, [_pcd_params(r, data_date) for r in new_rows]
            )
    kept = len(rows) - len(new_rows)
    log.stat("chain_day_rows_kept", kept)
    if kept:
        log.warn(
            "history_append_only",
            f"{kept} product x chain row(s) for {data_date.isoformat()} are already archived and protected "
            "by "
            "the append-only trigger; kept unchanged",
            count=kept,
        )


def write_store_prices(
    conn: psycopg.Connection, rows: Sequence[StorePriceRow], data_date: date, *, writable: bool, log: RunLog
) -> int:
    """store_price_day rows + has_data_date in one transaction. Returns the number of stores marked."""
    ordered = sorted(rows, key=lambda r: (r.product_id, r.store_id))
    with conn.transaction():
        existing = set() if writable else _existing_keys(conn, "store_price_day", data_date)
        new_rows = [r for r in ordered if (r.product_id, r.store_id) not in existing]
        with conn.cursor() as cur:
            cur.executemany(
                _SPD_UPSERT if writable else _SPD_INSERT_ONLY,
                [
                    (
                        data_date,
                        r.product_id,
                        r.store_id,
                        r.normal_amount,
                        r.normal_unit,
                        r.discounted_amount,
                        r.discounted_unit,
                        r.loyalty_amount,
                        r.loyalty_unit,
                    )
                    for r in new_rows
                ],
            )
        marked = mark_stores_with_data(conn, (r.store_id for r in ordered), data_date)
    kept = len(ordered) - len(new_rows)
    log.stat("store_price_rows_kept", kept)
    if kept:
        log.warn(
            "history_append_only",
            f"{kept} per-store row(s) for {data_date.isoformat()} are already archived; kept unchanged",
            count=kept,
        )
    return marked


def fetch_chains(conn: psycopg.Connection) -> list[ChainRef]:
    return [ChainRef(str(i), str(s)) for i, s in conn.execute("SELECT id, slug FROM core.chain ORDER BY id")]


def fetch_target_stores(conn: psycopg.Connection, *, budapest_only: bool) -> dict[str, tuple[str, ...]]:
    """Chain id -> store ids from the latest /shops snapshot (``last_seen`` = the newest), Budapest only by
    default."""
    query = (
        "SELECT chain_id, id FROM core.store "
        "WHERE last_seen = (SELECT max(last_seen) FROM core.store) AND (is_budapest OR NOT %s) "
        "ORDER BY chain_id, id"
    )
    stores: dict[str, list[str]] = defaultdict(list)
    for chain_id, store_id in conn.execute(query, (budapest_only,)):
        stores[str(chain_id)].append(str(store_id))
    return {chain_id: tuple(ids) for chain_id, ids in stores.items()}


# ───────────────────────────── the run ─────────────────────────────


def _reference(ctx: RunContext) -> frozenset[int]:
    """Refresh the reference data; returns the food leaves of the current GVH tree. When GVH cannot be
    reached but reference data is stored, the stored food leaves are used (partial run)."""
    try:
        ref = reference_step(ctx)
    except (GvhHttpError, GvhBudgetExceeded) as exc:
        stored = ctx.conn.execute("SELECT EXISTS (SELECT 1 FROM core.chain)").fetchone()
        if not (stored and stored[0]):
            raise IngestError(
                f"reference data unavailable and none stored yet ({describe_error(exc)})"
            ) from exc
        ctx.log.warn(
            "reference_failed", f"using the stored reference data: {describe_error(exc)}", degrade=True
        )
        return fetch_food_leaves(ctx.conn)
    # Leaves GVH no longer lists stay in core.category (products reference them) but are not fetched.
    return frozenset(c.id for c in ref.categories if c.is_leaf and c.is_food)


def _fetch_listings(
    ctx: RunContext, leaves: Sequence[int]
) -> tuple[dict[int, CategoryListing], Exception | None]:
    """Listing of every leaf. HTTP failures and the budget degrade the run; a schema error stops the listing
    and is returned so the caller can archive what is valid before failing."""
    listings: dict[int, CategoryListing] = {}
    failed: list[int] = []
    incomplete: list[str] = []
    abort: Exception | None = None
    for position, leaf_id in enumerate(leaves):
        try:
            listing = ctx.client.products_by_category(leaf_id)
        except GvhHttpError:
            failed.append(leaf_id)
            continue
        except GvhBudgetExceeded:
            ctx.log.warn(
                "request_budget_exhausted",
                f"request budget used up during the listing; {len(leaves) - position} leaf(s) not fetched",
                degrade=True,
                leaves=list(leaves[position:]),
            )
            break
        except GvhSchemaError as exc:
            abort = exc
            break
        listings[leaf_id] = listing
        if listing.missing or listing.duplicates or listing.count_changed:
            incomplete.append(f"{leaf_id}: {len(listing.products)}/{listing.count}")
    if failed:
        ctx.log.warn(
            "listing_failed",
            f"{len(failed)} leaf listing(s) failed after retries (their products rely on the XLSX)",
            degrade=True,
            leaves=failed,
        )
    if incomplete:
        ctx.log.warn(
            "listing_incomplete",
            f"{len(incomplete)} leaf listing(s) changed while paging (products shifted between pages)",
            leaves=incomplete,
        )
    ctx.log.stat("leaves_fetched", len(listings))
    ctx.log.stat("listing_pages", sum(listing.pages for listing in listings.values()))
    return listings, abort


def _per_store(ctx: RunContext, snap: Snapshot, writable: bool, *, budapest_only: bool) -> None:
    leaves = fetch_ingredient_leaves(ctx.conn)
    ctx.log.stat("ingredient_leaves", len(leaves))
    if not leaves:
        ctx.log.warn(
            "no_ingredient_leaves",
            "the ingredient ontology (app.ingredient) references no GVH leaf: no per-store prices fetched",
        )
        return
    stores_by_chain = fetch_target_stores(ctx.conn, budapest_only=budapest_only)
    targets = per_store_targets(snap, leaves, stores_by_chain)
    ctx.log.stat("per_store_products", len(targets))
    requests_before = ctx.client.stats.requests
    issues = Issues()
    rows: list[StorePriceRow] = []
    failed: list[str] = []
    for position, (product_id, store_ids) in enumerate(targets.items()):
        try:
            prices = ctx.client.product_shop_prices(product_id, store_ids)
        except GvhHttpError:
            failed.append(product_id)
            continue
        except GvhBudgetExceeded:
            ctx.log.warn(
                "request_budget_exhausted",
                f"request budget used up; per-store prices of {len(targets) - position} product(s) "
                "not fetched",
                degrade=True,
            )
            break
        except GvhSchemaError as exc:
            ctx.log.warn(
                "schema_error",
                f"per-store prices stopped: {describe_error(exc)}",
                degrade=True,
                product=product_id,
            )
            break
        rows.extend(store_price_rows(product_id, prices, frozenset(store_ids), issues))
    if failed:
        ctx.log.warn(
            "per_store_failed",
            f"per-store prices of {len(failed)} product(s) failed after retries",
            degrade=True,
            products=sample(failed),
        )
    issues.report(ctx.log)
    marked = write_store_prices(ctx.conn, rows, ctx.data_date, writable=writable, log=ctx.log)
    ctx.log.stat("per_store_requests", ctx.client.stats.requests - requests_before)
    ctx.log.stat("store_price_rows", len(rows))
    ctx.log.stat("stores_with_store_prices", len({row.store_id for row in rows}))
    ctx.log.stat("stores_marked_has_data", marked)
    if rows:
        _warn_if_availability_stale(ctx)


def _warn_if_availability_stale(ctx: RunContext) -> None:
    row = ctx.conn.execute(
        "SELECT max(data_date) FROM ops.ingest_run "
        "WHERE kind = 'availability' AND status IN ('ok', 'partial')"
    ).fetchone()
    latest = row[0] if row else None
    if latest is None or latest < ctx.data_date - timedelta(days=HAS_DATA_WINDOW_DAYS):
        ctx.log.warn(
            "availability_stale",
            "has_data_date was set only for stores with per-store prices; run `python -m bpf.ingest "
            "availability` so that the other stores keep has_data",
        )


def daily_step(ctx: RunContext, *, budapest_only: bool = True) -> None:
    food_leaves = _reference(ctx)
    if not food_leaves:
        raise IngestError("no food leaf categories")
    chains = ChainResolver(fetch_chains(ctx.conn))
    # Stale / invalid / unreachable: the run fails here, before anything is written.
    xlsx = ctx.client.daily_xlsx(ctx.data_date, run_id=ctx.run_id)
    ctx.log.stat("xlsx_rows", len(xlsx.rows))
    ctx.log.stat("food_leaves", len(food_leaves))
    listings, abort = _fetch_listings(ctx, sorted(food_leaves))
    snap = build_snapshot(listings, xlsx, chains=chains, food_leaves=food_leaves, log=ctx.log)
    for name, value in sorted(snap.stats.items()):
        ctx.log.stat(name, value)
    check_date_agreement(snap, ctx.log, chains=chains)
    writable = history_writable(ctx.conn, ctx.data_date)
    write_snapshot(ctx.conn, snap, ctx.data_date, writable=writable, log=ctx.log)
    if abort is not None:
        raise abort
    if not listings:
        raise IngestError("no category listing could be fetched (the XLSX rows were archived)")
    _per_store(ctx, snap, writable, budapest_only=budapest_only)


def run_daily(
    conn: psycopg.Connection,
    client: GvhClient,
    *,
    data_date: date | None = None,
    clock: Clock = utc_now,
    budapest_only: bool = True,
) -> IngestOutcome:
    """``python -m bpf.ingest daily``. ``data_date`` defaults to today in Europe/Budapest (``clock``)."""
    day = data_date or budapest_today(clock)
    return execute_run(
        conn,
        client,
        kind="daily",
        data_date=day,
        body=lambda ctx: daily_step(ctx, budapest_only=budapest_only),
    )
