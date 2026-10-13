import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	STORAGE_KEY,
	STORAGE_VERSION,
	clearAll,
	defaultState,
	isPersistent,
	load,
	migrate,
	normaliseRadius,
	resetForTests,
	save,
	update,
	type StoredState
} from './storage';

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

function stored(): unknown {
	const raw = fake.map.get(STORAGE_KEY);
	return raw === undefined ? undefined : JSON.parse(raw);
}

const fullState = (): StoredState => ({
	version: STORAGE_VERSION,
	language: 'en',
	people: 4,
	slots: 5,
	radiusKm: 2.5,
	plan: {
		createdAt: '2026-10-13T08:00:00.000Z',
		startDate: '2026-10-13',
		seed: 42,
		slots: 5,
		noRepeatDays: 5,
		days: [
			{ index: 0, meals: { reggeli: 'turos-kenyer', ebed: 'lencsefozelek', vacsora: null } },
			{ index: 1, meals: { ebed: 'lencsefozelek' } }
		]
	},
	pantry: { notAtHome: ['napraforgoolaj'] },
	exclusions: { tags: ['hal', 'sertes'], ingredients: ['tej'] },
	location: { consent: 'granted', source: 'device', districtId: '11', approx: { lat: 47.477, lon: 19.047, at: '2026-10-13T08:00:00.000Z' } },
	checkedItems: ['lencse', 'voroshagyma'],
	list: {
		range: 'next_week',
		entries: [
			{ key: '2026-10-13T08:00:00.000Z|next_week', removed: ['repa', 'rizs'], storeId: 'synthetic-lidl-1' },
			{ key: '2026-10-13T08:00:00.000Z|whole', removed: [], storeId: null }
		]
	}
});

describe('defaults', () => {
	it('are people 2, slots 3, radius 1.5 km, Hungarian, nothing else', () => {
		const state = load();
		expect(state).toEqual(defaultState());
		expect(state).toMatchObject({ version: 1, people: 2, slots: 3, radiusKm: 1.5, language: 'hu', plan: null });
		expect(state.location).toEqual({ consent: 'unset', source: 'none', districtId: null, approx: null });
		expect(state.pantry).toEqual({ notAtHome: [] });
		expect(state.list).toEqual({ range: 'this_week', entries: [] });
		expect(isPersistent()).toBe(true);
	});

	it('are a fresh object every time', () => {
		const a = load();
		a.people = 9;
		expect(load().people).toBe(2);
	});
});

describe('save / load / update', () => {
	it('round-trips a complete valid state', () => {
		expect(save(fullState())).toBe(true);
		expect(load()).toEqual(fullState());
		expect(stored()).toEqual(fullState());
	});

	it('update merges top-level fields and persists them', () => {
		const next = update({ people: 3, language: 'en' });
		expect(next).toMatchObject({ people: 3, language: 'en', slots: 3 });
		expect(load()).toMatchObject({ people: 3, language: 'en' });
		expect((stored() as StoredState).people).toBe(3);
	});

	it('never writes invalid values', () => {
		update({ people: 99, radiusKm: -1 });
		expect(stored()).toMatchObject({ people: 2, radiusKm: 1.5 });
	});

	it('returns copies that cannot change the stored state', () => {
		save(fullState());
		const state = load();
		state.checkedItems.push('x');
		state.exclusions.tags.length = 0;
		expect(load()).toEqual(fullState());
	});

	it('sees changes written by another tab', () => {
		save(fullState());
		const other = { ...fullState(), people: 7 };
		fake.map.set(STORAGE_KEY, JSON.stringify(other));
		expect(load().people).toBe(7);
	});
});

describe('migration', () => {
	it.each([
		['missing version', { ...fullState(), version: undefined }],
		['future version', { ...fullState(), version: 99 }],
		['version 0', { ...fullState(), version: 0 }],
		['negative version', { ...fullState(), version: -1 }],
		['fractional version', { ...fullState(), version: 1.5 }],
		['string version', { ...fullState(), version: '1' }]
	])('resets an unknown version (%s) to the defaults', (_name, doc) => {
		fake.map.set(STORAGE_KEY, JSON.stringify(doc));
		expect(load()).toEqual(defaultState());
	});

	it.each([['not json {'], ['[]'], ['42'], ['null'], ['"text"'], ['']])('resets unreadable content %j', (raw) => {
		fake.map.set(STORAGE_KEY, raw);
		expect(load()).toEqual(defaultState());
	});

	it('is idempotent on valid states', () => {
		expect(migrate(fullState())).toEqual(fullState());
		expect(migrate(migrate(defaultState()))).toEqual(defaultState());
	});

	it('fills fields missing from an older version-1 document with defaults', () => {
		expect(migrate({ version: 1, people: 3 })).toEqual({ ...defaultState(), people: 3 });
	});
});

