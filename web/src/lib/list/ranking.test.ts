// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { QuoteResponse, RankOut, StoreQuoteOut } from '../api/types';
import { translate } from '../i18n/messages';
import { hasPenalty, priceScopeKey, priceTypeKey, rankingRows, scopeNote, splitMissing, splitParts } from './ranking';

function storeQuote(id: string, chain: string, total: number, assumed = 0): StoreQuoteOut {
	return {
		store_id: id,
		chain,
		checkout_total: total,
		used_total: total,
		missing: [],
		assumed_count: assumed,
		ksh_estimate_total: 0,
		lines: []
	};
}

function rank(id: string, r: number, total: number, missing = 0, penalized = total): RankOut {
	return { store_id: id, rank: r, checkout_total: total, penalized_total: penalized, missing_count: missing };
}

describe('rankingRows', () => {
	// Server order inside the tie (store id) is "a-…", "z-…"; distance puts "z-tesco" first; chain names would
	// put "aldi" first. The client must follow distance only.
	const quote: Pick<QuoteResponse, 'ranking' | 'stores'> = {
		stores: [
			storeQuote('a-spar', 'spar', 5000, 2),
			storeQuote('m-aldi', 'aldi', 5000),
			storeQuote('z-tesco', 'tesco', 5000),
			storeQuote('b-lidl', 'lidl', 4000),
			storeQuote('c-penny', 'penny', 6000)
		],
		ranking: [
			rank('b-lidl', 1, 4000),
			rank('a-spar', 2, 5000),
			rank('m-aldi', 2, 5000),
			rank('z-tesco', 2, 5000),
			rank('c-penny', 5, 5800, 1, 6200)
		]
	};
	const distances = new Map([
		['b-lidl', 1.2],
		['a-spar', 0.9],
		['m-aldi', 0.4],
		['z-tesco', 0.1],
		['c-penny', 0.3]
	]);

	it('orders by rank, and a tie group by distance (never by chain or store name)', () => {
		const rows = rankingRows(quote, distances);
		expect(rows.map((r) => r.storeId)).toEqual(['b-lidl', 'z-tesco', 'm-aldi', 'a-spar', 'c-penny']);
		expect(rows.map((r) => r.rank)).toEqual([1, 2, 2, 2, 5]);
	});

	it('marks every member of a tie, and only them', () => {
		const rows = rankingRows(quote, distances);
		expect(rows.map((r) => r.tied)).toEqual([false, true, true, true, false]);
	});

	it('carries totals, missing and assumed counts and the distance', () => {
		const rows = rankingRows(quote, distances);
		expect(rows[3]).toEqual({
			storeId: 'a-spar',
			rank: 2,
			tied: true,
			chain: 'spar',
			checkoutTotal: 5000,
			penalizedTotal: 5000,
			missingCount: 0,
			assumedCount: 2,
			kshEstimateTotal: 0,
			distanceKm: 0.9
		});
		expect(rows[4]).toMatchObject({ missingCount: 1, penalizedTotal: 6200, checkoutTotal: 5800 });
	});

	it('keeps the server order for equal distances and puts unknown distances last in a tie', () => {
		const rows = rankingRows(quote, new Map([['m-aldi', 0.5], ['z-tesco', 0.5]]));
		expect(rows.map((r) => r.storeId)).toEqual(['b-lidl', 'm-aldi', 'z-tesco', 'a-spar', 'c-penny']);
		expect(rows[3]?.distanceKm).toBeNull();
	});

	it('skips a ranked store without a store quote', () => {
		const rows = rankingRows({ stores: [storeQuote('x', 'aldi', 1)], ranking: [rank('x', 1, 1), rank('ghost', 2, 2)] }, new Map());
		expect(rows.map((r) => r.storeId)).toEqual(['x']);
		expect(rows[0]?.tied).toBe(false);
	});
});

describe('hasPenalty', () => {
	it('is true only when missing lines change the whole-forint total', () => {
		expect(hasPenalty({ missingCount: 1, checkoutTotal: 5800, penalizedTotal: 6200 })).toBe(true);
		expect(hasPenalty({ missingCount: 1, checkoutTotal: 5800, penalizedTotal: 5800.4 })).toBe(false);
		expect(hasPenalty({ missingCount: 0, checkoutTotal: 5800, penalizedTotal: 6200 })).toBe(false);
	});
});

