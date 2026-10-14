/**
 * Recipe list and recipe detail end to end against the production build, with every /api call answered here.
 *
 * ALL DATA IN THIS FILE IS SYNTHETIC test data (recipe ids "minta-…", titles ending in "(szintetikus)",
 * every price, share and nutrition value, and the nutrition source). It is not GVH Árfigyelő, KSH or food
 * composition data and must never be shown as real. Calls this file does not answer itself fall through to
 * the synthetic mocks in tests/mocks (see its README).
 *
 * Covered at 360×740 and 1280×800 (and 320 px in English): filters (slot, tag, accent-insensitive search),
 * badges, price hints with every chain of a tie, the GVH source line with the data date, the servings
 * stepper, the tie-aware chain cost table with bars, nutrition (hidden when null), excluded ingredients,
 * "Hozzáadás a tervhez" with and without a plan, 404 and error states. Every test also asserts: no console
 * errors, no uncaught errors, no CSP violations, no request to another origin.
 */
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import type { ChainCostOut, MetaResponse, RecipeDetail, RecipeLineOut, RecipeSummary, Slot } from '../../src/lib/api/types';
import { MOCK_DATA_DATE, MOCK_META, handleMockApi, type MockResult } from '../mocks/api';
import { expectAccessible } from './a11y';
import { BASE_URL, SCREENSHOT_DIR } from './config';

const STORAGE_KEY = 'hetikosar.state';
const DATE_HU = '2026. 10. 13.';
/** A hu-HU date as the app renders it: no-break spaces, so it never wraps (src/lib/format.ts). */
const nb = (text: string): string => text.replaceAll(' ', '\u00a0');
const ATTRIBUTION = `Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), ${DATE_HU}`;
const DISCLAIMER = 'Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal.';
/** 10:00 in Budapest on Tuesday 2026-10-13. */
const NOW = new Date('2026-10-13T08:00:00Z');

// ───────────────────────────── SYNTHETIC recipes ─────────────────────────────

function summary(
	id: string,
	title: string,
	slots: Slot[],
	tags: string[],
	tested: boolean,
	cost: number | null,
	chains: string[],
	share: number
): RecipeSummary {
	return { id, title, summary: 'Szintetikus tesztrecept.', slots, servings: 4, minutes: 30, tags, tested, cost_per_serving_from: cost, cheapest_chains: chains, priced_share: share };
}

const LENCSE = summary('minta-lencse', 'Minta lencsefőzelék (szintetikus)', ['ebed', 'vacsora'], ['fozelek', 'huvelyes', 'husmentes'], false, 312.5, ['aldi', 'lidl'], 0.94);
const HARCSA = summary('minta-harcsa', 'Minta sült harcsa (szintetikus)', ['ebed', 'vacsora'], ['foetel', 'hal'], true, 655.2, ['aldi', 'lidl'], 1);
const CSIRKE = summary('minta-csirke', 'Minta csirkés tál (szintetikus)', ['ebed'], ['foetel', 'baromfi', 'gyors'], true, null, [], 0);
const TUROS = summary('minta-turos', 'Minta túrós kenyér (szintetikus)', ['reggeli', 'uzsonna'], ['reggeli_hideg', 'husmentes'], false, 180.2, ['penny'], 0.88);
const ALMA = summary('minta-alma', 'Minta almás joghurt (szintetikus)', ['tizorai'], ['snack', 'edes'], false, 150, ['lidl'], 1);
const RECIPES = [LENCSE, HARCSA, CSIRKE, TUROS, ALMA];

function line(lineNo: number, id: string, name: string, qty: number, display: string, extra: Partial<RecipeLineOut> = {}): RecipeLineOut {
	return { line_no: lineNo, ingredient_id: id, ingredient_name: name, qty, unit: 'kg', display, optional: false, pantry: false, ...extra };
}

const HARCSA_COSTS: ChainCostOut[] = [
	{ chain: 'aldi', cost_per_serving: 655.2, rank: 1, priced_share: 1, missing: [] },
	// Cheaper only because it prices half of the cost: never ranked (contract v1.2, the 90 % rule).
	{ chain: 'auchan', cost_per_serving: 400, rank: null, priced_share: 0.5, missing: ['harcsafile'] },
	{ chain: 'lidl', cost_per_serving: 655.4, rank: 1, priced_share: 1, missing: [] },
	{ chain: 'penny', cost_per_serving: 700, rank: 3, priced_share: 1, missing: [] },
	{ chain: 'spar', cost_per_serving: null, rank: null, priced_share: 0, missing: ['harcsafile'] },
	{ chain: 'tesco', cost_per_serving: 720.3, rank: 4, priced_share: 0.92, missing: ['citrom'] }
];

