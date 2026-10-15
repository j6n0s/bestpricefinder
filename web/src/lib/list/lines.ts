/**
 * Shopping-list line handling on the device: which lines are to buy, which are "valószínűleg otthon van"
 * (pantry), which the user removed, which the user excluded in the settings, and which go into
 * POST /api/quote.
 *
 * Rules (docs/API.md "POST /api/quote", docs/DATA.md):
 * - A pantry line (`ListLineOut.pantry`) is shown in the "valószínűleg otthon van" section and stays out of
 *   the quote, unless the user marked it "nincs otthon" (`StoredState.pantry.notAtHome`): a staple is either
 *   at home or bought. Amounts at home of any ingredient (`StoredState.pantry.onHand`) are subtracted on the
 *   device before these rules apply (./onhand.ts); the app never sends `on_hand`.
 * - Tap water (`viz`) is never bought: it stays "otthon van" and offers no "nincs otthon" switch.
 * - A line of an ingredient excluded in the settings (`StoredState.exclusions.ingredients`; it can come back
 *   through an optional recipe line or a hand-picked recipe) is not bought and not quoted, unless the user
 *   chose "mégis megveszem" for this list (`ListEntry.included`). An exclusion may be an allergy, so it is
 *   never bought silently.
 * - A line the user removed from this list never goes into the quote.
 * - The quote takes at most 200 unique lines with 0 < qty ≤ 1000 and 1–25 unique store ids, and never
 *   anything else (no coordinates: the API client rebuilds the body from these fields only).
 */
import { ID_PATTERNS, LIMITS, type ListLineOut, type QtyLineIn, type QuoteRequest, type StoreId } from '../api/types';

export interface LineChoices {
	/** Lines removed from this list by hand. */
	removed: ReadonlySet<string>;
	/** Pantry staples marked "nincs otthon": they are bought, so they go into the quote. */
	notAtHome: ReadonlySet<string>;
	/** Ingredients excluded in the settings: not bought unless in `included`. */
	excluded: ReadonlySet<string>;
	/** Excluded ingredients the user chose to buy anyway on this list ("mégis megveszem"). */
	included: ReadonlySet<string>;
}

export function lineChoices(
	removed: Iterable<string>,
	notAtHome: Iterable<string>,
	excluded: Iterable<string> = [],
	included: Iterable<string> = []
): LineChoices {
	return { removed: new Set(removed), notAtHome: new Set(notAtHome), excluded: new Set(excluded), included: new Set(included) };
}

/** Ingredients that are never bought (tap water): always "otthon van", with no "nincs otthon" switch. */
export const NEVER_BOUGHT: ReadonlySet<string> = new Set(['viz']);

/** True when the "nincs otthon" switch makes sense for this staple. */
export function canBeBought(ingredientId: string): boolean {
	return !NEVER_BOUGHT.has(ingredientId);
}

type LineLike = Pick<ListLineOut, 'ingredient_id' | 'pantry'>;

export type LineKind = 'buy' | 'pantry_at_home' | 'pantry_missing' | 'removed' | 'excluded';

/**
 * - `removed`: taken off this list by hand;
 * - `pantry_at_home`: a staple that is probably at home (not bought, not quoted), and tap water always;
 * - `excluded`: a line that would be bought, of an ingredient excluded in the settings, without
 *   "mégis megveszem" (not bought, not quoted);
 * - `pantry_missing`: a staple marked "nincs otthon" (bought and quoted);
 * - `buy`: everything else.
 */
export function lineKind(line: LineLike, choices: LineChoices): LineKind {
	const id = line.ingredient_id;
	if (choices.removed.has(id)) return 'removed';
	if (NEVER_BOUGHT.has(id)) return 'pantry_at_home';
	// A staple at home is not bought anyway: it stays in its usual section even when excluded.
	if (line.pantry && !choices.notAtHome.has(id)) return 'pantry_at_home';
	if (choices.excluded.has(id) && !choices.included.has(id)) return 'excluded';
	return line.pantry ? 'pantry_missing' : 'buy';
}

/** True for an excluded ingredient the user chose to buy anyway (shown with a "kizárt alapanyag" label). */
export function isIncludedExclusion(line: LineLike, choices: LineChoices): boolean {
	const id = line.ingredient_id;
	return choices.excluded.has(id) && choices.included.has(id) && isBought(line, choices);
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
	/** Lines of ingredients excluded in the settings (not bought), in input order. */
	excluded: T[];
	/** Lines removed by hand, in input order. */
	removed: T[];
}

export function listSections<T extends LineLike>(lines: readonly T[], choices: LineChoices): ListSections<T> {
	const sections: ListSections<T> = { buy: [], pantry: [], excluded: [], removed: [] };
	for (const line of lines) {
		const kind = lineKind(line, choices);
		if (kind === 'removed') sections.removed.push(line);
		else if (kind === 'excluded') sections.excluded.push(line);
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
 * de-duplicated, checked against the id pattern and capped at 25 in the given (nearest first) order, so the
 * nearest stores survive the cap; then they are SORTED BY ID. The server needs only the set (its ranking
 * ignores the request order, and the client orders ties by distance itself), and a nearest-first order would
 * tell the server far more about where the user is than the set does (an order-k Voronoi cell instead of the
 * ~100 m rounding). The order of `store_ids` therefore carries no location information.
 */
export function buildQuoteRequest(lines: readonly QtyLineIn[], storeIds: readonly StoreId[]): QuoteRequest | null {
	const stores: StoreId[] = [];
	for (const id of storeIds) {
		if (stores.length >= LIMITS.quoteStores) break;
		if (ID_PATTERNS.store.test(id) && !stores.includes(id)) stores.push(id);
	}
	if (lines.length === 0 || stores.length === 0) return null;
	// Default sort: UTF-16 code-unit order, deterministic and locale-free (the request body is memoised as a
	// string, so equal sets must give equal bodies).
	stores.sort();
	return {
		lines: lines.map((line) => ({ ingredient_id: line.ingredient_id, qty: line.qty })),
		store_ids: stores,
		include_loyalty: false
	};
}

/** `ids` with `id` added (true) or removed (false), keeping the order; the input is never changed. */
export function toggleId(ids: readonly string[], id: string, on: boolean): string[] {
	const without = ids.filter((existing) => existing !== id);
	return on ? [...without, id] : without;
}
