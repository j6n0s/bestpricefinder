/**
 * Shopping-list line handling on the device: which lines are to buy, which are "valószínűleg otthon van"
 * (pantry), which the user removed, and which go into POST /api/quote.
 *
 * Rules (docs/API.md "POST /api/quote", docs/DATA.md):
 * - A pantry line (`ListLineOut.pantry`) is shown in the "valószínűleg otthon van" section and stays out of
 *   the quote, unless the user marked it "nincs otthon" (`StoredState.pantry.notAtHome`).
 * - An ingredient stored as "enough at home" (`StoredState.pantry.onHand` entry with `qty: null`) is treated
 *   like a pantry line. An on-hand entry WITH a quantity is subtracted by the server instead (`on_hand`).
 * - A line the user removed from this list never goes into the quote.
 * - The quote takes at most 200 unique lines with 0 < qty ≤ 1000 and 1–25 unique store ids, and never
 *   anything else (no coordinates: the API client rebuilds the body from these fields only).
 */
import { ID_PATTERNS, LIMITS, type ListLineOut, type QtyLineIn, type QuoteRequest, type StoreId } from '../api/types';
import type { PantryEntry } from '../storage';

export interface LineChoices {
	/** Lines removed from this list by hand. */
	removed: ReadonlySet<string>;
	/** Pantry staples marked "nincs otthon": they are bought, so they go into the quote. */
	notAtHome: ReadonlySet<string>;
	/** Ingredients stored as "enough at home" (on-hand entries without a quantity). */
	enoughAtHome: ReadonlySet<string>;
}

export function lineChoices(
	removed: Iterable<string>,
	notAtHome: Iterable<string>,
	onHand: readonly PantryEntry[]
): LineChoices {
	return {
		removed: new Set(removed),
		notAtHome: new Set(notAtHome),
		enoughAtHome: new Set(onHand.filter((entry) => entry.qty === null).map((entry) => entry.ingredientId))
	};
}

type LineLike = Pick<ListLineOut, 'ingredient_id' | 'pantry'>;

/** Shown in the "valószínűleg otthon van" section (with a "nincs otthon" toggle). */
export function isPantryLike(line: LineLike, choices: LineChoices): boolean {
	return line.pantry || choices.enoughAtHome.has(line.ingredient_id);
}

export type LineKind = 'buy' | 'pantry_at_home' | 'pantry_missing' | 'removed';

/**
 * - `removed`: taken off this list by hand;
 * - `pantry_at_home`: a staple that is probably at home (not bought, not quoted);
 * - `pantry_missing`: a staple marked "nincs otthon" (bought and quoted);
 * - `buy`: everything else.
 */
export function lineKind(line: LineLike, choices: LineChoices): LineKind {
	if (choices.removed.has(line.ingredient_id)) return 'removed';
	if (isPantryLike(line, choices)) {
		return choices.notAtHome.has(line.ingredient_id) ? 'pantry_missing' : 'pantry_at_home';
	}
	return 'buy';
}

/** True for the lines that are bought, i.e. ticked off in the shop and sent to the quote. */
export function isBought(line: LineLike, choices: LineChoices): boolean {
	const kind = lineKind(line, choices);
	return kind === 'buy' || kind === 'pantry_missing';
}

export interface ListSections<T> {
	/** Non-pantry lines to buy, in input order. */
	buy: T[];
	/** Pantry lines (at home or marked "nincs otthon"), in input order. */
	pantry: T[];
	/** Lines removed by hand, in input order. */
	removed: T[];
}

export function listSections<T extends LineLike>(lines: readonly T[], choices: LineChoices): ListSections<T> {
	const sections: ListSections<T> = { buy: [], pantry: [], removed: [] };
	for (const line of lines) {
		const kind = lineKind(line, choices);
		if (kind === 'removed') sections.removed.push(line);
		else if (kind === 'buy') sections.buy.push(line);
		else sections.pantry.push(line);
	}
	return sections;
}

export interface QuoteLinesResult {
	lines: QtyLineIn[];
	/** Bought lines that could not be sent: over the 200-line limit, or a quantity outside 0 < qty ≤ 1000. */
	skipped: string[];
}

function validQty(qty: number): boolean {
	return Number.isFinite(qty) && qty > 0 && qty <= LIMITS.qtyMax;
}

/** The bought lines as quote lines: unique ingredient ids, in list order, at most 200. */
export function quoteLines(
	lines: readonly Pick<ListLineOut, 'ingredient_id' | 'pantry' | 'qty'>[],
	choices: LineChoices
): QuoteLinesResult {
	const out: QtyLineIn[] = [];
	const skipped: string[] = [];
	const seen = new Set<string>();
	for (const line of lines) {
		const id = line.ingredient_id;
		if (seen.has(id) || !isBought(line, choices)) continue;
		seen.add(id);
		if (!ID_PATTERNS.ingredient.test(id) || !validQty(line.qty) || out.length >= LIMITS.quoteLines) {
			skipped.push(id);
			continue;
		}
		out.push({ ingredient_id: id, qty: line.qty });
	}
	return { lines: out, skipped };
}

/**
 * The body of POST /api/quote, or null when there is nothing to price (no line or no store). Store ids are
 * de-duplicated, checked against the id pattern and capped at 25, in the given (nearest first) order.
 */
export function buildQuoteRequest(lines: readonly QtyLineIn[], storeIds: readonly StoreId[]): QuoteRequest | null {
	const stores: StoreId[] = [];
	for (const id of storeIds) {
		if (stores.length >= LIMITS.quoteStores) break;
		if (ID_PATTERNS.store.test(id) && !stores.includes(id)) stores.push(id);
	}
	if (lines.length === 0 || stores.length === 0) return null;
	return {
		lines: lines.map((line) => ({ ingredient_id: line.ingredient_id, qty: line.qty })),
		store_ids: stores,
		include_loyalty: false
	};
}

/** On-hand quantities for POST /api/list: entries with a quantity, unique, valid, at most 200. */
export function onHandForList(onHand: readonly PantryEntry[]): QtyLineIn[] {
	const out: QtyLineIn[] = [];
	const seen = new Set<string>();
	for (const entry of onHand) {
		if (out.length >= LIMITS.onHand) break;
		const { ingredientId, qty } = entry;
		if (qty === null || seen.has(ingredientId) || !ID_PATTERNS.ingredient.test(ingredientId) || !validQty(qty)) continue;
		seen.add(ingredientId);
		out.push({ ingredient_id: ingredientId, qty });
	}
	return out;
}

/** `ids` with `id` added (true) or removed (false), keeping the order; the input is never changed. */
export function toggleId(ids: readonly string[], id: string, on: boolean): string[] {
	const without = ids.filter((existing) => existing !== id);
	return on ? [...without, id] : without;
}
