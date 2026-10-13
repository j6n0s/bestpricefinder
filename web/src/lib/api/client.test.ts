import { afterEach, describe, expect, it, vi } from 'vitest';
import { errorMessageKey } from '../errors';
import {
	API_TIMEOUT_MS,
	ApiError,
	errorFromResponse,
	getHealth,
	getIngredientHistory,
	getMeta,
	getRecipe,
	getRecipes,
	isApiError,
	normaliseRecipeQuery,
	parseRetryAfter,
	postList,
	postPlanCheck,
	postPlanSuggest,
	postQuote
} from './client';
import type { QuoteRequest } from './types';

interface Call {
	url: string;
	init: RequestInit;
}

function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json; charset=utf-8', ...headers }
	});
}

/** A fetch double that records calls and answers with `respond`. */
function fakeFetch(respond: (call: Call) => Response | Promise<Response>): { fetch: typeof fetch; calls: Call[] } {
	const calls: Call[] = [];
	const fn = (async (input: RequestInfo | URL, init?: RequestInit) => {
		const call = { url: String(input), init: init ?? {} };
		calls.push(call);
		return respond(call);
	}) as typeof fetch;
	return { fetch: fn, calls };
}

/** A fetch double that never answers until its signal aborts (like a hung server). */
function hangingFetch(): typeof fetch {
	return ((_input: RequestInfo | URL, init?: RequestInit) =>
		new Promise<Response>((_resolve, reject) => {
			init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
		})) as typeof fetch;
}

afterEach(() => {
	vi.useRealTimers();
	vi.unstubAllGlobals();
});

describe('requests', () => {
	it('GETs JSON with no cookies, no referrer and no redirects', async () => {
		const { fetch, calls } = fakeFetch(() => json({ data_date: '2026-10-13' }));
		await getMeta({ fetch });
		expect(calls).toHaveLength(1);
		const [call] = calls;
		expect(call?.url).toBe('/api/meta');
		expect(call?.init.method).toBe('GET');
		expect(call?.init.credentials).toBe('omit');
		expect(call?.init.redirect).toBe('error');
		expect(call?.init.referrerPolicy).toBe('no-referrer');
		expect(call?.init.headers).toEqual({ Accept: 'application/json' });
		expect(call?.init.body).toBeUndefined();
	});

	it('POSTs a JSON body with the JSON content type', async () => {
		const { fetch, calls } = fakeFetch(() => json({ lines: [] }));
		await postList({ items: [{ recipe_id: 'lencsefozelek', servings: 4 }] }, { fetch });
		expect(calls[0]?.init.method).toBe('POST');
		expect(calls[0]?.init.headers).toEqual({ Accept: 'application/json', 'Content-Type': 'application/json' });
		expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ items: [{ recipe_id: 'lencsefozelek', servings: 4 }] });
	});

	it('builds recipe queries and encodes path ids', async () => {
		const { fetch, calls } = fakeFetch(() => json({ recipes: [] }));
		await getRecipes({ slot: 'ebed', tag: 'hal', q: '  lencse  ' }, { fetch });
		await getRecipes({}, { fetch });
		await getRecipe('a/b?c', { fetch });
		await getIngredientHistory('lencse', { chain: 'lidl', days: 30.7 }, { fetch });
		expect(calls.map((c) => c.url)).toEqual([
			'/api/recipes?slot=ebed&tag=hal&q=lencse',
			'/api/recipes',
			'/api/recipes/a%2Fb%3Fc',
			'/api/ingredients/lencse/history?chain=lidl&days=30'
		]);
	});

	it('normalises the recipe search text to 2-40 characters', () => {
		expect(normaliseRecipeQuery(undefined)).toBeNull();
		expect(normaliseRecipeQuery(' a ')).toBeNull();
		expect(normaliseRecipeQuery('ab')).toBe('ab');
		expect(normaliseRecipeQuery('x'.repeat(50))).toBe('x'.repeat(40));
	});
});

