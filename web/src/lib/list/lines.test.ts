// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { ListLineOut } from '../api/types';
import {
	buildQuoteRequest,
	isBought,
	isPantryLike,
	lineChoices,
	lineKind,
	listSections,
	onHandForList,
	quoteLines,
	toggleId
} from './lines';

function line(id: string, qty: number, pantry = false, group = 'zoldseg_gyumolcs'): ListLineOut {
	return { ingredient_id: id, name_hu: id, qty, unit: 'kg', list_group: group, pantry, recipe_ids: ['minta-recept'] };
}

const LINES: ListLineOut[] = [
	line('repa', 0.5),
	line('voroshagyma', 0.2),
	line('so', 0.01, true, 'fuszer_olaj'),
	line('napraforgoolaj', 0.05, true, 'fuszer_olaj'),
	line('rizs', 0.4, false, 'szaraz_tartos')
];

describe('lineKind', () => {
	it('classifies every case', () => {
		const choices = lineChoices(['rizs'], ['napraforgoolaj'], []);
		expect(lineKind(line('repa', 1), choices)).toBe('buy');
		expect(lineKind(line('rizs', 1), choices)).toBe('removed');
		expect(lineKind(line('so', 1, true), choices)).toBe('pantry_at_home');
		expect(lineKind(line('napraforgoolaj', 1, true), choices)).toBe('pantry_missing');
	});

	it('a removed pantry line is removed', () => {
		expect(lineKind(line('so', 1, true), lineChoices(['so'], ['so'], []))).toBe('removed');
	});

	it('"nincs otthon" on a non-pantry line changes nothing', () => {
		expect(lineKind(line('repa', 1), lineChoices([], ['repa'], []))).toBe('buy');
	});

	it('an on-hand entry without a quantity ("enough at home") makes a line pantry-like', () => {
		const choices = lineChoices([], [], [
			{ ingredientId: 'repa', qty: null },
			{ ingredientId: 'rizs', qty: 0.2 }
		]);
		expect(isPantryLike(line('repa', 1), choices)).toBe(true);
		expect(lineKind(line('repa', 1), choices)).toBe('pantry_at_home');
		// A quantity is subtracted by the server instead.
		expect(lineKind(line('rizs', 1), choices)).toBe('buy');
		expect(lineKind(line('repa', 1), lineChoices([], ['repa'], [{ ingredientId: 'repa', qty: null }]))).toBe(
			'pantry_missing'
		);
	});

	it('isBought is true exactly for "buy" and "pantry_missing"', () => {
		const choices = lineChoices(['rizs'], ['napraforgoolaj'], []);
		expect(LINES.filter((l) => isBought(l, choices)).map((l) => l.ingredient_id)).toEqual([
			'repa',
			'voroshagyma',
			'napraforgoolaj'
		]);
	});
});

describe('listSections', () => {
	it('splits into buy, pantry and removed, keeping the list order', () => {
		const sections = listSections(LINES, lineChoices(['voroshagyma'], ['napraforgoolaj'], []));
		expect(sections.buy.map((l) => l.ingredient_id)).toEqual(['repa', 'rizs']);
		expect(sections.pantry.map((l) => l.ingredient_id)).toEqual(['so', 'napraforgoolaj']);
		expect(sections.removed.map((l) => l.ingredient_id)).toEqual(['voroshagyma']);
	});
});

