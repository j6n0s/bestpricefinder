/**
 * Shopping list ("Bevásárlólista") and "Hol a legolcsóbb a közelben?" against the production build.
 *
 * Every /api answer here is SYNTHETIC test data (see src/lib/list/README.md and tests/mocks/README.md): store
 * ids "synthetic-…", addresses "Minta utca …", product names "Szintetikus …" and every price are invented.
 * The quote mock behaves like the server's contract (docs/API.md): penalized totals, competition ranks with
 * ties, a 2-store split only when it saves at least 1,500 Ft.
 *
 * Covered at 320×640, 360×740 and 1280×800: list -> location consent -> ranking -> pick a store -> grouped store list,
 * and the district-picker path (with "too few stores, widen the radius"); plus a refused location, the pantry
 * and exclusion settings, and storage refused by the browser. Every test checks: no console errors, no
 * uncaught errors, no CSP violations, no request to another origin, and that no request carries coordinates.
 */
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import type {
	IngredientOut,
	ListLineOut,
	PackOptionOut,
	PriceScope,
	PriceType,
	QuoteLineOut,
	QuoteRequest,
	QuoteResponse,
	RankOut,
	SplitOut,
	StoreOut,
	StoreQuoteOut
} from '../../src/lib/api/types';
import { MOCK_INGREDIENTS, MOCK_META, handleMockApi, type MockResult } from '../mocks/api';
import { expectAccessible } from './a11y';
import { BASE_URL, SCREENSHOT_DIR } from './config';

const DATA_DATE = '2026-10-13';
const DATE_HU = '2026. 10. 13.';
const ATTRIBUTION = `Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), ${DATE_HU}`;
const DISCLAIMER = 'Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal.';
const STORAGE_KEY = 'hetikosar.state';
/** Tuesday 13 October 2026, 10:00 in Budapest. */
const NOW = new Date('2026-10-13T08:00:00Z');
const NBSP = '\u00a0';
const sp = (text: string): string => text.replaceAll(' ', NBSP);

// ───────────────────────────── synthetic stores ─────────────────────────────

/** The device position the browser reports, and where it ends up after rounding to 3 decimals. */
const DEVICE = { latitude: 47.4961234, longitude: 19.0538765 };
const DEVICE_ROUNDED = { lat: 47.496, lon: 19.054 };
/** Centroid of district XI (src/lib/data/districts.json). */
const XI = { lat: 47.46404, lon: 19.03981 };
const KM_PER_DEG_LAT = 111.195;

function at(origin: { lat: number; lon: number }, kmNorth: number, kmEast: number): { lat: number; lon: number } {
	return {
		lat: origin.lat + kmNorth / KM_PER_DEG_LAT,
		lon: origin.lon + kmEast / (KM_PER_DEG_LAT * Math.cos((origin.lat * Math.PI) / 180))
	};
}

let addressNo = 0;
function store(
	id: string,
	chain: string,
	position: { lat: number; lon: number },
	options: { hasData?: boolean; format?: StoreOut['format'] } = {}
): StoreOut {
	addressNo += 1;
	return {
		id,
		chain,
		postal_code: '1051',
		city: 'Budapest',
		address: `Minta utca ${addressNo}.`,
		lat: position.lat,
		lon: position.lon,
		format: options.format ?? null,
		is_budapest: true,
		has_data: options.hasData ?? true
	};
}

const STORES: StoreOut[] = [
	store('synthetic-spar-nodata', 'spar', at(DEVICE_ROUNDED, 0.1, 0), { hasData: false }),
	store('synthetic-dm-1', 'dm', at(DEVICE_ROUNDED, 0, 0.05)),
	store('synthetic-spar-a', 'spar', at(DEVICE_ROUNDED, 0.2, 0)),
	store('synthetic-lidl-a', 'lidl', at(DEVICE_ROUNDED, 0, 0.3)),
	store('synthetic-aldi-a', 'aldi', at(DEVICE_ROUNDED, -0.5, 0)),
	store('synthetic-tesco-a', 'tesco', at(DEVICE_ROUNDED, 0, -0.7), { format: 'express' }),
	store('synthetic-lidl-b', 'lidl', at(DEVICE_ROUNDED, 0.8, 0)),
	store('synthetic-spar-b', 'spar', at(DEVICE_ROUNDED, 0, 0.9)),
	store('synthetic-lidl-c', 'lidl', at(DEVICE_ROUNDED, -1.0, 0)),
	store('synthetic-lidl-d', 'lidl', at(DEVICE_ROUNDED, 0, -1.1)),
	store('synthetic-penny-a', 'penny', at(DEVICE_ROUNDED, 1.2, 0)),
	store('synthetic-auchan-far', 'auchan', at(DEVICE_ROUNDED, 4, 0)),
	store('synthetic-aldi-xi', 'aldi', at(XI, 1.0, 0)),
	store('synthetic-penny-xi', 'penny', at(XI, -1.8, 0))
];
const STORE_BY_ID = new Map(STORES.map((s) => [s.id, s]));
const addressOf = (id: string): string => STORE_BY_ID.get(id)?.address ?? '';

/** Grocery stores with data within 1.5 km of the device, ≤3 per chain, nearest first. */
const DEVICE_CANDIDATES = [
	'synthetic-spar-a',
	'synthetic-lidl-a',
	'synthetic-aldi-a',
	'synthetic-tesco-a',
	'synthetic-lidl-b',
	'synthetic-spar-b',
	'synthetic-lidl-c',
	'synthetic-penny-a'
];

// ───────────────────────────── synthetic list ─────────────────────────────

function listLine(id: string, name: string, qty: number, unit: ListLineOut['unit'], group: string, pantry = false): ListLineOut {
	return { ingredient_id: id, name_hu: name, qty, unit, list_group: group, pantry, recipe_ids: ['minta-lencsefozelek'] };
}

/** In the server's order: list group (docs/DATA.md), then the accent-folded name. */
const LIST_LINES: ListLineOut[] = [
	listLine('gomba', 'csiperkegomba', 0.25, 'kg', 'zoldseg_gyumolcs'),
	listLine('friss_bazsalikom', 'friss bazsalikom', 1, 'db', 'zoldseg_gyumolcs'),
	listLine('sargarepa', 'sárgarépa', 0.25, 'kg', 'zoldseg_gyumolcs'),
	listLine('voroshagyma', 'vöröshagyma', 0.3, 'kg', 'zoldseg_gyumolcs'),
	listLine('kenyer', 'kenyér', 1, 'db', 'pekaru'),
	listLine('natur_joghurt', 'natúr joghurt', 0.5, 'kg', 'tejtermek_tojas'),
	listLine('csirkemellfile', 'csirkemellfilé', 1.2, 'kg', 'hus_hal'),
	listLine('voros_lencse', 'vörös lencse', 0.4, 'kg', 'szaraz_tartos'),
	listLine('napraforgoolaj', 'napraforgóolaj', 0.05, 'l', 'fuszer_olaj', true),
	listLine('pirospaprika', 'pirospaprika', 0.01, 'kg', 'fuszer_olaj', true)
];

const EXTRA_INGREDIENTS: IngredientOut[] = [
	{ id: 'napraforgoolaj', name_hu: 'napraforgóolaj', list_group: 'fuszer_olaj', unit: 'l', piece_weight_kg: null, pantry: true, priced_by: 'gvh', tags: ['fat_oil'] },
	{ id: 'so', name_hu: 'só', list_group: 'fuszer_olaj', unit: 'kg', piece_weight_kg: null, pantry: true, priced_by: 'none', tags: ['condiment'] }
];

