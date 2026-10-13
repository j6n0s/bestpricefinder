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
    # Variable weight (product.unit_title folded == "kg", or no packaging on a kg/l product): size None, price per
    # canonical unit. A db product without packaging is a pack of 1 piece (never bought in fractional pieces).
    # Packs whose unit price deviates >5 % from amount/packaging are still usable; unit_price is recomputed
    # from amount / canonical pack size (never trust GVH unitAmount blindly).

optimise_packs(qty: Decimal, options: Sequence[PackOption]) -> tuple[LinePick, ...] | None
    # Minimise checkout cost to cover >= qty with whole packs (combinations of different options allowed)
    # or exact weight for variable-weight options. Ties: less leftover, then fewer packs, then product id.
    # None if options is empty. Must be exact (no greedy) and fast: <= 2 ms typical per call. Search (module
    # docstring of bpf/pricing/packs.py): labels = multisets of the non-best packs, taken in increasing covered
    # quantity, dropped when dominated within their residue class modulo the best-unit-price pack's size.
    # Safety cap: one call stops after MAX_SEARCH_STEPS (200,000) steps and returns the best purchase found so
    # far (always covers qty, never worse than the best-unit-price pack alone); real catalogues stay far below
    # it (tests: 14 near-proportional options at 25.6 kg in a few ms, exact against a DP reference).

quote_store(lines: Sequence[tuple[str, Decimal]], store: Store, cat: Catalogue, *, include_loyalty: bool = False) -> StoreQuote
    # lines = (ingredient_id, canonical qty); unknown ids raise KeyError (the API validates first).
    # Status rules: model.LineStatus. used_cost = qty * (checkout_cost / total qty bought), i.e. the required
    # quantity at the average unit price of the chosen picks. alternatives = up to 3 other options (not used
    # in the picks), ordered by their own single-option checkout cost for qty, cheapest first.

rank_stores(quotes: Sequence[StoreQuote]) -> tuple[StoreRank, ...]
    # penalized_total = checkout_total + sum over missing lines of the median checkout_cost of that
    # ingredient across the OTHER quotes that priced it (if no other store has it: no penalty, but
    # missing_count still counts). Sort by whole_forints(penalized_total), then missing_count. Ties share a
    # rank (competition ranking 1, 1, 3) and are never broken by chain or store name (trap 13); store id
    # orders a tie group only for determinism.

suggest_split(quotes: Sequence[StoreQuote], *, threshold: Decimal = Decimal(1500)) -> SplitSuggestion | None
    # Best pair of stores: each line goes to the cheaper of the two (lines missing at both stay out of the
    # assignment and out of `total`). The pair is compared on a penalized basis: total + the median cost of the
    # lines missing at both, over the quotes outside the pair. Returned only if that penalized total <= best
    # single penalized_total - threshold; `saving` = best single penalized_total - pair penalized total.
    # `total` = the amount paid at the two stores. store_ids lists the better-ranked store first.

recipe_chain_costs(recipe: Recipe, cat: Catalogue) -> tuple[ChainRecipeCost, ...]
    # One entry per grocery chain (Chain.is_grocery), sorted by chain slug. Callers that pick "the cheapest"
    # must keep ties (equal whole-forint cost per serving) as a group. Chain-typical:
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

whole_forints(amount: Decimal) -> Decimal
    # The whole-forint amount the user sees: half-up to 0.01 (the API's money precision), then half-up to
    # 1 Ft (the client's Intl rounding of that JSON number). 504.495 -> 505 (not 504), 504.494 -> 504.
    # Every "equal in whole forints" tie rule (rank_stores, cheapest chain of a recipe) uses this key, so a
    # tie group is exactly the amounts that are displayed the same. Independent of the decimal context.
```

## `bpf.planner`
```python
suggest_plan(recipes: Sequence[Recipe], ingredients: Mapping[str, Ingredient], req: PlanRequest) -> Plan
check_plan(days: Sequence[PlanDay], recipes: Mapping[str, Recipe], ingredients: Mapping[str, Ingredient],
           *, people: int, red_meat_g_per_person_week: int = 600,
           weekly_budget: Decimal | None = None,
           recipe_cost_per_serving: Mapping[str, Decimal] | None = None,
           no_repeat_days: int = 5) -> tuple[RuleCheck, ...]
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

