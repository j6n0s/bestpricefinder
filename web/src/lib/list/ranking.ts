/**
 * Display helpers for the POST /api/quote answer: the store ranking, the 2-store split and the per-line
 * price labels.
 *
 * Ties (BUILD-BRIEF §4.1 trap 13, docs/API.md): stores with the same `rank` are a tie group. The server's
 * order inside a group means nothing, so the client orders a group by distance (nearest first) and never by
 * chain or store name; equal distances keep the server's order. Every member of a tie is shown as tied.
 */
import type { PlainKey } from '../i18n/messages';
import type {
	ChainSlug,
	IngredientId,
	PriceScope,
	PriceType,
	QuoteResponse,
	SplitOut,
	StoreId,
	StoreQuoteOut
} from '../api/types';

export interface RankRow {
	storeId: StoreId;
	rank: number;
	/** Another store shares this rank. */
	tied: boolean;
	chain: ChainSlug;
	checkoutTotal: number;
	/** checkout total + the estimated cost of the missing lines (what the ranking is based on). */
	penalizedTotal: number;
	missingCount: number;
	assumedCount: number;
	kshEstimateTotal: number;
	/** Distance from the chosen origin; null when unknown. */
	distanceKm: number | null;
}

function byDistance(a: number | null, b: number | null): number {
	if (a === null && b === null) return 0;
	if (a === null) return 1;
	if (b === null) return -1;
	return a - b;
}

/** One row per ranked store: rank ascending, a tie group by distance. Ranks without a store quote are skipped. */
export function rankingRows(
	quote: Pick<QuoteResponse, 'ranking' | 'stores'>,
	distances: ReadonlyMap<StoreId, number>
): RankRow[] {
	const stores = new Map<StoreId, StoreQuoteOut>(quote.stores.map((store) => [store.store_id, store]));
	const rankCounts = new Map<number, number>();
	for (const rank of quote.ranking) rankCounts.set(rank.rank, (rankCounts.get(rank.rank) ?? 0) + 1);
	const rows: RankRow[] = [];
	for (const rank of quote.ranking) {
		const store = stores.get(rank.store_id);
		if (!store) continue;
		rows.push({
			storeId: rank.store_id,
			rank: rank.rank,
			tied: (rankCounts.get(rank.rank) ?? 0) > 1,
			chain: store.chain,
			checkoutTotal: rank.checkout_total,
			penalizedTotal: rank.penalized_total,
			missingCount: rank.missing_count,
			assumedCount: store.assumed_count,
			kshEstimateTotal: store.ksh_estimate_total,
			distanceKm: distances.get(rank.store_id) ?? null
		});
	}
	// Array.prototype.sort is stable: equal rank and distance keep the server's order.
	return rows.sort((a, b) => a.rank - b.rank || byDistance(a.distanceKm, b.distanceKm));
}

/** True when the missing lines' estimate changes the shown total (in whole forints). */
export function hasPenalty(row: Pick<RankRow, 'missingCount' | 'checkoutTotal' | 'penalizedTotal'>): boolean {
	return row.missingCount > 0 && Math.round(row.penalizedTotal) !== Math.round(row.checkoutTotal);
}

export interface SplitPart {
	storeId: StoreId;
	/** Ingredient ids bought at this store, in the server's assignment order. */
	ingredientIds: IngredientId[];
}

/** The two stores of a split (better-ranked first, as the server sends them) with their lines. */
export function splitParts(split: Pick<SplitOut, 'store_ids' | 'assignment'>): SplitPart[] {
	return split.store_ids.map((storeId) => ({
		storeId,
		ingredientIds: Object.entries(split.assignment)
			.filter(([, assigned]) => assigned === storeId)
			.map(([ingredientId]) => ingredientId)
	}));
}

/**
 * The lines neither store of a split sells (`missing` at both): the server leaves them out of the split's
 * `assignment` and `total`, so the card must name them. In the first store's line order, each once.
 */
export function splitMissing(
	split: Pick<SplitOut, 'store_ids'>,
	stores: readonly Pick<StoreQuoteOut, 'store_id' | 'missing'>[]
): IngredientId[] {
	const first = stores.find((store) => store.store_id === split.store_ids[0]);
	const second = stores.find((store) => store.store_id === split.store_ids[1]);
	if (!first || !second) return [];
	const atSecond = new Set(second.missing);
	return [...new Set(first.missing)].filter((ingredientId) => atSecond.has(ingredientId));
}

/**
 * Plain-text label of a price type. DISCOUNTED is NOT a deal flag (Aldi never sets it, and it also marks
 * long-running reductions), so it is only ever "kedvezményes ár (GVH-jelölés)", never an "akció" badge
 * (docs/API.md "Price types and deals"). NORMAL needs no label.
 */
export function priceTypeKey(type: PriceType): PlainKey | null {
	switch (type) {
		case 'DISCOUNTED':
			return 'core.price_discounted';
		case 'LOYALTY':
			return 'list.price_loyalty';
		case 'NORMAL':
			return null;
	}
}

/** "bolti ár" (this store's own reported price) or "lánc ár" (the price at most of the chain's stores). */
export function priceScopeKey(scope: PriceScope): PlainKey {
	return scope === 'store' ? 'list.scope_store' : 'list.scope_chain';
}

/** The quote's scope note in the UI language ("a kiválasztott boltok közül, a … GVH-adatok alapján"). */
export function scopeNote(quote: Pick<QuoteResponse, 'scope_note_hu' | 'scope_note_en'>, lang: 'hu' | 'en'): string {
	return lang === 'en' && quote.scope_note_en ? quote.scope_note_en : quote.scope_note_hu;
}
