/**
 * POST /api/list from the stored plan: for the chosen range, every planned meal is `people` servings, summed
 * per recipe (`planToListItems` from the plan helpers). Recipes that are no longer in the library are left
 * out (the API would reject the whole request) and reported, so the page can say so. Nothing else is sent:
 * no `on_hand` (the app keeps no on-hand quantities) and no personal data.
 */
import type { ListRequest, RecipeId } from '../api/types';
import { planToListItems, unknownPlanRecipeIds } from '../plan/plan';
import type { StoredPlan } from '../storage';
import { planForRange, rangeInfo, type ListRange } from './range';

export interface ListRequestPlan {
	/** The body for POST /api/list; null when the range has no planned meal of a known recipe. */
	request: ListRequest | null;
	/** Planned recipe ids in the range that the library no longer has, each once. */
	unknownRecipeIds: RecipeId[];
	/** Planned days in the range. */
	days: number;
}

export function buildListRequest(
	plan: StoredPlan,
	range: ListRange,
	today: string,
	recipes: Iterable<{ readonly id: RecipeId }>,
	people: number
): ListRequestPlan {
	const info = rangeInfo(plan, range, today);
	const part = planForRange(plan, info);
	const known = [...recipes];
	const items = planToListItems(part, known, people);
	const unknownRecipeIds = unknownPlanRecipeIds(part, known);
	if (items.length === 0) return { request: null, unknownRecipeIds, days: info.dayIndexes.length };
	const request: ListRequest = { items };
	return { request, unknownRecipeIds, days: info.dayIndexes.length };
}

/** A stable identity of "this list": the plan it was made from and the range. */
export function listKey(plan: Pick<StoredPlan, 'createdAt'>, range: ListRange): string {
	return `${plan.createdAt}|${range}`;
}
