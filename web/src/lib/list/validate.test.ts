// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { QuoteResponse } from '../api/types';
import { recipeIds, validIngredients, validListLines, validQuote, validStores } from './validate';

const LINE = {
	ingredient_id: 'repa',
	name_hu: 'sárgarépa',
	qty: 0.5,
	unit: 'kg',
	list_group: 'zoldseg_gyumolcs',
	pantry: false,
	recipe_ids: ['minta-recept']
};

function quote(): QuoteResponse {
	return {
		data_date: '2026-10-13',
		stores: [
			{
				store_id: 's-1',
				chain: 'lidl',
				checkout_total: 1000,
				used_total: 900,
				missing: [],
				assumed_count: 0,
				ksh_estimate_total: 0,
				lines: [
					{
						ingredient_id: 'repa',
						qty: 0.5,
						unit: 'kg',
						status: 'priced',
						picks: [
							{
								option: {
									product_id: 'p-1',
									product_name: 'Szintetikus répa',
									pack_size: 1,
									pack_price: 1000,
									unit_price: 1000,
									price_type: 'DISCOUNTED',
									price_scope: 'store',
									availability: 'confirmed'
								},
								count: 1,
								qty: 1,
								cost: 1000
							}
						],
						checkout_cost: 1000,
						used_cost: 500,
						leftover_qty: 0.5,
						ksh_estimate: null,
						alternatives: []
					}
				]
			}
		],
		ranking: [{ store_id: 's-1', rank: 1, checkout_total: 1000, penalized_total: 1000, missing_count: 0 }],
		split: null,
		scope_note_hu: 'a kiválasztott boltok közül, a 2026-10-13-i GVH-adatok alapján',
		scope_note_en: 'among the selected stores, based on GVH data of 2026-10-13',
		attribution: {
			gvh: { text_hu: 'Forrás: GVH Árfigyelő (arfigyelo.gvh.hu)', text_en: 'Source', url: 'https://arfigyelo.gvh.hu' },
			ksh: { text_hu: 'Forrás: KSH', text_en: 'Source: KSH', url: 'https://www.ksh.hu/' }
		}
	};
}

describe('validListLines', () => {
	it('accepts the contract shape and drops repeated ingredient ids', () => {
		expect(validListLines({ lines: [LINE, { ...LINE, qty: 9 }] })).toEqual([LINE]);
		expect(validListLines({ lines: [] })).toEqual([]);
	});

	it('rejects a malformed answer as a whole', () => {
		for (const body of [
			null,
			[],
			{},
			{ lines: 'x' },
			{ lines: [{ ...LINE, qty: 'many' }] },
			{ lines: [{ ...LINE, qty: Number.NaN }] },
			{ lines: [{ ...LINE, unit: 'g' }] },
			{ lines: [{ ...LINE, pantry: 'no' }] },
			{ lines: [{ ...LINE, recipe_ids: [1] }] },
			{ lines: [{ ...LINE, name_hu: null }] }
		]) {
			expect(validListLines(body)).toBeNull();
		}
	});
});

describe('validQuote', () => {
	it('accepts the contract shape', () => {
		expect(validQuote(quote())).toEqual(quote());
	});

	it('accepts a split and a missing split', () => {
		const withSplit = { ...quote(), split: { store_ids: ['s-1', 's-2'], total: 900, saving: 1600, assignment: { repa: 's-1' } } };
		expect(validQuote(withSplit)?.split).toEqual(withSplit.split);
		const { split: _split, ...withoutSplit } = quote();
		expect(validQuote(withoutSplit)?.split).toBeNull();
	});

	it('drops repeated stores and ranks', () => {
		const q = quote();
		const doubled = { ...q, stores: [...q.stores, ...q.stores], ranking: [...q.ranking, ...q.ranking] };
		const result = validQuote(doubled);
		expect(result?.stores).toHaveLength(1);
		expect(result?.ranking).toHaveLength(1);
	});

	it('rejects malformed answers', () => {
		const q = quote();
		const store = q.stores[0];
		const line = store?.lines[0];
		if (!store || !line) throw new Error('fixture');
		const cases: unknown[] = [
			null,
			{ ...q, data_date: '13/10/2026' },
			{ ...q, stores: 'x' },
			{ ...q, ranking: [{ ...q.ranking[0], rank: 0 }] },
			{ ...q, ranking: [{ ...q.ranking[0], rank: 1.5 }] },
			{ ...q, scope_note_hu: '' },
			{ ...q, scope_note_en: null },
			{ ...q, attribution: null },
			{ ...q, split: { store_ids: ['s-1'], total: 1, saving: 1, assignment: {} } },
			{ ...q, split: { store_ids: ['s-1', 's-1'], total: 1, saving: 1, assignment: {} } },
			{ ...q, stores: [{ ...store, checkout_total: '1000' }] },
			{ ...q, stores: [{ ...store, lines: [{ ...line, status: 'cheap' }] }] },
			{ ...q, stores: [{ ...store, lines: [{ ...line, picks: [{ count: 1 }] }] }] },
			{ ...q, stores: [{ ...store, lines: [{ ...line, alternatives: [{ product_id: 'x' }] }] }] },
			{ ...q, stores: [{ ...store, lines: [{ ...line, checkout_cost: Number.POSITIVE_INFINITY }] }] }
		];
		for (const body of cases) expect(validQuote(body)).toBeNull();
	});
});

describe('validIngredients', () => {
	const ING = { id: 'so', name_hu: 'só', list_group: 'fuszer_olaj', unit: 'kg', piece_weight_kg: null, pantry: true, priced_by: 'none', tags: [] };

	it('keeps well-formed rows once each', () => {
		expect(validIngredients({ ingredients: [ING, { ...ING, name_hu: 'másik' }, { ...ING, id: 'bors', name_hu: 1 }] })).toEqual([ING]);
	});

	it('gives nothing for a malformed answer', () => {
		expect(validIngredients(null)).toEqual([]);
		expect(validIngredients({ ingredients: 'x' })).toEqual([]);
	});
});

describe('validStores', () => {
	const STORE = {
		id: 'synthetic-lidl-1',
		chain: 'lidl',
		postal_code: '1051',
		city: 'Budapest',
		address: 'Minta utca 1.',
		lat: 47.5,
		lon: 19.05,
		format: null,
		is_budapest: true,
		has_data: true
	};

	it('keeps well-formed stores once each, including stores without coordinates', () => {
		const noCoords = { ...STORE, id: 'synthetic-aldi-1', chain: 'aldi', lat: null, lon: null, address: null };
		expect(validStores({ stores: [STORE, { ...STORE, chain: 'aldi' }, noCoords] })).toEqual([STORE, noCoords]);
	});

	it('drops malformed rows and rejects an answer without a store list', () => {
		expect(validStores({ stores: [{ ...STORE, lat: '47.5' }, { ...STORE, has_data: 'yes' }, { ...STORE, id: 7 }, null] })).toEqual([]);
		expect(validStores({})).toBeNull();
		expect(validStores(null)).toBeNull();
	});
});

describe('recipeIds', () => {
	it('keeps the string ids only', () => {
		expect(recipeIds([{ id: 'minta-a' }, { id: 7 }, null, 'x', { title: 'nincs id' }, { id: 'minta-b' }])).toEqual(['minta-a', 'minta-b']);
	});
});
