// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { STORAGE_KEY, clearAll, isPersistent, load, resetForTests, update } from '../storage';
import {
	MAX_REMEMBERED_LISTS,
	defaultListPrefs,
	listEntry,
	loadListPrefs,
	saveListPrefs,
	withListEntry,
	type ListPrefs
} from './prefs';

/** In-memory Storage double; `failGet` / `failSet` / `failRemove` simulate private mode and full quotas. */
class FakeStorage implements Storage {
	readonly map = new Map<string, string>();
	failGet = false;
	failSet = false;
	failRemove = false;

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
		if (this.failRemove) throw new DOMException('denied', 'SecurityError');
		this.map.delete(key);
	}

	setItem(key: string, value: string): void {
		if (this.failSet) throw new DOMException('full', 'QuotaExceededError');
		this.map.set(key, String(value));
	}
}

let fake: FakeStorage;

beforeEach(() => {
	resetForTests();
	fake = new FakeStorage();
	vi.stubGlobal('localStorage', fake);
});

afterEach(() => {
	vi.unstubAllGlobals();
	resetForTests();
});

const sample = (): ListPrefs => ({
	range: 'next_week',
	entries: [
		{
			key: '2026-10-13T08:00:00.000Z|next_week',
			checked: ['voroshagyma'],
			removed: ['repa', 'rizs'],
			included: ['tojas'],
			storeId: 'synthetic-lidl-1'
		},
		{ key: '2026-10-13T08:00:00.000Z|whole', checked: [], removed: [], included: [], storeId: null }
	]
});

/** An entry with no ticks, removed or included lines unless given. */
function entryOf(key: string, extra: Partial<ListPrefs['entries'][number]> = {}): ListPrefs['entries'][number] {
	return { key, checked: [], removed: [], included: [], storeId: null, ...extra };
}

function storedList(): unknown {
	const raw = fake.map.get(STORAGE_KEY);
	return raw === undefined ? undefined : (JSON.parse(raw) as { list?: unknown }).list;
}

describe('list choices in the one stored document', () => {
	it('live in StoredState.list under hetikosar.state, with no key of their own', () => {
		expect(saveListPrefs(sample())).toBe(true);
		expect([...fake.map.keys()]).toEqual([STORAGE_KEY]);
		expect(storedList()).toEqual(sample());
		expect(load().list).toEqual(sample());
	});

	it('round-trip and keep the rest of the state', () => {
		update({ people: 4, pantry: { notAtHome: ['so'] } });
		saveListPrefs(sample());
		resetForTests();
		expect(loadListPrefs()).toEqual(sample());
		expect(load()).toMatchObject({ people: 4, pantry: { notAtHome: ['so'] } });
	});

	it('are the defaults when nothing is stored', () => {
		expect(loadListPrefs()).toEqual(defaultListPrefs());
		expect(defaultListPrefs()).toEqual({ range: 'this_week', entries: [] });
	});

	it('are wiped by "minden adat törlése", in memory too', () => {
		saveListPrefs(sample());
		expect(clearAll()).toBe(true);
		expect(fake.map.size).toBe(0);
		expect(loadListPrefs()).toEqual(defaultListPrefs());
	});

	it('keep working in memory when the browser refuses to write, and are still wiped by clearAll', () => {
		fake.failSet = true;
		expect(saveListPrefs(sample())).toBe(false);
		expect(isPersistent()).toBe(false);
		expect(loadListPrefs()).toEqual(sample());
		expect(fake.map.size).toBe(0);
		clearAll();
		expect(loadListPrefs()).toEqual(defaultListPrefs());
	});

	it('are wiped from the session even when the stored copy cannot be deleted', () => {
		saveListPrefs(sample());
		fake.failRemove = true;
		expect(clearAll()).toBe(false);
		expect(fake.map.has(STORAGE_KEY)).toBe(true);
		expect(loadListPrefs()).toEqual(defaultListPrefs());
		expect(isPersistent()).toBe(false);
	});

	it('work without any localStorage', () => {
		vi.stubGlobal('localStorage', undefined);
		expect(loadListPrefs()).toEqual(defaultListPrefs());
		expect(saveListPrefs(sample())).toBe(false);
		expect(loadListPrefs()).toEqual(sample());
		expect(clearAll()).toBe(false);
		expect(loadListPrefs()).toEqual(defaultListPrefs());
	});

	it('are validated on save like everything in the document', () => {
		const dirty = {
			range: 'month',
			entries: [
				{ key: 'ok', checked: ['BAD!', 'so', 'so'], removed: ['repa', 'BAD!', 'repa'], storeId: 'bad id!' },
				{ key: '', removed: [], storeId: null }
			]
		} as unknown as ListPrefs;
		saveListPrefs(dirty);
		expect(loadListPrefs()).toEqual({ range: 'this_week', entries: [entryOf('ok', { checked: ['so'], removed: ['repa'] })] });
	});

	it('returns copies that callers cannot use to change the stored choices', () => {
		saveListPrefs(sample());
		const loaded = loadListPrefs();
		loaded.entries[0]?.removed.push('hacked');
		loaded.entries[0]?.checked.push('hacked');
		expect(loadListPrefs()).toEqual(sample());
	});
});

