/**
 * Full-stack end-to-end test (docs/E2E.md, docs/PROGRESS.md step 8): week plan -> shopping list -> nearby stores
 * -> store totals -> recipes, and cart -> nearby stores -> one store or a route, in the production build served by
 * the REAL API, against a REAL PostgreSQL filled
 * by the REAL ingest and content loader. Nothing inside our own system is mocked: no `page.route` answers an
 * /api call here. The only stand-in is the GVH Árfigyelő itself (tests/fakegvh.py): its stores are the REAL
 * store list, its products and prices are SYNTHETIC test data (never real prices, never shipped).
 *
 * Runs once per project (390×844 phone, 1280×800 desktop) with geolocation granted at Nyugati tér. Throughout:
 * no console errors, no uncaught errors, no CSP violations, no request to another origin, and no request that
 * carries a coordinate.
 */
import { readFileSync } from 'node:fs';
import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import type {
	IngredientsResponse,
	ListRequest,
	ListResponse,
	MetaResponse,
	PlanResponse,
	QuoteRequest,
	QuoteResponse,
	RecipeDetail,
	RecipesResponse,
	StoreOut,
	StoresResponse
} from '../../src/lib/api/types';
import { BASE_URL_ENV, STORES_CSV, readState } from './stack';

/** Set by global-setup.ts once the stack is up (empty while Playwright only lists the tests). */
const BASE_URL = process.env[BASE_URL_ENV] ?? '';
const ORIGIN = BASE_URL ? new URL(BASE_URL).origin : '';
/** Nyugati tér, a BUILD-BRIEF §10 test point: what the browser reports. */
const DEVICE = { latitude: 47.5103, longitude: 19.0558 };
/** What the app keeps of it (rounded to 3 decimals, src/lib/location.ts), for the distance checks here. */
const ORIGIN_ROUNDED = { lat: 47.51, lon: 19.056 };
/** Any spelling of those coordinates (or a coordinate field) in a URL or a request body. */
const COORDINATES = /47[.,]51|19[.,]05|19[.,]06|latitude|longitude|"lat"|"lon"|\blat=|\blon=/;
const RADIUS_KM = 1.5;
const MAX_PER_CHAIN = 3;
const SLOTS_3 = ['reggeli', 'ebed', 'vacsora'] as const;
const PEOPLE = 2;
const DAYS = 7;
const DISCLAIMER = 'Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal.';
const EARTH_RADIUS_KM = 6371.0088;
/** The shop sections of a list, in the docs/DATA.md order, with their Hungarian headings. */
const LIST_GROUPS: readonly (readonly [string, string])[] = [
	['zoldseg_gyumolcs', 'Zöldség, gyümölcs'],
	['pekaru', 'Pékáru'],
	['tejtermek_tojas', 'Tejtermék, tojás'],
	['hus_hal', 'Hús, hal'],
	['szaraz_tartos', 'Száraz és tartós élelmiszer'],
	['fagyasztott', 'Fagyasztott'],
	['fuszer_olaj', 'Fűszer, olaj'],
	['egyeb', 'Egyéb']
];

test.use({ baseURL: BASE_URL || undefined, geolocation: DEVICE, permissions: ['geolocation'] });

declare global {
	interface Window {
		__cspViolations?: string[];
		__geoCalls?: (PositionOptions | null)[];
	}
}

// ───────────────────────────── helpers ─────────────────────────────

/** Text with no-break spaces made plain and whitespace collapsed (hu-HU numbers use U+00A0). */
function norm(text: string | null | undefined): string {
	return (text ?? '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();
}

/** A RegExp for `text` in which every space also matches no-break spaces (hu-HU numbers and dates use them).
 * `whole`: the element's entire text (trimmed) must match. */
function loose(text: string, whole = true): RegExp {
	const body = text
		.trim()
		.split(/\s+/)
		.map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
		.join('[\\s\\u00a0\\u202f]+');
	return new RegExp(whole ? `^\\s*${body}\\s*$` : body);
}

/** The whole-forint amount of the first "1 234 Ft" in a text. */
function forints(text: string | null | undefined): number {
	const match = norm(text).match(/(\d[\d ]*) Ft/);
	if (!match?.[1]) throw new Error(`no forint amount in ${JSON.stringify(text)}`);
	return Number(match[1].replaceAll(' ', ''));
}

/** "2026-10-13" -> "2026. 10. 13." (hu-HU). */
function dateHu(iso: string): string {
	const [year, month, day] = iso.split('-');
	return `${year}. ${month}. ${day}.`;
}

function haversineKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
	const rad = (deg: number): number => (deg * Math.PI) / 180;
	const h =
		Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lon - a.lon) / 2) ** 2;
	return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(Math.min(1, h)));
}

function distanceOf(store: StoreOut): number {
	if (store.lat === null || store.lon === null) return Number.POSITIVE_INFINITY;
	return haversineKm(ORIGIN_ROUNDED, { lat: store.lat, lon: store.lon });
}

/** The research store list (the real GVH /shops snapshot the fake serves): id -> row. Quoted fields allowed. */
function realStores(): Map<string, { chain: string; postalCode: string; lat: number; lon: number }> {
	const rows = readFileSync(STORES_CSV, 'utf-8').trim().split('\n');
	const header = parseCsvLine(rows[0] ?? '');
	const col = (name: string): number => header.indexOf(name);
	const out = new Map<string, { chain: string; postalCode: string; lat: number; lon: number }>();
	for (const row of rows.slice(1)) {
		const cells = parseCsvLine(row);
		out.set(cells[col('uuid')] ?? '', {
			chain: cells[col('chain')] ?? '',
			postalCode: cells[col('postalCode')] ?? '',
			lat: Number(cells[col('lat')]),
			lon: Number(cells[col('lon')])
		});
	}
	return out;
}

