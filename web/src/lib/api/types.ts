/**
 * TypeScript mirror of the /api contract in server/bpf/api/schemas.py (prose: docs/API.md).
 *
 * HAND-WRITTEN STOPGAP: this file will be replaced by types generated from docs/openapi.json
 * (`python -m bpf.api.openapi`, then an OpenAPI-to-TypeScript step writing src/lib/api/schema.d.ts).
 * Until then every model in schemas.py is mirrored here one to one, in the same order and with the same
 * field names. If this file and schemas.py disagree, schemas.py wins: fix this file.
 *
 * Mapping rules:
 * - `datetime.date` is an ISO string "YYYY-MM-DD"; `datetime.datetime` is an ISO 8601 string.
 * - `Decimal` request fields are JSON numbers; responses carry money in HUF (at most 2 decimals) and
 *   quantities in the ingredient's canonical unit (at most 3 decimals) as numbers.
 * - Request fields with a server-side default are optional here. Response fields that have a default in
 *   pydantic are marked optional too, so the client copes with a server that omits them.
 */

// ───────────────────────────── shared types ─────────────────────────────

/** ^[a-z0-9_]{2,40}$ */
export type IngredientId = string;
/** ^[a-z0-9-]{2,60}$ */
export type RecipeId = string;
/** ^[A-Za-z0-9_-]{1,40}$ */
export type StoreId = string;
/** ^[a-z0-9-]{1,30}$, e.g. "lidl" */
export type ChainSlug = string;
/** "YYYY-MM-DD" */
export type IsoDate = string;
/** ISO 8601 date-time */
export type IsoDateTime = string;

export const SLOTS = ['reggeli', 'tizorai', 'ebed', 'uzsonna', 'vacsora'] as const;
export type Slot = (typeof SLOTS)[number];
/** The 3-slot day and the 5-slot day, in display order (server/bpf/pricing/model.py SLOTS_3, SLOTS_5). */
export const SLOTS_3: readonly Slot[] = ['reggeli', 'ebed', 'vacsora'];
export const SLOTS_5: readonly Slot[] = SLOTS;

export const UNITS = ['kg', 'l', 'db'] as const;
export type Unit = (typeof UNITS)[number];

/**
 * Reported for transparency only. DISCOUNTED is NOT a weekly-deal flag (Aldi never sets it, and it also marks
 * long-running reductions): the UI may say "kedvezményes ár (GVH-jelölés)" in plain text, never show an
 * "akció"/deal badge based on it (docs/API.md "Price types and deals").
 */
export type PriceType = 'NORMAL' | 'DISCOUNTED' | 'LOYALTY';
export type PriceScope = 'store' | 'chain';
export type AvailabilityKind = 'confirmed' | 'assumed';
export type LineStatus = 'priced' | 'pantry' | 'unavailable' | 'ksh_estimate' | 'unpriced';

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
] as const;
export type RecipeTag = (typeof RECIPE_TAGS)[number];

export type RuleName = 'fish' | 'legume' | 'meat_free_day' | 'red_meat' | 'potato' | 'sweets' | 'variety' | 'budget';

/** Id patterns from schemas.py, for client-side checks before a request. */
export const ID_PATTERNS = {
	ingredient: /^[a-z0-9_]{2,40}$/,
	recipe: /^[a-z0-9-]{2,60}$/,
	store: /^[A-Za-z0-9_-]{1,40}$/,
	chain: /^[a-z0-9-]{1,30}$/
} as const;

/** Request bounds from schemas.py. */
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

export const ERROR_CODES = [
	'invalid_request',
	'not_found',
	'payload_too_large',
	'unsupported_media_type',
	'rate_limited',
	'no_data',
	'internal',
	'method_not_allowed'
] as const;
export type ErrorCode = (typeof ERROR_CODES)[number];

/** Generic error body. Never echoes input values or internals. */
export interface ErrorResponse {
	error: ErrorCode;
	/** dotted paths of invalid fields (422 only) */
	fields?: string[];
}

// ───────────────────────────── /api/health, /api/meta ─────────────────────────────

export interface HealthResponse {
	status: 'ok' | 'degraded' | 'down';
	db: boolean;
	data_date: IsoDate | null;
}

export interface ChainOut {
	id: string;
	slug: ChainSlug;
	name: string;
	is_grocery: boolean;
}

export interface AttributionOut {
	text_hu: string;
	text_en: string;
	url: string;
	license?: string | null;
}

