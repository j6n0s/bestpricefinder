import { describe, expect, it } from 'vitest';
import { haversineKm, type LatLon } from '../geo';
import { DEFAULT_FRAME, mapFrame, pathData, scaleBar } from './map';

const NYUGATI: LatLon = { lat: 47.5103, lon: 19.0558 };
const OKTOGON: LatLon = { lat: 47.5052, lon: 19.0634 };
const DEAK: LatLon = { lat: 47.4979, lon: 19.0542 };

function distance(a: { x: number; y: number }, b: { x: number; y: number }): number {
	return Math.hypot(a.x - b.x, a.y - b.y);
}

describe('mapFrame', () => {
	it('keeps every point inside the padding and north up', () => {
		const frame = mapFrame([NYUGATI, OKTOGON, DEAK]);
		for (const point of [NYUGATI, OKTOGON, DEAK]) {
			const { x, y } = frame.project(point);
			expect(x).toBeGreaterThanOrEqual(DEFAULT_FRAME.padding - 1e-9);
			expect(x).toBeLessThanOrEqual(DEFAULT_FRAME.width - DEFAULT_FRAME.padding + 1e-9);
			expect(y).toBeGreaterThanOrEqual(DEFAULT_FRAME.padding - 1e-9);
			expect(y).toBeLessThanOrEqual(DEFAULT_FRAME.height - DEFAULT_FRAME.padding + 1e-9);
		}
		expect(frame.project(NYUGATI).y).toBeLessThan(frame.project(DEAK).y); // Nyugati is north of Deák
		expect(frame.project(OKTOGON).x).toBeGreaterThan(frame.project(DEAK).x); // Oktogon is east of Deák
	});

	it('keeps distances in proportion (within 0.5 %)', () => {
		const frame = mapFrame([NYUGATI, OKTOGON, DEAK]);
		for (const [a, b] of [
			[NYUGATI, OKTOGON],
			[OKTOGON, DEAK],
			[NYUGATI, DEAK]
		] as const) {
			const drawn = distance(frame.project(a), frame.project(b)) / frame.unitsPerKm;
			expect(Math.abs(drawn - haversineKm(a, b)) / haversineKm(a, b)).toBeLessThan(0.005);
		}
	});

	it('shows at least minSpanKm, so one point or two neighbours sit in the middle', () => {
		const one = mapFrame([NYUGATI]);
		expect(one.project(NYUGATI)).toEqual({ x: DEFAULT_FRAME.width / 2, y: DEFAULT_FRAME.height / 2 });
		expect(one.unitsPerKm).toBeCloseTo((DEFAULT_FRAME.height - 2 * DEFAULT_FRAME.padding) / DEFAULT_FRAME.minSpanKm, 9);
		const near = { lat: NYUGATI.lat + 0.0002, lon: NYUGATI.lon };
		const two = mapFrame([NYUGATI, near]);
		expect(two.unitsPerKm).toBe(one.unitsPerKm);
	});

	it('rejects an empty or invalid input', () => {
		expect(() => mapFrame([])).toThrow(RangeError);
		expect(() => mapFrame([{ lat: Number.NaN, lon: 19 }])).toThrow(RangeError);
	});
});

describe('scaleBar', () => {
	it('picks the longest nice distance that fits', () => {
		expect(scaleBar({ unitsPerKm: 100 }, 120)).toEqual({ km: 1, units: 100 });
		expect(scaleBar({ unitsPerKm: 400 }, 120)).toEqual({ km: 0.25, units: 100 });
		expect(scaleBar({ unitsPerKm: 30 }, 120)).toEqual({ km: 2.5, units: 75 });
		expect(scaleBar({ unitsPerKm: 5000 }, 120)).toEqual({ km: 0.05, units: 250 }); // never shorter than 50 m
	});
});

describe('pathData', () => {
	it('draws a polyline, rounded to 0.1 unit', () => {
		expect(pathData([{ x: 1.04, y: 2 }, { x: 3.16, y: 4.25 }])).toBe('M1 2 L3.2 4.3');
		expect(pathData([])).toBe('');
	});
});