const DETAILS: Record<string, RecipeDetail> = {
	[HARCSA.id]: {
		...HARCSA,
		data_date: MOCK_DATA_DATE,
		steps: ['Szintetikus első lépés, csak teszteléshez.', 'Szintetikus második lépés, csak teszteléshez.'],
		lines: [
			line(1, 'harcsafile', 'harcsafilé', 0.6, '60 dkg'),
			line(2, 'burgonya', 'burgonya', 1, '1 kg'),
			line(3, 'citrom', 'citrom', 0.05, 'fél citrom leve'),
			line(4, 'voroshagyma', 'vöröshagyma', 0.1, '1 fej'),
			line(5, 'so', 'só', 0.005, 'ízlés szerint', { pantry: true }),
			line(6, 'napraforgoolaj', 'napraforgóolaj', 0.03, '2 evőkanál', { pantry: true, optional: true, unit: 'l' })
		],
		chain_costs: HARCSA_COSTS,
		// SYNTHETIC values, only to exercise the layout.
		nutrition: { kcal: 512.4, protein_g: 31.26, carb_g: 45, sugar_g: 3.2, fat_g: 20.5, satfat_g: 4.1, fiber_g: 5.6, salt_g: 1.24, coverage: 0.86 }
	},
	[LENCSE.id]: {
		...LENCSE,
		data_date: MOCK_DATA_DATE,
		steps: ['Szintetikus lépés, csak teszteléshez.'],
		lines: [line(1, 'voros_lencse', 'vörös lencse', 0.4, '40 dkg'), line(2, 'voroshagyma', 'vöröshagyma', 0.1, '1 fej')],
		chain_costs: [{ chain: 'lidl', cost_per_serving: 312.5, rank: 1, priced_share: 0.94, missing: [] }],
		nutrition: null
	},
	[ALMA.id]: {
		...ALMA,
		data_date: MOCK_DATA_DATE,
		steps: ['Szintetikus lépés, csak teszteléshez.'],
		lines: [line(1, 'alma', 'alma', 0.4, '2 db')],
		chain_costs: [],
		nutrition: null
	}
};

const META: MetaResponse = {
	...MOCK_META,
	attribution: {
		...MOCK_META.attribution,
		nutrition: { text_hu: 'Szintetikus tápérték-forrás (teszt)', text_en: 'Synthetic nutrition source (test)', url: 'https://example.org/synthetic', license: null }
	}
};

// ───────────────────────────── harness ─────────────────────────────

interface Api {
	recipeQueries: string[];
	detailRequests: string[];
	consoleErrors: string[];
	pageErrors: string[];
	external: string[];
	failDetail: number;
}

declare global {
	interface Window {
		__cspViolations?: string[];
	}
}

async function setup(page: Page, settings: Record<string, unknown> | null = null): Promise<Api> {
	const api: Api = { recipeQueries: [], detailRequests: [], consoleErrors: [], pageErrors: [], external: [], failDetail: 0 };
	await page.clock.setFixedTime(NOW);
	if (settings) {
		await page.addInitScript(
			([key, value]) => {
				if (localStorage.getItem(key) === null) localStorage.setItem(key, value);
			},
			[STORAGE_KEY, JSON.stringify({ version: 1, ...settings })] as const
		);
	}
	await page.addInitScript(() => {
		const list: string[] = [];
		window.__cspViolations = list;
		document.addEventListener('securitypolicyviolation', (event) => {
			list.push(`${event.violatedDirective} ${event.blockedURI} ${event.sourceFile}:${event.lineNumber}`);
		});
	});
	page.on('console', (message) => {
		if (message.type() === 'error') api.consoleErrors.push(message.text());
	});
	page.on('pageerror', (error) => api.pageErrors.push(String(error)));
	await page.route('**/*', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		if (url.origin !== BASE_URL) {
			api.external.push(request.url());
			await route.abort();
			return;
		}
		if (!url.pathname.startsWith('/api/')) {
			await route.continue();
			return;
		}
		const result = answer(api, request.method(), url, request.postData() ?? '');
		await route.fulfill({ status: result.status, contentType: 'application/json; charset=utf-8', body: JSON.stringify(result.body) });
	});
	return api;
}

function answer(api: Api, method: string, url: URL, body: string): MockResult {
	if (method === 'GET' && url.pathname === '/api/meta') return { status: 200, body: META };
	if (method === 'GET' && url.pathname === '/api/recipes') {
		api.recipeQueries.push(url.search);
		return { status: 200, body: { data_date: MOCK_DATA_DATE, recipes: RECIPES } };
	}
	const match = /^\/api\/recipes\/([^/]+)$/.exec(url.pathname);
	if (method === 'GET' && match) {
		const id = decodeURIComponent(match[1] ?? '');
		api.detailRequests.push(id);
		if (api.failDetail > 0) {
			api.failDetail -= 1;
			return { status: 500, body: { error: 'internal', fields: [] } };
		}
		const found = DETAILS[id];
		return found ? { status: 200, body: found } : { status: 404, body: { error: 'not_found', fields: [] } };
	}
	// This spec's own recipes, so POST /api/plan/check (on the plan page) knows them.
	return handleMockApi(method, `${url.pathname}${url.search}`, body, { recipes: RECIPES });
}

