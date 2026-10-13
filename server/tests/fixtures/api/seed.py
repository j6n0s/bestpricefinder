"""SYNTHETIC catalogue for the API tests (see README.md in this folder: nothing here is real).

Inserted as ``bpf_ingest`` into a throwaway cluster. All amounts are made-up round numbers; the expected
results derived from them are written out in ``tests/test_api_endpoints.py``.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg

from bpf.api.app import create_app
from bpf.api.options import ApiOptions
from bpf.api.repo import CatalogueProvider
from bpf.config import Settings
from bpf.db import open_pool

with warnings.catch_warnings():  # starlette 1.x prefers httpx2 for its test client; httpx works the same
    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
    from fastapi.testclient import TestClient

D = Decimal
DATA_DATE = date(2026, 10, 12)
TODAY = date(2026, 10, 13)  # the injected "today" (Europe/Budapest): data of yesterday is not stale
NOW = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
FIRST_SEEN = date(2026, 9, 1)
NO_BUILD = Path("/nonexistent/bpf-test-web-build")

LEAF_CHICKEN, LEAF_EGG, LEAF_RICE, LEAF_OIL = 99001, 99002, 99003, 99004

CHAINS = [
    ("zz-chain-alfa", "Alfa", "alfa", True),
    ("zz-chain-beta", "Beta", "beta", True),
    ("zz-chain-gamma", "Gamma", "gamma", True),
    ("zz-chain-delta", "Delta", "delta", False),
]
# id, chain, postal code, city, has_data_date (relative to DATA_DATE in days; None = never)
STORES: list[tuple[str, str, str, str, int | None]] = [
    ("alfa-1", "zz-chain-alfa", "1051", "Budapest", 0),
    ("beta-1", "zz-chain-beta", "1111", "Budapest", 0),
    ("beta-2", "zz-chain-beta", "1111", "Budapest", -1),
    ("gamma-1", "zz-chain-gamma", "6720", "Szeged", 0),
    ("gamma-2", "zz-chain-gamma", "6720", "Szeged", -20),
    ("delta-1", "zz-chain-delta", "1051", "Budapest", None),
]
# id, name, leaf, unit, unit_title, packaging
PRODUCTS: list[tuple[str, str, int, str, str, Decimal | None]] = [
    ("zz-p-csm-a", "FRISS CSIRKEMELL FILE PULTOS", LEAF_CHICKEN, "kg", "kg", None),
    ("zz-p-csm-b", "Csirkemellfilé tálcás 500 g", LEAF_CHICKEN, "kg", "csomag", D("0.5")),
    ("zz-p-csm-panir", "Panírozott csirkemell 400 g", LEAF_CHICKEN, "kg", "csomag", D("0.4")),
    ("zz-p-tojas-10", "Tojás M 10 db", LEAF_EGG, "db", "csomag", D("10")),
    ("zz-p-tojas-6", "Tojás L 6 db", LEAF_EGG, "db", "csomag", D("6")),
    ("zz-p-rizs-1", "Rizs 1 kg", LEAF_RICE, "kg", "csomag", D("1")),
    ("zz-p-rizs-5", "Rizs 5 kg", LEAF_RICE, "kg", "csomag", D("5")),
    ("zz-p-olaj-1", "Napraforgóolaj 1 l", LEAF_OIL, "l", "csomag", D("1")),
]
# Chain rows on DATA_DATE: product, chain, product_min_amount, extra columns
CHAIN_PRICES: list[tuple[str, str, Decimal, dict[str, Any]]] = [
    ("zz-p-csm-a", "zz-chain-alfa", D(2490), {}),
    ("zz-p-csm-b", "zz-chain-alfa", D(1390), {}),
    ("zz-p-csm-panir", "zz-chain-alfa", D(500), {}),  # cheap, but excluded by the name rule "panir"
    ("zz-p-tojas-10", "zz-chain-alfa", D(899), {}),
    ("zz-p-rizs-1", "zz-chain-alfa", D(499), {}),
    ("zz-p-olaj-1", "zz-chain-alfa", D(799), {}),
    (
        "zz-p-csm-b",
        "zz-chain-beta",
        D(1490),
        {"normal_amount": D(1490), "discounted_amount": D(1290), "xlsx_min": D(1290), "xlsx_max": D(1490)},
    ),
    ("zz-p-tojas-6", "zz-chain-beta", D(499), {}),
    ("zz-p-tojas-10", "zz-chain-beta", D(999), {}),
    ("zz-p-rizs-1", "zz-chain-beta", D(549), {}),
    ("zz-p-csm-a", "zz-chain-gamma", D(2390), {}),
    ("zz-p-tojas-10", "zz-chain-gamma", D(949), {"normal_amount": D(1099), "discounted_amount": D(949)}),
    ("zz-p-rizs-1", "zz-chain-gamma", D(499), {}),
    (
        "zz-p-olaj-1",
        "zz-chain-gamma",
        D(749),
        {"loyalty_amount": D(699), "price_same_everywhere": True},
    ),
    ("zz-p-rizs-1", "zz-chain-delta", D(650), {}),
]
# Our own archive for /api/ingredients/rizs/history: (date, product, chain, product_min_amount)
HISTORY: list[tuple[date, str, str, Decimal]] = [
    (date(2026, 9, 1), "zz-p-rizs-1", "zz-chain-alfa", D(459)),  # outside 30 days
    (date(2026, 10, 1), "zz-p-rizs-1", "zz-chain-alfa", D(479)),  # inside 30 days, outside 7
    (date(2026, 10, 9), "zz-p-rizs-1", "zz-chain-alfa", D(489)),
    (date(2026, 10, 10), "zz-p-rizs-1", "zz-chain-alfa", D(489)),
    (date(2026, 10, 10), "zz-p-rizs-5", "zz-chain-alfa", D(2200)),  # 440 Ft/kg: the day's minimum
    (date(2026, 10, 11), "zz-p-rizs-1", "zz-chain-alfa", D(499)),
    (date(2026, 10, 11), "zz-p-rizs-1", "zz-chain-gamma", D(519)),
    (date(2026, 10, 13), "zz-p-rizs-1", "zz-chain-alfa", D(399)),  # after the latest successful run
]
NUTRITION = (
    "zz-nut-rizs",
    "ciqual",
    "Synthetic rice row",
    D(100),
    D(10),
    D(20),
    D(1),
    D(2),
    D("0.5"),
    D(3),
    D("0.1"),
)
KSH = (date(2026, 9, 1), "zz-paprika", "Szintetikus fűszerpaprika", "kg", D(4000))
# id, name, list_group, unit, piece_weight, pantry, leaves, include, exclude, product_units, ksh, nutrition,
# tags, perishable_days
INGREDIENTS: list[tuple[Any, ...]] = [
    (
        "csirkemell",
        "csirkemell",
        "hus_hal",
        "kg",
        None,
        False,
        [LEAF_CHICKEN],
        ["csirkemell"],
        ["panir"],
        [],
        None,
        None,
        ["poultry"],
        3,
    ),
    (
        "tojas",
        "tojás",
        "tejtermek_tojas",
        "db",
        D("0.06"),
        False,
        [LEAF_EGG],
        [],
        [],
        ["db"],
        None,
        None,
        ["egg"],
        14,
    ),
    (
        "rizs",
        "rizs",
        "szaraz_tartos",
        "kg",
        None,
        False,
        [LEAF_RICE],
        [],
        [],
        [],
        None,
        "zz-nut-rizs",
        ["grain"],
        None,
    ),
    (
        "napraforgoolaj",
        "napraforgóolaj",
        "fuszer_olaj",
        "l",
        None,
        True,
        [LEAF_OIL],
        [],
        [],
        [],
        None,
        None,
        ["fat_oil"],
        None,
    ),
    ("so", "só", "fuszer_olaj", "kg", None, True, [], [], [], [], None, None, ["spice"], None),
    (
        "pirospaprika",
        "pirospaprika",
        "fuszer_olaj",
        "kg",
        None,
        False,
        [],
        [],
        [],
        [],
        "zz-paprika",
        None,
        ["spice"],
        None,
    ),
    ("fahej", "fahéj", "fuszer_olaj", "kg", None, False, [], [], [], [], None, None, ["spice"], None),
    ("sertescomb", "sertéscomb", "hus_hal", "kg", None, False, [], [], [], [], None, None, ["red_meat"], 3),
]
# id, title, slots, servings, minutes, tags, lines [(ingredient, qty, display, optional)]
RECIPES: list[tuple[str, str, list[str], int, int | None, list[str], list[tuple[str, str, str, bool]]]] = [
    (
        "zz-csirkes-rizs",
        "Csirkés rizs",
        ["ebed", "vacsora"],
        4,
        40,
        ["foetel", "baromfi"],
        [
            ("csirkemell", "0.6", "60 dkg", False),
            ("rizs", "0.4", "40 dkg", False),
            ("napraforgoolaj", "0.03", "3 ek", False),
            ("so", "0.005", "1 tk", False),
            ("pirospaprika", "0.005", "1 tk", True),
        ],
    ),
    (
        "zz-tojasos-rizs",
        "Tojásos rizs",
        ["reggeli", "vacsora"],
        2,
        20,
        ["husmentes", "gyors"],
        [
            ("tojas", "4", "4 db", False),
            ("rizs", "0.2", "20 dkg", False),
            ("fahej", "0.002", "1 csipet", False),
        ],
    ),
    (
        "zz-rizs-koret",
        "Párolt rizs",
        ["ebed"],
        2,
        25,
        ["koret", "husmentes"],
        [("rizs", "0.2", "20 dkg", False)],
    ),
    (
        "zz-paprikas-csirke",
        "Paprikás csirke",
        ["ebed", "vacsora"],
        2,
        45,
        ["foetel", "baromfi"],
        [("csirkemell", "0.5", "50 dkg", False), ("pirospaprika", "0.01", "1 ek", False)],
    ),
    (
        "zz-porkolt",
        "Pörkölt",
        ["ebed", "vacsora"],
        4,
        90,
        ["foetel", "sertes"],
        [("sertescomb", "0.8", "80 dkg", False)],
    ),
]
STEP = "Szintetikus tesztlépés: ez a szöveg csak az API tesztjeihez készült."


def seed_reference(conn: psycopg.Connection, data_date: date = DATA_DATE) -> None:
    """Chains, stores, categories and products (what the daily run's reference step writes)."""
    for chain_id, name, slug, grocery in CHAINS:
        conn.execute(
            "INSERT INTO core.chain (id, name, slug, is_grocery) VALUES (%s, %s, %s, %s)",
            (chain_id, name, slug, grocery),
        )
    for store_id, chain_id, postal, city, has_data in STORES:
        conn.execute(
            "INSERT INTO core.store (id, chain_id, postal_code, city, address, lat, lon, format, first_seen, "
            "last_seen, has_data_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                store_id,
                chain_id,
                postal,
                city,
                f"Teszt utca {store_id}",
                47.5,
                19.05,
                "hyper" if store_id.endswith("-1") else None,
                FIRST_SEEN,
                data_date,
                None if has_data is None else data_date + timedelta(days=has_data),
            ),
        )
    conn.execute(
        "INSERT INTO core.category (id, parent_id, name, path, level, is_leaf, is_food) "
        "VALUES (99000, NULL, 'Szintetikus', 'Szintetikus', 1, false, true)"
    )
    for leaf in (LEAF_CHICKEN, LEAF_EGG, LEAF_RICE, LEAF_OIL):
        conn.execute(
            "INSERT INTO core.category (id, parent_id, name, path, level, is_leaf, is_food) "
            "VALUES (%s, 99000, %s, %s, 2, true, true)",
            (leaf, f"Levél {leaf}", f"Szintetikus/{leaf}"),
        )
    for product_id, name, leaf, unit, unit_title, packaging in PRODUCTS:
        conn.execute(
            "INSERT INTO core.product (id, name, category_id, unit, unit_title, packaging, first_seen, "
            "last_seen) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (product_id, name, leaf, unit, unit_title, packaging, FIRST_SEEN, data_date),
        )


