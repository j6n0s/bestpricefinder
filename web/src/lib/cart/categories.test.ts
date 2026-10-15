import { describe, expect, it } from 'vitest';
import type { IngredientOut } from '../api/types';
import { SUBCATEGORY_ORDER, categoriesOf, isSubcategory, selectGoods, subcategoriesOf, subcategoryLabelKey } from './categories';

function good(id: string, group: string, tags: string[] = []): IngredientOut {
	return {
		id,
		name_hu: id,
		list_group: group,
		unit: 'kg',
		piece_weight_kg: null,
		pantry: false,
		priced_by: 'gvh',
		tags: tags as IngredientOut['tags']
	};
}

describe('subcategoriesOf', () => {
	it('is the known tags in menu order, or "other"', () => {
		expect(subcategoriesOf(good('a', 'hus_hal', ['processed_meat', 'red_meat']))).toEqual(['red_meat', 'processed_meat']);
		expect(subcategoriesOf(good('b', 'szaraz_tartos', []))).toEqual(['other']);
		expect(subcategoriesOf(good('c', 'szaraz_tartos', ['brand_new_tag']))).toEqual(['other']); // a future vocabulary value
		expect(subcategoriesOf(good('d', 'szaraz_tartos', ['other']))).toEqual(['other']);
	});

	it('has a label key for every subcategory', () => {
		for (const sub of SUBCATEGORY_ORDER) expect(subcategoryLabelKey(sub)).toBe(sub === 'other' ? 'cart.sub_misc' : `cart.sub_${sub}`);
		expect(isSubcategory('fruit')).toBe(true);
		expect(isSubcategory('fruits')).toBe(false);
	});
});

const GOODS = [
	good('tej', 'tejtermek_tojas', ['dairy']),
	good('kave', 'szaraz_tartos'),
	good('alma', 'zoldseg_gyumolcs', ['fruit']),
	good('tojas', 'tejtermek_tojas', ['egg']),
	good('joghurt', 'tejtermek_tojas', ['dairy', 'sweet']),
	good('kenyer', 'pekaru', ['grain']),
	good('krumpli', 'zoldseg_gyumolcs', ['potato']),
	good('titok', 'uj_csoport', ['vegetable']) // an unknown section is shown under "egyeb"
];

describe('categoriesOf', () => {
	it('lists the sections with goods in order, each with its subcategories and sizes', () => {
		expect(categoriesOf(GOODS)).toEqual([
			{
				group: 'zoldseg_gyumolcs',
				count: 2,
				subcategories: [
					{ id: 'potato', count: 1 },
					{ id: 'fruit', count: 1 }
				]
			},
			{ group: 'pekaru', count: 1, subcategories: [{ id: 'grain', count: 1 }] },
			{
				group: 'tejtermek_tojas',
				count: 3,
				subcategories: [
					{ id: 'dairy', count: 2 },
					{ id: 'egg', count: 1 },
					{ id: 'sweet', count: 1 }
				]
			},
			{ group: 'szaraz_tartos', count: 1, subcategories: [{ id: 'other', count: 1 }] },
			{ group: 'egyeb', count: 1, subcategories: [{ id: 'vegetable', count: 1 }] }
		]);
		expect(categoriesOf([])).toEqual([]);
	});
});

describe('selectGoods', () => {
	it('keeps the goods of the section, or of one subcategory of it, in the input order', () => {
		const ids = (goods: IngredientOut[]): string[] => goods.map((g) => g.id);
		expect(ids(selectGoods(GOODS, { group: 'tejtermek_tojas', sub: null }))).toEqual(['tej', 'tojas', 'joghurt']);
		expect(ids(selectGoods(GOODS, { group: 'tejtermek_tojas', sub: 'dairy' }))).toEqual(['tej', 'joghurt']);
		expect(ids(selectGoods(GOODS, { group: 'tejtermek_tojas', sub: 'sweet' }))).toEqual(['joghurt']);
		expect(ids(selectGoods(GOODS, { group: 'szaraz_tartos', sub: 'other' }))).toEqual(['kave']);
		expect(ids(selectGoods(GOODS, { group: 'egyeb', sub: null }))).toEqual(['titok']);
		expect(ids(selectGoods(GOODS, { group: 'fagyasztott', sub: null }))).toEqual([]);
	});
});
