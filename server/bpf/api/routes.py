"""The /api endpoints (docs/API.md, models in bpf/api/schemas.py).

Handlers reach the database only through the :class:`~bpf.api.repo.CatalogueProvider`. GET handlers are
plain ``def`` (FastAPI runs them in its thread pool); the CPU-bound POST computations (quote, plan, list) run
in worker threads behind a small capacity limiter, so a burst of large quotes cannot take every thread.

Data availability (no successful daily ingest yet, ``api.latest`` empty):

* ``/api/quote`` and the history endpoint answer 503 ``no_data`` (they are nothing but prices);
* ``/api/health`` says ``degraded``; ``/api/meta`` and ``/api/stores`` report ``data_date: null`` (and no
  store ``has_data``); recipe costs are ``null`` with ``priced_share`` 0; ``/api/list`` and ``/api/plan/*``
  work (a plan budget then has no cost table: warning ``recipe_cost_missing``, no budget check);
* when the database cannot be reached and no catalogue is cached, every catalogue endpoint answers 503
  ``no_data`` and ``/api/health`` answers 503 ``down``.

Unknown ids: ``/api/list`` (recipes, on-hand ingredients), ``/api/quote`` (ingredients, stores) and
``/api/plan/check`` (recipes; a repeated day index too) answer 422 with the field paths. Unknown ids in
``/api/plan/suggest``'s ``exclude_ingredients`` are accepted and simply exclude nothing (a client may keep an
exclusion for an ingredient the ontology later dropped). The planner's cost table (budget) is the cheapest
chain-typical cost per serving of each recipe (``cost_per_serving_from``), passed only when a budget is set.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Annotated, Any

import anyio
import anyio.to_thread
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response

from bpf.api import present, texts
from bpf.api.caching import CACHE_NONE, CACHE_SHORT, CACHE_STATIC_DATA, cached_json, model_body, no_store_json
from bpf.api.errors import InvalidRequest, NoData, NotFound
from bpf.api.repo import CatalogueProvider, DataUnavailable, Snapshot
from bpf.api.schemas import (
    ChainOut,
    ErrorResponse,
    HealthResponse,
    HistoryPoint,
    HistoryResponse,
    HistorySeries,
    IngredientsResponse,
    ListLineOut,
    ListRequest,
    ListResponse,
    MetaResponse,
    PlanCheckRequest,
    PlanCheckResponse,
    PlanDayIO,
    PlanResponse,
    PlanSuggestRequest,
    QuoteRequest,
    QuoteResponse,
    RecipeDetail,
    RecipesResponse,
    RecipeSummary,
    RecipeTag,
    Slot,
    StoresResponse,
)
from bpf.api.strictjson import COMPUTE_DECIMAL_CONTEXT
from bpf.planner import check_plan, suggest_plan
from bpf.pricing import (
    SLOTS_3,
    SLOTS_5,
    PlanDay,
    PlanRequest,
    build_list,
    candidate_products,
    fold_name,
    ingredient_history,
    quote_store,
    rank_stores,
    suggest_split,
)

HEAVY_CONCURRENCY = 4
INGREDIENT_ID_RE = re.compile(r"[a-z0-9_]{2,40}")
RECIPE_ID_RE = re.compile(r"[a-z0-9-]{2,60}")
CHAIN_SLUG_PATTERN = r"^[a-z0-9-]{1,30}$"

_COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    405: {"model": ErrorResponse, "description": "method_not_allowed"},
    429: {"model": ErrorResponse, "description": "rate_limited (with Retry-After)"},
    500: {"model": ErrorResponse, "description": "internal"},
    503: {"model": ErrorResponse, "description": "no_data"},
}
_GET_ERRORS = {**_COMMON_ERRORS, 304: {"description": "Not Modified (If-None-Match matched the ETag)"}}
_POST_ERRORS: dict[int | str, dict[str, Any]] = {
    **_COMMON_ERRORS,
    413: {"model": ErrorResponse, "description": "payload_too_large"},
    415: {"model": ErrorResponse, "description": "unsupported_media_type"},
    422: {"model": ErrorResponse, "description": "invalid_request (fields = dotted paths, never values)"},
}


# ───────────────────────────── shared plumbing ─────────────────────────────


def get_provider(request: Request) -> CatalogueProvider:
    provider = getattr(request.app.state, "provider", None)
    if provider is None:
        raise RuntimeError("the catalogue provider is not running (lifespan not started)")
    return provider  # type: ignore[no-any-return]


Provider = Annotated[CatalogueProvider, Depends(get_provider)]


def current_snapshot(provider: CatalogueProvider) -> Snapshot:
    try:
        return provider.snapshot()
    except DataUnavailable:
        raise NoData() from None


def memo_body(snap: Snapshot, key: str, build: Callable[[], bytes]) -> bytes:
    body = snap.memo.get(key)
    if body is None:
        body = build()
        snap.memo[key] = body
    return body  # type: ignore[no-any-return]


def is_stale(data_date: date | None, today: date) -> bool:
    """True when there is no data or it is older than yesterday (Europe/Budapest)."""
    return data_date is None or data_date < today - timedelta(days=1)


class HeavyRunner:
    """Runs CPU-bound work in worker threads, at most ``tokens`` at a time (created lazily in the loop)."""

    def __init__(self, tokens: int = HEAVY_CONCURRENCY) -> None:
        self.tokens = tokens
        self._limiter: anyio.CapacityLimiter | None = None

    async def run[T](self, fn: Callable[..., T], *args: Any) -> T:
        if self._limiter is None:
            self._limiter = anyio.CapacityLimiter(self.tokens)
        return await anyio.to_thread.run_sync(functools.partial(fn, *args), limiter=self._limiter)


def heavy(request: Request) -> HeavyRunner:
    runner = getattr(request.app.state, "heavy", None)
    if runner is None:
        runner = HeavyRunner()
        request.app.state.heavy = runner
    return runner  # type: ignore[no-any-return]


# ───────────────────────────── GET endpoints ─────────────────────────────


def health(request: Request, provider: Provider) -> Response:
    try:
        data_date, _ = provider.latest()
    except DataUnavailable:
        down = HealthResponse(status="down", db=False, data_date=None)
        return no_store_json(model_body(down), status_code=503)
    status = "degraded" if is_stale(data_date, provider.today()) else "ok"
    body = model_body(HealthResponse(status=status, db=True, data_date=data_date))
    return cached_json(request, body, data_date=data_date, cache_control=CACHE_NONE)


def meta(request: Request, provider: Provider) -> Response:
    snap = current_snapshot(provider)
    today = provider.today()

    def build() -> bytes:
        cat = snap.catalogue
        chains = sorted(cat.chains.values(), key=lambda c: (c.slug, c.id))
        return model_body(
            MetaResponse(
                data_date=snap.data_date,
                ingested_at=snap.ingested_at,
                stale=is_stale(snap.data_date, today),
                ksh_period=snap.ksh_period,
                chains=[ChainOut(id=c.id, slug=c.slug, name=c.name, is_grocery=c.is_grocery) for c in chains],
                attribution=texts.attribution_set(snap.data_date, snap.nutrition_sources),
                disclaimer_hu=texts.DISCLAIMER_HU,
                disclaimer_en=texts.DISCLAIMER_EN,
            )
        )

    body = memo_body(snap, f"meta:{today.isoformat()}", build)
    return cached_json(request, body, data_date=snap.data_date, cache_control=CACHE_SHORT)


def stores(request: Request, provider: Provider) -> Response:
    snap = current_snapshot(provider)

    def build() -> bytes:
        response = StoresResponse(
            data_date=snap.data_date, stores=[present.store_out(s) for s in snap.stores]
        )
        return model_body(response)

    body = memo_body(snap, "stores", build)
    return cached_json(request, body, data_date=snap.data_date, cache_control=CACHE_STATIC_DATA)


def ingredients(request: Request, provider: Provider) -> Response:
    snap = current_snapshot(provider)

    def build() -> bytes:
        cat = snap.catalogue
        items = [present.ingredient_out(cat.ingredients[i], cat) for i in sorted(cat.ingredients)]
        return model_body(IngredientsResponse(ingredients=items))

    body = memo_body(snap, "ingredients", build)
    return cached_json(request, body, data_date=snap.data_date, cache_control=CACHE_STATIC_DATA)


def _recipe_summaries(snap: Snapshot) -> list[RecipeSummary]:
    memo = snap.memo.get("recipe_summaries")
    if memo is None:
        recipes = sorted(snap.catalogue.recipes.values(), key=lambda r: (fold_name(r.title), r.id))
        memo = [present.recipe_summary(r, snap) for r in recipes]
        snap.memo["recipe_summaries"] = memo
    return memo  # type: ignore[no-any-return]


def recipes(
    request: Request,
    provider: Provider,
    slot: Annotated[Slot | None, Query(description="one of the 5 slots")] = None,
    tag: Annotated[RecipeTag | None, Query(description="one recipe tag")] = None,
    q: Annotated[
        str | None, Query(min_length=2, max_length=40, description="accent-insensitive title substring")
    ] = None,
) -> Response:
    snap = current_snapshot(provider)
    needle = fold_name(q) if q is not None else None
    items = [
        r
        for r in _recipe_summaries(snap)
        if (slot is None or slot in r.slots)
        and (tag is None or tag in r.tags)
        and (needle is None or needle in fold_name(r.title))
    ]
    body = model_body(RecipesResponse(data_date=snap.data_date, recipes=items))
    return cached_json(request, body, data_date=snap.data_date, cache_control=CACHE_SHORT)


def recipe(request: Request, provider: Provider, id: str) -> Response:  # `id`: the documented path name
    snap = current_snapshot(provider)
    found = snap.catalogue.recipes.get(id) if RECIPE_ID_RE.fullmatch(id) else None
    if found is None:
        raise NotFound()
    body = memo_body(snap, f"recipe:{found.id}", lambda: model_body(present.recipe_detail(found, snap)))
    return cached_json(request, body, data_date=snap.data_date, cache_control=CACHE_SHORT)


def history(
    request: Request,
    provider: Provider,
    id: str,  # `id`: the documented path name
    chain: Annotated[str | None, Query(pattern=CHAIN_SLUG_PATTERN, description="chain slug")] = None,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> Response:
    snap = current_snapshot(provider)
    cat = snap.catalogue
    ing = cat.ingredients.get(id) if INGREDIENT_ID_RE.fullmatch(id) else None
    if ing is None:
        raise NotFound()
    chain_ids: list[str] | None = None
    if chain is not None:
        chain_ids = [c.id for c in cat.chains.values() if c.slug == chain]
        if not chain_ids:
            raise InvalidRequest(["query.chain"])
    if snap.data_date is None:
        raise NoData()
    last = snap.data_date
    first = last - timedelta(days=days - 1)
    products = [p.id for p in candidate_products(ing, cat)] if ing.leaf_ids else []
    try:
        rows = provider.history(products, chain_ids, first, last)
    except DataUnavailable:
        raise NoData() from None
    per_chain = ingredient_history(ing, cat, rows)
    series = [
        HistorySeries(
            chain=slug,
            points=[HistoryPoint(date=d, unit_price=present.money(price)) for d, price in points],
        )
        for chain_id, points in per_chain.items()
        if (slug := snap.chain_slug(chain_id)) is not None
    ]
    series.sort(key=lambda s: s.chain)
    body = model_body(HistoryResponse(ingredient_id=ing.id, unit=ing.unit, days=days, series=series))
    return cached_json(request, body, data_date=snap.data_date, cache_control=CACHE_SHORT)


# ───────────────────────────── POST endpoints ─────────────────────────────


def compute_list(snap: Snapshot, req: ListRequest) -> bytes:
    cat = snap.catalogue
    bad = [f"items.{i}.recipe_id" for i, item in enumerate(req.items) if item.recipe_id not in cat.recipes]
    bad += [
        f"on_hand.{i}.ingredient_id"
        for i, line in enumerate(req.on_hand)
        if line.ingredient_id not in cat.ingredients
    ]
    if bad:
        raise InvalidRequest(bad)
    on_hand: dict[str, Decimal] = {}
    for line in req.on_hand:
        on_hand[line.ingredient_id] = on_hand.get(line.ingredient_id, Decimal(0)) + line.qty
    lines = build_list(
        [(cat.recipes[item.recipe_id], item.servings) for item in req.items],
        cat.ingredients,
        on_hand=on_hand,
        include_optional=req.include_optional,
    )
    out = [
        ListLineOut(
            ingredient_id=line.ingredient_id,
            name_hu=cat.ingredients[line.ingredient_id].name_hu,
            qty=present.qty(line.qty),
            unit=line.unit,
            list_group=line.list_group,
            pantry=line.pantry,
            recipe_ids=list(line.recipe_ids),
        )
        for line in lines
    ]
    return model_body(ListResponse(lines=out))


def compute_quote(snap: Snapshot, req: QuoteRequest) -> bytes:
    cat = snap.catalogue
    if snap.data_date is None:
        raise NoData()
    bad = [
        f"lines.{i}.ingredient_id"
        for i, line in enumerate(req.lines)
        if line.ingredient_id not in cat.ingredients
    ]
    bad += [f"store_ids.{i}" for i, store_id in enumerate(req.store_ids) if store_id not in cat.stores]
    if bad:
        raise InvalidRequest(bad)
    lines = [(line.ingredient_id, line.qty) for line in req.lines]
    quotes = [
        quote_store(lines, cat.stores[store_id], cat, include_loyalty=req.include_loyalty)
        for store_id in req.store_ids
    ]
    response = QuoteResponse(
        data_date=snap.data_date,
        stores=[
            present.store_quote_out(q, cat.chains[cat.stores[q.store_id].chain_id].slug, cat) for q in quotes
        ],
        ranking=[present.rank_out(r) for r in rank_stores(quotes)],
        split=present.split_out(suggest_split(quotes)),
        scope_note_hu=texts.scope_note_hu(snap.data_date),
        scope_note_en=texts.scope_note_en(snap.data_date),
        attribution=texts.attribution_set(snap.data_date, snap.nutrition_sources),
    )
    return model_body(response)


def _budget(value: int | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def compute_plan(snap: Snapshot, req: PlanSuggestRequest) -> bytes:
    cat = snap.catalogue
    budget = _budget(req.weekly_budget)
    plan = suggest_plan(
        list(cat.recipes.values()),
        cat.ingredients,
        PlanRequest(
            days=req.days,
            slots=SLOTS_3 if req.slots == 3 else SLOTS_5,
            people=req.people,
            seed=req.seed,
            exclude_tags=frozenset(req.exclude_tags),
            exclude_ingredients=frozenset(req.exclude_ingredients),
            red_meat_g_per_person_week=req.red_meat_g_per_person_week,
            no_repeat_days=req.no_repeat_days,
            weekly_budget=budget,
            recipe_cost_per_serving=snap.planner_costs() if budget is not None else {},
        ),
    )
    response = PlanResponse(
        days=[PlanDayIO(index=day.index, meals=dict(day.meals)) for day in plan.days],
        checks=[present.rule_check_out(c) for c in plan.checks],
        warnings=list(plan.warnings),
    )
    return model_body(response)


def compute_check(snap: Snapshot, req: PlanCheckRequest) -> bytes:
    cat = snap.catalogue
    bad: list[str] = []
    seen: set[int] = set()
    for i, day in enumerate(req.days):
        if day.index in seen:
            bad.append(f"days.{i}.index")
        seen.add(day.index)
        bad += [
            f"days.{i}.meals.{slot}"
            for slot, recipe_id in day.meals.items()
            if recipe_id is not None and recipe_id not in cat.recipes
        ]
    if bad:
        raise InvalidRequest(bad)
    budget = _budget(req.weekly_budget)
    checks = check_plan(
        [PlanDay(index=day.index, meals=dict(day.meals)) for day in req.days],
        cat.recipes,
        cat.ingredients,
        people=req.people,
        red_meat_g_per_person_week=req.red_meat_g_per_person_week,
        weekly_budget=budget,
        recipe_cost_per_serving=snap.planner_costs() if budget is not None else None,
        no_repeat_days=req.no_repeat_days,
    )
    return model_body(PlanCheckResponse(checks=[present.rule_check_out(c) for c in checks]))


async def _post(
    request: Request, provider: CatalogueProvider, fn: Callable[[Snapshot, Any], bytes], req: Any
) -> Response:
    def work() -> bytes:
        with localcontext(COMPUTE_DECIMAL_CONTEXT):
            return fn(current_snapshot(provider), req)

    return no_store_json(await heavy(request).run(work))


async def post_list(request: Request, provider: Provider, body: ListRequest) -> Response:
    return await _post(request, provider, compute_list, body)


async def post_quote(request: Request, provider: Provider, body: QuoteRequest) -> Response:
    return await _post(request, provider, compute_quote, body)


async def post_plan_suggest(request: Request, provider: Provider, body: PlanSuggestRequest) -> Response:
    return await _post(request, provider, compute_plan, body)


async def post_plan_check(request: Request, provider: Provider, body: PlanCheckRequest) -> Response:
    return await _post(request, provider, compute_check, body)


# ───────────────────────────── registration ─────────────────────────────


def register_routes(app: FastAPI) -> None:
    """Add every endpoint of docs/API.md (``app.router.route_class`` must already be set)."""
    get = {"response_class": JSONResponse, "responses": _GET_ERRORS}
    app.get(
        "/api/health",
        response_model=HealthResponse,
        summary="Liveness and data freshness",
        response_class=JSONResponse,
        responses={**_COMMON_ERRORS, 503: {"model": HealthResponse, "description": "database unreachable"}},
    )(health)
    app.get("/api/meta", response_model=MetaResponse, summary="Data date, chains, attribution", **get)(meta)
    app.get("/api/stores", response_model=StoresResponse, summary="Every store", **get)(stores)
    app.get("/api/ingredients", response_model=IngredientsResponse, summary="The ingredient ontology", **get)(
        ingredients
    )
    app.get(
        "/api/ingredients/{id}/history",
        response_model=HistoryResponse,
        summary="Daily chain-typical unit price from our own archive",
        response_class=JSONResponse,
        responses={
            **_GET_ERRORS,
            404: {"model": ErrorResponse, "description": "not_found"},
            422: {"model": ErrorResponse, "description": "invalid_request"},
        },
    )(history)
    app.get(
        "/api/recipes",
        response_model=RecipesResponse,
        summary="Recipes with their cheapest chain-typical cost",
        response_class=JSONResponse,
        responses={**_GET_ERRORS, 422: {"model": ErrorResponse, "description": "invalid_request"}},
    )(recipes)
    app.get(
        "/api/recipes/{id}",
        response_model=RecipeDetail,
        summary="One recipe with lines, steps, chain costs and nutrition",
        response_class=JSONResponse,
        responses={
            **_GET_ERRORS,
            404: {"model": ErrorResponse, "description": "not_found"},
            422: {"model": ErrorResponse, "description": "invalid_request"},
        },
    )(recipe)
    post = {"response_class": JSONResponse, "responses": _POST_ERRORS}
    app.post("/api/list", response_model=ListResponse, summary="Aggregated shopping list", **post)(post_list)
    app.post("/api/quote", response_model=QuoteResponse, summary="Price a list at the chosen stores", **post)(
        post_quote
    )
    app.post("/api/plan/suggest", response_model=PlanResponse, summary="Suggest a rule-checked plan", **post)(
        post_plan_suggest
    )
    app.post("/api/plan/check", response_model=PlanCheckResponse, summary="Re-check an edited plan", **post)(
        post_plan_check
    )
