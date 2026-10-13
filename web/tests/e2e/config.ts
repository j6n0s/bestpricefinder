/** Shared e2e settings. */
export const E2E_PORT = Number(process.env.E2E_PORT ?? 4317);
export const BASE_URL = `http://127.0.0.1:${E2E_PORT}`;
/** Screenshots go here (default: web/test-results/screenshots, git-ignored). */
export const SCREENSHOT_DIR = process.env.E2E_SCREENSHOT_DIR ?? 'test-results/screenshots';
