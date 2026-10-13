/**
 * The recipe list's filters, kept in memory for this tab only: they survive moving between pages (so "back"
 * from a recipe shows the same list) but are never stored or put into the URL, because a filter such as
 * "húsmentes" is a diet preference and stays off the server (docs/ARCHITECTURE.md "Personal data").
 */
import type { RecipeTag, Slot } from '../api/types';

export interface RecipeFilterState {
	slot: Slot | '';
	tag: RecipeTag | '';
	q: string;
}

export const recipeFilters: RecipeFilterState = $state({ slot: '', tag: '', q: '' });

export function resetRecipeFilters(): void {
	recipeFilters.slot = '';
	recipeFilters.tag = '';
	recipeFilters.q = '';
}
