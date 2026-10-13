import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	CSV_PATH,
	OUT_PATH,
	buildDistricts,
	districtOf,
	medianRounded,
	parseCsv,
	parseScaled,
	serialise,
	toRoman,
	twiceMedian
} from '../../scripts/gen-districts.mjs';
import { DISTRICTS, districtById } from './districts';

describe('districts.json', () => {
	it('has the 23 Budapest districts with Roman numeral labels', () => {
		expect(DISTRICTS).toHaveLength(23);
		expect(DISTRICTS.map((d) => d.number)).toEqual(Array.from({ length: 23 }, (_, i) => i + 1));
		expect(DISTRICTS.map((d) => d.roman)).toEqual([
			'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII',
			'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX', 'XXI', 'XXII', 'XXIII'
		]);
		expect(DISTRICTS.map((d) => d.id)).toEqual(DISTRICTS.map((d) => String(d.number).padStart(2, '0')));
	});

	it('puts every centroid inside Budapest and counts its stores', () => {
		for (const d of DISTRICTS) {
			expect(d.lat).toBeGreaterThan(47.34);
			expect(d.lat).toBeLessThan(47.62);
			expect(d.lon).toBeGreaterThan(18.92);
			expect(d.lon).toBeLessThan(19.34);
			expect(d.stores).toBeGreaterThan(0);
		}
		// 419 Budapest stores in the 2026-10-12 snapshot (BUILD-BRIEF §3).
		expect(DISTRICTS.reduce((sum, d) => sum + d.stores, 0)).toBe(419);
	});

	it('is exactly what the generator produces from the research store list (never hand-edited)', () => {
		const expected = serialise(buildDistricts(readFileSync(CSV_PATH, 'utf8')));
		expect(readFileSync(OUT_PATH, 'utf8')).toBe(expected);
	});

	it('looks districts up by id', () => {
		expect(districtById('11')?.roman).toBe('XI');
		expect(districtById('24')).toBeNull();
		expect(districtById(null)).toBeNull();
		expect(Object.isFrozen(DISTRICTS)).toBe(true);
	});
});

describe('generator helpers', () => {
	it('derives the district from postal code digits 2-3', () => {
		expect(districtOf('1011')).toBe(1);
		expect(districtOf('1114')).toBe(11);
		expect(districtOf('1239')).toBe(23);
		expect(districtOf(' 1052 ')).toBe(5);
		expect(districtOf('1241')).toBeNull();
		expect(districtOf('1001')).toBeNull();
		expect(districtOf('2040')).toBeNull();
		expect(districtOf('111')).toBeNull();
		expect(districtOf('')).toBeNull();
	});

	it('writes Roman numerals', () => {
		expect([1, 4, 9, 14, 19, 23, 40, 90, 400, 1994].map(toRoman)).toEqual([
			'I', 'IV', 'IX', 'XIV', 'XIX', 'XXIII', 'XL', 'XC', 'CD', 'MCMXCIV'
		]);
		expect(() => toRoman(0)).toThrow(RangeError);
		expect(() => toRoman(2.5)).toThrow(RangeError);
	});

	it('parses quoted CSV fields', () => {
		expect(parseCsv('a,b,c\r\n"x, y","say ""hi""",\n1,2,3')).toEqual([
			['a', 'b', 'c'],
			['x, y', 'say "hi"', ''],
			['1', '2', '3']
		]);
		expect(parseCsv('a\n\n')).toEqual([['a']]);
		expect(() => parseCsv('"open')).toThrow();
	});

	it('takes exact medians and rounds half up', () => {
		const scaled = (xs: string[]) => xs.map((x) => parseScaled(x) as bigint);
		expect(medianRounded(scaled(['3', '1', '2']), 5)).toBe(2);
		// (19.14543 + 19.14544) / 2 = 19.145435 -> 19.14544 (a float mean would round to 19.14543).
		expect(medianRounded(scaled(['19.14543', '19.14544']), 5)).toBe(19.14544);
		expect(medianRounded(scaled(['47.459985', '47.459995']), 5)).toBe(47.45999);
		expect(medianRounded(scaled(['-1.000005']), 5)).toBe(-1.00001);
		expect(twiceMedian([1n, 3n])).toBe(4n);
		expect(() => twiceMedian([])).toThrow();
	});

	it('parses only plain decimal numbers', () => {
		expect(parseScaled('47.5')).toBe(47_500_000_000_000_000n);
		expect(parseScaled('-0.000000000000001')).toBe(-1n);
		expect(parseScaled('1e5')).toBeNull();
		expect(parseScaled('')).toBeNull();
		expect(parseScaled('0.0000000000000001')).toBeNull();
	});

	it('fails loudly when a district has no stores', () => {
		const csv = 'uuid,chain,postalCode,city,address,lat,lon\nx,Lidl,1011,Budapest,a,47.5,19.04\n';
		expect(() => buildDistricts(csv)).toThrow(/district 2/);
	});
});
