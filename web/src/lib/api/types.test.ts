/**
 * The runtime constants in types.ts that the generated types cannot carry (id patterns, list and number
 * bounds) must match the OpenAPI document the types are generated from (docs/openapi.json).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { ID_PATTERNS, LIMITS } from './types';

type Json = Record<string, unknown>;
const doc = JSON.parse(readFileSync(fileURLToPath(new URL('../../../../docs/openapi.json', import.meta.url)), 'utf8')) as Json;
const schemas = (doc.components as Json).schemas as Record<string, Json>;

function prop(model: string, field: string): Json {
	const value = (schemas[model]?.properties as Record<string, Json> | undefined)?.[field];
	if (!value) throw new Error(`${model}.${field} is not in docs/openapi.json`);
	return value;
}

/** The non-null branch of an `anyOf: [X, {type: null}]`, or the schema itself. */
function nonNull(schema: Json): Json {
	const anyOf = schema.anyOf as Json[] | undefined;
	return anyOf?.find((branch) => branch.type !== 'null') ?? schema;
}

function queryParam(path: string, name: string): Json {
	const params = (((doc.paths as Json)[path] as Json).get as Json).parameters as Json[];
	const param = params.find((p) => p.name === name);
	if (!param) throw new Error(`${path} has no query parameter ${name}`);
	return nonNull(param.schema as Json);
}

describe('types.ts constants match docs/openapi.json', () => {
	it('id patterns', () => {
		expect(prop('IngredientOut', 'id').pattern).toBe(ID_PATTERNS.ingredient.source);
		expect(prop('RecipeSummary', 'id').pattern).toBe(ID_PATTERNS.recipe.source);
		expect(prop('StoreOut', 'id').pattern).toBe(ID_PATTERNS.store.source);
		expect(prop('ChainOut', 'slug').pattern).toBe(ID_PATTERNS.chain.source);
		expect((prop('QuoteRequest', 'store_ids').items as Json).pattern).toBe(ID_PATTERNS.store.source);
		expect((prop('PlanSuggestRequest', 'exclude_ingredients').items as Json).pattern).toBe(ID_PATTERNS.ingredient.source);
	});

	it('list bounds', () => {
		expect(prop('ListRequest', 'items').maxItems).toBe(LIMITS.listItems);
		expect(prop('ListRequest', 'on_hand').maxItems).toBe(LIMITS.onHand);
		expect(prop('QuoteRequest', 'lines').maxItems).toBe(LIMITS.quoteLines);
		expect(prop('QuoteRequest', 'store_ids').maxItems).toBe(LIMITS.quoteStores);
		expect(prop('PlanCheckRequest', 'days').maxItems).toBe(LIMITS.planDaysMax);
		expect(prop('PlanSuggestRequest', 'exclude_tags').maxItems).toBe(LIMITS.excludeTagsMax);
		expect(prop('PlanSuggestRequest', 'exclude_ingredients').maxItems).toBe(LIMITS.excludeIngredientsMax);
	});

	it('number bounds', () => {
		expect(prop('PlanSuggestRequest', 'days').maximum).toBe(LIMITS.planDaysMax);
		expect(prop('PlanSuggestRequest', 'people')).toMatchObject({ minimum: LIMITS.peopleMin, maximum: LIMITS.peopleMax });
		expect(prop('PlanCheckRequest', 'people')).toMatchObject({ minimum: LIMITS.peopleMin, maximum: LIMITS.peopleMax });
		expect(prop('PlanSuggestRequest', 'red_meat_g_per_person_week').maximum).toBe(LIMITS.redMeatMaxG);
		expect(prop('PlanSuggestRequest', 'no_repeat_days').maximum).toBe(LIMITS.noRepeatDaysMax);
		expect(nonNull(prop('PlanSuggestRequest', 'weekly_budget')).maximum).toBe(LIMITS.weeklyBudgetMax);
		expect(queryParam('/api/recipes', 'q')).toMatchObject({ minLength: LIMITS.recipeQueryMin, maxLength: LIMITS.recipeQueryMax });
		expect(queryParam('/api/ingredients/{id}/history', 'days')).toMatchObject({
			minimum: LIMITS.historyDaysMin,
			maximum: LIMITS.historyDaysMax
		});
		// Quantity bounds live in the server's validator; the schema states them in the description only.
		expect(prop('QtyLineIn', 'qty').description).toContain(`<= ${LIMITS.qtyMax}`);
		expect(prop('ListItemIn', 'servings').description).toContain(`<= ${LIMITS.servingsMax}`);
	});
});
