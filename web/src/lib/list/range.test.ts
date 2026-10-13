// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { PlanDayIO } from '../api/types';
import type { StoredPlan } from '../storage';
import { currentWeekIndex, effectiveRange, isListRange, planForRange, rangeInfo } from './range';

function plan(startDate: string | null, days: number): StoredPlan {
	const list: PlanDayIO[] = Array.from({ length: days }, (_, index) => ({
		index,
		meals: { reggeli: null, ebed: 'minta-lencse', vacsora: null }
	}));
	return { createdAt: '2026-10-01T08:00:00.000Z', startDate, seed: 1, slots: 3, noRepeatDays: 5, days: list };
}

describe('currentWeekIndex', () => {
	const p = plan('2026-10-01', 31);

	it('is 0 before the start and in the first 7 days', () => {
		expect(currentWeekIndex(p, '2026-09-20')).toBe(0);
		expect(currentWeekIndex(p, '2026-10-01')).toBe(0);
		expect(currentWeekIndex(p, '2026-10-07')).toBe(0);
	});

	it('counts 7-day blocks from the start date', () => {
		expect(currentWeekIndex(p, '2026-10-08')).toBe(1);
		expect(currentWeekIndex(p, '2026-10-13')).toBe(1);
		expect(currentWeekIndex(p, '2026-10-15')).toBe(2);
		expect(currentWeekIndex(p, '2026-10-31')).toBe(4);
	});

	it('is not shifted by the daylight-saving change (25 October 2026)', () => {
		const q = plan('2026-10-20', 14);
		expect(currentWeekIndex(q, '2026-10-26')).toBe(0);
		expect(currentWeekIndex(q, '2026-10-27')).toBe(1);
	});

	it('treats an undated plan, or an invalid date, as week 0', () => {
		expect(currentWeekIndex(plan(null, 7), '2026-10-13')).toBe(0);
		expect(currentWeekIndex(p, 'not a date')).toBe(0);
		expect(currentWeekIndex(p, '2026-02-30')).toBe(0);
	});
});

describe('rangeInfo', () => {
	const p = plan('2026-10-01', 31);
	const today = '2026-10-13';

	it('"this week" is the 7-day block that contains today', () => {
		expect(rangeInfo(p, 'this_week', today)).toEqual({
			range: 'this_week',
			dayIndexes: [7, 8, 9, 10, 11, 12, 13],
			from: '2026-10-08',
			to: '2026-10-14'
		});
	});

	it('"next week" is the following block', () => {
		expect(rangeInfo(p, 'next_week', today)).toMatchObject({
			dayIndexes: [14, 15, 16, 17, 18, 19, 20],
			from: '2026-10-15',
			to: '2026-10-21'
		});
	});

	it('"whole" is every day of the plan, sorted and unique', () => {
		const shuffled = { ...p, days: [...p.days].reverse() };
		const info = rangeInfo(shuffled, 'whole', today);
		expect(info.dayIndexes).toEqual(Array.from({ length: 31 }, (_, i) => i));
		expect(info.from).toBe('2026-10-01');
		expect(info.to).toBe('2026-10-31');
	});

	it('a short last block only has the days that exist', () => {
		expect(rangeInfo(p, 'this_week', '2026-10-30').dayIndexes).toEqual([28, 29, 30]);
		expect(rangeInfo(p, 'next_week', '2026-10-30').dayIndexes).toEqual([]);
	});

	it('is empty after the plan ended, with no dates', () => {
		expect(rangeInfo(p, 'this_week', '2026-11-20')).toEqual({ range: 'this_week', dayIndexes: [], from: null, to: null });
	});

	it('uses the first block before the plan starts', () => {
		expect(rangeInfo(p, 'this_week', '2026-09-28').dayIndexes).toEqual([0, 1, 2, 3, 4, 5, 6]);
		expect(rangeInfo(p, 'next_week', '2026-09-28').dayIndexes).toEqual([7, 8, 9, 10, 11, 12, 13]);
	});

	it('gives no dates for an undated plan', () => {
		const info = rangeInfo(plan(null, 10), 'next_week', today);
		expect(info.dayIndexes).toEqual([7, 8, 9]);
		expect(info.from).toBeNull();
		expect(info.to).toBeNull();
	});
});

describe('planForRange', () => {
	it('keeps only the range days and never changes the input', () => {
		const p = plan('2026-10-01', 14);
		const copy = structuredClone(p);
		const part = planForRange(p, { dayIndexes: [7, 8] });
		expect(part.days.map((d) => d.index)).toEqual([7, 8]);
		expect(part.createdAt).toBe(p.createdAt);
		expect(p).toEqual(copy);
	});
});

describe('effectiveRange', () => {
	it('keeps the preferred range when it has days', () => {
		expect(effectiveRange(plan('2026-10-01', 31), 'next_week', '2026-10-13')).toBe('next_week');
		expect(effectiveRange(plan('2026-10-01', 31), 'whole', '2026-10-13')).toBe('whole');
	});

	it('falls back to this week, then to the whole plan', () => {
		const week = plan('2026-10-13', 7);
		expect(effectiveRange(week, 'next_week', '2026-10-13')).toBe('this_week');
		expect(effectiveRange(week, 'this_week', '2026-12-01')).toBe('whole');
		expect(effectiveRange(week, 'next_week', '2026-12-01')).toBe('whole');
	});
});

describe('isListRange', () => {
	it('accepts only the three ranges', () => {
		expect(isListRange('this_week')).toBe(true);
		expect(isListRange('next_week')).toBe(true);
		expect(isListRange('whole')).toBe(true);
		expect(isListRange('month')).toBe(false);
		expect(isListRange(undefined)).toBe(false);
	});
});
