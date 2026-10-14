import { describe, expect, it } from 'vitest';
import type { QuoteLineOut, QuoteResponse, StoreOut, StoreQuoteOut } from '../api/types';
import type { LatLon } from '../geo';
import { journeyStores, osmLink, shoppingView } from './view';

const ORIGIN: LatLon = { lat: 47.5103, lon: 19.0558 };

function at(northKm: number, eastKm: number): LatLon {
	return {
		lat: ORIGIN.lat + northKm / 111.32,
		lon: ORIGIN.lon + eastKm / (111.32 * Math.cos((ORIGIN.lat * Math.PI) / 180))
	};
}

function storeOut(id: string, chain: string, point: LatLon | null): StoreOut {
	return {
		id,
		chain,
		postal_code: '1062',
		city: 'Budapest',
		address: 'Teszt utca 1.',
		lat: point?.lat ?? null,
		lon: point?.lon ?? null,
		format: null,
		is_budapest: true,
		has_data: true
	};
}

function line(id: string, cost: number | null, status: QuoteLineOut['status'] = 'priced'): QuoteLineOut {
	return {
		ingredient_id: id,
		qty: 1,
		unit: 'kg',
		status: cost === null && status === 'priced' ? 'unavailable' : status,
		picks: [],
		checkout_cost: status === 'priced' ? cost : null,
		used_cost: status === 'priced' ? cost : null,
		leftover_qty: null,
		ksh_estimate: null,
		alternatives: []
	};
}

function quoted(id: string, chain: string, lines: QuoteLineOut[]): StoreQuoteOut {
	const priced = lines.filter((l) => l.status === 'priced');
	return {
		store_id: id,
		chain,
		checkout_total: priced.reduce((sum, l) => sum + (l.checkout_cost ?? 0), 0),
		used_total: 0,
		missing: lines.filter((l) => l.status === 'unavailable').map((l) => l.ingredient_id),
		assumed_count: 0,
		ksh_estimate_total: 0,
		lines
	};
}

function quote(stores: StoreQuoteOut[]): QuoteResponse {
	return {
		data_date: '2026-10-14',
		stores,
		ranking: [],
		split: null,
		scope_note_hu: 'a kiválasztott boltok közül, a 2026-10-14-i GVH-adatok alapján',
		scope_note_en: 'among the selected stores, based on GVH data of 2026-10-14',
		attribution: {} as QuoteResponse['attribution']
	};
}

describe('journeyStores', () => {
	it('takes the checkout cost of priced lines only, and skips stores without coordinates', () => {
		const q = quote([
			quoted('spar-1', 'spar', [line('tej', 400), line('kenyer', null), line('alma', null, 'unpriced')]),
			quoted('lidl-1', 'lidl', [line('tej', 350)])
		]);
		const stores = new Map([
			['spar-1', storeOut('spar-1', 'spar', at(0.2, 0))],
			['lidl-1', storeOut('lidl-1', 'lidl', null)]
		]);
		const result = journeyStores(q, stores);
		expect(result.map((s) => s.id)).toEqual(['spar-1']);
		expect([...result[0]!.costs]).toEqual([['tej', 400]]);
	});
});

describe('shoppingView', () => {
	const stores = new Map([
		['spar-1', storeOut('spar-1', 'spar', at(0.3, 0))],
		['lidl-1', storeOut('lidl-1', 'lidl', at(0.3, 0.02))],
		['aldi-1', storeOut('aldi-1', 'aldi', at(-0.4, 0))]
	]);

	it('shows the single store and a cheaper route, with savings, extra walk and numbered stops', () => {
		const q = quote([
			quoted('spar-1', 'spar', [line('tej', 400), line('kenyer', 600), line('sajt', 2000), line('rizs', null)]),
			quoted('lidl-1', 'lidl', [line('tej', 900), line('kenyer', 1100), line('sajt', 1000), line('rizs', null)]),
			quoted('aldi-1', 'aldi', [line('tej', null), line('kenyer', null), line('sajt', null), line('rizs', null)])
		]);
		const view = shoppingView(q, stores, ORIGIN)!;
		expect(view.lineIds).toEqual(['tej', 'kenyer', 'sajt', 'rizs']);
		expect(view.nowhere).toEqual(['rizs']); // nobody sells it: said once, not as a missing line
		// Both single stores cost 3,000 Ft: the nearer one (Spar, 300 m) wins the tie.
		expect(view.single).toMatchObject({ storeId: 'spar-1', chain: 'spar', total: 3000, missing: [] });
		const journey = view.journey!;
		expect(journey.stops.map((s) => [s.number, s.storeId, s.items])).toEqual([
			[1, 'spar-1', ['tej', 'kenyer']],
			[2, 'lidl-1', ['sajt']]
		]);
		expect(journey.total).toBe(2000);
		expect(journey.saving).toBe(1000); // well above the 500 Ft an extra stop has to save
		expect(journey.moreItems).toBe(0);
		expect(journey.missing).toEqual([]);
		expect(journey.extraKm).toBeCloseTo(journey.routeKm - view.single!.routeKm, 9);
		expect(view.notWorth).toBeNull();
	});

	it('explains when no route is worth it, with what it would have saved', () => {
		const q = quote([
			quoted('spar-1', 'spar', [line('tej', 400), line('kenyer', 600)]),
			quoted('lidl-1', 'lidl', [line('tej', 300), line('kenyer', 650)])
		]);
		const view = shoppingView(q, stores, ORIGIN)!;
		expect(view.journey).toBeNull();
		expect(view.notWorth).toEqual({ saving: view.single!.total - 900 });
	});

	it('a route that only adds items reports them as "more items", not as a saving', () => {
		const q = quote([
			quoted('spar-1', 'spar', [line('tej', 400), line('kenyer', null)]),
			quoted('aldi-1', 'aldi', [line('tej', null), line('kenyer', 600)])
		]);
		const view = shoppingView(q, stores, ORIGIN)!;
		expect(view.single?.missing).toEqual(['kenyer']);
		expect(view.journey?.moreItems).toBe(1);
		expect(view.journey?.saving).toBe(400 - 1000);
		expect(view.journey?.missing).toEqual([]);
	});

	it('is null for an invalid starting point, and empty-handed without priced stores', () => {
		const q = quote([quoted('spar-1', 'spar', [line('tej', 400)])]);
		expect(shoppingView(q, stores, { lat: Number.NaN, lon: 19 })).toBeNull();
		const none = shoppingView(quote([quoted('spar-1', 'spar', [line('tej', null)])]), stores, ORIGIN)!;
		expect(none).toEqual({ lineIds: ['tej'], nowhere: ['tej'], single: null, journey: null, notWorth: null });
	});
});

describe('osmLink', () => {
	it('links only the store position, rounded to 5 decimals', () => {
		expect(osmLink({ lat: 47.5103456, lon: 19.0558 })).toBe(
			'https://www.openstreetmap.org/?mlat=47.51035&mlon=19.05580#map=18/47.51035/19.05580'
		);
	});
});