// ───────────────────────────── synthetic quote (contract behaviour) ─────────────────────────────

/** Synthetic price level per chain (Lidl and Aldi tie on purpose). */
const LEVEL: Record<string, number> = { lidl: 1, aldi: 1, penny: 1.1, spar: 1.25, tesco: 1.8 };

function option(
	name: string,
	packSize: number | null,
	packPrice: number,
	unitPrice: number,
	extra: { type?: PriceType; scope?: PriceScope; assumed?: boolean } = {}
): PackOptionOut {
	return {
		product_id: `synthetic-${name.toLowerCase().replaceAll(' ', '-')}-${packSize ?? 'kg'}`,
		product_name: `Szintetikus ${name}`,
		pack_size: packSize,
		pack_price: packPrice,
		unit_price: unitPrice,
		price_type: extra.type ?? 'NORMAL',
		price_scope: extra.scope ?? 'chain',
		availability: extra.assumed ? 'assumed' : 'confirmed'
	};
}

const round2 = (value: number): number => Math.round(value * 100) / 100;

function packLine(id: string, qty: number, unit: QuoteLineOut['unit'], pack: PackOptionOut, alternatives: PackOptionOut[] = []): QuoteLineOut {
	const size = pack.pack_size ?? qty;
	const count = pack.pack_size === null ? 1 : Math.ceil(qty / size - 1e-9);
	const bought = pack.pack_size === null ? qty : round2(count * size * 1000) / 1000;
	const cost = pack.pack_size === null ? round2(qty * pack.unit_price) : count * pack.pack_price;
	return {
		ingredient_id: id,
		qty,
		unit,
		status: 'priced',
		picks: [{ option: pack, count, qty: bought, cost }],
		checkout_cost: cost,
		used_cost: round2((qty * cost) / bought),
		leftover_qty: Math.round((bought - qty) * 1000) / 1000,
		ksh_estimate: null,
		alternatives
	};
}

function emptyLine(id: string, qty: number, unit: QuoteLineOut['unit'], status: QuoteLineOut['status'], ksh: number | null = null): QuoteLineOut {
	return { ingredient_id: id, qty, unit, status, picks: [], checkout_cost: null, used_cost: null, leftover_qty: null, ksh_estimate: ksh, alternatives: [] };
}

const unitOf = (id: string): QuoteLineOut['unit'] => LIST_LINES.find((l) => l.ingredient_id === id)?.unit ?? 'kg';

function quoteLine(id: string, qty: number, chain: string): QuoteLineOut {
	const m = LEVEL[chain] ?? 1.3;
	const p = (base: number): number => Math.round(base * m);
	const storeScope: PriceScope = chain === 'spar' || chain === 'tesco' ? 'store' : 'chain';
	switch (id) {
		case 'voroshagyma':
			return packLine(id, qty, 'kg', option('vöröshagyma', 1, p(449), p(449), { scope: storeScope }), [
				option('vöröshagyma kicsi', 0.5, p(299), p(598)),
				option('vöröshagyma lédig', null, p(399), p(399))
			]);
		case 'sargarepa':
			return packLine(id, qty, 'kg', option('sárgarépa', 0.5, p(299), p(598), { assumed: chain === 'tesco' }));
		case 'natur_joghurt':
			return packLine(id, qty, 'kg', option('natúr joghurt', 0.175, p(189), round2(p(189) / 0.175)));
		case 'csirkemellfile': {
			// A synthetic store-level price that makes the Lidl + Tesco split worth it.
			const unitPrice = chain === 'tesco' ? 990 : p(2990);
			const type: PriceType = chain === 'lidl' ? 'DISCOUNTED' : 'NORMAL';
			return packLine(id, qty, 'kg', option('csirkemellfilé', null, unitPrice, unitPrice, { type, scope: chain === 'lidl' ? 'store' : storeScope }));
		}
		case 'kenyer':
			return packLine(id, qty, 'db', option('kenyér', 1, p(599), p(599)));
		case 'voros_lencse':
			return chain === 'spar' ? emptyLine(id, qty, 'kg', 'unavailable') : packLine(id, qty, 'kg', option('vörös lencse', 0.5, p(899), p(1798)));
		case 'napraforgoolaj':
			return packLine(id, qty, 'l', option('napraforgóolaj', 1, p(899), p(899), { assumed: chain === 'tesco' }));
		case 'gomba':
			return emptyLine(id, qty, 'kg', 'ksh_estimate', round2(qty * 2400));
		case 'pirospaprika':
			return emptyLine(id, qty, 'kg', 'pantry');
		default:
			return emptyLine(id, qty, unitOf(id), 'unpriced');
	}
}

function median(values: number[]): number {
	const sorted = [...values].sort((a, b) => a - b);
	const mid = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? (sorted[mid] ?? 0) : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
}

function costOf(quote: StoreQuoteOut, ingredientId: string): number | null {
	const line = quote.lines.find((l) => l.ingredient_id === ingredientId);
	return line?.status === 'priced' ? line.checkout_cost : null;
}

function mockQuote(request: QuoteRequest): QuoteResponse {
	const stores: StoreQuoteOut[] = request.store_ids.map((id) => {
		const info = STORE_BY_ID.get(id);
		if (!info) throw new Error(`unknown store ${id}`);
		const lines = request.lines.map((line) => quoteLine(line.ingredient_id, line.qty, info.chain));
		const priced = lines.filter((l) => l.status === 'priced');
		return {
			store_id: id,
			chain: info.chain,
			checkout_total: round2(priced.reduce((sum, l) => sum + (l.checkout_cost ?? 0), 0)),
			used_total: round2(priced.reduce((sum, l) => sum + (l.used_cost ?? 0), 0)),
			missing: lines.filter((l) => l.status === 'unavailable').map((l) => l.ingredient_id),
			assumed_count: priced.filter((l) => l.picks.some((pick) => pick.option.availability === 'assumed')).length,
			ksh_estimate_total: round2(lines.reduce((sum, l) => sum + (l.ksh_estimate ?? 0), 0)),
			lines
		};
	});
	const penalized = (q: StoreQuoteOut): number =>
		q.checkout_total +
		q.missing.reduce((sum, ingredientId) => {
			const others = stores.filter((o) => o !== q).map((o) => costOf(o, ingredientId)).filter((c): c is number => c !== null);
			return sum + (others.length > 0 ? median(others) : 0);
		}, 0);
	const keyed = stores.map((q) => ({ q, whole: Math.round(penalized(q)), pen: round2(penalized(q)) }));
	// Server order inside a tie: store id (meaningless; the client orders a tie by distance).
	keyed.sort((a, b) => a.whole - b.whole || a.q.missing.length - b.q.missing.length || (a.q.store_id < b.q.store_id ? -1 : 1));
	const ranking: RankOut[] = keyed.map((k) => ({
		store_id: k.q.store_id,
		rank: 1 + keyed.filter((o) => o.whole < k.whole || (o.whole === k.whole && o.q.missing.length < k.q.missing.length)).length,
		checkout_total: k.q.checkout_total,
		penalized_total: k.pen,
		missing_count: k.q.missing.length
	}));
	let split: SplitOut | null = null;
	const a = stores.find((q) => q.store_id === 'synthetic-lidl-a');
	const b = stores.find((q) => q.store_id === 'synthetic-tesco-a');
	if (a && b) {
		const assignment: Record<string, string> = {};
		let total = 0;
		for (const line of request.lines) {
			const ca = costOf(a, line.ingredient_id);
			const cb = costOf(b, line.ingredient_id);
			if (ca === null && cb === null) continue;
			const toB = ca === null || (cb !== null && cb < ca);
			assignment[line.ingredient_id] = toB ? b.store_id : a.store_id;
			total += (toB ? cb : ca) ?? 0;
		}
		const best = keyed[0]?.pen ?? 0;
		if (best - total >= 1500) split = { store_ids: [a.store_id, b.store_id], total: round2(total), saving: round2(best - total), assignment };
	}
	return {
		data_date: DATA_DATE,
		stores,
		ranking,
		split,
		scope_note_hu: `a kiválasztott boltok közül, a ${DATA_DATE}-i GVH-adatok alapján`,
		scope_note_en: `among the selected stores, based on GVH data of ${DATA_DATE}`,
		attribution: MOCK_META.attribution
	};
}

