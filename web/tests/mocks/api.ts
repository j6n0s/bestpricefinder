/**
 * SYNTHETIC /api responses for development (`npm run dev:mock`) and tests (Playwright, unit tests).
 *
 * Every value here is invented test data: store ids, addresses, products and prices are NOT real GVH or KSH
 * data and must never be shown as such (see README.md next to this file). Only the chain names and slugs
 * match the real chain list, because the app's logic depends on them.
 *
 * The shapes are typed against src/lib/api/types.ts, so a contract change breaks this file at compile time.
 */
import type {
	ChainOut,
	ErrorCode,
	ErrorResponse,
	HealthResponse,
	HistoryResponse,
	IngredientOut,
	IngredientsResponse,
	ListResponse,
	MetaResponse,
	PlanCheckResponse,
	PlanResponse,
	QuoteLineOut,
	QuoteResponse,
	RecipeDetail,
	RecipeSummary,
	RecipesResponse,
	Slot,
	StoreOut,
	StoresResponse,
	StoreQuoteOut
} from '../../src/lib/api/types';

export const MOCK_DATA_DATE = '2026-10-13';
export const MOCK_DISCLAIMER_HU = 'Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal.';

const CHAIN_NAMES: readonly [string, string, boolean][] = [
	['aldi', 'Aldi', true],
	['auchan', 'Auchan', true],
	['lidl', 'Lidl', true],
	['penny', 'Penny', true],
	['spar', 'Spar', true],
	['tesco', 'Tesco', true],
	['dm', 'dm', false],
	['rossmann', 'Rossmann', false],
	['muller', 'Müller', false]
];

export const MOCK_CHAINS: ChainOut[] = CHAIN_NAMES.map(([slug, name, isGrocery]) => ({
	id: `synthetic-chain-${slug}`,
	slug,
	name,
	is_grocery: isGrocery
}));

export const MOCK_META: MetaResponse = {
	data_date: MOCK_DATA_DATE,
	ingested_at: '2026-10-13T02:31:00Z',
	stale: false,
	ksh_period: '2026-09-01',
	chains: MOCK_CHAINS,
	attribution: {
		gvh: {
			text_hu: 'Forrás: GVH Árfigyelő (arfigyelo.gvh.hu)',
			text_en: 'Source: GVH Árfigyelő (arfigyelo.gvh.hu)',
			url: 'https://arfigyelo.gvh.hu',
			license: null
		},
		ksh: {
			text_hu: 'Forrás: KSH',
			text_en: 'Source: KSH',
			url: 'https://www.ksh.hu/stadat_files/ara/hu/ara0044.html',
			license: 'CC BY 4.0'
		},
		nutrition: null
	},
	disclaimer_hu: MOCK_DISCLAIMER_HU,
	disclaimer_en: 'Unofficial app, not affiliated with the Hungarian Competition Authority (GVH).'
};

export const MOCK_HEALTH: HealthResponse = { status: 'ok', db: true, data_date: MOCK_DATA_DATE };

function store(
	id: string,
	chain: string,
	lat: number | null,
	lon: number | null,
	options: Partial<Pick<StoreOut, 'has_data' | 'format' | 'postal_code' | 'is_budapest'>> = {}
): StoreOut {
	return {
		id,
		chain,
		postal_code: options.postal_code ?? '1051',
		city: 'Budapest',
		address: `Minta utca ${id.length}.`,
		lat,
		lon,
		format: options.format ?? null,
		is_budapest: options.is_budapest ?? true,
		has_data: options.has_data ?? true
	};
}

/** Around a synthetic origin near the city centre (47.4995, 19.0518). */
export const MOCK_STORES: StoreOut[] = [
	store('synthetic-lidl-1', 'lidl', 47.5, 19.052),
	store('synthetic-lidl-2', 'lidl', 47.505, 19.06),
	store('synthetic-aldi-1', 'aldi', 47.495, 19.045),
	store('synthetic-spar-1', 'spar', 47.4998, 19.0525),
	store('synthetic-spar-2', 'spar', 47.502, 19.049, { has_data: false }),
	store('synthetic-tesco-1', 'tesco', 47.497, 19.058, { format: 'express' }),
	store('synthetic-penny-1', 'penny', 47.51, 19.07),
	store('synthetic-dm-1', 'dm', 47.4996, 19.0519),
	store('synthetic-auchan-1', 'auchan', 47.43, 19.18, { postal_code: '1239' }),
	store('synthetic-nocoords-1', 'aldi', null, null),
	store('synthetic-penny-far', 'penny', 46.25, 20.15, { postal_code: '6720', is_budapest: false })
];

export const MOCK_STORES_RESPONSE: StoresResponse = { data_date: MOCK_DATA_DATE, stores: MOCK_STORES };

