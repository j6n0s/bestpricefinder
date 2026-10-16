import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { load, resetForTests, update } from '../storage';
import { CartSession } from './session.svelte';

/** The cart kept in memory only (no localStorage here): what matters is how the class changes the stored cart. */
beforeEach(() => {
	resetForTests();
	update({ cart: { lines: [{ ingredientId: 'alma', qty: 0.5 }], checked: ['alma'], storeId: 'synthetic-lidl-1' } });
});

afterEach(() => {
	resetForTests();
});

describe('CartSession: clear and undo', () => {
	it('empties the cart, keeps the chosen store, and puts the lines back on undo', () => {
		const session = new CartSession();
		session.clearCart();
		expect(load().cart).toEqual({ lines: [], checked: [], storeId: 'synthetic-lidl-1' });
		expect(session.undoLines).toEqual([{ ingredientId: 'alma', qty: 0.5 }]);
		session.undoClear();
		expect(session.undoLines).toBeNull();
		expect(load().cart.lines).toEqual([{ ingredientId: 'alma', qty: 0.5 }]);
		session.undoClear(); // nothing to undo any more: no change
		expect(load().cart.lines).toEqual([{ ingredientId: 'alma', qty: 0.5 }]);
	});

	it('keeps what another tab stored since the clear, and does not duplicate a good', () => {
		const session = new CartSession();
		session.clearCart();
		// Another tab adds goods meanwhile (its write reaches the storage; this tab's undo offer still stands).
		update({ cart: { lines: [{ ingredientId: 'tej', qty: 1 }, { ingredientId: 'alma', qty: 2 }], checked: [], storeId: null } });
		session.undoClear();
		expect(load().cart.lines).toEqual([
			{ ingredientId: 'tej', qty: 1 },
			{ ingredientId: 'alma', qty: 2 }
		]);
	});

	it('restores at most the cart limit', () => {
		const many = Array.from({ length: 100 }, (_, i) => ({ ingredientId: `aru_${String(i).padStart(3, '0')}`, qty: 1 }));
		update({ cart: { lines: many, checked: [], storeId: null } });
		const session = new CartSession();
		session.clearCart();
		update({ cart: { lines: [{ ingredientId: 'tej', qty: 1 }], checked: [], storeId: null } });
		session.undoClear();
		const lines = load().cart.lines;
		expect(lines).toHaveLength(100);
		expect(lines[0]).toEqual({ ingredientId: 'tej', qty: 1 });
		expect(lines.at(-1)).toEqual({ ingredientId: 'aru_098', qty: 1 });
	});
});