// ───────────────────────────── harness ─────────────────────────────

interface Recorder {
	consoleErrors: string[];
	pageErrors: string[];
	external: string[];
	requests: { method: string; url: string; body: string }[];
	listBodies: unknown[];
	quoteBodies: QuoteRequest[];
	cspViolations: () => Promise<string[]>;
}

declare global {
	interface Window {
		__cspViolations?: string[];
		__geoCalls?: (PositionOptions | null)[];
	}
}

function json(status: number, body: unknown): MockResult {
	return { status, body };
}

interface HarnessOptions {
	/** The /api/list answer (default LIST_LINES). */
	listLines?: ListLineOut[];
	/** Changes the synthetic /api/quote answer (for states the default data does not produce). */
	quote?: (quote: QuoteResponse) => QuoteResponse;
}

async function harness(page: Page, options: HarnessOptions = {}): Promise<Recorder> {
	const rec: Recorder = {
		consoleErrors: [],
		pageErrors: [],
		external: [],
		requests: [],
		listBodies: [],
		quoteBodies: [],
		cspViolations: () => page.evaluate(() => window.__cspViolations ?? ['listener missing'])
	};
	await page.clock.setFixedTime(NOW);
	await page.addInitScript(() => {
		const violations: string[] = [];
		window.__cspViolations = violations;
		document.addEventListener('securitypolicyviolation', (event) => {
			violations.push(`${event.violatedDirective} ${event.blockedURI} ${event.sourceFile}:${event.lineNumber}`);
		});
		const calls: (PositionOptions | null)[] = [];
		window.__geoCalls = calls;
		if ('geolocation' in navigator) {
			const original = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);
			navigator.geolocation.getCurrentPosition = (success, error, options) => {
				calls.push(options ?? null);
				original(success, error, options);
			};
		}
	});
	page.on('console', (message) => {
		if (message.type() === 'error') rec.consoleErrors.push(message.text());
	});
	page.on('pageerror', (error) => rec.pageErrors.push(String(error)));
	page.on('request', (request) =>
		rec.requests.push({ method: request.method(), url: request.url(), body: request.postData() ?? '' })
	);
	await page.route('**/*', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		if (url.origin !== BASE_URL) {
			rec.external.push(request.url());
			await route.abort();
			return;
		}
		if (!url.pathname.startsWith('/api/')) {
			await route.continue();
			return;
		}
		const method = request.method();
		const body = request.postData() ?? '';
		let result: MockResult;
		if (method === 'GET' && url.pathname === '/api/stores') {
			result = json(200, { data_date: DATA_DATE, stores: STORES });
		} else if (method === 'GET' && url.pathname === '/api/ingredients') {
			result = json(200, { ingredients: [...MOCK_INGREDIENTS, ...EXTRA_INGREDIENTS] });
		} else if (method === 'POST' && url.pathname === '/api/list') {
			rec.listBodies.push(JSON.parse(body) as unknown);
			result = json(200, { lines: options.listLines ?? LIST_LINES });
		} else if (method === 'POST' && url.pathname === '/api/quote') {
			const parsed = JSON.parse(body) as QuoteRequest;
			rec.quoteBodies.push(parsed);
			const quote = mockQuote(parsed);
			result = json(200, options.quote ? options.quote(quote) : quote);
		} else {
			result = handleMockApi(method, `${url.pathname}${url.search}`, body);
		}
		await route.fulfill({ status: result.status, contentType: 'application/json; charset=utf-8', body: JSON.stringify(result.body) });
	});
	return rec;
}

async function expectClean(page: Page, rec: Recorder): Promise<void> {
	expect(rec.consoleErrors, 'console errors').toEqual([]);
	expect(rec.pageErrors, 'uncaught errors').toEqual([]);
	expect(await rec.cspViolations(), 'CSP violations').toEqual([]);
	expect(rec.external, 'external requests').toEqual([]);
	// Coordinates never leave the device: not the raw position, not the rounded one, not a store's.
	for (const request of rec.requests) {
		expect(`${request.url} ${request.body}`).not.toMatch(/47[.,]49|47[.,]46|19[.,]05|19[.,]03|latitude|longitude|"lat"|"lon"/);
	}
	await expectNoHorizontalScroll(page);
}

async function expectNoHorizontalScroll(page: Page): Promise<void> {
	const metrics = await page.evaluate(() => ({
		scrollWidth: document.documentElement.scrollWidth,
		clientWidth: document.documentElement.clientWidth
	}));
	expect(metrics.scrollWidth, 'document wider than the viewport').toBeLessThanOrEqual(metrics.clientWidth);
}

/** Every interactive element of the page is at least 44×44 px (checkboxes count through their label). */
async function expectTouchTargets(page: Page): Promise<void> {
	const small = await page.evaluate(() => {
		const targets = document.querySelectorAll<HTMLElement>(
			'main button, main select, main input:not([type="radio"]):not([type="checkbox"]), main .btn, main label.choice, main label.check, main summary'
		);
		return [...targets]
			.filter((el) => el.offsetParent !== null)
			.map((el) => ({ el, rect: el.getBoundingClientRect() }))
			.filter(({ rect }) => rect.width < 44 || rect.height < 44)
			.map(({ el, rect }) => `${el.tagName}.${el.className} "${el.textContent?.trim().slice(0, 40)}" ${rect.width}x${rect.height}`);
	});
	expect(small, 'touch targets under 44×44 px').toEqual([]);
}

function screenshotPath(name: string): string {
	mkdirSync(SCREENSHOT_DIR, { recursive: true });
	return join(SCREENSHOT_DIR, `${name}.png`);
}

function storedJson(page: Page, key: string): Promise<Record<string, unknown> | null> {
	return page.evaluate((k) => {
		const raw = localStorage.getItem(k);
		return raw === null ? null : (JSON.parse(raw) as Record<string, unknown>);
	}, key);
}

/** A stored version-1 state with a 14-day plan from Monday 12 October 2026 (synthetic recipes). */
function seededState(extra: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		version: 1,
		language: 'hu',
		people: 2,
		slots: 3,
		radiusKm: 1.5,
		plan: {
			createdAt: '2026-10-11T18:00:00.000Z',
			startDate: '2026-10-12',
			seed: 3,
			slots: 3,
			noRepeatDays: 5,
			days: Array.from({ length: 14 }, (_, index) => ({
				index,
				meals: { reggeli: null, ebed: 'minta-lencsefozelek', vacsora: index % 2 === 0 ? 'minta-csirke' : null }
			}))
		},
		pantry: { notAtHome: [] },
		exclusions: { tags: [], ingredients: [] },
		location: { consent: 'unset', source: 'none', districtId: null, approx: null },
		...extra
	};
}

/** Seeds the state once (later navigations and reloads keep what the app stored). */
async function seed(page: Page, state: Record<string, unknown>): Promise<void> {
	await page.addInitScript(
		([key, value]) => {
			if (localStorage.getItem(key) === null) localStorage.setItem(key, value);
		},
		[STORAGE_KEY, JSON.stringify(state)] as const
	);
}

