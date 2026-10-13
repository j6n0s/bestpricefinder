/**
 * Public reference data the list feature needs, fetched at most once per page session and kept in memory:
 * GET /api/stores (about 1,800 rows; distances are computed from it on the device), GET /api/ingredients
 * (pantry and exclusion settings) and GET /api/recipes (which planned recipes still exist). A failed request
 * is forgotten, so "Újra" fetches again. The service worker caches these GETs as well (stale-while-revalidate).
 */
import { getIngredients, getRecipes, getStores, type RequestOptions } from '../api/client';
import type { IngredientsResponse, RecipesResponse, StoresResponse } from '../api/types';

type Loader<T> = (options?: RequestOptions) => Promise<T>;

/** Memoises one GET: concurrent and later callers share the first successful answer. */
export function memoised<T>(fetcher: Loader<T>): { get: () => Promise<T>; reset: () => void } {
	let cached: Promise<T> | null = null;
	return {
		get(): Promise<T> {
			if (cached) return cached;
			const pending = fetcher().catch((error: unknown) => {
				if (cached === pending) cached = null;
				throw error;
			});
			cached = pending;
			return pending;
		},
		reset(): void {
			cached = null;
		}
	};
}

const stores = memoised<StoresResponse>((options) => getStores(options));
const ingredients = memoised<IngredientsResponse>((options) => getIngredients(options));
const recipes = memoised<RecipesResponse>((options) => getRecipes({}, options));

export const loadStores = (): Promise<StoresResponse> => stores.get();
export const loadIngredients = (): Promise<IngredientsResponse> => ingredients.get();
export const loadRecipes = (): Promise<RecipesResponse> => recipes.get();

/** Test hook. */
export function resetDataCacheForTests(): void {
	stores.reset();
	ingredients.reset();
	recipes.reset();
}
