// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import { RECIPE_TAGS, type IngredientOut } from '../api/types';
import { translate } from '../i18n/messages';
import {
	EXCLUDABLE_TAGS,
	byName,
	excludableTagKey,
	foldText,
	otherExcludedTags,
	pantryIngredients,
	searchIngredients
} from './settings';

function ingredient(id: string, name: string, pantry = false): IngredientOut {
	return { id, name_hu: name, list_group: 'egyeb', unit: 'kg', piece_weight_kg: null, pantry, priced_by: 'gvh', tags: [] };
}

const INGREDIENTS = [
	ingredient('voroshagyma', 'vöröshagyma'),
	ingredient('so', 'só', true),
	ingredient('olivaolaj', 'olívaolaj', true),
	ingredient('almaecet', 'almaecet', true),
	ingredient('alma', 'alma'),
	ingredient('oregano', 'oregánó', true),
	ingredient('csirkemell', 'csirkemellfilé'),
	ingredient('zab', 'zabpehely')
];

describe('EXCLUDABLE_TAGS', () => {
	it('are recipe tags with a label in both languages', () => {
		for (const tag of EXCLUDABLE_TAGS) {
			expect(RECIPE_TAGS).toContain(tag);
			for (const lang of ['hu', 'en'] as const) {
				const label = translate(lang, excludableTagKey(tag));
				expect(label.length).toBeGreaterThan(0);
				expect(label).not.toMatch(/^list\./);
			}
		}
		expect(new Set(EXCLUDABLE_TAGS).size).toBe(EXCLUDABLE_TAGS.length);
	});

	it('finds stored tags this screen does not offer', () => {
		expect(otherExcludedTags(['hal', 'gyors', 'olcso'])).toEqual(['gyors', 'olcso']);
		expect(otherExcludedTags([])).toEqual([]);
	});
});

describe('foldText', () => {
	it('drops accents, case and extra spaces', () => {
		expect(foldText('  Vöröshagyma  ')).toBe('voroshagyma');
		expect(foldText('OLÍVA   olaj')).toBe('oliva olaj');
		expect(foldText('őŐűŰ')).toBe('oouu');
	});
});

describe('byName / pantryIngredients', () => {
	it('sorts by Hungarian name and lists only pantry staples', () => {
		expect(pantryIngredients(INGREDIENTS).map((i) => i.id)).toEqual(['almaecet', 'olivaolaj', 'oregano', 'so']);
		expect(byName(INGREDIENTS).map((i) => i.id)[0]).toBe('alma');
	});

	it('leaves out tap water, which is never bought', () => {
		const withWater = [...INGREDIENTS, ingredient('viz', 'víz', true)];
		expect(pantryIngredients(withWater).map((i) => i.id)).not.toContain('viz');
		expect(pantryIngredients(withWater)).toHaveLength(4);
	});
});

describe('searchIngredients', () => {
	it('matches anywhere in the name, ignoring accents and case', () => {
		expect(searchIngredients(INGREDIENTS, 'OLAJ', new Set()).map((i) => i.id)).toEqual(['olivaolaj']);
		expect(searchIngredients(INGREDIENTS, 'voros', new Set()).map((i) => i.id)).toEqual(['voroshagyma']);
		expect(searchIngredients(INGREDIENTS, 'alma', new Set()).map((i) => i.id)).toEqual(['alma', 'almaecet']);
	});

	it('needs at least 2 characters', () => {
		expect(searchIngredients(INGREDIENTS, 'a', new Set())).toEqual([]);
		expect(searchIngredients(INGREDIENTS, '   ', new Set())).toEqual([]);
	});

	it('leaves out what is already excluded and caps the results', () => {
		expect(searchIngredients(INGREDIENTS, 'alma', new Set(['alma'])).map((i) => i.id)).toEqual(['almaecet']);
		expect(searchIngredients(INGREDIENTS, 'a', new Set(), 1)).toEqual([]);
		expect(searchIngredients(INGREDIENTS, 'al', new Set(), 1)).toHaveLength(1);
		expect(searchIngredients(INGREDIENTS, 'al', new Set(), -1)).toEqual([]);
	});
});
