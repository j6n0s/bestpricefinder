/**
 * Pure helpers for the weekly plan ("Heti terv"): building requests for POST /api/plan/suggest and
 * /api/plan/check, turning a suggestion into the stored plan, editing meals, grouping days into weeks and
 * turning the plan into shopping-list items for POST /api/list.
 *
 * The plan itself is personal data and lives only in localStorage (`StoredState.plan`, $lib/storage). Plans
 * are immutable here: every edit returns a new object (or the same object when nothing changes).
 */
import {
	ID_PATTERNS,
	LIMITS,
	SLOTS_3,
	SLOTS_5,
	type ListItemIn,
	type PlanCheckRequest,
	type PlanDayIO,
	type PlanResponse,
	type PlanSuggestRequest,
	type RecipeId,
	type RecipeTag,
	type Slot
} from '../api/types';
import type { StoredPlan } from '../storage';
import { addDays, daysToMonthEnd, isCalendarDate, weekdayIndex } from './dates';

/** "Egy hét": 7 days from the start date. */
export const PLAN_WEEK_DAYS = 7;
export const PLAN_MAX_DAYS: number = LIMITS.planDaysMax;
/** The API defaults (server/bpf/api/schemas.py); sent explicitly so suggest and check always agree. */
export const DEFAULT_NO_REPEAT_DAYS = 5;
export const DEFAULT_RED_MEAT_G = 600;
export const SEED_MAX = 2 ** 31 - 1;
/** ListItemIn.servings must be ≤ 100, so larger totals are split into several items of the same recipe. */
export const MAX_SERVINGS_PER_ITEM: number = LIMITS.servingsMax;

export type PlanLength = 'week' | 'month';
export type SlotCount = 3 | 5;

/** The slots of a 3- or 5-meal day, in display order. */
export function slotsFor(count: SlotCount): readonly Slot[] {
	return count === 5 ? SLOTS_5 : SLOTS_3;
}

/** Number of plan days: 7 for "egy hét", or up to the end of the start date's month (at most 31). */
export function planLengthDays(length: PlanLength, startDate: string): number {
	if (length === 'week') return PLAN_WEEK_DAYS;
	return Math.min(PLAN_MAX_DAYS, daysToMonthEnd(startDate));
}

/**
 * The seed of a NEW plan ("Terv készítése"): a random integer in the API's 0…2^31−1 range. The planner is
 * deterministic for the same input, and the request carries no date, so a constant seed would give the same
 * week every week. A different seed than the current plan's (`avoid`) is guaranteed, so a new plan is never
 * silently the same as the one it replaces. `random` is injectable for tests.
 */
export function freshSeed(avoid: number | null = null, random: () => number = Math.random): number {
	const value = random();
	const unit = Number.isFinite(value) ? Math.min(Math.max(value, 0), 1 - Number.EPSILON) : 0;
	const seed = Math.floor(unit * (SEED_MAX + 1));
	return seed === avoid ? nextSeed(seed) : seed;
}

/** The seed of "Új javaslat": one more, wrapping inside the API's 0…2^31−1 range. */
export function nextSeed(seed: number): number {
	if (!Number.isInteger(seed) || seed < 0 || seed >= SEED_MAX) return 0;
	return seed + 1;
}

function assertInt(value: number, min: number, max: number, name: string): void {
	if (!Number.isInteger(value) || value < min || value > max) {
		throw new RangeError(`${name} must be an integer in ${min}..${max}`);
	}
}

export interface SuggestInput {
	days: number;
	slots: SlotCount;
	people: number;
	seed: number;
	excludeTags: readonly RecipeTag[];
	excludeIngredients: readonly string[];
	noRepeatDays?: number;
}

/** The body of POST /api/plan/suggest. Throws RangeError on out-of-contract input. */
export function buildSuggestRequest(input: SuggestInput): PlanSuggestRequest {
	assertInt(input.days, 1, PLAN_MAX_DAYS, 'days');
	assertInt(input.people, LIMITS.peopleMin, LIMITS.peopleMax, 'people');
	assertInt(input.seed, 0, SEED_MAX, 'seed');
	const noRepeatDays = input.noRepeatDays ?? DEFAULT_NO_REPEAT_DAYS;
	assertInt(noRepeatDays, 0, LIMITS.noRepeatDaysMax, 'noRepeatDays');
	return {
		days: input.days,
		slots: input.slots,
		people: input.people,
		seed: input.seed,
		exclude_tags: [...new Set(input.excludeTags)].slice(0, LIMITS.excludeTagsMax),
		exclude_ingredients: [...new Set(input.excludeIngredients)]
			.filter((id) => ID_PATTERNS.ingredient.test(id))
			.slice(0, LIMITS.excludeIngredientsMax),
		red_meat_g_per_person_week: DEFAULT_RED_MEAT_G,
		no_repeat_days: noRepeatDays
	};
}