describe('privacy: request bodies carry only known fields', () => {
	it('/api/quote never sends coordinates or anything else that is not in the contract', async () => {
		const { fetch, calls } = fakeFetch(() => json({ stores: [] }));
		const leaky = {
			lines: [{ ingredient_id: 'lencse', qty: 0.4, lat: 47.5 }],
			store_ids: ['lidl-1'],
			lat: 47.5,
			lon: 19.05,
			origin: { lat: 47.5, lon: 19.05 }
		} as unknown as QuoteRequest;
		await postQuote(leaky, { fetch });
		const body = String(calls[0]?.init.body);
		expect(JSON.parse(body)).toEqual({ lines: [{ ingredient_id: 'lencse', qty: 0.4 }], store_ids: ['lidl-1'] });
		expect(body).not.toMatch(/lat|lon|origin|47\.5|19\.05/);
	});

	it('keeps include_loyalty when given', async () => {
		const { fetch, calls } = fakeFetch(() => json({}));
		await postQuote({ lines: [{ ingredient_id: 'x1', qty: 1 }], store_ids: ['s'], include_loyalty: true }, { fetch });
		expect(JSON.parse(String(calls[0]?.init.body))).toEqual({
			lines: [{ ingredient_id: 'x1', qty: 1 }],
			store_ids: ['s'],
			include_loyalty: true
		});
	});

	it('plan requests copy only contract fields and known slots', async () => {
		const { fetch, calls } = fakeFetch(() => json({ checks: [] }));
		await postPlanSuggest({ days: 7, slots: 5, exclude_tags: ['hal'], extra: 1 } as never, { fetch });
		await postPlanCheck(
			{ days: [{ index: 0, meals: { ebed: 'a1', brunch: 'x' } as never }], people: 2, no_repeat_days: 3, home: 'x' } as never,
			{ fetch }
		);
		expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ days: 7, slots: 5, exclude_tags: ['hal'] });
		expect(JSON.parse(String(calls[1]?.init.body))).toEqual({
			days: [{ index: 0, meals: { ebed: 'a1' } }],
			people: 2,
			no_repeat_days: 3
		});
	});

	it('/api/list keeps on_hand and include_optional only', async () => {
		const { fetch, calls } = fakeFetch(() => json({ lines: [] }));
		await postList(
			{
				items: [{ recipe_id: 'r1', servings: 2, note: 'x' } as never],
				on_hand: [{ ingredient_id: 'liszt', qty: 1, where: 'kamra' } as never],
				include_optional: false
			},
			{ fetch }
		);
		expect(JSON.parse(String(calls[0]?.init.body))).toEqual({
			items: [{ recipe_id: 'r1', servings: 2 }],
			on_hand: [{ ingredient_id: 'liszt', qty: 1 }],
			include_optional: false
		});
	});
});