async function expectClean(page: Page, api: Api, allowConsole: RegExp | null = null): Promise<void> {
	expect(api.consoleErrors.filter((text) => !(allowConsole && allowConsole.test(text))), 'console errors').toEqual([]);
	expect(api.pageErrors, 'uncaught errors').toEqual([]);
	expect(await page.evaluate(() => window.__cspViolations ?? ['listener missing']), 'CSP violations').toEqual([]);
	expect(api.external, 'external requests').toEqual([]);
}

async function expectNoHorizontalScroll(page: Page): Promise<void> {
	const metrics = await page.evaluate(() => ({
		scrollWidth: document.documentElement.scrollWidth,
		clientWidth: document.documentElement.clientWidth
	}));
	expect(metrics.scrollWidth, 'document wider than the viewport').toBeLessThanOrEqual(metrics.clientWidth);
}

async function expectTouchTargets(page: Page): Promise<void> {
	const small = await page.evaluate(() =>
		[...document.querySelectorAll<HTMLElement>('main a, main button, main select, main input:not([type="radio"]):not([type="checkbox"]), main .btn, main label.choice')]
			.filter((el) => el.offsetParent !== null)
			.map((el) => ({ el, rect: el.getBoundingClientRect() }))
			.filter(({ rect }) => rect.width < 44 || rect.height < 44)
			.map(({ el, rect }) => `${el.tagName} "${el.textContent?.trim().slice(0, 40)}" ${rect.width}x${rect.height}`)
	);
	expect(small, 'touch targets under 44×44 px').toEqual([]);
}

function storedPlan(page: Page): Promise<Record<string, unknown> | null> {
	return page.evaluate((key) => {
		const raw = localStorage.getItem(key);
		return raw === null ? null : ((JSON.parse(raw) as { plan: Record<string, unknown> | null }).plan ?? null);
	}, STORAGE_KEY);
}

function screenshot(name: string): string {
	mkdirSync(SCREENSHOT_DIR, { recursive: true });
	return join(SCREENSHOT_DIR, `${name}.png`);
}

const card = (page: Page, title: string) => page.getByTestId('recipe-card').filter({ has: page.getByRole('heading', { name: title }) });
const cardTitles = (page: Page) => page.getByTestId('recipe-card').getByRole('heading');

// ───────────────────────────── at two sizes ─────────────────────────────

const VIEWPORTS = [
	{ name: 'phone-360', width: 360, height: 740, mobile: true },
	{ name: 'desktop-1280', width: 1280, height: 800, mobile: false }
] as const;