export interface AttributionSet {
	gvh: AttributionOut;
	ksh: AttributionOut;
	nutrition?: AttributionOut | null;
}

export interface MetaResponse {
	data_date: IsoDate | null;
	ingested_at: IsoDateTime | null;
	/** true when data_date is older than yesterday (Europe/Budapest) */
	stale: boolean;
	ksh_period: IsoDate | null;
	chains: ChainOut[];
	attribution: AttributionSet;
	disclaimer_hu: string;
	disclaimer_en: string;
}

// ───────────────────────────── /api/stores ─────────────────────────────

export interface StoreOut {
	id: StoreId;
	chain: ChainSlug;
	postal_code: string | null;
	city: string | null;
	address: string | null;
	lat: number | null;
	lon: number | null;
	format: 'hyper' | 'express' | 'other' | null;
	is_budapest: boolean;
	/** false when the store had no product on the latest data date: hide it or label it "nincs áradat" */
	has_data: boolean;
}

export interface StoresResponse {
	data_date: IsoDate | null;
	stores: StoreOut[];
}

// ───────────────────────────── /api/ingredients ─────────────────────────────

export interface IngredientOut {
	id: IngredientId;
	name_hu: string;
	list_group: string;
	unit: Unit;
	piece_weight_kg: number | null;
	pantry: boolean;
	priced_by: 'gvh' | 'ksh' | 'none';
	tags: string[];
}

export interface IngredientsResponse {
	ingredients: IngredientOut[];
}

// ───────────────────────────── /api/recipes ─────────────────────────────

export interface RecipeSummary {
	id: RecipeId;
	title: string;
	summary: string | null;
	slots: Slot[];
	servings: number;
	minutes: number | null;
	tags: string[];
	tested: boolean;
	/** cheapest chain-typical used cost per serving across grocery chains (HUF); null if unpriced */
	cost_per_serving_from: number | null;
	/**
	 * Every grocery chain tied at cost_per_serving_from (equal in whole forints). A tie group, never an order:
	 * the UI must not single out one chain of a tie (BUILD-BRIEF §4.1 trap 13).
	 */
	cheapest_chains: ChainSlug[];
	/** 0..1, share of cost priced at the cheapest chain(s) (the lowest share of a tie) */
	priced_share: number;
}

export interface RecipesResponse {
	data_date: IsoDate | null;
	recipes: RecipeSummary[];
}

export interface RecipeLineOut {
	line_no: number;
	ingredient_id: IngredientId;
	ingredient_name: string;
	qty: number;
	unit: Unit;
	display: string;
	optional: boolean;
	pantry: boolean;
}

export interface ChainCostOut {
	chain: ChainSlug;
	cost_per_serving: number | null;
	/** 0..1 */
	priced_share: number;
	missing: IngredientId[];
}

export interface NutritionOut {
	kcal: number;
	protein_g: number;
	carb_g: number;
	sugar_g: number;
	fat_g: number;
	satfat_g: number;
	fiber_g: number;
	salt_g: number;
	/** 0..1 */
	coverage: number;
}

export interface RecipeDetail extends RecipeSummary {
	data_date: IsoDate | null;
	steps: string[];
	lines: RecipeLineOut[];
	chain_costs: ChainCostOut[];
	/** per serving; null until composition data is imported */
	nutrition: NutritionOut | null;
}

/** Query of GET /api/recipes. `q`: 2–40 characters, accent-insensitive title search. */
export interface RecipesQuery {
	slot?: Slot;
	tag?: RecipeTag;
	q?: string;
}

// ───────────────────────────── /api/list ─────────────────────────────

export interface ListItemIn {
	recipe_id: RecipeId;
	/** servings wanted (e.g. people × meals), 0 < servings <= 100 */
	servings: number;
}

export interface QtyLineIn {
	ingredient_id: IngredientId;
	/** in the ingredient's canonical unit, 0 < qty <= 1000 */
	qty: number;
}

export interface ListRequest {
	/** 1–200 */
	items: ListItemIn[];
	/** ≤ 200 */
	on_hand?: QtyLineIn[];
	include_optional?: boolean;
}

export interface ListLineOut {
	ingredient_id: IngredientId;
	name_hu: string;
	qty: number;
	unit: Unit;
	list_group: string;
	pantry: boolean;
	recipe_ids: RecipeId[];
}

export interface ListResponse {
	lines: ListLineOut[];
}