describe('listEntry / withListEntry', () => {
	it('accept Proxy objects such as Svelte $state (which structuredClone cannot copy)', () => {
		const proxied = new Proxy(sample(), {});
		const entry = listEntry(proxied, '2026-10-13T08:00:00.000Z|next_week');
		const proxyEntry = new Proxy(
			{ ...entry, removed: new Proxy([...entry.removed], {}), checked: new Proxy([...entry.checked], {}) },
			{}
		);
		const next = withListEntry(proxied, proxyEntry);
		expect(next.entries[0]).toEqual(sample().entries[0]);
		expect(saveListPrefs(new Proxy(next, {}))).toBe(true);
		expect(update({ list: new Proxy(next, {}) }).list.entries[0]?.removed).toEqual(['repa', 'rizs']);
		expect(loadListPrefs().entries[0]?.removed).toEqual(['repa', 'rizs']);
	});

	it('gives an empty entry for a new list: no ticks (a new plan or range never starts ticked)', () => {
		expect(listEntry(sample(), 'new')).toEqual({ key: 'new', checked: [], removed: [], included: [], storeId: null });
		expect(listEntry(sample(), '2026-10-13T08:00:00.000Z|whole').checked).toEqual([]);
		expect(listEntry(sample(), '2026-10-13T08:00:00.000Z|next_week').checked).toEqual(['voroshagyma']);
	});

	it('finds an entry and returns a copy', () => {
		const prefs = sample();
		const entry = listEntry(prefs, '2026-10-13T08:00:00.000Z|next_week');
		expect(entry.storeId).toBe('synthetic-lidl-1');
		entry.removed.push('x');
		entry.checked.push('x');
		entry.included.push('x');
		expect(prefs).toEqual(sample());
	});

	it('stores an entry as the most recent, replacing the old one, and forgets the oldest', () => {
		const prefs = sample();
		const whole = entryOf('2026-10-13T08:00:00.000Z|whole', { checked: ['so'], removed: ['so'], storeId: 'x-1' });
		const next = withListEntry(prefs, whole);
		expect(next.entries.map((l) => l.key)).toEqual(['2026-10-13T08:00:00.000Z|whole', '2026-10-13T08:00:00.000Z|next_week']);
		expect(next.entries[0]).toEqual(whole);
		expect(next.entries[1]).toEqual(sample().entries[0]);
		expect(next.range).toBe('next_week');
		expect(prefs).toEqual(sample());

		let many = defaultListPrefs();
		for (let i = 0; i < MAX_REMEMBERED_LISTS + 3; i += 1) many = withListEntry(many, entryOf(`k${i}`));
		expect(many.entries).toHaveLength(MAX_REMEMBERED_LISTS);
		expect(MAX_REMEMBERED_LISTS).toBe(12);
		expect(many.entries[0]?.key).toBe(`k${MAX_REMEMBERED_LISTS + 2}`);
	});
});
