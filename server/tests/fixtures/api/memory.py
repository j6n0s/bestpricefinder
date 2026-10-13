"""In-memory catalogue source with the SAME synthetic data as ``seed.py`` (see README.md: nothing is real).

``memory_raw()`` builds the rows ``bpf.api.repo`` would read from the views after ``seed.seed_all``; the DB
tests compare the two, which checks the view loading column by column.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import FastAPI

from bpf.api.app import create_app
from bpf.api.repo import (
    AvailabilityRow,
    CatalogueProvider,
    HistoryRow,
    Key,
    RawData,
    SourceUnavailable,
    StoreRow,
)
from bpf.config import Settings
from bpf.pricing import (
    Chain,
    ChainPrice,
    Ingredient,
    KshPrice,
    NutritionRow,
    Product,
    Recipe,
    RecipeLine,
    StorePrice,
)
from tests.fixtures.api import seed
from tests.fixtures.api.seed import TestClient


def memory_raw(
    key: Key = ("memory",),
    data_date: date | None = seed.DATA_DATE,
    *,
    availability_finished_at: datetime | None = seed.AVAILABILITY_FINISHED_AT,
) -> RawData:
    has_prices = data_date is not None
    chains = [Chain(cid, slug, name, grocery) for cid, name, slug, grocery in seed.CHAINS]
    stores = [
        StoreRow(
            id=sid,
            chain_id=cid,
            postal_code=postal,
            city=city,
            address=f"Teszt utca {sid}",
            lat=47.5,
            lon=19.05,
            format="hyper" if sid.endswith("-1") else None,
            is_budapest=postal.startswith("1"),
            has_data_date=None if rel is None else seed.DATA_DATE + timedelta(days=rel),
        )
        for sid, cid, postal, city, rel in seed.STORES
    ]
    ingredients = [
        Ingredient(
            id=r[0],
            name_hu=r[1],
            list_group=r[2],
            unit=r[3],
            piece_weight_kg=r[4],
            pantry=r[5],
            leaf_ids=tuple(r[6]),
            include_patterns=tuple(r[7]),
            exclude_patterns=tuple(r[8]),
            product_units=tuple(r[9]),
            ksh_code=r[10],
            nutrition_code=r[11],
            tags=tuple(r[12]),
            perishable_days=r[13],
        )
        for r in seed.INGREDIENTS
    ]
    products = [
        Product(pid, name, leaf, unit, title, pack) for pid, name, leaf, unit, title, pack in seed.PRODUCTS
    ]
    chain_prices = (
        [
            ChainPrice(product_id=pid, chain_id=cid, product_min_amount=amount, **extra)
            for pid, cid, amount, extra in seed.CHAIN_PRICES
        ]
        if has_prices
        else []
    )
    store_prices = (
        [StorePrice("zz-p-csm-b", "beta-1", normal_amount=Decimal(1490), discounted_amount=Decimal(1290))]
        if has_prices
        else []
    )
    as_of = seed.AVAILABILITY_DATE
    availability = [
        AvailabilityRow("zz-p-tojas-6", "zz-chain-beta", as_of, ("beta-1",)),
        AvailabilityRow("zz-p-rizs-1", "zz-chain-alfa", as_of, ("alfa-1",)),
    ]
    period, code, name, unit, price = seed.KSH
    recipes = [
        Recipe(
            id=rid,
            title=title,
            slots=tuple(slots),  # type: ignore[arg-type]
            servings=servings,
            lines=tuple(
                RecipeLine(n, ing, Decimal(qty), display, optional)
                for n, (ing, qty, display, optional) in enumerate(lines, start=1)
            ),
            steps=(seed.STEP,),
            tags=tuple(tags),
            minutes=minutes,
            summary=f"Szintetikus teszt: {title}",
            tested=False,
        )
        for rid, title, slots, servings, minutes, tags, lines in seed.RECIPES
    ]
    return RawData(
        key=key,
        data_date=data_date,
        ingested_at=datetime(2026, 10, 12, 2, 45, tzinfo=UTC) if has_prices else None,
        availability_finished_at=availability_finished_at,
        chains=chains,
        stores=stores,
        ingredients=ingredients,
        products=products,
        chain_prices=chain_prices,
        store_prices=store_prices,
        availability=availability,
        ksh=[KshPrice(code, name, unit, Decimal(1), price, period)],  # type: ignore[arg-type]
        recipes=recipes,
        nutrition=[NutritionRow(*seed.NUTRITION)],  # type: ignore[arg-type]
    )


class MemorySource:
    """A ``CatalogueSource`` without a database. ``down = True`` makes every call fail like a dead DB."""

    def __init__(self, raw: RawData | None = None) -> None:
        self.raw = raw if raw is not None else memory_raw()
        self.down = False
        self.loads = 0

    def _check(self) -> None:
        if self.down:
            raise SourceUnavailable("memory source is down")

    def fetch_key(self) -> Key:
        self._check()
        return self.raw.key

    def load(self) -> RawData:
        self._check()
        self.loads += 1
        return self.raw

    def latest(self) -> tuple[date | None, datetime | None]:
        self._check()
        return self.raw.data_date, self.raw.ingested_at

    def history(
        self, product_ids: Sequence[str], chain_ids: Sequence[str] | None, first: date, last: date
    ) -> list[HistoryRow]:
        self._check()
        return []

    def session_info(self) -> tuple[str, str]:
        self._check()
        return ("memory", "on")

    def close(self) -> None:
        pass


def memory_provider(source: MemorySource | None = None, **kwargs: object) -> CatalogueProvider:
    return CatalogueProvider(source or MemorySource(), now=lambda: seed.NOW, **kwargs)  # type: ignore[arg-type]


def memory_settings(**overrides: Any) -> Settings:
    """Settings for an app without a database: no web build, effectively no rate limit."""
    values: dict[str, Any] = {"web_build_dir": seed.NO_BUILD, "api_rate_limit_per_minute": 10_000_000}
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def app_with(*, provider: CatalogueProvider | None = None, **overrides: Any) -> FastAPI:
    """An app on the in-memory catalogue; ``overrides`` are Settings fields (e.g. ``hsts=True``)."""
    return create_app(memory_settings(**overrides), catalogue_provider=provider or memory_provider())


def client_with(**kwargs: Any) -> TestClient:
    return TestClient(app_with(**kwargs), raise_server_exceptions=False)
