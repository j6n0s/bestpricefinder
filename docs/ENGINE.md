# Engine contract (Python modules)

**Status:** contract v1, 2026-10-13 (cloud agent). These are the public names that `bpf.api` imports. Each package's `__init__.py` re-exports exactly these names. The data types are in [`server/bpf/pricing/model.py`](../server/bpf/pricing/model.py). Everything in `bpf.pricing` and `bpf.planner` is **pure**: no I/O, no DB, no clock, no randomness except a `random.Random(seed)` passed in or created from an explicit seed.

## `bpf.pricing`
```python
fold_name(name: str) -> str                                   # from model.py

candidate_products(ing: Ingredient, cat: Catalogue) -> tuple[Product, ...]
    # leaf membership -> include (ANY) / exclude (NONE) regexes on fold_name(product.name)
    # -> product.unit allowed by ing.product_units (if non-empty) -> unit convertible to ing.unit.
    # Deterministic order: product id.

to_canonical(qty: Decimal, product_unit: str, ing: Ingredient) -> Decimal | None
    # product-unit quantity -> ingredient canonical unit. Same unit: identity. kg<->db via
    # ing.piece_weight_kg. kg<->l only via ing.density_kg_per_l. Otherwise None (not convertible).

resolve_price(product: Product, store: Store, cat: Catalogue, *, include_loyalty: bool = False) -> ResolvedPrice | None
    # 1. Store not has_data -> None.
    # 2. StorePrice row (product, store) -> min of NORMAL / DISCOUNTED (+ LOYALTY if include_loyalty),
    #    scope "store", availability "confirmed".
    # 3. Else ChainPrice (product, store.chain_id):
    #    - availability list known for (product, chain) and store not in it -> None;
    #    - amount = product_min_amount; if None: xlsx_min when xlsx_min == xlsx_max, else None;
    #    - LOYALTY only if include_loyalty and price_same_everywhere is True and loyalty_amount < amount;
    #    - scope "chain"; availability "confirmed" if the store is in the list, "assumed" if no list exists.
    # 4. Else None.
    # price_type = the type whose amount was chosen (DISCOUNTED when product_min_amount equals a
    # discounted_amount that is below normal_amount, else NORMAL; LOYALTY when the loyalty price was used).

pack_options(ing: Ingredient, store: Store, cat: Catalogue, *, include_loyalty: bool = False) -> tuple[PackOption, ...]
    # candidate_products -> resolve_price -> PackOption in canonical units.
    # Variable weight (product.unit_title folded == "kg", or no packaging): size None, price per canonical unit.
    # Packs whose unit price deviates >5 % from amount/packaging are still usable; unit_price is recomputed
    # from amount / canonical pack size (never trust GVH unitAmount blindly).

optimise_packs(qty: Decimal, options: Sequence[PackOption]) -> tuple[LinePick, ...] | None
    # Minimise checkout cost to cover >= qty with whole packs (combinations of different options allowed)
    # or exact weight for variable-weight options. Ties: less leftover, then fewer packs, then product id.
    # None if options is empty. Must be exact (no greedy) and fast: <= 2 ms typical per call.

quote_store(lines: Sequence[tuple[str, Decimal]], store: Store, cat: Catalogue, *, include_loyalty: bool = False) -> StoreQuote
    # lines = (ingredient_id, canonical qty); unknown ids raise KeyError (the API validates first).
    # Status rules: model.LineStatus. used_cost = qty * (checkout_cost / total qty bought), i.e. the required
    # quantity at the average unit price of the chosen picks. alternatives = up to 3 other options (not used
    # in the picks), ordered by their own single-option checkout cost for qty, cheapest first.

rank_stores(quotes: Sequence[StoreQuote]) -> tuple[StoreRank, ...]
    # penalized_total = checkout_total + sum over missing lines of the median checkout_cost of that
    # ingredient across the OTHER quotes that priced it (if no other store has it: no penalty, but
    # missing_count still counts). Sort by penalized_total, then missing_count, then store id.

suggest_split(quotes: Sequence[StoreQuote], *, threshold: Decimal = Decimal(1500)) -> SplitSuggestion | None
    # Best pair of stores: each line goes to the cheaper of the two (lines missing at both are ignored
    # for both). Return only if total <= best single penalized_total - threshold.

recipe_chain_costs(recipe: Recipe, cat: Catalogue) -> tuple[ChainRecipeCost, ...]
    # One entry per grocery chain (Chain.is_grocery), sorted by chain slug. Chain-typical:
    # product_min_amount unit prices, used quantities, the cheapest candidate per line, pantry lines and
    # optional lines excluded. priced_share = priced cost / (priced cost + estimated cost of missing lines,
    # where the estimate is the median of other chains' price for that line, or KSH, or 0).

build_list(items: Sequence[tuple[Recipe, Decimal]], ingredients: Mapping[str, Ingredient], *,
           on_hand: Mapping[str, Decimal] | None = None, include_optional: bool = True) -> tuple[ListLine, ...]
    # items = (recipe, servings wanted). Scale qty by servings / recipe.servings, sum per ingredient,
    # subtract on_hand, drop <= 0, sort by (list_group order from docs/DATA.md, name_hu).

ingredient_history(ing: Ingredient, cat: Catalogue,
                   rows: Iterable[tuple[date, str, str, Decimal | None]]) -> dict[str, tuple[tuple[date, Decimal], ...]]
    # rows = (data_date, product_id, chain_id, product_min_amount) from api.product_chain_history.
    # Per chain id and date: min canonical unit price among candidate_products(ing). Sorted by date.

nutrition_per_serving(recipe: Recipe, cat: Catalogue) -> NutritionPerServing | None
    # Mass per line in kg (db via piece_weight_kg, l via density or 1.0 for water-like liquids ONLY when
    # density is set); per-100 g rows from cat.nutrition. None when coverage < 0.8 or no data.
```

