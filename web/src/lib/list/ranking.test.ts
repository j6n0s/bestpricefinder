// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { QuoteResponse, RankOut, StoreQuoteOut } from '../api/types';
import { translate } from '../i18n/messages';
import { hasPenalty, priceNoteKeys, priceTypeKey, rankingRows, scopeNote, sharedNoteKeys } from './ranking';

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

	it('tells chain prices and unconfirmed stock apart from the own store price, in plain words', () => {
		const notes = (price_scope: 'store' | 'chain', availability: 'confirmed' | 'assumed', lang: 'hu' | 'en' = 'hu') =>
			priceNoteKeys({ price_scope, availability }).map((key) => translate(lang, key));
		expect(notes('store', 'confirmed')).toEqual([]);
		expect(notes('chain', 'confirmed')).toEqual(['A lánc ára, itt eltérhet.']);
		expect(notes('chain', 'assumed')).toEqual(['A lánc ára, itt eltérhet.', 'Nem biztos, hogy itt kapható.']);
		expect(notes('store', 'assumed', 'en')).toEqual(['May not be stocked here.']);
	});

	it('says a note once for the store when every product there shares it', () => {
		const opt = (price_scope: 'store' | 'chain', availability: 'confirmed' | 'assumed') => ({ price_scope, availability });
		const line = (status: 'priced' | 'unavailable', picks: ReturnType<typeof opt>[], alternatives: ReturnType<typeof opt>[] = []) => ({
			status,
			picks: picks.map((option) => ({ count: 1, qty: 1, cost: 1, option })),
			alternatives
		});
		const shared = (lines: ReturnType<typeof line>[]) => sharedNoteKeys(lines as never);
		expect(shared([line('priced', [opt('chain', 'assumed')]), line('priced', [opt('chain', 'confirmed')])])).toEqual(['list.note_chain']);
		expect(shared([line('priced', [opt('chain', 'assumed')], [opt('chain', 'assumed')])])).toEqual(['list.note_chain', 'list.note_assumed']);
		// One store price (a pick or an alternative) keeps the chain note on the lines.
		expect(shared([line('priced', [opt('chain', 'confirmed')], [opt('store', 'confirmed')])])).toEqual([]);
		expect(shared([line('priced', [opt('store', 'confirmed')]), line('priced', [opt('chain', 'confirmed')])])).toEqual([]);
		// Lines without prices do not count; no priced line, no shared note.
		expect(shared([line('unavailable', []), line('priced', [opt('chain', 'confirmed')])])).toEqual(['list.note_chain']);
		expect(shared([line('unavailable', [])])).toEqual([]);
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
