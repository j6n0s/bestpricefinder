"""Availability refresh: ``python -m bpf.ingest availability`` (weekly; BUILD-BRIEF §4.1 recommended ingest).

``GET /product/{id}`` for every product in the leaves referenced by the ingredient ontology (``all_food``:
every food leaf) that was seen at the latest served daily data date. The detail lists **every** chain that
sells the product (no 3-chain cap) with ``availableInShops``, the stores that report a price for it. Each
(product, chain) list becomes a ``core.product_availability`` row ``as_of`` the run's date, and every listed
store gets ``has_data_date`` (docs/ENGINE.md ``Store.has_data``).

Rows are written in batches of 200 products, one transaction each, so a long run (about 1 request per second)
keeps what it fetched. Status: ``failed`` on a schema error (batches before it stay archived) or when a
prerequisite is broken; ``partial`` when products could not be fetched (404, HTTP failure after retries) or
the request budget ran out; ``ok`` otherwise (also when there is nothing to refresh, with a warning).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import psycopg

from bpf.gvh import GvhBudgetExceeded, GvhClient, GvhHttpError, GvhSchemaError, ProductDetail
from bpf.ingest.common import (
    Clock,
    IngestError,
    IngestOutcome,
    RunContext,
    budapest_today,
    execute_run,
    fetch_food_leaves,
    fetch_ingredient_leaves,
    history_writable,
    mark_stores_with_data,
    sample,
    utc_now,
)
from bpf.ingest.daily import ChainResolver, Issues, fetch_chains
from bpf.ingest.reference import STORE_ID_RE

BATCH_SIZE = 200

_PA_INSERT = (
    "INSERT INTO core.product_availability (product_id, as_of, chain_id, store_ids) VALUES (%s, %s, %s, %s) "
    "ON CONFLICT (product_id, chain_id, as_of) "
)
_PA_UPSERT = _PA_INSERT + "DO UPDATE SET store_ids = EXCLUDED.store_ids"
_PA_INSERT_ONLY = _PA_INSERT + "DO NOTHING"


@dataclass(frozen=True, slots=True)
class AvailabilityRow:
    product_id: str
    chain_id: str
    store_ids: tuple[str, ...]


def availability_rows(
    product_id: str, detail: ProductDetail, chains: ChainResolver, issues: Issues
) -> list[AvailabilityRow]:
    """One row per known chain of a product detail; store ids de-duplicated, sorted, invalid ones dropped."""
    if detail.id != product_id:
        issues.add("detail_id_mismatch", f"{product_id} -> {detail.id[:64]}")
    rows: dict[str, AvailabilityRow] = {}
    for chain in detail.chainStores:
        chain_id = chains.by_uuid(chain.uuid, chain.name or "", issues)
        if chain_id is None:
            continue
        if chain_id in rows:
            issues.add("duplicate_chain_entry", f"{product_id} {chain_id}")
            continue
        valid = set()
        for store_id in chain.availableInShops:
            if STORE_ID_RE.fullmatch(store_id):
                valid.add(store_id)
            else:
                issues.add("invalid_store_id", f"{product_id} {store_id[:40]!r}")
        rows[chain_id] = AvailabilityRow(product_id, chain_id, tuple(sorted(valid)))
    return [rows[chain_id] for chain_id in sorted(rows)]


def write_availability(
    conn: psycopg.Connection, rows: Sequence[AvailabilityRow], as_of: date, *, writable: bool
) -> tuple[int, int]:
    """Upsert one batch and mark its stores; returns (rows kept unchanged, stores marked)."""
    if not rows:
        return 0, 0
    with conn.transaction():
        existing: set[tuple[str, str]] = set()
        if not writable:
            existing = {
                (str(p), str(c))
                for p, c in conn.execute(
                    "SELECT product_id, chain_id FROM core.product_availability WHERE as_of = %s", (as_of,)
                ).fetchall()
            }
        new_rows = [r for r in rows if (r.product_id, r.chain_id) not in existing]
        with conn.cursor() as cur:
            cur.executemany(
                _PA_UPSERT if writable else _PA_INSERT_ONLY,
                [(r.product_id, as_of, r.chain_id, list(r.store_ids)) for r in new_rows],
            )
        marked = mark_stores_with_data(conn, (store for r in rows for store in r.store_ids), as_of)
    return len(rows) - len(new_rows), marked


def _products_to_refresh(conn: psycopg.Connection, leaves: frozenset[int]) -> tuple[list[str], date | None]:
    row = conn.execute("SELECT data_date FROM api.latest").fetchone()
    latest = row[0] if row else None
    if latest is None:
        return [], None
    products = conn.execute(
        "SELECT id FROM core.product WHERE category_id = ANY(%s) AND last_seen >= %s ORDER BY id",
        (sorted(leaves), latest),
    ).fetchall()
    return [str(product[0]) for product in products], latest


def availability_step(ctx: RunContext, *, all_food: bool = False) -> None:
    leaves = fetch_food_leaves(ctx.conn) if all_food else fetch_ingredient_leaves(ctx.conn)
    # A run that refreshes nothing FAILS: an ok/partial availability run counts as "recent" in
    # api.ingest_latest, and the API's Store.has_data rule would then hide every store without fresh
    # availability rows (docs/ENGINE.md).
    if not leaves:
        if all_food:
            raise IngestError("nothing to refresh: no food category stored (run `reference` first)")
        raise IngestError(
            "nothing to refresh: the ontology references no GVH leaf (--all-food refreshes all)"
        )
    products, latest = _products_to_refresh(ctx.conn, leaves)
    ctx.log.stat("leaves", len(leaves))
    ctx.log.stat("products", len(products))
    if latest is None:
        raise IngestError("nothing to refresh: no successful daily run yet (run `daily` first)")
    ctx.log.stat("daily_data_date", latest)
    chains = ChainResolver(fetch_chains(ctx.conn))
    writable = history_writable(ctx.conn, ctx.data_date)
    issues = Issues()
    batch: list[AvailabilityRow] = []
    totals = {"rows": 0, "kept": 0, "marked": 0, "fetched": 0}
    not_found: list[str] = []
    failed: list[str] = []

    def flush() -> None:
        kept, marked = write_availability(ctx.conn, batch, ctx.data_date, writable=writable)
        totals["rows"] += len(batch)
        totals["kept"] += kept
        totals["marked"] += marked
        batch.clear()

    try:
        for position, product_id in enumerate(products):
            try:
                detail = ctx.client.product(product_id)
            except GvhHttpError as exc:
                (not_found if exc.status == 404 else failed).append(product_id)
                continue
            except GvhBudgetExceeded:
                ctx.log.warn(
                    "request_budget_exhausted",
                    f"request budget used up; {len(products) - position} product(s) not refreshed",
                    degrade=True,
                )
                break
            totals["fetched"] += 1
            batch.extend(availability_rows(product_id, detail, chains, issues))
            if totals["fetched"] % BATCH_SIZE == 0:
                flush()
    except GvhSchemaError:
        flush()  # archive what was validated before the schema change, then fail loudly
        raise
    flush()
    if not_found:
        ctx.log.warn(
            "product_not_found",
            f"{len(not_found)} product(s) not found",
            degrade=True,
            products=sample(not_found),
        )
    if failed:
        ctx.log.warn(
            "product_failed",
            f"{len(failed)} product(s) failed after retries",
            degrade=True,
            products=sample(failed),
        )
    issues.report(ctx.log)
    ctx.log.stat("products_fetched", totals["fetched"])
    ctx.log.stat("availability_rows", totals["rows"])
    ctx.log.stat("availability_rows_kept", totals["kept"])
    ctx.log.stat("stores_marked_has_data", totals["marked"])
    if totals["kept"]:
        ctx.log.warn(
            "history_append_only",
            f"{totals['kept']} availability row(s) for {ctx.data_date.isoformat()} already archived; "
            "kept unchanged",
            count=totals["kept"],
        )


def run_availability(
    conn: psycopg.Connection,
    client: GvhClient,
    *,
    data_date: date | None = None,
    clock: Clock = utc_now,
    all_food: bool = False,
) -> IngestOutcome:
    """``python -m bpf.ingest availability``: refresh ``availableInShops`` (about 1 request per product)."""
    day = data_date or budapest_today(clock)
    return execute_run(
        conn,
        client,
        kind="availability",
        data_date=day,
        body=lambda ctx: availability_step(ctx, all_food=all_food),
    )
