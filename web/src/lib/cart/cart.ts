/**
 * The shopping cart ("Kosár"): goods the user picks by hand, priced at the nearby stores like the list made
 * from a plan. Pure helpers; the cart itself lives on this device only (StoredState.cart).
 *
 * - Only goods with GVH store prices can be put in the cart (`priced_by: "gvh"`). KSH-only goods have a
 *   national average, never a store price, and tap water is never bought.
 * - Quantities are in the ingredient's own unit (kg, l, db) and move along a ladder of round amounts, so the
 *   − / + buttons give "250 g, 300 g, 400 g, 500 g, 750 g, 1 kg…" rather than odd numbers.
 */
import type { IngredientOut, ListLineOut, QtyLineIn, Unit } from '../api/types';
import { groupLines } from '../list/groups';
import { canBeBought } from '../list/lines';
import { foldText } from '../plan/recipes';
import type { StoredCartLine } from '../storage';

export type CartLine = StoredCartLine;

/** At most this many goods in the cart (POST /api/quote takes 200 lines; storage keeps the same bound). */
export const MAX_CART_LINES = 100;
/** The API accepts 0 < qty <= 1000 (storage keeps the same bound). */
export const MAX_CART_QTY = 1000;

export const QTY_LADDERS: Readonly<Record<Unit, readonly number[]>> = {
	kg: [0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10],
	l: [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12],
	db: [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20, 24, 30, 40, 50]
};

const DEFAULT_QTY: Readonly<Record<Unit, number>> = { kg: 0.5, l: 1, db: 1 };
/** Goods almost always bought by the box. */
const DEFAULT_OVERRIDES: Readonly<Record<string, number>> = { tojas: 10 };

export function isBuyable(ingredient: Pick<IngredientOut, 'id' | 'priced_by'>): boolean {
	return ingredient.priced_by === 'gvh' && canBeBought(ingredient.id);
}

/** The first amount put in the cart. */
export function defaultQty(ingredient: Pick<IngredientOut, 'id' | 'unit'>): number {
	return DEFAULT_OVERRIDES[ingredient.id] ?? DEFAULT_QTY[ingredient.unit];
}

/**
 * The next amount on the unit's ladder above (+1) or below (−1) `qty`. Below the smallest step: null (the
 * line is removed). Above the largest: the largest. An amount between two steps moves to the next one.
 */
export function stepQty(qty: number, unit: Unit, direction: 1 | -1): number | null {
	const ladder = QTY_LADDERS[unit];
	const eps = 1e-9;
	if (direction === 1) {
		return ladder.find((step) => step > qty + eps) ?? ladder.at(-1) ?? qty;
	}
	const lower = [...ladder].reverse().find((step) => step < qty - eps);
	return lower ?? null;
}

/** True when + would not change the amount. */
export function atMaximum(qty: number, unit: Unit): boolean {
	const top = QTY_LADDERS[unit].at(-1) ?? Infinity;
	return qty >= top - 1e-9;
}

/** About how many pieces `qty` kg is, for goods with a typical piece weight ("kb. 3 db"); null otherwise. */
export function approxPieces(qty: number, ingredient: Pick<IngredientOut, 'unit' | 'piece_weight_kg'>): number | null {
	const weight = ingredient.piece_weight_kg;
	if (ingredient.unit !== 'kg' || weight === null || !(weight > 0)) return null;
	const pieces = Math.round(qty / weight);
	return pieces >= 1 ? pieces : null;
}

/** The goods that can be put in the cart, by shop section (the shopping-list order), then by name. */
export function buyableGoods(ingredients: readonly IngredientOut[]): IngredientOut[] {
	const goods = ingredients
		.filter(isBuyable)
		.slice()
		.sort((a, b) => a.name_hu.localeCompare(b.name_hu, 'hu'));
	return groupLines(goods).flatMap((group) => group.lines);
}

/** Goods whose name contains the query (accents and case ignored); an empty query keeps them all. */
export function searchGoods<T extends Pick<IngredientOut, 'name_hu'>>(goods: readonly T[], query: string): T[] {
	const folded = foldText(query);
	if (folded === '') return goods.slice();
	return goods.filter((good) => foldText(good.name_hu).includes(folded));
}

/** `lines` with `ingredientId` at `qty` (added at the end when new; removed when qty is null). */
export function setLineQty(lines: readonly CartLine[], ingredientId: string, qty: number | null): CartLine[] {
	const index = lines.findIndex((line) => line.ingredientId === ingredientId);
	if (qty === null) return lines.filter((line) => line.ingredientId !== ingredientId);
	const clean = Math.min(MAX_CART_QTY, Math.round(qty * 1000) / 1000);
	if (!(clean > 0)) return lines.filter((line) => line.ingredientId !== ingredientId);
	if (index >= 0) return lines.map((line, i) => (i === index ? { ingredientId, qty: clean } : line));
	if (lines.length >= MAX_CART_LINES) return lines.slice();
	return [...lines, { ingredientId, qty: clean }];
}

/**
 * The cart as shopping-list lines (names and sections for the store views), skipping goods the catalogue no
 * longer has or no longer prices.
 */
export function cartListLines(lines: readonly CartLine[], byId: ReadonlyMap<string, IngredientOut>): ListLineOut[] {
	const out: ListLineOut[] = [];
	for (const line of lines) {
		const ingredient = byId.get(line.ingredientId);
		if (!ingredient || !isBuyable(ingredient)) continue;
		out.push({
			ingredient_id: ingredient.id,
			name_hu: ingredient.name_hu,
			qty: line.qty,
			unit: ingredient.unit,
			list_group: ingredient.list_group,
			pantry: false,
			recipe_ids: []
		});
	}
	return out;
}

/**
 * The cart lines whose good still has store prices. The others (the catalogue changed since they were added)
 * are not shown; they leave the cart at its next change, so they never block the MAX_CART_LINES limit.
 */
export function buyableLines(lines: readonly CartLine[], byId: ReadonlyMap<string, IngredientOut>): CartLine[] {
	return lines.filter((line) => {
		const ingredient = byId.get(line.ingredientId);
		return ingredient !== undefined && isBuyable(ingredient);
	});
}

/** The lines for POST /api/quote. */
export function cartQuoteInput(lines: readonly ListLineOut[]): QtyLineIn[] {
	return lines.map((line) => ({ ingredient_id: line.ingredient_id, qty: line.qty }));
}
