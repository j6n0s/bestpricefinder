/**
 * Weekly plan page ("Heti terv"). STUB: the plan feature agent extends this namespace (and plan.en.ts).
 * The warning texts map the machine codes of POST /api/plan/suggest (docs/API.md, docs/ENGINE.md).
 */
export const planHu = {
	title: 'Heti terv',
	placeholder: 'Hamarosan: itt állíthatod össze a hét étkezéseit.',

	warning_slot_pool_empty: 'Ehhez az étkezéshez nincs választható recept: {slot}.',
	warning_slot_pool_too_small: 'Ehhez az étkezéshez kevés a recept, ezért ismétlődhetnek: {slot}.',
	warning_no_fish_recipe_available: 'Nincs választható halas recept.',
	warning_no_legume_recipe_available: 'Nincs választható hüvelyes recept.',
	warning_no_meat_free_recipe_available: 'Ehhez az étkezéshez nincs húsmentes recept: {slot}.',
	warning_no_potato_free_recipe_available: 'Ehhez az étkezéshez nincs burgonya nélküli recept: {slot}.',
	warning_red_meat_cap_unreachable: 'A vörös hús heti felső határa ezekkel a receptekkel nem tartható.',
	warning_sweets_cap_unreachable: 'Az édességek heti felső határa ezekkel a receptekkel nem tartható.',
	warning_budget_unreachable: 'A heti keret ezekkel a receptekkel nem tartható.',
	warning_recipe_cost_missing: 'Nincs elég áradat a heti keret ellenőrzéséhez.',
	warning_unknown: 'Ismeretlen figyelmeztetés: {code}.'
} as const;
