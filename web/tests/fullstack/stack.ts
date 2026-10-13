/**
 * Shared paths and the stack state for the full-stack suite (docs/E2E.md).
 *
 * The Python launcher (`server/tests/fullstack`, started by global-setup.ts) writes `stack.json` into the run
 * directory once the REAL stack is up: PostgreSQL made by deploy/local/db-init.sh, the fake GVH (REAL store
 * list, SYNTHETIC products and prices), the real ingest and content loader, and the real API serving
 * web/build. The state holds no secrets.
 */
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const WEB_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
export const REPO_DIR = resolve(WEB_DIR, '..');
export const SERVER_DIR = join(REPO_DIR, 'server');
export const BUILD_DIR = join(WEB_DIR, 'build');
/** The real store list the fake GVH serves (research data, read-only). */
export const STORES_CSV = join(REPO_DIR, 'research', 'gvh-location', 'data', 'stores.csv');
/** Logs, stack.json and teardown.json of the launcher (git-ignored; outside Playwright's outputDir). */
export const RUN_DIR = resolve(process.env.FULLSTACK_RUN_DIR ?? join(WEB_DIR, 'test-results', 'fullstack-stack'));
export const STATE_FILE = join(RUN_DIR, 'stack.json');
export const TEARDOWN_FILE = join(RUN_DIR, 'teardown.json');
export const READY_PREFIX = 'FULLSTACK-READY ';
/** Set by global-setup.ts for the workers: the API's address. */
export const BASE_URL_ENV = 'FULLSTACK_BASE_URL';

export interface StepState {
	name: string;
	exit_code: number;
	status: string;
	summary: string;
	seconds: number;
	requests: number;
	min_request_gap_s: number | null;
	request_span_s: number | null;
}

export interface StackState {
	base_url: string;
	api_port: number;
	data_date: string;
	launcher_pid: number;
	run_dir: string;
	web_build: string | null;
	postgres: { major: number; port: number };
	fake_gvh: { synthetic: true; base: string; seed: number; per_leaf: number; leaves: number; products: number; stores: number; requests: number };
	steps: StepState[];
	runs: { id: number; kind: string; status: string; data_date: string | null; requests: number; warnings: string[] }[];
	timings: Record<string, number>;
}

export interface TeardownState {
	clean: boolean;
	errors: string[];
	signals: string[];
	timings: Record<string, number>;
}

export function readState(): StackState {
	return JSON.parse(readFileSync(STATE_FILE, 'utf-8')) as StackState;
}

export function readTeardown(): TeardownState {
	return JSON.parse(readFileSync(TEARDOWN_FILE, 'utf-8')) as TeardownState;
}