export const MOCK_INGREDIENTS: IngredientOut[] = [
	{
		id: 'csirkemellfile',
		name_hu: 'csirkemellfilé',
		list_group: 'hus_hal',
		unit: 'kg',
		piece_weight_kg: null,
		pantry: false,
		priced_by: 'gvh',
		tags: ['poultry']
	},
	{
		id: 'voroshagyma',
		name_hu: 'vöröshagyma',
		list_group: 'zoldseg_gyumolcs',
		unit: 'kg',
		piece_weight_kg: 0.1,
		pantry: false,
		priced_by: 'gvh',
		tags: ['vegetable']
	},
	{
		id: 'voros_lencse',
		name_hu: 'vörös lencse',
		list_group: 'szaraz_tartos',
		unit: 'kg',
		piece_weight_kg: null,
		pantry: false,
		priced_by: 'gvh',
		tags: ['legume']
	},
	{
		id: 'pirospaprika',
		name_hu: 'pirospaprika',
		list_group: 'fuszer_olaj',
		unit: 'kg',
		piece_weight_kg: null,
		pantry: true,
		priced_by: 'none',
		tags: ['spice']
	},
	{
		id: 'gomba',
		name_hu: 'csiperkegomba',
		list_group: 'zoldseg_gyumolcs',
		unit: 'kg',
		piece_weight_kg: null,
		pantry: false,
		priced_by: 'ksh',
		tags: ['vegetable']
	}
];

const summaryA: RecipeSummary = {
	id: 'minta-lencsefozelek',
	title: 'Minta lencsefőzelék (szintetikus)',
	summary: 'Szintetikus tesztrecept.',
	slots: ['ebed', 'vacsora'],
	servings: 4,
	minutes: 45,
	tags: ['fozelek', 'huvelyes', 'husmentes'],
	tested: false,
	cost_per_serving_from: 312.5,
	cheapest_chain: 'lidl',
	priced_share: 0.94
};

const summaryB: RecipeSummary = {
	id: 'minta-csirke',
	title: 'Minta csirkés tál (szintetikus)',
	summary: null,
	slots: ['ebed'],
	servings: 2,
	minutes: 25,
	tags: ['foetel', 'baromfi', 'gyors'],
	tested: true,
	cost_per_serving_from: null,
	cheapest_chain: null,
	priced_share: 0
};

export const MOCK_RECIPES: RecipeSummary[] = [summaryA, summaryB];

export const MOCK_RECIPE_DETAILS: Record<string, RecipeDetail> = {
	[summaryA.id]: {
		...summaryA,
		data_date: MOCK_DATA_DATE,
		steps: ['Szintetikus első lépés, csak teszteléshez.', 'Szintetikus második lépés, csak teszteléshez.'],
		lines: [
			{
				line_no: 1,
				ingredient_id: 'voros_lencse',
				ingredient_name: 'vörös lencse',
				qty: 0.4,
				unit: 'kg',
				display: '40 dkg',
				optional: false,
				pantry: false
			},
			{
				line_no: 2,
				ingredient_id: 'voroshagyma',
				ingredient_name: 'vöröshagyma',
				qty: 0.1,
				unit: 'kg',
				display: '1 fej',
				optional: false,
				pantry: false
			},
			{
				line_no: 3,
				ingredient_id: 'pirospaprika',
				ingredient_name: 'pirospaprika',
				qty: 0.005,
				unit: 'kg',
				display: '1 tk',
				optional: false,
				pantry: true
			}
		],
		chain_costs: [
			{ chain: 'aldi', cost_per_serving: 330, priced_share: 0.94, missing: [] },
			{ chain: 'lidl', cost_per_serving: 312.5, priced_share: 0.94, missing: [] },
			{ chain: 'spar', cost_per_serving: null, priced_share: 0, missing: ['voros_lencse', 'voroshagyma'] }
		],
		nutrition: null
	},
	[summaryB.id]: {
		...summaryB,
		data_date: MOCK_DATA_DATE,
		steps: ['Szintetikus lépés, csak teszteléshez.'],
		lines: [
			{
				line_no: 1,
				ingredient_id: 'csirkemellfile',
				ingredient_name: 'csirkemellfilé',
				qty: 0.3,
				unit: 'kg',
				display: '30 dkg',
				optional: false,
				pantry: false
			}
		],
		chain_costs: [],
		nutrition: null
	}
};

/** Fixed synthetic unit prices (HUF per canonical unit) used to build quote answers. */
const SYNTHETIC_UNIT_PRICE: Record<string, number> = { csirkemellfile: 2000, voroshagyma: 400, voros_lencse: 1200 };

export interface MockResult {
	status: number;
	body: unknown;
}

