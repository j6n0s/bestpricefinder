/**
 * The cart ("Kosár"): browse the goods, put them in a cart with − / + amounts, and see where the cart is cheapest
 * nearby: in one store, or on a short route through several stores with a map (computed on the device).
 *
 * Every /api answer here is SYNTHETIC test data (see tests/mocks/README.md): store ids "synthetic-…", addresses
 * "Minta utca …", product names "Szintetikus …" and every price are invented. The expected totals and routes
 * below are worked out by hand from these prices and positions.
 *
 * Every test checks: no console errors, no uncaught errors, no CSP violations, no request to another origin,
 * no request that carries coordinates, and no horizontal scroll.
 */
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import type {
	IngredientOut,
	PackOptionOut,
	QuoteLineOut,
	QuoteRequest,
	QuoteResponse,
	RankOut,
	StoreOut,
	StoreQuoteOut
} from '../../src/lib/api/types';
import { MOCK_META, handleMockApi, type MockResult } from '../mocks/api';
import { expectAccessible } from './a11y';
import { BASE_URL, SCREENSHOT_DIR } from './config';

const DATA_DATE = '2026-10-13';
const STORAGE_KEY = 'hetikosar.state';
/** Tuesday 13 October 2026, 10:00 in Budapest. */
const NOW = new Date('2026-10-13T08:00:00Z');
const NBSP = ' ';
const sp = (text: string): string => text.replaceAll(' ', NBSP);

// ───────────────────────────── synthetic stores ─────────────────────────────

/** The device position the browser reports, and where it ends up after rounding to 3 decimals. */
const DEVICE = { latitude: 47.4961234, longitude: 19.0538765 };
const DEVICE_ROUNDED = { lat: 47.496, lon: 19.054 };
const KM_PER_DEG_LAT = 111.195;

function at(kmNorth: number, kmEast: number): { lat: number; lon: number } {
	return {
		lat: DEVICE_ROUNDED.lat + kmNorth / KM_PER_DEG_LAT,
		lon: DEVICE_ROUNDED.lon + kmEast / (KM_PER_DEG_LAT * Math.cos((DEVICE_ROUNDED.lat * Math.PI) / 180))
	};
}

function store(id: string, chain: string, position: { lat: number; lon: number }, address: string): StoreOut {
	return {
		id,
		chain,
		postal_code: '1051',
		city: 'Budapest',
		address,
		lat: position.lat,
		lon: position.lon,
		format: null,
		is_budapest: true,
		has_data: true
	};
}

/** Aldi 200 m east, Spar 400 m north, Penny 600 m south; Lidl 3 km away (outside the 1.5 km radius). */
const STORES: StoreOut[] = [
	store('synthetic-aldi-k', 'aldi', at(0, 0.2), 'Minta utca 1.'),
	store('synthetic-spar-k', 'spar', at(0.4, 0), 'Minta utca 2.'),
	store('synthetic-penny-k', 'penny', at(-0.6, 0), 'Minta utca 3.'),
	store('synthetic-lidl-far', 'lidl', at(3, 0), 'Minta utca 4.')
];
const STORE_BY_ID = new Map(STORES.map((s) => [s.id, s]));
const NEARBY_IDS = ['synthetic-aldi-k', 'synthetic-penny-k', 'synthetic-spar-k'];

// ───────────────────────────── synthetic catalogue ─────────────────────────────

function good(
	id: string,
	name: string,
	unit: IngredientOut['unit'],
	group: string,
	priced: IngredientOut['priced_by'] = 'gvh',
	pieceWeight: number | null = null,
	tags: IngredientOut['tags'] = []
): IngredientOut {
	return { id, name_hu: name, list_group: group, unit, piece_weight_kg: pieceWeight, pantry: false, priced_by: priced, tags };
}

const INGREDIENTS: IngredientOut[] = [
	good('tej', 'tej', 'l', 'tejtermek_tojas', 'gvh', null, ['dairy']),
	good('orolt_kave', 'őrölt kávé', 'kg', 'szaraz_tartos'), // no tag: "Egyéb" in its section
	good('alma', 'alma', 'kg', 'zoldseg_gyumolcs', 'gvh', 0.18, ['fruit']),
	good('tojas', 'tojás', 'db', 'tejtermek_tojas', 'gvh', null, ['egg']),
	good('kenyer', 'kenyér', 'db', 'pekaru', 'gvh', null, ['grain']),
	good('banan', 'banán', 'kg', 'zoldseg_gyumolcs', 'gvh', 0.17, ['fruit']),
	// Not in the cart's goods: no store price, only a KSH estimate, and tap water.
	good('so', 'só', 'kg', 'fuszer_olaj', 'none', null, ['condiment']),
	good('gomba', 'csiperkegomba', 'kg', 'zoldseg_gyumolcs', 'ksh', null, ['vegetable']),
	good('viz', 'víz', 'l', 'egyeb')
];
/** The goods in shop-section order, then by name. */
const GOODS_ORDER = ['alma', 'banan', 'kenyer', 'tej', 'tojas', 'orolt_kave'];

