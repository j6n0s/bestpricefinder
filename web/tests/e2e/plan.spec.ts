/**
 * Weekly plan ("Heti terv") end to end against the production build, with every /api call answered here.
 *
 * ALL DATA IN THIS FILE IS SYNTHETIC test data (recipe ids "minta-…", titles ending in "(szintetikus)",
 * every price and every rule result). It is not GVH Árfigyelő or KSH data and must never be shown as real.
 * Calls this file does not answer itself fall through to the synthetic mocks in tests/mocks (see its README).
 *
 * Covered at 360×740 and 1280×800: make a plan -> change a meal -> the weekly checks update -> open the
 * recipe -> add it to the plan; plus "Új javaslat" (next seed) with undo, delete with undo, the month length,
 * reload from storage, excluded tags, API errors, English, keyboard use, and that no request carries personal
 * data beyond the plan fields. Every test also asserts: no console errors, no uncaught errors, no CSP
 * violations, no request to another origin.
 */
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import type {
	PlanCheckRequest,
	PlanDayIO,
	PlanResponse,
	PlanSuggestRequest,
	RecipeDetail,
	RecipeSummary,
	RuleCheckOut,
	Slot
} from '../../src/lib/api/types';
import { MOCK_DATA_DATE, handleMockApi, type MockResult } from '../mocks/api';
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
	return {
		id,
		title,
		summary: 'Szintetikus tesztrecept.',
		slots,
		servings: 4,
		minutes: 30,
		tags,
		tested,
		cost_per_serving_from: cost,
		cheapest_chains: chains,
		priced_share: share
	};
}

const LENCSE = summary('minta-lencse', 'Minta lencsefőzelék (szintetikus)', ['ebed', 'vacsora'], ['fozelek', 'huvelyes', 'husmentes'], false, 312.5, ['aldi', 'lidl'], 0.94);
const HARCSA = summary('minta-harcsa', 'Minta sült harcsa (szintetikus)', ['ebed', 'vacsora'], ['foetel', 'hal'], true, 655.4, ['lidl'], 1);
const CSIRKE = summary('minta-csirke', 'Minta csirkés tál (szintetikus)', ['ebed'], ['foetel', 'baromfi', 'gyors'], true, null, [], 0);
const TUROS = summary('minta-turos', 'Minta túrós kenyér (szintetikus)', ['reggeli', 'uzsonna'], ['reggeli_hideg', 'husmentes'], false, 180.2, ['penny'], 0.88);
const RAKOTT = summary('minta-rakott', 'Minta rakott krumpli (szintetikus)', ['vacsora'], ['foetel', 'sertes'], false, 410, ['aldi'], 0.97);
const RECIPES = [LENCSE, HARCSA, CSIRKE, TUROS, RAKOTT];
const BY_ID = new Map(RECIPES.map((r) => [r.id, r]));

function detail(recipe: RecipeSummary): RecipeDetail {
	return {
		...recipe,
		data_date: MOCK_DATA_DATE,
		steps: ['Szintetikus lépés, csak teszteléshez.'],
		lines: [
			{ line_no: 1, ingredient_id: 'voroshagyma', ingredient_name: 'vöröshagyma', qty: 0.1, unit: 'kg', display: '1 fej', optional: false, pantry: false }
		],
		chain_costs: [
			{
				chain: 'lidl',
				cost_per_serving: recipe.cost_per_serving_from,
				rank: recipe.cost_per_serving_from === null ? null : 1,
				priced_share: recipe.priced_share,
				missing: []
			}
		],
		nutrition: null
	};
}

// ───────────────────────────── SYNTHETIC planner ─────────────────────────────

const SLOTS_3: Slot[] = ['reggeli', 'ebed', 'vacsora'];
const SLOTS_5: Slot[] = ['reggeli', 'tizorai', 'ebed', 'uzsonna', 'vacsora'];

/** Never suggests the fish recipe, so the fish rule fails until the user picks it. */
function suggestDays(request: PlanSuggestRequest): PlanDayIO[] {
	const slots = request.slots === 5 ? SLOTS_5 : SLOTS_3;
	const seed = request.seed ?? 0;
	const excluded = request.exclude_tags ?? [];
	return Array.from({ length: request.days ?? 7 }, (_, index) => {
		const meals: PlanDayIO['meals'] = {};
		slots.forEach((slot) => {
			const pool = RECIPES.filter(
				(r) => r.id !== HARCSA.id && r.slots.includes(slot) && !r.tags.some((tag) => (excluded as string[]).includes(tag))
			);
			meals[slot] = pool.length === 0 ? null : (pool[(index + seed + (slot === 'vacsora' ? 1 : 0)) % pool.length]?.id ?? null);
		});
		return { index, meals };
	});
}

