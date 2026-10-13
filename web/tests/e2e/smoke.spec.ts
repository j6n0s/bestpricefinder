/**
 * Smoke test of the production build (all /api routes answered by the SYNTHETIC mocks in tests/mocks).
 * Every route at 320×640, 360×740 and 1280×800: no console errors, no uncaught errors, no CSP violations,
 * no external requests, no horizontal scroll; screenshots go to E2E_SCREENSHOT_DIR.
 * Plus: the legal texts, language switch, settings persistence, "minden adat törlése", the location consent
 * flow (and that no request ever carries coordinates), keyboard access, touch target sizes, dark mode,
 * reduced motion, API error states and offline use through the service worker.
 */
import { mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';
import { MOCK_META, handleMockApi, type MockResult } from '../mocks/api';
import { BASE_URL, SCREENSHOT_DIR } from './config';
import { startStaticServer } from './static-server';

const DISCLAIMER = 'Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal.';
const DATE_HU = '2026. 10. 13.';
const ATTRIBUTION = `Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), ${DATE_HU}`;
const STORAGE_KEY = 'hetikosar.state';
const BUILD_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../build');

const ROUTES = [
	{ path: '/', heading: 'Heti étrend, bevásárlólista, közeli árak', nav: 'Kezdőlap' },
	{ path: '/terv', heading: 'Heti terv', nav: 'Heti terv' },
	{ path: '/receptek', heading: 'Receptek', nav: 'Receptek' },
	{ path: '/receptek/minta-lencsefozelek', heading: 'Recept', nav: 'Receptek' },
	{ path: '/lista', heading: 'Bevásárlólista', nav: 'Lista' },
	{ path: '/beallitasok', heading: 'Beállítások', nav: 'Beállítások' },
	{ path: '/forrasok', heading: 'Források és adatvédelem', nav: null }
] as const;

const VIEWPORTS = [
	{ name: 'phone-320', width: 320, height: 640, mobile: true },
	{ name: 'phone-360', width: 360, height: 740, mobile: true },
	{ name: 'desktop-1280', width: 1280, height: 800, mobile: false }
] as const;

type ApiResponder = (method: string, url: string, body: string) => MockResult | Promise<MockResult>;

interface Watcher {
	consoleErrors: string[];
	pageErrors: string[];
	external: string[];
	requests: { url: string; body: string }[];
	cspViolations: () => Promise<string[]>;
}

declare global {
	interface Window {
		__cspViolations?: string[];
		__geoCalls?: (PositionOptions | null)[];
	}
}

/** Routes /api to the mocks (or `api`), aborts and records any external request, and records errors. */
async function watch(page: Page, api: ApiResponder = handleMockApi): Promise<Watcher> {
	const watcher: Watcher = {
		consoleErrors: [],
		pageErrors: [],
		external: [],
		requests: [],
		cspViolations: () => page.evaluate(() => window.__cspViolations ?? ['listener missing'])
	};
	await page.addInitScript(() => {
		const list: string[] = [];
		window.__cspViolations = list;
		document.addEventListener('securitypolicyviolation', (event) => {
			list.push(`${event.violatedDirective} ${event.blockedURI} ${event.sourceFile}:${event.lineNumber}`);
		});
	});
	page.on('console', (message) => {
		if (message.type() === 'error') watcher.consoleErrors.push(message.text());
	});
	page.on('pageerror', (error) => watcher.pageErrors.push(String(error)));
	page.on('request', (request) => watcher.requests.push({ url: request.url(), body: request.postData() ?? '' }));
	await page.route('**/*', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		if (url.origin !== BASE_URL) {
			watcher.external.push(request.url());
			await route.abort();
			return;
		}
		if (url.pathname.startsWith('/api/')) {
			const result = await api(request.method(), `${url.pathname}${url.search}`, request.postData() ?? '');
			await route.fulfill({
				status: result.status,
				contentType: 'application/json; charset=utf-8',
				body: JSON.stringify(result.body)
			});
			return;
		}
		await route.continue();
	});
	return watcher;
}

async function expectClean(watcher: Watcher, allowConsole: RegExp | null = null): Promise<void> {
	const consoleErrors = watcher.consoleErrors.filter((text) => !(allowConsole && allowConsole.test(text)));
	expect(consoleErrors, 'console errors').toEqual([]);
	expect(watcher.pageErrors, 'uncaught errors').toEqual([]);
	expect(await watcher.cspViolations(), 'CSP violations').toEqual([]);
	expect(watcher.external, 'external requests').toEqual([]);
}

