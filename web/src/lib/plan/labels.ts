/** Day labels of the plan ("Kedd, 2026. 10. 13." / "3. nap"), shared by the plan page and the recipe page. */
import { formatDate } from '../format';
import { translate, type PlainKey } from '../i18n/messages';
import type { Lang } from '../storage';

const WEEKDAY_KEYS: readonly PlainKey[] = [
	'plan.weekday_0',
	'plan.weekday_1',
	'plan.weekday_2',
	'plan.weekday_3',
	'plan.weekday_4',
	'plan.weekday_5',
	'plan.weekday_6'
];

/** Monday = 0 … Sunday = 6. */
export function weekdayName(weekday: number, lang: Lang): string {
	const key = WEEKDAY_KEYS[weekday];
	return key ? translate(lang, key) : '';
}

export interface DayLike {
	index: number;
	date: string | null;
	weekday: number | null;
}

/** "Kedd, 2026. 10. 13." for a dated day, "3. nap" / "Day 3" for an undated one. */
export function dayLabel(day: DayLike, lang: Lang): string {
	const date = formatDate(day.date);
	if (date && day.weekday !== null && WEEKDAY_KEYS[day.weekday]) {
		return translate(lang, 'plan.day_heading', { weekday: weekdayName(day.weekday, lang), date });
	}
	return translate(lang, 'plan.day_undated', { number: day.index + 1 });
}