// ───────────────────────────── synthetic quote (contract behaviour) ─────────────────────────────

/**
 * Synthetic unit prices (Ft per kg, l or piece) per chain; null: the store does not sell it ("unavailable").
 * Kenyér has no store price anywhere ("unpriced").
 */
const PRICES: Record<string, Record<string, number | null>> = {
	alma: { aldi: 500, spar: 800, penny: 700 },
	banan: { aldi: 600, spar: null, penny: null },
	tej: { aldi: 300, spar: 400, penny: 380 },
	tojas: { aldi: 40, spar: 110, penny: 95 },
	orolt_kave: { aldi: null, spar: 10000, penny: 7200 }
};

const round2 = (value: number): number => Math.round(value * 100) / 100;

function quoteLine(id: string, qty: number, chain: string): QuoteLineOut {
	const unit = INGREDIENTS.find((g) => g.id === id)?.unit ?? 'kg';
	const empty = (status: QuoteLineOut['status']): QuoteLineOut => ({
		ingredient_id: id,
		qty,
		unit,
		status,
		picks: [],
		checkout_cost: null,
		used_cost: null,
		leftover_qty: null,
		ksh_estimate: null,
		alternatives: []
	});
	const prices = PRICES[id];
	if (!prices) return empty('unpriced');
	const price = prices[chain] ?? null;
	if (price === null) return empty('unavailable');
	const packSize = unit === 'db' ? 1 : null; // pieces by the piece, the rest by weight or volume
	const pack: PackOptionOut = {
		product_id: `synthetic-${id}-${chain}`,
		product_name: `Szintetikus ${id}`,
		pack_size: packSize,
		pack_price: price,
		unit_price: price,
		price_type: 'NORMAL',
		price_scope: 'chain',
		availability: 'confirmed'
	};
	const count = packSize === null ? 1 : Math.ceil(qty - 1e-9);
	const bought = packSize === null ? qty : count;
	const cost = packSize === null ? round2(qty * price) : count * price;
	return {
		ingredient_id: id,
		qty,
		unit,
		status: 'priced',
		picks: [{ option: pack, count, qty: bought, cost }],
		checkout_cost: cost,
		used_cost: cost,
		leftover_qty: Math.round((bought - qty) * 1000) / 1000,
		ksh_estimate: null,
		alternatives: []
	};
}

function median(values: number[]): number {
	const sorted = [...values].sort((a, b) => a - b);
	const mid = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? (sorted[mid] ?? 0) : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
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
			assumed_count: 0,
			ksh_estimate_total: 0,
			lines
		};
	});
	const costOf = (quote: StoreQuoteOut, ingredientId: string): number | null => {
		const line = quote.lines.find((l) => l.ingredient_id === ingredientId);
		return line?.status === 'priced' ? line.checkout_cost : null;
	};
	const penalized = (q: StoreQuoteOut): number =>
		q.checkout_total +
		q.missing.reduce((sum, ingredientId) => {
			const others = stores.filter((o) => o !== q).map((o) => costOf(o, ingredientId)).filter((c): c is number => c !== null);
			return sum + (others.length > 0 ? median(others) : 0);
		}, 0);
	const keyed = stores.map((q) => ({ q, whole: Math.round(penalized(q)), pen: round2(penalized(q)) }));
	keyed.sort((a, b) => a.whole - b.whole || a.q.missing.length - b.q.missing.length || (a.q.store_id < b.q.store_id ? -1 : 1));
	const ranking: RankOut[] = keyed.map((k) => ({
		store_id: k.q.store_id,
		rank: 1 + keyed.filter((o) => o.whole < k.whole || (o.whole === k.whole && o.q.missing.length < k.q.missing.length)).length,
		checkout_total: k.q.checkout_total,
		penalized_total: k.pen,
		missing_count: k.q.missing.length
	}));
	return {
		data_date: DATA_DATE,
		stores,
		ranking,
		split: null,
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
	quoteBodies: QuoteRequest[];
	cspViolations: () => Promise<string[]>;
}

declare global {
	interface Window {
		__cspViolations?: string[];
		__geoCalls?: (PositionOptions | null)[];
	}
}

