import { describe, expect, it } from 'vitest';
import type { PlanDayIO, Slot } from '../api/types';
import { migrate, type StoredPlan } from '../storage';
import {
	DEFAULT_NO_REPEAT_DAYS,
	MAX_SERVINGS_PER_ITEM,
	SEED_MAX,
	buildCheckRequest,
	buildSuggestRequest,
	clearMeal,
	dayDate,
	emptyPlan,
	mealAt,
	mealCount,
	freshSeed,
	nextSeed,
	planFromResponse,
	planLengthDays,
	planToListItems,
	planWeeks,
	setMeal,
	slotsFor,
	unknownPlanRecipeIds,
	type PlanMeta
} from './plan';

const META: PlanMeta = {
	startDate: '2026-10-13',
	seed: 4,
	slots: 3,
	noRepeatDays: DEFAULT_NO_REPEAT_DAYS,
	createdAt: '2026-10-13T08:00:00.000Z'
};

function plan(days: PlanDayIO[], overrides: Partial<StoredPlan> = {}): StoredPlan {
	return { ...META, days, ...overrides };
}

function day(index: number, meals: PlanDayIO['meals']): PlanDayIO {
	return { index, meals };
}

const recipes = (...ids: string[]): { id: string }[] => ids.map((id) => ({ id }));

describe('plan length and slots', () => {
	it('has the 3- and 5-meal days in display order', () => {
		expect(slotsFor(3)).toEqual(['reggeli', 'ebed', 'vacsora']);
		expect(slotsFor(5)).toEqual(['reggeli', 'tizorai', 'ebed', 'uzsonna', 'vacsora']);
	});

	it('is 7 days for a week and up to the end of the month otherwise', () => {
		expect(planLengthDays('week', '2026-10-28')).toBe(7);
		expect(planLengthDays('month', '2026-10-13')).toBe(19);
		expect(planLengthDays('month', '2026-10-31')).toBe(1);
		expect(planLengthDays('month', '2026-12-01')).toBe(31);
		expect(planLengthDays('month', '2026-02-01')).toBe(28);
	});
});

describe('freshSeed (a new plan)', () => {
	it('is a whole number in the API range 0…2^31−1, also at the edges of random()', () => {
		expect(freshSeed(null, () => 0)).toBe(0);
		expect(freshSeed(null, () => 0.5)).toBe(2 ** 30);
		expect(freshSeed(null, () => 0.999999)).toBe(Math.floor(0.999999 * 2 ** 31));
		expect(freshSeed(null, () => 1)).toBe(SEED_MAX);
		expect(freshSeed(null, () => Number.NaN)).toBe(0);
		expect(freshSeed(null, () => -1)).toBe(0);
		for (let i = 0; i < 200; i += 1) {
			const seed = freshSeed();
			expect(Number.isInteger(seed) && seed >= 0 && seed <= SEED_MAX).toBe(true);
		}
	});

	it('differs between plans: not a constant, and never the seed of the plan it replaces', () => {
		expect(freshSeed(null, () => 0.1)).not.toBe(freshSeed(null, () => 0.2));
		expect(freshSeed(0, () => 0)).toBe(1);
		expect(freshSeed(SEED_MAX, () => 1)).toBe(0);
		expect(freshSeed(5, () => 0)).toBe(0);
	});
});

describe('nextSeed', () => {
	it('adds one and wraps inside 0…2^31−1', () => {
		expect(nextSeed(0)).toBe(1);
		expect(nextSeed(41)).toBe(42);
		expect(nextSeed(SEED_MAX - 1)).toBe(SEED_MAX);
		expect(nextSeed(SEED_MAX)).toBe(0);
		expect(nextSeed(-1)).toBe(0);
		expect(nextSeed(1.5)).toBe(0);
		expect(nextSeed(Number.NaN)).toBe(0);
	});
});