describe('splitParts', () => {
	it('lists each store with its lines, in the server order', () => {
		expect(
			splitParts({
				store_ids: ['s-lidl', 's-tesco'],
				assignment: { repa: 's-lidl', csirkemell: 's-tesco', rizs: 's-lidl' }
			})
		).toEqual([
			{ storeId: 's-lidl', ingredientIds: ['repa', 'rizs'] },
			{ storeId: 's-tesco', ingredientIds: ['csirkemell'] }
		]);
	});
});

describe('price labels', () => {
	it('never turns DISCOUNTED into an "akció"/deal badge', () => {
		const key = priceTypeKey('DISCOUNTED');
		expect(key).toBe('core.price_discounted');
		expect(translate('hu', 'core.price_discounted')).toBe('kedvezményes ár (GVH-jelölés)');
		for (const lang of ['hu', 'en'] as const) {
			expect(translate(lang, 'core.price_discounted')).not.toMatch(/akci|deal|sale/i);
			expect(translate(lang, 'list.price_loyalty')).not.toMatch(/akci|deal|sale/i);
		}
	});

	it('labels loyalty prices and leaves normal prices unlabelled', () => {
		expect(priceTypeKey('LOYALTY')).toBe('list.price_loyalty');
		expect(priceTypeKey('NORMAL')).toBeNull();
	});

	it('distinguishes store prices from chain prices', () => {
		expect(translate('hu', priceScopeKey('store'))).toBe('bolti ár');
		expect(translate('hu', priceScopeKey('chain'))).toBe('lánc ár');
		expect(translate('en', priceScopeKey('chain'))).toBe('chain price');
	});
});

describe('scopeNote', () => {
	const quote = {
		scope_note_hu: 'a kiválasztott boltok közül, a 2026-10-13-i GVH-adatok alapján',
		scope_note_en: 'among the selected stores, based on GVH data of 2026-10-13'
	};

	it('uses the server text in the UI language', () => {
		expect(scopeNote(quote, 'hu')).toBe(quote.scope_note_hu);
		expect(scopeNote(quote, 'en')).toBe(quote.scope_note_en);
		expect(scopeNote({ ...quote, scope_note_en: '' }, 'en')).toBe(quote.scope_note_hu);
	});

	it('fits the ranking sentence in both languages', () => {
		expect(translate('hu', 'list.ranking_scope', { note: scopeNote(quote, 'hu') })).toBe(
			'Legolcsóbb elöl, a kiválasztott boltok közül, a 2026-10-13-i GVH-adatok alapján.'
		);
	});
});

describe('splitMissing', () => {
	const store = (store_id: string, missing: string[]) => ({ store_id, missing });

	it('returns the lines neither store of the split sells, in the first store’s order', () => {
		const stores = [
			store('synthetic-lidl-a', ['lencse', 'bazsalikom', 'tojas']),
			store('synthetic-aldi-a', []),
			store('synthetic-tesco-a', ['tojas', 'lencse'])
		];
		expect(splitMissing({ store_ids: ['synthetic-lidl-a', 'synthetic-tesco-a'] }, stores)).toEqual(['lencse', 'tojas']);
		expect(splitMissing({ store_ids: ['synthetic-tesco-a', 'synthetic-lidl-a'] }, stores)).toEqual(['tojas', 'lencse']);
	});

	it('is empty when the other store covers every missing line, or a store is unknown', () => {
		const stores = [store('a-1', ['lencse']), store('b-1', ['tojas'])];
		expect(splitMissing({ store_ids: ['a-1', 'b-1'] }, stores)).toEqual([]);
		expect(splitMissing({ store_ids: ['a-1', 'x-1'] }, stores)).toEqual([]);
	});

	it('lists a line once even when a store repeats it', () => {
		expect(splitMissing({ store_ids: ['a-1', 'b-1'] }, [store('a-1', ['so', 'so']), store('b-1', ['so'])])).toEqual(['so']);
	});
});
