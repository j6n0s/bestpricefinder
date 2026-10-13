/**
 * Shape checks for the /api/list and /api/quote answers before the page renders them. The API client only
 * checks that the body is a JSON object; a malformed answer (a server bug, a proxy page) must never crash the
 * page or show a wrong price, so an answer that does not match the contract (server/bpf/api/schemas.py) is
 * rejected as a whole, and duplicate ids (which would break keyed lists) are dropped.
 */
import {
	UNITS,
	type AttributionSet,
	type AvailabilityKind,
	type IngredientOut,
	type LineStatus,
	type ListLineOut,
	type PackOptionOut,
	type PickOut,
	type PriceScope,
	type PriceType,
	type QuoteLineOut,
	type QuoteResponse,
	type RankOut,
	type SplitOut,
	type StoreOut,
	type StoreQuoteOut
} from '../api/types';

// Each list is checked against the generated union, so a contract change is a type error here.
const STATUSES = ['priced', 'pantry', 'unavailable', 'ksh_estimate', 'unpriced'] as const satisfies readonly LineStatus[];
const PRICE_TYPES = ['NORMAL', 'DISCOUNTED', 'LOYALTY'] as const satisfies readonly PriceType[];
const PRICE_SCOPES = ['store', 'chain'] as const satisfies readonly PriceScope[];
const AVAILABILITY = ['confirmed', 'assumed'] as const satisfies readonly AvailabilityKind[];
const PRICED_BY = ['gvh', 'ksh', 'none'] as const satisfies readonly IngredientOut['priced_by'][];
const STORE_FORMATS = ['hyper', 'express', 'other'] as const satisfies readonly NonNullable<StoreOut['format']>[];
/** Compile-time only: a type error unless every member of the union `All` is in `Listed`. */
type AllListed<All, Listed extends All> = [Exclude<All, Listed>] extends [never] ? true : false;
type Check<T extends true> = T;
type _StatusesListed = Check<AllListed<LineStatus, (typeof STATUSES)[number]>>;
type _PriceTypesListed = Check<AllListed<PriceType, (typeof PRICE_TYPES)[number]>>;
type _PriceScopesListed = Check<AllListed<PriceScope, (typeof PRICE_SCOPES)[number]>>;
type _AvailabilityListed = Check<AllListed<AvailabilityKind, (typeof AVAILABILITY)[number]>>;
type _PricedByListed = Check<AllListed<IngredientOut['priced_by'], (typeof PRICED_BY)[number]>>;
type _FormatsListed = Check<AllListed<NonNullable<StoreOut['format']>, (typeof STORE_FORMATS)[number]>>;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

type Rec = Record<string, unknown>;