function parseCsvLine(line: string): string[] {
	const cells: string[] = [];
	let cell = '';
	let quoted = false;
	for (let i = 0; i < line.length; i += 1) {
		const ch = line[i];
		if (quoted) {
			if (ch === '"' && line[i + 1] === '"') {
				cell += '"';
				i += 1;
			} else if (ch === '"') quoted = false;
			else cell += ch;
		} else if (ch === '"') quoted = true;
		else if (ch === ',') {
			cells.push(cell);
			cell = '';
		} else cell += ch;
	}
	cells.push(cell.replace(/\r$/, ''));
	return cells;
}

interface Watch {
	consoleErrors: string[];
	pageErrors: string[];
	external: string[];
	requests: { method: string; url: string; body: string }[];
}

/** Records console errors, uncaught errors, CSP violations, geolocation calls and every request of the browser
 * context; a request to another origin is recorded and aborted (it never reaches the network). Our own requests
 * are untouched. */
async function watch(page: Page): Promise<Watch> {
	const seen: Watch = { consoleErrors: [], pageErrors: [], external: [], requests: [] };
	// "Terv készítése" asks with a random seed; pinned here (seed 0) so a failing run can be reproduced.
	await page.addInitScript(() => {
		Math.random = () => 0;
	});
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
		if (message.type() === 'error') seen.consoleErrors.push(message.text());
	});
	page.on('pageerror', (error) => seen.pageErrors.push(String(error)));
	// Context-wide, so a popup or a new tab would be covered too.
	const context = page.context();
	context.on('request', (request) => seen.requests.push({ method: request.method(), url: request.url(), body: request.postData() ?? '' }));
	await context.route(
		(url) => url.origin !== ORIGIN,
		async (route) => {
			seen.external.push(route.request().url());
			await route.abort();
		}
	);
	return seen;
}

async function expectClean(page: Page, seen: Watch, where: string): Promise<void> {
	// Soft: every kind of problem is reported, not only the first (the test still fails).
	expect.soft(seen.consoleErrors, `console errors (${where})`).toEqual([]);
	expect.soft(seen.pageErrors, `uncaught errors (${where})`).toEqual([]);
	expect.soft(await page.evaluate(() => window.__cspViolations ?? ['listener missing']), `CSP violations (${where})`).toEqual([]);
	expect.soft(seen.external, `requests to another origin (${where})`).toEqual([]);
	expect.soft(seen.requests.filter((r) => new URL(r.url).origin !== ORIGIN).map((r) => r.url), `request origins (${where})`).toEqual([]);
	expect
		.soft(seen.requests.filter((r) => COORDINATES.test(`${r.url} ${r.body}`)).map((r) => `${r.method} ${r.url} ${r.body}`), `requests carrying a coordinate (${where})`)
		.toEqual([]);
	await expect.soft(page.locator('body'), `"akció" (${where})`).not.toContainText(/akció/i);
}

/** Loads a page of the SPA (a full document load) and checks its HTML response: 200, and the CSP header carries
 * every directive of the build's meta policy plus frame-ancestors 'none', and no 'unsafe-inline'. */
async function openPage(page: Page, path: string): Promise<void> {
	const html = await page.goto(path);
	expect(html?.status(), `GET ${path}`).toBe(200);
	expect(html?.headers()['content-type'], `GET ${path}`).toMatch(/^text\/html/);
	const header = html?.headers()['content-security-policy'] ?? '';
	expect(header, `CSP header of ${path}`).toMatch(/(^|; )frame-ancestors 'none'$/);
	expect(header, `CSP header of ${path}`).toContain("default-src 'self'");
	expect(header, `CSP header of ${path}`).not.toContain('unsafe-inline');
	const metaPolicy = (await page.locator('meta[http-equiv="content-security-policy"]').getAttribute('content')) ?? '';
	const directives = metaPolicy.split(';').map(norm).filter(Boolean);
	expect(directives.length, `the build's CSP meta policy (${path})`).toBeGreaterThan(0);
	for (const directive of directives) {
		expect(header.split('; '), `the CSP header of ${path} keeps "${directive}"`).toContain(directive);
	}
}

async function getJson<T>(request: APIRequestContext, path: string): Promise<T> {
	const response = await request.get(path);
	expect(response.status(), `GET ${path}`).toBe(200);
	return (await response.json()) as T;
}

function isApiPost(path: string): (response: { url(): string; request(): { method(): string } }) => boolean {
	return (response) => response.url() === `${BASE_URL}${path}` && response.request().method() === 'POST';
}

async function rowTexts(rows: Locator): Promise<{ id: string; rank: string; total: string; text: string }[]> {
	return rows.evaluateAll((els) =>
		els.map((el) => ({
			id: el.getAttribute('data-store-id') ?? '',
			rank: el.querySelector('[data-testid="rank"]')?.textContent ?? '',
			total: el.querySelector('[data-testid="rank-total"]')?.textContent ?? '',
			text: el.textContent ?? ''
		}))
	);
}

// ───────────────────────────── the test ─────────────────────────────

