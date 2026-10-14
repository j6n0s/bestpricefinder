import type { cartHu } from './cart.hu';
import type { Messages } from './types';

export const cartEn: Messages<typeof cartHu> = {
	title: 'Cart',
	intro:
		'Pick what you want to buy and we show where it is cheapest nearby: in one store, or on a short route. Your cart stays on this device only.',
	loading: 'Loading the goods…',
	error_title: 'The goods could not be loaded',

	cart_title: 'Your cart',
	cart_count_one: '{count} item',
	cart_count_other: '{count} items',
	cart_empty: 'Your cart is empty: pick from the goods.',
	to_prices: 'Where is it cheapest?',
	clear: 'Empty the cart',
	cleared: 'You emptied the cart.',
	undo: 'Undo',
	dropped_one: '{count} item was left out: it has no store price any more.',
	dropped_other: '{count} items were left out: they have no store price any more.',
	full: 'The cart holds at most {max} items.',

	browse_title: 'Goods',
	browse_more: 'More goods',
	search_label: 'Search the goods',
	search_hint: 'Accents are optional. Only goods with store prices are shown.',
	goods_count_one: '{count} item',
	goods_count_other: '{count} items',
	no_results: 'No such item.',
	clear_search: 'Clear the search',

	add: 'Add',
	add_named: 'Add to cart: {name}',
	less_named: 'Less: {name}',
	more_named: 'More: {name}',
	remove_named: 'Remove from cart: {name}',
	qty_named: '{name}: {qty}',
	pieces: 'about {count} pcs'
};