/** Tab labels may wrap between words but must never overflow (which is how a word that does not fit shows). */
async function expectNavLabelsFit(page: Page): Promise<void> {
	const overflowing = await page
		.getByRole('navigation', { name: /Fő navigáció|Main navigation/ })
		.locator('.label')
		.evaluateAll((labels) =>
			labels.filter((label) => label.scrollWidth > label.clientWidth + 0.5).map((label) => label.textContent)
		);
	expect(overflowing, 'nav labels that do not fit').toEqual([]);
}

async function expectNoHorizontalScroll(page: Page): Promise<void> {
	const metrics = await page.evaluate(() => {
		window.scrollTo(10_000, window.scrollY);
		const scrolledX = window.scrollX;
		window.scrollTo(0, window.scrollY);
		return {
			scrollWidth: document.documentElement.scrollWidth,
			clientWidth: document.documentElement.clientWidth,
			scrolledX
		};
	});
	expect(metrics.scrollWidth, 'document wider than the viewport').toBeLessThanOrEqual(metrics.clientWidth);
	expect(metrics.scrolledX, 'page scrolls horizontally').toBe(0);
}

function screenshotPath(name: string): string {
	mkdirSync(SCREENSHOT_DIR, { recursive: true });
	return join(SCREENSHOT_DIR, `${name}.png`);
}

function storedState(page: Page): Promise<Record<string, unknown> | null> {
	return page.evaluate((key) => {
		const raw = localStorage.getItem(key);
		return raw === null ? null : (JSON.parse(raw) as Record<string, unknown>);
	}, STORAGE_KEY);
}

const slug = (path: string): string => (path === '/' ? 'home' : path.slice(1).replaceAll('/', '_'));

// ───────────────────────────── every route at every width ─────────────────────────────

for (const viewport of VIEWPORTS) {
	test.describe(`${viewport.name}`, () => {
		test.use({
			viewport: { width: viewport.width, height: viewport.height },
			isMobile: viewport.mobile,
			hasTouch: viewport.mobile
		});

		for (const route of ROUTES) {
			test(`loads ${route.path}`, async ({ page }) => {
				const watcher = await watch(page);
				await page.goto(route.path);
				await expect(page.getByRole('heading', { level: 1 })).toHaveText(route.heading);
				await expect(page.getByTestId('data-status')).toContainText(`Adatok: ${DATE_HU}`);
				await expect(page.locator('footer').getByTestId('disclaimer')).toHaveText(DISCLAIMER);
				const nav = page.getByRole('navigation', { name: 'Fő navigáció' });
				await expect(nav).toBeVisible();
				if (route.nav) {
					await expect(nav.getByRole('link', { name: route.nav })).toHaveAttribute('aria-current', 'page');
				} else {
					await expect(nav.locator('[aria-current="page"]')).toHaveCount(0);
				}
				await expect(page).toHaveTitle(/Heti kosár/);
				await expectNavLabelsFit(page);
				await expectNoHorizontalScroll(page);
				await page.screenshot({ path: screenshotPath(`${viewport.name}-${slug(route.path)}`), fullPage: true });
				await expectClean(watcher);
			});
		}
	});
}

test.describe('narrowest phone in English', () => {
	test.use({ viewport: { width: 320, height: 640 }, isMobile: true, hasTouch: true });

	test('every page fits at 320 px in English too', async ({ page }) => {
		const watcher = await watch(page);
		await page.goto('/');
		await page.getByRole('button', { name: 'English' }).click();
		for (const route of ROUTES) {
			await page.goto(route.path);
			await expect(page.getByTestId('data-status')).toContainText(`Data: ${DATE_HU}`);
			await expectNavLabelsFit(page);
			await expectNoHorizontalScroll(page);
			await page.screenshot({ path: screenshotPath(`en-phone-320-${slug(route.path)}`), fullPage: true });
		}
		await expectClean(watcher);
	});
});

// ───────────────────────────── security and legal ─────────────────────────────