function cleanRecipeId(value: unknown): RecipeId | null {
	return typeof value === 'string' && ID_PATTERNS.recipe.test(value) ? value : null;
}

/** Every slot of the plan present, each a valid recipe id or null. */
function normaliseMeals(meals: PlanDayIO['meals'], slots: readonly Slot[]): PlanDayIO['meals'] {
	const out: PlanDayIO['meals'] = {};
	for (const slot of slots) out[slot] = cleanRecipeId(meals[slot]);
	return out;
}

export interface PlanMeta {
	startDate: string | null;
	seed: number;
	slots: SlotCount;
	noRepeatDays: number;
	/** ISO date-time. */
	createdAt: string;
}

/**
 * The stored plan for a /api/plan/suggest answer: days sorted by index (duplicates and out-of-range indexes
 * dropped), every planned slot present, anything that is not a recipe id turned into null.
 * Throws when the answer has no usable day.
 */
export function planFromResponse(response: Pick<PlanResponse, 'days'>, meta: PlanMeta): StoredPlan {
	const slots = slotsFor(meta.slots);
	const seen = new Set<number>();
	const days: PlanDayIO[] = [];
	for (const day of [...response.days].sort((a, b) => a.index - b.index)) {
		if (!Number.isInteger(day.index) || day.index < 0 || day.index >= PLAN_MAX_DAYS || seen.has(day.index)) continue;
		seen.add(day.index);
		days.push({ index: day.index, meals: normaliseMeals(day.meals ?? {}, slots) });
		if (days.length === PLAN_MAX_DAYS) break;
	}
	if (days.length === 0) throw new Error('the plan has no days');
	return { ...meta, startDate: isCalendarDate(meta.startDate) ? meta.startDate : null, days };
}

/** A plan of `days` days with every slot empty (used when a recipe is added before any plan exists). */
export function emptyPlan(meta: PlanMeta, days: number): StoredPlan {
	assertInt(days, 1, PLAN_MAX_DAYS, 'days');
	const slots = slotsFor(meta.slots);
	return {
		...meta,
		startDate: isCalendarDate(meta.startDate) ? meta.startDate : null,
		days: Array.from({ length: days }, (_, index) => ({ index, meals: normaliseMeals({}, slots) }))
	};
}

/** The recipe in a slot: a recipe id, null when empty, undefined when the day or slot is not in the plan. */
export function mealAt(plan: StoredPlan, dayIndex: number, slot: Slot): RecipeId | null | undefined {
	if (!slotsFor(plan.slots).includes(slot)) return undefined;
	const day = plan.days.find((d) => d.index === dayIndex);
	if (!day) return undefined;
	return cleanRecipeId(day.meals[slot]);
}

/**
 * Puts `recipeId` (or null to clear) into one slot. Returns the same plan object when nothing changes: an
 * unknown day, a slot the plan does not have, an invalid id, or the slot already holding that value.
 */
export function setMeal(plan: StoredPlan, dayIndex: number, slot: Slot, recipeId: RecipeId | null): StoredPlan {
	if (recipeId !== null && !ID_PATTERNS.recipe.test(recipeId)) return plan;
	const current = mealAt(plan, dayIndex, slot);
	if (current === undefined || current === recipeId) return plan;
	return {
		...plan,
		days: plan.days.map((day) =>
			day.index === dayIndex ? { index: day.index, meals: { ...day.meals, [slot]: recipeId } } : day
		)
	};
}

export function clearMeal(plan: StoredPlan, dayIndex: number, slot: Slot): StoredPlan {
	return setMeal(plan, dayIndex, slot, null);
}

/** The calendar date of a plan day, or null for an undated plan. */
export function dayDate(plan: Pick<StoredPlan, 'startDate'>, dayIndex: number): string | null {
	return plan.startDate && isCalendarDate(plan.startDate) ? addDays(plan.startDate, dayIndex) : null;
}

export interface PlanMealView {
	slot: Slot;
	recipeId: RecipeId | null;
}

export interface PlanDayView {
	index: number;
	/** "YYYY-MM-DD", or null for an undated plan. */
	date: string | null;
	/** Monday = 0 … Sunday = 6, or null for an undated plan. */
	weekday: number | null;
	meals: PlanMealView[];
}

export interface PlanWeekView {
	/** 0-based; the same 7-day blocks the API checks (week = day index ÷ 7, rounded down). */
	week: number;
	days: PlanDayView[];
}