Selection is a deterministic, seeded constraint search (a feasibility-first construction that enforces the rules cell by cell, with restarts from derived seeds, then local search). **Variety is the lowest-priority rule:** the search never trades another rule for fewer repeats. Verified on the real library: 800/800 plans (7/14/28/31 days, 3 and 5 slots, 100 seeds) pass every rule.
1. Fill every slot from the recipes eligible for it (exclusions applied).
2. Repair rule violations with local search.
3. Prefer reusing the same perishable ingredients within a week (leftover-aware). Score: minimise the count of distinct perishable ingredients per week.

Rule details (as implemented; keep the API and UI wording consistent with them):
- A repeat means `day2 - day1 < no_repeat_days`: 5 allows day 0 and day 5, 1 forbids only same-day repeats, and 0 turns the rule off. Snacks (tizorai, uzsonna) use `min(2, no_repeat_days)`; so does any pair where one of the two meals is a snack. Two-day (`ket_napos`) recipes are paired greedily from the first day, so a third day in a row counts as a repeat.
- Partial weeks: the red-meat cap and the budget are pro rata (`cap × days // 7`, rounded down). Count rules (fish, legume, meat-free day) report `n/a` (ok) for blocks shorter than 4 days. The sweets cap of 2 is not pro rata.
- Potato runs and repeats are followed across week boundaries and reported in the later week. A meat-free day needs at least one meal.
- Optional recipe lines count towards red meat and potato. Budget: a meal without a cost estimate fails that week's budget; a budget with no cost table gives the warning `recipe_cost_missing` and no budget check.
- Invalid input raises `ValueError`, and unknown recipe or ingredient ids raise `KeyError` (the API validates first).
- `slot_pool_too_small:<slot>` also covers slots that could avoid repeats only with more than 2 sweet meals in a week, or with potato on two days in a row; the plan then repeats in that slot.
- Warning codes: `slot_pool_empty:<slot>`, `slot_pool_too_small:<slot>`, `no_fish_recipe_available`, `no_legume_recipe_available`, `no_meat_free_recipe_available:<slot>`, `no_potato_free_recipe_available:<slot>`, `red_meat_cap_unreachable`, `sweets_cap_unreachable`, `budget_unreachable`, `recipe_cost_missing`.

If the pool cannot satisfy a rule, return the best plan with a failing check and a warning (e.g. `no_fish_recipe_available`); never loop forever. The time budget is 200 ms for 31 days × 5 slots.

## `bpf.gvh` (HTTP client, the only module that talks to GVH)
`GvhClient(settings, *, transport: httpx.BaseTransport | None = None, clock=..., sleep=..., max_requests=None, max_retries=3, backoff_s=..., timeout_s=30)`. It is synchronous and uses `httpx.Client`. Throttle: ≤1 req/s (`gvh_min_interval_s`). Timeouts: 30 s per socket operation, and a wall-clock budget per response (120 s for API calls, 300 s for the XLSX), so a trickling response cannot hold the ingest lock indefinitely. At most 3 retries with backoff on 5xx and connection errors (never on 4xx). The UA comes from settings and must contain a contact address. Methods return validated pydantic models and raise `GvhSchemaError` on unexpected shapes:
- `categories()`, `chain_stores()`, `shops()`;
- `products_by_category(leaf_id, *, shop_ids=None)`, which iterates every page with `limit=48` and returns a `CategoryListing` (`count`, `pages`, `duplicates`, `count_changed`, the validated products);
- `product(product_id)`;
- `product_shop_prices(product_id, store_ids)`, which chunks into ≤200 ids per call, maps `PRODUCT-SHOP-PRICES-NOT-FOUND` to an empty result and returns `dict[store_id, tuple[PriceEntry, ...]]`;
- `daily_xlsx(expected_date)`, returning a `DailyXlsx`, which is cache-busted with a value unique per run (`?v=YYYYMMDD-<run id>`; the plain URL served 6–30 h old copies), checks that the sheet name `Napi feltöltések - YYYY-MM-DD` equals `expected_date` (else raises `StaleXlsxError`), parses decimal-comma text to Decimal and validates the header. The XLSX is untrusted input: parsing refuses to run unless openpyxl uses `defusedxml` (a pinned runtime dependency; entity expansion and external entities are forbidden), and the zip archive is checked first (at most 200 entries and 256 MB unpacked).