test('the HTML carries a strict hash-based CSP and no inline handlers or styles', async ({ page, request }) => {
	const response = await request.get('/');
	const html = await response.text();
	const meta = /<meta http-equiv="content-security-policy" content="([^"]+)"/.exec(html)?.[1] ?? '';
	expect(meta).toContain("default-src 'self'");
	expect(meta).toMatch(/script-src 'self' 'sha256-[A-Za-z0-9+/=]+'/);
	expect(meta).toContain("style-src 'self'");
	expect(meta).toContain("object-src 'none'");
	expect(meta).not.toContain('unsafe-inline');
	expect(meta).not.toContain('unsafe-eval');
	expect(html).not.toMatch(/\son[a-z]+=/i);
	expect(html).not.toMatch(/\sstyle=/i);

	const watcher = await watch(page);
	for (const route of ROUTES) {
		await page.goto(route.path);
		await expect(page.getByRole('heading', { level: 1 })).toHaveText(route.heading);
		const inlineHandlers = await page.evaluate(() =>
			[...document.querySelectorAll('*')].flatMap((el) =>
				[...el.attributes].filter((attr) => /^on/i.test(attr.name)).map((attr) => `${el.tagName}[${attr.name}]`)
			)
		);
		expect(inlineHandlers, route.path).toEqual([]);
		const images = await page.locator('img').count();
		expect(images, `${route.path}: no product images or logos`).toBe(0);
	}
	await expectClean(watcher);
});

test('the sources page shows the GVH attribution with the data date, KSH licence and the disclaimer', async ({ page }) => {
	const watcher = await watch(page);
	await page.goto('/forrasok');
	await expect(page.getByTestId('attribution-gvh')).toHaveText(ATTRIBUTION);
	await expect(page.getByRole('link', { name: 'Forrás: KSH, 2026. 09.' })).toHaveAttribute(
		'href',
		'https://www.ksh.hu/stadat_files/ara/hu/ara0044.html'
	);
	await expect(page.getByRole('link', { name: 'CC BY 4.0 licenc' })).toBeVisible();
	await expect(page.getByText('A helyzetedet, a címedet vagy bármilyen személyes azonosítót soha nem küldjük el.', { exact: false })).toBeVisible();
	await expect(page.getByText('Nem használunk sütiket, analitikát vagy követőkódot', { exact: false })).toBeVisible();
	await expect(page.getByTestId('disclaimer')).toHaveCount(2);
	const cookies = await page.context().cookies();
	expect(cookies).toEqual([]);
	await expectClean(watcher);
});

// ───────────────────────────── language ─────────────────────────────

test('switches to English and back, persisting the choice', async ({ page }) => {
	const watcher = await watch(page);
	await page.goto('/');
	await expect(page.locator('html')).toHaveAttribute('lang', 'hu');
	await page.getByRole('button', { name: 'English' }).click();
	await expect(page.locator('html')).toHaveAttribute('lang', 'en');
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Weekly meals, shopping list, nearby prices');
	await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Settings' })).toBeVisible();
	await expect(page.getByTestId('data-status')).toContainText(`Data: ${DATE_HU}`);
	// The Hungarian disclaimer stays verbatim, followed by its translation.
	const disclaimer = page.locator('footer').getByTestId('disclaimer');
	await expect(disclaimer).toContainText(DISCLAIMER);
	await expect(disclaimer).toContainText('Unofficial app, not affiliated with the Hungarian Competition Authority (GVH).');

	await page.reload();
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Weekly meals, shopping list, nearby prices');
	expect(await storedState(page)).toMatchObject({ language: 'en' });

	await page.goto('/forrasok');
	await expect(page.getByTestId('attribution-gvh')).toHaveText(`Source: GVH Árfigyelő (arfigyelo.gvh.hu), ${DATE_HU}`);

	await page.getByRole('button', { name: 'Magyar' }).click();
	await expect(page.locator('html')).toHaveAttribute('lang', 'hu');
	await expect(page.getByRole('heading', { level: 1 })).toHaveText('Források és adatvédelem');
	await expectClean(watcher);
});

// ───────────────────────────── settings ─────────────────────────────

