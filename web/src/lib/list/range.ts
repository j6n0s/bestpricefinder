/**
 * Which part of the stored plan the shopping list is for: "Ez a hét", "Jövő hét" or "Az egész terv".
 *
 * Weeks are the plan's own 7-day blocks counted from day 0 (the same blocks as the plan page and the rule
 * checks: week = day index ÷ 7, rounded down). "Ez a hét" is the block that contains today (Budapest date);
 * before the plan starts it is the first block. An undated plan counts as starting today. After the plan's
 * last day "Ez a hét" and "Jövő hét" are empty, and the page offers the whole plan.
 */
import type { StoredPlan } from '../storage';
import { parseCalendarDate } from '../plan/dates';
import { dayDate } from '../plan/plan';

export const LIST_RANGES = ['this_week', 'next_week', 'whole'] as const;
export type ListRange = (typeof LIST_RANGES)[number];

const DAY_MS = 86_400_000;
const WEEK_DAYS = 7;

export function isListRange(value: unknown): value is ListRange {
	return typeof value === 'string' && (LIST_RANGES as readonly string[]).includes(value);
}

/** The 7-day block of the plan that contains `today` ("YYYY-MM-DD"); 0 before the start or when undated. */
export function currentWeekIndex(plan: Pick<StoredPlan, 'startDate'>, today: string): number {
	const start = parseCalendarDate(plan.startDate);
	const now = parseCalendarDate(today);
	if (start === null || now === null) return 0;
	const days = Math.round((now.getTime() - start.getTime()) / DAY_MS);
	return days <= 0 ? 0 : Math.floor(days / WEEK_DAYS);
}

export interface RangeInfo {
	range: ListRange;
	/** Day indexes of the plan in this range, ascending. */
	dayIndexes: number[];
	/** Calendar date of the first and last of those days; null for an undated plan or an empty range. */
	from: string | null;
	to: string | null;
}

/** The plan days a range covers. */
export function rangeInfo(plan: Pick<StoredPlan, 'startDate' | 'days'>, range: ListRange, today: string): RangeInfo {
	const all = [...new Set(plan.days.map((day) => day.index))].sort((a, b) => a - b);
	let dayIndexes = all;
	if (range !== 'whole') {
		const week = currentWeekIndex(plan, today) + (range === 'next_week' ? 1 : 0);
		dayIndexes = all.filter((index) => Math.floor(index / WEEK_DAYS) === week);
	}
	const first = dayIndexes[0];
	const last = dayIndexes.at(-1);
	return {
		range,
		dayIndexes,
		from: first === undefined ? null : dayDate(plan, first),
		to: last === undefined ? null : dayDate(plan, last)
	};
}

/** The plan restricted to the range's days (the input is never changed). */
export function planForRange<P extends Pick<StoredPlan, 'days'>>(plan: P, info: Pick<RangeInfo, 'dayIndexes'>): P {
	const keep = new Set(info.dayIndexes);
	return { ...plan, days: plan.days.filter((day) => keep.has(day.index)) };
}

/**
 * The range to show: the preferred one when it has days, else "Ez a hét" when it has days, else the whole
 * plan.
 */
export function effectiveRange(
	plan: Pick<StoredPlan, 'startDate' | 'days'>,
	preferred: ListRange,
	today: string
): ListRange {
	if (rangeInfo(plan, preferred, today).dayIndexes.length > 0) return preferred;
	if (rangeInfo(plan, 'this_week', today).dayIndexes.length > 0) return 'this_week';
	return 'whole';
}

