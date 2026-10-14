import { describe, expect, it } from 'vitest';
import { haversineKm, type LatLon } from '../geo';
import {
	DEFAULT_JOURNEY_OPTIONS,
	journeySaving,
	planShopping,
	type JourneyOptions,
	type JourneyStore,
	type ShoppingPlan
} from './journey';

/** Nyugati tér (BUILD-BRIEF §10). */
const ORIGIN: LatLon = { lat: 47.5103, lon: 19.0558 };

/** A point `northKm` north and `eastKm` east of ORIGIN. */
function at(northKm: number, eastKm: number): LatLon {
	return {
		lat: ORIGIN.lat + northKm / 111.32,
		lon: ORIGIN.lon + eastKm / (111.32 * Math.cos((ORIGIN.lat * Math.PI) / 180))
	};
}

function store(id: string, point: LatLon, costs: Record<string, number>): JourneyStore {
	return { id, point, costs: new Map(Object.entries(costs)) };
}

const LINES = ['tej', 'kenyer', 'alma', 'sajt'];

describe('planShopping: the single store', () => {
	it('picks the store that sells everything, even when another is cheaper for what it has', () => {
		const full = store('full', at(0.3, 0), { tej: 400, kenyer: 600, alma: 500, sajt: 900 });
		const cheapButPartial = store('partial', at(0.2, 0), { tej: 300, kenyer: 500, alma: 400 });
		const result = planShopping(ORIGIN, LINES, [cheapButPartial, full]);
		expect(result.single?.stops.map((s) => s.storeId)).toEqual(['full']);
		expect(result.single?.missing).toEqual([]);
		expect(result.single?.total).toBe(2400);
	});

	it('with equal coverage, the lower price wins; with equal prices, the nearer store', () => {
		const near = store('near', at(0.2, 0), { tej: 400, kenyer: 600 });
		const far = store('far', at(1.0, 0), { tej: 400, kenyer: 600 });
		const cheaper = store('cheaper', at(1.2, 0), { tej: 100, kenyer: 600 });
		expect(planShopping(ORIGIN, ['tej', 'kenyer'], [far, near]).single?.stops[0]?.storeId).toBe('near');
		expect(planShopping(ORIGIN, ['tej', 'kenyer'], [far, near, cheaper]).single?.stops[0]?.storeId).toBe('cheaper');
	});

	it('walking counts: a store 2 km further must save more than 2 × 2 × 150 Ft', () => {
		const near = store('near', at(0.1, 0), { tej: 1000 });
		const farSaving500 = store('far', at(2.1, 0), { tej: 500 });
		const farSaving700 = store('far2', at(2.1, 0.0001), { tej: 300 });
		expect(planShopping(ORIGIN, ['tej'], [near, farSaving500]).single?.stops[0]?.storeId).toBe('near');
		expect(planShopping(ORIGIN, ['tej'], [near, farSaving700]).single?.stops[0]?.storeId).toBe('far2');
	});

	it('reports the lines the store does not sell, in input order', () => {
		const only = store('only', at(0.1, 0), { kenyer: 500 });
		const result = planShopping(ORIGIN, LINES, [only]);
		expect(result.single?.missing).toEqual(['tej', 'alma', 'sajt']);
		expect(result.journey).toBeNull();
		expect(result.bestMulti).toBeNull();
	});
});