function chooseButton(page: Page, chain: string, storeId: string): ReturnType<Page['getByRole']> {
	return page.getByRole('button', { name: `Lista ennél a boltnál: ${chain}, 1051 Budapest, ${addressOf(storeId)}`, exact: true });
}

const VIEWPORTS = [
	{ name: 'phone-320', width: 320, height: 640, mobile: true },
	{ name: 'phone-360', width: 360, height: 740, mobile: true },
	{ name: 'desktop-1280', width: 1280, height: 800, mobile: false }
] as const;

// ───────────────────────────── the main flows at both sizes ─────────────────────────────

for (const viewport of VIEWPORTS) {
	test.describe(viewport.name, () => {
		test.use({
			viewport: { width: viewport.width, height: viewport.height },
			isMobile: viewport.mobile,
			hasTouch: viewport.mobile,
			geolocation: DEVICE,
			permissions: ['geolocation']
		});

		test('list -> location consent -> ranking -> chosen store, grouped', async ({ page }) => {
			const rec = await harness(page);
			await seed(page, seededState());
			await page.goto('/lista');

			await expect(page.getByRole('heading', { level: 1 })).toHaveText('Bevásárlólista');
			const thisWeek = page.getByRole('radio', { name: /Ez a hét/ });
			await expect(thisWeek).toBeChecked();
			await expect(page.locator('label').filter({ has: thisWeek })).toContainText(`2026. 10. 12. – 2026. 10. 18. · 7 nap`);

			// This week: 7 lunches and 4 dinners, 2 people each, summed per recipe.
			await expect(page.getByRole('heading', { level: 2, name: 'Zöldség, gyümölcs' })).toBeVisible();
			expect(rec.listBodies).toEqual([
				{
					items: [
						{ recipe_id: 'minta-lencsefozelek', servings: 14 },
						{ recipe_id: 'minta-csirke', servings: 8 }
					]
				}
			]);

			// Sections in the docs/DATA.md order, pantry staples apart.
			const h2 = await page.locator('main h2').allTextContents();
			expect(h2).toEqual([
				'Zöldség, gyümölcs',
				'Pékáru',
				'Tejtermék, tojás',
				'Hús, hal',
				'Száraz és tartós élelmiszer',
				'Valószínűleg otthon van',
				'Hol a legolcsóbb a közelben?'
			]);
			await expect(page.getByText('8 tétel a listán')).toBeVisible();
			await expect(page.getByRole('checkbox', { name: /^vöröshagyma\s300\sg$/ })).toBeVisible();

			// Tick a line: stored on the device.
			await page.getByRole('checkbox', { name: /^vöröshagyma/ }).check();
			await expect(page.getByText('Kipipálva: 1 / 8')).toBeVisible();
			// Ticks belong to this list (plan + range), not to every list.
			expect(await storedJson(page, STORAGE_KEY)).toMatchObject({
				list: { entries: [{ key: '2026-10-11T18:00:00.000Z|this_week', checked: ['voroshagyma'] }] }
			});

			// Remove a line by hand: it leaves the list (and the quote), focus stays on the list.
			await page.getByRole('button', { name: 'kenyér eltávolítása a listáról' }).click();
			await expect(page.getByRole('heading', { level: 2, name: 'Pékáru' })).toHaveCount(0);
			await expect(page.getByText('Eltávolított tételek (1)')).toBeVisible();
			await expect(page.getByRole('checkbox', { name: /^natúr joghurt/ })).toBeFocused();

			// A pantry staple that is not at home goes on the list.
			await page.getByRole('checkbox', { name: 'Nincs otthon: napraforgóolaj' }).check();
			await expect(page.getByRole('heading', { level: 2, name: 'Fűszer, olaj' })).toBeVisible();
			await expect(page.getByRole('checkbox', { name: /^napraforgóolaj/ })).toBeVisible();
			expect(await storedJson(page, STORAGE_KEY)).toMatchObject({ pantry: { notAtHome: ['napraforgoolaj'] } });
			await expect(page.getByText('8 tétel a listán')).toBeVisible();

			// The explanation comes first: nothing is asked or fetched before the user chooses.
			await expect(page.getByRole('heading', { name: 'Honnan keressük a boltokat?' })).toBeVisible();
			await expect(page.getByText('csak a kiválasztott boltok azonosítóit küldjük el', { exact: false })).toBeVisible();
			expect(await page.evaluate(() => window.__geoCalls?.length)).toBe(0);
			expect(rec.requests.filter((r) => r.url.includes('/api/stores') || r.url.includes('/api/quote'))).toEqual([]);
			await expectAccessible(page, `list ${viewport.name} before location`);
			await page.screenshot({ path: screenshotPath(`list-${viewport.name}-before-location`), fullPage: true });

			await page.getByRole('button', { name: 'Saját helyzetem használata' }).click();
			await expect(page.getByTestId('origin')).toContainText(
				`Kiindulási pont: a készülék hozzávetőleges helyzete (${sp('2026. 10. 13. 10:00')} állapot szerint).`
			);
			await expect(page.getByTestId('origin')).toBeFocused();
			expect(await page.evaluate(() => window.__geoCalls)).toEqual([{ enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 }]);
			expect(await storedJson(page, STORAGE_KEY)).toMatchObject({
				location: { consent: 'granted', source: 'device', approx: { lat: 47.496, lon: 19.054 } }
			});

			// Candidates: grocery, with data, in 1.5 km, at most 3 per chain; only their ids are sent.
			await expect(page.getByTestId('candidates')).toContainText(sp('8 bolt 1,5 km távolságon belül'));
			await expect(page.getByTestId('candidates')).toContainText('1 közeli bolt nem szerepel, mert nincs róla áradat.');
			await expect(page.getByTestId('store-ranking')).toBeVisible();
			expect(rec.quoteBodies).toHaveLength(1);
			const sent = rec.quoteBodies[0];
			expect(Object.keys(sent ?? {}).sort()).toEqual(['include_loyalty', 'lines', 'store_ids']);
			// Only the set of the nearest stores, sorted by id: the order must not reveal the distances.
			expect(sent?.store_ids).toEqual([...DEVICE_CANDIDATES].sort());
			expect(sent?.include_loyalty).toBe(false);
			expect(sent?.lines).toEqual([
				{ ingredient_id: 'gomba', qty: 0.25 },
				{ ingredient_id: 'friss_bazsalikom', qty: 1 },
				{ ingredient_id: 'sargarepa', qty: 0.25 },
				{ ingredient_id: 'voroshagyma', qty: 0.3 },
				{ ingredient_id: 'natur_joghurt', qty: 0.5 },
				{ ingredient_id: 'csirkemellfile', qty: 1.2 },
				{ ingredient_id: 'voros_lencse', qty: 0.4 },
				{ ingredient_id: 'napraforgoolaj', qty: 0.05 }
			]);

			// The ranking: scoped and dated; the four tied Lidl/Aldi stores by distance, never by name.
			const ranking = page.getByTestId('store-ranking');
			await expect(page.getByTestId('ranking-scope')).toHaveText(
				'Legolcsóbb elöl, a kiválasztott boltok közül, a 2026-10-13-i GVH-adatok alapján.'
			);
			const rows = ranking.getByTestId('rank-row');
			await expect(rows).toHaveCount(8);
			expect(await rows.evaluateAll((els) => els.map((el) => el.getAttribute('data-store-id')))).toEqual([
				'synthetic-lidl-a',
				'synthetic-aldi-a',
				'synthetic-lidl-b',
				'synthetic-lidl-c',
				'synthetic-tesco-a',
				'synthetic-penny-a',
				'synthetic-spar-a',
				'synthetic-spar-b'
			]);
			expect(await ranking.getByTestId('rank').allTextContents()).toEqual(['1.', '1.', '1.', '1.', '5.', '6.', '7.', '7.']);
			await expect(rows.nth(0)).toContainText('holtverseny');
			await expect(rows.nth(0)).toContainText(sp('6 701 Ft'));
			await expect(rows.nth(0)).toContainText(sp('300 m'));
			await expect(rows.nth(4)).not.toContainText('holtverseny');
			await expect(rows.nth(4)).toContainText('2 tétel elérhetősége nem biztos');
			await expect(rows.nth(6)).toContainText('1 tétel hiányzik');
			await expect(rows.nth(6)).toContainText(sp('A sorrendben a hiányzó tételek becsült árával: 8 152 Ft'));
			await expect(page.getByTestId('split')).toContainText(sp('Két boltban 2 400 Ft-tal olcsóbb'));
			await expect(page.locator('main').getByTestId('attribution-gvh').first()).toHaveText(ATTRIBUTION);
			await expect(page.locator('main').getByTestId('disclaimer').first()).toHaveText(DISCLAIMER);
			await expect(page.locator('main')).not.toContainText(/akció/i);

			// Pick a store: its list, grouped by section, with packs, labels and the KSH estimate kept apart.
			await chooseButton(page, 'Lidl', 'synthetic-lidl-a').click();
			const storeList = page.getByTestId('store-list');
			await expect(storeList.getByRole('heading', { level: 3 })).toHaveText('Lista: Lidl');
			await expect(storeList.getByRole('heading', { level: 3 })).toBeFocused();
			await expect(storeList.getByTestId('store-total')).toHaveText(sp('Fizetendő: 6 701 Ft'));
			expect(await storeList.locator('h4').allTextContents()).toEqual([
				'Zöldség, gyümölcs',
				'Tejtermék, tojás',
				'Hús, hal',
				'Száraz és tartós élelmiszer',
				'Fűszer, olaj'
			]);
			const line = (id: string) => storeList.locator(`[data-ingredient-id="${id}"]`);
			await expect(line('natur_joghurt')).toContainText(sp('3 × 175 g'));
			await expect(line('natur_joghurt')).toContainText(sp('Marad kb. 25 g'));
			await expect(line('natur_joghurt')).toContainText('lánc ár');
			await expect(line('csirkemellfile')).toContainText(sp('1,2 kg, mérve'));
			await expect(line('csirkemellfile')).toContainText(sp('3 588 Ft'));
			await expect(line('csirkemellfile')).toContainText('kedvezményes ár (GVH-jelölés)');
			await expect(line('csirkemellfile')).toContainText('bolti ár');
			await expect(line('voroshagyma')).toContainText(sp('Marad kb. 700 g'));
			await line('voroshagyma').getByText('2 másik termék ebben a boltban').click();
			await expect(line('voroshagyma')).toContainText(sp('500 g: 299 Ft (598 Ft/kg)'));
			await expect(line('voroshagyma')).toContainText(sp('mérve: 399 Ft/kg'));
			await expect(line('napraforgoolaj')).toContainText(sp('Marad kb. 950 ml'));
			await expect(line('friss_bazsalikom')).toContainText('nincs ár');
			await expect(line('friss_bazsalikom')).toContainText(sp('Kell: 1 db'));
			await expect(line('gomba')).toContainText('becsült országos átlagár (KSH)');
			await expect(line('gomba')).toContainText(sp('≈ 600 Ft, nincs benne a fizetendő összegben'));
			await expect(storeList.getByTestId('ksh-total')).toContainText(sp('600 Ft'));
			await expect(storeList.getByTestId('attribution-gvh')).toHaveText(ATTRIBUTION);
			await expect(storeList.getByTestId('attribution-ksh')).toContainText('Forrás: KSH');
			await expect(storeList.getByTestId('disclaimer')).toHaveText(DISCLAIMER);
			// Ticks are shared with the main list.
			await expect(line('voroshagyma').getByRole('checkbox')).toBeChecked();
			await page.screenshot({ path: screenshotPath(`list-${viewport.name}-store`), fullPage: true });
			await expectTouchTargets(page);
			await expectAccessible(page, `list ${viewport.name} store list`);
			// The store list's sections are not landmarks of their own: one "Zöldség, gyümölcs" region only.
			await expect(page.getByRole('region', { name: 'Zöldség, gyümölcs', exact: true })).toHaveCount(1);
			// Every priced line is a whole forint at Lidl: no rounding note.
			await expect(storeList.getByTestId('store-total-rounding')).toHaveCount(0);

			// At Spar the lentils are not available, and the weighed chicken costs a fraction of a forint: the
			// rounded lines may not add up to the exact total, and the view says so.
			await chooseButton(page, 'Spar', 'synthetic-spar-a').click();
			await expect(storeList.getByRole('heading', { level: 3 })).toHaveText('Lista: Spar');
			await expect(line('voros_lencse')).toContainText('nincs ebben a boltban');
			await expect(storeList.getByTestId('store-total-rounding')).toContainText('egész forintra kerekítve');
			await chooseButton(page, 'Lidl', 'synthetic-lidl-a').click();

			// The chosen store is remembered for this list, in the one stored document (no key of its own); after
			// a reload the same view comes back.
			expect(await storedJson(page, STORAGE_KEY)).toMatchObject({
				version: 1,
				list: {
					range: 'this_week',
					entries: [
						{
							key: '2026-10-11T18:00:00.000Z|this_week',
							checked: ['voroshagyma'],
							removed: ['kenyer'],
							included: [],
							storeId: 'synthetic-lidl-a'
						}
					]
				}
			});
			expect(await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith('hetikosar.')))).toEqual([
				STORAGE_KEY
			]);
			await page.reload();
			await expect(page.getByTestId('store-list').getByRole('heading', { level: 3 })).toHaveText('Lista: Lidl');
			await expect(page.getByRole('checkbox', { name: /^vöröshagyma/ }).first()).toBeChecked();
			await expect(page.getByText('Eltávolított tételek (1)')).toBeVisible();

			// Another range gives another list (whole plan: 14 lunches and 7 dinners for 2).
			await page.getByRole('radio', { name: /Az egész terv/ }).check();
			await expect.poll(() => rec.listBodies.at(-1)).toEqual({
				items: [
					{ recipe_id: 'minta-lencsefozelek', servings: 28 },
					{ recipe_id: 'minta-csirke', servings: 14 }
				]
			});
			await expect(page.getByText('Eltávolított tételek (1)')).toHaveCount(0);
			await expectClean(page, rec);
		});

		test('district picker, too few stores, wider radius', async ({ page }) => {
			const rec = await harness(page);
			await seed(page, seededState());
			await page.goto('/lista');
			await expect(page.getByRole('heading', { level: 2, name: 'Hol a legolcsóbb a közelben?' })).toBeVisible();

			// One status region exists before anything happens, so screen readers announce what follows.
			const status = page.getByTestId('nearby-status');
			await expect(status).toHaveAttribute('role', 'status');
			await expect(status).toHaveText('');

			await page.getByLabel('Budapesti kerület').selectOption('11');
			await expect(page.getByTestId('origin')).toContainText('Kiindulási pont: XI. kerület.');
			await expect(page.getByTestId('too-few')).toContainText(
				sp('1,5 km távolságon belül csak 1 bolt van, így nincs mivel összehasonlítani.')
			);
			await expect(status).toContainText(sp('1 bolt 1,5 km távolságon belül'));
			await expect(status).toContainText('csak 1 bolt van');
			await expect(status).toContainText('Legolcsóbb a kiválasztott boltok közül');
			await expect(page.getByTestId('rank-row')).toHaveCount(1);
			expect(rec.quoteBodies.at(-1)?.store_ids).toEqual(['synthetic-aldi-xi']);
			expect(await page.evaluate(() => window.__geoCalls?.length)).toBe(0);

			await page.getByRole('button', { name: /^Keresés 2,0\skm távolságon belül$/ }).click();
			await expect(page.getByTestId('rank-row')).toHaveCount(2);
			await expect(page.getByTestId('too-few')).toHaveCount(0);
			await expect(status).toContainText(sp('2 bolt 2,0 km távolságon belül'));
			await expect(status).not.toContainText('csak 1 bolt van');
			await expect(status).toContainText(`Legolcsóbb a kiválasztott boltok közül, a ${DATA_DATE}-i GVH-adatok alapján: Aldi`);
			expect(rec.quoteBodies.at(-1)?.store_ids).toEqual(['synthetic-aldi-xi', 'synthetic-penny-xi']);
			expect(await storedJson(page, STORAGE_KEY)).toMatchObject({
				radiusKm: 2,
				location: { consent: 'unset', source: 'district', districtId: '11', approx: null }
			});
			await expect(page.getByTestId('origin')).toContainText(sp('Keresési sugár: 2,0 km.'));

			// "Kész" closes the chooser and moves focus to the starting point.
			await page.getByRole('button', { name: 'Kész' }).click();
			await expect(page.getByRole('heading', { name: 'Honnan keressük a boltokat?' })).toHaveCount(0);
			await expect(page.getByTestId('origin')).toBeFocused();
			await expectAccessible(page, `list ${viewport.name} district`);
			await page.screenshot({ path: screenshotPath(`list-${viewport.name}-district`), fullPage: true });

			// The same view in English: texts change, numbers and dates stay hu-HU.
			await page.getByRole('button', { name: 'English' }).click();
			await expect(page.getByRole('heading', { level: 1 })).toHaveText('Shopping list');
			await expect(page.getByRole('heading', { level: 2, name: 'Fruit and vegetables' })).toBeVisible();
			await expect(page.getByTestId('ranking-scope')).toHaveText(
				'Cheapest first, among the selected stores, based on GVH data of 2026-10-13.'
			);
			await expect(page.locator('main').getByTestId('attribution-gvh').first()).toHaveText(
				`Source: GVH Árfigyelő (arfigyelo.gvh.hu), ${DATE_HU}`
			);
			await expectClean(page, rec);
		});
	});
}


