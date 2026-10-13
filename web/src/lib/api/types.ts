/**
 * The /api contract for the app code: thin aliases over the types GENERATED from docs/openapi.json.
 *
 * Source of truth: server/bpf/api/schemas.py -> `python -m bpf.api.openapi` -> docs/openapi.json ->
 * `npm run gen:api` (openapi-typescript) -> src/lib/api/schema.d.ts (never edit it by hand). `npm run check`
 * runs `gen:api:check`, which fails when schema.d.ts differs from what docs/openapi.json generates now, so a
 * contract change always surfaces as a type error in the code that uses the changed model.
 *
 * Only four kinds of things live in this file:
 * 1. one alias per model, under the names the app has always used (`RecipeSummary`, `QuoteResponse`, …);
 * 2. NARROWINGS where the OpenAPI document is looser than docs/API.md, each one checked at compile time to
 *    stay assignable to the generated type (so a request body we build is always valid for the schema):
 *    - quantities (`QtyLineIn.qty`, `ListItemIn.servings`) are JSON numbers only: the schema still says
 *      `number | string` because the server types them as Decimal, but contract v1.2 rejects strings;
 *    - `PlanDayIO.meals` is keyed by slot (the schema's `propertyNames` enum is lost in TypeScript);
 * 3. runtime constants: the slot, unit, tag and error-code lists are checked at compile time against the
 *    generated unions; the id patterns and request limits (which the generated types cannot carry) are
 *    checked against docs/openapi.json by types.test.ts;
 * 4. compile-time checks that each endpoint in the generated `paths` takes and returns the model the client
 *    (client.ts) uses for it.
 *
 * Mapping rules (from the generator): a `date` is an ISO string "YYYY-MM-DD", a `date-time` an ISO 8601
 * string; request fields with a server default are optional; money is HUF as a number with at most 2
 * decimals, quantities are in the ingredient's canonical unit with at most 3 decimals.
 */
import type { components, paths } from './schema';

type Schemas = components['schemas'];

/** True when A and B are the same type (used only in the compile-time checks below). */
type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
/** True when A can be used where B is expected. */
type Assignable<A, B> = [A] extends [B] ? true : false;
/** Compile-time assertion (no runtime code): `Check<X>` is a type error unless X is `true`. */
type Check<T extends true> = T;
/** The JSON body of an endpoint's 200 response, its JSON request body and its query (from `paths`). */
type Ok<P extends keyof paths, M extends 'get' | 'post'> = paths[P][M] extends {
	responses: { 200: { content: { 'application/json': infer T } } };
}
	? T
	: never;
type Body<P extends keyof paths> = paths[P]['post'] extends { requestBody: { content: { 'application/json': infer T } } }
	? T
	: never;
type Query<P extends keyof paths> = NonNullable<paths[P]['get'] extends { parameters: { query?: infer Q } } ? Q : never>;

// ───────────────────────────── shared types ─────────────────────────────

/** ^[a-z0-9_]{2,40}$ */
export type IngredientId = Schemas['IngredientOut']['id'];
/** ^[a-z0-9-]{2,60}$ */
export type RecipeId = Schemas['RecipeSummary']['id'];
/** ^[A-Za-z0-9_-]{1,40}$ */
export type StoreId = Schemas['StoreOut']['id'];
/** ^[a-z0-9-]{1,30}$, e.g. "lidl" */
export type ChainSlug = Schemas['ChainOut']['slug'];
/** "YYYY-MM-DD" */
export type IsoDate = NonNullable<Schemas['MetaResponse']['data_date']>;
/** ISO 8601 date-time */
export type IsoDateTime = NonNullable<Schemas['MetaResponse']['ingested_at']>;