describe('field validation', () => {
	it.each([0, 13, 2.5, '3', null, Number.NaN])('people %j falls back to 2', (people) => {
		expect(migrate({ ...fullState(), people }).people).toBe(2);
	});

	it.each([1, 12])('people %s is kept', (people) => {
		expect(migrate({ ...fullState(), people }).people).toBe(people);
	});

	it.each([4, '5', 0, null])('slots %j falls back to 3', (slots) => {
		expect(migrate({ ...fullState(), slots }).slots).toBe(3);
	});

	it.each([
		[0.5, 0.5],
		[5, 5],
		[1.3, 1.5],
		[2.2, 2],
		[0.4, null],
		[5.01, null],
		[Number.NaN, null],
		['2', null]
	])('radius %j -> %j (null = invalid)', (input, expected) => {
		expect(normaliseRadius(input)).toBe(expected);
		expect(migrate({ ...fullState(), radiusKm: input }).radiusKm).toBe(expected ?? 1.5);
	});

	it.each(['de', '', 'HU', null])('language %j falls back to hu', (language) => {
		expect(migrate({ ...fullState(), language }).language).toBe('hu');
	});

	it('drops an invalid plan as a whole', () => {
		const plan = fullState().plan;
		const bad = [
			{ ...plan, days: [] },
			{ ...plan, days: Array.from({ length: 32 }, (_, index) => ({ index: index % 31, meals: {} })) },
			{ ...plan, days: [{ index: 0, meals: { brunch: 'x' } }] },
			{ ...plan, days: [{ index: 0, meals: { ebed: 'Bad Id' } }] },
			{ ...plan, days: [{ index: 0, meals: {} }, { index: 0, meals: {} }] },
			{ ...plan, days: [{ index: 31, meals: {} }] },
			{ ...plan, seed: -1 },
			{ ...plan, slots: 4 },
			{ ...plan, noRepeatDays: 15 },
			{ ...plan, createdAt: 'yesterday' },
			{ ...plan, startDate: '13/10/2026' },
			'plan'
		];
		for (const candidate of bad) expect(migrate({ ...fullState(), plan: candidate }).plan).toBeNull();
	});

	it('cleans pantry, exclusions and checked items entry by entry', () => {
		const state = migrate({
			...fullState(),
			pantry: { notAtHome: ['olaj', 'olaj', 7, 'Ő'] },
			exclusions: { tags: ['hal', 'hal', 'unknown_tag', 3], ingredients: ['tej', 'x'] },
			checkedItems: ['a1', 'a1', 'b2', '', 'C']
		});
		expect(state.pantry).toEqual({ notAtHome: ['olaj'] });
		expect(state.exclusions).toEqual({ tags: ['hal'], ingredients: ['tej'] });
		expect(state.checkedItems).toEqual(['a1', 'b2']);
	});

	it('drops the retired on-hand quantities of older documents (no version bump needed)', () => {
		const state = migrate({
			...fullState(),
			pantry: { onHand: [{ ingredientId: 'liszt', qty: 1 }], notAtHome: ['olaj'] }
		});
		expect(state.pantry).toEqual({ notAtHome: ['olaj'] });
		expect(JSON.stringify(state)).not.toContain('onHand');
	});

	it('cleans the list choices strictly: range, keys, removed ids and store ids', () => {
		const list = (value: unknown) => migrate({ ...fullState(), list: value }).list;
		expect(list(undefined)).toEqual({ range: 'this_week', entries: [] });
		expect(list('x')).toEqual({ range: 'this_week', entries: [] });
		expect(list({ range: 'month', entries: 'x' })).toEqual({ range: 'this_week', entries: [] });
		expect(list({ range: 'whole' })).toEqual({ range: 'whole', entries: [] });
		expect(
			list({
				range: 'next_week',
				entries: [
					{ key: 'ok', removed: ['repa', 'repa', 'BAD!', 7, 'rizs', 'Ő'], storeId: 'bad id!' },
					{ key: 'ok', removed: [], storeId: 'synthetic-aldi-1' },
					{ key: '', removed: [] },
					{ key: 'x'.repeat(81), removed: [] },
					{ key: 'tab\tkey', removed: [] },
					{ key: 'ékezet', removed: [] },
					{ key: 7, removed: [] },
					'not an object',
					null,
					{ key: 'x'.repeat(80), removed: 'nope', storeId: 'synthetic-aldi-1' },
					{ key: ' ~', removed: null, storeId: 'a'.repeat(41) },
					{ key: 'no-store', removed: [] }
				]
			})
		).toEqual({
			range: 'next_week',
			entries: [
				{ key: 'ok', removed: ['repa', 'rizs'], storeId: null },
				{ key: 'x'.repeat(80), removed: [], storeId: 'synthetic-aldi-1' },
				{ key: ' ~', removed: [], storeId: null },
				{ key: 'no-store', removed: [], storeId: null }
			]
		});
	});

	it('keeps at most 12 lists and 200 removed lines per list', () => {
		const ids = Array.from({ length: 250 }, (_, i) => `item_${i}`);
		const entries = Array.from({ length: 20 }, (_, i) => ({ key: `k${i}`, removed: ids, storeId: null }));
		const { list } = migrate({ ...fullState(), list: { range: 'whole', entries } });
		expect(list.entries.map((entry) => entry.key)).toEqual(Array.from({ length: 12 }, (_, i) => `k${i}`));
		expect(list.entries[0]?.removed).toHaveLength(200);
		expect(list.entries[0]?.removed.at(-1)).toBe('item_199');
	});

	it('bounds list sizes', () => {
		const ids = Array.from({ length: 600 }, (_, i) => `item_${i}`);
		const state = migrate({ ...fullState(), checkedItems: ids, exclusions: { tags: [], ingredients: ids } });
		expect(state.checkedItems).toHaveLength(500);
		expect(state.exclusions.ingredients).toHaveLength(50);
	});

	it('keeps a position only with consent, rounded to about 100 m', () => {
		const at = '2026-10-13T08:00:00.000Z';
		const granted = migrate({
			...fullState(),
			location: { consent: 'granted', source: 'device', districtId: null, approx: { lat: 47.4774123, lon: 19.0470987, at } }
		});
		expect(granted.location.approx).toEqual({ lat: 47.477, lon: 19.047, at });

		const unset = migrate({
			...fullState(),
			location: { consent: 'unset', source: 'device', districtId: null, approx: { lat: 47.5, lon: 19.05, at } }
		});
		expect(unset.location).toEqual({ consent: 'unset', source: 'none', districtId: null, approx: null });
	});

	it('falls back to a valid origin source', () => {
		const loc = (location: unknown) => migrate({ ...fullState(), location }).location;
		expect(loc({ consent: 'declined', source: 'device', districtId: '05', approx: null }).source).toBe('district');
		expect(loc({ consent: 'unset', source: 'district', districtId: '24', approx: null })).toEqual({
			consent: 'unset',
			source: 'none',
			districtId: null,
			approx: null
		});
		expect(loc({ consent: 'granted', source: 'satellite', districtId: '23', approx: null }).source).toBe('none');
		expect(loc({ consent: 'maybe', source: 'none', districtId: '00', approx: null }).consent).toBe('unset');
		expect(loc('x')).toEqual(defaultState().location);
	});

	it('rejects impossible coordinates', () => {
		const at = '2026-10-13T08:00:00.000Z';
		for (const approx of [
			{ lat: 91, lon: 19, at },
			{ lat: 47, lon: 181, at },
			{ lat: Number.NaN, lon: 19, at },
			{ lat: 47, lon: 19, at: 'never' },
			{ lat: '47', lon: 19, at }
		]) {
			const state = migrate({ ...fullState(), location: { consent: 'granted', source: 'device', districtId: null, approx } });
			expect(state.location.approx).toBeNull();
			expect(state.location.source).toBe('none');
		}
	});
});