/** Rule results in the server's exact string format (server/bpf/planner/rules.py). */
function computeChecks(days: PlanDayIO[], noRepeatDays: number): RuleCheckOut[] {
	const weeks = new Map<number, PlanDayIO[]>();
	for (const day of days) weeks.set(Math.floor(day.index / 7), [...(weeks.get(Math.floor(day.index / 7)) ?? []), day]);
	const checks: RuleCheckOut[] = [];
	for (const [week, weekDays] of [...weeks].sort((a, b) => a[0] - b[0])) {
		const meals = weekDays.flatMap((d) => Object.values(d.meals).filter((id): id is string => typeof id === 'string'));
		const tagged = (tag: string): number => meals.filter((id) => BY_ID.get(id)?.tags.includes(tag)).length;
		const freeDays = weekDays.filter((d) => {
			const ids = Object.values(d.meals).filter((id): id is string => typeof id === 'string');
			return ids.length > 0 && ids.every((id) => BY_ID.get(id)?.tags.includes('husmentes'));
		}).length;
		const applies = weekDays.length >= 4;
		const count = (rule: 'fish' | 'legume' | 'meat_free_day', n: number, noun: string): RuleCheckOut =>
			applies
				? { week, rule, ok: n >= 1, value: `${n} ${noun}`, limit: '≥ 1' }
				: { week, rule, ok: true, value: 'n/a', limit: '≥ 1' };
		const red = 150 * meals.filter((id) => id === RAKOTT.id).length;
		const cap = Math.floor((600 * weekDays.length) / 7);
		let run = 0;
		let maxRun = 0;
		for (const day of [...weekDays].sort((a, b) => a.index - b.index)) {
			run = Object.values(day.meals).includes(RAKOTT.id) ? run + 1 : 0;
			maxRun = Math.max(maxRun, run);
		}
		checks.push(
			count('fish', tagged('hal'), 'hal'),
			count('legume', tagged('huvelyes'), 'hüvelyes'),
			count('meat_free_day', freeDays, 'húsmentes nap'),
			{ week, rule: 'red_meat', ok: red <= cap, value: `${red} g/fő`, limit: `≤ ${cap} g/fő` },
			{ week, rule: 'potato', ok: maxRun <= 1, value: `${maxRun} nap egymás után`, limit: '≤ 1 nap egymás után' },
			{ week, rule: 'sweets', ok: true, value: '0 édes', limit: '≤ 2' },
			{ week, rule: 'variety', ok: true, value: '0 ismétlés', limit: `0 ismétlés ${noRepeatDays} napon belül` }
		);
	}
	return checks;
}

// ───────────────────────────── harness ─────────────────────────────

interface Api {
	suggests: PlanSuggestRequest[];
	checks: PlanCheckRequest[];
	requests: { url: string; body: string }[];
	consoleErrors: string[];
	pageErrors: string[];
	external: string[];
	/** Make the next POST /api/plan/suggest answer with this status. */
	failSuggest: number | null;
}

declare global {
	interface Window {
		__cspViolations?: string[];
	}
}

async function setup(page: Page, override?: (method: string, path: string) => MockResult | null): Promise<Api> {
	const api: Api = { suggests: [], checks: [], requests: [], consoleErrors: [], pageErrors: [], external: [], failSuggest: null };
	await page.clock.setFixedTime(NOW);
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
	page.on('request', (request) => api.requests.push({ url: request.url(), body: request.postData() ?? '' }));
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
		const method = request.method();
		const path = url.pathname;
		const result = override?.(method, path) ?? answer(api, method, path, url, request.postData() ?? '');
		await route.fulfill({ status: result.status, contentType: 'application/json; charset=utf-8', body: JSON.stringify(result.body) });
	});
	return api;
}