test.describe('settings', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('saves household, slots, radius, language and district on the device', async ({ page }) => {
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		await expect(page.getByTestId('people-value')).toHaveText('2 fő');
		await page.getByRole('button', { name: 'Eggyel több fő' }).click();
		await page.getByRole('button', { name: 'Eggyel több fő' }).click();
		await expect(page.getByTestId('people-value')).toHaveText('4 fő');
		await page.getByLabel('5 étkezés: reggeli, tízórai, ebéd, uzsonna, vacsora').check();

		const radius = page.getByLabel('Keresési sugár');
		await expect(radius).toHaveValue('1.5');
		await radius.focus();
		await page.keyboard.press('ArrowRight');
		await expect(radius).toHaveValue('2');
		await expect(radius).toHaveAttribute('aria-valuetext', '2,0 km');

		await page.getByLabel('Budapesti kerület').selectOption({ label: 'XI. kerület' });
		await expect(page.getByTestId('location-source')).toContainText('XI. kerület');

		expect(await storedState(page)).toMatchObject({
			version: 1,
			people: 4,
			slots: 5,
			radiusKm: 2,
			location: { consent: 'unset', source: 'district', districtId: '11', approx: null }
		});

		await page.reload();
		await expect(page.getByTestId('people-value')).toHaveText('4 fő');
		await expect(page.getByLabel('5 étkezés: reggeli, tízórai, ebéd, uzsonna, vacsora')).toBeChecked();
		await expect(page.getByLabel('Keresési sugár')).toHaveValue('2');
		await expect(page.getByLabel('Budapesti kerület')).toHaveValue('11');
		await expectClean(watcher);
	});

	test('people stay within 1–12', async ({ page }) => {
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		const fewer = page.getByRole('button', { name: 'Eggyel kevesebb fő' });
		await fewer.click();
		await expect(page.getByTestId('people-value')).toHaveText('1 fő');
		await expect(fewer).toHaveAttribute('aria-disabled', 'true');
		// aria-disabled (not disabled) keeps the button focusable; activating it changes nothing.
		await expect(fewer).toBeFocused();
		await page.keyboard.press('Enter');
		await page.keyboard.press('Space');
		await expect(page.getByTestId('people-value')).toHaveText('1 fő');
		await expect(fewer).toBeFocused();
		const more = page.getByRole('button', { name: 'Eggyel több fő' });
		for (let i = 0; i < 11; i += 1) await more.click();
		await expect(page.getByTestId('people-value')).toHaveText('12 fő');
		await expect(more).toHaveAttribute('aria-disabled', 'true');
		await expect(more).toBeFocused();
		await page.keyboard.press('Enter');
		await expect(page.getByTestId('people-value')).toHaveText('12 fő');
		expect(await storedState(page)).toMatchObject({ people: 12 });
		await expectClean(watcher);
	});

	test('"Minden adat törlése" asks first, then deletes everything', async ({ page }) => {
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		await page.getByRole('button', { name: 'Eggyel több fő' }).click();
		await page.getByLabel('Budapesti kerület').selectOption('05');
		await page.getByRole('button', { name: 'English' }).click();
		await expect(page.getByRole('heading', { level: 1 })).toHaveText('Settings');

		await page.getByRole('button', { name: 'Delete all data' }).click();
		const dialog = page.getByRole('dialog', { name: 'Delete all data?' });
		await expect(dialog).toBeVisible();
		await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
		await dialog.getByRole('button', { name: 'Cancel' }).click();
		await expect(dialog).toBeHidden();
		expect(await storedState(page)).toMatchObject({ people: 3, language: 'en' });

		await page.getByRole('button', { name: 'Delete all data' }).click();
		await page.keyboard.press('Escape');
		await expect(dialog).toBeHidden();
		expect(await storedState(page)).toMatchObject({ people: 3 });

		await page.getByRole('button', { name: 'Delete all data' }).click();
		await dialog.getByRole('button', { name: 'Yes, delete everything' }).click();
		await expect(page.getByText('Minden adat törölve.')).toBeVisible();
		await expect(page.getByRole('heading', { level: 1 })).toHaveText('Beállítások');
		await expect(page.getByTestId('people-value')).toHaveText('2 fő');
		await expect(page.getByLabel('Budapesti kerület')).toHaveValue('');
		expect(await storedState(page)).toBeNull();
		const keys = await page.evaluate(() => Object.keys(localStorage));
		expect(keys.filter((key) => key.startsWith('hetikosar.'))).toEqual([]);
		await expectClean(watcher);
	});

	test('shows a notice when the browser refuses to store data', async ({ page }) => {
		await page.addInitScript(() => {
			Storage.prototype.setItem = () => {
				throw new DOMException('quota', 'QuotaExceededError');
			};
		});
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		await page.getByRole('button', { name: 'Eggyel több fő' }).click();
		await expect(page.getByTestId('people-value')).toHaveText('3 fő');
		await expect(page.getByText('A böngésző nem engedi az adatok mentését', { exact: false })).toBeVisible();
		await expectClean(watcher);
	});
});