const ok = (body: unknown): MockResult => ({ status: 200, body });
const fail = (status: number, error: ErrorCode, fields: string[] = []): MockResult => ({
	status,
	body: { error, fields } satisfies ErrorResponse
});

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function onlyKeys(value: Record<string, unknown>, allowed: readonly string[]): string[] {
	return Object.keys(value).filter((key) => !allowed.includes(key));
}

function quoteLine(ingredientId: string, qty: number, storeIndex: number): QuoteLineOut {
	const unitPrice = SYNTHETIC_UNIT_PRICE[ingredientId];
	if (unitPrice === undefined) {
		return {
			ingredient_id: ingredientId,
			qty,
			unit: 'kg',
			status: ingredientId === 'gomba' ? 'ksh_estimate' : 'unpriced',
			picks: [],
			checkout_cost: null,
			used_cost: null,
			leftover_qty: null,
			ksh_estimate: ingredientId === 'gomba' ? Math.round(qty * 1800 * 100) / 100 : null,
			alternatives: []
		};
	}
	const price = unitPrice + storeIndex * 50;
	const cost = Math.round(qty * price * 100) / 100;
	return {
		ingredient_id: ingredientId,
		qty,
		unit: 'kg',
		status: 'priced',
		picks: [
			{
				option: {
					product_id: `synthetic-product-${ingredientId}`,
					product_name: `Szintetikus termék (${ingredientId})`,
					pack_size: null,
					pack_price: price,
					unit_price: price,
					price_type: 'NORMAL',
					price_scope: 'chain',
					availability: 'assumed'
				},
				count: 1,
				qty,
				cost
			}
		],
		checkout_cost: cost,
		used_cost: cost,
		leftover_qty: 0,
		ksh_estimate: null,
		alternatives: []
	};
}

function mockQuote(body: Record<string, unknown>): MockResult {
	const extra = onlyKeys(body, ['lines', 'store_ids', 'include_loyalty']);
	if (extra.length > 0) return fail(422, 'invalid_request', extra);
	const { lines, store_ids: storeIds } = body;
	if (!Array.isArray(lines) || lines.length === 0 || !Array.isArray(storeIds) || storeIds.length === 0) {
		return fail(422, 'invalid_request', ['lines', 'store_ids']);
	}
	const known = new Map(MOCK_STORES.map((s) => [s.id, s]));
	const stores: StoreQuoteOut[] = [];
	for (const [index, id] of storeIds.entries()) {
		const found = typeof id === 'string' ? known.get(id) : undefined;
		if (!found) return fail(422, 'invalid_request', [`store_ids.${index}`]);
		const quoteLines = lines.map((line) => {
			const rec = isRecord(line) ? line : {};
			return quoteLine(String(rec.ingredient_id), Number(rec.qty), index);
		});
		const total = quoteLines.reduce((sum, line) => sum + (line.checkout_cost ?? 0), 0);
		stores.push({
			store_id: found.id,
			chain: found.chain,
			checkout_total: Math.round(total * 100) / 100,
			used_total: Math.round(total * 100) / 100,
			missing: [],
			assumed_count: quoteLines.filter((line) => line.status === 'priced').length,
			ksh_estimate_total: quoteLines.reduce((sum, line) => sum + (line.ksh_estimate ?? 0), 0),
			lines: quoteLines
		});
	}
	const ranking = [...stores]
		.sort((a, b) => a.checkout_total - b.checkout_total || (a.store_id < b.store_id ? -1 : 1))
		.map((s, i) => ({
			store_id: s.store_id,
			rank: i + 1,
			checkout_total: s.checkout_total,
			penalized_total: s.checkout_total,
			missing_count: 0
		}));
	const response: QuoteResponse = {
		data_date: MOCK_DATA_DATE,
		stores,
		ranking,
		split: null,
		scope_note_hu: `a kiválasztott boltok közül, a ${MOCK_DATA_DATE}-i GVH-adatok alapján`,
		scope_note_en: `among the selected stores, based on GVH data of ${MOCK_DATA_DATE}`,
		attribution: MOCK_META.attribution
	};
	return ok(response);
}

function mockPlan(body: Record<string, unknown>): MockResult {
	const days = typeof body.days === 'number' && Number.isInteger(body.days) ? body.days : 7;
	const slots: readonly Slot[] = body.slots === 5 ? ['reggeli', 'tizorai', 'ebed', 'uzsonna', 'vacsora'] : ['reggeli', 'ebed', 'vacsora'];
	if (days < 1 || days > 31) return fail(422, 'invalid_request', ['days']);
	const response: PlanResponse = {
		days: Array.from({ length: days }, (_, index) => ({
			index,
			meals: Object.fromEntries(
				slots.map((slot) => [slot, slot === 'ebed' || slot === 'vacsora' ? summaryA.id : null])
			) as Partial<Record<Slot, string | null>>
		})),
		checks: [{ week: 0, rule: 'legume', ok: true, value: '7 hüvelyes', limit: '≥ 1' }],
		warnings: ['slot_pool_empty:reggeli']
	};
	return ok(response);
}

