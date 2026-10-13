import { describe, expect, it } from 'vitest';
import { dayLabel, weekdayName } from './labels';

describe('day labels', () => {
	it('names dated days with the weekday and the hu-HU date in both languages', () => {
		// The date itself never wraps (no-break spaces); the space after the comma may.
		const date = '2026.\u00a010.\u00a013.';
		expect(dayLabel({ index: 0, date: '2026-10-13', weekday: 1 }, 'hu')).toBe(`Kedd, ${date}`);
		expect(dayLabel({ index: 0, date: '2026-10-13', weekday: 1 }, 'en')).toBe(`Tuesday, ${date}`);
	});

	it('numbers undated days from 1', () => {
		expect(dayLabel({ index: 2, date: null, weekday: null }, 'hu')).toBe('3. nap');
		expect(dayLabel({ index: 0, date: null, weekday: null }, 'en')).toBe('Day 1');
		expect(dayLabel({ index: 4, date: 'bad', weekday: 1 }, 'hu')).toBe('5. nap');
	});

	it('has seven weekdays starting on Monday', () => {
		expect(weekdayName(0, 'hu')).toBe('Hétfő');
		expect(weekdayName(6, 'en')).toBe('Sunday');
		expect(weekdayName(7, 'hu')).toBe('');
	});
});
