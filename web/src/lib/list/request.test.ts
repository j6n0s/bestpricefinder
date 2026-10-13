// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { StoredPlan } from '../storage';
import { buildListRequest, listKey } from './request';

const PLAN: StoredPlan = {
	createdAt: '2026-10-13T08:00:00.000Z',
	startDate: '2026-10-13',
	seed: 7,
	slots: 3,
	noRepeatDays: 5,
	days: [
		...Array.from({ length: 7 }, (_, index) => ({
			index,
			meals: { reggeli: 'minta-pirits', ebed: index % 2 === 0 ? 'minta-lencse' : 'minta-csirke', vacsora: null }
		})),
		{ index: 7, meals: { reggeli: 'minta-torolt', ebed: 'minta-hal', vacsora: 'minta-hal' } },
		{ index: 8, meals: { reggeli: null, ebed: null, vacsora: null } }
	]
};

const RECIPES = [{ id: 'minta-pirits' }, { id: 'minta-lencse' }, { id: 'minta-csirke' }, { id: 'minta-hal' }];

describe('buildListRequest', () => {
	it('this week: people servings per planned meal, summed per recipe, in plan order', () => {
		const result = buildListRequest(PLAN, 'this_week', '2026-10-13', RECIPES, 2, []);
		expect(result.days).toBe(7);
		expect(result.unknownRecipeIds).toEqual([]);
		expect(result.request).toEqual({
			items: [
				{ recipe_id: 'minta-pirits', servings: 14 },
				{ recipe_id: 'minta-lencse', servings: 8 },
				{ recipe_id: 'minta-csirke', servings: 6 }
			]
		});
	});

	it('next week: leaves out recipes the library no longer has and reports them', () => {
		const result = buildListRequest(PLAN, 'next_week', '2026-10-13', RECIPES, 3, []);
		expect(result.request).toEqual({ items: [{ recipe_id: 'minta-hal', servings: 6 }] });
		expect(result.unknownRecipeIds).toEqual(['minta-torolt']);
		expect(result.days).toBe(2);
	});

	it('whole plan: every day', () => {
		const result = buildListRequest(PLAN, 'whole', '2026-10-13', RECIPES, 1, []);
		expect(result.request?.items).toEqual([
			{ recipe_id: 'minta-pirits', servings: 7 },
			{ recipe_id: 'minta-lencse', servings: 4 },
			{ recipe_id: 'minta-csirke', servings: 3 },
			{ recipe_id: 'minta-hal', servings: 2 }
		]);
	});

	it('adds the on-hand quantities (only those with a quantity)', () => {
		const result = buildListRequest(PLAN, 'this_week', '2026-10-13', RECIPES, 2, [
			{ ingredientId: 'liszt', qty: 0.5 },
			{ ingredientId: 'so', qty: null }
		]);
		expect(result.request?.on_hand).toEqual([{ ingredient_id: 'liszt', qty: 0.5 }]);
	});

	it('has no request when the range has no known meal', () => {
		const result = buildListRequest(PLAN, 'next_week', '2026-10-13', [{ id: 'minta-pirits' }], 2, []);
		expect(result.request).toBeNull();
		expect(result.unknownRecipeIds).toEqual(['minta-torolt', 'minta-hal']);
		expect(buildListRequest(PLAN, 'this_week', '2026-12-01', RECIPES, 2, []).request).toBeNull();
	});

	it('never sends anything but recipe ids, servings and on-hand quantities', () => {
		const result = buildListRequest(PLAN, 'whole', '2026-10-13', RECIPES, 2, [{ ingredientId: 'liszt', qty: 1 }]);
		expect(Object.keys(result.request ?? {}).sort()).toEqual(['items', 'on_hand']);
		for (const item of result.request?.items ?? []) expect(Object.keys(item).sort()).toEqual(['recipe_id', 'servings']);
	});
});

describe('listKey', () => {
	it('identifies a list by its plan and range', () => {
		expect(listKey(PLAN, 'this_week')).toBe('2026-10-13T08:00:00.000Z|this_week');
		expect(listKey(PLAN, 'whole')).not.toBe(listKey(PLAN, 'this_week'));
	});
});