describe('planShopping: the journey', () => {
	it('goes to a second store for what the first one does not sell', () => {
		const a = store('a', at(0.3, 0), { tej: 400, kenyer: 600, alma: 500 });
		const b = store('b', at(0.3, 0.3), { sajt: 900, tej: 450 });
		const result = planShopping(ORIGIN, LINES, [a, b]);
		expect(result.single?.missing).toEqual(['sajt']);
		expect(result.journey?.missing).toEqual([]);
		expect(result.journey?.stops.map((s) => [s.storeId, s.items])).toEqual(
			expect.arrayContaining([
				['a', ['tej', 'kenyer', 'alma']],
				['b', ['sajt']]
			])
		);
		expect(result.journey?.total).toBe(2400);
	});

	it('suggests a second store only when it saves more than the extra stop and walk cost', () => {
		const a = store('a', at(0.5, 0), { tej: 400, kenyer: 600, alma: 500, sajt: 1000 });
		// b is next to a: the detour is about 0 km, so only the 500 Ft extra-stop cost counts.
		const small = store('b', at(0.5, 0.01), { sajt: 600 }); // saves 400 < 500
		const big = store('b', at(0.5, 0.01), { sajt: 300 }); // saves 700 > 500
		const noJourney = planShopping(ORIGIN, LINES, [a, small]);
		expect(noJourney.journey).toBeNull();
		expect(noJourney.bestMulti?.total).toBe(2100);
		expect(noJourney.single?.total).toBe(2500);
		const withJourney = planShopping(ORIGIN, LINES, [a, big]);
		expect(withJourney.journey?.stops).toHaveLength(2);
		expect(journeySaving(withJourney)).toBe(700);
		expect(withJourney.bestMulti).toBeNull();
	});

	it('buys every line at the cheapest store of the journey', () => {
		const a = store('a', at(0.4, 0), { tej: 300, kenyer: 900, alma: 500, sajt: 2000 });
		const b = store('b', at(0.4, 0.05), { tej: 500, kenyer: 300, alma: 500, sajt: 900 });
		// No extra-stop or walking cost here: 2,000 Ft at both beats 2,200 Ft at b alone.
		const journey = planShopping(ORIGIN, LINES, [a, b], { extraStopFt: 0, perKmFt: 0 }).journey as ShoppingPlan;
		const items = new Map(journey.stops.map((s) => [s.storeId, s.items]));
		expect(items.get('a')).toEqual(['tej', 'alma']); // alma: equal price, a is nearer
		expect(items.get('b')).toEqual(['kenyer', 'sajt']);
		expect(journey.total).toBe(300 + 500 + 300 + 900);
		for (const stop of journey.stops) {
			expect(stop.subtotal).toBe(stop.items.reduce((sum, id) => sum + (stop.storeId === 'a' ? a : b).costs.get(id)!, 0));
		}
	});

	it('walks the stops in the shortest round-trip order and reports every leg', () => {
		// Three stores on a line north of the origin: the round trip visits them nearest first (or the reverse).
		const s1 = store('s1', at(0.5, 0), { tej: 100 });
		const s2 = store('s2', at(1.0, 0), { kenyer: 100 });
		const s3 = store('s3', at(1.5, 0), { alma: 100 });
		const result = planShopping(ORIGIN, ['tej', 'kenyer', 'alma'], [s3, s1, s2], {
			extraStopFt: 0,
			perKmFt: 0
		});
		const journey = result.journey as ShoppingPlan;
		expect(journey.stops.map((s) => s.storeId)).toEqual(['s1', 's2', 's3']);
		expect(journey.routeKm).toBeCloseTo(3.0, 2);
		expect(journey.stops.map((s) => s.legKm)).toEqual([
			expect.closeTo(0.5, 2),
			expect.closeTo(0.5, 2),
			expect.closeTo(0.5, 2)
		]);
		expect(journey.returnKm).toBeCloseTo(1.5, 2);
		expect(journey.stops.reduce((sum, s) => sum + s.legKm, 0) + journey.returnKm).toBeCloseTo(journey.routeKm, 9);
	});

	it('never uses more stops than maxStops, and every stop buys something', () => {
		const stores = ['a', 'b', 'c', 'd'].map((id, index) =>
			store(id, at(0.2 * (index + 1), 0), { [LINES[index]!]: 100 })
		);
		const three = planShopping(ORIGIN, LINES, stores, { extraStopFt: 0, perKmFt: 0 });
		expect(three.journey?.stops).toHaveLength(3);
		expect(three.journey?.missing).toHaveLength(1);
		const two = planShopping(ORIGIN, LINES, stores, { maxStops: 2, extraStopFt: 0, perKmFt: 0 });
		expect(two.journey?.stops).toHaveLength(2);
		const four = planShopping(ORIGIN, LINES, stores, { maxStops: 4, extraStopFt: 0, perKmFt: 0 });
		expect(four.journey?.stops).toHaveLength(4);
		expect(four.journey?.missing).toEqual([]);
		for (const plan of [three.journey, two.journey, four.journey]) {
			for (const stop of plan!.stops) expect(stop.items.length).toBeGreaterThan(0);
		}
	});

	it('does not depend on store ids or names: renaming the stores picks the same places', () => {
		// North and south of the origin at exactly the same distance and the same prices: a perfect tie.
		const make = (names: string[]): JourneyStore[] => [
			store(names[0]!, at(0.5, 0), { tej: 400, kenyer: 600 }),
			store(names[1]!, at(-0.5, 0), { tej: 400, kenyer: 600 })
		];
		const positionOf = (stores: JourneyStore[], id: string): LatLon => stores.find((s) => s.id === id)!.point;
		const x = make(['aldi-1', 'spar-1']);
		const y = make(['zz-9', 'aa-1']);
		const px = positionOf(x, planShopping(ORIGIN, ['tej', 'kenyer'], x).single!.stops[0]!.storeId);
		const py = positionOf(y, planShopping(ORIGIN, ['tej', 'kenyer'], y).single!.stops[0]!.storeId);
		expect(px).toEqual(py);
		// Both are 0.5 km away at the same price: the neutral order is "south first".
		expect(px).toEqual(at(-0.5, 0));
	});
});

