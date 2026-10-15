/**
 * "Otthon lévő mennyiségek": amounts of any ingredient the user has at home (StoredState.pantry.onHand, in the
 * ingredient's own unit, on the cart's ladder of round amounts). The shopping list subtracts them ON THE
 * DEVICE before anything is quoted: a line fully covered is "otthon van" (shown in the pantry section with
 * the amount, not bought, not quoted); a line partly covered is bought for the rest, with a note. The app
 * never sends `on_hand` to the server (docs/API.md), so the list request and its offline copy do not depend on
 * the pantry. Pure helpers; tap water (never bought) is left alone.
 */
import type { ListLineOut } from '../api/types';
import type { StoredCartLine } from '../storage';
import { NEVER_BOUGHT } from './lines';

/** Quantities are kept to 3 decimals, like the cart; below this a remainder counts as nothing. */
const EPSILON = 1e-9;

export interface CoveredLine {
	/** The list line as the API returned it (its full quantity). */
	line: ListLineOut;
	/** The amount at home (at least the line's quantity). */
	onHand: number;
}

export interface OnHandResult {
	/** The lines to show and quote: amounts at home subtracted; a line's object is reused when nothing was. */
	lines: ListLineOut[];
	/** Lines fully covered by the amount at home, in list order. */
	covered: CoveredLine[];
	/** Per line that is still bought for a smaller amount: the amount at home that was subtracted. */
	reduced: ReadonlyMap<string, number>;
}

/** `ingredientId -> qty` for the stored amounts (invalid or non-positive amounts are ignored). */
export function onHandMap(lines: readonly StoredCartLine[]): Map<string, number> {
	const map = new Map<string, number>();
	for (const line of lines) {
		if (Number.isFinite(line.qty) && line.qty > 0 && !map.has(line.ingredientId)) map.set(line.ingredientId, line.qty);
	}
	return map;
}

/** The lines with the amounts at home subtracted; see the module comment. */
export function applyOnHand(lines: readonly ListLineOut[], onHand: ReadonlyMap<string, number>): OnHandResult {
	const out: ListLineOut[] = [];
	const covered: CoveredLine[] = [];
	const reduced = new Map<string, number>();
	for (const line of lines) {
		const home = onHand.get(line.ingredient_id);
		if (home === undefined || !(home > 0) || NEVER_BOUGHT.has(line.ingredient_id) || !Number.isFinite(line.qty)) {
			out.push(line);
			continue;
		}
		const remaining = Math.round((line.qty - home) * 1000) / 1000;
		if (remaining <= EPSILON) {
			covered.push({ line, onHand: home });
			continue;
		}
		reduced.set(line.ingredient_id, home);
		out.push({ ...line, qty: remaining });
	}
	return { lines: out, covered, reduced };
}

/**
 * `lines` with `ingredientId` at `qty` (added at the end when new; removed when qty is null or not positive),
 * rounded to 3 decimals and capped at `maxQty`; a new line beyond `maxLines` is not added. The input is never
 * changed.
 */
export function setOnHandQty(
	lines: readonly StoredCartLine[],
	ingredientId: string,
	qty: number | null,
	maxLines: number,
	maxQty: number
): StoredCartLine[] {
	const index = lines.findIndex((line) => line.ingredientId === ingredientId);
	if (qty === null) return lines.filter((line) => line.ingredientId !== ingredientId);
	const clean = Math.min(maxQty, Math.round(qty * 1000) / 1000);
	if (!(clean > 0)) return lines.filter((line) => line.ingredientId !== ingredientId);
	if (index >= 0) return lines.map((line, i) => (i === index ? { ingredientId, qty: clean } : line));
	if (lines.length >= maxLines) return lines.slice();
	return [...lines, { ingredientId, qty: clean }];
}
