// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { ListLineOut, StoreQuoteOut } from '../api/types';
import { STORAGE_KEY, clearAll, load, resetForTests } from '../storage';
import { isConnectionError, saveLastList, saveLastQuote, savedListFor, savedQuoteFor } from './offline';

class MapStorage implements Storage {
	readonly map = new Map<string, string>();
	writes = 0;
	get length(): number {
		return this.map.size;
	}
	clear(): void {
		this.map.clear();
	}
	getItem(key: string): string | null {
		return this.map.get(key) ?? null;
	}
	key(index: number): string | null {
		return [...this.map.keys()][index] ?? null;
	}
	removeItem(key: string): void {
		this.map.delete(key);
	}
	setItem(key: string, value: string): void {
		this.writes += 1;
		this.map.set(key, String(value));
	}
}

let fake: MapStorage;

beforeEach(() => {
	resetForTests();
	fake = new MapStorage();
	vi.stubGlobal('localStorage', fake);
});

afterEach(() => {
	vi.unstubAllGlobals();
	resetForTests();
});

const NOW = new Date('2026-10-13T08:00:00.000Z');
const BODY = '{"items":[{"recipe_id":"minta-lencsefozelek","servings":14}]}';
const LINES: ListLineOut[] = [
	{ ingredient_id: 'voros_lencse', name_hu: 'vörös lencse', qty: 0.4, unit: 'kg', list_group: 'szaraz_tartos', pantry: false, recipe_ids: ['minta-lencsefozelek'] }
];
const STORE: StoreQuoteOut = {
	store_id: 'synthetic-lidl-a',
	chain: 'lidl',
	checkout_total: 899,
	used_total: 719,
	missing: [],
	assumed_count: 0,
	ksh_estimate_total: 0,
	lines: [
		{
			ingredient_id: 'voros_lencse',
			qty: 0.4,
			unit: 'kg',
			status: 'priced',
			picks: [],
			checkout_cost: 899,
			used_cost: 719,
			leftover_qty: 0.1,
			ksh_estimate: null,
			alternatives: []
		}
	]
};
const offline = new ApiError({ kind: 'offline' });

describe('isConnectionError', () => {
	it('is true for offline, network and timeout only', () => {
		expect(isConnectionError(offline)).toBe(true);
		expect(isConnectionError(new ApiError({ kind: 'network' }))).toBe(true);
		expect(isConnectionError(new ApiError({ kind: 'timeout' }))).toBe(true);
		expect(isConnectionError(new ApiError({ kind: 'http', status: 500 }))).toBe(false);
		expect(isConnectionError(new ApiError({ kind: 'invalid_response' }))).toBe(false);
		expect(isConnectionError(new ApiError({ kind: 'aborted' }))).toBe(false);
		expect(isConnectionError(new Error('offline'))).toBe(false);
	});
});

describe('the last list', () => {
	it('round-trips in the one stored document, for exactly its request', () => {
		saveLastList(BODY, LINES, NOW);
		expect([...fake.map.keys()]).toEqual([STORAGE_KEY]);
		expect(savedListFor(BODY, offline)).toEqual({ body: BODY, savedAt: NOW.toISOString(), lines: LINES });
		expect(savedListFor(`${BODY} `, offline)).toBeNull();
	});

	it('is used only when the request failed for lack of a connection', () => {
		saveLastList(BODY, LINES, NOW);
		expect(savedListFor(BODY, new ApiError({ kind: 'http', status: 422 }))).toBeNull();
		expect(savedListFor(BODY, new ApiError({ kind: 'invalid_response' }))).toBeNull();
	});

	it('accepts Proxy objects such as Svelte $state, and malformed lines are not kept', () => {
		saveLastList(BODY, new Proxy(LINES.map((line) => new Proxy(line, {})), {}), NOW);
		expect(savedListFor(BODY, offline)?.lines).toEqual(LINES);
		saveLastList(BODY, [{ ...LINES[0], qty: 'sok' } as unknown as ListLineOut], NOW);
		expect(savedListFor(BODY, offline)).toBeNull();
	});

	it('is wiped by "Minden adat törlése"', () => {
		saveLastList(BODY, LINES, NOW);
		clearAll();
		expect(load().lastList).toBeNull();
		expect(savedListFor(BODY, offline)).toBeNull();
	});
});

describe('the chosen store’s last quote', () => {
	const quoteBody = '{"lines":[{"ingredient_id":"voros_lencse","qty":0.4}],"store_ids":["synthetic-lidl-a"],"include_loyalty":false}';

	it('keeps the store, its data date and the request it answers', () => {
		saveLastQuote(quoteBody, '2026-10-13', new Proxy(STORE, {}), NOW);
		expect(savedQuoteFor(quoteBody, offline)).toEqual({ body: quoteBody, savedAt: NOW.toISOString(), dataDate: '2026-10-13', store: STORE });
		expect(savedQuoteFor('{}', offline)).toBeNull();
		expect(savedQuoteFor(quoteBody, new ApiError({ kind: 'http', status: 503 }))).toBeNull();
	});

	it('is not rewritten when the same copy is already stored', () => {
		saveLastQuote(quoteBody, '2026-10-13', STORE, NOW);
		const writes = fake.writes;
		saveLastQuote(quoteBody, '2026-10-13', STORE, new Date('2026-10-13T09:00:00.000Z'));
		expect(fake.writes).toBe(writes);
		saveLastQuote(quoteBody, '2026-10-13', { ...STORE, store_id: 'synthetic-aldi-a', chain: 'aldi' }, NOW);
		expect(fake.writes).toBe(writes + 1);
		expect(load().lastQuote?.store.store_id).toBe('synthetic-aldi-a');
	});

	it('is wiped by "Minden adat törlése"', () => {
		saveLastQuote(quoteBody, '2026-10-13', STORE, NOW);
		clearAll();
		expect(load().lastQuote).toBeNull();
	});
});