// ───────────────────────────── /api/quote ─────────────────────────────

export interface QuoteRequest {
	/** 1–200, unique ingredient ids */
	lines: QtyLineIn[];
	/** 1–25, unique; never coordinates */
	store_ids: StoreId[];
	include_loyalty?: boolean;
}

export interface PackOptionOut {
	product_id: string;
	product_name: string;
	/** canonical units per pack; null = sold by weight */
	pack_size: number | null;
	/** HUF per pack; for sold-by-weight items HUF per canonical unit */
	pack_price: number;
	/** HUF per canonical unit */
	unit_price: number;
	price_type: PriceType;
	price_scope: PriceScope;
	availability: AvailabilityKind;
}

export interface PickOut {
	option: PackOptionOut;
	count: number;
	qty: number;
	cost: number;
}

export interface QuoteLineOut {
	ingredient_id: IngredientId;
	qty: number;
	unit: Unit;
	status: LineStatus;
	picks: PickOut[];
	checkout_cost: number | null;
	used_cost: number | null;
	leftover_qty: number | null;
	ksh_estimate: number | null;
	alternatives: PackOptionOut[];
}

export interface StoreQuoteOut {
	store_id: StoreId;
	chain: ChainSlug;
	checkout_total: number;
	used_total: number;
	missing: IngredientId[];
	assumed_count: number;
	ksh_estimate_total: number;
	lines: QuoteLineOut[];
}

export interface RankOut {
	store_id: StoreId;
	/**
	 * Competition rank: tied stores share it (1, 1, 3). The order inside a tie group means nothing; the client
	 * orders a tie by distance and never by chain or store name.
	 */
	rank: number;
	checkout_total: number;
	penalized_total: number;
	missing_count: number;
}

export interface SplitOut {
	/** exactly 2 */
	store_ids: [StoreId, StoreId];
	total: number;
	saving: number;
	/** ingredient id -> store id */
	assignment: Record<IngredientId, StoreId>;
}

export interface QuoteResponse {
	data_date: IsoDate;
	stores: StoreQuoteOut[];
	ranking: RankOut[];
	split: SplitOut | null;
	/** e.g. "a kiválasztott boltok közül, a 2026-10-13-i GVH-adatok alapján" */
	scope_note_hu: string;
	scope_note_en: string;
	attribution: AttributionSet;
}

// ───────────────────────────── /api/plan ─────────────────────────────

export interface PlanSuggestRequest {
	/** 1–31, default 7 */
	days?: number;
	/** default 3 */
	slots?: 3 | 5;
	/** 1–12, default 2 */
	people?: number;
	/** 0–2^31-1, default 0 */
	seed?: number;
	/** ≤ 20 */
	exclude_tags?: RecipeTag[];
	/** ≤ 50 */
	exclude_ingredients?: IngredientId[];
	/** 0–3000, default 600 */
	red_meat_g_per_person_week?: number;
	/** 0–14, default 5 */
	no_repeat_days?: number;
	/** 0–1 000 000 HUF, default null */
	weekly_budget?: number | null;
}

export interface PlanDayIO {
	/** 0–30 */
	index: number;
	meals: Partial<Record<Slot, RecipeId | null>>;
}

export interface PlanCheckRequest {
	/** 1–31 */
	days: PlanDayIO[];
	people?: number;
	red_meat_g_per_person_week?: number;
	no_repeat_days?: number;
	weekly_budget?: number | null;
}

export interface RuleCheckOut {
	week: number;
	rule: RuleName;
	ok: boolean;
	value: string;
	limit: string;
}

export interface PlanResponse {
	days: PlanDayIO[];
	checks: RuleCheckOut[];
	/** machine codes; the client maps them to HU/EN text (docs/API.md) */
	warnings: string[];
}

export interface PlanCheckResponse {
	checks: RuleCheckOut[];
}

// ───────────────────────────── /api/ingredients/{id}/history ─────────────────────────────

export interface HistoryPoint {
	date: IsoDate;
	unit_price: number;
}

export interface HistorySeries {
	chain: ChainSlug;
	points: HistoryPoint[];
}

export interface HistoryResponse {
	ingredient_id: IngredientId;
	unit: Unit;
	days: number;
	series: HistorySeries[];
}

/** Query of GET /api/ingredients/{id}/history. `days`: 7–365, default 30. */
export interface HistoryQuery {
	chain?: ChainSlug;
	days?: number;
}
