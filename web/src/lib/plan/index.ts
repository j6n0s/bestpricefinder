/**
 * The weekly plan's pure helpers. For the shopping list: `planToListItems(plan, recipes, people)` turns the
 * stored plan (StoredState.plan) into the `items` of POST /api/list.
 */
export {
	DEFAULT_NO_REPEAT_DAYS,
	DEFAULT_RED_MEAT_G,
	MAX_SERVINGS_PER_ITEM,
	PLAN_MAX_DAYS,
	PLAN_WEEK_DAYS,
	buildCheckRequest,
	buildSuggestRequest,
	clearMeal,
	dayDate,
	emptyPlan,
	mealAt,
	mealCount,
	nextSeed,
	planFromResponse,
	planLengthDays,
	planToListItems,
	planWeeks,
	setMeal,
	slotsFor,
	unknownPlanRecipeIds,
	type PlanDayView,
	type PlanLength,
	type PlanMealView,
	type PlanMeta,
	type PlanWeekView,
	type SlotCount,
	type SuggestInput
} from './plan';
export { addDays, daysToMonthEnd, isCalendarDate, parseCalendarDate, todayInBudapest, weekdayIndex } from './dates';
