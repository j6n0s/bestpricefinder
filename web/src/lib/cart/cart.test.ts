import { describe, expect, it } from 'vitest';
import type { IngredientOut } from '../api/types';
import {
	MAX_CART_LINES,
	QTY_LADDERS,
	approxPieces,
	atMaximum,
	buyableGoods,
	buyableLines,
	cartListLines,
	cartQuoteInput,
	defaultQty,
	isBuyable,
	searchGoods,
	setLineQty,
	stepQty
} from './cart';

function ingredient(
	id: string,
	name: string,
	unit: IngredientOut['unit'],
	group: string,
	priced: IngredientOut['priced_by'] = 'gvh',
	pieceWeight: number | null = null
): IngredientOut {
	return {
		id,
		name_hu: name,
		list_group: group,
		unit,
		piece_weight_kg: pieceWeight,
		pantry: false,
		priced_by: priced,
		tags: []
	};
}

const ALMA = ingredient('alma', 'alma', 'kg', 'zoldseg_gyumolcs', 'gvh', 0.18);
const TEJ = ingredient('tej', 'tej (1,5% vagy 2,8%)', 'l', 'tejtermek_tojas');
const TOJAS = ingredient('tojas', 'tojás', 'db', 'tejtermek_tojas');
const ZSEMLE = ingredient('zsemle', 'zsemle', 'db', 'pekaru');
const OREGANO = ingredient('oregano', 'oregánó (szárított)', 'kg', 'fuszer_olaj', 'none');
const KSH = ingredient('kshonly', 'csak KSH-ár', 'kg', 'egyeb', 'ksh');
const VIZ = ingredient('viz', 'víz', 'l', 'egyeb', 'gvh');
const BANAN = ingredient('banan', 'banán', 'kg', 'zoldseg_gyumolcs', 'gvh', 0.17);

describe('buyable goods', () => {
	it('keeps only goods with GVH store prices, never tap water', () => {
		expect([ALMA, TEJ, OREGANO, KSH, VIZ].filter(isBuyable).map((g) => g.id)).toEqual(['alma', 'tej']);
	});

	it('orders them by shop section, then by Hungarian name', () => {
		const goods = buyableGoods([TEJ, TOJAS, ZSEMLE, BANAN, ALMA, OREGANO]);
		expect(goods.map((g) => g.id)).toEqual(['alma', 'banan', 'zsemle', 'tej', 'tojas']);
	});

	it('searches names without accents or case', () => {
		const goods = [ALMA, TEJ, TOJAS, BANAN];
		expect(searchGoods(goods, 'TOJAS').map((g) => g.id)).toEqual(['tojas']);
		expect(searchGoods(goods, ' bAnÁn ').map((g) => g.id)).toEqual(['banan']);
		expect(searchGoods(goods, '2,8%').map((g) => g.id)).toEqual(['tej']);
		expect(searchGoods(goods, '')).toHaveLength(4);
		expect(searchGoods(goods, 'nincs ilyen')).toEqual([]);
	});
});

describe('quantities', () => {
	it('starts at a sensible amount per unit (eggs by the box)', () => {
		expect(defaultQty(ALMA)).toBe(0.5);
		expect(defaultQty(TEJ)).toBe(1);
		expect(defaultQty(ZSEMLE)).toBe(1);
		expect(defaultQty(TOJAS)).toBe(10);
		for (const good of [ALMA, TEJ, ZSEMLE, TOJAS]) {
			expect(QTY_LADDERS[good.unit]).toContain(defaultQty(good));
		}
	});

	it('steps along the ladder; below the smallest step the line goes', () => {
		expect(stepQty(0.5, 'kg', 1)).toBe(0.75);
		expect(stepQty(0.5, 'kg', -1)).toBe(0.4);
		expect(stepQty(0.1, 'kg', -1)).toBeNull();
		expect(stepQty(1, 'db', -1)).toBeNull();
		expect(stepQty(10, 'kg', 1)).toBe(10); // the top stays the top
		expect(atMaximum(10, 'kg')).toBe(true);
		expect(atMaximum(7.5, 'kg')).toBe(false);
		// Between two steps (an amount from elsewhere): to the next step either way.
		expect(stepQty(0.6, 'kg', 1)).toBe(0.75);
		expect(stepQty(0.6, 'kg', -1)).toBe(0.5);
		expect(stepQty(0.05, 'kg', 1)).toBe(0.1);
		expect(stepQty(0.05, 'kg', -1)).toBeNull();
	});

	it('every ladder is strictly increasing and within the API bounds', () => {
		for (const ladder of Object.values(QTY_LADDERS)) {
			for (let i = 1; i < ladder.length; i++) expect(ladder[i]).toBeGreaterThan(ladder[i - 1]!);
			expect(ladder[0]).toBeGreaterThan(0);
			expect(ladder[ladder.length - 1]).toBeLessThanOrEqual(1000);
		}
	});

	it('says about how many pieces a weight is, for goods with a piece weight', () => {
		expect(approxPieces(0.5, ALMA)).toBe(3); // 0.5 / 0.18 = 2.8
		expect(approxPieces(0.1, ALMA)).toBe(1);
		expect(approxPieces(0.05, ALMA)).toBeNull(); // under half a piece
		expect(approxPieces(1, TEJ)).toBeNull();
		expect(approxPieces(1, { unit: 'kg', piece_weight_kg: null })).toBeNull();
	});
});