async function harness(page: Page, extraIngredients: IngredientOut[] = []): Promise<Recorder> {
	const rec: Recorder = {
		consoleErrors: [],
		pageErrors: [],
		external: [],
		requests: [],
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
			result = { status: 200, body: { data_date: DATA_DATE, stores: STORES } };
		} else if (method === 'GET' && url.pathname === '/api/ingredients') {
			result = { status: 200, body: { ingredients: [...INGREDIENTS, ...extraIngredients] } };
		} else if (method === 'POST' && url.pathname === '/api/quote') {
			const parsed = JSON.parse(body) as QuoteRequest;
			rec.quoteBodies.push(parsed);
			result = { status: 200, body: mockQuote(parsed) };
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
		expect(`${request.url} ${request.body}`).not.toMatch(/47[.,]49|47[.,]50|19[.,]05|latitude|longitude|"lat"|"lon"/);
	}
	const metrics = await page.evaluate(() => ({
		scrollWidth: document.documentElement.scrollWidth,
		clientWidth: document.documentElement.clientWidth
	}));
	expect(metrics.scrollWidth, 'document wider than the viewport').toBeLessThanOrEqual(metrics.clientWidth);
}

function screenshotPath(name: string): string {
	mkdirSync(SCREENSHOT_DIR, { recursive: true });
	return join(SCREENSHOT_DIR, `${name}.png`);
}

async function storedCart(page: Page): Promise<unknown> {
	return page.evaluate((key) => {
		const raw = localStorage.getItem(key);
		return raw === null ? null : (JSON.parse(raw) as { cart?: unknown }).cart;
	}, STORAGE_KEY);
}