// ───────────────────────────── per-list ticks, other tabs, exclusions, split, position age ─────────────────────────────

const DEVICE_LOCATION = { consent: 'granted', source: 'device', districtId: null, approx: { lat: 47.496, lon: 19.054, at: NOW.toISOString() } };

test.describe('ticks per list', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('a new plan or another range starts with no ticks; undoing a new plan brings them back', async ({ page }) => {
		const rec = await harness(page);
		await seed(page, seededState());
		await page.goto('/lista');
		const onion = page.getByRole('checkbox', { name: /^vöröshagyma/ });
		await onion.check();
		await expect(page.getByText('Kipipálva: 1 / 8')).toBeVisible();

		// Another range of the same plan: another list, no ticks; back: the tick is there.
		await page.getByRole('radio', { name: /Jövő hét/ }).check();
		await expect(page.getByText('Kipipálva: 0 / 8')).toBeVisible();
		await expect(onion).not.toBeChecked();
		await page.getByRole('radio', { name: /Ez a hét/ }).check();
		await expect(page.getByText('Kipipálva: 1 / 8')).toBeVisible();
		await expect(onion).toBeChecked();

		// "Új javaslat", undone: the same plan again, with its ticks.
		const nav = page.getByRole('navigation', { name: 'Fő navigáció' });
		await nav.getByRole('link', { name: 'Heti terv' }).click();
		await page.getByRole('button', { name: 'Új javaslat' }).click();
		await expect(page.getByText('Elkészült az új terv.')).toBeVisible();
		await page.getByRole('button', { name: 'Visszavonás' }).click();
		await expect(page.getByText('Visszaállítottuk az előző tervet.')).toBeVisible();
		await nav.getByRole('link', { name: 'Lista' }).click();
		await expect(page.getByText('Kipipálva: 1 / 8')).toBeVisible();

		// Next week's routine: delete the plan and make a new one. Its list starts with no ticks.
		await nav.getByRole('link', { name: 'Heti terv' }).click();
		await page.getByRole('button', { name: 'Terv törlése' }).click();
		await page.getByRole('button', { name: 'Terv készítése' }).click();
		await expect(page.getByRole('heading', { level: 2, name: 'A terved' })).toBeFocused();
		await nav.getByRole('link', { name: 'Lista' }).click();
		await expect(page.getByText(/Kipipálva: 0 \/ \d+/)).toBeVisible();
		await expect(page.getByRole('checkbox', { checked: true })).toHaveCount(0);

		// "Pipák törlése" removes itself: focus goes to the first line, never to <body>.
		await onion.check();
		await page.getByRole('button', { name: 'Pipák törlése' }).click();
		await expect(page.getByText(/Kipipálva: 0 \/ \d+/)).toBeVisible();
		await expect(page.locator('input[data-line-check]').first()).toBeFocused();
		expect(await page.evaluate(() => document.activeElement !== document.body)).toBe(true);
		await expectClean(page, rec);
	});
});

