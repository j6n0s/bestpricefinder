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
	onExternalChange,
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
	preferencesAsked: true,
	location: { consent: 'granted', source: 'device', districtId: '11', approx: { lat: 47.477, lon: 19.047, at: '2026-10-13T08:00:00.000Z' } },
	list: {
		range: 'next_week',
		entries: [
			{
				key: '2026-10-13T08:00:00.000Z|next_week',
				checked: ['lencse', 'voroshagyma'],
				removed: ['repa', 'rizs'],
				included: ['tej'],
				storeId: 'synthetic-lidl-1'
			},
			{ key: '2026-10-13T08:00:00.000Z|whole', checked: [], removed: [], included: [], storeId: null }
		]
	},
	lastList: {
		body: '{"items":[{"recipe_id":"lencsefozelek","servings":2}]}',
		savedAt: '2026-10-13T08:05:00.000Z',
		lines: [
			{
				ingredient_id: 'voros_lencse',
				name_hu: 'vörös lencse',
				qty: 0.2,
				unit: 'kg',
				list_group: 'szaraz_tartos',
				pantry: false,
				recipe_ids: ['lencsefozelek']
			}
		]
	},
	lastQuote: {
		body: '{"lines":[{"ingredient_id":"voros_lencse","qty":0.2}],"store_ids":["synthetic-lidl-1"],"include_loyalty":false}',
		savedAt: '2026-10-13T08:06:00.000Z',
		dataDate: '2026-10-13',
		store: {
			store_id: 'synthetic-lidl-1',
			chain: 'lidl',
			checkout_total: 899,
			used_total: 360,
			missing: [],
			assumed_count: 0,
			ksh_estimate_total: 0,
			lines: [
				{
					ingredient_id: 'voros_lencse',
					qty: 0.2,
					unit: 'kg',
					status: 'priced',
					picks: [
						{
							option: {
								product_id: 'synthetic-lencse-0.5',
								product_name: 'Szintetikus vörös lencse',
								pack_size: 0.5,
								pack_price: 899,
								unit_price: 1798,
								price_type: 'NORMAL',
								price_scope: 'chain',
								availability: 'confirmed'
							},
							count: 1,
							qty: 0.5,
							cost: 899
						}
					],
					checkout_cost: 899,
					used_cost: 360,
					leftover_qty: 0.3,
					ksh_estimate: null,
					alternatives: []
				}
			]
		}
	},
	cart: { lines: [{ ingredientId: 'alma', qty: 0.75 }, { ingredientId: 'tojas', qty: 10 }], checked: ['alma'], storeId: 'synthetic-lidl-1' }
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
		state.list.entries[0]?.checked.push('x');
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

	it('cleans pantry and exclusions entry by entry', () => {
		const state = migrate({
			...fullState(),
			pantry: { notAtHome: ['olaj', 'olaj', 7, 'Ő'] },
			exclusions: { tags: ['hal', 'hal', 'unknown_tag', 3], ingredients: ['tej', 'x'] }
		});
		expect(state.pantry).toEqual({ notAtHome: ['olaj'] });
		expect(state.exclusions).toEqual({ tags: ['hal'], ingredients: ['tej'] });
	});

	it('drops the global ticks of earlier builds: ticks belong to one list (no version bump needed)', () => {
		const state = migrate({ ...fullState(), checkedItems: ['voroshagyma', 'kenyer'] });
		expect(JSON.stringify(state)).not.toContain('checkedItems');
		expect(state.list.entries[0]?.checked).toEqual(['lencse', 'voroshagyma']);
	});

	it('cleans the ticks and the "bought anyway" ids of each list; older entries without them get []', () => {
		const entry = (value: Record<string, unknown>) =>
			migrate({ ...fullState(), list: { range: 'whole', entries: [{ key: 'k', storeId: null, ...value }] } }).list.entries[0];
		expect(entry({ removed: ['repa'] })).toEqual({ key: 'k', checked: [], removed: ['repa'], included: [], storeId: null });
		expect(entry({ checked: ['a1', 'a1', 'b2', '', 'C', 7], included: ['tej', 'tej', 'BAD!'] })).toEqual({
			key: 'k',
			checked: ['a1', 'b2'],
			removed: [],
			included: ['tej'],
			storeId: null
		});
		expect(entry({ checked: 'x', included: null })).toMatchObject({ checked: [], included: [] });
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
				{ key: 'ok', checked: [], removed: ['repa', 'rizs'], included: [], storeId: null },
				{ key: 'x'.repeat(80), checked: [], removed: [], included: [], storeId: 'synthetic-aldi-1' },
				{ key: ' ~', checked: [], removed: [], included: [], storeId: null },
				{ key: 'no-store', checked: [], removed: [], included: [], storeId: null }
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
		const state = migrate({
			...fullState(),
			list: { range: 'whole', entries: [{ key: 'k', checked: ids, removed: [], included: ids, storeId: null }] },
			exclusions: { tags: [], ingredients: ids }
		});
		expect(state.list.entries[0]?.checked).toHaveLength(500);
		expect(state.list.entries[0]?.included).toHaveLength(50);
		expect(state.exclusions.ingredients).toHaveLength(50);
	});

	it('keeps the offline copies only when they are well formed', () => {
		const full = fullState();
		const lastList = (value: unknown) => migrate({ ...full, lastList: value }).lastList;
		const lastQuote = (value: unknown) => migrate({ ...full, lastQuote: value }).lastQuote;
		expect(lastList(full.lastList)).toEqual(full.lastList);
		expect(lastQuote(full.lastQuote)).toEqual(full.lastQuote);
		const line = full.lastList?.lines[0];
		for (const bad of [
			undefined,
			'x',
			{ ...full.lastList, body: '' },
			{ ...full.lastList, body: 'x'.repeat(65_537) },
			{ ...full.lastList, savedAt: 'yesterday' },
			{ ...full.lastList, lines: 'x' },
			{ ...full.lastList, lines: [{ ...line, qty: '0.2' }] },
			{ ...full.lastList, lines: Array.from({ length: 501 }, (_, i) => ({ ...line, ingredient_id: `item_${i}` })) }
		]) {
			expect(lastList(bad)).toBeNull();
		}
		const store = full.lastQuote?.store;
		for (const bad of [
			undefined,
			{ ...full.lastQuote, dataDate: '13/10/2026' },
			{ ...full.lastQuote, savedAt: 7 },
			{ ...full.lastQuote, body: 7 },
			{ ...full.lastQuote, store: { ...store, store_id: 'bad id!' } },
			{ ...full.lastQuote, store: { ...store, checkout_total: '899' } },
			{ ...full.lastQuote, store: { ...store, lines: [{ ...store?.lines[0], status: 'akcio' }] } }
		]) {
			expect(lastQuote(bad)).toBeNull();
		}
		// Duplicate list lines are dropped (keyed lists).
		expect(lastList({ ...full.lastList, lines: [line, line] })?.lines).toHaveLength(1);
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

describe('the first-visit question', () => {
	it('is not answered by default, and an old document without the field asks it once', () => {
		expect(load().preferencesAsked).toBe(false);
		const { preferencesAsked: _dropped, ...old } = fullState();
		fake.map.set(STORAGE_KEY, JSON.stringify(old));
		resetForTests();
		expect(load().preferencesAsked).toBe(false);
		expect(load().exclusions).toEqual(fullState().exclusions);
	});

	it('is kept only as true, and "Minden adat törlése" asks it again', () => {
		for (const bad of ['true', 1, null, {}]) {
			fake.map.set(STORAGE_KEY, JSON.stringify({ ...fullState(), preferencesAsked: bad }));
			resetForTests();
			expect(load().preferencesAsked).toBe(false);
		}
		expect(update({ preferencesAsked: true }).preferencesAsked).toBe(true);
		expect((stored() as StoredState).preferencesAsked).toBe(true);
		clearAll();
		expect(load().preferencesAsked).toBe(false);
	});
});

describe('the cart', () => {
	it('defaults to an empty cart, and an old document without one gets it', () => {
		expect(defaultState().cart).toEqual({ lines: [], checked: [], storeId: null });
		const { cart: _dropped, ...withoutCart } = fullState();
		expect(migrate(withoutCart).cart).toEqual({ lines: [], checked: [], storeId: null });
	});

	it('keeps valid lines and drops invalid, repeated or out-of-range ones', () => {
		const cart = migrate({
			...fullState(),
			cart: {
				lines: [
					{ ingredientId: 'alma', qty: 0.5 },
					{ ingredientId: 'alma', qty: 2 }, // repeated: the first one wins
					{ ingredientId: 'tej', qty: 1.23456 }, // rounded to 0.001
					{ ingredientId: 'Bad Id!', qty: 1 },
					{ ingredientId: 'sajt', qty: 0 },
					{ ingredientId: 'vaj', qty: -1 },
					{ ingredientId: 'liszt', qty: 1001 },
					{ ingredientId: 'rizs', qty: '1' },
					{ ingredientId: 'tojas', qty: Number.NaN },
					'nonsense',
					{ ingredientId: 'kenyer', qty: 1000 }
				],
				checked: ['alma', 'alma', 'Bad Id!', 'tej'],
				storeId: 'spar-110'
			}
		}).cart;
		expect(cart.lines).toEqual([
			{ ingredientId: 'alma', qty: 0.5 },
			{ ingredientId: 'tej', qty: 1.235 },
			{ ingredientId: 'kenyer', qty: 1000 }
		]);
		expect(cart.checked).toEqual(['alma', 'tej']);
		expect(cart.storeId).toBe('spar-110');
	});

	it('keeps at most 100 goods, and drops a bad store id or a cart that is not an object', () => {
		const lines = Array.from({ length: 150 }, (_, i) => ({ ingredientId: `g${i}`, qty: 1 }));
		expect(migrate({ ...fullState(), cart: { lines, checked: [], storeId: 'bad id' } }).cart).toMatchObject({
			storeId: null
		});
		expect(migrate({ ...fullState(), cart: { lines, checked: [], storeId: null } }).cart.lines).toHaveLength(100);
		expect(migrate({ ...fullState(), cart: [] }).cart).toEqual({ lines: [], checked: [], storeId: null });
	});

	it('survives a save and load, and "Minden adat törlése" empties it', () => {
		update({ cart: { lines: [{ ingredientId: 'alma', qty: 0.75 }], checked: ['alma'], storeId: 'lidl-274' } });
		expect(load().cart).toEqual({ lines: [{ ingredientId: 'alma', qty: 0.75 }], checked: ['alma'], storeId: 'lidl-274' });
		clearAll();
		expect(load().cart).toEqual({ lines: [], checked: [], storeId: null });
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
		expect(stored()).toMatchObject({ people: 3, plan: null, list: { entries: [] }, lastList: null, lastQuote: null });
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

describe('onExternalChange (another tab)', () => {
	/** A window double: the storage module listens to its `storage` events. */
	function fakeWindow(): EventTarget {
		const target = new EventTarget();
		vi.stubGlobal('window', target);
		return target;
	}

	function storageEvent(key: string | null, area: Storage = fake): Event {
		return Object.assign(new Event('storage'), { key, storageArea: area });
	}

	it('drops the in-memory copy and reports the defaults when another tab deleted everything', () => {
		const win = fakeWindow();
		save(fullState());
		const seen: StoredState[] = [];
		const stop = onExternalChange((state) => seen.push(state));
		fake.map.clear(); // "Minden adat törlése" in the other tab
		win.dispatchEvent(storageEvent(STORAGE_KEY));
		expect(seen).toEqual([defaultState()]);
		expect(load()).toEqual(defaultState());
		stop();
		win.dispatchEvent(storageEvent(STORAGE_KEY));
		expect(seen).toHaveLength(1);
	});

	it('reports what the other tab stored, also after localStorage.clear() (key null)', () => {
		const win = fakeWindow();
		const seen: number[] = [];
		onExternalChange((state) => seen.push(state.people));
		fake.map.set(STORAGE_KEY, JSON.stringify({ ...fullState(), people: 7 }));
		win.dispatchEvent(storageEvent(null));
		expect(seen).toEqual([7]);
	});

	it('even the copy this tab could not write gives way to the other tab', () => {
		const win = fakeWindow();
		save(fullState());
		fake.failSet = true;
		update({ people: 9 }); // kept in memory only
		expect(load().people).toBe(9);
		fake.failSet = false;
		fake.map.delete(STORAGE_KEY);
		const seen: StoredState[] = [];
		onExternalChange((state) => seen.push(state));
		win.dispatchEvent(storageEvent(STORAGE_KEY));
		expect(seen[0]).toEqual(defaultState());
	});

	it('ignores other keys and other storage areas', () => {
		const win = fakeWindow();
		const seen: unknown[] = [];
		onExternalChange((state) => seen.push(state));
		win.dispatchEvent(storageEvent('other.app'));
		win.dispatchEvent(storageEvent(STORAGE_KEY, new FakeStorage()));
		expect(seen).toEqual([]);
	});

	it('is a no-op without a window', () => {
		vi.stubGlobal('window', undefined);
		const stop = onExternalChange(() => {
			throw new Error('never called');
		});
		expect(() => stop()).not.toThrow();
	});
});
