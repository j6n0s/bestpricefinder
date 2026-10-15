/**
 * "Kategóriák" on the cart page: the goods browsed like a shop's menu. A bar of shop sections (the list groups,
 * in the docs/DATA.md order) and, under a section, its subcategories: the IngredientTag values of its goods
 * (server/bpf/pricing/model.py; `tags` of GET /api/ingredients), in a fixed order, with "other" for the goods
 * that have no known tag. A good with several tags is in each of them. A section whose goods all fall in one
 * subcategory needs no menu: its button chooses the whole section. A tag the client does not know (a future
 * vocabulary value) counts as "other", so a new server value never breaks the page or gets an untranslated
 * label. Pure helpers; nothing here is stored or sent anywhere.
 */
import type { IngredientOut } from '../api/types';
import type { PlainKey } from '../i18n/messages';
import { LIST_GROUP_ORDER, displayGroup, type ListGroup } from '../list/groups';

/** The subcategories in menu order: the tag vocabulary, grouped by kind, "other" last. */
export const SUBCATEGORY_ORDER = [
	'vegetable',
	'potato',
	'fruit',
	'dairy',
	'egg',
	'red_meat',
	'poultry',
	'processed_meat',
	'fish',
	'grain',
	'wholegrain',
	'legume',
	'nut_seed',
	'sweet',
	'fat_oil',
	'spice',
	'condiment',
	'other'
] as const;

export type Subcategory = (typeof SUBCATEGORY_ORDER)[number];

const SUBCATEGORY_KEYS: Readonly<Record<Subcategory, PlainKey>> = {
	vegetable: 'cart.sub_vegetable',
	potato: 'cart.sub_potato',
	fruit: 'cart.sub_fruit',
	dairy: 'cart.sub_dairy',
	egg: 'cart.sub_egg',
	red_meat: 'cart.sub_red_meat',
	poultry: 'cart.sub_poultry',
	processed_meat: 'cart.sub_processed_meat',
	fish: 'cart.sub_fish',
	grain: 'cart.sub_grain',
	wholegrain: 'cart.sub_wholegrain',
	legume: 'cart.sub_legume',
	nut_seed: 'cart.sub_nut_seed',
	sweet: 'cart.sub_sweet',
	fat_oil: 'cart.sub_fat_oil',
	spice: 'cart.sub_spice',
	condiment: 'cart.sub_condiment',
	other: 'cart.sub_misc' // not `sub_other`: a key ending in _other is read as a plural form
};

export function isSubcategory(value: unknown): value is Subcategory {
	return typeof value === 'string' && (SUBCATEGORY_ORDER as readonly string[]).includes(value);
}

/** The i18n key of a subcategory's label. */
export function subcategoryLabelKey(sub: Subcategory): PlainKey {
	return SUBCATEGORY_KEYS[sub];
}

type Tagged = Pick<IngredientOut, 'list_group' | 'tags'>;

/** The subcategories a good is in: its known tags, in menu order; "other" when it has none. */
export function subcategoriesOf(good: Pick<IngredientOut, 'tags'>): Subcategory[] {
	const tags = new Set(good.tags);
	const known = SUBCATEGORY_ORDER.filter((sub) => sub !== 'other' && tags.has(sub));
	return known.length > 0 ? known : ['other'];
}

export interface SubcategoryEntry {
	id: Subcategory;
	/** Goods of the section in this subcategory. */
	count: number;
}

export interface Category {
	group: ListGroup;
	/** Goods of the section. */
	count: number;
	/** In menu order. One entry means every good of the section is in it: no menu is needed. */
	subcategories: SubcategoryEntry[];
}

/** The bar: the sections that have goods, in order, each with its subcategories and their sizes. */
export function categoriesOf(goods: readonly Tagged[]): Category[] {
	const counts = new Map<ListGroup, Map<Subcategory, number>>();
	const totals = new Map<ListGroup, number>();
	for (const good of goods) {
		const group = displayGroup(good.list_group);
		totals.set(group, (totals.get(group) ?? 0) + 1);
		const perGroup = counts.get(group) ?? new Map<Subcategory, number>();
		for (const sub of subcategoriesOf(good)) perGroup.set(sub, (perGroup.get(sub) ?? 0) + 1);
		counts.set(group, perGroup);
	}
	return LIST_GROUP_ORDER.flatMap((group) => {
		const perGroup = counts.get(group);
		if (!perGroup) return [];
		const subcategories = SUBCATEGORY_ORDER.flatMap((sub) => {
			const count = perGroup.get(sub);
			return count === undefined ? [] : [{ id: sub, count }];
		});
		return [{ group, count: totals.get(group) ?? 0, subcategories }];
	});
}

export interface Selection {
	group: ListGroup;
	/** null: the whole section. */
	sub: Subcategory | null;
}

/** The goods of a selection, in the input order. */
export function selectGoods<T extends Tagged>(goods: readonly T[], selection: Selection): T[] {
	return goods.filter(
		(good) =>
			displayGroup(good.list_group) === selection.group &&
			(selection.sub === null || subcategoriesOf(good).includes(selection.sub))
	);
}
