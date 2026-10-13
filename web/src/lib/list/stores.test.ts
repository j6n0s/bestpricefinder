// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { StoreOut } from '../api/types';
import { formatDistance } from '../format';
import { DEFAULT_GROCERY_CHAINS, EARTH_RADIUS_KM, type LatLon } from '../geo';
import { chainLabel, chainNames, distanceMap, nearbyCandidates, storeAddress, widerRadius } from './stores';

const ORIGIN: LatLon = { lat: 47.5, lon: 19.05 };
const KM_PER_DEGREE = (2 * Math.PI * EARTH_RADIUS_KM) / 360;
const north = (km: number): number => ORIGIN.lat + km / KM_PER_DEGREE;

function store(id: string, chain: string, km: number, hasData = true): StoreOut {
	return {
		id,
		chain,
		postal_code: '1051',
		city: 'Budapest',
		address: `Minta utca ${id.length}.`,
		lat: north(km),
		lon: ORIGIN.lon,
		format: null,
		is_budapest: true,
		has_data: hasData
	};
}

describe('nearbyCandidates', () => {
	it('keeps grocery stores with data in the radius, at most 3 per chain, nearest first', () => {
		const stores = [
			store('lidl-4', 'lidl', 1.4),
			store('lidl-1', 'lidl', 0.2),
			store('lidl-3', 'lidl', 0.9),
			store('lidl-2', 'lidl', 0.5),
			store('aldi-1', 'aldi', 0.3),
			store('spar-nodata', 'spar', 0.1, false),
			store('dm-1', 'dm', 0.05),
			store('penny-far', 'penny', 1.6)
		];
		const result = nearbyCandidates(ORIGIN, stores, 1.5, DEFAULT_GROCERY_CHAINS);
		expect(result.picks.map((p) => p.store.id)).toEqual(['lidl-1', 'aldi-1', 'lidl-2', 'lidl-3']);
		expect(result.tooFew).toBe(false);
		expect(result.withoutData).toBe(1);
		expect(result.picks[0]?.distanceKm).toBeCloseTo(0.2, 6);
	});

	it('includes a store just inside the radius and leaves out one just outside', () => {
		const result = nearbyCandidates(ORIGIN, [store('a', 'aldi', 1.4999), store('b', 'lidl', 1.5001)], 1.5, DEFAULT_GROCERY_CHAINS);
		expect(result.picks.map((p) => p.store.id)).toEqual(['a']);
	});

	it('flags fewer than 2 stores as too few', () => {
		expect(nearbyCandidates(ORIGIN, [], 1.5, DEFAULT_GROCERY_CHAINS)).toEqual({ picks: [], tooFew: true, withoutData: 0 });
		const one = nearbyCandidates(ORIGIN, [store('a', 'aldi', 0.4), store('b', 'lidl', 3)], 1.5, DEFAULT_GROCERY_CHAINS);
		expect(one.picks).toHaveLength(1);
		expect(one.tooFew).toBe(true);
	});

	it('caps the candidates at 25 (the /api/quote limit)', () => {
		const chains = ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8', 'c9', 'c10'];
		const stores = chains.flatMap((chain, c) => [0, 1, 2].map((n) => store(`${chain}-${n}`, chain, 0.01 * (c * 3 + n + 1))));
		const result = nearbyCandidates(ORIGIN, stores, 5, new Set(chains));
		expect(result.picks).toHaveLength(25);
		// Every chain keeps its nearest store before any chain gets a third one.
		expect(new Set(result.picks.map((p) => p.store.chain)).size).toBe(10);
	});

	it('uses the grocery chain list it is given', () => {
		const result = nearbyCandidates(ORIGIN, [store('dm-1', 'dm', 0.1), store('aldi-1', 'aldi', 0.2)], 1, new Set(['dm']));
		expect(result.picks.map((p) => p.store.id)).toEqual(['dm-1']);
	});
});

describe('widerRadius', () => {
	it('steps up by 0.5 km up to 5 km', () => {
		expect(widerRadius(1.5)).toBe(2);
		expect(widerRadius(0.5)).toBe(1);
		expect(widerRadius(4.5)).toBe(5);
		expect(widerRadius(5)).toBeNull();
		expect(widerRadius(Number.NaN)).toBeNull();
	});
});

describe('distanceMap', () => {
	it('maps store ids to distances', () => {
		const result = nearbyCandidates(ORIGIN, [store('a', 'aldi', 0.4), store('b', 'lidl', 1)], 1.5, DEFAULT_GROCERY_CHAINS);
		const map = distanceMap(result.picks);
		expect(map.get('a')).toBeCloseTo(0.4, 6);
		expect(map.get('b')).toBeCloseTo(1, 6);
		expect(map.has('c')).toBe(false);
	});
});

describe('distance labels', () => {
	it('labels the on-device distances in metres below 1 km and in km with one decimal above', () => {
		const result = nearbyCandidates(
			ORIGIN,
			[store('a', 'aldi', 0.2), store('b', 'lidl', 0.999), store('c', 'spar', 1.0), store('d', 'penny', 1.46)],
			1.5,
			DEFAULT_GROCERY_CHAINS
		);
		expect(result.picks.map((p) => formatDistance(p.distanceKm).replaceAll('\u00a0', ' '))).toEqual([
			'200 m',
			'1,0 km',
			'1,0 km',
			'1,5 km'
		]);
	});
});

describe('storeAddress', () => {
	it('joins the parts that exist', () => {
		expect(storeAddress({ postal_code: '1051', city: 'Budapest', address: 'Minta utca 1.' })).toBe(
			'1051 Budapest, Minta utca 1.'
		);
		expect(storeAddress({ postal_code: null, city: 'Budapest', address: 'Minta utca 1.' })).toBe('Budapest, Minta utca 1.');
		expect(storeAddress({ postal_code: '1051', city: null, address: null })).toBe('1051');
		expect(storeAddress({ postal_code: ' ', city: null, address: ' ' })).toBe('');
		expect(storeAddress(undefined)).toBe('');
	});
});

describe('chainLabel', () => {
	it('uses the name from /api/meta and falls back to the slug', () => {
		const names = chainNames([
			{ slug: 'lidl', name: 'Lidl' },
			{ slug: 'muller', name: 'Müller' }
		]);
		expect(chainLabel('lidl', names)).toBe('Lidl');
		expect(chainLabel('muller', names)).toBe('Müller');
		expect(chainLabel('newchain', names)).toBe('newchain');
		expect(chainLabel('lidl', chainNames(null))).toBe('lidl');
	});
});