describe('quoteLines', () => {
	it('sends the bought lines only: no removed line, no pantry line unless it is "nincs otthon"', () => {
		const result = quoteLines(LINES, lineChoices(['rizs'], ['napraforgoolaj'], []));
		expect(result).toEqual({
			lines: [
				{ ingredient_id: 'repa', qty: 0.5 },
				{ ingredient_id: 'voroshagyma', qty: 0.2 },
				{ ingredient_id: 'napraforgoolaj', qty: 0.05 }
			],
			skipped: []
		});
	});

	it('leaves out every pantry line by default', () => {
		const result = quoteLines(LINES, lineChoices([], [], []));
		expect(result.lines.map((l) => l.ingredient_id)).toEqual(['repa', 'voroshagyma', 'rizs']);
	});

	it('sends each ingredient once', () => {
		const result = quoteLines([line('repa', 0.5), line('repa', 0.7)], lineChoices([], [], []));
		expect(result.lines).toEqual([{ ingredient_id: 'repa', qty: 0.5 }]);
	});

	it('skips quantities outside 0 < qty <= 1000 and invalid ids, and reports them', () => {
		const result = quoteLines(
			[line('nulla', 0), line('negativ', -1), line('sok', 1000.5), line('nan', Number.NaN), line('Rossz-ID', 1), line('ok', 1000)],
			lineChoices([], [], [])
		);
		expect(result.lines).toEqual([{ ingredient_id: 'ok', qty: 1000 }]);
		expect(result.skipped).toEqual(['nulla', 'negativ', 'sok', 'nan', 'Rossz-ID']);
	});

	it('caps the quote at 200 lines and reports the rest', () => {
		const many = Array.from({ length: 205 }, (_, i) => line(`tetel_${String(i).padStart(3, '0')}`, 1));
		const result = quoteLines(many, lineChoices([], [], []));
		expect(result.lines).toHaveLength(200);
		expect(result.skipped).toEqual(['tetel_200', 'tetel_201', 'tetel_202', 'tetel_203', 'tetel_204']);
	});
});

describe('buildQuoteRequest', () => {
	const lines = [{ ingredient_id: 'repa', qty: 0.5 }];

	it('builds the body from ingredient ids, quantities and store ids only', () => {
		const leaky = [{ ingredient_id: 'repa', qty: 0.5, lat: 47.5, lon: 19.05 }];
		const request = buildQuoteRequest(leaky, ['synthetic-lidl-1', 'synthetic-aldi-1']);
		expect(request).toEqual({
			lines: [{ ingredient_id: 'repa', qty: 0.5 }],
			store_ids: ['synthetic-lidl-1', 'synthetic-aldi-1'],
			include_loyalty: false
		});
		expect(JSON.stringify(request)).not.toMatch(/lat|lon|47\.5|19\.05/);
	});

	it('is null without lines or without stores', () => {
		expect(buildQuoteRequest([], ['synthetic-lidl-1'])).toBeNull();
		expect(buildQuoteRequest(lines, [])).toBeNull();
		expect(buildQuoteRequest(lines, ['bad id!'])).toBeNull();
	});

	it('de-duplicates store ids, drops invalid ones and keeps at most 25 in the given order', () => {
		const ids = ['s-1', 's-1', 'bad id', ...Array.from({ length: 30 }, (_, i) => `s-${i + 2}`)];
		const request = buildQuoteRequest(lines, ids);
		expect(request?.store_ids).toHaveLength(25);
		expect(request?.store_ids.slice(0, 3)).toEqual(['s-1', 's-2', 's-3']);
		expect(new Set(request?.store_ids).size).toBe(25);
	});
});

describe('onHandForList', () => {
	it('sends only entries with a valid quantity, once each, at most 200', () => {
		expect(
			onHandForList([
				{ ingredientId: 'liszt', qty: 1 },
				{ ingredientId: 'so', qty: null },
				{ ingredientId: 'liszt', qty: 2 },
				{ ingredientId: 'cukor', qty: 0 },
				{ ingredientId: 'tej', qty: 1001 },
				{ ingredientId: 'BAD', qty: 1 }
			])
		).toEqual([{ ingredient_id: 'liszt', qty: 1 }]);
		const many = Array.from({ length: 210 }, (_, i) => ({ ingredientId: `t_${i}`, qty: 1 }));
		expect(onHandForList(many)).toHaveLength(200);
	});
});

describe('toggleId', () => {
	it('adds once and removes, without changing the input', () => {
		const ids = ['a', 'b'];
		expect(toggleId(ids, 'c', true)).toEqual(['a', 'b', 'c']);
		expect(toggleId(ids, 'a', true)).toEqual(['b', 'a']);
		expect(toggleId(ids, 'a', false)).toEqual(['b']);
		expect(toggleId(ids, 'x', false)).toEqual(['a', 'b']);
		expect(ids).toEqual(['a', 'b']);
	});
});
