import type { planHu } from './plan.hu';
import type { Messages } from './types';

export const planEn: Messages<typeof planHu> = {
	title: 'Weekly plan',
	placeholder: 'Coming soon: put together the week’s meals here.',

	warning_slot_pool_empty: 'There is no recipe to choose for this meal: {slot}.',
	warning_slot_pool_too_small: 'There are few recipes for this meal, so some may repeat: {slot}.',
	warning_no_fish_recipe_available: 'There is no fish recipe to choose.',
	warning_no_legume_recipe_available: 'There is no legume recipe to choose.',
	warning_no_meat_free_recipe_available: 'There is no meat-free recipe for this meal: {slot}.',
	warning_no_potato_free_recipe_available: 'There is no potato-free recipe for this meal: {slot}.',
	warning_red_meat_cap_unreachable: 'The weekly red meat limit cannot be kept with these recipes.',
	warning_sweets_cap_unreachable: 'The weekly sweets limit cannot be kept with these recipes.',
	warning_budget_unreachable: 'The weekly budget cannot be kept with these recipes.',
	warning_recipe_cost_missing: 'There is not enough price data to check the weekly budget.',
	warning_unknown: 'Unknown warning: {code}.'
};
