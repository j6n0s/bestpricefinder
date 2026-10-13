import { describe, expect, it } from 'vitest';
import type { StoreOut } from './api/types';
import {
	DEFAULT_GROCERY_CHAINS,
	EARTH_RADIUS_KM,
	MAX_QUOTE_STORES,
	groceryChainSet,
	haversineKm,
	pickNearestPerChain,
	storesWithinRadius,
	type LatLon
} from './geo';

/** Synthetic store (test data only). */
function mk(id: string, chain: string, lat: number | null, lon: number | null, hasData = true): StoreOut {
	return {
		id,
		chain,
		postal_code: '1051',
		city: 'Budapest',
		address: null,
		lat,
		lon,
		format: null,
		is_budapest: true,
		has_data: hasData
	};
}

const ORIGIN: LatLon = { lat: 47.5, lon: 19.05 };
/** A store `km` north of ORIGIN (1° of latitude = 111.195 km on the haversine sphere). */
const north = (km: number): number => ORIGIN.lat + km / ((2 * Math.PI * EARTH_RADIUS_KM) / 360);

describe('haversineKm', () => {
	const DEGREE_KM = (2 * Math.PI * EARTH_RADIUS_KM) / 360;

	it('is 0 for the same point', () => {
		expect(haversineKm(ORIGIN, ORIGIN)).toBe(0);
	});

	it('gives one degree on the equator and on a meridian', () => {
		expect(haversineKm({ lat: 0, lon: 0 }, { lat: 0, lon: 1 })).toBeCloseTo(111.1950802335329, 9);
		expect(haversineKm({ lat: 0, lon: 0 }, { lat: 1, lon: 0 })).toBeCloseTo(DEGREE_KM, 9);
	});

	it('gives a quarter and half of the circumference', () => {
		expect(haversineKm({ lat: 0, lon: 0 }, { lat: 0, lon: 90 })).toBeCloseTo(10007.557221017962, 6);
		expect(haversineKm({ lat: 0, lon: 0 }, { lat: 0, lon: 180 })).toBeCloseTo(20015.114442035923, 6);
		expect(haversineKm({ lat: 90, lon: 0 }, { lat: -90, lon: 0 })).toBeCloseTo(20015.114442035923, 6);
	});

	it('never returns NaN for antipodal points', () => {
		const d = haversineKm({ lat: 10.123, lon: 20.456 }, { lat: -10.123, lon: -159.544 });
		expect(Number.isNaN(d)).toBe(false);
		expect(d).toBeCloseTo(Math.PI * EARTH_RADIUS_KM, 6);
	});

	it('handles the antimeridian', () => {
		expect(haversineKm({ lat: 0, lon: 179.5 }, { lat: 0, lon: -179.5 })).toBeCloseTo(DEGREE_KM, 9);
	});

	it('matches independently computed distances between the BUILD-BRIEF test points', () => {
		const nyugati = { lat: 47.5103, lon: 19.0558 };
		const moricz = { lat: 47.4774, lon: 19.047 };
		const ors = { lat: 47.503, lon: 19.1365 };
		const ujpest = { lat: 47.5603, lon: 19.0906 };
		const hatar = { lat: 47.4658, lon: 19.1262 };
		expect(haversineKm(moricz, nyugati)).toBeCloseTo(3.7175819858456416, 9);
		expect(haversineKm(nyugati, ors)).toBeCloseTo(6.115710488130517, 9);
		expect(haversineKm(ors, ujpest)).toBeCloseTo(7.243678876843788, 9);
		expect(haversineKm(hatar, ujpest)).toBeCloseTo(10.842753652617857, 9);
		expect(haversineKm({ lat: 47.4979, lon: 19.0402 }, { lat: 48.2085, lon: 16.3731 })).toBeCloseTo(214.10488356814994, 8);
	});

	it('is symmetric', () => {
		const a = { lat: 47.4774, lon: 19.047 };
		const b = { lat: 47.5603, lon: 19.0906 };
		expect(haversineKm(a, b)).toBe(haversineKm(b, a));
	});

	it.each([
		[{ lat: Number.NaN, lon: 0 }],
		[{ lat: 0, lon: Number.POSITIVE_INFINITY }],
		[{ lat: 90.0001, lon: 0 }],
		[{ lat: 0, lon: -180.5 }]
	])('rejects invalid coordinates %o', (bad) => {
		expect(() => haversineKm(bad, ORIGIN)).toThrow(RangeError);
		expect(() => haversineKm(ORIGIN, bad)).toThrow(RangeError);
	});
});