function answer(api: Api, method: string, path: string, url: URL, body: string): MockResult {
	if (method === 'GET' && path === '/api/recipes') return { status: 200, body: { data_date: MOCK_DATA_DATE, recipes: RECIPES } };
	const recipeMatch = /^\/api\/recipes\/([^/]+)$/.exec(path);
	if (method === 'GET' && recipeMatch) {
		const recipe = BY_ID.get(decodeURIComponent(recipeMatch[1] ?? ''));
		return recipe ? { status: 200, body: detail(recipe) } : { status: 404, body: { error: 'not_found', fields: [] } };
	}
	if (method === 'POST' && path === '/api/plan/suggest') {
		const request = JSON.parse(body) as PlanSuggestRequest;
		api.suggests.push(request);
		if (api.failSuggest !== null) {
			const status = api.failSuggest;
			api.failSuggest = null;
			return { status, body: { error: 'internal', fields: [] } };
		}
		const days = suggestDays(request);
		const response: PlanResponse = {
			days,
			checks: computeChecks(days, request.no_repeat_days ?? 5),
			warnings: ['slot_pool_too_small:reggeli', 'no_fish_recipe_available', 'slot_pool_too_small:reggeli']
		};
		return { status: 200, body: response };
	}
	if (method === 'POST' && path === '/api/plan/check') {
		const request = JSON.parse(body) as PlanCheckRequest;
		api.checks.push(request);
		return { status: 200, body: { checks: computeChecks(request.days, request.no_repeat_days ?? 5) } };
	}
	return handleMockApi(method, `${url.pathname}${url.search}`, body);
}

async function expectClean(page: Page, api: Api, allowConsole: RegExp | null = null): Promise<void> {
	expect(api.consoleErrors.filter((text) => !(allowConsole && allowConsole.test(text))), 'console errors').toEqual([]);
	expect(api.pageErrors, 'uncaught errors').toEqual([]);
	expect(await page.evaluate(() => window.__cspViolations ?? ['listener missing']), 'CSP violations').toEqual([]);
	expect(api.external, 'external requests').toEqual([]);
	for (const request of api.requests) {
		expect(`${request.url} ${request.body}`, 'no location in any request').not.toMatch(/latitude|longitude|"lat"|"lon"|lat=|lon=/);
	}
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
		[...document.querySelectorAll<HTMLElement>('main a, main button, main select, main input:not([type="radio"]):not([type="checkbox"]), main .btn, main label.choice, main summary, dialog button, dialog input')]
			.filter((el) => el.offsetParent !== null || el.closest('dialog[open]') !== null)
			.map((el) => ({ el, rect: el.getBoundingClientRect() }))
			.filter(({ rect }) => rect.width > 0 && (rect.width < 44 || rect.height < 44))
			.map(({ el, rect }) => `${el.tagName} "${el.textContent?.trim().slice(0, 40)}" ${rect.width}x${rect.height}`)
	);
	expect(small, 'touch targets under 44×44 px').toEqual([]);
}

function storedPlan(page: Page): Promise<{ seed: number; startDate: string; slots: number; noRepeatDays: number; days: PlanDayIO[] } | null> {
	return page.evaluate((key) => {
		const raw = localStorage.getItem(key);
		return raw === null ? null : ((JSON.parse(raw) as { plan: never }).plan ?? null);
	}, STORAGE_KEY);
}

function screenshot(name: string): string {
	mkdirSync(SCREENSHOT_DIR, { recursive: true });
	return join(SCREENSHOT_DIR, `${name}.png`);
}

const week0 = (page: Page) => page.getByTestId('plan-week-0');
const chip = (page: Page, rule: string, week = 0) => page.getByTestId(`plan-week-${week}`).getByTestId(`check-${rule}`);

async function makeWeekPlan(page: Page): Promise<void> {
	await page.goto('/terv');
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Heti terv');
	await expect(page.getByTestId('plan-start-chosen')).toHaveText(`Kedd, ${DATE_HU}`);
	await page.getByRole('button', { name: 'Terv készítése' }).click();
	await expect(page.getByRole('heading', { level: 2, name: 'A terved' })).toBeFocused();
}

// ───────────────────────────── the main flow, at two sizes ─────────────────────────────

const VIEWPORTS = [
	{ name: 'phone-360', width: 360, height: 740, mobile: true },
	{ name: 'desktop-1280', width: 1280, height: 800, mobile: false }
] as const;