for (const viewport of VIEWPORTS) {
	test.describe(viewport.name, () => {
		test.use({ viewport: { width: viewport.width, height: viewport.height }, isMobile: viewport.mobile, hasTouch: viewport.mobile });

		test('the list: badges, tie-aware prices, source line and filters', async ({ page }) => {
			const api = await setup(page);
			await page.goto('/receptek');
			await expect(page.getByRole('heading', { level: 1 })).toHaveText('Receptek');
			await expect(page.getByTestId('recipe-count')).toHaveText('5 recept');
			await expect(cardTitles(page)).toHaveText(RECIPES.map((r) => r.title));

			const lencse = card(page, LENCSE.title);
			await expect(lencse.getByRole('link', { name: LENCSE.title })).toHaveAttribute('href', '/receptek/minta-lencse');
			await expect(lencse).toContainText('30 perc');
			await expect(lencse).toContainText('4 adag');
			// "kipróbálatlan recept" is on the detail page only, never on the cards (LENCSE is untested).
			await expect(lencse).not.toContainText('kipróbálatlan recept');
			await expect(lencse.getByRole('list', { name: 'Címkék' }).getByRole('listitem')).toHaveText(['főzelék', 'hüvelyes', 'húsmentes']);
			await expect(lencse.getByTestId('recipe-price')).toHaveText('313 Ft/adag-tól (Aldi, Lidl)');
			await expect(lencse).toContainText('az ár a hozzávalók 94 %\u2011át fedi le');
			await expect(card(page, HARCSA.title)).not.toContainText('kipróbálatlan recept');
			await expect(card(page, HARCSA.title)).not.toContainText('fedi le');
			await expect(card(page, CSIRKE.title)).toContainText('nincs ár');
			await expect(card(page, CSIRKE.title).getByTestId('recipe-price')).toHaveCount(0);
			await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText(ATTRIBUTION);
			await expect(page.locator('main').getByTestId('disclaimer')).toHaveText(DISCLAIMER);
			await expectNoHorizontalScroll(page);
			await expectTouchTargets(page);
			await expectAccessible(page, `recipes ${viewport.name} list`);
			await page.screenshot({ path: screenshot(`recipes-${viewport.name}-list`), fullPage: true });

			// Slot, tag and accent-insensitive search, filtered on the device.
			await page.getByLabel('Étkezés').selectOption({ label: 'Reggeli' });
			await expect(cardTitles(page)).toHaveText([TUROS.title]);
			await expect(page.getByTestId('recipe-count')).toHaveText('1 recept');
			// Only untested recipes shown: no banner about it and no badge on the cards either.
			await expect(page.locator('main')).not.toContainText('kipróbálatlan');
			await page.getByLabel('Étkezés').selectOption({ label: 'Mindegyik' });
			await expect(page.getByLabel('Címke').locator('option')).toHaveText([
				'Mindegyik', 'főzelék', 'főétel', 'hideg reggeli', 'kisétkezés', 'húsmentes', 'hal', 'hüvelyes', 'baromfi', 'édes', 'gyors'
			]);
			await page.getByLabel('Címke').selectOption({ label: 'húsmentes' });
			await expect(cardTitles(page)).toHaveText([LENCSE.title, TUROS.title]);
			await page.getByLabel('Címke').selectOption({ label: 'Mindegyik' });

			const search = page.getByLabel('Keresés a címben');
			await search.fill('FOZELEK');
			await expect(cardTitles(page)).toHaveText([LENCSE.title]);
			await search.fill('sult   harcsa');
			await expect(cardTitles(page)).toHaveText([HARCSA.title]);
			await search.fill('túrós');
			await expect(cardTitles(page)).toHaveText([TUROS.title]);
			await search.fill('m');
			await expect(page.getByTestId('recipe-count')).toHaveText('5 recept');

			await page.getByLabel('Étkezés').selectOption({ label: 'Tízórai' });
			await search.fill('lencse');
			await expect(page.getByText('Nincs a szűrőknek megfelelő recept.')).toBeVisible();
			await expect(page.getByTestId('recipe-count')).toHaveText('0 recept');
			// Both "Szűrők törlése" buttons remove themselves: focus continues at the search field.
			await page.getByRole('button', { name: 'Szűrők törlése' }).first().click();
			await expect(page.getByTestId('recipe-count')).toHaveText('5 recept');
			await expect(search).toHaveValue('');
			await expect(search).toBeFocused();
			await search.fill('nincs ilyen recept');
			await page.getByRole('button', { name: 'Szűrők törlése' }).last().click();
			await expect(page.getByTestId('recipe-count')).toHaveText('5 recept');
			await expect(search).toBeFocused();

			// The filters live in memory only: "back" from a recipe shows the same list, the URL stays clean.
			await page.getByLabel('Étkezés').selectOption({ label: 'Ebéd' });
			await search.fill('harcsa');
			await page.getByRole('link', { name: HARCSA.title }).click();
			// The list's cards are h2 too: wait for the detail page itself before going back.
			await expect(page).toHaveURL(/\/receptek\/minta-harcsa$/);
			await expect(page.getByRole('heading', { level: 1 })).toHaveText(HARCSA.title);
			await expect(page.getByTestId('chain-costs')).toBeVisible();
			await page.goBack();
			await expect(page.getByRole('heading', { level: 1 })).toHaveText('Receptek');
			await expect(cardTitles(page)).toHaveText([HARCSA.title]);
			await expect(page.getByLabel('Étkezés')).toHaveValue('ebed');
			expect(new URL(page.url()).search).toBe('');
			// One unfiltered GET per visit; the filters never reach the server.
			expect(api.recipeQueries.every((query) => query === '')).toBe(true);
			await expectClean(page, api);
		});

		test('the detail: servings, chain costs, nutrition and adding to a new plan', async ({ page }) => {
			const api = await setup(page);
			await page.goto(`/receptek/${HARCSA.id}`);
			// The recipe title is the h1, the small "Recept" label a paragraph, every section an h2.
			await expect(page.getByRole('heading', { level: 1 })).toHaveText(HARCSA.title);
			await expect(page.locator('main .intro .kind')).toHaveText('Recept');
			await expect(page).toHaveTitle(`${HARCSA.title} · Heti kosár`);
			expect(
				await page.locator('main').locator('h1, h2, h3, h4, h5, h6').evaluateAll((hs) => hs.map((h) => `${h.tagName} ${h.textContent?.trim()}`))
			).toEqual([
				`H1 ${HARCSA.title}`,
				'H2 Hozzávalók',
				'H2 Elkészítés',
				'H2 Ár láncok szerint',
				'H2 Tápérték adagonként',
				'H2 Hozzáadás a tervhez'
			]);
			await expect(page.locator('main')).not.toContainText('kipróbálatlan recept');
			await expect(page.locator('main .intro').getByTestId('recipe-price')).toHaveText('655 Ft/adag-tól (Aldi, Lidl)');

			// Ingredients at the recipe's own servings: the display texts verbatim; pantry and optional marked.
			const qty = (id: string) => page.getByTestId(`ingredient-${id}`).getByTestId('ingredient-qty');
			await expect(page.getByTestId('servings-value')).toHaveText('4 adag');
			await expect(qty('harcsafile')).toHaveText('60 dkg');
			await expect(qty('citrom')).toHaveText('fél citrom leve');
			await expect(page.getByTestId('ingredient-so')).toContainText('valószínűleg otthon van');
			await expect(page.getByTestId('ingredient-napraforgoolaj')).toContainText('(elhagyható)');
			await expect(page.getByTestId('scaled-note')).toHaveCount(0);

			// Scaled to 2 servings, then to 6.
			const fewer = page.getByRole('button', { name: 'Eggyel kevesebb adag' });
			const more = page.getByRole('button', { name: 'Eggyel több adag' });
			await fewer.click();
			await fewer.click();
			await expect(page.getByTestId('servings-value')).toHaveText('2 adag');
			await expect(qty('harcsafile')).toHaveText('30 dkg');
			await expect(qty('burgonya')).toHaveText('0,5 kg');
			await expect(qty('citrom')).toHaveText('0,25 citrom leve');
			await expect(qty('voroshagyma')).toHaveText('0,5 fej');
			await expect(qty('so')).toHaveText('ízlés szerint');
			await expect(qty('napraforgoolaj')).toHaveText('1 evőkanál');
			await expect(page.getByTestId('scaled-note')).toHaveText(
				'A mennyiségeket 2 adagra számoltuk át az eredeti, 4 adagos receptből. Kerekített, közelítő értékek.'
			);
			for (let i = 0; i < 4; i += 1) await more.click();
			await expect(page.getByTestId('servings-value')).toHaveText('6 adag');
			await expect(qty('harcsafile')).toHaveText('90 dkg');
			await expect(qty('burgonya')).toHaveText('1,5 kg');
			for (let i = 0; i < 5; i += 1) await fewer.click();
			await expect(page.getByTestId('servings-value')).toHaveText('1 adag');
			await expect(fewer).toHaveAttribute('aria-disabled', 'true');
			// aria-disabled keeps the button focusable; activating it at the bound changes nothing.
			await expect(fewer).toBeFocused();
			await page.keyboard.press('Enter');
			await expect(page.getByTestId('servings-value')).toHaveText('1 adag');
			await expect(fewer).toBeFocused();

			// Chain costs: cheapest first, the tie shares rank 1, unpriced last, coverage and missing items named.
			const table = page.getByRole('table').filter({ has: page.getByText('Lánc-jellemző ár adagonként') });
			await expect(table.locator('caption')).toHaveText('Lánc-jellemző ár adagonként, a legalacsonyabbtól a legmagasabbig');
			const rows = table.locator('tbody tr');
			await expect(rows).toHaveCount(6);
			expect(await rows.evaluateAll((trs) => trs.map((tr) => tr.getAttribute('data-testid')))).toEqual([
				'chain-cost-aldi',
				'chain-cost-lidl',
				'chain-cost-penny',
				'chain-cost-tesco',
				'chain-cost-auchan',
				'chain-cost-spar'
			]);
			await expect(rows.nth(0).getByRole('rowheader')).toHaveText('1. Aldi holtverseny');
			await expect(rows.nth(1).getByRole('rowheader')).toHaveText('1. Lidl holtverseny');
			await expect(rows.nth(2).getByRole('rowheader')).toHaveText('3. Penny');
			await expect(rows.nth(0).getByRole('cell')).toContainText('655 Ft');
			await expect(rows.nth(1).getByRole('cell')).toContainText('655 Ft');
			await expect(rows.nth(3).getByRole('cell')).toContainText('720 Ft');
			await expect(rows.nth(3).getByRole('cell')).toContainText('az ár a hozzávalók 92 %\u2011át fedi le');
			await expect(rows.nth(3).getByRole('cell')).toContainText('Ár nélkül: citrom');
			await expect(rows.nth(3).getByRole('rowheader')).toHaveText('4. Tesco');
			// The partial chain: shown with its coverage, unranked, after the ranked ones, and explained.
			await expect(rows.nth(4).getByRole('rowheader')).toHaveText('Auchan részleges ár');
			await expect(rows.nth(4).getByRole('cell')).toContainText('400 Ft');
			await expect(rows.nth(4).getByRole('cell')).toContainText('az ár a hozzávalók 50 %\u2011át fedi le');
			await expect(page.getByTestId('chain-costs-partial-note')).toContainText('A részleges árú láncok nincsenek a sorrendben');
			await expect(rows.nth(5).getByRole('rowheader')).toHaveText('Spar');
			await expect(rows.nth(5).getByRole('cell')).toContainText('nincs ár');
			await expect(rows.nth(5).getByRole('cell')).toContainText('Ár nélkül: harcsafilé');
			await expect(rows.nth(5).locator('svg')).toHaveCount(0);
			const bars = await rows.locator('rect.fill').evaluateAll((rects) => rects.map((rect) => Number(rect.getAttribute('width'))));
			expect(bars).toEqual([91, 91, 97.2, 100, 55.5]);
			await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText(ATTRIBUTION);
			await expect(page.locator('main').getByTestId('disclaimer')).toHaveText(DISCLAIMER);

			// Nutrition: factual numbers, coverage and source.
			const nutrition = page.getByTestId('nutrition');
			await expect(page.getByRole('heading', { name: 'Tápérték adagonként' })).toBeVisible();
			await expect(nutrition.getByRole('row', { name: /Energia/ })).toHaveText('Energia512 kcal');
			await expect(nutrition.getByRole('row', { name: /Fehérje/ })).toHaveText('Fehérje31,3 g');
			await expect(nutrition.getByRole('row', { name: /Só/ })).toHaveText('Só1,2 g');
			await expect(page.getByText('A hozzávalók 86 %\u2011ára van tápérték-adat; a többi nélkül számoltunk.')).toBeVisible();
			await expect(page.getByRole('link', { name: 'Szintetikus tápérték-forrás (teszt)' })).toHaveAttribute('href', 'https://example.org/synthetic');

			// Adding without a plan starts a 7-day plan from today with only this meal.
			const add = page.getByTestId('add-to-plan');
			await expect(add).toContainText('Még nincs terved.');
			await expect(add.getByLabel('Nap').locator('option')).toHaveText([
				`Kedd, ${DATE_HU}`,
				'Szerda, 2026. 10. 14.',
				'Csütörtök, 2026. 10. 15.',
				'Péntek, 2026. 10. 16.',
				'Szombat, 2026. 10. 17.',
				'Vasárnap, 2026. 10. 18.',
				'Hétfő, 2026. 10. 19.'
			]);
			await expect(add.getByLabel('Nap')).toHaveValue('0');
			await expect(add.getByLabel('Étkezés').locator('option')).toHaveText(['ebéd', 'vacsora']);
			await add.getByLabel('Nap').selectOption({ label: `Szerda, ${nb('2026. 10. 14.')}` });
			await add.getByLabel('Étkezés').selectOption({ label: 'vacsora' });
			await add.getByRole('button', { name: 'Hozzáadás a tervhez' }).click();
			await expect(add.getByRole('status')).toContainText('Hozzáadtuk a tervhez: Szerda, 2026. 10. 14., vacsora.');
			await expect(add).not.toContainText('Még nincs terved.');
			await expect(add).toContainText('Ez a recept már ebben az étkezésben van.');
			const plan = await storedPlan(page);
			expect(plan).toMatchObject({ startDate: '2026-10-13', seed: 0, slots: 3, noRepeatDays: 5 });
			const days = (plan?.days ?? []) as { index: number; meals: Record<string, string | null> }[];
			expect(days.map((d) => d.index)).toEqual([0, 1, 2, 3, 4, 5, 6]);
			expect(days.flatMap((d) => Object.values(d.meals)).filter((id) => id !== null)).toEqual([HARCSA.id]);
			expect(days[1]?.meals).toEqual({ reggeli: null, ebed: null, vacsora: HARCSA.id });

			await expectNoHorizontalScroll(page);
			await expectTouchTargets(page);
			await expectAccessible(page, `recipes ${viewport.name} detail`);
			await page.screenshot({ path: screenshot(`recipes-${viewport.name}-detail`), fullPage: true });

			await add.getByRole('link', { name: 'Terv megnyitása' }).click();
			await expect(page.getByTestId('meal-1-vacsora').getByRole('link')).toHaveText(HARCSA.title);
			expect(api.detailRequests).toEqual([HARCSA.id]);
			await expectClean(page, api);
		});
	});
}