function mockList(body: Record<string, unknown>): MockResult {
	if (!Array.isArray(body.items) || body.items.length === 0) return fail(422, 'invalid_request', ['items']);
	const response: ListResponse = {
		lines: [
			{
				ingredient_id: 'voroshagyma',
				name_hu: 'vöröshagyma',
				qty: 0.1,
				unit: 'kg',
				list_group: 'zoldseg_gyumolcs',
				pantry: false,
				recipe_ids: [summaryA.id]
			},
			{
				ingredient_id: 'voros_lencse',
				name_hu: 'vörös lencse',
				qty: 0.4,
				unit: 'kg',
				list_group: 'szaraz_tartos',
				pantry: false,
				recipe_ids: [summaryA.id]
			}
		]
	};
	return ok(response);
}

function parseBody(text: string): Record<string, unknown> | null {
	try {
		const value: unknown = JSON.parse(text);
		return isRecord(value) ? value : null;
	} catch {
		return null;
	}
}

/**
 * Answers one /api request from the synthetic data. `url` may be a path ("/api/meta?x=1") or a full URL.
 * Unknown paths give 404, other methods 405, malformed bodies 422, like the real API.
 */
export function handleMockApi(method: string, url: string, bodyText = ''): MockResult {
	const parsed = new URL(url, 'http://mock.invalid');
	const path = parsed.pathname;
	const m = method.toUpperCase();

	const getRoutes: Record<string, () => MockResult> = {
		'/api/health': () => ok(MOCK_HEALTH),
		'/api/meta': () => ok(MOCK_META),
		'/api/stores': () => ok(MOCK_STORES_RESPONSE),
		'/api/ingredients': () => ok({ ingredients: MOCK_INGREDIENTS } satisfies IngredientsResponse),
		'/api/recipes': () => {
			const slot = parsed.searchParams.get('slot');
			const tag = parsed.searchParams.get('tag');
			const q = parsed.searchParams.get('q')?.toLowerCase() ?? null;
			const recipes = MOCK_RECIPES.filter(
				(r) =>
					(slot === null || (r.slots as string[]).includes(slot)) &&
					(tag === null || r.tags.includes(tag)) &&
					(q === null || r.title.toLowerCase().includes(q))
			);
			return ok({ data_date: MOCK_DATA_DATE, recipes } satisfies RecipesResponse);
		}
	};
	const postRoutes: Record<string, (body: Record<string, unknown>) => MockResult> = {
		'/api/list': mockList,
		'/api/quote': mockQuote,
		'/api/plan/suggest': mockPlan,
		'/api/plan/check': () => ok({ checks: [] } satisfies PlanCheckResponse)
	};

	const recipeMatch = /^\/api\/recipes\/([^/]+)$/.exec(path);
	const historyMatch = /^\/api\/ingredients\/([^/]+)\/history$/.exec(path);
	const isGet = path in getRoutes || recipeMatch !== null || historyMatch !== null;
	const isPost = path in postRoutes;

	if (!isGet && !isPost) return fail(404, 'not_found');
	if (isGet && m !== 'GET') return fail(405, 'method_not_allowed');
	if (isPost && m !== 'POST') return fail(405, 'method_not_allowed');

	if (isPost) {
		const body = parseBody(bodyText);
		if (body === null) return fail(422, 'invalid_request', ['body']);
		const route = postRoutes[path];
		return route ? route(body) : fail(404, 'not_found');
	}
	if (recipeMatch) {
		const detail = MOCK_RECIPE_DETAILS[decodeURIComponent(recipeMatch[1] ?? '')];
		return detail ? ok(detail) : fail(404, 'not_found');
	}
	if (historyMatch) {
		const id = decodeURIComponent(historyMatch[1] ?? '');
		const ingredient = MOCK_INGREDIENTS.find((i) => i.id === id);
		if (!ingredient) return fail(404, 'not_found');
		const history: HistoryResponse = {
			ingredient_id: id,
			unit: ingredient.unit,
			days: 30,
			series: [
				{
					chain: 'lidl',
					points: [
						{ date: '2026-10-12', unit_price: 1190 },
						{ date: MOCK_DATA_DATE, unit_price: 1200 }
					]
				}
			]
		};
		return ok(history);
	}
	const route = getRoutes[path];
	return route ? route() : fail(404, 'not_found');
}