describe('storesWithinRadius', () => {
	it('keeps stores at most radius km away, nearest first, ties by id', () => {
		const stores = [
			mk('far', 'lidl', north(2), ORIGIN.lon),
			mk('b-tie', 'aldi', north(0.5), ORIGIN.lon),
			mk('a-tie', 'spar', north(0.5), ORIGIN.lon),
			mk('near', 'penny', north(0.1), ORIGIN.lon)
		];
		const result = storesWithinRadius(ORIGIN, stores, 1.5);
		expect(result.map((r) => r.store.id)).toEqual(['near', 'a-tie', 'b-tie']);
		expect(result[0]?.distanceKm).toBeCloseTo(0.1, 6);
	});

	it('includes a store exactly on the radius and excludes one just outside', () => {
		const store = mk('edge', 'lidl', 47.51, 19.06);
		const d = haversineKm(ORIGIN, { lat: 47.51, lon: 19.06 });
		expect(storesWithinRadius(ORIGIN, [store], d)).toHaveLength(1);
		expect(storesWithinRadius(ORIGIN, [store], d - 1e-9)).toHaveLength(0);
	});

	it('skips stores without valid coordinates', () => {
		const stores = [
			mk('nolat', 'lidl', null, 19.05),
			mk('nolon', 'lidl', 47.5, null),
			mk('nan', 'lidl', Number.NaN, 19.05),
			mk('bad', 'lidl', 123, 19.05),
			mk('ok', 'lidl', 47.5, 19.05)
		];
		expect(storesWithinRadius(ORIGIN, stores, 5).map((r) => r.store.id)).toEqual(['ok']);
	});

	it('radius 0 keeps only stores at the origin', () => {
		const stores = [mk('here', 'lidl', ORIGIN.lat, ORIGIN.lon), mk('there', 'lidl', north(0.01), ORIGIN.lon)];
		expect(storesWithinRadius(ORIGIN, stores, 0).map((r) => r.store.id)).toEqual(['here']);
	});

	it.each([-1, Number.NaN, Number.POSITIVE_INFINITY])('rejects radius %s', (radius) => {
		expect(() => storesWithinRadius(ORIGIN, [], radius)).toThrow(RangeError);
	});

	it('rejects an invalid origin', () => {
		expect(() => storesWithinRadius({ lat: 100, lon: 0 }, [], 1)).toThrow(RangeError);
	});

	it('does not mutate its input', () => {
		const stores = [mk('b', 'lidl', north(1), ORIGIN.lon), mk('a', 'lidl', north(0.5), ORIGIN.lon)];
		const copy = structuredClone(stores);
		storesWithinRadius(ORIGIN, stores, 5);
		expect(stores).toEqual(copy);
	});
});

