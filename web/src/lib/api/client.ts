/**
 * Typed fetch wrapper for every /api endpoint (contract: server/bpf/api/schemas.py, docs/API.md).
 *
 * - JSON only: requests send `Accept: application/json`; POST bodies are `application/json`.
 * - Every request times out after 15 s (AbortController); a caller's AbortSignal is honoured too.
 * - Failures become an `ApiError` with a `kind` (http, offline, network, timeout, aborted, invalid_response)
 *   and, for HTTP errors, the server's `{error, fields}` body mapped to `code` and `fields`.
 * - Same origin, no cookies (`credentials: 'omit'`), no redirects followed.
 * - Privacy: request bodies are rebuilt from the known fields only, so nothing else (for example a location
 *   accidentally spread into a request object) can ever leave the device. /api/quote takes store ids only.
 * - Quantities (`qty`, `servings`) always go out as JSON numbers (contract v1.2 rejects strings): a value
 *   that is not a finite number is sent as `null`, which the server answers with a 422 for that field.
 */
import {
	ERROR_CODES,
	type ErrorCode,
	type HealthResponse,
	type HistoryQuery,
	type HistoryResponse,
	type IngredientsResponse,
	type IngredientId,
	type PlanDayIO,
	type ListRequest,
	type ListResponse,
	type MetaResponse,
	type PlanCheckRequest,
	type PlanCheckResponse,
	type PlanResponse,
	type PlanSuggestRequest,
	type QtyLineIn,
	type QuoteRequest,
	type QuoteResponse,
	type RecipeDetail,
	type RecipeId,
	type RecipesQuery,
	type RecipesResponse,
	type StoresResponse,
	LIMITS,
	SLOTS
} from './types';

export const API_TIMEOUT_MS = 15_000;

export type ApiErrorKind = 'http' | 'offline' | 'network' | 'timeout' | 'aborted' | 'invalid_response';

export interface ApiErrorInit {
	kind: ApiErrorKind;
	status?: number | null;
	code?: ErrorCode | null;
	fields?: readonly string[];
	retryAfterS?: number | null;
}

export class ApiError extends Error {
	override readonly name = 'ApiError';
	readonly kind: ApiErrorKind;
	/** HTTP status for kind "http" (and "invalid_response" when a response arrived); otherwise null. */
	readonly status: number | null;
	/** The server's error code (`ErrorResponse.error`), or one derived from the status when the body has none. */
	readonly code: ErrorCode | null;
	/** Dotted paths of invalid fields (422 only); never values. */
	readonly fields: readonly string[];
	/** Seconds from a 429 `Retry-After` header. */
	readonly retryAfterS: number | null;

	constructor(init: ApiErrorInit) {
		super(init.code ? `${init.kind}: ${init.code}` : init.status ? `${init.kind}: HTTP ${init.status}` : init.kind);
		this.kind = init.kind;
		this.status = init.status ?? null;
		this.code = init.code ?? null;
		this.fields = Object.freeze([...(init.fields ?? [])]);
		this.retryAfterS = init.retryAfterS ?? null;
	}
}

export function isApiError(value: unknown): value is ApiError {
	return value instanceof ApiError;
}

export interface RequestOptions {
	/** Cancels the request; the promise then rejects with an ApiError of kind "aborted". */
	signal?: AbortSignal;
	/** Injected fetch (tests, or SvelteKit's load fetch). Defaults to the global fetch. */
	fetch?: typeof fetch;
	/** Defaults to API_TIMEOUT_MS. */
	timeoutMs?: number;
}

interface InternalOptions extends RequestOptions {
	/** Non-2xx statuses whose body is a valid response for this endpoint (e.g. 503 from /api/health). */
	acceptStatuses?: readonly number[];
}

/** True when the browser reports that it is offline. Never throws. */
export function isOffline(): boolean {
	try {
		return typeof navigator !== 'undefined' && navigator.onLine === false;
	} catch {
		return false;
	}
}

const STATUS_CODES: Readonly<Record<number, ErrorCode>> = {
	404: 'not_found',
	405: 'method_not_allowed',
	413: 'payload_too_large',
	415: 'unsupported_media_type',
	422: 'invalid_request',
	429: 'rate_limited',
	500: 'internal',
	503: 'no_data'
};