def seed_content(conn: psycopg.Connection) -> None:
    """Nutrition, KSH, ingredients and recipes (what the content loader writes)."""
    conn.execute(
        "INSERT INTO app.nutrition (code, source, name, kcal, protein_g, carb_g, sugar_g, fat_g, satfat_g, "
        "fiber_g, salt_g) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        NUTRITION,
    )
    conn.execute(
        "INSERT INTO app.ksh_price (period, code, name, unit, price) VALUES (%s, %s, %s, %s, %s)", KSH
    )
    for row in INGREDIENTS:
        conn.execute(
            "INSERT INTO app.ingredient (id, name_hu, list_group, unit, piece_weight_kg, pantry, leaf_ids, "
            "include_patterns, exclude_patterns, product_units, ksh_code, nutrition_code, tags, "
            "perishable_days) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            row,
        )
    for recipe_id, title, slots, servings, minutes, tags, lines in RECIPES:
        add_recipe(conn, recipe_id, title, slots, servings, minutes, tags, lines)


def add_recipe(
    conn: psycopg.Connection,
    recipe_id: str,
    title: str,
    slots: list[str],
    servings: int,
    minutes: int | None,
    tags: list[str],
    lines: list[tuple[str, str, str, bool]],
) -> None:
    conn.execute(
        "INSERT INTO app.recipe (id, title, summary, slots, servings, minutes, tags, steps) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (recipe_id, title, f"Szintetikus teszt: {title}", slots, servings, minutes, tags, [STEP]),
    )
    for line_no, (ingredient_id, qty, display, optional) in enumerate(lines, start=1):
        conn.execute(
            "INSERT INTO app.recipe_line (recipe_id, line_no, ingredient_id, qty, display, optional) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (recipe_id, line_no, ingredient_id, D(qty), display, optional),
        )