/** A stored version-1 state with this cart (and no plan). */
function cartState(lines: { ingredientId: string; qty: number }[], extra: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		version: 1,
		language: 'hu',
		people: 2,
		slots: 3,
		radiusKm: 1.5,
		plan: null,
		pantry: { notAtHome: [] },
		exclusions: { tags: [], ingredients: [] },
		location: { consent: 'unset', source: 'none', districtId: null, approx: null },
		cart: { lines, checked: [], storeId: null },
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

const goodRow = (page: Page, id: string) => page.getByTestId('browse').locator(`[data-testid="good"][data-ingredient-id="${id}"]`);

const VIEWPORTS = [
	{ name: 'phone-320', width: 320, height: 640, mobile: true },
	{ name: 'phone-360', width: 360, height: 740, mobile: true },
	{ name: 'desktop-1280', width: 1280, height: 800, mobile: false }
] as const;

const WITH_LOCATION = { geolocation: DEVICE, permissions: ['geolocation'] };

// ───────────────────────────── the main flow at every size ─────────────────────────────

for (const viewport of VIEWPORTS) {
	test.describe(viewport.name, () => {
		test.use({
			viewport: { width: viewport.width, height: viewport.height },
			isMobile: viewport.mobile,
			hasTouch: viewport.mobile,
			...WITH_LOCATION
		});

		test('browse by category: a bar of sections and, under one, its kinds of goods', async ({ page }) => {
			const rec = await harness(page);
			await page.goto('/kosar');
			const browse = page.getByTestId('browse');
			const bar = page.getByRole('navigation', { name: 'Kategóriák' });
			await expect(bar.getByRole('button')).toHaveText(['Zöldség, gyümölcs', 'Pékáru', 'Tejtermék, tojás', 'Száraz és tartós élelmiszer']);
			await expect(page.getByTestId('category-menu')).toHaveCount(0);

			// A section with one kind of goods is chosen straight from the bar.
			await bar.getByRole('button', { name: 'Pékáru' }).click();
			await expect(page.getByTestId('chosen-category')).toHaveText('Pékáru');
			await expect(page.getByTestId('chosen-category')).toBeFocused();
			await expect(bar.getByRole('button', { name: 'Pékáru' })).toHaveAttribute('aria-pressed', 'true');
			await expect(page.getByTestId('goods-count')).toHaveText('1 termék');
			await expect(browse.getByTestId('good')).toHaveText([/kenyér/]);
			await expect(browse.locator('h3.group')).toHaveCount(1); // the chosen section's heading only

			// A section with several kinds opens a menu: the whole section, or one kind, with how many goods.
			await bar.getByRole('button', { name: 'Tejtermék, tojás' }).click();
			const menu = page.getByTestId('category-menu');
			await expect(bar.getByRole('button', { name: 'Tejtermék, tojás' })).toHaveAttribute('aria-expanded', 'true');
			await expect(menu.getByRole('button')).toHaveText(['Az egész kategória', 'Tej, sajt, joghurt, tejföl (1 termék)', 'Tojás (1 termék)']);
			await page.screenshot({ path: screenshotPath(`cart-${viewport.name}-categories`), fullPage: true });
			await menu.getByRole('button', { name: 'Tojás' }).click();
			await expect(menu).toHaveCount(0);
			await expect(bar.getByRole('button', { name: 'Tejtermék, tojás' })).toHaveAttribute('aria-expanded', 'false');
			await expect(page.getByTestId('chosen-category')).toHaveText('Tejtermék, tojás: Tojás');
			await expect(page.getByTestId('chosen-category')).toBeFocused();
			await expect(browse.getByTestId('good')).toHaveText([/tojás/]);
			await expect(page.getByTestId('goods-count')).toHaveText('1 termék');
			await page.getByRole('button', { name: 'Kosárba: tojás' }).click();
			await expect(page.getByTestId('cart-count')).toHaveText('1 tétel');
			await expectAccessible(page, `cart ${viewport.name} category`);

			// Escape closes the menu and returns to its button; "Az egész kategória" shows the whole section.
			await bar.getByRole('button', { name: 'Tejtermék, tojás' }).click();
			await expect(menu.getByRole('button', { name: 'Tojás' })).toHaveAttribute('aria-current', 'true');
			await page.keyboard.press('Escape');
			await expect(menu).toHaveCount(0);
			await expect(bar.getByRole('button', { name: 'Tejtermék, tojás' })).toBeFocused();
			await page.keyboard.press('Enter');
			await menu.getByRole('button', { name: 'Az egész kategória' }).click();
			await expect(page.getByTestId('chosen-category')).toHaveText('Tejtermék, tojás');
			await expect(browse.getByTestId('good')).toHaveText([/^tej/, /^tojás/]);
			await expect(page.getByTestId('goods-count')).toHaveText('2 termék');

			// A search looks through every section and drops the category; "Minden termék" shows everything again.
			await page.getByLabel('Keresés a termékek között').fill('alma');
			await expect(page.getByTestId('chosen-category')).toHaveCount(0);
			await expect(browse.getByTestId('good')).toHaveText([/^alma/]);
			await page.getByLabel('Keresés a termékek között').fill('');
			await expect(page.getByTestId('goods-count')).toHaveText('6 termék');
			await expect(browse.locator('h3.group')).toHaveCount(4);
			await bar.getByRole('button', { name: 'Pékáru' }).click();
			await page.getByRole('button', { name: 'Minden termék' }).click();
			await expect(page.getByTestId('chosen-category')).toHaveCount(0);
			await expect(bar.getByRole('button', { name: 'Pékáru' })).toBeFocused();
			await expect(page.getByTestId('goods-count')).toHaveText('6 termék');
			await expectClean(page, rec);
		});

		test('browse -> cart -> one store or a route, with a map', async ({ page }) => {
			const rec = await harness(page);
			await page.goto('/kosar');

			await expect(page.getByRole('heading', { level: 1 })).toHaveText('Kosár');
			// The cart lives in the header (no tab in the bottom bar); its button says how many goods it holds.
			const headerCart = page.getByRole('banner').getByRole('link', { name: 'Kosár, 0 tétel' });
			await expect(headerCart).toHaveAttribute('aria-current', 'page');
			await expect(page.getByRole('navigation', { name: 'Fő navigáció' }).getByRole('link', { name: 'Kosár' })).toHaveCount(0);
			await expect(page.getByTestId('cart-count')).toHaveText('0 tétel');
			await expect(page.getByTestId('cart')).toContainText('A kosarad még üres.');

			// Only goods with store prices, by shop section, then name; the list starts open for an empty cart.
			const browse = page.getByTestId('browse');
			await expect(browse).toHaveAttribute('open', '');
			await expect(page.getByTestId('goods-count')).toHaveText('6 termék');
			expect(await browse.getByTestId('good').evaluateAll((els) => els.map((el) => el.getAttribute('data-ingredient-id')))).toEqual(GOODS_ORDER);
			expect(await browse.locator('h3').allTextContents()).toEqual([
				'Zöldség, gyümölcs',
				'Pékáru',
				'Tejtermék, tojás',
				'Száraz és tartós élelmiszer'
			]);

			// Search: without accents or case; nothing found offers a way back.
			const search = page.getByLabel('Keresés a termékek között');
			await search.fill('KAVE');
			await expect(page.getByTestId('goods-count')).toHaveText('1 termék');
			await expect(browse.getByTestId('good')).toHaveText([/őrölt kávé/]);
			await search.fill('nincs ilyen');
			await expect(browse).toContainText('Nincs ilyen termék.');
			await page.getByRole('button', { name: 'Keresés törlése' }).click();
			await expect(search).toBeFocused();
			await expect(search).toHaveValue('');
			await expect(page.getByTestId('goods-count')).toHaveText('6 termék');

			// Add: a sensible first amount, about how many pieces; − / + along round amounts.
			await page.getByRole('button', { name: 'Kosárba: alma' }).click();
			await expect(page.getByRole('banner').getByRole('link', { name: 'Kosár, 1 tétel' })).toBeVisible();
			await expect(page.getByTestId('header-cart-count')).toHaveText('1');
			await expect(goodRow(page, 'alma').getByRole('status')).toHaveAccessibleName(sp('alma: 500 g'));
			await expect(goodRow(page, 'alma')).toContainText(sp('3 db'));
			await goodRow(page, 'alma').getByRole('button', { name: 'Több: alma' }).click();
			await expect(goodRow(page, 'alma').getByRole('status')).toHaveAccessibleName(sp('alma: 750 g'));
			await expect(goodRow(page, 'alma')).toContainText(sp('4 db'));
			await goodRow(page, 'alma').getByRole('button', { name: 'Kevesebb: alma' }).click();
			await expect(goodRow(page, 'alma').getByRole('status')).toHaveAccessibleName(sp('alma: 500 g'));
			await expect(page.getByTestId('cart-count')).toHaveText('1 tétel');
			expect(await storedCart(page)).toEqual({ lines: [{ ingredientId: 'alma', qty: 0.5 }], checked: [], storeId: null });

			// At the smallest amount the − is a bin that takes the good out again.
			await page.getByRole('button', { name: 'Kosárba: kenyér' }).click();
			await expect(goodRow(page, 'kenyer').getByRole('status')).toHaveAccessibleName(sp('kenyér: 1 db'));
			await expect(goodRow(page, 'kenyer').getByRole('button', { name: 'Kevesebb: kenyér' })).toHaveCount(0);
			await goodRow(page, 'kenyer').getByRole('button', { name: 'Törlés a kosárból: kenyér' }).click();
			await expect(page.getByRole('button', { name: 'Kosárba: kenyér' })).toBeVisible();
			await expect(page.getByTestId('cart-count')).toHaveText('1 tétel');

			// Eggs come by the box of 10.
			await page.getByRole('button', { name: 'Kosárba: tej' }).click();
			await page.getByRole('button', { name: 'Kosárba: tojás' }).click();
			await expect(goodRow(page, 'tojas').getByRole('status')).toHaveAccessibleName(sp('tojás: 10 db'));
			await page.getByRole('button', { name: 'Kosárba: őrölt kávé' }).click();
			await expect(page.getByTestId('cart-count')).toHaveText('4 tétel');
			expect(await storedCart(page)).toEqual({
				lines: [
					{ ingredientId: 'alma', qty: 0.5 },
					{ ingredientId: 'tej', qty: 1 },
					{ ingredientId: 'tojas', qty: 10 },
					{ ingredientId: 'orolt_kave', qty: 0.5 }
				],
				checked: [],
				storeId: null
			});

			// The cart, grouped by shop section.
			const cart = page.getByTestId('cart');
			expect(await cart.getByTestId('cart-line').evaluateAll((els) => els.map((el) => el.getAttribute('data-ingredient-id')))).toEqual([
				'alma',
				'tej',
				'tojas',
				'orolt_kave'
			]);
			expect(await cart.locator('h3').allTextContents()).toEqual(['Zöldség, gyümölcs', 'Tejtermék, tojás', 'Száraz és tartós élelmiszer']);

			// Nothing is asked or fetched before the user chooses where to search from.
			await page.getByRole('link', { name: 'Hol a legolcsóbb?' }).click();
			await expect(page.getByRole('heading', { name: 'Hol a legolcsóbb a közelben?' })).toBeInViewport();
			await expect(page.getByTestId('location-privacy').getByRole('link', { name: 'Adatvédelem' })).toHaveAttribute(
				'href',
				'/forrasok#src-privacy'
			);
			// The privacy line comes BEFORE the button that asks the browser (BUILD-BRIEF §8.8), also for screen readers.
			expect(
				await page.evaluate(() => {
					const line = document.querySelector('[data-testid="location-privacy"]');
					const button = [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Saját helyzetem használata');
					return Boolean(line && button && line.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING);
				})
			).toBe(true);
			expect(await page.evaluate(() => window.__geoCalls?.length)).toBe(0);
			expect(rec.requests.filter((r) => r.url.includes('/api/stores') || r.url.includes('/api/quote'))).toEqual([]);
			await expectAccessible(page, `cart ${viewport.name} before location`);

			await page.getByRole('button', { name: 'Saját helyzetem használata' }).click();
			await expect(page.getByTestId('store-ranking')).toBeVisible();
			// Only the nearby stores' ids (sorted) and the cart's goods are sent.
			expect(rec.quoteBodies).toHaveLength(1);
			expect(rec.quoteBodies[0]?.store_ids).toEqual(NEARBY_IDS);
			expect(rec.quoteBodies[0]?.lines).toEqual([
				{ ingredient_id: 'alma', qty: 0.5 },
				{ ingredient_id: 'tej', qty: 1 },
				{ ingredient_id: 'tojas', qty: 10 },
				{ ingredient_id: 'orolt_kave', qty: 0.5 }
			]);

			// One store: Penny has everything for 5,280 Ft (Spar too, for 6,900 Ft; Aldi has no coffee).
			const options = page.getByTestId('shopping-options');
			await expect(options.getByRole('heading', { level: 3 })).toHaveText('Hol vásárolj?');
			await expect(page.getByTestId('options-scope')).toHaveText(
				'A sétát is beszámítva, a kiválasztott boltok közül, a 2026-10-13-i GVH-adatok alapján.'
			);
			await expect(options.getByTestId('nowhere')).toHaveCount(0);
			const single = options.getByTestId('option-single');
			await expect(single).toHaveAttribute('data-store-id', 'synthetic-penny-k');
			await expect(single).toContainText('Penny');
			await expect(single.getByTestId('single-total')).toHaveText(sp('5 280 Ft'));
			await expect(single).toContainText('Itt minden megvan.');
			await expect(single).toContainText(sp('Séta oda-vissza: 1,2 km légvonalban.'));

			// The route: Aldi (nearest) for apples, milk and eggs (950 Ft), then Penny for the coffee (3,600 Ft):
			// 4,550 Ft, 730 Ft less, for a 1.43 km round instead of 1.2 km (worth more than 500 Ft + 150 Ft/km).
			const route = options.getByTestId('option-journey');
			await expect(route.getByRole('heading', { level: 4 })).toHaveText('Körút: 2 bolt');
			await expect(route.getByTestId('journey-total')).toHaveText(sp('4 550 Ft'));
			await expect(route).toContainText(sp('730 Ft-tal olcsóbb, mint egy boltban.'));
			await expect(route.getByTestId('journey-walk')).toHaveText(sp('Séta: 1,4 km légvonalban, 230 m-rel több, mint egy boltba.'));
			const stops = route.getByTestId('journey-stops').locator(':scope > li');
			expect(await stops.evaluateAll((els) => els.map((el) => el.getAttribute('data-store-id')))).toEqual([
				'synthetic-aldi-k',
				'synthetic-penny-k'
			]);
			await expect(stops.nth(0)).toContainText(sp('200 m a kiindulási ponttól'));
			await expect(stops.nth(0)).toContainText('alma, tej, tojás');
			await expect(stops.nth(0)).toContainText(sp('950 Ft / 3 tétel'));
			await expect(stops.nth(1)).toContainText(sp('630 m az előző bolttól'));
			await expect(stops.nth(1)).toContainText('őrölt kávé');
			await expect(stops.nth(1)).toContainText(sp('3 600 Ft / 1 tétel'));
			await expect(route).toContainText(sp('Vissza a kiindulási pontig: 600 m.'));
			const map = route.getByTestId('journey-map');
			await expect(map.getByTestId('map-stop')).toHaveCount(2);
			await expect(map.getByRole('img')).toHaveAccessibleName(/^A körút vázlata: kiindulási pont → 1\. Aldi, .* → 2\. Penny, .* → kiindulási pont\.$/);
			// The map link holds only the store's own (public) position, never the user's.
			const aldi = STORE_BY_ID.get('synthetic-aldi-k')!;
			const [lat, lon] = [aldi.lat!.toFixed(5), aldi.lon!.toFixed(5)];
			await expect(stops.nth(0).getByRole('link')).toHaveAttribute('href', `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=18/${lat}/${lon}`);
			await expect(page.locator('main')).not.toContainText(/47[.,]496|19[.,]054/); // the position is never shown

			// The route's list, store by store; ticks are kept with the cart.
			const toggle = route.locator('button[aria-expanded]');
			await expect(toggle).toHaveText('Bevásárlólista boltonként');
			await expect(toggle).toHaveAttribute('aria-expanded', 'false');
			await toggle.click();
			await expect(toggle).toHaveAttribute('aria-expanded', 'true');
			await expect(toggle).toHaveText('A boltonkénti lista elrejtése');
			const lists = options.getByTestId('journey-lists');
			await expect(lists.getByTestId('store-line')).toHaveCount(4);
			await lists.getByRole('checkbox', { name: /^tojás/ }).check();
			expect(await storedCart(page)).toMatchObject({ checked: ['tojas'] });

			await expectAccessible(page, `cart ${viewport.name} options`);
			await page.screenshot({ path: screenshotPath(`cart-${viewport.name}-options`), fullPage: true });

			// The single store's list.
			await single.getByRole('button', { name: /^Lista ennél a boltnál/ }).click();
			const storeList = page.getByTestId('store-list');
			await expect(storeList.getByRole('heading', { level: 3 })).toHaveText('Lista: Penny');
			await expect(storeList.getByTestId('store-total')).toHaveText(sp('Fizetendő: 5 280 Ft'));
			expect(await storedCart(page)).toMatchObject({ storeId: 'synthetic-penny-k' });

			// A reload keeps everything on this device; the goods list starts closed for a full cart.
			await page.reload();
			await expect(page.getByTestId('cart-count')).toHaveText('4 tétel');
			await expect(page.getByTestId('browse')).not.toHaveAttribute('open', '');
			await expect(page.getByTestId('store-list').getByRole('heading', { level: 3 })).toHaveText('Lista: Penny');
			await expectClean(page, rec);
		});
	});
}

// ───────────────────────────── the other paths ─────────────────────────────

test.describe('cart details', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true, ...WITH_LOCATION });

	test('a good missing from every store: the route gets everything that is sold nearby', async ({ page }) => {
		const rec = await harness(page);
		await seed(
			page,
			cartState([
				{ ingredientId: 'banan', qty: 1 },
				{ ingredientId: 'orolt_kave', qty: 0.5 },
				{ ingredientId: 'tej', qty: 1 },
				{ ingredientId: 'kenyer', qty: 1 }
			])
		);
		await page.goto('/kosar');
		await page.getByRole('button', { name: 'Saját helyzetem használata' }).click();
		const options = page.getByTestId('shopping-options');
		// Bread has no store price nearby; bananas are only at Aldi, coffee is not at Aldi: no single store has both.
		await expect(options.getByTestId('nowhere')).toHaveText('1 tételnek egyik közeli boltban sincs ára: kenyér');
		const single = options.getByTestId('option-single');
		await expect(single).toHaveAttribute('data-store-id', 'synthetic-aldi-k');
		await expect(single.getByTestId('single-total')).toHaveText(sp('900 Ft'));
		await expect(single).toContainText('1 tétel csak máshol kapható: őrölt kávé');
		const route = options.getByTestId('option-journey');
		await expect(route.getByRole('heading', { level: 4 })).toHaveText('Körút: 2 bolt');
		await expect(route.getByTestId('journey-total')).toHaveText(sp('4 500 Ft'));
		await expect(route).toContainText('Így 1 tétellel többet kapsz meg.');
		await expect(route).toContainText('Így mindent megkapsz, ami a közelben kapható.');
		await expect(route).not.toContainText('olcsóbb');
		const stops = route.getByTestId('journey-stops').locator(':scope > li');
		await expect(stops.nth(0)).toContainText('banán, tej');
		await expect(stops.nth(1)).toContainText('őrölt kávé');
		await expectAccessible(page, 'cart coverage route');
		await expectClean(page, rec);
	});

	test('one store is best when the route saves too little', async ({ page }) => {
		const rec = await harness(page);
		// Without the eggs, Aldi saves only 100 + 80 = 180 Ft (apples, milk): less than the 500 Ft for a stop.
		await seed(
			page,
			cartState([
				{ ingredientId: 'alma', qty: 0.5 },
				{ ingredientId: 'tej', qty: 1 },
				{ ingredientId: 'orolt_kave', qty: 0.5 }
			])
		);
		await page.goto('/kosar');
		await page.getByRole('button', { name: 'Saját helyzetem használata' }).click();
		const options = page.getByTestId('shopping-options');
		await expect(options.getByTestId('option-single')).toHaveAttribute('data-store-id', 'synthetic-penny-k');
		await expect(options.getByTestId('option-single').getByTestId('single-total')).toHaveText(sp('4 330 Ft'));
		await expect(options.getByTestId('option-journey')).toHaveCount(0);
		await expect(options.getByTestId('no-journey')).toHaveText(
			sp('Most egy bolt a legjobb: több bolttal legfeljebb 180 Ft-ot spórolnál.')
		);
		await expectClean(page, rec);
	});

	test('remove, clear and undo; keyboard focus stays near the good', async ({ page }) => {
		const rec = await harness(page);
		await seed(
			page,
			cartState([
				{ ingredientId: 'alma', qty: 0.5 },
				{ ingredientId: 'tej', qty: 0.25 }
			])
		);
		await page.goto('/kosar');
		await expect(page.getByTestId('cart-count')).toHaveText('2 tétel');
		await expect(page.getByTestId('browse')).not.toHaveAttribute('open', '');
		await page.getByText('További termékek').click();
		await expect(page.getByTestId('browse')).toHaveAttribute('open', '');

		// By keyboard: "Kosárba" turns into − amount +, and the focus moves to "+".
		await page.getByRole('button', { name: 'Kosárba: banán' }).focus();
		await page.keyboard.press('Enter');
		await expect(goodRow(page, 'banan').getByRole('button', { name: 'Több: banán' })).toBeFocused();
		// … and back: − down to the smallest amount, where it turns into the bin; the focus returns to "Kosárba".
		const less = goodRow(page, 'banan').getByRole('button', { name: 'Kevesebb: banán' });
		for (let step = 0; step < 5; step++) await less.press('Enter'); // 500 -> 400 -> 300 -> 250 -> 200 -> 100 g
		const bin = goodRow(page, 'banan').getByRole('button', { name: 'Törlés a kosárból: banán' });
		await expect(bin).toBeFocused();
		await bin.press('Enter');
		await expect(page.getByRole('button', { name: 'Kosárba: banán' })).toBeFocused();

		// The bin in the cart (tej is at its smallest amount): the line goes, the focus goes to the cart's heading.
		await page.getByTestId('cart').getByRole('button', { name: 'Törlés a kosárból: tej' }).press('Enter');
		await expect(page.getByTestId('cart-count')).toHaveText('1 tétel');
		await expect(page.getByRole('heading', { level: 2, name: /A kosarad/ })).toBeFocused();

		// Clear, then undo.
		await page.getByRole('button', { name: 'Kosár ürítése' }).click();
		await expect(page.getByTestId('cart-count')).toHaveText('0 tétel');
		await expect(page.getByTestId('cart')).toContainText('Kiürítetted a kosarat.');
		await expect(page.getByRole('button', { name: 'Visszavonás' })).toBeFocused();
		expect(await storedCart(page)).toEqual({ lines: [], checked: [], storeId: null });
		await page.getByRole('button', { name: 'Visszavonás' }).click();
		await expect(page.getByTestId('cart-count')).toHaveText('1 tétel');
		expect(await storedCart(page)).toEqual({ lines: [{ ingredientId: 'alma', qty: 0.5 }], checked: [], storeId: null });
		await expectAccessible(page, 'cart after undo');
		await expectClean(page, rec);
	});

	test('goods that lost their store price leave the cart; a full cart says so', async ({ page }) => {
		const many = Array.from({ length: 100 }, (_, i) =>
			good(`aru_${String(i).padStart(3, '0')}`, `szintetikus áru ${String(i).padStart(3, '0')}`, 'db', 'egyeb')
		);
		const rec = await harness(page, many.slice(0, 99));
		// 100 lines: 99 synthetic goods still priced, one ("aru_099") no longer in the catalogue.
		await seed(page, cartState(many.map((g) => ({ ingredientId: g.id, qty: 1 }))));
		await page.goto('/kosar');
		await expect(page.getByTestId('cart-count')).toHaveText('99 tétel');
		await expect(page.getByTestId('cart-dropped')).toHaveText('1 termék kimaradt, mert már nincs bolti ára.');

		// Room for one more: the dropped good makes way.
		await page.getByText('További termékek').click();
		await page.getByRole('button', { name: 'Kosárba: alma' }).click();
		await expect(page.getByTestId('cart-count')).toHaveText('100 tétel');
		await expect(page.getByTestId('cart-dropped')).toHaveCount(0);
		const lines = ((await storedCart(page)) as { lines: { ingredientId: string }[] }).lines;
		expect(lines).toHaveLength(100);
		expect(lines.map((line) => line.ingredientId)).not.toContain('aru_099');
		expect(lines.at(-1)).toEqual({ ingredientId: 'alma', qty: 0.5 });

		// Now the cart is full.
		await page.getByRole('button', { name: 'Kosárba: tej' }).click();
		await expect(page.getByTestId('browse')).toContainText('A kosárba legfeljebb 100 termék fér.');
		await expect(page.getByTestId('cart-count')).toHaveText('100 tétel');
		await expectClean(page, rec);
	});
});