export type Slot = Schemas['RecipeSummary']['slots'][number];
export const SLOTS = ['reggeli', 'tizorai', 'ebed', 'uzsonna', 'vacsora'] as const satisfies readonly Slot[];
type _SlotsMatchSchema = Check<Same<(typeof SLOTS)[number], Slot>>;
/** The 3-slot day and the 5-slot day, in display order (server/bpf/pricing/model.py SLOTS_3, SLOTS_5). */
export const SLOTS_3: readonly Slot[] = ['reggeli', 'ebed', 'vacsora'];
export const SLOTS_5: readonly Slot[] = SLOTS;

export type Unit = Schemas['IngredientOut']['unit'];
export const UNITS = ['kg', 'l', 'db'] as const satisfies readonly Unit[];
type _UnitsMatchSchema = Check<Same<(typeof UNITS)[number], Unit>>;

/**
 * Reported for transparency only. DISCOUNTED is NOT a weekly-deal flag (Aldi never sets it, and it also marks
 * long-running reductions): the UI may say "kedvezményes ár (GVH-jelölés)" in plain text, never show a deal
 * badge based on it (docs/API.md "Price types and deals").
 */
export type PriceType = Schemas['PackOptionOut']['price_type'];
export type PriceScope = Schemas['PackOptionOut']['price_scope'];
export type AvailabilityKind = Schemas['PackOptionOut']['availability'];
export type LineStatus = Schemas['QuoteLineOut']['status'];

export type RecipeTag = NonNullable<Schemas['PlanSuggestRequest']['exclude_tags']>[number];
export const RECIPE_TAGS = [
	'leves',
	'fozelek',
	'foetel',
	'koret',
	'salata',
	'reggeli_hideg',
	'reggeli_meleg',
	'snack',
	'husmentes',
	'vegetarianus',
	'hal',
	'huvelyes',
	'baromfi',
	'sertes',
	'marha',
	'edes',
	'gyors',
	'ket_napos',
	'olcso',
	'gyerekbarat'
] as const satisfies readonly RecipeTag[];
type _RecipeTagsMatchSchema = Check<Same<(typeof RECIPE_TAGS)[number], RecipeTag>>;

export type RuleName = Schemas['RuleCheckOut']['rule'];

/** Id patterns from schemas.py, for client-side checks before a request. */
export const ID_PATTERNS = {
	ingredient: /^[a-z0-9_]{2,40}$/,
	recipe: /^[a-z0-9-]{2,60}$/,
	store: /^[A-Za-z0-9_-]{1,40}$/,
	chain: /^[a-z0-9-]{1,30}$/
} as const;

/** Request bounds from schemas.py (the generated types carry no bounds; types.test.ts checks them). */
export const LIMITS = {
	listItems: 200,
	onHand: 200,
	quoteLines: 200,
	quoteStores: 25,
	qtyMax: 1000,
	servingsMax: 100,
	planDaysMax: 31,
	peopleMin: 1,
	peopleMax: 12,
	excludeTagsMax: 20,
	excludeIngredientsMax: 50,
	redMeatMaxG: 3000,
	noRepeatDaysMax: 14,
	weeklyBudgetMax: 1_000_000,
	recipeQueryMin: 2,
	recipeQueryMax: 40,
	historyDaysMin: 7,
	historyDaysMax: 365
} as const;

// ───────────────────────────── errors ─────────────────────────────

/** Generic error body. Never echoes input values or internals. */
export type ErrorResponse = Schemas['ErrorResponse'];
export type ErrorCode = ErrorResponse['error'];
export const ERROR_CODES = [
	'invalid_request',
	'not_found',
	'payload_too_large',
	'unsupported_media_type',
	'rate_limited',
	'no_data',
	'internal',
	'method_not_allowed'
] as const satisfies readonly ErrorCode[];
type _ErrorCodesMatchSchema = Check<Same<(typeof ERROR_CODES)[number], ErrorCode>>;

// ───────────────────────────── /api/health, /api/meta ─────────────────────────────

export type HealthResponse = Schemas['HealthResponse'];
export type ChainOut = Schemas['ChainOut'];
export type AttributionOut = Schemas['AttributionOut'];
export type AttributionSet = Schemas['AttributionSet'];
export type MetaResponse = Schemas['MetaResponse'];

