/**
 * Number, money, quantity and date formatting. Always hu-HU, in both UI languages (user decision):
 * "1 234 Ft", "0,4 kg", "2026. 10. 13.". The space inside numbers and before units is a no-break space
 * (U+00A0) so a price never wraps across lines.
 */
import type { Unit } from './api/types';
import { coreEn } from './i18n/core.en';
import { coreHu } from './i18n/core.hu';
import type { Lang } from './storage';

const LOCALE = 'hu-HU';
const NBSP = ' ';
const DASH = '–';

// hu-HU groups only from 5 digits by default ("1234"); the app always groups ("1 234").
const moneyFormat = new Intl.NumberFormat(LOCALE, {
	maximumFractionDigits: 0,
	useGrouping: 'always',
	signDisplay: 'negative'
});
const qtyFormat = new Intl.NumberFormat(LOCALE, {
	maximumFractionDigits: 3,
	useGrouping: 'always',
	signDisplay: 'negative'
});
const kmFormat = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const percentFormat = new Intl.NumberFormat(LOCALE, { style: 'percent', maximumFractionDigits: 0 });
const dateFormat = new Intl.DateTimeFormat(LOCALE, { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'UTC' });
const monthFormat = new Intl.DateTimeFormat(LOCALE, { year: 'numeric', month: '2-digit', timeZone: 'UTC' });
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
	year: 'numeric',
	month: '2-digit',
	day: '2-digit',
	hour: 'numeric',
	minute: '2-digit',
	timeZone: 'Europe/Budapest'
});

/** HUF rounded to whole forints: 1234.5 -> "1 235 Ft". Non-finite values give "–". */
export function formatMoney(value: number): string {
	if (!Number.isFinite(value)) return DASH;
	return `${moneyFormat.format(value)}${NBSP}Ft`;
}

/** A plain number with at most 3 decimals: 0.4 -> "0,4", 1234 -> "1 234". */
export function formatNumber(value: number): string {
	if (!Number.isFinite(value)) return DASH;
	return qtyFormat.format(value);
}

/** Unit name in the UI language: kg, l, db (EN: pcs). */
export function unitName(unit: Unit, lang: Lang): string {
	const dict = lang === 'en' ? coreEn : coreHu;
	switch (unit) {
		case 'kg':
			return dict.unit_kg;
		case 'l':
			return dict.unit_l;
		case 'db':
			return dict.unit_db;
	}
}

/** A quantity in its canonical unit: (0.4, "kg") -> "0,4 kg"; (2, "db", "en") -> "2 pcs". */
export function formatQty(qty: number, unit: Unit, lang: Lang = 'hu'): string {
	return `${formatNumber(qty)}${NBSP}${unitName(unit, lang)}`;
}

/** A distance: below 1 km in metres rounded to 10 m ("850 m"), else km with one decimal ("1,5 km"). */
export function formatDistance(km: number): string {
	if (!Number.isFinite(km) || km < 0) return DASH;
	const metres = Math.round((km * 1000) / 10) * 10;
	if (metres < 1000) return `${metres}${NBSP}m`;
	return `${kmFormat.format(km)}${NBSP}km`;
}

/** A 0..1 share as a whole percentage: 0.9 -> "90%". */
export function formatPercent(share: number): string {
	if (!Number.isFinite(share)) return DASH;
	return percentFormat.format(share);
}

/** Parses a strict calendar date "YYYY-MM-DD" (a full ISO date-time is accepted and cut to its date). */
export function parseIsoDate(value: string): Date | null {
	const match = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/.exec(value);
	if (!match) return null;
	const year = Number(match[1]);
	const month = Number(match[2]);
	const day = Number(match[3]);
	const date = new Date(Date.UTC(year, month - 1, day));
	if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
	return date;
}

/** "2026-10-13" -> "2026. 10. 13."; null or an invalid date -> "". */
export function formatDate(iso: string | null | undefined): string {
	if (!iso) return '';
	const date = parseIsoDate(iso);
	return date ? dateFormat.format(date) : '';
}

/** "2026-09-01" -> "2026. 09." (the KSH period is a month); null or invalid -> "". */
export function formatMonth(iso: string | null | undefined): string {
	if (!iso) return '';
	const date = parseIsoDate(iso);
	return date ? monthFormat.format(date) : '';
}

/** An ISO date-time in Budapest time: "2026-10-13T02:31:00Z" -> "2026. 10. 13. 4:31"; invalid -> "". */
export function formatDateTime(iso: string | null | undefined): string {
	if (!iso) return '';
	const time = Date.parse(iso);
	return Number.isNaN(time) ? '' : dateTimeFormat.format(new Date(time));
}
