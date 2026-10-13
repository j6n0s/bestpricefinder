import { describe, expect, it } from 'vitest';
import { MOCK_DATA_DATE, MOCK_STORES, handleMockApi } from './api';

describe('synthetic mock API', () => {
	it('answers every GET endpoint of the contract', () => {
		for (const path of [
			'/api/health',
			'/api/meta',
			'/api/stores',
			'/api/ingredients',
			'/api/recipes',
			'/api/recipes?slot=ebed&q=lencse',
			'/api/recipes/minta-lencsefozelek',
			'/api/ingredients/voros_lencse/history?days=30'
		]) {
			expect(handleMockApi('GET', path).status, path).toBe(200);
		}
	});

	it('answers every POST endpoint of the contract', () => {
		const bodies: Record<string, unknown> = {
			'/api/list': { items: [{ recipe_id: 'minta-lencsefozelek', servings: 2 }] },
			'/api/quote': { lines: [{ ingredient_id: 'voros_lencse', qty: 0.4 }], store_ids: ['synthetic-lidl-1'] },
			'/api/plan/suggest': { days: 3, slots: 5 },
			'/api/plan/check': { days: [{ index: 0, meals: {} }] }
		};
		for (const [path, body] of Object.entries(bodies)) {
			expect(handleMockApi('POST', path, JSON.stringify(body)).status, path).toBe(200);
		}
	});

	it('behaves like the real API on bad requests', () => {
		expect(handleMockApi('GET', '/api/nope')).toEqual({ status: 404, body: { error: 'not_found', fields: [] } });
		expect(handleMockApi('POST', '/api/meta').status).toBe(405);
		expect(handleMockApi('GET', '/api/quote').status).toBe(405);
		expect(handleMockApi('GET', '/api/recipes/unknown').status).toBe(404);
		expect(handleMockApi('POST', '/api/quote', '{bad').status).toBe(422);
		expect(handleMockApi('POST', '/api/quote', JSON.stringify({ lines: [{ ingredient_id: 'x', qty: 1 }], store_ids: ['nope'] }))).toEqual({
			status: 422,
			body: { error: 'invalid_request', fields: ['store_ids.0'] }
		});
	});

	it('rejects coordinates in a quote, like extra="forbid" on the server', () => {
		const result = handleMockApi(
			'POST',
			'/api/quote',
			JSON.stringify({ lines: [{ ingredient_id: 'x', qty: 1 }], store_ids: ['synthetic-lidl-1'], lat: 47.5, lon: 19 })
		);
		expect(result).toEqual({ status: 422, body: { error: 'invalid_request', fields: ['lat', 'lon'] } });
	});

	it('ranks stores with competition ranks (ties share a rank)', () => {
		const result = handleMockApi(
			'POST',
			'/api/quote',
			JSON.stringify({
				lines: [{ ingredient_id: 'voros_lencse', qty: 1 }],
				store_ids: ['synthetic-lidl-1', 'synthetic-aldi-1', 'synthetic-lidl-2']
			})
		);
		const ranks = (result.body as { ranking: { store_id: string; rank: number }[] }).ranking.map((r) => r.rank);
		expect(ranks).toEqual([1, 2, 3]);
	});

	it('is clearly synthetic', () => {
		for (const store of MOCK_STORES) expect(store.id).toMatch(/^synthetic-/);
		const meta = handleMockApi('GET', '/api/meta').body as { data_date: string };
		expect(meta.data_date).toBe(MOCK_DATA_DATE);
	});
});
