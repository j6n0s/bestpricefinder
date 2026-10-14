/**
 * The cart ("Kosár"): goods picked by hand, without a plan, priced at the nearby stores. The cart is personal
 * data and stays on this device (StoredState.cart).
 */
export const cartHu = {
	title: 'Kosár',
	loading: 'Termékek betöltése…',
	error_title: 'A termékek betöltése nem sikerült',

	cart_title: 'A kosarad',
	cart_count_one: '{count} tétel',
	cart_count_other: '{count} tétel',
	cart_empty: 'A kosarad még üres.',
	to_prices: 'Hol a legolcsóbb?',
	clear: 'Kosár ürítése',
	cleared: 'Kiürítetted a kosarat.',
	undo: 'Visszavonás',
	dropped_one: '{count} termék kimaradt, mert már nincs bolti ára.',
	dropped_other: '{count} termék kimaradt, mert már nincs bolti ára.',
	full: 'A kosárba legfeljebb {max} termék fér.',

	browse_title: 'Termékek',
	browse_more: 'További termékek',
	search_label: 'Keresés a termékek között',
	goods_count_one: '{count} termék',
	goods_count_other: '{count} termék',
	no_results: 'Nincs ilyen termék.',
	clear_search: 'Keresés törlése',

	add: 'Kosárba',
	add_named: 'Kosárba: {name}',
	less_named: 'Kevesebb: {name}',
	more_named: 'Több: {name}',
	remove_named: 'Törlés a kosárból: {name}',
	qty_named: '{name}: {qty}',
	pieces: 'kb. {count} db'
} as const;