describe('private mode and storage failures', () => {
	it('works in memory when reading throws', () => {
		fake.failGet = true;
		expect(load()).toEqual(defaultState());
		expect(isPersistent()).toBe(false);
	});

	it('keeps the state for the session when writing throws (quota or private mode)', () => {
		fake.failSet = true;
		expect(save({ ...defaultState(), people: 5 })).toBe(false);
		expect(isPersistent()).toBe(false);
		expect(load().people).toBe(5);
		expect(update({ slots: 5 })).toMatchObject({ people: 5, slots: 5 });
		expect(fake.map.size).toBe(0);
	});

	it('never throws when accessing localStorage itself throws', () => {
		vi.unstubAllGlobals();
		Object.defineProperty(globalThis, 'localStorage', {
			configurable: true,
			get() {
				throw new DOMException('blocked', 'SecurityError');
			}
		});
		try {
			expect(load()).toEqual(defaultState());
			expect(save({ ...defaultState(), language: 'en' })).toBe(false);
			expect(load().language).toBe('en');
			expect(clearAll()).toBe(false);
			expect(load()).toEqual(defaultState());
			expect(isPersistent()).toBe(false);
		} finally {
			Reflect.deleteProperty(globalThis, 'localStorage');
		}
	});

	it('works when localStorage does not exist at all', () => {
		vi.stubGlobal('localStorage', undefined);
		expect(load()).toEqual(defaultState());
		expect(update({ people: 6 }).people).toBe(6);
		expect(isPersistent()).toBe(false);
	});

	it('does not revert to the older stored copy after a failed write', () => {
		save(fullState());
		fake.failSet = true;
		update({ people: 9 });
		expect(load().people).toBe(9);
		expect((stored() as StoredState).people).toBe(4);
		fake.failSet = false;
		update({ slots: 3 });
		expect(stored()).toMatchObject({ people: 9, slots: 3 });
	});

	it('returns the defaults when another tab deleted the data', () => {
		save(fullState());
		fake.map.delete(STORAGE_KEY);
		expect(load()).toEqual(defaultState());
	});

	it('becomes persistent again once a write succeeds', () => {
		fake.failSet = true;
		save(defaultState());
		expect(isPersistent()).toBe(false);
		fake.failSet = false;
		save(defaultState());
		expect(isPersistent()).toBe(true);
	});
});

