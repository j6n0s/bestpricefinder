/**
 * What the goods page ("Termékek", where goods are found and put in the cart) and the cart page ("Kosár",
 * the list of the chosen goods) share: the catalogue (GET /api/ingredients), the stored state
 * (StoredState.cart, location, radius) and every change of the cart. Svelte 5 class state; each page makes
 * its own instance and calls `start()` from onMount.
 *
 * - The goods are the ingredients with `priced_by: "gvh"` (store prices exist); tap water never.
 * - Every change starts from a fresh load(): another tab may have changed the cart meanwhile, and a stale
 *   copy must never write old data back. Another tab's writes arrive through onExternalChange.
 * - Goods that lost their store price are written out of the cart as soon as the catalogue arrives (with a
 *   notice that stays until the next change), so the header's count and the pages' agree.
 */
import { ApiError } from '../api/client';
import type { IngredientOut, StoreId } from '../api/types';
import { loadIngredients } from '../list/data';
import { toggleId } from '../list/lines';
import {
	isPersistent,
	load,
	onExternalChange,
	update,
	type StatePatch,
	type StoredCart,
	type StoredLocation,
	type StoredState
} from '../storage';
import { MAX_CART_LINES, buyableGoods, buyableLines, cartListLines, cartQuoteInput, defaultQty, setLineQty, type CartLine } from './cart';

export type CatalogueState =
	| { status: 'idle' | 'loading' }
	| { status: 'ready'; ingredients: IngredientOut[] }
	| { status: 'error'; error: unknown };

export class CartSession {
	stored = $state<StoredState>(load());
	persistent = $state(isPersistent());
	catalogue = $state<CatalogueState>({ status: 'idle' });
	/** Goods written out of the cart for lack of a store price, shown until the next change. */
	dropped = $state(0);
	/** The cart is full: the last "Kosárba" did nothing. */
	fullNotice = $state(false);
	/** The lines of the cart just emptied, while "Visszavonás" is offered. */
	undoLines = $state<CartLine[] | null>(null);

	ingredients = $derived(this.catalogue.status === 'ready' ? this.catalogue.ingredients : []);
	byId = $derived(new Map(this.ingredients.map((ingredient) => [ingredient.id, ingredient])));
	/** The goods that can be put in the cart, by shop section, then by name. */
	goods = $derived(buyableGoods(this.ingredients));
	cart = $derived(this.stored.cart);
	qtyById = $derived(new Map(this.cart.lines.map((line) => [line.ingredientId, line.qty])));
	/** The cart as list lines (names, units), once the catalogue is known. */
	listLines = $derived(this.catalogue.status === 'ready' ? cartListLines(this.cart.lines, this.byId) : []);
	quoteInput = $derived(cartQuoteInput(this.listLines));
	checked = $derived(new Set(this.cart.checked));

	/** Loads the catalogue and follows the other tabs' writes. Returns the function to call on destroy. */
	start(): () => void {
		this.fetchCatalogue();
		return onExternalChange((next) => {
			this.stored = next;
			this.persistent = isPersistent();
		});
	}

	fetchCatalogue(): void {
		this.catalogue = { status: 'loading' };
		loadIngredients()
			.then((data) => {
				if (!Array.isArray(data?.ingredients)) {
					this.catalogue = { status: 'error', error: new ApiError({ kind: 'invalid_response' }) };
					return;
				}
				this.catalogue = { status: 'ready', ingredients: data.ingredients };
				this.pruneUnpriced();
			})
			.catch((error: unknown) => {
				this.catalogue = { status: 'error', error };
			});
	}

	private pruneUnpriced(): void {
		const current = load().cart;
		const kept = buyableLines(current.lines, this.byId);
		if (kept.length === current.lines.length) return;
		this.dropped = current.lines.length - kept.length;
		this.patch({ cart: { ...current, lines: kept } });
	}

	patch(next: StatePatch): void {
		this.stored = update(next);
		this.persistent = isPersistent();
	}

	/** Changes the cart, starting from a fresh load(). */
	changeCart(change: (current: StoredCart) => StoredCart): void {
		this.patch({ cart: change(load().cart) });
	}

	/** Sets a good's amount (null removes it); goods without store prices any more leave with this change. */
	setQty(ingredientId: string, qty: number | null): void {
		this.undoLines = null;
		this.dropped = 0;
		this.changeCart((current) => {
			const lines = setLineQty(buyableLines(current.lines, this.byId), ingredientId, qty);
			const checked = qty === null ? toggleId(current.checked, ingredientId, false) : current.checked;
			return { ...current, lines, checked };
		});
	}

	/** Puts a good in the cart at its first amount. False, with the notice, when the cart is full. */
	add(good: IngredientOut): boolean {
		const lines = buyableLines(load().cart.lines, this.byId);
		if (lines.length >= MAX_CART_LINES && !lines.some((line) => line.ingredientId === good.id)) {
			this.fullNotice = true;
			return false;
		}
		this.fullNotice = false;
		this.setQty(good.id, defaultQty(good));
		return true;
	}

	/** Empties the cart; the lines are kept for "Visszavonás" until the next change. */
	clearCart(): void {
		const current = load().cart;
		this.undoLines = current.lines;
		this.patch({ cart: { lines: [], checked: [], storeId: current.storeId } });
	}

	undoClear(): void {
		const lines = this.undoLines;
		this.undoLines = null;
		if (lines) this.changeCart((current) => ({ ...current, lines }));
	}

	toggleCheck(ingredientId: string, on: boolean): void {
		this.changeCart((current) => ({ ...current, checked: toggleId(current.checked, ingredientId, on) }));
	}

	chooseStore(storeId: StoreId): void {
		this.changeCart((current) => ({ ...current, storeId }));
	}

	setLocation(next: StoredLocation): void {
		this.patch({ location: next });
	}

	setRadius(radiusKm: number): void {
		this.patch({ radiusKm });
	}
}