test.describe('another tab', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('revoking the position in another tab reaches the list, which never writes it back', async ({ page, context }) => {
		const rec = await harness(page);
		await seed(page, seededState({ location: DEVICE_LOCATION }));
		await page.goto('/lista');
		await expect(page.getByTestId('origin')).toContainText('a készülék hozzávetőleges helyzete');
		await expect(page.getByTestId('rank-row').first()).toBeVisible();

		const settings = await context.newPage();
		const other = await harness(settings);
		await settings.goto('/beallitasok');
		await settings.getByRole('button', { name: 'Engedély visszavonása' }).click();
		await expect(settings.getByTestId('location-status')).toContainText('Nincs engedélyezve.');

		// The list tab learns about it: the deleted position is no longer used, and the chooser is open again.
		await expect(page.getByTestId('origin')).toHaveCount(0);
		await expect(page.getByRole('heading', { name: 'Honnan keressük a boltokat?' })).toBeVisible();
		await page.getByLabel('Budapesti kerület').selectOption('11');
		await expect(page.getByTestId('origin')).toContainText('Kiindulási pont: XI. kerület.');
		const stored = await storedJson(page, STORAGE_KEY);
		expect(stored).toMatchObject({ location: { consent: 'unset', source: 'district', districtId: '11', approx: null } });
		await expectClean(page, rec);
		await expectClean(settings, other);
	});

	test('a tab that missed the change still builds the new location from what is stored', async ({ page, context }) => {
		// This tab never hears about the other tab (as if the browser had not delivered the storage event).
		await page.addInitScript(() => {
			window.addEventListener('storage', (event) => event.stopImmediatePropagation(), true);
		});
		const rec = await harness(page);
		await seed(page, seededState({ location: DEVICE_LOCATION }));
		await page.goto('/lista');
		await expect(page.getByTestId('origin')).toContainText('a készülék hozzávetőleges helyzete');

		const settings = await context.newPage();
		const other = await harness(settings);
		await settings.goto('/beallitasok');
		await settings.getByRole('button', { name: 'Engedély visszavonása' }).click();
		await expect(settings.getByTestId('location-status')).toContainText('Nincs engedélyezve.');

		// The stale tab still shows the old origin; choosing a district must not bring the position back.
		await page.getByRole('button', { name: 'Másik kiindulási pont' }).click();
		await page.getByLabel('Budapesti kerület').selectOption('11');
		await expect.poll(async () => (await storedJson(page, STORAGE_KEY))?.location).toEqual({
			consent: 'unset',
			source: 'district',
			districtId: '11',
			approx: null
		});
		await expectClean(page, rec);
		await expectClean(settings, other);
	});

	test('"Minden adat törlése" in another tab empties the list tab, which writes nothing back', async ({ page, context }) => {
		const rec = await harness(page);
		await seed(page, seededState({ location: DEVICE_LOCATION }));
		await page.goto('/lista');
		await page.getByRole('checkbox', { name: /^vöröshagyma/ }).check();
		await expect(page.getByText('Kipipálva: 1 / 8')).toBeVisible();

		const settings = await context.newPage();
		const other = await harness(settings);
		await settings.goto('/beallitasok');
		await settings.getByRole('button', { name: 'Minden adat törlése' }).click();
		await settings.getByRole('dialog').getByRole('button', { name: 'Igen, mindent törlök' }).click();
		await expect(settings.getByText('Minden adat törölve.')).toBeVisible();

		await expect(page.getByText('Még nincs heti terved')).toBeVisible();
		await expect(page.getByTestId('origin')).toHaveCount(0);
		expect(await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith('hetikosar.')))).toEqual([]);
		await expectClean(page, rec);
		await expectClean(settings, other);
	});
});

