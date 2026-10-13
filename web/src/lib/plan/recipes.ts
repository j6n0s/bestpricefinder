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

const WORD_NUMBERS: Readonly<Record<string, number>> = { fél: 0.5, másfél: 1.5 };

function parseAmount(token: string): number {
	const word = WORD_NUMBERS[token.toLocaleLowerCase('hu-HU')];
	return word ?? Number(token.replace(',', '.'));
}

/**
 * A number ("40", "1,5"), "fél" (½) or "másfél" (1½), optionally a range ("1–2"); not inside a word or
 * another number, and not a percentage or a suffixed number ("2,8%", "2-es").
 */
const AMOUNT = /(?<![\p{L}\p{N},.])(\d+(?:,\d+)?|másfél|fél)(?:(\s*[–-]\s*)(\d+(?:,\d+)?|másfél|fél))?(?![\p{N}%]|,\d|-\p{L})/giu;

/**
 * Scales every amount in a recipe line's display text ("40 dkg" × 0.5 -> "20 dkg", "3 evőkanál (1 a rizshez,
 * 2 a mártáshoz)" × 2 -> "6 evőkanál (2 a rizshez, 4 a mártáshoz)", "másfél fej" × 2 -> "3 fej"). Text
 * without a number ("ízlés szerint") stays as it is. With factor 1 (or an invalid factor) the text is
 * returned unchanged.
 */
export function scaleDisplay(display: string, factor: number): string {
	if (!Number.isFinite(factor) || factor <= 0 || factor === 1) return display;
	return display.replace(
		AMOUNT,
		(match: string, first: string, separator: string | undefined, second: string | undefined, offset: number) => {
			const last = second ?? first;
			const next = display.charAt(offset + match.length);
			// "fél" / "másfél" must be whole words ("félbevágott" is not an amount).
			if (/^\D/u.test(last) && /\p{L}/u.test(next)) return match;
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

/**
 * docs/ENGINE.md "Cheapest chain of a recipe" (contract v1.2): only chains that price at least 90 % of the
 * recipe's estimated cost can be "the cheapest", or, when none reaches 90 %, the best-covered chains. The
 * server's priced_share is rounded DOWN to 4 decimals, so `>= 0.9` on it is exactly the server's test.
 */
export const MIN_CHEAPEST_SHARE = 0.9;

export interface ChainCostRow {
	chain: ChainSlug;
	name: string;
	costPerServing: number | null;
	/**
	 * Competition rank on whole forints among the comparable chains (tied chains share it: 1, 1, 3); null for
	 * a partial or an unpriced chain.
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

function shareOf(cost: ChainCostOut): number {
	return Number.isFinite(cost.priced_share) ? cost.priced_share : 0;
}

/** The priced chains that may be ranked: priced_share ≥ 0.9, else the ones with the highest share. */
export function comparableChainCosts<T extends ChainCostOut>(costs: readonly T[]): T[] {
	const priced = costs.filter(isPriced);
	const covered = priced.filter((cost) => shareOf(cost) >= MIN_CHEAPEST_SHARE);
	if (covered.length > 0 || priced.length === 0) return covered;
	const top = Math.max(...priced.map(shareOf));
	return priced.filter((cost) => shareOf(cost) === top);
}

/**
 * The chain cost comparison. First the comparable chains (see `comparableChainCosts`), cheapest first: equal
 * whole-forint costs form a tie, share a rank and keep the server's order (never re-ordered by name). Then
 * the partial chains, unranked, in the server's order (a chain that prices only a cheap subset of the lines
 * is never shown as cheaper than a fully priced one). Unpriced chains come last, in the server's order.
 */
export function chainCostRows(costs: readonly ChainCostOut[], names: ReadonlyMap<ChainSlug, string>): ChainCostRow[] {
	const priced = costs.filter(isPriced);
	const comparable = new Set<ChainCostOut>(comparableChainCosts(costs));
	const ranked = priced.filter((cost) => comparable.has(cost));
	const whole = (cost: number): number => Math.round(cost);
	const max = priced.reduce((highest, cost) => Math.max(highest, cost.cost_per_serving), 0);
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
	const rows: ChainCostRow[] = ranked
		.map((cost, position) => ({ cost, position }))
		.sort((a, b) => whole(a.cost.cost_per_serving) - whole(b.cost.cost_per_serving) || a.position - b.position)
		.map(({ cost }) => {
			const own = whole(cost.cost_per_serving);
			const cheaper = ranked.filter((other) => whole(other.cost_per_serving) < own).length;
			const same = ranked.filter((other) => whole(other.cost_per_serving) === own).length;
			return pricedRow(cost, cheaper + 1, same > 1);
		});
	for (const cost of priced) {
		if (!comparable.has(cost)) rows.push(pricedRow(cost, null, false));
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