for (const viewport of VIEWPORTS) {
	test.describe(viewport.name, () => {
		test.use({ viewport: { width: viewport.width, height: viewport.height }, isMobile: viewport.mobile, hasTouch: viewport.mobile });

		test('make a plan -> change a meal -> checks update -> open the recipe -> add it to the plan', async ({ page }) => {
			const api = await setup(page);
			await makeWeekPlan(page);

			// The suggestion request carries the household settings and nothing personal beyond them.
			expect(api.suggests).toEqual([
				{
					days: 7,
					slots: 3,
					people: 2,
					seed: 0,
					exclude_tags: [],
					exclude_ingredients: [],
					red_meat_g_per_person_week: 600,
					no_repeat_days: 5
				}
			]);
			await expect(page.getByTestId('plan-summary')).toContainText(`${DATE_HU} – 2026. 10. 19., 7 nap · 2 fő · napi 3 étkezés`);
			await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(7);
			await expect(page.getByTestId('plan-day-0').getByRole('heading')).toHaveText(`Kedd, ${DATE_HU}`);
			await expect(page.getByTestId('plan-day-6').getByRole('heading')).toHaveText('Hétfő, 2026. 10. 19.');

			// Warnings as sentences, each once.
			const warnings = page.getByTestId('plan-warnings');
			await expect(warnings.getByRole('listitem')).toHaveText([
				'Ehhez az étkezéshez kevés a választható recept, ezért ismétlődhetnek: reggeli.',
				'Nincs választható halas recept.'
			]);

			// Neutral factual chips from the suggestion's checks.
			await expect(chip(page, 'fish')).toContainText('Hal: 0 (cél: legalább 1)');
			await expect(chip(page, 'fish')).toHaveAttribute('data-ok', 'false');
			await expect(chip(page, 'legume')).toContainText('Hüvelyes: 7 (cél: legalább 1)');
			await expect(chip(page, 'red_meat')).toContainText('Vörös hús: 600 g/fő (cél: legfeljebb 600 g/fő)');
			await expect(chip(page, 'variety')).toContainText('Változatosság: 0 ismétlés (cél: 0 ismétlés 5 napon belül)');
			await expect(week0(page).getByRole('list', { name: 'A hét összesítése' }).getByRole('listitem')).toHaveCount(7);

			// Meals link to their recipes, with the chain-typical price hint and the untested badge.
			const day0Dinner = page.getByTestId('meal-0-vacsora');
			await expect(day0Dinner.getByRole('link')).toHaveText(RAKOTT.title);
			await expect(day0Dinner).toContainText('≈ 410 Ft/adag-tól (Aldi)');
			await expect(day0Dinner).toContainText('kipróbálatlan recept');
			await expect(page.getByTestId('meal-1-ebed')).toContainText('nincs ár');
			await expect(page.getByTestId('meal-0-ebed')).toContainText('≈ 313 Ft/adag-tól (Aldi, Lidl)');
			// priced_share < 1 always comes with a caveat (contract v1.2), short in the plan cards.
			await expect(page.getByTestId('meal-0-ebed').getByTestId('recipe-coverage')).toHaveText('részleges ár (94 %)');
			await expect(day0Dinner.getByTestId('recipe-coverage')).toHaveText('részleges ár (97 %)');
			// Every view with prices: the GVH source line with the data date, and the disclaimer near it.
			await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText(ATTRIBUTION);
			await expect(page.locator('main').getByTestId('disclaimer')).toHaveText(DISCLAIMER);

			const stored = await storedPlan(page);
			expect(stored).toMatchObject({ startDate: '2026-10-13', seed: 0, slots: 3, noRepeatDays: 5 });
			expect(stored?.days[0]).toEqual({ index: 0, meals: { reggeli: TUROS.id, ebed: LENCSE.id, vacsora: RAKOTT.id } });
			await expectNoHorizontalScroll(page);
			await expectTouchTargets(page);
			await expectAccessible(page, `plan ${viewport.name} made`);
			await page.screenshot({ path: screenshot(`plan-${viewport.name}-made`), fullPage: true });

			// Change Tuesday's dinner to the fish recipe through the picker (accent-insensitive search).
			const change = page.getByRole('button', { name: `Csere (Kedd, ${DATE_HU}, vacsora)` });
			await change.click();
			const dialog = page.getByRole('dialog', { name: 'Étel választása' });
			await expect(dialog).toBeVisible();
			await expect(dialog.getByLabel('Keresés a receptek címében')).toBeFocused();
			await expect(dialog).toContainText(`Kedd, ${DATE_HU}, vacsora`);
			await expect(dialog.getByRole('status')).toHaveText('3 választható recept');
			await expect(dialog.getByRole('button', { name: /Minta rakott krumpli/ })).toHaveAttribute('aria-current', 'true');
			await expect(dialog.getByTestId('attribution-gvh')).toHaveText(ATTRIBUTION);
			await expectTouchTargets(page);
			await expectAccessible(page, `plan ${viewport.name} picker`);
			await expectNoHorizontalScroll(page);
			await page.screenshot({ path: screenshot(`plan-${viewport.name}-picker`) });
			await dialog.getByLabel('Keresés a receptek címében').fill('SULT harcsa');
			await expect(dialog.getByRole('status')).toHaveText('1 választható recept');
			const checksBefore = api.checks.length;
			await dialog.getByRole('button', { name: /Minta sült harcsa/ }).click();
			await expect(dialog).toBeHidden();
			await expect(change).toBeFocused();
			await expect(day0Dinner.getByRole('link')).toHaveText(HARCSA.title);
			// Fully priced (priced_share 1): no caveat.
			await expect(day0Dinner.getByTestId('recipe-coverage')).toHaveCount(0);

			// The edit is re-checked with the plan's variety window; the chip updates.
			await expect(chip(page, 'fish')).toContainText('Hal: 1 (cél: legalább 1)');
			await expect(chip(page, 'fish')).toHaveAttribute('data-ok', 'true');
			await expect(chip(page, 'red_meat')).toContainText('Vörös hús: 450 g/fő (cél: legfeljebb 600 g/fő)');
			expect(api.checks.length).toBe(checksBefore + 1);
			expect(api.checks.at(-1)).toMatchObject({ people: 2, red_meat_g_per_person_week: 600, no_repeat_days: 5 });
			expect(api.checks.at(-1)?.days[0]).toEqual({ index: 0, meals: { reggeli: TUROS.id, ebed: LENCSE.id, vacsora: HARCSA.id } });
			expect((await storedPlan(page))?.days[0]?.meals.vacsora).toBe(HARCSA.id);

			// Remove a meal: the slot is empty, the change button keeps focus and the plan is re-checked.
			await page.getByRole('button', { name: `Törlés (Szerda, 2026. 10. 14., ebéd)` }).click();
			await expect(page.getByTestId('meal-1-ebed')).toContainText('Nincs étel');
			const choose = page.getByRole('button', { name: 'Választás (Szerda, 2026. 10. 14., ebéd)' });
			await expect(choose).toBeFocused();
			await expect.poll(() => api.checks.at(-1)?.days[1]?.meals.ebed).toBeNull();

			// Open the recipe and add it to Thursday's lunch.
			await day0Dinner.getByRole('link', { name: HARCSA.title }).click();
			await expect(page).toHaveURL(/\/receptek\/minta-harcsa$/);
			await expect(page.getByRole('heading', { level: 1 })).toHaveText(HARCSA.title);
			const add = page.getByTestId('add-to-plan');
			await add.getByLabel('Nap').selectOption({ label: `Csütörtök, ${nb('2026. 10. 15.')}` });
			await add.getByLabel('Étkezés').selectOption({ label: 'ebéd' });
			await expect(add.getByLabel('Étkezés').locator('option')).toHaveText(['ebéd', 'vacsora']);
			await expect(add).toContainText('Ebben az étkezésben már van egy recept, a hozzáadás lecseréli.');
			await add.getByRole('button', { name: 'Hozzáadás a tervhez' }).click();
			await expect(add.getByRole('status')).toContainText('Hozzáadtuk a tervhez: Csütörtök, 2026. 10. 15., ebéd.');
			expect((await storedPlan(page))?.days[2]?.meals.ebed).toBe(HARCSA.id);
			await expectNoHorizontalScroll(page);
			await page.screenshot({ path: screenshot(`plan-${viewport.name}-added`), fullPage: true });

			// Back on the plan: the meal is there and the stored plan is re-checked on load.
			const checksBeforeOpen = api.checks.length;
			await add.getByRole('link', { name: 'Terv megnyitása' }).click();
			await expect(page.getByTestId('meal-2-ebed').getByRole('link')).toHaveText(HARCSA.title);
			await expect(chip(page, 'fish')).toContainText('Hal: 2 (cél: legalább 1)');
			expect(api.checks.length).toBe(checksBeforeOpen + 1);
			await expectClean(page, api);
		});
	});
}