test.describe('in English', () => {
	test.use({ viewport: { width: 1280, height: 800 }, ...WITH_LOCATION });

	test('the cart and the shopping options', async ({ page }) => {
		const rec = await harness(page);
		await seed(
			page,
			cartState(
				[
					{ ingredientId: 'alma', qty: 0.5 },
					{ ingredientId: 'tej', qty: 1 },
					{ ingredientId: 'tojas', qty: 10 },
					{ ingredientId: 'orolt_kave', qty: 0.5 }
				],
				{ language: 'en' }
			)
		);
		await page.goto('/kosar');
		await expect(page.getByRole('heading', { level: 1 })).toHaveText('Cart');
		await expect(page.getByTestId('cart-count')).toHaveText('4 items');
		await expect(page.getByTestId('cart').getByRole('button', { name: 'Less: alma' })).toBeVisible();
		await page.getByRole('button', { name: 'Use my location' }).click();
		const options = page.getByTestId('shopping-options');
		await expect(options.getByRole('heading', { level: 3 })).toHaveText('Where to shop');
		await expect(options.getByTestId('option-single').getByRole('heading', { level: 4 })).toHaveText('In one store');
		await expect(options.getByTestId('option-journey').getByRole('heading', { level: 4 })).toHaveText('Route: 2 stores');
		await expect(options.getByTestId('option-journey')).toContainText(sp('730 Ft cheaper than one store.'));
		await expectAccessible(page, 'cart in English');
		await page.screenshot({ path: screenshotPath('cart-en-desktop-options'), fullPage: true });
		await expectClean(page, rec);
	});
});
