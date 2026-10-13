import { defineConfig, devices } from '@playwright/test';

/**
 * Full-stack end-to-end suite (docs/E2E.md): `npm run test:fullstack` builds web/build, then global-setup.ts
 * starts the REAL stack with `python -m tests.fullstack` (PostgreSQL from deploy/local/db-init.sh, the fake GVH
 * with the REAL store list and SYNTHETIC products, the real ingest, content loader and API serving web/build),
 * and global-teardown.ts stops it. The specs read the API's address from the launcher's stack.json.
 *
 * Uses the Chromium preinstalled under PLAYWRIGHT_BROWSERS_PATH (never `playwright install`). Service workers
 * are blocked so that every request of the page is visible to the test (the offline behaviour is covered by
 * tests/e2e/smoke.spec.ts).
 */
export default defineConfig({
	testDir: 'tests/fullstack',
	outputDir: 'test-results/fullstack',
	globalSetup: './tests/fullstack/global-setup.ts',
	globalTeardown: './tests/fullstack/global-teardown.ts',
	fullyParallel: true,
	forbidOnly: Boolean(process.env.CI),
	retries: 0,
	workers: 2,
	reporter: [['list']],
	timeout: 180_000,
	expect: { timeout: 15_000 },
	use: {
		...devices['Desktop Chrome'],
		locale: 'hu-HU',
		timezoneId: 'Europe/Budapest',
		serviceWorkers: 'block',
		trace: 'retain-on-failure'
	},
	projects: [
		{ name: 'phone-390', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
		{ name: 'desktop-1280', use: { viewport: { width: 1280, height: 800 } } }
	]
});
