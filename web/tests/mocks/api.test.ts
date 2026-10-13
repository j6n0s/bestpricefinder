import { describe, expect, it } from 'vitest';
import type { RecipeSummary, RuleCheckOut } from '../../src/lib/api/types';
import { MOCK_DATA_DATE, MOCK_RECIPES, MOCK_STORES, handleMockApi } from './api';

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

	it('rejects coordinates in a quote, like extra="forbid" on the server (an unknown root field is "body")', () => {
		const result = handleMockApi(
			'POST',
			'/api/quote',
			JSON.stringify({ lines: [{ ingredient_id: 'x', qty: 1 }], store_ids: ['synthetic-lidl-1'], lat: 47.5, lon: 19 })
		);
		expect(result).toEqual({ status: 422, body: { error: 'invalid_request', fields: ['body'] } });
	});

	it('accepts quantities only as JSON numbers, like contract v1.2', () => {
		const quote = (qty: unknown) =>
			handleMockApi('POST', '/api/quote', JSON.stringify({ lines: [{ ingredient_id: 'voros_lencse', qty }], store_ids: ['synthetic-lidl-1'] }));
		expect(quote(0.4).status).toBe(200);
		for (const qty of ['0.4', 0, -1, 1000.5, null]) {
			expect(quote(qty), JSON.stringify(qty)).toEqual({ status: 422, body: { error: 'invalid_request', fields: ['lines.0.qty'] } });
		}
		const list = (servings: unknown) =>
			handleMockApi('POST', '/api/list', JSON.stringify({ items: [{ recipe_id: 'minta-lencsefozelek', servings }] }));
		expect(list(2).status).toBe(200);
		for (const servings of ['2', 0, 101, null]) {
			expect(list(servings), JSON.stringify(servings)).toEqual({
				status: 422,
				body: { error: 'invalid_request', fields: ['items.0.servings'] }
			});
		}
	});

	it('/api/plan/check computes the weekly checks from the request', () => {
		const lencse = 'minta-lencsefozelek';
		const csirke = 'minta-csirke';
		const days = Array.from({ length: 9 }, (_, index) => ({
			index,
			meals: { reggeli: null, ebed: index % 2 === 0 ? lencse : csirke, vacsora: null }
		}));
		const result = handleMockApi('POST', '/api/plan/check', JSON.stringify({ days, people: 2, no_repeat_days: 2 }));
		expect(result.status).toBe(200);
		const checks = (result.body as { checks: RuleCheckOut[] }).checks;
		const of = (week: number, rule: string) => checks.find((check) => check.week === week && check.rule === rule);
		// Week 0 (7 days): lentils on days 0, 2, 4, 6 -> 4 legumes and 4 meat-free days, no fish, no repeat
		// within 2 days. Week 1 (2 days): fewer than 4 days, so the count rules do not apply.
		expect(checks.filter((check) => check.week === 0).map((check) => check.rule)).toEqual([
			'fish',
			'legume',
			'meat_free_day',
			'red_meat',
			'potato',
			'sweets',
			'variety'
		]);
		expect(of(0, 'fish')).toEqual({ week: 0, rule: 'fish', ok: false, value: '0 hal', limit: '≥ 1' });
		expect(of(0, 'legume')).toMatchObject({ ok: true, value: '4 hüvelyes' });
		expect(of(0, 'meat_free_day')).toMatchObject({ ok: true, value: '4 húsmentes nap' });
		expect(of(0, 'variety')).toEqual({ week: 0, rule: 'variety', ok: true, value: '0 ismétlés', limit: '0 ismétlés 2 napon belül' });
		expect(of(1, 'fish')).toMatchObject({ ok: true, value: 'n/a' });
		expect(of(0, 'budget')).toBeUndefined();

		// The same lentils every day breaks the variety rule; a budget adds the budget check.
		const daily = Array.from({ length: 7 }, (_, index) => ({ index, meals: { ebed: lencse } }));
		const again = handleMockApi('POST', '/api/plan/check', JSON.stringify({ days: daily, weekly_budget: 2000 }));
		const againChecks = (again.body as { checks: RuleCheckOut[] }).checks;
		expect(againChecks.find((c) => c.rule === 'variety')).toMatchObject({ ok: false, value: '6 ismétlés' });
		expect(againChecks.find((c) => c.rule === 'budget')).toEqual({
			week: 0,
			rule: 'budget',
			ok: false,
			value: '4375 Ft',
			limit: '≤ 2000 Ft'
		});
	});

	it('/api/plan/check uses the recipes a spec passes in, with their tags', () => {
		const hal = { ...MOCK_RECIPES[0], id: 'minta-spec-hal', tags: ['hal'] } as RecipeSummary;
		const days = Array.from({ length: 4 }, (_, index) => ({ index, meals: { ebed: index === 0 ? hal.id : null } }));
		const body = JSON.stringify({ days });
		expect(handleMockApi('POST', '/api/plan/check', body).body).toEqual({
			error: 'invalid_request',
			fields: ['days.0.meals.ebed']
		});
		const result = handleMockApi('POST', '/api/plan/check', body, { recipes: [hal] });
		expect((result.body as { checks: RuleCheckOut[] }).checks.find((c) => c.rule === 'fish')).toMatchObject({ ok: true, value: '1 hal' });
	});

	it('/api/plan/check rejects unknown recipes and malformed plans with the field path', () => {
		const check = (body: unknown) => handleMockApi('POST', '/api/plan/check', JSON.stringify(body));
		expect(check({ days: [{ index: 0, meals: { ebed: 'minta-ismeretlen' } }] })).toEqual({
			status: 422,
			body: { error: 'invalid_request', fields: ['days.0.meals.ebed'] }
		});
		expect(check({ days: [] }).body).toEqual({ error: 'invalid_request', fields: ['days'] });
		expect(check({ days: [{ index: 31, meals: {} }] }).body).toEqual({ error: 'invalid_request', fields: ['days.0.index'] });
		expect(check({ days: [{ index: 0, meals: { brunch: null } }] }).body).toEqual({ error: 'invalid_request', fields: ['days.0.meals'] });
		expect(check({ days: [{ index: 0, meals: {} }], people: 13 }).body).toEqual({ error: 'invalid_request', fields: ['people'] });
		expect(check({ days: [{ index: 0, meals: {} }], lat: 47.5 }).body).toEqual({ error: 'invalid_request', fields: ['body'] });
	});

	it('ranks stores with competition ranks (ties share a rank)', () => {
		const result = handleMockApi(
			'POST',
			'/api/quote',
			JSON.stringify({
				lines: [{ ingredient_id: 'voros_lencse', qty: 1 }],
				store_ids: ['synthetic-spar-1', 'synthetic-lidl-1', 'synthetic-aldi-1']
			})
		);
		const ranking = (result.body as { ranking: { store_id: string; rank: number }[] }).ranking;
		expect(ranking.map((r) => [r.store_id, r.rank])).toEqual([
			['synthetic-aldi-1', 1],
			['synthetic-lidl-1', 1],
			['synthetic-spar-1', 3]
		]);
	});

	it('is clearly synthetic', () => {
		for (const store of MOCK_STORES) expect(store.id).toMatch(/^synthetic-/);
		const meta = handleMockApi('GET', '/api/meta').body as { data_date: string };
		expect(meta.data_date).toBe(MOCK_DATA_DATE);
	});
});
