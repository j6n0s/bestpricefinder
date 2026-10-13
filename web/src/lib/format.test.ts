import { describe, expect, it } from 'vitest';
import {
	formatDate,
	formatDateTime,
	formatDistance,
	formatMoney,
	formatMonth,
	formatNumber,
	formatPercent,
	formatQty,
	parseIsoDate,
	unitName
} from './format';

const NBSP = ' ';

describe('formatMoney (hu-HU, whole forints)', () => {
	it.each([
		[0, '0 Ft'],
		[5, '5 Ft'],
		[999, '999 Ft'],
		[1234, '1 234 Ft'],
		[12345, '12 345 Ft'],
		[1234567, '1 234 567 Ft'],
		[13529.4, '13 529 Ft'],
		[1234.5, '1 235 Ft'],
		[0.5, '1 Ft'],
		[-1500, '-1 500 Ft'],
		[-0.4, '0 Ft']
	])('%s -> %s', (value, expected) => {
		expect(formatMoney(value)).toBe(expected.replaceAll(' ', NBSP));
	});

	it('uses no-break spaces so a price never wraps', () => {
		expect(formatMoney(1234)).toBe(`1${NBSP}234${NBSP}Ft`);
		expect(formatMoney(1234)).not.toMatch(/ /);
	});

	it.each([Number.NaN, Number.POSITIVE_INFINITY])('shows a dash for %s', (value) => {
		expect(formatMoney(value)).toBe('–');
	});
});

describe('formatNumber / formatQty', () => {
	it.each([
		[0.4, '0,4'],
		[1.25, '1,25'],
		[0.005, '0,005'],
		[0.0004, '0'],
		[2, '2'],
		[1234.5678, '1 234,568']
	])('formatNumber(%s) = %s', (value, expected) => {
		expect(formatNumber(value)).toBe(expected.replaceAll(' ', NBSP));
	});

	it('names units in the UI language', () => {
		expect(formatQty(0.4, 'kg')).toBe(`0,4${NBSP}kg`);
		expect(formatQty(1.5, 'l')).toBe(`1,5${NBSP}l`);
		expect(formatQty(2, 'db')).toBe(`2${NBSP}db`);
		expect(formatQty(2, 'db', 'en')).toBe(`2${NBSP}pcs`);
		expect(unitName('kg', 'en')).toBe('kg');
		expect(unitName('db', 'hu')).toBe('db');
	});

	it('keeps the hu-HU decimal comma in English too', () => {
		expect(formatQty(0.25, 'kg', 'en')).toBe(`0,25${NBSP}kg`);
	});
});

describe('formatDistance', () => {
	it.each([
		[0, '0 m'],
		[0.0134, '10 m'],
		[0.5424, '540 m'],
		[0.996, '1,0 km'],
		[0.9949, '990 m'],
		[1, '1,0 km'],
		[1.5, '1,5 km'],
		[12.353, '12,4 km']
	])('%s km -> %s', (km, expected) => {
		expect(formatDistance(km)).toBe(expected.replaceAll(' ', NBSP));
	});

	it.each([-1, Number.NaN])('shows a dash for %s', (km) => {
		expect(formatDistance(km)).toBe('–');
	});
});

describe('formatPercent', () => {
	it('rounds a share to a whole percentage', () => {
		expect(formatPercent(0.9)).toBe('90%');
		expect(formatPercent(0.944)).toBe('94%');
		expect(formatPercent(1)).toBe('100%');
		expect(formatPercent(Number.NaN)).toBe('–');
	});
});

describe('dates (hu-HU)', () => {
	/** The expected text with every space as a no-break space. */
	const nb = (text: string): string => text.replaceAll(' ', NBSP);

	it('formats a data date as "2026. 10. 13."', () => {
		expect(formatDate('2026-10-13')).toBe(nb('2026. 10. 13.'));
		expect(formatDate('2026-01-05')).toBe(nb('2026. 01. 05.'));
	});

	it('never lets a date wrap: only no-break spaces inside dates (the source line, the header)', () => {
		for (const text of [formatDate('2026-10-13'), formatMonth('2026-09-01'), formatDateTime('2026-10-13T02:31:00Z')]) {
			expect(text).toContain(NBSP);
			expect(text).not.toMatch(/[ \t\n\u202f]/);
		}
		expect(formatDate('2026-10-13')).toBe(`2026.${NBSP}10.${NBSP}13.`);
	});

	it('does not shift the calendar day with the time zone', () => {
		expect(formatDate('2026-12-31')).toBe(nb('2026. 12. 31.'));
		expect(formatDate('2026-10-13T23:59:59+02:00')).toBe(nb('2026. 10. 13.'));
	});

	it.each([null, undefined, '', '2026-13-01', '2026-02-30', '13.10.2026', '2026-1-5', 'x'])('gives "" for %j', (value) => {
		expect(formatDate(value)).toBe('');
	});

	it('validates calendar dates strictly', () => {
		expect(parseIsoDate('2028-02-29')).not.toBeNull();
		expect(parseIsoDate('2026-02-29')).toBeNull();
		expect(parseIsoDate('2026-10-13junk')).toBeNull();
	});

	it('formats the KSH period as a month', () => {
		expect(formatMonth('2026-09-01')).toBe(nb('2026. 09.'));
		expect(formatMonth(null)).toBe('');
	});

	it('formats an ingest time in Budapest time (summer and winter)', () => {
		expect(formatDateTime('2026-10-13T02:31:00Z')).toBe(nb('2026. 10. 13. 4:31'));
		expect(formatDateTime('2026-01-15T23:05:00Z')).toBe(nb('2026. 01. 16. 0:05'));
		expect(formatDateTime('nope')).toBe('');
		expect(formatDateTime(null)).toBe('');
	});
});