## `bpf.ingest` (CLI `python -m bpf.ingest {reference|daily|availability} [--date YYYY-MM-DD] [--all-stores] [--all-food] [--max-requests N] [-v]`; exit 0 ok, 1 failed, 2 usage error, 3 partial)
Runs as `bpf_ingest`. Each run inserts an `ops.ingest_run` row (`running` → `ok` | `partial` | `failed`, with request and byte counts, warnings and stats). The run is idempotent per data date (upsert today's rows; history is append-only by trigger). The order is ARCHITECTURE.md "Data flow". The data date is today in Europe/Budapest. Unit validation: products with a unit outside {kg, l, db} are skipped, with a warning listing them. Per-store calls only for (product, chain) pairs whose XLSX `min < max`, for Budapest stores, in leaves referenced by the ontology (the leaf set is read from `app.ingredient.leaf_ids`; `bpf_ingest` has no SELECT on the `api` views except `api.latest`). Per-store prices are for Budapest stores by default (`--all-stores` for all). Availability refreshes the ontology's leaves by default (`--all-food` for every food product). `daily` runs the reference step first. **Date agreement check (trap 10):** the API switches day at about 00:00 UTC and has no date field, so after fetching both, compare the XLSX minimum with the listing's daily minimum (min of NORMAL and DISCOUNTED, excluding LOYALTY) on every product×chain pair present in both. The same day disagrees on about 0.1 % of pairs, while consecutive days differ on 1.2–2.6 %. If more than 0.6 % disagree, record the warning `api_xlsx_date_mismatch` with the share and finish the run as `partial`. Loyalty prices come only from the listing (`prices[]` LOYALTY) and the per-store endpoint; the XLSX and `productMinAmount` exclude them. A stale XLSX fails the run before anything is written; the scheduler retries later. `BPF_CONTACT_EMAIL` is required (it goes into the User-Agent).

## `bpf.content` (package `server/bpf/content/`; CLI `python -m bpf.content [--dry-run] [--coverage-report] [--allow-low-coverage] [--convert-ksh RAW [--ksh-format stadat|research] [--ksh-fetched YYYY-MM-DD] [--ksh-url URL]]`)
See docs/DATA.md.

## `bpf.api`
**`Store.has_data` rule (repo):** while no `availability` run (status ok or partial) has finished within the last 8 days (read from the view `api.ingest_latest`, migration 0003), every store is `has_data=True` (per-store rows alone exist only for Budapest stores of chains whose prices vary, so they cannot tell which stores have data). Otherwise `has_data = has_data_date is not None and data_date - has_data_date <= 8 days`. The ingest sets `has_data_date` to the data date for every store that appears in that day's `store_price_day` rows or in a fresh `availableInShops` list.

**Cheapest chain of a recipe (repo, for `cost_per_serving_from` / `cheapest_chains`):** the candidates are the grocery chains whose `priced_share` ≥ 0.9 for the recipe; if no chain reaches 0.9, the chains with the highest `priced_share`. `cost_per_serving_from` is the lowest `cost_per_serving` among the candidates (sent at 2 decimals like all money). `cheapest_chains` lists every candidate whose `cost_per_serving` shows as the same whole forints, by `bpf.pricing.whole_forints` (a tie group); chain ranks compare the same key. `priced_share` is the lowest share in that group. A chain that prices only a cheap subset of the lines can therefore never be called the cheapest.

**KSH rows (repo):** `api.ksh_latest.price` is HUF per ONE `unit` (the loader divides the CSV price by `unit_qty`), so the repo builds `KshPrice(unit_qty=Decimal(1), price=row.price)`.

`create_app(settings: Settings | None = None, *, catalogue_provider: CatalogueProvider | None = None) -> FastAPI`. `CatalogueProvider` loads a `Catalogue` from the `api.*` views as `bpf_api`, caches it per `data_date` (it re-checks `api.latest` at most once every 60 s) and is replaceable in tests. Run with `uvicorn bpf.api.app:app` (a module-level `app = create_app()` built lazily) or `python -m bpf.api` (binds 127.0.0.1:8000 by default).
