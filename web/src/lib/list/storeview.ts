/**
 * The shopping list for one chosen store: the store's quote lines joined with the list lines (for the
 * ingredient name and the list section), grouped by list section in the docs/DATA.md order, each section in
 * list order.
 */
import type { ListLineOut, QuoteLineOut, StoreQuoteOut } from '../api/types';
import { FALLBACK_GROUP, groupLines, type LineGroup } from './groups';

export interface StoreLine {
	line: QuoteLineOut;
	/** The ingredient's Hungarian name (plain text); the id when the list no longer has the line. */
	name: string;
	list_group: string;
}

/** The store's lines in list order (lines unknown to the list last, in quote order). */
export function storeLines(store: Pick<StoreQuoteOut, 'lines'>, listLines: readonly ListLineOut[]): StoreLine[] {
	const position = new Map(listLines.map((line, index) => [line.ingredient_id, index]));
	const byId = new Map(listLines.map((line) => [line.ingredient_id, line]));
	return store.lines
		.map((line, index) => {
			const listLine = byId.get(line.ingredient_id);
			return {
				order: position.get(line.ingredient_id) ?? listLines.length + index,
				view: {
					line,
					name: listLine?.name_hu ?? line.ingredient_id,
					list_group: listLine?.list_group ?? FALLBACK_GROUP
				}
			};
		})
		.sort((a, b) => a.order - b.order)
		.map(({ view }) => view);
}

export function storeGroups(store: Pick<StoreQuoteOut, 'lines'>, listLines: readonly ListLineOut[]): LineGroup<StoreLine>[] {
	return groupLines(storeLines(store, listLines));
}

/** True when any line of the store shows a KSH estimate (the view then needs the KSH attribution). */
export function hasKshEstimate(store: Pick<StoreQuoteOut, 'lines'>): boolean {
	return store.lines.some((line) => line.status === 'ksh_estimate' && line.ksh_estimate !== null);
}

/**
 * True when some priced line costs a fraction of a forint (sold by weight: price × exact weight). Each line is
 * shown rounded to whole forints while the total is the server's exact sum, so the shown lines may not add up
 * to the shown total; the view then says why. (No arithmetic on money here: the total stays the server's.)
 */
export function hasFractionalCosts(store: Pick<StoreQuoteOut, 'lines'>): boolean {
	return store.lines.some(
		(line) => line.status === 'priced' && line.checkout_cost !== null && !Number.isInteger(line.checkout_cost)
	);
}