// ───────────────────────────── /api/stores ─────────────────────────────

/** `has_data: false`: the store had no product on the latest data date; hide it or label it "nincs áradat". */
export type StoreOut = Schemas['StoreOut'];
export type StoresResponse = Schemas['StoresResponse'];

// ───────────────────────────── /api/ingredients ─────────────────────────────

export type IngredientOut = Schemas['IngredientOut'];
export type IngredientsResponse = Schemas['IngredientsResponse'];

// ───────────────────────────── /api/recipes ─────────────────────────────

/**
 * `cheapest_chains` is a tie group, never an order: every chain tied at `cost_per_serving_from` (whole
 * forints), all of them shown, none singled out (BUILD-BRIEF §4.1 trap 13). Only chains that price ≥ 90 % of
 * the recipe's cost can be in it (docs/ENGINE.md); `priced_share` < 1 must be shown as a caveat.
 */
export type RecipeSummary = Schemas['RecipeSummary'];
export type RecipesResponse = Schemas['RecipesResponse'];
export type RecipeLineOut = Schemas['RecipeLineOut'];
export type ChainCostOut = Schemas['ChainCostOut'];
export type NutritionOut = Schemas['NutritionOut'];
/** The summary fields plus data_date, steps, lines, chain_costs and nutrition (null until imported). */
export type RecipeDetail = Schemas['RecipeDetail'];
type _DetailIsSummary = Check<Assignable<RecipeDetail, RecipeSummary>>;

/** Query of GET /api/recipes. `q`: 2–40 characters, accent-insensitive title search. */
export interface RecipesQuery {
	slot?: Slot;
	tag?: RecipeTag;
	q?: string;
}
type _RecipesQueryFitsSchema = Check<Assignable<RecipesQuery, Query<'/api/recipes'>>>;

// ───────────────────────────── /api/list ─────────────────────────────

/** Narrowed: `servings` (0 < servings ≤ 100) is a JSON number, never a string (contract v1.2). */
export type ListItemIn = Omit<Schemas['ListItemIn'], 'servings'> & { servings: number };
type _ListItemInFitsSchema = Check<Assignable<ListItemIn, Schemas['ListItemIn']>>;

/** Narrowed: `qty` (canonical unit, 0 < qty ≤ 1000) is a JSON number, never a string (contract v1.2). */
export type QtyLineIn = Omit<Schemas['QtyLineIn'], 'qty'> & { qty: number };
type _QtyLineInFitsSchema = Check<Assignable<QtyLineIn, Schemas['QtyLineIn']>>;

export type ListRequest = Omit<Schemas['ListRequest'], 'items' | 'on_hand'> & {
	/** 1–200 */
	items: ListItemIn[];
	/** ≤ 200 */
	on_hand?: QtyLineIn[];
};
type _ListRequestFitsSchema = Check<Assignable<ListRequest, Schemas['ListRequest']>>;

export type ListLineOut = Schemas['ListLineOut'];
export type ListResponse = Schemas['ListResponse'];

// ───────────────────────────── /api/quote ─────────────────────────────

export type QuoteRequest = Omit<Schemas['QuoteRequest'], 'lines'> & {
	/** 1–200, unique ingredient ids */
	lines: QtyLineIn[];
};
type _QuoteRequestFitsSchema = Check<Assignable<QuoteRequest, Schemas['QuoteRequest']>>;

export type PackOptionOut = Schemas['PackOptionOut'];
export type PickOut = Schemas['PickOut'];
export type QuoteLineOut = Schemas['QuoteLineOut'];
export type StoreQuoteOut = Schemas['StoreQuoteOut'];
/**
 * `rank` is a competition rank: tied stores share it (1, 1, 3). The order inside a tie group means nothing;
 * the client orders a tie by distance and never by chain or store name.
 */
