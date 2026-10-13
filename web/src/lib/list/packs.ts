/**
 * Quantity and pack labels for the store list: "2 × 175 g", "1,5 kg", "500 ml", "10 db", "2 990 Ft/kg".
 * Always hu-HU numbers (src/lib/format.ts); unit names come from the i18n layer. Amounts below 1 kg or 1 l
 * are shown in grams or millilitres, which is how packs are labelled in the shop.
 */
import type { PickOut, Unit } from '../api/types';
import { formatMoney, formatNumber, formatQty, unitName } from '../format';
import { translate } from '../i18n/messages';
import type { Lang } from '../storage';

const NBSP = '\u00a0';
const DASH = '–';
/** Quantities are exact to 0.001 canonical units; anything smaller is rounding noise. */
const EPSILON = 0.0005;

/** A quantity in its canonical unit; below 1 kg / 1 l in g / ml: (0.175, "kg") -> "175 g". */
export function formatAmount(qty: number, unit: Unit, lang: Lang): string {
	if (!Number.isFinite(qty)) return DASH;
	if ((unit === 'kg' || unit === 'l') && qty > 0 && qty < 1) {
		const small = Math.round(qty * 1_000_000) / 1000;
		return `${formatNumber(small)}${NBSP}${translate(lang, unit === 'kg' ? 'list.unit_g' : 'list.unit_ml')}`;
	}
	return formatQty(qty, unit, lang);
}

/** "2 × 175 g" for whole packs; null for a sold-by-weight pick (its weight is shown instead). */
export function packsText(pick: Pick<PickOut, 'count' | 'option'>, unit: Unit, lang: Lang): string | null {
	const size = pick.option.pack_size;
	if (size === null || !Number.isFinite(size) || size <= 0) return null;
	return `${pick.count}${NBSP}×${NBSP}${formatAmount(size, unit, lang)}`;
}

/** A unit price: (2990, "kg") -> "2 990 Ft/kg". */
export function unitPriceText(price: number, unit: Unit, lang: Lang): string {
	return `${formatMoney(price)}/${unitName(unit, lang)}`;
}

/** The leftover after buying whole packs, or null when there is none worth mentioning. */
export function leftoverText(leftover: number | null, unit: Unit, lang: Lang): string | null {
	if (leftover === null || !Number.isFinite(leftover) || leftover < EPSILON) return null;
	return formatAmount(leftover, unit, lang);
}