describe('buildSuggestRequest', () => {
	const input = {
		days: 19,
		slots: 5 as const,
		people: 3,
		seed: 7,
		excludeTags: ['hal' as const, 'hal' as const, 'sertes' as const],
		excludeIngredients: ['gomba', 'BAD ID', 'gomba', 'tej']
	};

	it('sends exactly the contract fields, with the API defaults made explicit', () => {
		expect(buildSuggestRequest(input)).toEqual({
			days: 19,
			slots: 5,
			people: 3,
			seed: 7,
			exclude_tags: ['hal', 'sertes'],
			exclude_ingredients: ['gomba', 'tej'],
			red_meat_g_per_person_week: 600,
			no_repeat_days: 5
		});
		expect(buildSuggestRequest({ ...input, noRepeatDays: 0 }).no_repeat_days).toBe(0);
	});

	it('caps the exclusion lists at the API limits', () => {
		const ingredients = Array.from({ length: 60 }, (_, i) => `ing_${i}`);
		const request = buildSuggestRequest({ ...input, excludeIngredients: ingredients });
		expect(request.exclude_ingredients).toHaveLength(50);
	});

	it('rejects values outside the contract', () => {
		for (const bad of [
			{ days: 0 },
			{ days: 32 },
			{ days: 2.5 },
			{ people: 0 },
			{ people: 13 },
			{ seed: -1 },
			{ seed: SEED_MAX + 1 },
			{ noRepeatDays: 15 },
			{ noRepeatDays: -1 }
		]) {
			expect(() => buildSuggestRequest({ ...input, ...bad }), JSON.stringify(bad)).toThrow(RangeError);
		}
	});
});

describe('planFromResponse', () => {
	it('sorts days, fills every planned slot and drops what is not a recipe id', () => {
		const stored = planFromResponse(
			{
				days: [
					day(1, { reggeli: 'b', ebed: null, vacsora: 'c-1' }),
					day(0, { ebed: 'a-1', tizorai: 'snack', vacsora: 'NOT VALID' }),
					day(1, { reggeli: 'duplicate' }),
					day(31, { ebed: 'too-late' })
				]
			},
			META
		);
		expect(stored).toEqual({
			...META,
			days: [
				{ index: 0, meals: { reggeli: null, ebed: 'a-1', vacsora: null } },
				{ index: 1, meals: { reggeli: null, ebed: null, vacsora: 'c-1' } }
			]
		});
	});

	it('keeps a valid start date only', () => {
		const stored = planFromResponse({ days: [day(0, { ebed: 'ab' })] }, { ...META, startDate: '2026-02-30' });
		expect(stored.startDate).toBeNull();
	});

	it('throws when no day is usable', () => {
		expect(() => planFromResponse({ days: [] }, META)).toThrow();
		expect(() => planFromResponse({ days: [day(-1, {})] }, META)).toThrow();
	});

	it('produces a plan the storage module keeps as it is', () => {
		const days = Array.from({ length: 31 }, (_, i) => day(i, { reggeli: 'r-1', tizorai: null, ebed: 'e-1', uzsonna: 'u-1', vacsora: 'v-1' }));
		const stored = planFromResponse({ days }, { ...META, slots: 5 });
		expect(migrate({ version: 1, plan: stored }).plan).toEqual(stored);
	});
});

describe('emptyPlan', () => {
	it('has every slot empty on every day', () => {
		const stored = emptyPlan(META, 7);
		expect(stored.days).toHaveLength(7);
		expect(stored.days.map((d) => d.index)).toEqual([0, 1, 2, 3, 4, 5, 6]);
		for (const d of stored.days) expect(d.meals).toEqual({ reggeli: null, ebed: null, vacsora: null });
		expect(migrate({ version: 1, plan: stored }).plan).toEqual(stored);
		expect(() => emptyPlan(META, 0)).toThrow(RangeError);
		expect(() => emptyPlan(META, 32)).toThrow(RangeError);
	});
});

