/**
 * Pure helpers for the recipe pages and the meal picker: accent-insensitive search (the same folding as the
 * server's `fold_name`), list filters, quantity scaling for the servings stepper, and the chain cost rows of
 * the recipe detail (tie-aware, BUILD-BRIEF §4.1 trap 13).
 *
 * No arithmetic on money happens here except ordering and bar lengths: every price shown is the server's
 * number, formatted by $lib/format.
 */
import { normaliseRecipeQuery } from '../api/client';
import {
	RECIPE_TAGS,
	type ChainCostOut,
	type ChainOut,
	type ChainSlug,
	type IngredientId,
	type RecipeSummary,
	type RecipeTag,
	type Slot
} from '../api/types';
import { formatNumber } from '../format';
import type { PlainKey } from '../i18n/messages';
import { isSlot } from './checks';

/**
 * True when there is at least one recipe and none of them is tested. A view showing only untested recipes
 * says so once (recipes.untested_all) instead of repeating the "kipróbálatlan recept" badge on every one.
 */
export function allUntested(recipes: Iterable<Pick<RecipeSummary, 'tested'>>): boolean {
	let any = false;
	for (const recipe of recipes) {
		if (recipe.tested) return false;
		any = true;
	}
	return any;
}

/** Servings stepper bounds on the recipe page. */
export const SERVINGS_MIN = 1;
export const SERVINGS_MAX = 24;