test('week plan -> list -> nearby stores -> store totals -> recipes, on the real stack', async ({ page, request }) => {
	expect(BASE_URL, `${BASE_URL_ENV} (set by global-setup.ts)`).not.toBe('');
	const STATE = readState();
	expect(STATE.base_url, 'stack.json describes the stack under test').toBe(BASE_URL);
	const seen = await watch(page);
	const meta = await getJson<MetaResponse>(request, '/api/meta');
	const { recipes } = await getJson<RecipesResponse>(request, '/api/recipes');
	const titles = new Map(recipes.map((recipe) => [recipe.id, recipe.title]));
	expect(meta.data_date).toBe(STATE.data_date);
	expect(meta.disclaimer_hu).toBe(DISCLAIMER);
	const attribution = `Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), ${dateHu(STATE.data_date)}`;
	const chainName = new Map(meta.chains.map((chain) => [chain.slug, chain.name]));

	// ── f. every HTML document carries the CSP header (the meta policy plus frame-ancestors 'none') ──
	await openPage(page, '/terv');

	// ── a. /terv: a 7-day plan, 3 slots, 2 people, from the real planner ──
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Heti terv');
	const suggested = page.waitForResponse(isApiPost('/api/plan/suggest'));
	await page.getByRole('button', { name: 'Terv készítése' }).click();
	const suggestResponse = await suggested;
	expect(suggestResponse.status()).toBe(200);
	expect(suggestResponse.request().postDataJSON()).toMatchObject({ days: DAYS, slots: 3, people: PEOPLE });
	const plan = (await suggestResponse.json()) as PlanResponse;
	await expect(page.getByRole('heading', { level: 2, name: 'A terved' })).toBeFocused();
	await expect(page.getByTestId('plan-summary')).toContainText(loose(`${DAYS} nap, ${PEOPLE} fő, napi 3 étkezés`, false));
	expect(plan.days).toHaveLength(DAYS);
	await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(DAYS);
	await expect(page.locator('[data-testid^="meal-"]')).toHaveCount(DAYS * SLOTS_3.length);
	for (const day of plan.days) {
		for (const slot of SLOTS_3) {
			const recipeId = day.meals[slot];
			expect(recipeId, `day ${day.index} ${slot} is filled`).toBeTruthy();
			const title = titles.get(recipeId ?? '');
			expect(title, `recipe ${recipeId} exists`).toBeDefined();
			await expect(page.getByTestId(`meal-${day.index}-${slot}`).getByRole('link')).toHaveText(title ?? '');
		}
	}
	// The rule checks of the week, as the server computed them.
	const week0 = plan.checks.filter((check) => check.week === 0);
	expect(week0.map((check) => check.rule).sort()).toEqual(
		['fish', 'legume', 'meat_free_day', 'potato', 'red_meat', 'variety'].sort()
	);
	const checkItems = page.getByTestId('plan-week-0').getByRole('list', { name: 'A hét összesítése' }).getByRole('listitem');
	await expect(checkItems).toHaveCount(week0.length);
	for (const check of week0) {
		await expect(page.getByTestId('plan-week-0').getByTestId(`check-${check.rule}`)).toHaveAttribute('data-ok', String(check.ok));
	}
	// Recipe and plan prices are chain-typical, and the source line says so (BUILD-BRIEF §8.6).
	await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText(loose(`Lánc-jellemző árak. ${attribution}`));
	// "Források" is closed, but its line still names the source and the data date; the disclaimer is in the footer.
	await expect(page.locator('main').getByTestId('attribution-summary')).toHaveText(loose(`Források: GVH Árfigyelő, ${dateHu(STATE.data_date)}`));
	await expect(page.locator('main').getByTestId('disclaimer')).toHaveCount(0);
	await expect(page.locator('footer').getByTestId('disclaimer')).toHaveText(loose(DISCLAIMER));
	await expectClean(page, seen, '/terv');

	// ── b. /lista: the list of this plan from the real /api/list ──
	const listed = page.waitForResponse(isApiPost('/api/list'));
	await openPage(page, '/lista');
	const listResponse = await listed;
	expect(listResponse.status()).toBe(200);
	const listRequest = listResponse.request().postDataJSON() as ListRequest;
	const servings = new Map<string, number>();
	for (const day of plan.days) {
		for (const slot of SLOTS_3) {
			const recipeId = day.meals[slot];
			if (recipeId) servings.set(recipeId, (servings.get(recipeId) ?? 0) + PEOPLE);
		}
	}
	const byRecipe = (a: { recipe_id: string }, b: { recipe_id: string }): number => a.recipe_id.localeCompare(b.recipe_id);
	expect([...listRequest.items].sort(byRecipe)).toEqual(
		[...servings].map(([recipe_id, count]) => ({ recipe_id, servings: count })).sort(byRecipe)
	);
	expect(Object.keys(listRequest)).toEqual(['items']); // no on_hand, nothing personal
	const list = (await listResponse.json()) as ListResponse;
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Bevásárlólista');
	const toBuy = list.lines.filter((line) => !line.pantry);
	const pantry = list.lines.filter((line) => line.pantry);
	expect(toBuy.length).toBeGreaterThan(0);
	expect(pantry.length, 'the real recipes use pantry staples').toBeGreaterThan(0);
	await expect(page.getByText(loose(`${toBuy.length} tétel a listán`))).toBeVisible();
	const shown = await page.locator('input[data-line-check]').evaluateAll((els) => els.map((el) => el.getAttribute('data-line-check')));
	expect(shown.sort()).toEqual(toBuy.map((line) => line.ingredient_id).sort());
	await expect(page.getByRole('heading', { level: 2, name: 'Valószínűleg otthon van' })).toBeVisible();
	for (const line of pantry) {
		const notAtHome = page.getByRole('checkbox', { name: `Nincs otthon: ${line.name_hu}`, exact: true });
		// Tap water is never bought, so it has no "nincs otthon" switch.
		if (line.ingredient_id === 'viz') await expect(notAtHome).toHaveCount(0);
		else await expect(notAtHome).not.toBeChecked();
	}

	// ── c. "Hol a legolcsóbb a közelben?": the explanation first, then the device's position ──
	await expect(page.getByRole('heading', { level: 2, name: 'Hol a legolcsóbb a közelben?' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Honnan keressük a boltokat?' })).toBeVisible();
	await expect(page.getByTestId('location-privacy')).toHaveText('A helyzeted nem kerül a szerverre. Adatvédelem');
	expect(await page.evaluate(() => window.__geoCalls?.length)).toBe(0);
	expect(seen.requests.filter((r) => r.url.includes('/api/stores') || r.url.includes('/api/quote'))).toEqual([]);

	const quoted = page.waitForResponse(isApiPost('/api/quote'));
	await page.getByRole('button', { name: 'Saját helyzetem használata' }).click();
	await expect(page.getByTestId('origin')).toContainText(
		/Kiindulási pont: a helyzeted \(\d{4}\.\s\d{2}\.\s\d{2}\.\s\d{1,2}:\d{2}\)\./
	);
	const quoteResponse = await quoted;
	expect(quoteResponse.status()).toBe(200);
	const sent = quoteResponse.request().postDataJSON() as QuoteRequest;
	const quote = (await quoteResponse.json()) as QuoteResponse;
	expect(await page.evaluate(() => window.__geoCalls?.length)).toBe(1);

	// Only ids and quantities were sent: the bought lines and the store ids.
	expect(Object.keys(sent).sort()).toEqual(['include_loyalty', 'lines', 'store_ids']);
	expect(sent.include_loyalty).toBe(false);
	expect(sent.lines.map((line) => line.ingredient_id).sort()).toEqual(toBuy.map((line) => line.ingredient_id).sort());
	for (const line of sent.lines) {
		expect(line.qty).toBe(toBuy.find((l) => l.ingredient_id === line.ingredient_id)?.qty);
	}

	// The stores: real Budapest stores around Nyugati tér, chosen on the device (grocery, with data, within
	// 1.5 km, the nearest 3 per chain), checked here against the API's store list and the research CSV.
	const { stores } = await getJson<StoresResponse>(request, '/api/stores');
	const storeById = new Map(stores.map((store) => [store.id, store]));
	const grocery = new Set(meta.chains.filter((chain) => chain.is_grocery).map((chain) => chain.slug));
	const inRadius = stores.filter((store) => grocery.has(store.chain) && distanceOf(store) <= RADIUS_KM);
	const eligible = inRadius.filter((store) => store.has_data);
	const expectedIds = new Set<string>();
	for (const chain of grocery) {
		eligible
			.filter((store) => store.chain === chain)
			.sort((a, b) => distanceOf(a) - distanceOf(b))
			.slice(0, MAX_PER_CHAIN)
			.forEach((store) => expectedIds.add(store.id));
	}
	expect(expectedIds.size, 'stores near Nyugati tér').toBeGreaterThanOrEqual(5);
	expect([...sent.store_ids].sort()).toEqual([...expectedIds].sort());
	// Sorted by id: the order of the ids must not reveal the distances (and so the position).
	expect(sent.store_ids, 'sorted by id').toEqual([...sent.store_ids].sort());
	const real = realStores();
	for (const id of sent.store_ids) {
		const row = real.get(id);
		const store = storeById.get(id);
		expect(row, `${id} is in the real store list`).toBeDefined();
		expect(row?.postalCode.startsWith('1'), `${id} is in Budapest`).toBe(true);
		expect(Math.abs((row?.lat ?? 0) - (store?.lat ?? 1))).toBeLessThan(1e-6);
		expect(Math.abs((row?.lon ?? 0) - (store?.lon ?? 1))).toBeLessThan(1e-6);
	}
	const withoutData = inRadius.filter((store) => !store.has_data).length;
	await expect(page.getByTestId('candidates')).toContainText(loose(`${expectedIds.size} bolt 1,5 km távolságon belül`, false));
	if (withoutData > 0) {
		await expect(page.getByTestId('candidates')).toContainText(loose(`${withoutData} közeli boltról nincs áradat`, false));
	} else {
		await expect(page.getByTestId('candidates')).not.toContainText('nem szerepel');
	}

	// The same request to the real API gives the same answer.
	const replay = await request.post('/api/quote', { data: sent });
	expect(replay.status()).toBe(200);
	expect(await replay.json()).toEqual(quote);
	expect(quote.data_date).toBe(STATE.data_date);
	expect(quote.stores.map((store) => store.store_id).sort()).toEqual([...sent.store_ids].sort());

	// The ranking on screen is the server's: ranks, totals (whole forints) and ties.
	const ranking = page.getByTestId('store-ranking');
	const rows = ranking.getByTestId('rank-row');
	await expect(rows).toHaveCount(quote.ranking.length);
	const ui = await rowTexts(rows);
	const rankCount = new Map<number, number>();
	for (const entry of quote.ranking) rankCount.set(entry.rank, (rankCount.get(entry.rank) ?? 0) + 1);
	const whole = (value: number): number => Math.round(value);
	// Competition ranks (1, 1, 3): a rank r follows exactly r - 1 better stores; a tie group has the same missing
	// count and the same whole-forint penalized total (within the 2-decimal JSON rounding); better ranks never
	// cost more.
	for (const entry of quote.ranking) {
		expect(quote.ranking.filter((o) => o.rank < entry.rank).length, `competition rank of ${entry.store_id}`).toBe(entry.rank - 1);
		for (const other of quote.ranking) {
			if (other.rank === entry.rank) {
				expect(other.missing_count).toBe(entry.missing_count);
				expect(Math.abs(other.penalized_total - entry.penalized_total)).toBeLessThan(1);
			} else if (other.rank < entry.rank) {
				expect(other.penalized_total).toBeLessThanOrEqual(entry.penalized_total + 0.01);
			}
		}
	}
	expect(new Set(ui.map((row) => row.id))).toEqual(new Set(quote.ranking.map((entry) => entry.store_id)));
	let previous: { rank: number; distance: number } | null = null;
	for (const row of ui) {
		const entry = quote.ranking.find((r) => r.store_id === row.id);
		if (!entry) throw new Error(`row ${row.id} is not in the ranking`);
		expect(norm(row.rank)).toBe(`${entry.rank}.`);
		expect(forints(row.total), `total at ${row.id}`).toBe(whole(entry.checkout_total));
		const tied = (rankCount.get(entry.rank) ?? 0) > 1;
		expect(row.text.includes('holtverseny'), `tie label at ${row.id}`).toBe(tied);
		if (entry.missing_count > 0) expect(norm(row.text)).toContain(`${entry.missing_count} tétel hiányzik`);
		const penalty = norm(row.text).match(/A teljes lista becsült ára: (\d[\d ]*) Ft/);
		if (entry.missing_count > 0 && whole(entry.penalized_total) !== whole(entry.checkout_total)) {
			expect(Number(penalty?.[1]?.replaceAll(' ', '')), `penalized total at ${row.id}`).toBe(whole(entry.penalized_total));
		} else {
			expect(penalty, `no penalty line at ${row.id}`).toBeNull();
		}
		const distance = distanceOf(storeById.get(row.id) as StoreOut);
		if (previous) {
			expect(entry.rank, 'rank order').toBeGreaterThanOrEqual(previous.rank);
			if (entry.rank === previous.rank) expect(distance, 'a tie is ordered by distance').toBeGreaterThanOrEqual(previous.distance);
		}
		previous = { rank: entry.rank, distance };
	}
	expect([...rankCount.values()].some((count) => count > 1), 'the national-price chains tie near Nyugati tér').toBe(true);
	await expect(page.getByTestId('ranking-scope')).toHaveText(`Legolcsóbb elöl, ${quote.scope_note_hu}.`);
	expect(quote.scope_note_hu).toContain(STATE.data_date);
	await expect(page.locator('main').getByTestId('attribution-gvh').first()).toHaveText(loose(attribution));
	await expect(page.locator('main').getByTestId('disclaimer')).toHaveCount(0);
	await expect(page.locator('footer').getByTestId('disclaimer')).toHaveText(loose(DISCLAIMER));
	await expect(page.locator('body')).not.toContainText(/akció/i);

	// ── d. the cheapest store (rank 1, the nearest of a tie): its list, grouped, with packs and costs ──
	const first = ui[0];
	if (!first) throw new Error('empty ranking');
	const chosen = quote.stores.find((store) => store.store_id === first.id);
	if (!chosen) throw new Error(`no quote for ${first.id}`);
	expect(quote.ranking.find((entry) => entry.store_id === first.id)?.rank).toBe(1);
	await rows.first().getByRole('button', { name: /^Lista ennél a boltnál/ }).click();
	const storeList = page.getByTestId('store-list');
	await expect(storeList.getByRole('heading', { level: 3 })).toHaveText(`Lista: ${chainName.get(chosen.chain) ?? chosen.chain}`);
	await expect(storeList.getByRole('heading', { level: 3 })).toBeFocused();
	expect(forints(await storeList.getByTestId('store-total').textContent())).toBe(whole(chosen.checkout_total));
	await expect(storeList.getByTestId('store-total')).toContainText('Fizetendő:');
	// The total is the priced lines' checkout costs; KSH estimates are never in it.
	const priced = chosen.lines.filter((line) => line.status === 'priced');
	expect(priced.length, 'something is priced at the cheapest store').toBeGreaterThan(0);
	const sum = priced.reduce((total, line) => total + (line.checkout_cost ?? 0), 0);
	expect(Math.abs(sum - chosen.checkout_total)).toBeLessThan(0.011);
	// Grouped by shop section (docs/DATA.md order), each section in the list's order.
	const listOrder = new Map(list.lines.map((line, index) => [line.ingredient_id, index]));
	const groupOf = new Map(list.lines.map((line) => [line.ingredient_id, line.list_group]));
	const expectedGroups = LIST_GROUPS.map(([group, heading]) => ({
		heading,
		ids: chosen.lines
			.map((line) => line.ingredient_id)
			.filter((id) => groupOf.get(id) === group)
			.sort((a, b) => (listOrder.get(a) ?? 0) - (listOrder.get(b) ?? 0))
	})).filter((group) => group.ids.length > 0);
	expect(chosen.lines.every((line) => groupOf.has(line.ingredient_id)), 'every quoted line is a line of the list').toBe(true);
	expect(expectedGroups.length, 'the list spans several shop sections').toBeGreaterThan(1);
	const shownGroups = await storeList.locator('div.group').evaluateAll((sections) =>
		sections.map((section) => ({
			heading: section.querySelector('h4')?.textContent?.trim() ?? '',
			ids: [...section.querySelectorAll('[data-testid="store-line"]')].map((el) => el.getAttribute('data-ingredient-id') ?? '')
		}))
	);
	expect(shownGroups).toEqual(expectedGroups);
	await expect(storeList.getByTestId('store-line')).toHaveCount(chosen.lines.length);
	// A note every product of the store shares is said once, above the lines; otherwise on the lines that have it.
	const options = chosen.lines.filter((line) => line.status === 'priced').flatMap((line) => [...line.picks.map((pick) => pick.option), ...line.alternatives]);
	const allChain = options.length > 0 && options.every((option) => option.price_scope === 'chain');
	const allAssumed = options.length > 0 && options.every((option) => option.availability === 'assumed');
	if (allChain) await expect(storeList.getByTestId('store-notes')).toContainText('Lánc árak: ebben a boltban eltérhetnek.');
	if (allAssumed) await expect(storeList.getByTestId('store-notes')).toContainText('Nem biztos, hogy minden termék kapható itt.');
	if (!allChain && !allAssumed) await expect(storeList.getByTestId('store-notes')).toHaveCount(0);
	for (const line of chosen.lines) {
		const element = storeList.locator(`[data-testid="store-line"][data-ingredient-id="${line.ingredient_id}"]`);
		await expect(element).toHaveCount(1);
		if (line.status === 'priced') {
			expect(forints(await element.getByTestId('line-cost').textContent()), `cost of ${line.ingredient_id}`).toBe(whole(line.checkout_cost ?? NaN));
			const picks = await element.locator('ul.picks > li').evaluateAll((els) =>
				els.map((el) => ({ product: el.querySelector('.product')?.textContent ?? '', pack: el.querySelector('.pack')?.textContent ?? '', text: el.textContent ?? '' }))
			);
			expect(picks).toHaveLength(line.picks.length);
			line.picks.forEach((pick, index) => {
				const ui = picks[index];
				expect(norm(ui?.product)).toBe(norm(pick.option.product_name));
				// "1 000 Ft / 500 g", "700 Ft / 2 × 175 g": the price per amount.
				expect(forints(norm(ui?.pack).split(' / ')[0]), `pick cost of ${line.ingredient_id}`).toBe(whole(pick.cost));
				if (pick.option.pack_size !== null) expect(norm(ui?.pack)).toMatch(new RegExp(` / ${pick.count} × `));
				if (pick.option.price_scope === 'chain' && !allChain) expect(norm(ui?.text)).toContain('A lánc ára, itt eltérhet.');
				else expect(norm(ui?.text)).not.toContain('lánc ára');
				if (pick.option.availability === 'assumed' && !allAssumed) expect(norm(ui?.text)).toContain('Nem biztos, hogy itt kapható.');
				else expect(norm(ui?.text)).not.toContain('Nem biztos');
			});
		} else if (line.status === 'unavailable') {
			await expect(element).toContainText('nincs ebben a boltban');
		} else if (line.status === 'ksh_estimate' && line.ksh_estimate !== null) {
			await expect(element).toContainText('becsült országos átlagár (KSH)');
			expect(forints(await element.getByTestId('ksh-value').textContent())).toBe(whole(line.ksh_estimate));
			await expect(element.getByTestId('ksh-value')).toContainText('nincs benne a fizetendő összegben');
		} else {
			await expect(element).toContainText('nincs ár');
		}
	}
	if (chosen.ksh_estimate_total > 0) {
		expect(forints(await storeList.getByTestId('ksh-total').textContent())).toBe(whole(chosen.ksh_estimate_total));
		await expect(page.locator('main').getByTestId('attribution-ksh')).toContainText('Forrás: KSH');
	}
	// One "Források" for the whole page, at the bottom; the disclaimer once, in the footer.
	await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText([loose(attribution)]);
	await expect(page.locator('main').getByTestId('attribution-summary')).toHaveText([
		loose(`Források: GVH Árfigyelő, ${dateHu(STATE.data_date)}${chosen.ksh_estimate_total > 0 ? ', KSH' : ''}`)
	]);
	await expect(page.locator('main').getByTestId('disclaimer')).toHaveCount(0);
	await expect(page.locator('footer').getByTestId('disclaimer')).toHaveText(loose(DISCLAIMER));
	await page.screenshot({ path: test.info().outputPath('lista-store.png'), fullPage: true });
	await expectClean(page, seen, '/lista');

	// ── e. /receptek and the detail of the first planned recipe: the chain table is the server's ──
	await openPage(page, '/receptek');
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Receptek');
	await expect(page.getByTestId('recipe-card')).toHaveCount(recipes.length);
	await expect(page.getByTestId('recipe-count')).toHaveText(loose(`${recipes.length} recept`));
	await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText(loose(`Lánc-jellemző árak. ${attribution}`));
	const recipeId = plan.days[0]?.meals.ebed ?? '';
	const detailLoaded = page.waitForResponse((response) => response.url() === `${BASE_URL}/api/recipes/${encodeURIComponent(recipeId)}`);
	await page
		.getByTestId('recipe-card')
		.getByRole('link', { name: titles.get(recipeId) ?? '', exact: true })
		.click();
	const detailResponse = await detailLoaded;
	expect(detailResponse.status()).toBe(200);
	const detail = (await detailResponse.json()) as RecipeDetail;
	await expect(page.getByRole('heading', { level: 1 })).toHaveText(detail.title);
	expect(detail.tested).toBe(false);
	await expect(page.locator('.recipe .meta')).toContainText('kipróbálatlan recept');
	const table = page.getByTestId('chain-costs');
	await expect(table.locator('tbody tr')).toHaveCount(detail.chain_costs.length);
	const tableRows = await table.locator('tbody tr').evaluateAll((els) => els.map((el) => ({ id: el.getAttribute('data-testid') ?? '', head: el.querySelector('th')?.textContent ?? '', cell: el.querySelector('td')?.textContent ?? '' })));
	const recipeRanks = new Map<number, number>();
	for (const cost of detail.chain_costs) if (cost.rank !== null) recipeRanks.set(cost.rank, (recipeRanks.get(cost.rank) ?? 0) + 1);
	let lastRank = 0;
	let unrankedSeen = false;
	for (const row of tableRows) {
		const cost = detail.chain_costs.find((c) => `chain-cost-${c.chain}` === row.id);
		if (!cost) throw new Error(`table row ${row.id} is not in /api/recipes/${recipeId}`);
		const head = norm(row.head);
		expect(head).toContain(chainName.get(cost.chain) ?? cost.chain);
		if (cost.rank !== null) {
			expect(unrankedSeen, 'ranked chains come first').toBe(false);
			expect(head.startsWith(`${cost.rank}.`), `rank of ${cost.chain}`).toBe(true);
			expect(cost.rank).toBeGreaterThanOrEqual(lastRank);
			lastRank = cost.rank;
			expect(head.includes('holtverseny'), `tie label of ${cost.chain}`).toBe((recipeRanks.get(cost.rank) ?? 0) > 1);
		} else {
			unrankedSeen = true;
			expect(head).not.toMatch(/^\d+\./);
		}
		if (cost.cost_per_serving !== null) {
			expect(forints(row.cell), `cost per serving at ${cost.chain}`).toBe(whole(cost.cost_per_serving));
			expect(head.includes('részleges ár')).toBe(cost.rank === null);
		} else {
			expect(norm(row.cell)).toContain('nincs ár');
		}
	}
	await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText(
		loose(`Lánc-jellemző árak. Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), ${dateHu(detail.data_date ?? '')}`)
	);
	await expect(page.locator('main').getByTestId('disclaimer')).toHaveCount(0);
	await expect(page.locator('footer').getByTestId('disclaimer')).toHaveText(loose(DISCLAIMER));
	await page.screenshot({ path: test.info().outputPath('recipe-detail.png'), fullPage: true });

	// ── f, g. throughout: clean console, CSP, same origin only, never a coordinate ──
	await expectClean(page, seen, 'whole flow');
	const apiCalls = seen.requests.filter((r) => new URL(r.url).pathname.startsWith('/api/')).map((r) => `${r.method} ${new URL(r.url).pathname}`);
	for (const call of ['POST /api/plan/suggest', 'POST /api/list', 'GET /api/stores', 'POST /api/quote', `GET /api/recipes/${recipeId}`]) {
		expect(apiCalls, 'the flow used the real API').toContain(call);
	}

	// What this run saw (the products and prices behind it are SYNTHETIC fake-GVH data).
	const statuses = (lines: { status: string }[]): Record<string, number> =>
		lines.reduce<Record<string, number>>((acc, line) => ({ ...acc, [line.status]: (acc[line.status] ?? 0) + 1 }), {});
	const summary = {
		data_date: STATE.data_date,
		plan_recipes: servings.size,
		list: { to_buy: toBuy.length, pantry: pantry.length },
		stores: sent.store_ids.length,
		without_data_in_radius: withoutData,
		ranking: quote.ranking.map((entry) => `${entry.rank}. ${entry.store_id} ${whole(entry.checkout_total)} Ft (${entry.missing_count} missing)`),
		chosen: { store: chosen.store_id, total: whole(chosen.checkout_total), lines: statuses(chosen.lines), ksh_total: chosen.ksh_estimate_total },
		recipe: { id: detail.id, chains: detail.chain_costs.map((cost) => `${cost.chain}:${cost.rank ?? '-'}`) },
		api_calls: apiCalls.length
	};
	await test.info().attach('summary.json', { body: JSON.stringify(summary, null, 1), contentType: 'application/json' });
	console.log(`[fullstack ${test.info().project.name}] ${JSON.stringify(summary)}`);
});

// ───────────────────────────── the cart ─────────────────────────────

/** How many goods the cart test puts in the cart (spread over the catalogue). */
const CART_GOODS = 12;
/** The route rules of src/lib/journey/journey.ts (DEFAULT_JOURNEY_OPTIONS), checked independently here. */
const EXTRA_STOP_FT = 500;
const PER_KM_FT = 150;

test('cart -> nearby stores -> one store or a route, on the real stack', async ({ page, request }) => {
	expect(BASE_URL, `${BASE_URL_ENV} (set by global-setup.ts)`).not.toBe('');
	const seen = await watch(page);
	const { ingredients } = await getJson<IngredientsResponse>(request, '/api/ingredients');
	const goods = ingredients.filter((good) => good.priced_by === 'gvh' && good.id !== 'viz');
	const goodById = new Map(goods.map((good) => [good.id, good]));
	expect(goods.length, 'goods with store prices').toBeGreaterThan(CART_GOODS);

	// ── the goods: every ingredient with store prices (never tap water) ──
	await openPage(page, '/termekek');
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Termékek');
	await expect(page.getByTestId('goods-count')).toHaveText(loose(`${goods.length} termék`));
	const shownIds = await page.getByTestId('good').evaluateAll((els) => els.map((el) => el.getAttribute('data-ingredient-id') ?? ''));
	expect([...shownIds].sort()).toEqual(goods.map((good) => good.id).sort());

	// ── the cart: goods spread over the shop sections, each at its first amount ──
	const picked = Array.from({ length: CART_GOODS }, (_, i) => shownIds[Math.floor((i * shownIds.length) / CART_GOODS)] ?? '');
	expect(new Set(picked).size).toBe(CART_GOODS);
	for (const id of picked) {
		await page.locator(`[data-testid="good"][data-ingredient-id="${id}"]`).getByRole('button', { name: /^Kosárba: / }).click();
	}
	await expect(page.getByTestId('goods-cart-link')).toHaveText(loose(`Kosár: ${CART_GOODS} tétel`));
	await page.getByTestId('goods-cart-link').click();
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Kosár');
	await expect(page.getByTestId('cart-count')).toHaveText(loose(`${CART_GOODS} tétel`));
	await expect(page.getByTestId('cart-line')).toHaveCount(CART_GOODS);

	const quoted = page.waitForResponse(isApiPost('/api/quote'));
	await page.getByRole('button', { name: 'Saját helyzetem használata' }).click();
	const quoteResponse = await quoted;
	expect(quoteResponse.status()).toBe(200);
	const sent = quoteResponse.request().postDataJSON() as QuoteRequest;
	const quote = (await quoteResponse.json()) as QuoteResponse;
	// Only ids and amounts, in the cart's order; the store ids sorted (they must not reveal the distances).
	expect(Object.keys(sent).sort()).toEqual(['include_loyalty', 'lines', 'store_ids']);
	expect(sent.lines).toEqual(
		picked.map((id) => {
			const unit = goodById.get(id)?.unit;
			return { ingredient_id: id, qty: id === 'tojas' ? 10 : unit === 'kg' ? 0.5 : 1 };
		})
	);
	expect(sent.store_ids).toEqual([...sent.store_ids].sort());
	expect(sent.store_ids.length, 'stores near Nyugati tér').toBeGreaterThanOrEqual(5);

	// ── "Hol vásárolj?", checked against the quote with the rules worked out independently here ──
	const { stores } = await getJson<StoresResponse>(request, '/api/stores');
	const storeById = new Map(stores.map((store) => [store.id, store]));
	const pointOf = (id: string): { lat: number; lon: number } => {
		const store = storeById.get(id);
		if (!store || store.lat === null || store.lon === null) throw new Error(`no position for ${id}`);
		return { lat: store.lat, lon: store.lon };
	};
	/** store -> good -> checkout cost, for the priced lines only. */
	const costs = new Map(
		quote.stores.map((store) => [
			store.store_id,
			new Map(store.lines.filter((line) => line.status === 'priced' && line.checkout_cost !== null).map((line) => [line.ingredient_id, line.checkout_cost ?? 0]))
		])
	);
	const costsAt = (id: string): Map<string, number> => costs.get(id) ?? new Map<string, number>();
	const sold = new Set([...costs.values()].flatMap((byGood) => [...byGood.keys()]));
	expect(sold.size, 'something in the cart is sold nearby').toBeGreaterThan(0);
	const whole = (value: number): number => Math.round(value);
	const sum = (values: Iterable<number>): number => [...values].reduce((total, value) => total + value, 0);
	const routeKm = (ids: readonly string[]): number => {
		const points = [ORIGIN_ROUNDED, ...ids.map(pointOf), ORIGIN_ROUNDED];
		return sum(points.slice(1).map((point, index) => haversineKm(points[index] ?? point, point)));
	};

	const options = page.getByTestId('shopping-options');
	await expect(options.getByRole('heading', { level: 3 })).toHaveText('Hol vásárolj?');
	const nowhere = picked.filter((id) => !sold.has(id));
	if (nowhere.length > 0) {
		await expect(options.getByTestId('nowhere')).toContainText(loose(`${nowhere.length} tételnek egyik közeli boltban sincs ára:`, false));
		for (const id of nowhere) await expect(options.getByTestId('nowhere')).toContainText(goodById.get(id)?.name_hu ?? id);
	} else {
		await expect(options.getByTestId('nowhere')).toHaveCount(0);
	}

	// One store: the most goods first, then the total plus the walk there and back.
	const single = options.getByTestId('option-single');
	const singleId = (await single.getAttribute('data-store-id')) ?? '';
	expect(sent.store_ids).toContain(singleId);
	const singleTotal = sum(costsAt(singleId).values());
	const singleCoverage = costsAt(singleId).size;
	const singleScore = singleTotal + PER_KM_FT * routeKm([singleId]);
	expect(forints(await single.getByTestId('single-total').textContent()), 'the single store total').toBe(whole(singleTotal));
	for (const other of sent.store_ids) {
		const coverage = costsAt(other).size;
		expect(coverage, `${other} has no more goods than the single store`).toBeLessThanOrEqual(singleCoverage);
		if (coverage === singleCoverage) {
			const score = sum(costsAt(other).values()) + PER_KM_FT * routeKm([other]);
			expect(score, `${other} is no better than the single store`).toBeGreaterThanOrEqual(singleScore - 1e-6);
		}
	}
	const singleMissing = [...sold].filter((id) => !costsAt(singleId).has(id));
	if (singleMissing.length > 0) await expect(single).toContainText(loose(`${singleMissing.length} tétel csak máshol kapható:`, false));

	// The route, when there is one: every good on it is bought where it is cheapest among its stops, each stop buys
	// something, and it beats the single store (more goods, or a lower total plus walk plus stops).
	const route = options.getByTestId('option-journey');
	let routeSummary: string;
	if ((await route.count()) > 0) {
		const stopIds = await route
			.getByTestId('journey-stops')
			.locator(':scope > li')
			.evaluateAll((els) => els.map((el) => el.getAttribute('data-store-id') ?? ''));
		expect(stopIds.length).toBeGreaterThanOrEqual(2);
		expect(stopIds.length).toBeLessThanOrEqual(3);
		await route.locator('button[aria-expanded]').click();
		const lists = await options
			.getByTestId('journey-lists')
			.locator('.stop-list')
			.evaluateAll((els) => els.map((el) => [...el.querySelectorAll('[data-testid="store-line"]')].map((line) => line.getAttribute('data-ingredient-id') ?? '')));
		expect(lists).toHaveLength(stopIds.length);
		const covered = [...sold].filter((id) => stopIds.some((stop) => costsAt(stop).has(id)));
		expect(lists.flat().sort(), 'every good sold on the route is on exactly one stop').toEqual([...covered].sort());
		let total = 0;
		for (const [index, stop] of stopIds.entries()) {
			const items = lists[index] ?? [];
			expect(items.length, `stop ${index + 1} buys something`).toBeGreaterThan(0);
			for (const id of items) {
				const here = costsAt(stop).get(id);
				expect(here, `${id} is sold at ${stop}`).toBeDefined();
				for (const other of stopIds) {
					const there = costsAt(other).get(id);
					if (there !== undefined) expect(here ?? Infinity, `${id} is cheapest at ${stop}`).toBeLessThanOrEqual(there);
				}
			}
			const subtotal = sum(items.map((id) => costsAt(stop).get(id) ?? 0));
			total += subtotal;
			const stopText = norm(await route.getByTestId('journey-stops').locator(':scope > li').nth(index).textContent());
			expect(stopText).toContain(` / ${items.length} tétel`);
			expect(forints(stopText.slice(0, stopText.indexOf(` / ${items.length} tétel`)).split(', ').at(-1)), `subtotal of stop ${index + 1}`).toBe(whole(subtotal));
		}
		expect(forints(await route.getByTestId('journey-total').textContent()), 'the route total').toBe(whole(total));
		const routeScore = total + PER_KM_FT * routeKm(stopIds) + EXTRA_STOP_FT * (stopIds.length - 1);
		if (covered.length === singleCoverage) expect(routeScore, 'the route is worth its walk').toBeLessThan(singleScore);
		else expect(covered.length, 'the route gets more goods').toBeGreaterThan(singleCoverage);
		// The stops are walked in their shortest order.
		const orders = (ids: string[]): string[][] =>
			ids.length <= 1 ? [ids] : ids.flatMap((id, index) => orders([...ids.slice(0, index), ...ids.slice(index + 1)]).map((rest) => [id, ...rest]));
		for (const order of orders(stopIds)) expect(routeKm(stopIds), `shorter than ${order.join(' -> ')}`).toBeLessThanOrEqual(routeKm(order) + 1e-9);
		await expect(route.getByTestId('journey-map').getByTestId('map-stop')).toHaveCount(stopIds.length);
		routeSummary = `${stopIds.length} stops, ${whole(total)} Ft, ${covered.length} goods`;
	} else {
		routeSummary = (await options.getByTestId('no-journey').count()) > 0 ? norm(await options.getByTestId('no-journey').textContent()) : 'no route';
	}
	await expect(page.locator('main')).not.toContainText(/47[.,]51|19[.,]05/); // the position is never shown
	await page.screenshot({ path: test.info().outputPath('kosar-options.png'), fullPage: true });
	await expectClean(page, seen, '/kosar');

	const summary = {
		cart: picked.length,
		stores: sent.store_ids.length,
		nowhere: nowhere.length,
		single: `${singleId} ${whole(singleTotal)} Ft, ${singleCoverage} goods`,
		route: routeSummary
	};
	await test.info().attach('cart-summary.json', { body: JSON.stringify(summary, null, 1), contentType: 'application/json' });
	console.log(`[fullstack cart ${test.info().project.name}] ${JSON.stringify(summary)}`);
});
