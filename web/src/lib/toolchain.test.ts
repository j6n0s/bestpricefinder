/**
 * The locked development toolchain stays outside known advisories (`npm audit --audit-level=moderate` must
 * pass). The shipped SPA contains none of these packages, but the test runner runs on every `npm test`.
 * - vitest / @vitest/mocker 2.1.0–4.1.10: GHSA-82fw-gwwq-j7x9 (path traversal, moderate);
 * - tinypool ≤ 2.1.1: GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr (prototype pollution to RCE, critical).
 *   vitest 4.1.11 no longer depends on tinypool.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

interface LockPackage {
	version?: string;
}

const lock = JSON.parse(readFileSync(fileURLToPath(new URL('../../package-lock.json', import.meta.url)), 'utf8')) as {
	packages: Record<string, LockPackage>;
};

function version(name: string): number[] | null {
	const found = lock.packages[`node_modules/${name}`]?.version;
	return found ? found.split(/[.-]/).slice(0, 3).map(Number) : null;
}

function atLeast(actual: number[] | null, wanted: number[]): boolean {
	if (actual === null) return false;
	for (let i = 0; i < wanted.length; i += 1) {
		const a = actual[i] ?? 0;
		const w = wanted[i] ?? 0;
		if (a !== w) return a > w;
	}
	return true;
}

describe('locked development toolchain', () => {
	it('vitest and @vitest/mocker are at 4.1.11 or later', () => {
		expect(atLeast(version('vitest'), [4, 1, 11]), `vitest ${version('vitest')?.join('.')}`).toBe(true);
		expect(atLeast(version('@vitest/mocker'), [4, 1, 11]), `@vitest/mocker ${version('@vitest/mocker')?.join('.')}`).toBe(true);
	});

	it('no tinypool at or below 2.1.1', () => {
		const tinypool = version('tinypool');
		expect(tinypool === null || atLeast(tinypool, [2, 1, 2]), `tinypool ${tinypool?.join('.')}`).toBe(true);
	});
});