function isErrorCode(value: unknown): value is ErrorCode {
	return typeof value === 'string' && (ERROR_CODES as readonly string[]).includes(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseJson(text: string): unknown {
	try {
		return JSON.parse(text) as unknown;
	} catch {
		return undefined;
	}
}

function isJsonResponse(res: Response): boolean {
	const type = res.headers.get('content-type') ?? '';
	return /^application\/(?:[\w.+-]+\+)?json\b/i.test(type.trim());
}

/** Retry-After in seconds (delta-seconds form only; the API never sends an HTTP date). */
export function parseRetryAfter(value: string | null): number | null {
	if (value === null || !/^\s*\d{1,6}\s*$/.test(value)) return null;
	return Number.parseInt(value, 10);
}

/** Maps a non-2xx response to an ApiError, using the `{error, fields}` body when it is well-formed. */
export function errorFromResponse(status: number, body: unknown, retryAfter: string | null): ApiError {
	let code: ErrorCode | null = STATUS_CODES[status] ?? null;
	let fields: string[] = [];
	if (isRecord(body)) {
		if (isErrorCode(body.error)) code = body.error;
		if (Array.isArray(body.fields)) {
			fields = body.fields.filter((f): f is string => typeof f === 'string').slice(0, 200);
		}
	}
	return new ApiError({ kind: 'http', status, code, fields, retryAfterS: parseRetryAfter(retryAfter) });
}

async function request<T>(method: 'GET' | 'POST', path: string, body: unknown, options: InternalOptions): Promise<T> {
	const doFetch = options.fetch ?? globalThis.fetch.bind(globalThis);
	const timeoutMs = options.timeoutMs ?? API_TIMEOUT_MS;
	const controller = new AbortController();
	const outer = options.signal;
	let timedOut = false;
	const onOuterAbort = (): void => controller.abort();
	const timer = setTimeout(() => {
		timedOut = true;
		controller.abort();
	}, timeoutMs);
	if (outer) {
		if (outer.aborted) controller.abort();
		else outer.addEventListener('abort', onOuterAbort, { once: true });
	}

	const failure = (): ApiError => {
		if (timedOut) return new ApiError({ kind: 'timeout' });
		if (outer?.aborted) return new ApiError({ kind: 'aborted' });
		return new ApiError({ kind: isOffline() ? 'offline' : 'network' });
	};

	try {
		const headers: Record<string, string> = { Accept: 'application/json' };
		const init: RequestInit = {
			method,
			headers,
			signal: controller.signal,
			credentials: 'omit',
			redirect: 'error',
			referrerPolicy: 'no-referrer'
		};
		if (method === 'POST') {
			headers['Content-Type'] = 'application/json';
			init.body = JSON.stringify(body);
		}

		let res: Response;
		let text: string;
		try {
			if (controller.signal.aborted) throw new Error('aborted before start');
			res = await doFetch(path, init);
			text = await res.text();
		} catch {
			throw failure();
		}

		const accepted = res.ok || (options.acceptStatuses ?? []).includes(res.status);
		const parsed = isJsonResponse(res) ? parseJson(text) : undefined;
		if (!accepted) throw errorFromResponse(res.status, parsed, res.headers.get('retry-after'));
		if (!isRecord(parsed)) throw new ApiError({ kind: 'invalid_response', status: res.status });
		return parsed as T;
	} finally {
		clearTimeout(timer);
		outer?.removeEventListener('abort', onOuterAbort);
	}
}

function withQuery(path: string, params: URLSearchParams): string {
	const query = params.toString();
	return query ? `${path}?${query}` : path;
}

/** Normalises the recipe search text: trimmed, at most 40 characters, omitted when shorter than 2. */
export function normaliseRecipeQuery(q: string | undefined): string | null {
	if (q === undefined) return null;
	const trimmed = q.trim().slice(0, LIMITS.recipeQueryMax).trim();
	return trimmed.length >= LIMITS.recipeQueryMin ? trimmed : null;
}

// ───────────────────────────── GET endpoints ─────────────────────────────

/** GET /api/health. A 503 with the `{status: "down"}` body is returned, not thrown. */
export function getHealth(options: RequestOptions = {}): Promise<HealthResponse> {
	return request<HealthResponse>('GET', '/api/health', undefined, { ...options, acceptStatuses: [503] });
}

export function getMeta(options: RequestOptions = {}): Promise<MetaResponse> {
	return request<MetaResponse>('GET', '/api/meta', undefined, options);
}

export function getStores(options: RequestOptions = {}): Promise<StoresResponse> {
	return request<StoresResponse>('GET', '/api/stores', undefined, options);
}

export function getIngredients(options: RequestOptions = {}): Promise<IngredientsResponse> {
	return request<IngredientsResponse>('GET', '/api/ingredients', undefined, options);
}

export function getRecipes(query: RecipesQuery = {}, options: RequestOptions = {}): Promise<RecipesResponse> {
	const params = new URLSearchParams();
	if (query.slot) params.set('slot', query.slot);
	if (query.tag) params.set('tag', query.tag);
	const q = normaliseRecipeQuery(query.q);
	if (q !== null) params.set('q', q);
	return request<RecipesResponse>('GET', withQuery('/api/recipes', params), undefined, options);
}

export function getRecipe(id: RecipeId, options: RequestOptions = {}): Promise<RecipeDetail> {
	return request<RecipeDetail>('GET', `/api/recipes/${encodeURIComponent(id)}`, undefined, options);
}

export function getIngredientHistory(
	id: IngredientId,
	query: HistoryQuery = {},
	options: RequestOptions = {}
): Promise<HistoryResponse> {
	const params = new URLSearchParams();
	if (query.chain) params.set('chain', query.chain);
	if (query.days !== undefined) params.set('days', String(Math.trunc(query.days)));
	return request<HistoryResponse>(
		'GET',
		withQuery(`/api/ingredients/${encodeURIComponent(id)}/history`, params),
		undefined,
		options
	);
}

// ───────────────────────────── POST endpoints (bodies rebuilt from known fields) ─────────────────────────────

/**
 * A quantity as it goes on the wire: the number itself, never a string (contract v1.2). Anything that is not
 * a finite number becomes null, which the server rejects with a 422 naming the field.
 */
export function jsonNumber(value: unknown): number | null {
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/** A request body with every quantity field widened to what `jsonNumber` can produce. */
type Wire<T, K extends string> = { [P in keyof T]: P extends K ? number | null : T[P] };
type ListBody = Omit<ListRequest, 'items' | 'on_hand'> & {
	items: Wire<ListRequest['items'][number], 'servings'>[];
	on_hand?: Wire<QtyLineIn, 'qty'>[];
};
type QuoteBody = Omit<QuoteRequest, 'lines'> & { lines: Wire<QtyLineIn, 'qty'>[] };

export function postList(req: ListRequest, options: RequestOptions = {}): Promise<ListResponse> {
	const body: ListBody = {
		items: req.items.map((item) => ({ recipe_id: item.recipe_id, servings: jsonNumber(item.servings) }))
	};
	if (req.on_hand !== undefined) {
		body.on_hand = req.on_hand.map((line) => ({ ingredient_id: line.ingredient_id, qty: jsonNumber(line.qty) }));
	}
	if (req.include_optional !== undefined) body.include_optional = req.include_optional;
	return request<ListResponse>('POST', '/api/list', body, options);
}

export function postQuote(req: QuoteRequest, options: RequestOptions = {}): Promise<QuoteResponse> {
	const body: QuoteBody = {
		lines: req.lines.map((line) => ({ ingredient_id: line.ingredient_id, qty: jsonNumber(line.qty) })),
		store_ids: req.store_ids.map((id) => String(id))
	};
	if (req.include_loyalty !== undefined) body.include_loyalty = req.include_loyalty;
	return request<QuoteResponse>('POST', '/api/quote', body, options);
}

export function postPlanSuggest(req: PlanSuggestRequest, options: RequestOptions = {}): Promise<PlanResponse> {
	const body: PlanSuggestRequest = {};
	if (req.days !== undefined) body.days = req.days;
	if (req.slots !== undefined) body.slots = req.slots;
	if (req.people !== undefined) body.people = req.people;
	if (req.seed !== undefined) body.seed = req.seed;
	if (req.exclude_tags !== undefined) body.exclude_tags = [...req.exclude_tags];
	if (req.exclude_ingredients !== undefined) body.exclude_ingredients = [...req.exclude_ingredients];
	if (req.red_meat_g_per_person_week !== undefined) body.red_meat_g_per_person_week = req.red_meat_g_per_person_week;
	if (req.no_repeat_days !== undefined) body.no_repeat_days = req.no_repeat_days;
	if (req.weekly_budget !== undefined) body.weekly_budget = req.weekly_budget;
	return request<PlanResponse>('POST', '/api/plan/suggest', body, options);
}

/** Copies only the five known slot keys of a plan day's meals. */
function pickMeals(meals: PlanDayIO['meals']): PlanDayIO['meals'] {
	const out: PlanDayIO['meals'] = {};
	for (const slot of SLOTS) {
		const value = meals[slot];
		if (value !== undefined) out[slot] = value;
	}
	return out;
}

export function postPlanCheck(req: PlanCheckRequest, options: RequestOptions = {}): Promise<PlanCheckResponse> {
	const body: PlanCheckRequest = {
		days: req.days.map((day) => ({ index: day.index, meals: pickMeals(day.meals) }))
	};
	if (req.people !== undefined) body.people = req.people;
	if (req.red_meat_g_per_person_week !== undefined) body.red_meat_g_per_person_week = req.red_meat_g_per_person_week;
	if (req.no_repeat_days !== undefined) body.no_repeat_days = req.no_repeat_days;
	if (req.weekly_budget !== undefined) body.weekly_budget = req.weekly_budget;
	return request<PlanCheckResponse>('POST', '/api/plan/check', body, options);
}

/** All endpoints in one object, for callers that prefer `api.getMeta()`. */
export const api = {
	getHealth,
	getMeta,
	getStores,
	getIngredients,
	getRecipes,
	getRecipe,
	getIngredientHistory,
	postList,
	postQuote,
	postPlanSuggest,
	postPlanCheck
} as const;