describe('clearAll ("minden adat törlése")', () => {
	it('removes every key of the app and nothing else', () => {
		save(fullState());
		fake.map.set('hetikosar.other', 'x');
		fake.map.set('hetikosar.list', '{"version":1,"range":"whole","lists":[]}');
		fake.map.set('someone-else', 'keep');
		expect(clearAll()).toBe(true);
		expect([...fake.map.keys()]).toEqual(['someone-else']);
		expect(load()).toEqual(defaultState());
	});

	it('also forgets the in-memory copy kept after a failed write', () => {
		fake.failSet = true;
		save(fullState());
		expect(load().people).toBe(4);
		expect(load().list).toEqual(fullState().list);
		clearAll();
		expect(load()).toEqual(defaultState());
	});

	it('resets the session even when the stored copy cannot be deleted, until a write succeeds', () => {
		save(fullState());
		fake.failRemove = true;
		expect(clearAll()).toBe(false);
		// The old copy is still on disk, but this session never shows it again.
		expect(fake.map.has(STORAGE_KEY)).toBe(true);
		expect(load()).toEqual(defaultState());
		expect(isPersistent()).toBe(false);
		expect(update({ people: 3 })).toMatchObject({ people: 3, plan: null, list: { range: 'this_week', entries: [] } });
		// The next successful write replaces the old copy with the cleared state.
		expect(stored()).toMatchObject({ people: 3, plan: null, checkedItems: [] });
		expect(isPersistent()).toBe(true);
	});

	it('resets the session when reading and writing are refused too', () => {
		save(fullState());
		fake.failSet = true;
		update({ people: 9 });
		fake.failGet = true;
		fake.failRemove = true;
		expect(clearAll()).toBe(false);
		expect(load()).toEqual(defaultState());
		expect(isPersistent()).toBe(false);
	});

	it('succeeds when there was nothing stored (writes had been refused)', () => {
		fake.failSet = true;
		save(fullState());
		expect(clearAll()).toBe(true);
		expect(load()).toEqual(defaultState());
	});

	it('resets the session without any localStorage', () => {
		vi.stubGlobal('localStorage', undefined);
		save(fullState());
		expect(load().people).toBe(4);
		expect(clearAll()).toBe(false);
		expect(load()).toEqual(defaultState());
		expect(isPersistent()).toBe(false);
	});
});