describe('editing meals', () => {
	const base = plan([day(0, { reggeli: null, ebed: 'a-1', vacsora: null }), day(1, { reggeli: 'b-1', ebed: null, vacsora: null })]);

	it('sets one slot without touching anything else', () => {
		const next = setMeal(base, 1, 'vacsora', 'c-1');
		expect(next).not.toBe(base);
		expect(mealAt(next, 1, 'vacsora')).toBe('c-1');
		expect(next.days[0]).toBe(base.days[0]);
		expect(base.days[1]?.meals.vacsora).toBeNull();
		expect({ ...next, days: undefined }).toEqual({ ...base, days: undefined });
	});

	it('clears a slot', () => {
		const next = clearMeal(base, 0, 'ebed');
		expect(mealAt(next, 0, 'ebed')).toBeNull();
		expect(mealCount(next)).toBe(1);
	});

	it('returns the same plan when nothing changes or the target is invalid', () => {
		expect(setMeal(base, 0, 'ebed', 'a-1')).toBe(base);
		expect(clearMeal(base, 0, 'vacsora')).toBe(base);
		expect(setMeal(base, 9, 'ebed', 'x-1')).toBe(base);
		expect(setMeal(base, 0, 'tizorai', 'x-1')).toBe(base);
		expect(setMeal(base, 0, 'ebed', 'Not An Id')).toBe(base);
		expect(setMeal(base, 0, 'ebed', '')).toBe(base);
	});

	it('reads a slot: id, null, or undefined outside the plan', () => {
		expect(mealAt(base, 0, 'ebed')).toBe('a-1');
		expect(mealAt(base, 0, 'reggeli')).toBeNull();
		expect(mealAt(base, 5, 'ebed')).toBeUndefined();
		expect(mealAt(base, 0, 'uzsonna')).toBeUndefined();
	});
});

describe('planWeeks', () => {
	it('groups days into the 7-day blocks of the checks, with dates and Monday-based weekdays', () => {
		const days = Array.from({ length: 19 }, (_, i) => day(18 - i, { ebed: null }));
		const weeks = planWeeks(plan(days));
		expect(weeks.map((w) => w.week)).toEqual([0, 1, 2]);
		expect(weeks.map((w) => w.days.length)).toEqual([7, 7, 5]);
		const first = weeks[0]?.days[0];
		expect(first).toEqual({
			index: 0,
			date: '2026-10-13',
			weekday: 1,
			meals: [
				{ slot: 'reggeli', recipeId: null },
				{ slot: 'ebed', recipeId: null },
				{ slot: 'vacsora', recipeId: null }
			]
		});
		expect(weeks[2]?.days.at(-1)).toMatchObject({ index: 18, date: '2026-10-31', weekday: 5 });
	});

	it('has no dates for an undated plan', () => {
		const weeks = planWeeks(plan([day(0, { ebed: 'a-1' })], { startDate: null }));
		expect(weeks[0]?.days[0]).toMatchObject({ date: null, weekday: null });
		expect(dayDate({ startDate: null }, 3)).toBeNull();
		expect(dayDate({ startDate: '2026-10-30' }, 3)).toBe('2026-11-02');
	});

	it('shows only the plan’s own slots', () => {
		const weeks = planWeeks(plan([day(0, { ebed: 'a-1', tizorai: 'x-1' } as Record<Slot, string>)]));
		expect(weeks[0]?.days[0]?.meals.map((m) => m.slot)).toEqual(['reggeli', 'ebed', 'vacsora']);
	});
});

describe('buildCheckRequest', () => {
	const stored = plan(
		[day(1, { reggeli: 'gone', ebed: 'b-1', vacsora: null }), day(0, { reggeli: 'a-1', ebed: 'a-1', vacsora: 'b-1' })],
		{ noRepeatDays: 3 }
	);

	it('sends the days in order with the plan’s variety window', () => {
		expect(buildCheckRequest(stored, 4)).toEqual({
			days: [
				{ index: 0, meals: { reggeli: 'a-1', ebed: 'a-1', vacsora: 'b-1' } },
				{ index: 1, meals: { reggeli: 'gone', ebed: 'b-1', vacsora: null } }
			],
			people: 4,
			red_meat_g_per_person_week: 600,
			no_repeat_days: 3
		});
	});

	it('sends recipes that no longer exist as empty slots', () => {
		const request = buildCheckRequest(stored, 2, new Set(['a-1', 'b-1']));
		expect(request.days[1]?.meals).toEqual({ reggeli: null, ebed: 'b-1', vacsora: null });
	});

	it('rejects an invalid household size', () => {
		expect(() => buildCheckRequest(stored, 0)).toThrow(RangeError);
	});
});