def insert_chain_price(
    conn: psycopg.Connection, data_date: date, product_id: str, chain_id: str, amount: Decimal, **extra: Any
) -> None:
    columns = ["data_date", "product_id", "chain_id", "product_min_amount", *extra]
    values = [data_date, product_id, chain_id, amount, *extra.values()]
    placeholders = ", ".join(["%s"] * len(values))
    conn.execute(
        f"INSERT INTO core.product_chain_day ({', '.join(columns)}) VALUES ({placeholders})",  # noqa: S608
        values,
    )


def seed_day_prices(
    conn: psycopg.Connection,
    data_date: date = DATA_DATE,
    overrides: dict[tuple[str, str], Decimal] | None = None,
) -> None:
    """Chain rows and the per-store row for ``data_date``; ``overrides`` replaces (product, chain) amounts."""
    for product_id, chain_id, amount, extra in CHAIN_PRICES:
        amount = (overrides or {}).get((product_id, chain_id), amount)
        insert_chain_price(conn, data_date, product_id, chain_id, amount, **extra)
    conn.execute(
        "INSERT INTO core.store_price_day (data_date, product_id, store_id, normal_amount, "
        "discounted_amount) "
        "VALUES (%s, 'zz-p-csm-b', 'beta-1', 1490, 1290)",
        (data_date,),
    )