## `bpf.planner`
```python
suggest_plan(recipes: Sequence[Recipe], ingredients: Mapping[str, Ingredient], req: PlanRequest) -> Plan
check_plan(days: Sequence[PlanDay], recipes: Mapping[str, Recipe], ingredients: Mapping[str, Ingredient],
           *, people: int, red_meat_g_per_person_week: int = 600,
           weekly_budget: Decimal | None = None,
           recipe_cost_per_serving: Mapping[str, Decimal] | None = None) -> tuple[RuleCheck, ...]
```
Rules (per 7-day block, from public healthy-eating principles; **no MDOSZ/OKOSTÁNYÉR naming or content**):
- `fish`: ≥1 meal with a `hal` recipe.
- `legume`: ≥1 meal with a `huvelyes` recipe.
- `meat_free_day`: ≥1 day where every meal is `husmentes`.
- `red_meat`: the raw grams of `red_meat` and `processed_meat` ingredient lines eaten per person must be ≤ the cap. Per meal: line kg × 1000 / recipe.servings. Count a partial week pro rata to 7 days.
- `potato`: no two consecutive days with a `potato` ingredient in any main meal.
- `sweets`: ≤2 meals with an `edes` recipe.
- `variety`: the same recipe never repeats within `no_repeat_days`. The exception: a `ket_napos` recipe may fill the same slot on the very next day.
- `budget` (when given): the estimated cost of the week ≤ the budget.

Selection is a deterministic, seeded constraint search:
1. Fill every slot from the recipes eligible for it (exclusions applied).
2. Repair rule violations with local search.
3. Prefer reusing the same perishable ingredients within a week (leftover-aware). Score: minimise the count of distinct perishable ingredients per week.

If the pool cannot satisfy a rule, return the best plan with a failing check and a warning (e.g. `no_fish_recipe_available`); never loop forever. The time budget is 200 ms for 31 days × 5 slots.

## `bpf.gvh` (HTTP client, the only module that talks to GVH)
`GvhClient(settings, *, transport: httpx.BaseTransport | None = None)`. It is synchronous and uses `httpx.Client`. Throttle: ≤1 req/s (`gvh_min_interval_s`), 30 s timeout, at most 3 retries with backoff on 5xx and connection errors (never on 4xx). The UA comes from settings and must contain a contact address. Methods return validated pydantic models and raise `GvhSchemaError` on unexpected shapes:
- `categories()`, `chain_stores()`, `shops()`;
- `products_by_category(leaf_id, *, shop_ids=None)`, which iterates every page with `limit=48`;
- `product(product_id)`;
- `product_shop_prices(product_id, store_ids)`, which chunks into ≤200 ids per call and maps `PRODUCT-SHOP-PRICES-NOT-FOUND` to an empty result;
- `daily_xlsx(expected_date)`, which is cache-busted (`?v=YYYYMMDD`), checks that the sheet name `Napi feltöltések - YYYY-MM-DD` equals `expected_date` (else raises `StaleXlsxError`), parses decimal-comma text to Decimal and validates the header.

## `bpf.ingest` (CLI `python -m bpf.ingest {reference|daily|availability} [--date YYYY-MM-DD] [--budapest-only]`)
Runs as `bpf_ingest`. Each run inserts an `ops.ingest_run` row (`running` → `ok` | `partial` | `failed`, with request and byte counts, warnings and stats). The run is idempotent per data date (upsert today's rows; history is append-only by trigger). The order is ARCHITECTURE.md "Data flow". The data date is today in Europe/Budapest. Unit validation: products with a unit outside {kg, l, db} are skipped, with a warning listing them. Per-store calls only for (product, chain) pairs whose XLSX `min < max`, for Budapest stores, in leaves referenced by `data/ingredients.json` (the leaf set is read from `api.ingredient`).

## `bpf.content` (CLI `python -m bpf.content [--dry-run] [--coverage-report] [--allow-low-coverage] [--convert-ksh RAW]`)
See docs/DATA.md.

## `bpf.api`
**`Store.has_data` rule (repo):** if no store has a `has_data_date` (no availability or per-store run yet), every store is `has_data=True`. Otherwise `has_data = has_data_date is not None and data_date - has_data_date <= 8 days`. The ingest sets `has_data_date` to the data date for every store that appears in that day's `store_price_day` rows or in a fresh `availableInShops` list.

`create_app(settings: Settings | None = None, *, catalogue_provider: CatalogueProvider | None = None) -> FastAPI`. `CatalogueProvider` loads a `Catalogue` from the `api.*` views as `bpf_api`, caches it per `data_date` (it re-checks `api.latest` at most once every 60 s) and is replaceable in tests. Run with `uvicorn bpf.api.app:app` (a module-level `app = create_app()` built lazily) or `python -m bpf.api` (binds 127.0.0.1:8000 by default).
