import { describe, expect, it } from 'vitest';
import { addDays, daysToMonthEnd, isCalendarDate, parseCalendarDate, todayInBudapest, weekdayIndex } from './dates';

describe('parseCalendarDate', () => {
	it('accepts strict real calendar dates only', () => {
		expect(parseCalendarDate('2026-10-13')?.toISOString()).toBe('2026-10-13T00:00:00.000Z');
		expect(parseCalendarDate('2028-02-29')).not.toBeNull();
		for (const bad of ['2026-02-29', '2026-02-30', '2026-13-01', '2026-00-10', '2026-1-1', '2026-10-13T00:00', ' 2026-10-13', '1969-12-31', '']) {
			expect(parseCalendarDate(bad), bad).toBeNull();
		}
		expect(parseCalendarDate(null)).toBeNull();
		expect(parseCalendarDate(20261013)).toBeNull();
		expect(isCalendarDate('2026-10-13')).toBe(true);
		expect(isCalendarDate('2026-10-32')).toBe(false);
	});
});

describe('todayInBudapest', () => {
	it('uses the Budapest calendar day, not UTC (summer time, UTC+2)', () => {
		expect(todayInBudapest(new Date('2026-10-12T21:59:59Z'))).toBe('2026-10-12');
		expect(todayInBudapest(new Date('2026-10-12T22:00:00Z'))).toBe('2026-10-13');
	});

	it('uses the Budapest calendar day in winter (UTC+1), across a year boundary', () => {
		expect(todayInBudapest(new Date('2026-12-31T22:59:59Z'))).toBe('2026-12-31');
		expect(todayInBudapest(new Date('2026-12-31T23:00:00Z'))).toBe('2027-01-01');
	});
});

describe('addDays', () => {
	it('crosses month and year boundaries and the daylight-saving changes without drifting', () => {
		expect(addDays('2026-10-13', 0)).toBe('2026-10-13');
		expect(addDays('2026-10-13', 6)).toBe('2026-10-19');
		expect(addDays('2026-10-31', 1)).toBe('2026-11-01');
		expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
		expect(addDays('2028-02-28', 1)).toBe('2028-02-29');
		expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
		// Summer time ends on 2026-10-25 and starts on 2026-03-29 in Budapest.
		expect(addDays('2026-10-24', 1)).toBe('2026-10-25');
		expect(addDays('2026-10-24', 2)).toBe('2026-10-26');
		expect(addDays('2026-03-28', 2)).toBe('2026-03-30');
		expect(addDays('2026-10-01', 30)).toBe('2026-10-31');
	});

	it('throws on an invalid date or a non-integer offset', () => {
		expect(() => addDays('2026-02-30', 1)).toThrow(RangeError);
		expect(() => addDays('2026-10-13', 0.5)).toThrow(RangeError);
	});
});

describe('daysToMonthEnd', () => {
	it('counts the start day and the last day of the month', () => {
		expect(daysToMonthEnd('2026-10-13')).toBe(19);
		expect(daysToMonthEnd('2026-10-31')).toBe(1);
		expect(daysToMonthEnd('2026-10-01')).toBe(31);
		expect(daysToMonthEnd('2026-02-01')).toBe(28);
		expect(daysToMonthEnd('2028-02-01')).toBe(29);
		expect(daysToMonthEnd('2026-04-30')).toBe(1);
		expect(() => daysToMonthEnd('nope')).toThrow(RangeError);
	});
});

describe('weekdayIndex', () => {
	it('starts the week on Monday', () => {
		expect(weekdayIndex('2026-10-12')).toBe(0);
		expect(weekdayIndex('2026-10-13')).toBe(1);
		expect(weekdayIndex('2026-10-18')).toBe(6);
		expect(weekdayIndex('2027-01-01')).toBe(4);
		expect(() => weekdayIndex('2026-10-32')).toThrow(RangeError);
	});
});
