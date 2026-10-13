// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { STORAGE_PREFIX, clearAll, resetForTests } from '../storage';
import {
	LIST_PREFS_KEY,
	LIST_PREFS_VERSION,
	MAX_REMEMBERED_LISTS,
	defaultListPrefs,
	listEntry,
	loadListPrefs,
	resetListPrefsForTests,
	sanitiseListPrefs,
	saveListPrefs,
	withListEntry,
	type ListPrefs
} from './prefs';

/** In-memory Storage double; `failGet` / `failSet` simulate private mode and full quotas. */
class FakeStorage implements Storage {
	readonly map = new Map<string, string>();
	failGet = false;
	failSet = false;

	get length(): number {
		return this.map.size;
	}

	clear(): void {
		this.map.clear();
	}

	getItem(key: string): string | null {
		if (this.failGet) throw new DOMException('denied', 'SecurityError');
		return this.map.get(key) ?? null;
	}

	key(index: number): string | null {
		return [...this.map.keys()][index] ?? null;
	}

	removeItem(key: string): void {
		this.map.delete(key);
	}

	setItem(key: string, value: string): void {
		if (this.failSet) throw new DOMException('full', 'QuotaExceededError');
		this.map.set(key, String(value));
	}
}

let fake: FakeStorage;

beforeEach(() => {
	resetListPrefsForTests();
	resetForTests();
	fake = new FakeStorage();
	vi.stubGlobal('localStorage', fake);
});

afterEach(() => {
	vi.unstubAllGlobals();
	resetListPrefsForTests();
	resetForTests();
});

const sample = (): ListPrefs => ({
	version: LIST_PREFS_VERSION,
	range: 'next_week',
	lists: [
		{ key: '2026-10-13T08:00:00.000Z|next_week', removed: ['repa', 'rizs'], storeId: 'synthetic-lidl-1' },
		{ key: '2026-10-13T08:00:00.000Z|whole', removed: [], storeId: null }
	]
});

describe('list prefs storage', () => {
	it('uses a key with the app prefix, so "minden adat törlése" removes it', () => {
		expect(LIST_PREFS_KEY.startsWith(STORAGE_PREFIX)).toBe(true);
		expect(saveListPrefs(sample())).toBe(true);
		expect(fake.map.has(LIST_PREFS_KEY)).toBe(true);
		expect(clearAll()).toBe(true);
		expect(fake.map.has(LIST_PREFS_KEY)).toBe(false);
		expect(loadListPrefs()).toEqual(defaultListPrefs());
	});

	it('round-trips through localStorage', () => {
		saveListPrefs(sample());
		resetListPrefsForTests();
		expect(loadListPrefs()).toEqual(sample());
		expect(JSON.parse(fake.map.get(LIST_PREFS_KEY) ?? 'null')).toEqual(sample());
	});

	it('gives the defaults when nothing is stored, or the JSON is broken', () => {
		expect(loadListPrefs()).toEqual(defaultListPrefs());
		fake.map.set(LIST_PREFS_KEY, '{not json');
		expect(loadListPrefs()).toEqual(defaultListPrefs());
	});

	it('resets an unknown or missing version', () => {
		fake.map.set(LIST_PREFS_KEY, JSON.stringify({ ...sample(), version: 2 }));
		expect(loadListPrefs()).toEqual(defaultListPrefs());
		fake.map.set(LIST_PREFS_KEY, JSON.stringify({ range: 'whole', lists: [] }));
		expect(loadListPrefs()).toEqual(defaultListPrefs());
	});

	it('keeps working in memory when the browser refuses to write', () => {
		fake.failSet = true;
		expect(saveListPrefs(sample())).toBe(false);
		expect(loadListPrefs()).toEqual(sample());
		fake.failSet = false;
		expect(saveListPrefs(defaultListPrefs())).toBe(true);
		expect(loadListPrefs()).toEqual(defaultListPrefs());
	});

	it('keeps working in memory when the browser refuses to read', () => {
		fake.failGet = true;
		expect(loadListPrefs()).toEqual(defaultListPrefs());
		saveListPrefs(sample());
		expect(loadListPrefs()).toEqual(sample());
	});

	it('works without any localStorage', () => {
		vi.stubGlobal('localStorage', undefined);
		expect(loadListPrefs()).toEqual(defaultListPrefs());
		expect(saveListPrefs(sample())).toBe(false);
		expect(loadListPrefs()).toEqual(sample());
	});

	it('returns copies that callers cannot use to change the stored prefs', () => {
		saveListPrefs(sample());
		const loaded = loadListPrefs();
		loaded.lists[0]?.removed.push('hacked');
		expect(loadListPrefs()).toEqual(sample());
	});
});