describe('cart lines', () => {
	it('adds at the end, changes in place, removes with null or a non-positive amount', () => {
		let lines = setLineQty([], 'alma', 0.5);
		lines = setLineQty(lines, 'tej', 1);
		lines = setLineQty(lines, 'alma', 0.75);
		expect(lines).toEqual([
			{ ingredientId: 'alma', qty: 0.75 },
			{ ingredientId: 'tej', qty: 1 }
		]);
		expect(setLineQty(lines, 'alma', null)).toEqual([{ ingredientId: 'tej', qty: 1 }]);
		expect(setLineQty(lines, 'tej', 0)).toEqual([{ ingredientId: 'alma', qty: 0.75 }]);
		expect(setLineQty(lines, 'tej', 5000)).toContainEqual({ ingredientId: 'tej', qty: 1000 });
		expect(setLineQty(lines, 'tej', 0.12345)).toContainEqual({ ingredientId: 'tej', qty: 0.123 });
	});

	it('never grows past MAX_CART_LINES, and never changes its input', () => {
		const full = Array.from({ length: MAX_CART_LINES }, (_, i) => ({ ingredientId: `g${i}`, qty: 1 }));
		const frozen = Object.freeze(full.slice());
		expect(setLineQty(frozen, 'one-more', 1)).toHaveLength(MAX_CART_LINES);
		expect(setLineQty(frozen, 'g0', 2)[0]).toEqual({ ingredientId: 'g0', qty: 2 });
	});

	it('becomes list lines and quote lines, skipping goods the catalogue no longer prices', () => {
		const byId = new Map([ALMA, TEJ, KSH].map((g) => [g.id, g]));
		const lines = cartListLines(
			[
				{ ingredientId: 'tej', qty: 2 },
				{ ingredientId: 'gone', qty: 1 },
				{ ingredientId: 'kshonly', qty: 1 },
				{ ingredientId: 'alma', qty: 0.5 }
			],
			byId
		);
		expect(lines).toEqual([
			{ ingredient_id: 'tej', name_hu: TEJ.name_hu, qty: 2, unit: 'l', list_group: 'tejtermek_tojas', pantry: false, recipe_ids: [] },
			{ ingredient_id: 'alma', name_hu: 'alma', qty: 0.5, unit: 'kg', list_group: 'zoldseg_gyumolcs', pantry: false, recipe_ids: [] }
		]);
		expect(cartQuoteInput(lines)).toEqual([
			{ ingredient_id: 'tej', qty: 2 },
			{ ingredient_id: 'alma', qty: 0.5 }
		]);
	});

	it('keeps only the lines whose good still has store prices, in order', () => {
		const byId = new Map([ALMA, TEJ, KSH].map((g) => [g.id, g]));
		const lines = [
			{ ingredientId: 'tej', qty: 2 },
			{ ingredientId: 'gone', qty: 1 },
			{ ingredientId: 'kshonly', qty: 1 },
			{ ingredientId: 'alma', qty: 0.5 }
		];
		expect(buyableLines(lines, byId)).toEqual([
			{ ingredientId: 'tej', qty: 2 },
			{ ingredientId: 'alma', qty: 0.5 }
		]);
		expect(buyableLines(lines, new Map())).toEqual([]);
	});
});