/** Lower-case, accents removed (NFKD minus combining marks), whitespace collapsed: like the server's fold_name. */
export function foldText(text: string): string {
	return text
		.normalize('NFKD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.split(/\s+/)
		.filter((part) => part.length > 0)
		.join(' ');
}

/** The folded search text, or null when it is too short to filter by (the API's 2–40 character rule). */
export function foldedQuery(q: string | null | undefined): string | null {
	const normalised = normaliseRecipeQuery(q ?? undefined);
	if (normalised === null) return null;
	const folded = foldText(normalised);
	return folded.length > 0 ? folded : null;
}

export function isRecipeTag(value: unknown): value is RecipeTag {
	return typeof value === 'string' && (RECIPE_TAGS as readonly string[]).includes(value);
}

export interface RecipeFilter {
	slot?: Slot | null;
	tag?: RecipeTag | null;
	q?: string | null;
}

type Filterable = Pick<RecipeSummary, 'title' | 'slots' | 'tags'>;

/** Recipes matching every given filter: slot, tag, and an accent-insensitive substring of the title. */
export function filterRecipes<T extends Filterable>(recipes: readonly T[], filter: RecipeFilter): T[] {
	const query = foldedQuery(filter.q);
	const slot = isSlot(filter.slot) ? filter.slot : null;
	const tag = isRecipeTag(filter.tag) ? filter.tag : null;
	return recipes.filter(
		(recipe) =>
			(slot === null || recipe.slots.includes(slot)) &&
			(tag === null || recipe.tags.includes(tag)) &&
			(query === null || foldText(recipe.title).includes(query))
	);
}

export function hasExcludedTag(recipe: Pick<RecipeSummary, 'tags'>, excludedTags: readonly string[]): boolean {
	return recipe.tags.some((tag) => excludedTags.includes(tag));
}

const collator = new Intl.Collator('hu', { sensitivity: 'base' });

/**
 * The recipes the picker offers for one slot: eligible for the slot, without the user's excluded tags,
 * matching the search, sorted by title (Hungarian collation).
 */
export function eligibleRecipes<T extends Filterable>(
	recipes: readonly T[],
	slot: Slot,
	excludedTags: readonly string[],
	q: string | null = null
): T[] {
	return filterRecipes(recipes, { slot, q })
		.filter((recipe) => !hasExcludedTag(recipe, excludedTags))
		.sort((a, b) => collator.compare(a.title, b.title));
}

/** The i18n key of a recipe tag's label, or null for a tag outside the vocabulary. */
export function tagLabelKey(tag: string): PlainKey | null {
	return isRecipeTag(tag) ? (`recipes.tag_${tag}` as PlainKey) : null;
}

export function clampServings(value: number): number {
	if (!Number.isFinite(value)) return SERVINGS_MIN;
	return Math.min(SERVINGS_MAX, Math.max(SERVINGS_MIN, Math.round(value)));
}

/** A scaled kitchen quantity, rounded: whole numbers from 10, one decimal from 1, two decimals below 1. */
export function roundScaled(value: number): number {
	if (!Number.isFinite(value) || value <= 0) return 0;
	if (value >= 10) return Math.round(value);
	if (value >= 1) return Math.round((value + 1e-9) * 10) / 10;
	return Math.max(0.01, Math.round((value + 1e-9) * 100) / 100);
}

/** Hungarian number words used as amounts in recipe displays ("egy kisebb fej", "negyed kígyóuborka"). */
const WORD_NUMBERS: Readonly<Record<string, number>> = {
	egy: 1,
	fél: 0.5,
	másfél: 1.5,
	negyed: 0.25,
	háromnegyed: 0.75
};

function parseAmount(token: string): number {
	const word = WORD_NUMBERS[token.toLocaleLowerCase('hu-HU')];
	return word ?? Number(token.replace(',', '.'));
}

/**
 * A number ("40", "1,5") or a number word ("egy" 1, "fél" ½, "másfél" 1½, "negyed" ¼, "háromnegyed" ¾),
 * optionally a range ("1–2"); not inside a word or another number, and not a percentage or a suffixed number
 * ("2,8%", "2-es"). Longer words come first, and the look-behind keeps "negyed" from matching inside
 * "háromnegyed" (and "egy" inside "negyed").
 */
const NUMBER_WORDS = 'háromnegyed|negyed|másfél|fél|egy';
const AMOUNT = new RegExp(
	`(?<![\\p{L}\\p{N},.])(\\d+(?:,\\d+)?|${NUMBER_WORDS})(?:(\\s*[–-]\\s*)(\\d+(?:,\\d+)?|${NUMBER_WORDS}))?(?![\\p{N}%]|,\\d|-\\p{L})`,
	'giu'
);

/**
 * Scales every amount in a recipe line's display text ("40 dkg" × 0.5 -> "20 dkg", "3 evőkanál (1 a rizshez,
 * 2 a mártáshoz)" × 2 -> "6 evőkanál (2 a rizshez, 4 a mártáshoz)", "másfél fej" × 2 -> "3 fej", "negyed fej"
 * × 2 -> "0,5 fej", "1 kg (egy kisebb fej)" × 2 -> "2 kg (2 kisebb fej)"). Number words count only as whole
 * words ("egyszerű", "negyedelt", "félbevágott" stay). Text without an amount ("ízlés szerint") stays as it
 * is. With factor 1 (or an invalid factor) the text is returned unchanged.
 */
export function scaleDisplay(display: string, factor: number): string {
	if (!Number.isFinite(factor) || factor <= 0 || factor === 1) return display;
	return display.replace(
		AMOUNT,
		(match: string, first: string, separator: string | undefined, second: string | undefined, offset: number) => {
			const last = second ?? first;
			const next = display.charAt(offset + match.length);
			// Number words must be whole words ("félbevágott", "egyszerű", "negyedelt" are not amounts).
			if (/^\D/u.test(last) && /\p{L}/u.test(next)) return match;
			// "egy-egy", "fél-fél" mean "one/half each", not a range.
			if (second !== undefined && /^\D/u.test(first) && first.toLocaleLowerCase('hu-HU') === second.toLocaleLowerCase('hu-HU')) {
				return match;
			}
			const scaled = formatNumber(roundScaled(parseAmount(first) * factor));
			if (second === undefined || separator === undefined) return scaled;
			return `${scaled}${separator}${formatNumber(roundScaled(parseAmount(second) * factor))}`;
		}
	);
}

/** A 0..1 share as a whole percentage, rounded DOWN so a partial coverage never reads as 100 %. */
export function coveragePercent(share: number): number {
	if (!Number.isFinite(share)) return 0;
	return Math.min(100, Math.max(0, Math.floor(share * 100 + 1e-9)));
}

/** slug -> display name from /api/meta. */
export function chainNameMap(chains: readonly ChainOut[] | null | undefined): Map<ChainSlug, string> {
	return new Map((chains ?? []).map((chain) => [chain.slug, chain.name]));
}

export function chainName(slug: ChainSlug, names: ReadonlyMap<ChainSlug, string>): string {
	return names.get(slug) ?? slug;
}

/** Every chain of a tie group, in the server's order (a tie is never broken, so no chain is singled out). */
export function chainList(slugs: readonly ChainSlug[], names: ReadonlyMap<ChainSlug, string>): string {
	return slugs.map((slug) => chainName(slug, names)).join(', ');
}

export interface ChainCostRow {
	chain: ChainSlug;
	name: string;
	costPerServing: number | null;
	/**
	 * The server's competition rank on whole forints among the comparable chains (tied chains share it: 1, 1,
	 * 3); null for a partial or an unpriced chain.
	 */
	rank: number | null;
	/** Another comparable chain has the same whole-forint cost. */
	tied: boolean;
	/** Priced, but below the coverage the ranking needs: its price covers only part of the recipe. */
	partial: boolean;
	/** Bar length, 0–100, relative to the most expensive priced chain. */
	barPercent: number;
	coveragePercent: number;
	missing: readonly IngredientId[];
}

function isPriced(cost: ChainCostOut): cost is ChainCostOut & { cost_per_serving: number } {
	return typeof cost.cost_per_serving === 'number' && Number.isFinite(cost.cost_per_serving);
}

/**
 * The chain cost comparison (docs/ENGINE.md "Cheapest chain of a recipe", contract v1.2). The ranks come from
 * the server (`ChainCostOut.rank`): a competition rank on whole forints computed from the unrounded costs, so
 * the client never re-derives it from the 2-decimal JSON money. Ranked chains come first, by rank; tied
 * chains share a rank and keep the server's order (never re-ordered by name). Then the priced but unranked
 * chains (they price only part of the recipe: shown as partial), then the unpriced ones, in the server's order.
 */
export function chainCostRows(costs: readonly ChainCostOut[], names: ReadonlyMap<ChainSlug, string>): ChainCostRow[] {
	const priced = costs.filter(isPriced);
	const max = priced.reduce((highest, cost) => Math.max(highest, cost.cost_per_serving), 0);
	const rankOf = (cost: ChainCostOut): number | null =>
		typeof cost.rank === 'number' && Number.isInteger(cost.rank) && cost.rank >= 1 ? cost.rank : null;
	const pricedRow = (cost: ChainCostOut & { cost_per_serving: number }, rank: number | null, tied: boolean): ChainCostRow => {
		const ratio = max > 0 ? cost.cost_per_serving / max : 0;
		return {
			chain: cost.chain,
			name: chainName(cost.chain, names),
			costPerServing: cost.cost_per_serving,
			rank,
			tied,
			partial: rank === null,
			barPercent: cost.cost_per_serving > 0 ? Math.min(100, Math.max(1, Math.round(ratio * 1000) / 10)) : 0,
			coveragePercent: coveragePercent(cost.priced_share),
			missing: cost.missing
		};
	};
	const ranked = priced
		.map((cost, position) => ({ cost, position, rank: rankOf(cost) }))
		.filter((entry): entry is { cost: (typeof priced)[number]; position: number; rank: number } => entry.rank !== null)
		.sort((a, b) => a.rank - b.rank || a.position - b.position);
	const rows: ChainCostRow[] = ranked.map(({ cost, rank }) =>
		pricedRow(cost, rank, ranked.filter((other) => other.rank === rank).length > 1)
	);
	for (const cost of priced) {
		if (rankOf(cost) === null) rows.push(pricedRow(cost, null, false));
	}
	for (const cost of costs) {
		if (isPriced(cost)) continue;
		rows.push({
			chain: cost.chain,
			name: chainName(cost.chain, names),
			costPerServing: null,
			rank: null,
			tied: false,
			partial: false,
			barPercent: 0,
			coveragePercent: coveragePercent(cost.priced_share),
			missing: cost.missing
		});
	}
	return rows;
}