// ───────────────────────────── location ─────────────────────────────

test.describe('location consent', () => {
	test.use({
		viewport: { width: 360, height: 740 },
		isMobile: true,
		hasTouch: true,
		geolocation: { latitude: 47.4774123, longitude: 19.0470987 },
		permissions: ['geolocation']
	});

	test('asks only after the explanation, stores a rounded position and never sends it', async ({ page }) => {
		await page.addInitScript(() => {
			const calls: (PositionOptions | null)[] = [];
			window.__geoCalls = calls;
			const original = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);
			navigator.geolocation.getCurrentPosition = (success, error, options) => {
				calls.push(options ?? null);
				original(success, error, options);
			};
		});
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		await expect(page.getByTestId('location-status')).toContainText('Nincs engedélyezve.');

		await page.getByRole('button', { name: 'Helyzet használata…' }).click();
		await expect(page.getByRole('heading', { name: 'Közeli boltok a helyzeted alapján' })).toBeFocused();
		await expect(page.getByText('A helyzeted soha nem kerül a szerverre', { exact: false })).toBeVisible();
		expect(await page.evaluate(() => window.__geoCalls?.length)).toBe(0);
		await expectNoHorizontalScroll(page);
		await page.screenshot({ path: screenshotPath('phone-360-location-explainer'), fullPage: true });

		await page.getByRole('button', { name: 'Rendben, kérem a helyzetet' }).click();
		await expect(page.getByText('A hozzávetőleges helyzetet elmentettük ezen a készüléken.')).toBeVisible();
		expect(await page.evaluate(() => window.__geoCalls)).toEqual([
			{ enableHighAccuracy: false, timeout: 15_000, maximumAge: 600_000 }
		]);
		await expect(page.getByTestId('location-status')).toContainText('Engedélyezve.');
		await expect(page.getByTestId('location-source')).toContainText('a készülék hozzávetőleges helyzete');
		const stored = await storedState(page);
		expect(stored).toMatchObject({ location: { consent: 'granted', source: 'device', approx: { lat: 47.477, lon: 19.047 } } });

		// Visiting every page (each loads data from /api) never sends the position anywhere.
		for (const route of ROUTES) {
			await page.goto(route.path);
			await expect(page.getByRole('heading', { level: 1 })).toHaveText(route.heading);
		}
		for (const request of watcher.requests) {
			expect(`${request.url} ${request.body}`).not.toMatch(/47[.,]477|19[.,]047|latitude|longitude/);
		}

		await page.goto('/beallitasok');
		await page.getByRole('button', { name: 'Engedély visszavonása' }).click();
		await expect(page.getByText('A tárolt helyzetet töröltük.', { exact: false })).toBeVisible();
		await expect(page.getByTestId('location-status')).toContainText('Nincs engedélyezve.');
		expect(await storedState(page)).toMatchObject({ location: { consent: 'unset', source: 'none', approx: null } });
		await expectClean(watcher);
	});

	test('cancelling the explanation asks nothing', async ({ page }) => {
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		await page.getByRole('button', { name: 'Helyzet használata…' }).click();
		await page.getByRole('button', { name: 'Mégse' }).click();
		await expect(page.getByRole('button', { name: 'Helyzet használata…' })).toBeFocused();
		expect(await storedState(page)).toBeNull();
		await expectClean(watcher);
	});
});

test.describe('location refused by the browser', () => {
	test.use({ viewport: { width: 360, height: 740 }, permissions: [] });

	test('explains the refusal and offers the district instead', async ({ page, context }) => {
		await context.clearPermissions();
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		await page.getByRole('button', { name: 'Helyzet használata…' }).click();
		await page.getByRole('button', { name: 'Rendben, kérem a helyzetet' }).click();
		await expect(page.getByText('A böngésző nem engedte a helyzet lekérését', { exact: false })).toBeVisible();
		await expect(page.getByTestId('location-status')).toContainText('Elutasítva.');
		expect(await storedState(page)).toMatchObject({ location: { consent: 'declined', approx: null } });
		await expectClean(watcher);
	});
});

// ───────────────────────────── accessibility ─────────────────────────────