export type RankOut = Schemas['RankOut'];
/** `store_ids`: exactly 2; `assignment`: ingredient id -> store id. */
export type SplitOut = Schemas['SplitOut'];
/** `scope_note_hu`, e.g. "a kiválasztott boltok közül, a 2026-10-13-i GVH-adatok alapján". */
export type QuoteResponse = Schemas['QuoteResponse'];

// ───────────────────────────── /api/plan ─────────────────────────────

export type PlanSuggestRequest = Schemas['PlanSuggestRequest'];

/** Narrowed: `meals` is keyed by slot (the schema's propertyNames enum has no TypeScript form). */
export type PlanDayIO = Omit<Schemas['PlanDayIO'], 'meals'> & {
	meals: Partial<Record<Slot, RecipeId | null>>;
};
type _PlanDayFitsSchema = Check<Assignable<PlanDayIO, Schemas['PlanDayIO']>>;

export type PlanCheckRequest = Omit<Schemas['PlanCheckRequest'], 'days'> & {
	/** 1–31 */
	days: PlanDayIO[];
};
type _PlanCheckRequestFitsSchema = Check<Assignable<PlanCheckRequest, Schemas['PlanCheckRequest']>>;

export type RuleCheckOut = Schemas['RuleCheckOut'];

/** `warnings`: machine codes; the client maps them to HU/EN text (docs/API.md). */
export type PlanResponse = Omit<Schemas['PlanResponse'], 'days'> & { days: PlanDayIO[] };
type _PlanResponseFitsSchema = Check<Assignable<PlanResponse, Schemas['PlanResponse']>>;
export type PlanCheckResponse = Schemas['PlanCheckResponse'];

// ───────────────────────────── /api/ingredients/{id}/history ─────────────────────────────

export type HistoryPoint = Schemas['HistoryPoint'];
export type HistorySeries = Schemas['HistorySeries'];
export type HistoryResponse = Schemas['HistoryResponse'];

/** Query of GET /api/ingredients/{id}/history. `days`: 7–365, default 30. */
export interface HistoryQuery {
	chain?: ChainSlug;
	days?: number;
}
type _HistoryQueryFitsSchema = Check<Assignable<HistoryQuery, Query<'/api/ingredients/{id}/history'>>>;

// ───────────────────────────── endpoint -> model checks ─────────────────────────────
// The client (client.ts) promises these models per endpoint; the generated `paths` must agree.

type _HealthModel = Check<Same<Ok<'/api/health', 'get'>, HealthResponse>>;
type _MetaModel = Check<Same<Ok<'/api/meta', 'get'>, MetaResponse>>;
type _StoresModel = Check<Same<Ok<'/api/stores', 'get'>, StoresResponse>>;
type _IngredientsModel = Check<Same<Ok<'/api/ingredients', 'get'>, IngredientsResponse>>;
type _RecipesModel = Check<Same<Ok<'/api/recipes', 'get'>, RecipesResponse>>;
type _RecipeModel = Check<Same<Ok<'/api/recipes/{id}', 'get'>, RecipeDetail>>;
type _HistoryModel = Check<Same<Ok<'/api/ingredients/{id}/history', 'get'>, HistoryResponse>>;
type _ListRequestModel = Check<Assignable<ListRequest, Body<'/api/list'>>>;
type _ListModel = Check<Same<Ok<'/api/list', 'post'>, ListResponse>>;
type _QuoteRequestModel = Check<Assignable<QuoteRequest, Body<'/api/quote'>>>;
type _QuoteModel = Check<Same<Ok<'/api/quote', 'post'>, QuoteResponse>>;
type _SuggestRequestModel = Check<Same<PlanSuggestRequest, Body<'/api/plan/suggest'>>>;
type _SuggestModel = Check<Assignable<PlanResponse, Ok<'/api/plan/suggest', 'post'>>>;
type _PlanCheckRequestModel = Check<Assignable<PlanCheckRequest, Body<'/api/plan/check'>>>;
type _PlanCheckModel = Check<Same<Ok<'/api/plan/check', 'post'>, PlanCheckResponse>>;
