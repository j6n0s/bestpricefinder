import { describe, expect, it } from 'vitest';
import type { ListLineOut } from '../api/types';
import { applyOnHand, onHandMap, setOnHandQty } from './onhand';

function line(id: string, qty: number, unit: ListLineOut['unit'] = 'kg', pantry = false): ListLineOut {
	return { ingredient_id: id, name_hu: id, qty, unit, list_group: 'egyeb', pantry, recipe_ids: ['r'] };
}

describe('onHandMap', () => {
	it('keeps the first positive amount per ingredient', () => {
		const map = onHandMap([
			{ ingredientId: 'liszt', qty: 1 },
			{ ingredientId: 'liszt', qty: 2 },
			{ ingredientId: 'tojas', qty: 0 },
			{ ingredientId: 'rizs', qty: Number.NaN }
		]);
		expect([...map]).toEqual([['liszt', 1]]);
	});
});

describe('applyOnHand', () => {
	it('subtracts what is at home, covers whole lines, and leaves the rest untouched', () => {
		const lines = [line('liszt', 1), line('tojas', 6, 'db'), line('rizs', 0.5), line('viz', 1, 'l', true)];
		const result = applyOnHand(lines, new Map([['liszt', 0.4], ['tojas', 10], ['viz', 5]]));
		expect(result.lines).toEqual([line('liszt', 0.6), line('rizs', 0.5), line('viz', 1, 'l', true)]);
		expect(result.lines[1]).toBe(lines[2]); // untouched lines keep their identity
		expect(result.lines[2]).toBe(lines[3]); // tap water is never bought: left alone
		expect(result.covered).toEqual([{ line: lines[1], onHand: 10 }]);
		expect([...result.reduced]).toEqual([['liszt', 0.4]]);
	});

	it('rounds to 3 decimals and treats a tiny remainder as covered', () => {
		const result = applyOnHand(
			[line('a', 0.3), line('b', 1), line('c', 1)],
			new Map([
				['a', 0.1 + 0.2], // 0.30000000000000004 at home: covered, not "-0.000 remaining"
				['b', 0.9994], // 0.0006 remaining rounds to 0.001
				['c', 0.9996] // 0.0004 remaining rounds to nothing
			])
		);
		expect(result.covered.map((c) => c.line.ingredient_id)).toEqual(['a', 'c']);
		expect(result.lines).toEqual([line('b', 0.001)]);
	});

	it('ignores amounts that are not positive and lines without a finite quantity', () => {
		const odd = line('c', Number.NaN);
		const result = applyOnHand([line('a', 1), odd], new Map([['a', 0], ['c', 1]]));
		expect(result.lines).toEqual([line('a', 1), odd]);
		expect(result.covered).toEqual([]);
		expect(result.reduced.size).toBe(0);
	});
});

describe('setOnHandQty', () => {
	const lines = [
		{ ingredientId: 'liszt', qty: 1 },
		{ ingredientId: 'tojas', qty: 6 }
	];

	it('adds, changes, caps and removes without touching the input', () => {
		expect(setOnHandQty(lines, 'rizs', 0.5, 200, 1000)).toEqual([...lines, { ingredientId: 'rizs', qty: 0.5 }]);
		expect(setOnHandQty(lines, 'liszt', 2.00049, 200, 1000)).toEqual([{ ingredientId: 'liszt', qty: 2 }, lines[1]]);
		expect(setOnHandQty(lines, 'liszt', 5000, 200, 1000)).toEqual([{ ingredientId: 'liszt', qty: 1000 }, lines[1]]);
		expect(setOnHandQty(lines, 'tojas', null, 200, 1000)).toEqual([lines[0]]);
		expect(setOnHandQty(lines, 'tojas', 0, 200, 1000)).toEqual([lines[0]]);
		expect(lines).toHaveLength(2);
	});

	it('does not add beyond the line limit but still changes an existing line', () => {
		expect(setOnHandQty(lines, 'rizs', 1, 2, 1000)).toEqual(lines);
		expect(setOnHandQty(lines, 'liszt', 3, 2, 1000)).toEqual([{ ingredientId: 'liszt', qty: 3 }, lines[1]]);
	});
});