// ───────────────────────────── more plan behaviour ─────────────────────────────

test.describe('plan details', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('"Új javaslat" asks with the next seed and can be undone', async ({ page }) => {
		const api = await setup(page);
		await makeWeekPlan(page);
		await expect(page.getByTestId('meal-0-ebed').getByRole('link')).toHaveText(LENCSE.title);

		await page.getByRole('button', { name: 'Új javaslat' }).click();
		await expect(page.getByTestId('meal-0-ebed').getByRole('link')).toHaveText(CSIRKE.title);
		expect(api.suggests.map((s) => s.seed)).toEqual([0, 1]);
		expect(api.suggests[1]).toMatchObject({ days: 7, slots: 3, people: 2 });
		expect(await storedPlan(page)).toMatchObject({ seed: 1, startDate: '2026-10-13' });
		await expect(page.getByRole('status').filter({ hasText: 'Elkészült az új terv.' })).toBeVisible();

		await page.getByRole('button', { name: 'Visszavonás' }).click();
		await expect(page.getByText('Visszaállítottuk az előző tervet.')).toBeVisible();
		await expect(page.getByTestId('meal-0-ebed').getByRole('link')).toHaveText(LENCSE.title);
		expect(await storedPlan(page)).toMatchObject({ seed: 0 });
		await expect(page.getByRole('heading', { level: 2, name: 'A terved' })).toBeFocused();
		await expectClean(page, api);
	});

	test('deleting the plan can be undone, and the plan survives a reload', async ({ page }) => {
		const api = await setup(page);
		await makeWeekPlan(page);
		await page.getByRole('button', { name: 'Terv törlése' }).click();
		await expect(page.getByText('A tervet töröltük.')).toBeVisible();
		await expect(page.getByRole('button', { name: 'Visszavonás' })).toBeFocused();
		expect(await storedPlan(page)).toBeNull();
		await expect(page.getByRole('heading', { level: 2, name: 'Új terv' })).toBeVisible();

		await page.getByRole('button', { name: 'Visszavonás' }).click();
		await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(7);
		expect(await storedPlan(page)).toMatchObject({ seed: 0 });

		const checks = api.checks.length;
		await page.reload();
		await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(7);
		await expect(chip(page, 'fish')).toContainText('Hal: 0 (cél: legalább 1)');
		await expect.poll(() => api.checks.length).toBeGreaterThan(checks);
		expect(api.suggests).toHaveLength(1);
		await expectClean(page, api);
	});

	test('plans up to the end of the month, week by week', async ({ page }) => {
		const api = await setup(page);
		await page.goto('/terv');
		await page.getByLabel('A hónap végéig (19 nap)').check();
		await page.getByRole('button', { name: 'Terv készítése' }).click();
		await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(19);
		expect(api.suggests[0]).toMatchObject({ days: 19 });
		await expect(page.getByRole('heading', { level: 3, name: /^3\. hét/ })).toContainText('2026. 10. 27. – 2026. 10. 31.');
		await expect(page.getByTestId('plan-day-18').getByRole('heading')).toHaveText('Szombat, 2026. 10. 31.');
		await expect(chip(page, 'fish', 2)).toContainText('Hal: 0 (cél: legalább 1)');
		await expect(chip(page, 'red_meat', 2)).toContainText('(cél: legfeljebb 428 g/fő)');

		// A start date late in the month: a 3-day plan, whose count rules are not assessed.
		await page.getByText('Más kezdőnap vagy időtartam').click();
		await page.getByLabel('Kezdőnap').fill('2026-10-29');
		await expect(page.getByTestId('plan-start-chosen')).toHaveText('Csütörtök, 2026. 10. 29.');
		await page.getByLabel('A hónap végéig (3 nap)').check();
		await page.getByRole('button', { name: 'Terv készítése' }).click();
		await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(3);
		expect(api.suggests[1]).toMatchObject({ days: 3, seed: 0 });
		await expect(chip(page, 'fish')).toContainText('Hal: nem értékeljük, mert ez a hét 4 napnál rövidebb');
		expect(await storedPlan(page)).toMatchObject({ startDate: '2026-10-29' });
		await expect(page.getByTestId('plan-summary')).toContainText('2026. 10. 29. – 2026. 10. 31., 3 nap');

		// The last day of the month: a one-day plan shows one date, not a range (the form is still open).
		await page.getByLabel('Kezdőnap').fill('2026-10-31');
		await page.getByLabel('A hónap végéig (1 nap)').check();
		await page.getByRole('button', { name: 'Terv készítése' }).click();
		await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(1);
		await expect(page.getByTestId('plan-summary')).toContainText('2026. 10. 31., 1 nap · 2 fő');
		await expect(page.getByRole('heading', { level: 3, name: /^1\. hét/ })).toHaveText('1. hét 2026. 10. 31.');
		await expectNoHorizontalScroll(page);
		await expectClean(page, api);
	});

	test('an invalid start date blocks the request', async ({ page }) => {
		const api = await setup(page);
		await page.goto('/terv');
		await page.getByLabel('Kezdőnap').fill('');
		await expect(page.getByText('Adj meg egy érvényes dátumot.')).toBeVisible();
		await expect(page.getByRole('button', { name: 'Terv készítése' })).toBeDisabled();
		expect(api.suggests).toEqual([]);
		await expectClean(page, api);
	});

	test('excluded tags from the settings go into the request and the picker', async ({ page }) => {
		await page.addInitScript((key) => {
			if (localStorage.getItem(key) === null) {
				localStorage.setItem(key, JSON.stringify({ version: 1, people: 3, slots: 5, exclusions: { tags: ['hal'], ingredients: ['gomba'] } }));
			}
		}, STORAGE_KEY);
		const api = await setup(page);
		await page.goto('/terv');
		await expect(page.getByTestId('plan-form')).toContainText('3 fő, napi 5 étkezés, 2 kizárt címke vagy alapanyag.');
		await page.getByRole('button', { name: 'Terv készítése' }).click();
		await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(7);
		expect(api.suggests[0]).toMatchObject({ slots: 5, people: 3, exclude_tags: ['hal'], exclude_ingredients: ['gomba'] });
		await expect(page.getByTestId('meal-0-tizorai')).toContainText('Nincs étel');

		await page.getByRole('button', { name: `Csere (Kedd, ${DATE_HU}, vacsora)` }).click();
		const dialog = page.getByRole('dialog', { name: 'Étel választása' });
		await expect(dialog.getByText('A beállításokban kizárt címkéjű recepteket nem mutatjuk.')).toBeVisible();
		await expect(dialog.getByText('A kizárt alapanyagokat a kézi választásnál nem szűrjük', { exact: false })).toBeVisible();
		await expect(dialog.getByRole('button', { name: /Minta sült harcsa/ })).toHaveCount(0);
		await dialog.getByLabel('Keresés a receptek címében').fill('harcsa');
		await expect(dialog.getByText('Nincs a keresésnek megfelelő recept ehhez az étkezéshez.')).toBeVisible();

		// Escape closes the picker without a change and returns focus.
		const checks = api.checks.length;
		await page.keyboard.press('Escape');
		await expect(dialog).toBeHidden();
		await expect(page.getByRole('button', { name: `Csere (Kedd, ${DATE_HU}, vacsora)` })).toBeFocused();
		expect(api.checks.length).toBe(checks);
		await expectClean(page, api);
	});

	test('the picker works with the keyboard alone', async ({ page }) => {
		const api = await setup(page);
		await makeWeekPlan(page);
		const choose = page.getByRole('button', { name: `Csere (Kedd, ${DATE_HU}, ebéd)` });
		await choose.focus();
		await page.keyboard.press('Enter');
		const dialog = page.getByRole('dialog', { name: 'Étel választása' });
		await expect(dialog.getByLabel('Keresés a receptek címében')).toBeFocused();
		// Escape closes the picker without a change, and focus goes back to the button that opened it.
		await page.keyboard.type('xy');
		await page.keyboard.press('Escape');
		await expect(dialog).toBeHidden();
		await expect(choose).toBeFocused();
		await expect(page.getByTestId('meal-0-ebed').getByRole('link')).toHaveText(LENCSE.title);
		await page.keyboard.press('Enter');
		await expect(dialog.getByLabel('Keresés a receptek címében')).toBeFocused();
		await expect(dialog.getByLabel('Keresés a receptek címében')).toHaveValue('');
		await page.keyboard.type('csirke');
		await expect(dialog.getByRole('status')).toHaveText('1 választható recept');
		await page.keyboard.press('Tab');
		await expect(dialog.getByRole('button', { name: /Minta csirkés tál/ })).toBeFocused();
		const outline = await dialog.getByRole('button', { name: /Minta csirkés tál/ }).evaluate((el) => getComputedStyle(el).outlineStyle);
		expect(outline).not.toBe('none');
		await page.keyboard.press('Enter');
		await expect(dialog).toBeHidden();
		await expect(choose).toBeFocused();
		await expect(page.getByTestId('meal-0-ebed').getByRole('link')).toHaveText(CSIRKE.title);
		await expectClean(page, api);
	});

	test('a failed suggestion shows an error with a working retry', async ({ page }) => {
		const api = await setup(page);
		api.failSuggest = 500;
		await page.goto('/terv');
		await page.getByRole('button', { name: 'Terv készítése' }).click();
		const alert = page.getByRole('alert');
		await expect(alert).toContainText('A terv elkészítése nem sikerült');
		expect(await storedPlan(page)).toBeNull();
		await alert.getByRole('button', { name: 'Újra' }).click();
		await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(7);
		await expect(page.getByRole('alert')).toHaveCount(0);
		expect(api.suggests).toHaveLength(2);
		await expectClean(page, api, /status of 500/);
	});

	test('a failed check is reported and can be retried', async ({ page }) => {
		let failCheck = false;
		const api = await setup(page, (method, path) =>
			failCheck && method === 'POST' && path === '/api/plan/check' ? { status: 503, body: { error: 'no_data', fields: [] } } : null
		);
		await makeWeekPlan(page);
		failCheck = true;
		await page.getByRole('button', { name: `Törlés (Kedd, ${DATE_HU}, ebéd)` }).click();
		await expect(page.getByRole('alert')).toContainText('A terv ellenőrzése most nem sikerült.');
		await expect(page.getByRole('alert')).toContainText('A szerveren még nincs áradat.');
		failCheck = false;
		await page.getByRole('alert').getByRole('button', { name: 'Újra' }).click();
		await expect(page.getByRole('alert')).toHaveCount(0);
		await expect(chip(page, 'legume')).toContainText('Hüvelyes: 6 (cél: legalább 1)');
		await expectClean(page, api, /status of 503/);
	});

	test('a stored recipe that no longer exists is flagged and sent as empty', async ({ page }) => {
		await page.addInitScript((key) => {
			if (localStorage.getItem(key) !== null) return;
			const meals = (ebed: string | null) => ({ reggeli: null, ebed, vacsora: null });
			localStorage.setItem(
				key,
				JSON.stringify({
					version: 1,
					plan: {
						createdAt: '2026-10-12T10:00:00.000Z',
						startDate: '2026-10-13',
						seed: 0,
						slots: 3,
						noRepeatDays: 4,
						days: [
							{ index: 0, meals: meals('minta-torolt') },
							{ index: 1, meals: meals('minta-lencse') }
						]
					}
				})
			);
		}, STORAGE_KEY);
		const api = await setup(page);
		await page.goto('/terv');
		await expect(page.getByText('A tervben 1 olyan recept van, amely már nem érhető el. Cseréld le vagy töröld.')).toBeVisible();
		await expect(page.getByTestId('meal-0-ebed')).toContainText('Ez a recept már nem érhető el.');
		await expect.poll(() => api.checks.length).toBe(1);
		expect(api.checks[0]).toEqual({
			days: [
				{ index: 0, meals: { reggeli: null, ebed: null, vacsora: null } },
				{ index: 1, meals: { reggeli: null, ebed: 'minta-lencse', vacsora: null } }
			],
			people: 2,
			red_meat_g_per_person_week: 600,
			no_repeat_days: 4
		});
		await expect(chip(page, 'fish')).toContainText('Hal: nem értékeljük, mert ez a hét 4 napnál rövidebb');
		await expectClean(page, api);
	});

	test('says so when the browser refuses to store the plan', async ({ page }) => {
		await page.addInitScript(() => {
			Storage.prototype.setItem = () => {
				throw new DOMException('quota', 'QuotaExceededError');
			};
		});
		const api = await setup(page);
		await makeWeekPlan(page);
		await expect(page.getByText('A böngésző nem engedi az adatok mentését', { exact: false })).toBeVisible();
		await expect(page.locator('[data-testid^="plan-day-"]')).toHaveCount(7);
		await expectClean(page, api);
	});
});