// ───────────────────────────── more detail behaviour ─────────────────────────────

test.describe('recipe details', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('"Minden adat törlése" also forgets the recipe filters kept in memory', async ({ page }) => {
		const api = await setup(page);
		await page.goto('/receptek');
		await page.getByLabel('Címke').selectOption({ label: 'húsmentes' });
		await page.getByLabel('Keresés a címben').fill('lencse');
		await expect(cardTitles(page)).toHaveText([LENCSE.title]);
		// In-app navigation keeps the filters (a diet preference) for this tab, until everything is deleted.
		const nav = page.getByRole('navigation', { name: 'Fő navigáció' });
		await nav.getByRole('link', { name: 'Beállítások' }).click();
		await nav.getByRole('link', { name: 'Receptek' }).click();
		await expect(page.getByLabel('Címke')).toHaveValue('husmentes');
		await nav.getByRole('link', { name: 'Beállítások' }).click();
		await page.getByRole('button', { name: 'Minden adat törlése' }).click();
		await page.getByRole('dialog').getByRole('button', { name: 'Igen, mindent törlök' }).click();
		await expect(page.getByText('Minden adat törölve.')).toBeVisible();
		await nav.getByRole('link', { name: 'Receptek' }).click();
		await expect(page.getByLabel('Címke')).toHaveValue('');
		await expect(page.getByLabel('Keresés a címben')).toHaveValue('');
		await expect(cardTitles(page)).toHaveCount(RECIPES.length);
		await expectClean(page, api);
	});

	test('nutrition is hidden when null; excluded ingredients and untested recipes are marked', async ({ page }) => {
		const api = await setup(page, { exclusions: { tags: [], ingredients: ['voroshagyma'] } });
		await page.goto(`/receptek/${LENCSE.id}`);
		await expect(page.getByRole('heading', { level: 1 })).toHaveText(LENCSE.title);
		await expect(page.locator('main .intro')).toContainText('kipróbálatlan recept');
		await expect(page.getByTestId('ingredient-voroshagyma')).toContainText('a beállításokban kizártad');
		await expect(page.getByTestId('ingredient-voros_lencse')).not.toContainText('kizártad');
		await expect(page.getByRole('heading', { name: 'Tápérték adagonként' })).toHaveCount(0);
		await expect(page.getByTestId('nutrition')).toHaveCount(0);
		await expect(page.locator('main .intro')).toContainText('az ár a hozzávalók 94 %\u2011át fedi le');
		await expectClean(page, api);
	});

	test('adding to an existing plan offers only its slots that the recipe is for', async ({ page }) => {
		const meals = { reggeli: null, tizorai: 'minta-alma', ebed: null, uzsonna: null, vacsora: null };
		const api = await setup(page, {
			slots: 3,
			plan: {
				createdAt: '2026-10-12T10:00:00.000Z',
				startDate: '2026-10-12',
				seed: 3,
				slots: 5,
				noRepeatDays: 5,
				days: [
					{ index: 0, meals },
					{ index: 1, meals }
				]
			}
		});
		await page.goto(`/receptek/${ALMA.id}`);
		const add = page.getByTestId('add-to-plan');
		await expect(add.getByLabel('Nap').locator('option')).toHaveText(['Hétfő, 2026. 10. 12.', `Kedd, ${DATE_HU}`]);
		// Today is the plan's second day.
		await expect(add.getByLabel('Nap')).toHaveValue('1');
		await expect(add.getByLabel('Étkezés').locator('option')).toHaveText(['tízórai']);
		await expect(add).toContainText('Ez a recept már ebben az étkezésben van.');
		await expect(page.getByText('Ehhez a recepthez még nincs lánconkénti ár.')).toBeVisible();
		await expectClean(page, api);
	});

	test('a plan deleted in another tab is not recreated empty', async ({ page }) => {
		const meals = { reggeli: null, tizorai: null, ebed: null, uzsonna: null, vacsora: null };
		const api = await setup(page, {
			slots: 5,
			plan: { createdAt: '2026-10-12T10:00:00.000Z', startDate: '2026-10-13', seed: 0, slots: 5, noRepeatDays: 5, days: [{ index: 0, meals }] }
		});
		await page.goto(`/receptek/${ALMA.id}`);
		const add = page.getByTestId('add-to-plan');
		await expect(add.getByLabel('Étkezés').locator('option')).toHaveText(['tízórai']);
		// Another tab deletes the plan and switches to 3 meals a day.
		await page.evaluate((key) => {
			const state = JSON.parse(localStorage.getItem(key) ?? '{}') as Record<string, unknown>;
			localStorage.setItem(key, JSON.stringify({ ...state, plan: null, slots: 3 }));
		}, STORAGE_KEY);
		await add.getByRole('button', { name: 'Hozzáadás a tervhez' }).click();
		expect(await storedPlan(page)).toBeNull();
		await expect(add).toContainText('Ez a recept ezekhez az étkezésekhez való: tízórai. A tervedben nincs ilyen étkezés.');
		await expect(add.getByRole('status')).not.toContainText('Hozzáadtuk');
		await expectClean(page, api);
	});

	test('a snack recipe cannot go into a 3-meal plan', async ({ page }) => {
		const api = await setup(page);
		await page.goto(`/receptek/${ALMA.id}`);
		const add = page.getByTestId('add-to-plan');
		await expect(add).toContainText('Ez a recept ezekhez az étkezésekhez való: tízórai. A tervedben nincs ilyen étkezés.');
		await expect(add.getByRole('link', { name: 'Módosítás a beállításokban' })).toHaveAttribute('href', '/beallitasok');
		await expect(add.getByRole('button')).toHaveCount(0);
		expect(await storedPlan(page)).toBeNull();
		await expectClean(page, api);
	});

	test('an unknown recipe says so without a retry; an invalid id makes no request', async ({ page }) => {
		const api = await setup(page);
		await page.goto('/receptek/minta-nincs-ilyen');
		const alert = page.getByRole('alert');
		await expect(alert).toContainText('A recept betöltése nem sikerült');
		await expect(alert).toContainText('A keresett elem nem található.');
		await expect(alert.getByRole('button')).toHaveCount(0);
		await expect(page.getByRole('heading', { level: 1 })).toHaveText('Recept');
		await page.goto('/receptek/NEM_JO');
		await expect(page.getByRole('alert')).toContainText('A keresett elem nem található.');
		expect(api.detailRequests).toEqual(['minta-nincs-ilyen']);
		await expect(page.getByRole('link', { name: 'Vissza a receptekhez' })).toHaveAttribute('href', '/receptek');
		await expectClean(page, api, /status of 404/);
	});

	test('a server error can be retried', async ({ page }) => {
		const api = await setup(page);
		api.failDetail = 1;
		await page.goto(`/receptek/${HARCSA.id}`);
		await expect(page.getByRole('alert')).toContainText('Váratlan hiba történt.');
		// The page keeps a sensible h1 while it has no recipe to show.
		await expect(page.getByRole('heading', { level: 1 })).toHaveText('Recept');
		await page.getByRole('alert').getByRole('button', { name: 'Újra' }).click();
		await expect(page.getByRole('heading', { level: 1 })).toHaveText(HARCSA.title);
		expect(api.detailRequests).toEqual([HARCSA.id, HARCSA.id]);
		await expectClean(page, api, /status of 500/);
	});
});