describe('planShopping: input handling', () => {
	it('skips stores without a valid position or without any priced line, and repeated ids', () => {
		const good = store('good', at(0.2, 0), { tej: 100 });
		const noPoint = store('nopoint', { lat: Number.NaN, lon: 19 }, { tej: 1 });
		const outside = store('outside', { lat: 95, lon: 19 }, { tej: 1 });
		const nothing = store('nothing', at(0.1, 0), { tej: Number.NaN, kenyer: -5 });
		const repeated = store('good', at(0.01, 0), { tej: 1 });
		const result = planShopping(ORIGIN, ['tej', 'kenyer'], [good, noPoint, outside, nothing, repeated]);
		expect(result.single?.stops[0]?.storeId).toBe('good');
		expect(result.single?.total).toBe(100);
		expect(result.journey).toBeNull();
	});

	it('returns nothing without stores, and counts every line once', () => {
		expect(planShopping(ORIGIN, LINES, [])).toEqual({ single: null, journey: null, bestMulti: null });
		const only = store('a', at(0.1, 0), { tej: 100 });
		expect(planShopping(ORIGIN, ['tej', 'tej', 'alma'], [only]).single).toMatchObject({ total: 100, missing: ['alma'] });
	});

	it('rejects an invalid origin or options', () => {
		const only = [store('a', at(0.1, 0), { tej: 100 })];
		expect(() => planShopping({ lat: 91, lon: 0 }, LINES, only)).toThrow(RangeError);
		expect(() => planShopping(ORIGIN, LINES, only, { maxStops: 0 })).toThrow(RangeError);
		expect(() => planShopping(ORIGIN, LINES, only, { maxStops: 5 })).toThrow(RangeError);
		expect(() => planShopping(ORIGIN, LINES, only, { extraStopFt: -1 })).toThrow(RangeError);
		expect(() => planShopping(ORIGIN, LINES, only, { perKmFt: Number.NaN })).toThrow(RangeError);
	});

	it('handles the largest request (25 stores × 200 lines) quickly', () => {
		const lines = Array.from({ length: 200 }, (_, index) => `l${index}`);
		const rng = mulberry32(7);
		const stores = Array.from({ length: 25 }, (_, index) =>
			store(
				`s${index}`,
				at(rng() * 3 - 1.5, rng() * 3 - 1.5),
				Object.fromEntries(lines.filter(() => rng() < 0.8).map((id) => [id, 100 + Math.round(rng() * 900)]))
			)
		);
		const started = performance.now();
		const result = planShopping(ORIGIN, lines, stores);
		expect(performance.now() - started).toBeLessThan(3000);
		expect(result.single).not.toBeNull();
	});
});

// ───────────────────────────── cross-check against a brute force ─────────────────────────────