test.describe('accessibility', () => {
	test.use({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('the first Tab reaches a visible skip link that moves focus to the content', async ({ page }) => {
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
		await page.keyboard.press('Tab');
		const skip = page.getByRole('link', { name: 'Ugrás a tartalomra' });
		await expect(skip).toBeFocused();
		const box = await skip.boundingBox();
		expect(box?.y ?? -1).toBeGreaterThanOrEqual(0);
		const outline = await skip.evaluate((el) => getComputedStyle(el).outlineStyle);
		expect(outline).not.toBe('none');
		await page.keyboard.press('Enter');
		await expect(page.locator('main')).toBeFocused();
		await expectClean(watcher);
	});

	test('touch targets are at least 44×44 px', async ({ page }) => {
		const watcher = await watch(page);
		for (const path of ['/', '/beallitasok', '/forrasok', '/receptek/minta-lencsefozelek']) {
			await page.goto(path);
			await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
			await expect(page.getByTestId('data-status')).toContainText('Adatok:');
			const small = await page.evaluate(() => {
				const targets = document.querySelectorAll<HTMLElement>(
					'button, select, input:not([type="radio"]):not([type="checkbox"]), nav a, .btn, label.choice, .skip-link'
				);
				return [...targets]
					.filter((el) => el.offsetParent !== null || el.classList.contains('skip-link'))
					.map((el) => ({ el, rect: el.getBoundingClientRect() }))
					.filter(({ rect }) => rect.width < 44 || rect.height < 44)
					.map(({ el, rect }) => `${el.tagName}.${el.className} "${el.textContent?.trim()}" ${rect.width}x${rect.height}`);
			});
			expect(small, path).toEqual([]);
		}
		await expectClean(watcher);
	});

	test('every form control has an accessible name', async ({ page }) => {
		const watcher = await watch(page);
		await page.goto('/beallitasok');
		for (const control of await page.locator('input, select, button').all()) {
			const name = await control.evaluate((el) => {
				const labelled = el.getAttribute('aria-label') ?? '';
				const labels = (el as HTMLInputElement).labels ? [...((el as HTMLInputElement).labels ?? [])].map((l) => l.textContent) : [];
				return `${labelled}${labels.join('')}${el.tagName === 'BUTTON' ? el.textContent : ''}`.trim();
			});
			expect(name.length, await control.evaluate((el) => el.outerHTML.slice(0, 80))).toBeGreaterThan(0);
		}
		await expectClean(watcher);
	});
});

test.describe('dark mode', () => {
	test.use({ colorScheme: 'dark', viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });

	test('uses the dark tokens', async ({ page }) => {
		const watcher = await watch(page);
		for (const path of ['/', '/beallitasok']) {
			await page.goto(path);
			await expect(page.getByTestId('data-status')).toContainText('Adatok:');
			expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe('rgb(17, 20, 18)');
			await page.screenshot({ path: screenshotPath(`dark-phone-360-${slug(path)}`), fullPage: true });
		}
		await expectNoHorizontalScroll(page);
		await expectClean(watcher);
	});
});

test.describe('motion', () => {
	for (const reducedMotion of ['reduce', 'no-preference'] as const) {
		test(`the spinner honours prefers-reduced-motion: ${reducedMotion}`, async ({ page }) => {
			await page.emulateMedia({ reducedMotion });
			let release: () => void = () => undefined;
			const gate = new Promise<void>((done) => {
				release = done;
			});
			const watcher = await watch(page, async (method, url, body) => {
				if (url.startsWith('/api/meta')) await gate;
				return handleMockApi(method, url, body);
			});
			await page.goto('/');
			const ring = page.locator('.spinner .ring').first();
			await expect(ring).toBeVisible();
			const animation = await ring.evaluate((el) => getComputedStyle(el).animationName);
			if (reducedMotion === 'reduce') expect(animation).toBe('none');
			else expect(animation).not.toBe('none');
			release();
			await expect(page.getByTestId('data-status')).toContainText(`Adatok: ${DATE_HU}`);
			await expectClean(watcher);
		});
	}
});

// ───────────────────────────── API states ─────────────────────────────

test('shows an error with retry when /api/meta fails, then recovers', async ({ page }) => {
	let fail = true;
	const watcher = await watch(page, (method, url, body) =>
		fail && url.startsWith('/api/meta') ? { status: 500, body: { error: 'internal', fields: [] } } : handleMockApi(method, url, body)
	);
	await page.goto('/');
	await expect(page.getByTestId('data-status')).toContainText('Az adatok dátuma most nem érhető el.');
	fail = false;
	await page.getByTestId('data-status').getByRole('button', { name: 'Újra' }).click();
	await expect(page.getByTestId('data-status')).toContainText(`Adatok: ${DATE_HU}`);
	await expectClean(watcher, /status of 500/);
});

test('warns when the price data is stale and handles "no data yet"', async ({ page }) => {
	let meta: unknown = { ...MOCK_META, stale: true };
	const watcher = await watch(page, (method, url, body) =>
		url.startsWith('/api/meta') ? { status: 200, body: meta } : handleMockApi(method, url, body)
	);
	await page.goto('/');
	await expect(page.getByText('Az árak nem frissek', { exact: false }).first()).toBeVisible();
	await expect(page.getByText(`A legutóbbi áradatok dátuma: ${DATE_HU}`, { exact: false })).toBeVisible();
	await expect(page.getByText(`${DATE_HU}.`, { exact: false })).toHaveCount(0);
	await page.screenshot({ path: screenshotPath('desktop-stale-warning') });

	meta = { ...MOCK_META, data_date: null, ingested_at: null };
	await page.reload();
	await expect(page.getByTestId('data-status')).toContainText('Még nincs áradat.');
	await expectClean(watcher);
});

// ───────────────────────────── offline (service worker) ─────────────────────────────

test.describe('offline', () => {
	test.use({ serviceWorkers: 'allow', viewport: { width: 360, height: 740 } });

	test('the service worker precaches the shell and serves the app and cached data when the server is gone', async ({
		page,
		context
	}) => {
		const port = 4300 + Math.floor(Math.random() * 600);
		const server = await startStaticServer(BUILD_DIR, port, handleMockApi);
		const origin = `http://127.0.0.1:${port}`;
		const pageErrors: string[] = [];
		page.on('pageerror', (error) => pageErrors.push(String(error)));
		try {
			await page.goto(`${origin}/`);
			await expect(page.getByTestId('data-status')).toContainText(`Adatok: ${DATE_HU}`);
			await page.evaluate(async () => {
				await navigator.serviceWorker.ready;
			});
			await page.reload();
			await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
			await expect(page.getByTestId('data-status')).toContainText(`Adatok: ${DATE_HU}`);

			const caches = await page.evaluate(async () => {
				const names = await window.caches.keys();
				const contents: Record<string, string[]> = {};
				for (const name of names) {
					const cache = await window.caches.open(name);
					contents[name] = (await cache.keys()).map((request) => new URL(request.url).pathname);
				}
				return contents;
			});
			const shell = Object.entries(caches).find(([name]) => name.startsWith('hk-shell-'));
			const api = Object.entries(caches).find(([name]) => name.startsWith('hk-api-'));
			expect(shell?.[1]).toEqual(expect.arrayContaining(['/', '/manifest.webmanifest', '/icons/icon-192.png']));
			expect(shell?.[1].some((path) => path.startsWith('/_app/immutable/'))).toBe(true);
			expect(api?.[1]).toContain('/api/meta');
			expect(Object.keys(caches)).toHaveLength(2);

			// The server goes away and the device goes offline.
			await new Promise<void>((done) => {
				server.closeAllConnections();
				server.close(() => done());
			});
			await context.setOffline(true);

			await page.reload();
			await expect(page.getByRole('heading', { level: 1 })).toHaveText('Heti étrend, bevásárlólista, közeli árak');
			await expect(page.getByTestId('data-status')).toContainText(`Adatok: ${DATE_HU}`);
			await expect(page.getByText('Nincs internetkapcsolat. A legutóbb betöltött adatokat látod.')).toBeVisible();

			await page.getByRole('navigation', { name: 'Fő navigáció' }).getByRole('link', { name: 'Beállítások' }).click();
			await expect(page.getByRole('heading', { level: 1 })).toHaveText('Beállítások');
			await page.goto(`${origin}/forrasok`);
			await expect(page.getByRole('heading', { level: 1 })).toHaveText('Források és adatvédelem');
			await expect(page.getByTestId('attribution-gvh')).toHaveText(ATTRIBUTION);
			await page.screenshot({ path: screenshotPath('offline-phone-360-forrasok'), fullPage: true });
			expect(pageErrors).toEqual([]);
		} finally {
			await context.setOffline(false);
			server.closeAllConnections();
			server.close();
		}
	});
});