describe('pickNearestPerChain', () => {
	const lidl = [0.1, 0.2, 0.3, 0.4, 0.5].map((km, i) => mk(`lidl-${i}`, 'lidl', north(km), ORIGIN.lon));

	it('keeps the 3 nearest stores per chain by default', () => {
		const result = pickNearestPerChain(ORIGIN, lidl, { radiusKm: 1.5 });
		expect(result.map((r) => r.store.id)).toEqual(['lidl-0', 'lidl-1', 'lidl-2']);
	});

	it('honours maxPerChain', () => {
		expect(pickNearestPerChain(ORIGIN, lidl, { radiusKm: 1.5, maxPerChain: 1 }).map((r) => r.store.id)).toEqual([
			'lidl-0'
		]);
		expect(pickNearestPerChain(ORIGIN, lidl, { radiusKm: 1.5, maxPerChain: 10 })).toHaveLength(5);
	});

	it('respects the radius before choosing', () => {
		expect(pickNearestPerChain(ORIGIN, lidl, { radiusKm: 0.25 }).map((r) => r.store.id)).toEqual(['lidl-0', 'lidl-1']);
	});

	it('drops drugstores unless groceryOnly is false', () => {
		const stores = [mk('dm-1', 'dm', north(0.05), ORIGIN.lon), mk('spar-1', 'spar', north(0.2), ORIGIN.lon)];
		expect(pickNearestPerChain(ORIGIN, stores, { radiusKm: 1 }).map((r) => r.store.id)).toEqual(['spar-1']);
		expect(pickNearestPerChain(ORIGIN, stores, { radiusKm: 1, groceryOnly: false }).map((r) => r.store.id)).toEqual([
			'dm-1',
			'spar-1'
		]);
	});

	it('drops stores without price data unless hasDataOnly is false', () => {
		const stores = [mk('spar-nodata', 'spar', north(0.05), ORIGIN.lon, false), mk('spar-ok', 'spar', north(0.2), ORIGIN.lon)];
		expect(pickNearestPerChain(ORIGIN, stores, { radiusKm: 1 }).map((r) => r.store.id)).toEqual(['spar-ok']);
		expect(pickNearestPerChain(ORIGIN, stores, { radiusKm: 1, hasDataOnly: false }).map((r) => r.store.id)).toEqual([
			'spar-nodata',
			'spar-ok'
		]);
	});

	it('a store without data does not use up its chain quota', () => {
		const stores = [
			mk('spar-nodata', 'spar', north(0.01), ORIGIN.lon, false),
			...[0.1, 0.2, 0.3].map((km, i) => mk(`spar-${i}`, 'spar', north(km), ORIGIN.lon))
		];
		expect(pickNearestPerChain(ORIGIN, stores, { radiusKm: 1 }).map((r) => r.store.id)).toEqual([
			'spar-0',
			'spar-1',
			'spar-2'
		]);
	});

	it('uses the grocery chain list from /api/meta when given', () => {
		const stores = [mk('x-1', 'newchain', north(0.1), ORIGIN.lon), mk('lidl-x', 'lidl', north(0.2), ORIGIN.lon)];
		const chains = groceryChainSet([
			{ slug: 'newchain', is_grocery: true },
			{ slug: 'lidl', is_grocery: false }
		]);
		expect(pickNearestPerChain(ORIGIN, stores, { radiusKm: 1, groceryChains: chains }).map((r) => r.store.id)).toEqual([
			'x-1'
		]);
	});

	it('round-robins chains when maxTotal is reached, so a dense chain cannot crowd out the others', () => {
		const dense = [0.01, 0.02, 0.03].map((km, i) => mk(`spar-${i}`, 'spar', north(km), ORIGIN.lon));
		const others = [
			mk('lidl-0', 'lidl', north(0.9), ORIGIN.lon),
			mk('aldi-0', 'aldi', north(1.0), ORIGIN.lon),
			mk('penny-0', 'penny', north(1.1), ORIGIN.lon)
		];
		const result = pickNearestPerChain(ORIGIN, [...dense, ...others], { radiusKm: 2, maxTotal: 4 });
		expect(result.map((r) => r.store.id)).toEqual(['spar-0', 'lidl-0', 'aldi-0', 'penny-0']);
	});

	it('within a round prefers the nearer chains', () => {
		const stores = ['aldi', 'lidl', 'penny'].map((chain, i) => mk(`${chain}-0`, chain, north(0.1 * (i + 1)), ORIGIN.lon));
		expect(pickNearestPerChain(ORIGIN, stores, { radiusKm: 1, maxTotal: 2 }).map((r) => r.store.id)).toEqual([
			'aldi-0',
			'lidl-0'
		]);
	});

	it('never returns more than 25 stores (the /api/quote limit)', () => {
		const slugs = Array.from({ length: 12 }, (_, i) => `chain${i}`);
		const stores = slugs.flatMap((slug, c) =>
			[0, 1, 2].map((k) => mk(`${slug}-${k}`, slug, north(0.01 * (c * 3 + k + 1)), ORIGIN.lon))
		);
		const result = pickNearestPerChain(ORIGIN, stores, { radiusKm: 5, maxTotal: 100, groceryChains: new Set(slugs) });
		expect(result).toHaveLength(MAX_QUOTE_STORES);
		// Every chain keeps at least its nearest store.
		expect(new Set(result.map((r) => r.store.chain)).size).toBe(12);
	});

	it('returns the result nearest first', () => {
		const stores = [
			mk('aldi-far', 'aldi', north(1.2), ORIGIN.lon),
			mk('lidl-mid', 'lidl', north(0.6), ORIGIN.lon),
			mk('spar-near', 'spar', north(0.1), ORIGIN.lon)
		];
		const distances = pickNearestPerChain(ORIGIN, stores, { radiusKm: 2 }).map((r) => r.distanceKm);
		expect(distances).toEqual([...distances].sort((a, b) => a - b));
	});

	it('returns an empty list when nothing is in range', () => {
		expect(pickNearestPerChain(ORIGIN, lidl, { radiusKm: 0.05 })).toEqual([]);
	});

	it.each([
		[{ maxPerChain: 0 }],
		[{ maxPerChain: 1.5 }],
		[{ maxTotal: 0 }],
		[{ maxTotal: Number.NaN }]
	])('rejects invalid limits %o', (limits) => {
		expect(() => pickNearestPerChain(ORIGIN, lidl, { radiusKm: 1, ...limits })).toThrow(RangeError);
	});
});

describe('groceryChainSet', () => {
	it('falls back to the six grocery chains when meta has none', () => {
		expect(groceryChainSet([])).toBe(DEFAULT_GROCERY_CHAINS);
		expect([...DEFAULT_GROCERY_CHAINS].sort()).toEqual(['aldi', 'auchan', 'lidl', 'penny', 'spar', 'tesco']);
	});
});