test.describe('excluded ingredients and tap water', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('an excluded ingredient is not bought or priced unless the user buys it anyway; water is never bought', async ({ page }) => {
		const water = listLine('viz', 'víz', 4.832, 'l', 'egyeb', true);
		const rec = await harness(page, { listLines: [...LIST_LINES, water] });
		await seed(page, seededState({ exclusions: { tags: [], ingredients: ['natur_joghurt'] } }));
		await page.goto('/lista');

		const excluded = page.getByTestId('excluded-lines');
		await expect(excluded.getByRole('heading', { level: 2 })).toHaveText('Kizárt alapanyagok');
		await expect(excluded).toContainText('natúr joghurt');
		await expect(page.getByText('7 tétel a listán')).toBeVisible();
		await expect(page.getByRole('checkbox', { name: /^natúr joghurt/ })).toHaveCount(0);

		// The pantry note no longer promises a price for every staple; water has no "nincs otthon" switch.
		await expect(page.getByText('ha van rá bolti ár', { exact: false })).toBeVisible();
		await expect(page.getByRole('checkbox', { name: 'Nincs otthon: víz' })).toHaveCount(0);
		await expect(page.getByRole('checkbox', { name: 'Nincs otthon: napraforgóolaj' })).toBeVisible();

		await page.getByLabel('Budapesti kerület').selectOption('05');
		await expect(page.getByTestId('rank-row').first()).toBeVisible();
		expect(rec.quoteBodies.at(-1)?.lines.map((line) => line.ingredient_id)).not.toContain('natur_joghurt');
		expect(rec.quoteBodies.at(-1)?.lines.map((line) => line.ingredient_id)).not.toContain('viz');

		await excluded.getByRole('button', { name: 'Mégis megveszem: natúr joghurt' }).click();
		const yoghurt = page.getByRole('checkbox', { name: /^natúr joghurt/ });
		await expect(yoghurt).toBeFocused();
		await expect(page.getByText('8 tétel a listán')).toBeVisible();
		await expect(page.locator('li').filter({ has: yoghurt })).toContainText('kizárt alapanyag');
		await expect(page.getByTestId('excluded-lines')).toHaveCount(0);
		await expect.poll(() => rec.quoteBodies.at(-1)?.lines.map((line) => line.ingredient_id)).toContain('natur_joghurt');
		expect(await storedJson(page, STORAGE_KEY)).toMatchObject({
			list: { entries: [{ key: '2026-10-11T18:00:00.000Z|this_week', included: ['natur_joghurt'] }] }
		});
		await expectAccessible(page, 'list excluded ingredients');
		await expectClean(page, rec);
	});
});

test.describe('the 2-store split', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('names the lines neither store sells and says the total leaves them out', async ({ page }) => {
		const unavailableAtSplit = (quote: QuoteResponse): QuoteResponse => ({
			...quote,
			stores: quote.stores.map((store) =>
				store.store_id === 'synthetic-lidl-a' || store.store_id === 'synthetic-tesco-a'
					? {
							...store,
							missing: [...store.missing, 'friss_bazsalikom'],
							lines: store.lines.map((line) =>
								line.ingredient_id === 'friss_bazsalikom' ? emptyLine(line.ingredient_id, line.qty, line.unit, 'unavailable') : line
							)
						}
					: store
			)
		});
		const rec = await harness(page, { quote: unavailableAtSplit });
		await seed(page, seededState());
		await page.goto('/lista');
		await page.getByLabel('Budapesti kerület').selectOption('05');
		const split = page.getByTestId('split');
		await expect(split).toContainText(sp('Két boltban'));
		await expect(split.getByTestId('split-missing')).toContainText('1 tétel egyik boltban sem kapható:');
		await expect(split.getByTestId('split-missing')).toContainText('friss bazsalikom');
		await expect(split).toContainText('A fizetendő összeg ezt a tételt nem tartalmazza.');
		await expectAccessible(page, 'list split with missing lines');
		await expectClean(page, rec);
	});
});

test.describe('a stored device position', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('shows when it was taken, flags one over a day old, and asks the browser only on a click', async ({ page }) => {
		const rec = await harness(page);
		const old = { ...DEVICE_LOCATION, approx: { ...DEVICE_LOCATION.approx, at: '2026-10-10T08:00:00.000Z' } };
		await seed(page, seededState({ location: old }));
		await page.goto('/lista');

		await expect(page.getByTestId('origin')).toContainText(
			`Kiindulási pont: a készülék hozzávetőleges helyzete (${sp('2026. 10. 10. 10:00')} állapot szerint).`
		);
		await expect(page.getByTestId('position-stale')).toContainText('több mint egy napja');
		// The chooser is open so the position can be updated, but the stored one is still used meanwhile.
		await expect(page.getByRole('heading', { name: 'Honnan keressük a boltokat?' })).toBeVisible();
		await expect(page.getByTestId('rank-row').first()).toBeVisible();
		expect(await page.evaluate(() => window.__geoCalls?.length)).toBe(0);

		await page.getByRole('button', { name: 'Kész' }).click();
		await page.getByRole('button', { name: 'Helyzet frissítése' }).click();
		await expect(page.getByRole('heading', { name: 'Honnan keressük a boltokat?' })).toBeFocused();
		expect(await page.evaluate(() => window.__geoCalls?.length)).toBe(0);
		await expectClean(page, rec);
	});
});

// ───────────────────────────── other states ─────────────────────────────

test.describe('location refused by the browser', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true, permissions: [] });

	test('explains, stores the refusal and still offers the districts', async ({ page }) => {
		const rec = await harness(page);
		await seed(page, seededState());
		await page.goto('/lista');
		await page.getByRole('button', { name: 'Saját helyzetem használata' }).click();
		await expect(page.getByText('A böngésző nem engedte a helyzet lekérését.', { exact: false })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Saját helyzetem használata' })).toBeFocused();
		await expect(page.getByLabel('Budapesti kerület')).toBeVisible();
		expect(await storedJson(page, STORAGE_KEY)).toMatchObject({ location: { consent: 'declined', approx: null } });
		expect(rec.quoteBodies).toEqual([]);
		await expectClean(page, rec);
	});
});

