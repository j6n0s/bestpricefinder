import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

/**
 * The one inline script of src/app.html applies the stored theme before the first paint. It runs before any
 * module of the app, so it is tested here as the browser sees it: extracted with the regex svelte.config.js
 * hashes it with, and run against stand-ins for localStorage and the document.
 */
const html = readFileSync(fileURLToPath(new URL('../app.html', import.meta.url)), 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];

interface FakeDocument {
	documentElement: { dataset: Record<string, string | undefined> };
	querySelectorAll: (selector: string) => { content: string }[];
	metas: { content: string }[];
}

function run(stored: string | null | (() => never)): FakeDocument {
	const metas = [{ content: '#ffffff' }, { content: '#000000' }];
	const document: FakeDocument = {
		documentElement: { dataset: {} },
		querySelectorAll: (selector) => (selector === 'meta[name="theme-color"]' ? metas : []),
		metas
	};
	const localStorage = {
		getItem: (key: string): string | null => {
			if (typeof stored === 'function') return stored();
			return key === 'hetikosar.state' ? stored : null;
		}
	};
	new Function('localStorage', 'document', scripts[0]?.[1] ?? '')(localStorage, document);
	return document;
}

describe('the pre-paint theme script', () => {
	it('is the only inline script, and reads the storage key of the app', () => {
		expect(scripts).toHaveLength(1);
		expect(scripts[0]?.[1]).toContain("'hetikosar.state'");
	});

	it('applies a stored choice of a version-1 document, with the theme-color metas', () => {
		const dark = run(JSON.stringify({ version: 1, theme: 'dark' }));
		expect(dark.documentElement.dataset.theme).toBe('dark');
		expect(dark.metas.map((meta) => meta.content)).toEqual(['#000000', '#000000']);
		const light = run(JSON.stringify({ version: 1, theme: 'light' }));
		expect(light.documentElement.dataset.theme).toBe('light');
		expect(light.metas.map((meta) => meta.content)).toEqual(['#ffffff', '#ffffff']);
	});

	it('leaves the browser setting alone for "system", no document, another version, or an unknown theme', () => {
		for (const stored of [
			null,
			JSON.stringify({ version: 1, theme: 'system' }),
			JSON.stringify({ version: 1 }),
			JSON.stringify({ version: 2, theme: 'dark' }),
			JSON.stringify({ theme: 'dark' }),
			JSON.stringify({ version: 1, theme: 'sepia' }),
			'not json',
			'null'
		]) {
			const result = run(stored);
			expect(result.documentElement.dataset.theme, String(stored)).toBeUndefined();
			expect(result.metas.map((meta) => meta.content)).toEqual(['#ffffff', '#000000']);
		}
	});

	it('never throws, even when the storage itself does', () => {
		expect(() =>
			run(() => {
				throw new Error('blocked');
			})
		).not.toThrow();
	});
});