function isRecord(value: unknown): value is Rec {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

const isString = (value: unknown): value is string => typeof value === 'string';
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const isNumberOrNull = (value: unknown): value is number | null => value === null || isNumber(value);
const isInt = (value: unknown): value is number => isNumber(value) && Number.isInteger(value);
const oneOf = <T extends string>(values: readonly T[], value: unknown): value is T =>
	isString(value) && (values as readonly string[]).includes(value);
const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every(isString);

function isListLine(value: unknown): value is ListLineOut {
	return (
		isRecord(value) &&
		isString(value.ingredient_id) &&
		isString(value.name_hu) &&
		isNumber(value.qty) &&
		oneOf(UNITS, value.unit) &&
		isString(value.list_group) &&
		typeof value.pantry === 'boolean' &&
		isStringArray(value.recipe_ids)
	);
}

/** The lines of a POST /api/list answer, or null when the answer does not match the contract. */
export function validListLines(body: unknown): ListLineOut[] | null {
	if (!isRecord(body)) return null;
	const { lines } = body;
	if (!Array.isArray(lines) || !lines.every(isListLine)) return null;
	return uniqueBy(lines, (line) => line.ingredient_id);
}

function isOption(value: unknown): value is PackOptionOut {
	return (
		isRecord(value) &&
		isString(value.product_id) &&
		isString(value.product_name) &&
		isNumberOrNull(value.pack_size) &&
		isNumber(value.pack_price) &&
		isNumber(value.unit_price) &&
		oneOf(PRICE_TYPES, value.price_type) &&
		oneOf(PRICE_SCOPES, value.price_scope) &&
		oneOf(AVAILABILITY, value.availability)
	);
}

function isPick(value: unknown): value is PickOut {
	return isRecord(value) && isOption(value.option) && isInt(value.count) && isNumber(value.qty) && isNumber(value.cost);
}

function isQuoteLine(value: unknown): value is QuoteLineOut {
	return (
		isRecord(value) &&
		isString(value.ingredient_id) &&
		isNumber(value.qty) &&
		oneOf(UNITS, value.unit) &&
		oneOf(STATUSES, value.status) &&
		Array.isArray(value.picks) &&
		value.picks.every(isPick) &&
		isNumberOrNull(value.checkout_cost) &&
		isNumberOrNull(value.used_cost) &&
		isNumberOrNull(value.leftover_qty) &&
		isNumberOrNull(value.ksh_estimate) &&
		Array.isArray(value.alternatives) &&
		value.alternatives.every(isOption)
	);
}

function isStoreQuote(value: unknown): value is StoreQuoteOut {
	return (
		isRecord(value) &&
		isString(value.store_id) &&
		isString(value.chain) &&
		isNumber(value.checkout_total) &&
		isNumber(value.used_total) &&
		isStringArray(value.missing) &&
		isInt(value.assumed_count) &&
		isNumber(value.ksh_estimate_total) &&
		Array.isArray(value.lines) &&
		value.lines.every(isQuoteLine)
	);
}

function isRank(value: unknown): value is RankOut {
	return (
		isRecord(value) &&
		isString(value.store_id) &&
		isInt(value.rank) &&
		value.rank >= 1 &&
		isNumber(value.checkout_total) &&
		isNumber(value.penalized_total) &&
		isInt(value.missing_count)
	);
}

function isSplit(value: unknown): value is SplitOut {
	return (
		isRecord(value) &&
		Array.isArray(value.store_ids) &&
		value.store_ids.length === 2 &&
		value.store_ids.every(isString) &&
		value.store_ids[0] !== value.store_ids[1] &&
		isNumber(value.total) &&
		isNumber(value.saving) &&
		isRecord(value.assignment) &&
		Object.values(value.assignment).every(isString)
	);
}

function isAttribution(value: unknown): value is AttributionSet {
	return isRecord(value) && isRecord(value.gvh) && isRecord(value.ksh);
}

function uniqueBy<T>(items: readonly T[], key: (item: T) => string): T[] {
	const seen = new Set<string>();
	return items.filter((item) => {
		const k = key(item);
		if (seen.has(k)) return false;
		seen.add(k);
		return true;
	});
}

/** A POST /api/quote answer that matches the contract (duplicate stores and ranks dropped), else null. */
export function validQuote(body: unknown): QuoteResponse | null {
	if (!isRecord(body)) return null;
	const { data_date, stores, ranking, split, scope_note_hu, scope_note_en, attribution } = body;
	if (!isString(data_date) || !ISO_DATE.test(data_date)) return null;
	if (!Array.isArray(stores) || !stores.every(isStoreQuote)) return null;
	if (!Array.isArray(ranking) || !ranking.every(isRank)) return null;
	if (!(split === null || split === undefined || isSplit(split))) return null;
	if (!isString(scope_note_hu) || scope_note_hu.trim() === '' || !isString(scope_note_en)) return null;
	if (!isAttribution(attribution)) return null;
	return {
		data_date,
		stores: uniqueBy(stores, (store) => store.store_id),
		ranking: uniqueBy(ranking, (rank) => rank.store_id),
		split: split ?? null,
		scope_note_hu,
		scope_note_en,
		attribution
	};
}

function isIngredient(value: unknown): value is IngredientOut {
	return (
		isRecord(value) &&
		isString(value.id) &&
		isString(value.name_hu) &&
		isString(value.list_group) &&
		oneOf(UNITS, value.unit) &&
		isNumberOrNull(value.piece_weight_kg) &&
		typeof value.pantry === 'boolean' &&
		oneOf(PRICED_BY, value.priced_by) &&
		isStringArray(value.tags)
	);
}

/** The usable ingredients of a GET /api/ingredients answer (malformed rows and repeated ids dropped). */
export function validIngredients(body: unknown): IngredientOut[] {
	if (!isRecord(body) || !Array.isArray(body.ingredients)) return [];
	return uniqueBy(body.ingredients.filter(isIngredient), (ingredient) => ingredient.id);
}

const isStringOrNull = (value: unknown): value is string | null => value === null || isString(value);

function isStore(value: unknown): value is StoreOut {
	return (
		isRecord(value) &&
		isString(value.id) &&
		isString(value.chain) &&
		isStringOrNull(value.postal_code) &&
		isStringOrNull(value.city) &&
		isStringOrNull(value.address) &&
		isNumberOrNull(value.lat) &&
		isNumberOrNull(value.lon) &&
		(value.format === null || oneOf(STORE_FORMATS, value.format)) &&
		typeof value.is_budapest === 'boolean' &&
		typeof value.has_data === 'boolean'
	);
}

/**
 * The stores of a GET /api/stores answer with malformed rows and repeated ids dropped, or null when the
 * answer has no store list at all.
 */
export function validStores(body: unknown): StoreOut[] | null {
	if (!isRecord(body) || !Array.isArray(body.stores)) return null;
	return uniqueBy(body.stores.filter(isStore), (store) => store.id);
}

/** The recipe ids of a GET /api/recipes list (entries without a string id are ignored). */
export function recipeIds(recipes: readonly unknown[]): string[] {
	return recipes.flatMap((recipe) => (isRecord(recipe) && isString(recipe.id) ? [recipe.id] : []));
}