test.describe('pantry and exclusion settings', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('stay on the device and change the list', async ({ page }) => {
		const rec = await harness(page);
		await seed(page, seededState());
		await page.goto('/beallitasok');

		const pantry = page.getByTestId('pantry-settings');
		await expect(pantry.getByRole('checkbox', { name: 'napraforgóolaj' })).toBeChecked();
		await expect(pantry.getByRole('checkbox', { name: 'pirospaprika' })).toBeChecked();
		await expect(pantry.getByRole('checkbox', { name: 'só' })).toBeChecked();
		await expect(pantry.getByRole('checkbox')).toHaveCount(3);
		await pantry.getByRole('checkbox', { name: 'pirospaprika' }).uncheck();
		expect(await storedJson(page, STORAGE_KEY)).toMatchObject({ pantry: { notAtHome: ['pirospaprika'] } });

		const exclusions = page.getByTestId('exclusion-settings');
		await exclusions.getByRole('checkbox', { name: 'Hal' }).check();
		await exclusions.getByLabel('Alapanyag keresése').fill('lencse');
		await exclusions.getByRole('button', { name: 'vörös lencse kizárása' }).click();
		await expect(exclusions.getByLabel('Alapanyag keresése')).toBeFocused();
		await expect(exclusions.getByRole('button', { name: 'vörös lencse visszavétele' })).toBeVisible();
		await exclusions.getByLabel('Alapanyag keresése').fill('voros');
		await expect(exclusions.getByRole('button', { name: 'vöröshagyma kizárása' })).toBeVisible();
		await expect(exclusions.getByRole('button', { name: 'vörös lencse kizárása' })).toHaveCount(0);
		expect(await storedJson(page, STORAGE_KEY)).toMatchObject({ exclusions: { tags: ['hal'], ingredients: ['voros_lencse'] } });
		await expectNoHorizontalScroll(page);
		await page.screenshot({ path: screenshotPath('settings-phone-360-pantry-exclusions'), fullPage: true });

		await exclusions.getByRole('button', { name: 'vörös lencse visszavétele' }).click();
		expect(await storedJson(page, STORAGE_KEY)).toMatchObject({ exclusions: { tags: ['hal'], ingredients: [] } });

		// The list now shows the paprika as "nincs otthon" in its section.
		await page.goto('/lista');
		await expect(page.getByRole('checkbox', { name: 'Nincs otthon: pirospaprika' })).toBeChecked();
		await expect(page.getByRole('checkbox', { name: /^pirospaprika/ })).toBeVisible();
		await expect(page.getByText('9 tétel a listán')).toBeVisible();
		await expectClean(page, rec);
	});

	test('"Minden adat törlése" also clears the list choices', async ({ page }) => {
		const rec = await harness(page);
		await seed(page, seededState({ exclusions: { tags: ['hal'], ingredients: ['voros_lencse'] } }));
		await page.goto('/lista');
		await page.getByRole('button', { name: 'kenyér eltávolítása a listáról' }).click();
		expect(await storedJson(page, STORAGE_KEY)).toMatchObject({ list: { entries: [{ removed: ['kenyer'] }] } });
		await page.goto('/beallitasok');
		await expect(page.getByTestId('exclusion-settings').getByRole('checkbox', { name: 'Hal' })).toBeChecked();
		await page.getByRole('button', { name: 'Minden adat törlése' }).click();
		await page.getByRole('dialog').getByRole('button', { name: 'Igen, mindent törlök' }).click();
		await expect(page.getByText('Minden adat törölve.')).toBeVisible();
		await expect(page.getByTestId('exclusion-settings').getByRole('checkbox', { name: 'Hal' })).not.toBeChecked();
		await expect(page.getByTestId('exclusion-settings')).toContainText('Nincs kizárt alapanyag.');
		expect(await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith('hetikosar.')))).toEqual([]);
		// Back on the list (in-app navigation: a reload would run the seeding script again) there is no plan,
		// so nothing of the old list or its removed lines is shown.
		await page.getByRole('navigation', { name: 'Fő navigáció' }).getByRole('link', { name: 'Lista' }).click();
		await expect(page.getByText('Még nincs heti terved')).toBeVisible();
		await expect(page.getByText('Eltávolított tételek', { exact: false })).toHaveCount(0);
		await expectClean(page, rec);
	});
});

test.describe('storage refused by the browser', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('the list still works for this session and says so', async ({ page }) => {
		await page.addInitScript((state) => {
			localStorage.setItem('hetikosar.state', state);
			Storage.prototype.setItem = () => {
				throw new DOMException('quota', 'QuotaExceededError');
			};
		}, JSON.stringify(seededState()));
		const rec = await harness(page);
		await page.goto('/lista');
		await page.getByRole('checkbox', { name: /^vöröshagyma/ }).check();
		await expect(page.getByRole('checkbox', { name: /^vöröshagyma/ })).toBeChecked();
		await expect(page.getByText('A böngésző nem engedi az adatok mentését', { exact: false })).toBeVisible();
		await page.getByRole('button', { name: 'kenyér eltávolítása a listáról' }).click();
		await expect(page.getByText('Eltávolított tételek (1)')).toBeVisible();
		await expectClean(page, rec);
	});

	test('"Minden adat törlése" still clears this session when the stored copy cannot be deleted', async ({ page }) => {
		await page.addInitScript((state) => {
			localStorage.setItem('hetikosar.state', state);
			Storage.prototype.setItem = () => {
				throw new DOMException('quota', 'QuotaExceededError');
			};
			Storage.prototype.removeItem = () => {
				throw new DOMException('denied', 'SecurityError');
			};
		}, JSON.stringify(seededState()));
		const rec = await harness(page);
		await page.goto('/lista');
		await page.getByRole('button', { name: 'kenyér eltávolítása a listáról' }).click();
		await expect(page.getByText('Eltávolított tételek (1)')).toBeVisible();

		// In-app navigation keeps this session's memory: the reset must reach it.
		const nav = page.getByRole('navigation', { name: 'Fő navigáció' });
		await nav.getByRole('link', { name: 'Beállítások' }).click();
		await page.getByRole('button', { name: 'Minden adat törlése' }).click();
		await page.getByRole('dialog').getByRole('button', { name: 'Igen, mindent törlök' }).click();
		await expect(page.getByText('a böngésző nem engedte elérni a tárolóját', { exact: false })).toBeVisible();
		await expect(page.getByText('Minden adat törölve.')).toHaveCount(0);
		await expect(page.getByTestId('people-value')).toHaveText('2 fő');

		await nav.getByRole('link', { name: 'Lista' }).click();
		await expect(page.getByText('Még nincs heti terved')).toBeVisible();
		await expect(page.getByText('Eltávolított tételek', { exact: false })).toHaveCount(0);
		await expectClean(page, rec);
	});
});

test.describe('no plan yet', () => {
	test.use({ viewport: { width: 360, height: 740 } });

	test('points to the plan page and asks for nothing', async ({ page }) => {
		const rec = await harness(page);
		await page.goto('/lista');
		await expect(page.getByText('Még nincs heti terved')).toBeVisible();
		await expect(page.getByRole('link', { name: 'Heti terv készítése' })).toHaveAttribute('href', '/terv');
		expect(rec.requests.filter((r) => r.url.includes('/api/') && !r.url.endsWith('/api/meta'))).toEqual([]);
		await expectClean(page, rec);
	});
});