def seed_history(conn: psycopg.Connection) -> None:
    """The archive rows of other days (HISTORY)."""
    for day, product_id, chain_id, amount in HISTORY:
        insert_chain_price(conn, day, product_id, chain_id, amount)


def seed_availability(conn: psycopg.Connection, as_of: date) -> None:
    """availableInShops lists: the 6-egg pack only at beta-1, the rice at alfa-1."""
    conn.execute(
        "INSERT INTO core.product_availability (product_id, as_of, chain_id, store_ids) VALUES "
        "('zz-p-tojas-6', %s, 'zz-chain-beta', ARRAY['beta-1']), "
        "('zz-p-rizs-1', %s, 'zz-chain-alfa', ARRAY['alfa-1'])",
        (as_of, as_of),
    )


def add_run(
    conn: psycopg.Connection,
    data_date: date,
    *,
    kind: str = "daily",
    status: str = "ok",
    finished_at: datetime | None = None,
) -> None:
    finished = finished_at or datetime(data_date.year, data_date.month, data_date.day, 2, 45, tzinfo=UTC)
    conn.execute(
        "INSERT INTO ops.ingest_run (kind, status, started_at, finished_at, data_date) "
        "VALUES (%s, %s, %s, %s, %s)",
        (kind, status, finished - timedelta(minutes=30), finished, data_date),
    )


def seed_all(conn: psycopg.Connection) -> None:
    seed_reference(conn)
    seed_content(conn)
    seed_day_prices(conn)
    seed_history(conn)
    seed_availability(conn, DATA_DATE - timedelta(days=2))
    add_run(conn, DATA_DATE)


# ───────────────────────────── app helpers ─────────────────────────────


class FakeClock:
    """A monotonic clock the tests move by hand (the provider's 60 s re-check interval)."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def db_provider(
    settings: Settings, *, clock: Callable[[], float] | None = None, now: datetime = NOW
) -> CatalogueProvider:
    """A provider on a real ``bpf_api`` pool (``bpf.db.open_pool``) with an injected clock and "now"."""
    pool = open_pool("api", 1, 2, settings=settings, timeout=5.0)
    return CatalogueProvider.from_pool(pool, owns_pool=True, monotonic=clock or FakeClock(), now=lambda: now)


def api_settings(base: Settings, **overrides: Any) -> Settings:
    """``base`` (a cluster's settings) with test defaults: no web build, effectively no rate limit."""
    values: dict[str, Any] = {"web_build_dir": NO_BUILD, "api_rate_limit_per_minute": 10_000_000}
    values.update(overrides)
    return base.model_copy(update=values)


def make_client(
    settings: Settings, provider: CatalogueProvider, *, options: ApiOptions | None = None
) -> TestClient:
    app = create_app(settings, catalogue_provider=provider, options=options or ApiOptions(_env_file=None))
    return TestClient(app, raise_server_exceptions=False)


@contextmanager
def client_for(
    settings: Settings, *, clock: Callable[[], float] | None = None, options: ApiOptions | None = None
) -> Iterator[tuple[TestClient, CatalogueProvider]]:
    provider = db_provider(settings, clock=clock)
    try:
        yield make_client(settings, provider, options=options), provider
    finally:
        provider.close()