describe('errors', () => {
	it('maps the {error, fields} body of a 422', async () => {
		const { fetch } = fakeFetch(() => json({ error: 'invalid_request', fields: ['store_ids.0', 3] }, 422));
		const error = await postQuote({ lines: [{ ingredient_id: 'x1', qty: 1 }], store_ids: ['s'] }, { fetch }).catch(
			(e: unknown) => e
		);
		expect(isApiError(error)).toBe(true);
		expect(error).toMatchObject({ kind: 'http', status: 422, code: 'invalid_request', fields: ['store_ids.0'] });
		expect(errorMessageKey(error)).toBe('core.error_invalid_request');
	});

	it('reads Retry-After on 429', async () => {
		const { fetch } = fakeFetch(() => json({ error: 'rate_limited', fields: [] }, 429, { 'retry-after': '12' }));
		const error = (await getMeta({ fetch }).catch((e: unknown) => e)) as ApiError;
		expect(error).toMatchObject({ code: 'rate_limited', retryAfterS: 12 });
		expect(errorMessageKey(error)).toBe('core.error_rate_limited');
	});

	it('derives the code from the status when the body is not JSON or not the contract shape', async () => {
		const html = fakeFetch(() => new Response('<h1>Bad gateway</h1>', { status: 404, headers: { 'content-type': 'text/html' } }));
		await expect(getRecipe('nope', { fetch: html.fetch })).rejects.toMatchObject({ kind: 'http', status: 404, code: 'not_found' });
		const odd = fakeFetch(() => json({ error: 'something_new' }, 503));
		await expect(getMeta({ fetch: odd.fetch })).rejects.toMatchObject({ status: 503, code: 'no_data', fields: [] });
		const unknownStatus = fakeFetch(() => json({}, 418));
		await expect(getMeta({ fetch: unknownStatus.fetch })).rejects.toMatchObject({ status: 418, code: null });
	});

	it('treats a 2xx answer that is not a JSON object as invalid', async () => {
		for (const response of [
			new Response('ok', { status: 200, headers: { 'content-type': 'text/plain' } }),
			new Response('{bad json', { status: 200, headers: { 'content-type': 'application/json' } }),
			json([1, 2, 3]),
			json(null)
		]) {
			const { fetch } = fakeFetch(() => response);
			await expect(getMeta({ fetch })).rejects.toMatchObject({ kind: 'invalid_response', status: 200 });
		}
	});

	it('returns the body of a 503 from /api/health instead of throwing', async () => {
		const { fetch } = fakeFetch(() => json({ status: 'down', db: false, data_date: null }, 503));
		await expect(getHealth({ fetch })).resolves.toEqual({ status: 'down', db: false, data_date: null });
	});

	it('reports network failures as offline when the browser is offline', async () => {
		const failing = fakeFetch(() => {
			throw new TypeError('Failed to fetch');
		});
		vi.stubGlobal('navigator', { onLine: false });
		await expect(getMeta({ fetch: failing.fetch })).rejects.toMatchObject({ kind: 'offline', status: null });
		vi.stubGlobal('navigator', { onLine: true });
		const error = await getMeta({ fetch: failing.fetch }).catch((e: unknown) => e);
		expect(error).toMatchObject({ kind: 'network' });
		expect(errorMessageKey(error)).toBe('core.error_network');
	});

	it('times out after 15 s', async () => {
		vi.useFakeTimers();
		const pending = getMeta({ fetch: hangingFetch() }).catch((e: unknown) => e);
		await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS - 1);
		let settled = false;
		void pending.then(() => {
			settled = true;
		});
		await Promise.resolve();
		expect(settled).toBe(false);
		await vi.advanceTimersByTimeAsync(1);
		const error = await pending;
		expect(error).toMatchObject({ kind: 'timeout' });
		expect(errorMessageKey(error)).toBe('core.error_timeout');
	});

	it('honours a custom timeout', async () => {
		await expect(getMeta({ fetch: hangingFetch(), timeoutMs: 5 })).rejects.toMatchObject({ kind: 'timeout' });
	});

	it('distinguishes a caller abort from a timeout', async () => {
		const controller = new AbortController();
		const pending = getMeta({ fetch: hangingFetch(), signal: controller.signal });
		controller.abort();
		await expect(pending).rejects.toMatchObject({ kind: 'aborted' });
	});

	it('does not even start when the signal is already aborted', async () => {
		const { fetch, calls } = fakeFetch(() => json({}));
		const controller = new AbortController();
		controller.abort();
		await expect(getMeta({ fetch, signal: controller.signal })).rejects.toMatchObject({ kind: 'aborted' });
		expect(calls).toHaveLength(0);
	});

	it('errors thrown while reading the body are classified too', async () => {
		const broken = fakeFetch(
			() =>
				({
					ok: true,
					status: 200,
					headers: new Headers({ 'content-type': 'application/json' }),
					text: () => Promise.reject(new TypeError('network lost'))
				}) as unknown as Response
		);
		await expect(getMeta({ fetch: broken.fetch })).rejects.toMatchObject({ kind: 'network' });
	});
});

describe('helpers', () => {
	it('parseRetryAfter accepts delta-seconds only', () => {
		expect(parseRetryAfter('30')).toBe(30);
		expect(parseRetryAfter(' 5 ')).toBe(5);
		expect(parseRetryAfter(null)).toBeNull();
		expect(parseRetryAfter('Wed, 21 Oct 2026 07:28:00 GMT')).toBeNull();
		expect(parseRetryAfter('-1')).toBeNull();
	});

	it('errorFromResponse ignores a malformed body', () => {
		expect(errorFromResponse(500, 'oops', null)).toMatchObject({ code: 'internal', fields: [] });
		expect(errorFromResponse(422, { fields: 'x' }, null)).toMatchObject({ code: 'invalid_request', fields: [] });
	});

	it('ApiError is an Error with a readable message', () => {
		const error = new ApiError({ kind: 'http', status: 404, code: 'not_found' });
		expect(error).toBeInstanceOf(Error);
		expect(error.name).toBe('ApiError');
		expect(error.message).toBe('http: not_found');
		expect(Object.isFrozen(error.fields)).toBe(true);
	});

	it('errorMessageKey covers non-API errors', () => {
		expect(errorMessageKey(new Error('x'))).toBe('core.error_generic');
		expect(errorMessageKey(new ApiError({ kind: 'http', status: 503, code: 'no_data' }))).toBe('core.error_no_data');
		expect(errorMessageKey(new ApiError({ kind: 'http', status: 404, code: 'not_found' }))).toBe('core.error_not_found');
		expect(errorMessageKey(new ApiError({ kind: 'http', status: 500, code: 'internal' }))).toBe('core.error_generic');
		expect(errorMessageKey(new ApiError({ kind: 'offline' }))).toBe('core.error_offline');
		expect(errorMessageKey(new ApiError({ kind: 'invalid_response' }))).toBe('core.error_invalid_response');
		expect(errorMessageKey(new ApiError({ kind: 'aborted' }))).toBe('core.error_generic');
	});
});