test.describe('English at 320 px', () => {
	test.use({ viewport: { width: 320, height: 640 }, isMobile: true, hasTouch: true });

	test('recipe pages in English keep hu-HU prices and fit the narrowest phone', async ({ page }) => {
		const api = await setup(page, { language: 'en' });
		await page.goto('/receptek');
		await expect(page.getByRole('heading', { level: 1 })).toHaveText('Recipes');
		await expect(card(page, LENCSE.title).getByTestId('recipe-price')).toHaveText('from 313 Ft/serving (Aldi, Lidl)');
		await expect(card(page, LENCSE.title)).toContainText('the price covers 94% of the ingredients');
		await expect(card(page, CSIRKE.title)).toContainText('no price');
		await expect(card(page, TUROS.title)).not.toContainText('untested recipe');
		const langOf = (locator: ReturnType<Page['locator']>) => locator.evaluate((el) => el.closest('[lang]')?.getAttribute('lang'));
		// Hungarian content inside the English page is marked as Hungarian (WCAG 3.1.2), the UI as English.
		expect(await langOf(page.getByRole('link', { name: LENCSE.title }))).toBe('hu');
		expect(await langOf(page.getByRole('heading', { level: 1 }))).toBe('en');
		await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText(`Source: GVH Árfigyelő (arfigyelo.gvh.hu), ${DATE_HU}`);
		await expectNoHorizontalScroll(page);
		await expectTouchTargets(page);
		await expectAccessible(page, 'recipes en 320 list');

		await page.goto(`/receptek/${HARCSA.id}`);
		await expect(page.getByRole('heading', { level: 1 })).toHaveText(HARCSA.title);
		await expect(page.locator('main .intro .kind')).toHaveText('Recipe');
		expect(await langOf(page.getByRole('heading', { level: 1 }))).toBe('hu');
		expect(await langOf(page.locator('main .intro .kind'))).toBe('en');
		const steps = page.locator('ol.steps li');
		expect(await steps.count()).toBeGreaterThan(0);
		expect(await steps.evaluateAll((items) => items.map((li) => li.closest('[lang]')?.getAttribute('lang')))).toEqual(
			Array.from({ length: await steps.count() }, () => 'hu')
		);
		const quantities = page.getByTestId('ingredient-qty');
		expect(await quantities.evaluateAll((items) => items.map((el) => el.closest('[lang]')?.getAttribute('lang')))).toEqual(
			Array.from({ length: await quantities.count() }, () => 'hu')
		);
		expect(await langOf(page.locator('ul.ingredients .name').first())).toBe('hu');
		expect(await langOf(page.getByRole('heading', { level: 2, name: 'Method' }))).toBe('en');
		await expect(page.getByTestId('chain-cost-auchan').getByRole('rowheader')).toHaveText('Auchan partial price');
		await expect(page.getByRole('table').first().locator('caption')).toHaveText('Chain-typical price per serving, from lowest to highest');
		await expect(page.getByTestId('chain-cost-aldi').getByRole('rowheader')).toHaveText('1. Aldi tie');
		await expect(page.getByTestId('chain-cost-tesco')).toContainText('the price covers 92% of the ingredients');
		await expect(page.getByTestId('add-to-plan').getByLabel('Day').locator('option').first()).toHaveText(`Tuesday, ${DATE_HU}`);
		await page.getByRole('button', { name: 'One serving fewer' }).click();
		await expect(page.getByTestId('scaled-note')).toHaveText(
			'Quantities are scaled to 3 servings from the original 4-serving recipe. They are rounded, approximate values.'
		);
		await expectNoHorizontalScroll(page);
		await expectTouchTargets(page);
		await expectAccessible(page, 'recipes en 320 detail');
		await page.screenshot({ path: screenshot('recipes-en-phone-320-detail'), fullPage: true });
		await expectClean(page, api);
	});
});