describe('sanitiseListPrefs', () => {
	it('drops invalid entries and fields', () => {
		const result = sanitiseListPrefs({
			version: 1,
			range: 'month',
			lists: [
				{ key: 'ok', removed: ['repa', 'repa', 'BAD!', 7, 'rizs'], storeId: 'bad id!' },
				{ key: 'ok', removed: [], storeId: null },
				{ key: '', removed: [] },
				{ key: 'x'.repeat(81), removed: [] },
				{ key: 'tab\tkey', removed: [] },
				'not an object',
				{ key: 'second', removed: 'nope', storeId: 'synthetic-aldi-1' }
			]
		});
		expect(result).toEqual({
			version: 1,
			range: 'this_week',
			lists: [
				{ key: 'ok', removed: ['repa', 'rizs'], storeId: null },
				{ key: 'second', removed: [], storeId: 'synthetic-aldi-1' }
			]
		});
	});

	it('keeps at most the remembered number of lists', () => {
		const lists = Array.from({ length: MAX_REMEMBERED_LISTS + 5 }, (_, i) => ({ key: `k${i}`, removed: [], storeId: null }));
		expect(sanitiseListPrefs({ version: 1, range: 'whole', lists }).lists).toHaveLength(MAX_REMEMBERED_LISTS);
	});

	it('rejects non-objects', () => {
		for (const raw of [null, undefined, 1, 'x', [], [1]]) expect(sanitiseListPrefs(raw)).toEqual(defaultListPrefs());
	});
});

describe('listEntry / withListEntry', () => {
	it('accepts Proxy objects such as Svelte $state (which structuredClone cannot copy)', () => {
		const proxied = new Proxy(sample(), {});
		const entry = listEntry(proxied, '2026-10-13T08:00:00.000Z|next_week');
		const proxyEntry = new Proxy({ ...entry, removed: new Proxy([...entry.removed], {}) }, {});
		const next = withListEntry(proxied, proxyEntry);
		expect(next.lists[0]).toEqual({ key: '2026-10-13T08:00:00.000Z|next_week', removed: ['repa', 'rizs'], storeId: 'synthetic-lidl-1' });
		expect(saveListPrefs(new Proxy(next, {}))).toBe(true);
		expect(loadListPrefs().lists[0]?.removed).toEqual(['repa', 'rizs']);
	});

	it('gives an empty entry for a new list', () => {
		expect(listEntry(sample(), 'new')).toEqual({ key: 'new', removed: [], storeId: null });
	});

	it('finds an entry and returns a copy', () => {
		const prefs = sample();
		const entry = listEntry(prefs, '2026-10-13T08:00:00.000Z|next_week');
		expect(entry.storeId).toBe('synthetic-lidl-1');
		entry.removed.push('x');
		expect(prefs.lists[0]?.removed).toEqual(['repa', 'rizs']);
	});

	it('stores an entry as the most recent, replacing the old one, and forgets the oldest', () => {
		const prefs = sample();
		const next = withListEntry(prefs, { key: '2026-10-13T08:00:00.000Z|whole', removed: ['so'], storeId: 'x-1' });
		expect(next.lists.map((l) => l.key)).toEqual(['2026-10-13T08:00:00.000Z|whole', '2026-10-13T08:00:00.000Z|next_week']);
		expect(next.lists[0]).toEqual({ key: '2026-10-13T08:00:00.000Z|whole', removed: ['so'], storeId: 'x-1' });
		expect(prefs).toEqual(sample());

		let many = defaultListPrefs();
		for (let i = 0; i < MAX_REMEMBERED_LISTS + 3; i += 1) many = withListEntry(many, { key: `k${i}`, removed: [], storeId: null });
		expect(many.lists).toHaveLength(MAX_REMEMBERED_LISTS);
		expect(many.lists[0]?.key).toBe(`k${MAX_REMEMBERED_LISTS + 2}`);
	});
});