/** Small seeded PRNG (mulberry32), so a failing case can be reproduced. */
function mulberry32(seed: number): () => number {
	let state = seed >>> 0;
	return () => {
		state = (state + 0x6d2b79f5) >>> 0;
		let t = state;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/** An independent solver: every subset by bitmask, every order by recursion; returns the best (missing, score). */
function bruteForce(
	origin: LatLon,
	lines: string[],
	stores: JourneyStore[],
	options: JourneyOptions,
	minStops: number
): { missing: number; score: number } | null {
	let best: { missing: number; score: number } | null = null;
	for (let mask = 1; mask < 1 << stores.length; mask++) {
		const chosen = stores.filter((_, index) => mask & (1 << index));
		if (chosen.length < minStops || chosen.length > options.maxStops) continue;
		let total = 0;
		let missing = 0;
		const used = new Set<string>();
		for (const line of lines) {
			let cheapest = Infinity;
			let at: string | null = null;
			for (const s of chosen) {
				const value = s.costs.get(line);
				if (value !== undefined && value < cheapest) {
					cheapest = value;
					at = s.id;
				}
			}
			if (at === null) missing += 1;
			else {
				total += cheapest;
				used.add(at);
			}
		}
		if (used.size !== chosen.length) continue; // a store that buys nothing: not a real plan
		const shortest = (from: LatLon, rest: JourneyStore[]): number =>
			rest.length === 0
				? haversineKm(from, origin)
				: Math.min(...rest.map((s, i) => haversineKm(from, s.point) + shortest(s.point, rest.filter((_, j) => j !== i))));
		const score = total + options.perKmFt * shortest(origin, chosen) + options.extraStopFt * (chosen.length - 1);
		if (best === null || missing < best.missing || (missing === best.missing && score < best.score - 1e-6)) {
			best = { missing, score };
		}
	}
	return best;
}

describe('planShopping matches a brute force on random baskets', () => {
	const settings: JourneyOptions[] = [
		DEFAULT_JOURNEY_OPTIONS,
		{ maxStops: 2, extraStopFt: 0, perKmFt: 0 },
		{ maxStops: 3, extraStopFt: 2000, perKmFt: 500 },
		{ maxStops: 4, extraStopFt: 100, perKmFt: 50 }
	];
	for (let seed = 1; seed <= 60; seed++) {
		it(`seed ${seed}`, () => {
			const rng = mulberry32(seed);
			const lines = Array.from({ length: 2 + Math.floor(rng() * 7) }, (_, index) => `l${index}`);
			const stores = Array.from({ length: 1 + Math.floor(rng() * 7) }, (_, index) =>
				store(
					`s${index}`,
					at(rng() * 4 - 2, rng() * 4 - 2),
					// Prices to the fillér: no two are equal, so both solvers make the same assignment.
					Object.fromEntries(lines.filter(() => rng() < 0.65).map((id) => [id, 50 + Math.round(rng() * 90_000) / 100]))
				)
			).filter((s) => s.costs.size > 0);
			const options = settings[seed % settings.length]!;
			const result = planShopping(ORIGIN, lines, stores, options);
			const expectedSingle = bruteForce(ORIGIN, lines, stores, { ...options, maxStops: 1 }, 1);
			const expectedBest = bruteForce(ORIGIN, lines, stores, options, 1);
			const expectedMulti = bruteForce(ORIGIN, lines, stores, options, 2);
			if (expectedSingle === null) {
				expect(result.single).toBeNull();
				return;
			}
			expect(result.single?.missing.length).toBe(expectedSingle.missing);
			expect(result.single?.score).toBeCloseTo(expectedSingle.score, 6);
			const best = result.journey ?? result.single!;
			expect(best.missing.length).toBe(expectedBest!.missing);
			expect(best.score).toBeCloseTo(expectedBest!.score, 6);
			if (result.journey === null) {
				// One store is at least as good as any journey, and bestMulti is the best journey there is.
				if (expectedMulti === null) expect(result.bestMulti).toBeNull();
				else {
					expect(result.bestMulti?.missing.length).toBe(expectedMulti.missing);
					expect(result.bestMulti?.score).toBeCloseTo(expectedMulti.score, 6);
				}
			} else {
				expect(result.journey.stops.length).toBeGreaterThanOrEqual(2);
				expect(result.journey.stops.length).toBeLessThanOrEqual(options.maxStops);
			}
			for (const plan of [result.single, result.journey, result.bestMulti]) {
				if (!plan) continue;
				// Every line is bought once or reported missing; the totals add up.
				const bought = plan.stops.flatMap((s) => s.items);
				expect(new Set(bought).size).toBe(bought.length);
				expect([...bought, ...plan.missing].sort()).toEqual([...lines].sort());
				expect(plan.total).toBeCloseTo(plan.stops.reduce((sum, s) => sum + s.subtotal, 0), 9);
			}
		});
	}
});
