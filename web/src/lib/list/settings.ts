/**
 * Pure helpers for the pantry ("Kamra") and exclusion settings. Both are personal data kept only on this
 * device ($lib/storage). Exclusions filter the plan suggestions only (POST /api/plan/suggest uses them for
 * that one computation and never stores them).
 */
import type { IngredientOut, RecipeTag } from '../api/types';
import type { PlainKey } from '../i18n/messages';
import { canBeBought } from './lines';

/** Recipe tags that make sense to exclude, in display order (descriptive tags only, no health wording). */
export const EXCLUDABLE_TAGS = [
	'hal',
	'baromfi',
	'sertes',
	'marha',
	'huvelyes',
	'edes',
	'leves',
	'fozelek',
	'salata',
	'ket_napos'
] as const satisfies readonly RecipeTag[];

export type ExcludableTag = (typeof EXCLUDABLE_TAGS)[number];

const TAG_KEYS: Readonly<Record<ExcludableTag, PlainKey>> = {
	hal: 'list.tag_hal',
	baromfi: 'list.tag_baromfi',
	sertes: 'list.tag_sertes',
	marha: 'list.tag_marha',
	huvelyes: 'list.tag_huvelyes',
	edes: 'list.tag_edes',
	leves: 'list.tag_leves',
	fozelek: 'list.tag_fozelek',
	salata: 'list.tag_salata',
	ket_napos: 'list.tag_ket_napos'
};

export function excludableTagKey(tag: ExcludableTag): PlainKey {
	return TAG_KEYS[tag];
}

/** Excluded tags stored on the device that this screen does not offer (kept, and listed so they can be removed). */
export function otherExcludedTags(excluded: readonly RecipeTag[]): RecipeTag[] {
	return excluded.filter((tag) => !(EXCLUDABLE_TAGS as readonly string[]).includes(tag));
}

/** Lower case without accents, single spaces: "Vöröshagyma " -> "voroshagyma". */
export function foldText(text: string): string {
	return text
		.normalize('NFD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.replace(/\s+/g, ' ')
		.trim();
}

const collator = new Intl.Collator('hu', { sensitivity: 'base' });

/** Ingredients sorted by Hungarian name. */
export function byName<T extends Pick<IngredientOut, 'name_hu' | 'id'>>(items: readonly T[]): T[] {
	return [...items].sort((a, b) => collator.compare(a.name_hu, b.name_hu) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

/** Each id once (the first wins), so keyed lists never see a duplicate. */
export function uniqueIngredients<T extends Pick<IngredientOut, 'id'>>(items: readonly T[]): T[] {
	const seen = new Set<string>();
	return items.filter((item) => {
		if (seen.has(item.id)) return false;
		seen.add(item.id);
		return true;
	});
}

/**
 * The pantry staples ("valószínűleg otthon van") that can be marked "nincs otthon", each once, sorted by
 * name. Tap water is left out: it is never bought (`NEVER_BOUGHT` in ./lines).
 */
export function pantryIngredients(ingredients: readonly IngredientOut[]): IngredientOut[] {
	return byName(
		uniqueIngredients(ingredients.filter((ingredient) => ingredient.pantry === true && canBeBought(ingredient.id)))
	);
}

export const SEARCH_MIN_CHARS = 2;
export const SEARCH_MAX_RESULTS = 8;

/**
 * Ingredients whose name contains the query (accent-insensitive), not yet excluded, sorted by name, at most
 * `limit`. Empty for a query shorter than 2 characters.
 */
export function searchIngredients(
	ingredients: readonly IngredientOut[],
	query: string,
	excluded: ReadonlySet<string>,
	limit: number = SEARCH_MAX_RESULTS
): IngredientOut[] {
	const folded = foldText(query);
	if (folded.length < SEARCH_MIN_CHARS) return [];
	const matches = ingredients.filter(
		(ingredient) => !excluded.has(ingredient.id) && foldText(ingredient.name_hu).includes(folded)
	);
	return byName(matches).slice(0, Math.max(0, limit));
}
