import { defineConfig, devices } from '@playwright/test';
import { BASE_URL } from './tests/e2e/config';

/**
 * Smoke tests against the production build (web/build), served by tests/e2e/static-server.ts the way the
 * FastAPI server will serve it. Every /api call is answered by the SYNTHETIC mocks in tests/mocks.
 * Uses the Chromium preinstalled under PLAYWRIGHT_BROWSERS_PATH (never `playwright install`).
 */
export default defineConfig({
	testDir: 'tests/e2e',
	globalSetup: './tests/e2e/global-setup.ts',
	fullyParallel: true,
	forbidOnly: Boolean(process.env.CI),
	retries: 0,
	workers: 2,
	reporter: [['list']],
	timeout: 30_000,
	expect: { timeout: 5_000 },
	use: {
		...devices['Desktop Chrome'],
		baseURL: BASE_URL,
		locale: 'hu-HU',
		timezoneId: 'Europe/Budapest',
		// page.route cannot see requests a service worker makes, so the worker is blocked except in the
		// offline test, which opts in.
		serviceWorkers: 'block',
		trace: 'retain-on-failure'
	},
	projects: [{ name: 'chromium' }]
});