function dayView(plan: StoredPlan, day: PlanDayIO): PlanDayView {
	const date = dayDate(plan, day.index);
	return {
		index: day.index,
		date,
		weekday: date === null ? null : weekdayIndex(date),
		meals: slotsFor(plan.slots).map((slot) => ({ slot, recipeId: cleanRecipeId(day.meals[slot]) }))
	};
}

/** The plan's days in order, grouped into the 7-day blocks of the rule checks. */
export function planWeeks(plan: StoredPlan): PlanWeekView[] {
	const weeks: PlanWeekView[] = [];
	for (const day of [...plan.days].sort((a, b) => a.index - b.index)) {
		const week = Math.floor(day.index / PLAN_WEEK_DAYS);
		let group = weeks.at(-1);
		if (!group || group.week !== week) {
			group = { week, days: [] };
			weeks.push(group);
		}
		group.days.push(dayView(plan, day));
	}
	return weeks;
}

/** Recipe ids in the plan's slots, in plan order (day index, then slot order), with repeats. */
function plannedRecipeIds(plan: Pick<StoredPlan, 'days' | 'slots'>): RecipeId[] {
	const slots = slotsFor(plan.slots);
	const ids: RecipeId[] = [];
	for (const day of [...plan.days].sort((a, b) => a.index - b.index)) {
		for (const slot of slots) {
			const id = cleanRecipeId(day.meals[slot]);
			if (id !== null) ids.push(id);
		}
	}
	return ids;
}

/** Number of filled meals. */
export function mealCount(plan: Pick<StoredPlan, 'days' | 'slots'>): number {
	return plannedRecipeIds(plan).length;
}

function idSet(recipes: Iterable<{ readonly id: RecipeId }>): Set<RecipeId> {
	const ids = new Set<RecipeId>();
	for (const recipe of recipes) ids.add(recipe.id);
	return ids;
}

/** Planned recipe ids that are not in `recipes` (e.g. a recipe removed from the library), each once. */
export function unknownPlanRecipeIds(
	plan: Pick<StoredPlan, 'days' | 'slots'>,
	recipes: Iterable<{ readonly id: RecipeId }>
): RecipeId[] {
	const known = idSet(recipes);
	return [...new Set(plannedRecipeIds(plan).filter((id) => !known.has(id)))];
}

/**
 * The body of POST /api/plan/check for an (edited) plan. With `known`, recipe ids that are not in it are
 * sent as empty slots, because the API rejects the whole request for an unknown id.
 */
export function buildCheckRequest(
	plan: StoredPlan,
	people: number,
	known: ReadonlySet<RecipeId> | null = null
): PlanCheckRequest {
	assertInt(people, LIMITS.peopleMin, LIMITS.peopleMax, 'people');
	const slots = slotsFor(plan.slots);
	return {
		days: [...plan.days]
			.sort((a, b) => a.index - b.index)
			.map((day) => {
				const meals: PlanDayIO['meals'] = {};
				for (const slot of slots) {
					const id = cleanRecipeId(day.meals[slot]);
					meals[slot] = id !== null && (known === null || known.has(id)) ? id : null;
				}
				return { index: day.index, meals };
			}),
		people,
		red_meat_g_per_person_week: DEFAULT_RED_MEAT_G,
		no_repeat_days: plan.noRepeatDays
	};
}

/**
 * Shopping-list items for POST /api/list: every planned meal is `people` servings, summed per recipe (in
 * the order recipes first appear in the plan). Meals whose recipe is not in `recipes` are left out, because
 * the API rejects the whole request for an unknown recipe id. A total above 100 servings is split into
 * several items of the same recipe (the API sums them). Returns [] for no plan or no known meal.
 *
 * Bounds: at most 31 days × 5 slots × 12 people = 1,860 servings, i.e. at most 155 + 18 = 173 items, within
 * the API's limit of 200.
 */
export function planToListItems(
	plan: Pick<StoredPlan, 'days' | 'slots'> | null,
	recipes: Iterable<{ readonly id: RecipeId }>,
	people: number
): ListItemIn[] {
	assertInt(people, LIMITS.peopleMin, LIMITS.peopleMax, 'people');
	if (plan === null) return [];
	const known = idSet(recipes);
	const meals = new Map<RecipeId, number>();
	for (const id of plannedRecipeIds(plan)) {
		if (known.has(id)) meals.set(id, (meals.get(id) ?? 0) + 1);
	}
	const items: ListItemIn[] = [];
	for (const [recipeId, count] of meals) {
		let remaining = count * people;
		while (remaining > 0) {
			const servings = Math.min(remaining, MAX_SERVINGS_PER_ITEM);
			items.push({ recipe_id: recipeId, servings });
			remaining -= servings;
		}
	}
	return items;
}