test.describe('English and dark mode', () => {
	test.use({ viewport: { width: 320, height: 640 }, isMobile: true, hasTouch: true, colorScheme: 'dark' });

	test('the plan in English at 320 px keeps hu-HU dates and prices', async ({ page }) => {
		const api = await setup(page);
		await page.goto('/terv');
		await page.getByRole('button', { name: 'English' }).click();
		await expect(page.getByRole('heading', { level: 1 })).toHaveText('Weekly plan');
		await expect(page.getByTestId('plan-start-chosen')).toHaveText(`Tuesday, ${DATE_HU}`);
		await page.getByRole('button', { name: 'Make a plan' }).click();
		await expect(chip(page, 'fish')).toContainText('Fish: 0 (target: at least 1)');
		await expect(chip(page, 'potato')).toContainText('Potato: 1 day in a row (target: at most 1)');
		await expect(page.getByTestId('meal-0-ebed')).toContainText('from ≈ 313 Ft/serving (Aldi, Lidl)');
		await expect(page.getByTestId('plan-warnings')).toContainText('There are few recipes to choose for this meal, so some may repeat: breakfast.');
		await expect(page.getByRole('button', { name: `Change (Tuesday, ${DATE_HU}, dinner)` })).toBeVisible();
		await expect(page.locator('main').getByTestId('attribution-gvh')).toHaveText(`Source: GVH Árfigyelő (arfigyelo.gvh.hu), ${DATE_HU}`);
		await expectNoHorizontalScroll(page);
		await expectTouchTargets(page);
		await expectAccessible(page, 'plan en dark 320');
		await page.screenshot({ path: screenshot('plan-en-dark-phone-320'), fullPage: true });
		await expectClean(page, api);
	});
});
