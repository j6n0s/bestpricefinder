/**
 * Calendar helpers for the weekly plan. Plan dates are plain calendar dates ("YYYY-MM-DD") with no time zone;
 * "today" is the date in Budapest. All arithmetic is done on UTC midnights, so daylight-saving changes never
 * shift a day.
 */

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const DAY_MS = 86_400_000;

const budapestDate = new Intl.DateTimeFormat('en-CA', {
	timeZone: 'Europe/Budapest',
	year: 'numeric',
	month: '2-digit',
	day: '2-digit'
});

function pad(value: number, width: number): string {
	return String(value).padStart(width, '0');
}

/** Midnight UTC of a strict "YYYY-MM-DD" calendar date, or null when the text is not a real date. */
export function parseCalendarDate(value: unknown): Date | null {
	if (typeof value !== 'string') return null;
	const match = ISO_DATE.exec(value);
	if (!match) return null;
	const year = Number(match[1]);
	const month = Number(match[2]);
	const day = Number(match[3]);
	if (year < 1970 || year > 9999) return null;
	const date = new Date(Date.UTC(year, month - 1, day));
	if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
	return date;
}

export function isCalendarDate(value: unknown): value is string {
	return parseCalendarDate(value) !== null;
}

function toIso(date: Date): string {
	return `${pad(date.getUTCFullYear(), 4)}-${pad(date.getUTCMonth() + 1, 2)}-${pad(date.getUTCDate(), 2)}`;
}

/** Today's date in Budapest ("YYYY-MM-DD"). */
export function todayInBudapest(now: Date = new Date()): string {
	const parts = budapestDate.formatToParts(now);
	const part = (type: Intl.DateTimeFormatPartTypes): string => parts.find((p) => p.type === type)?.value ?? '';
	return `${part('year')}-${part('month')}-${part('day')}`;
}

/** `iso` plus `days` calendar days. Throws on an invalid date (callers validate first). */
export function addDays(iso: string, days: number): string {
	const date = parseCalendarDate(iso);
	if (date === null || !Number.isInteger(days)) throw new RangeError(`invalid date arithmetic: ${iso} + ${days}`);
	return toIso(new Date(date.getTime() + days * DAY_MS));
}

/** Days from `iso` to the last day of its month, both included (1–31). */
export function daysToMonthEnd(iso: string): number {
	const date = parseCalendarDate(iso);
	if (date === null) throw new RangeError(`invalid date: ${iso}`);
	const lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
	return lastDay - date.getUTCDate() + 1;
}

/** Day of the week with Monday = 0 … Sunday = 6 (the Hungarian week starts on Monday). */
export function weekdayIndex(iso: string): number {
	const date = parseCalendarDate(iso);
	if (date === null) throw new RangeError(`invalid date: ${iso}`);
	return (date.getUTCDay() + 6) % 7;
}