describe('planToListItems', () => {
	it('is empty without a plan or without meals', () => {
		expect(planToListItems(null, recipes('a-1'), 2)).toEqual([]);
		expect(planToListItems(emptyPlan(META, 7), recipes('a-1'), 2)).toEqual([]);
	});

	it('gives `people` servings per meal, summed per recipe, in plan order', () => {
		const stored = plan([
			day(1, { reggeli: 'c-1', ebed: 'a-1', vacsora: null }),
			day(0, { reggeli: 'b-1', ebed: 'a-1', vacsora: 'a-1' })
		]);
		expect(planToListItems(stored, recipes('a-1', 'b-1', 'c-1'), 2)).toEqual([
			{ recipe_id: 'b-1', servings: 2 },
			{ recipe_id: 'a-1', servings: 6 },
			{ recipe_id: 'c-1', servings: 2 }
		]);
		expect(planToListItems(stored, recipes('a-1', 'b-1', 'c-1'), 1)).toEqual([
			{ recipe_id: 'b-1', servings: 1 },
			{ recipe_id: 'a-1', servings: 3 },
			{ recipe_id: 'c-1', servings: 1 }
		]);
	});

	it('counts a two-day recipe on both days (each day is eaten by everyone)', () => {
		const stored = plan([day(0, { ebed: 'ketnapos' }), day(1, { ebed: 'ketnapos' })]);
		expect(planToListItems(stored, recipes('ketnapos'), 3)).toEqual([{ recipe_id: 'ketnapos', servings: 6 }]);
	});

	it('leaves out recipes the API does not know and slots outside the plan', () => {
		const stored = plan([day(0, { reggeli: 'gone', ebed: 'a-1', tizorai: 'a-1' } as Record<Slot, string>)]);
		expect(planToListItems(stored, recipes('a-1'), 2)).toEqual([{ recipe_id: 'a-1', servings: 2 }]);
		expect(unknownPlanRecipeIds(stored, recipes('a-1'))).toEqual(['gone']);
		expect(planToListItems(stored, [], 2)).toEqual([]);
	});

	it('splits more than 100 servings into several items of the same recipe', () => {
		const days = Array.from({ length: 31 }, (_, i) => day(i, { ebed: 'a-1' }));
		const items = planToListItems(plan(days), recipes('a-1'), 12);
		expect(items).toEqual([
			{ recipe_id: 'a-1', servings: 100 },
			{ recipe_id: 'a-1', servings: 100 },
			{ recipe_id: 'a-1', servings: 100 },
			{ recipe_id: 'a-1', servings: 72 }
		]);
		expect(items.every((item) => item.servings > 0 && item.servings <= MAX_SERVINGS_PER_ITEM)).toBe(true);
	});

	it('stays within the API limit of 200 items for the largest possible plan', () => {
		const ids = Array.from({ length: 155 }, (_, i) => `r-${i}`);
		const slots = slotsFor(5);
		const days = Array.from({ length: 31 }, (_, d) =>
			day(d, Object.fromEntries(slots.map((slot, s) => [slot, ids[d * 5 + s] ?? null])))
		);
		const distinct = planToListItems(plan(days, { slots: 5 }), recipes(...ids), 12);
		expect(distinct).toHaveLength(155);
		const same = Array.from({ length: 31 }, (_, d) => day(d, Object.fromEntries(slots.map((slot) => [slot, 'a-1']))));
		const one = planToListItems(plan(same, { slots: 5 }), recipes('a-1'), 12);
		expect(one.reduce((sum, item) => sum + item.servings, 0)).toBe(31 * 5 * 12);
		expect(one.length).toBeLessThanOrEqual(200);
	});

	it('rejects an invalid household size', () => {
		expect(() => planToListItems(null, [], 0)).toThrow(RangeError);
		expect(() => planToListItems(null, [], 13)).toThrow(RangeError);
		expect(() => planToListItems(null, [], 1.5)).toThrow(RangeError);
	});
});
