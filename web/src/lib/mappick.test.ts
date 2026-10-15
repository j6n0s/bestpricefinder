import { describe, expect, it } from 'vitest';
import { DISTRICTS } from './districts';
import { haversineKm } from './geo';
import {
	BUDAPEST_VIEW,
	MAX_SPAN_KM,
	MIN_SPAN_KM,
	countryView,
	describePoint,
	fitView,
	inView,
	nudge,
	storePoints,
	zoomView
} from './mappick';

const NYUGATI = { lat: 47.5103, lon: 19.0558 };
const DEBRECEN = { lat: 47.5316, lon: 21.6273 };
const PECS = { lat: 46.0727, lon: 18.2323 };

describe('fitView and the presets', () => {
	it('fits every point with a margin and respects the width limits', () => {
		const view = fitView([NYUGATI, DEBRECEN, PECS]);
		expect(inView(NYUGATI, view) && inView(DEBRECEN, view) && inView(PECS, view)).toBe(true);
		expect(view.spanKm).toBeGreaterThan(haversineKm(NYUGATI, DEBRECEN));
		expect(fitView([NYUGATI]).spanKm).toBeCloseTo(MIN_SPAN_KM * 1.15, 6);
		expect(fitView([{ lat: 0, lon: -90 }, { lat: 0, lon: 90 }]).spanKm).toBe(MAX_SPAN_KM);
		expect(() => fitView([])).toThrow(RangeError);
	});

	it('Budapest shows every district; the country view every store, or Budapest without stores', () => {
		for (const district of DISTRICTS) expect(inView(district, BUDAPEST_VIEW)).toBe(true);
		expect(BUDAPEST_VIEW.spanKm).toBeGreaterThan(20);
		expect(BUDAPEST_VIEW.spanKm).toBeLessThan(40);
		const stores = [
			{ lat: NYUGATI.lat, lon: NYUGATI.lon },
			{ lat: DEBRECEN.lat, lon: DEBRECEN.lon },
			{ lat: null, lon: null }
		];
		expect(storePoints(stores)).toHaveLength(2);
		const country = countryView(stores);
		expect(inView(DEBRECEN, country)).toBe(true);
		expect(countryView([{ lat: null, lon: null }])).toEqual(BUDAPEST_VIEW);
	});
});

describe('zoomView, nudge, inView', () => {
	it('zooms around a point within the limits', () => {
		const view = zoomView(BUDAPEST_VIEW, 0.5, NYUGATI);
		expect(view.centre).toEqual(NYUGATI);
		expect(view.spanKm).toBeCloseTo(BUDAPEST_VIEW.spanKm / 2, 9);
		expect(zoomView({ centre: NYUGATI, spanKm: 0.6 }, 0.5).spanKm).toBe(MIN_SPAN_KM);
		expect(zoomView({ centre: NYUGATI, spanKm: 900 }, 2).spanKm).toBe(MAX_SPAN_KM);
		expect(zoomView(BUDAPEST_VIEW, 2).centre).toEqual(BUDAPEST_VIEW.centre);
	});

	it('nudges by a twentieth of the width, north and east', () => {
		const view = { centre: NYUGATI, spanKm: 20 };
		const north = nudge(NYUGATI, view, 0, 1);
		const east = nudge(NYUGATI, view, 1, 0);
		expect(north.lat).toBeGreaterThan(NYUGATI.lat);
		expect(haversineKm(NYUGATI, north)).toBeCloseTo(1, 2);
		expect(east.lon).toBeGreaterThan(NYUGATI.lon);
		expect(haversineKm(NYUGATI, east)).toBeCloseTo(1, 2);
		expect(inView(nudge(NYUGATI, view, 9, 0), view)).toBe(true);
		expect(inView(nudge(NYUGATI, view, 11, 0), view)).toBe(false);
	});
});

describe('describePoint', () => {
	const stores = [
		{ lat: DEBRECEN.lat, lon: DEBRECEN.lon, city: 'Debrecen' },
		{ lat: NYUGATI.lat, lon: NYUGATI.lon, city: 'Budapest' },
		{ lat: null, lon: null, city: 'Sehol' }
	];

	it('names the nearest district in Budapest, the nearest store city elsewhere, nothing far away', () => {
		const near = describePoint(NYUGATI, stores);
		expect(near.kind).toBe('district');
		if (near.kind === 'district') expect(['V', 'VI', 'XIII']).toContain(near.district.roman);
		expect(describePoint({ lat: 47.55, lon: 21.6 }, stores)).toEqual({ kind: 'city', city: 'Debrecen' });
		expect(describePoint({ lat: 46.0, lon: 20.1 }, stores)).toEqual({ kind: 'nowhere' });
		expect(describePoint(PECS, [])).toEqual({ kind: 'nowhere' });
	});
});
