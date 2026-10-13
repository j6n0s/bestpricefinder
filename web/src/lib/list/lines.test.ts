// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { ListLineOut } from '../api/types';
import {
	NEVER_BOUGHT,
	buildQuoteRequest,
	canBeBought,
	isBought,
	isIncludedExclusion,
	lineChoices,
	lineKind,
	listSections,
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
		const choices = lineChoices(['rizs'], ['napraforgoolaj']);
		expect(lineKind(line('repa', 1), choices)).toBe('buy');
		expect(lineKind(line('rizs', 1), choices)).toBe('removed');
		expect(lineKind(line('so', 1, true), choices)).toBe('pantry_at_home');
		expect(lineKind(line('napraforgoolaj', 1, true), choices)).toBe('pantry_missing');
	});

	it('a removed pantry line is removed', () => {
		expect(lineKind(line('so', 1, true), lineChoices(['so'], ['so']))).toBe('removed');
	});

	it('"nincs otthon" on a non-pantry line changes nothing', () => {
		expect(lineKind(line('repa', 1), lineChoices([], ['repa']))).toBe('buy');
	});

	it('isBought is true exactly for "buy" and "pantry_missing"', () => {
		const choices = lineChoices(['rizs'], ['napraforgoolaj']);
		expect(LINES.filter((l) => isBought(l, choices)).map((l) => l.ingredient_id)).toEqual([
			'repa',
			'voroshagyma',
			'napraforgoolaj'
		]);
	});
});

describe('excluded ingredients (settings) on the list', () => {
	const withEgg = [...LINES, line('tojas', 0.667, false, 'tejtermek_tojas')];

	it('an excluded ingredient is "excluded": not bought, not quoted', () => {
		const choices = lineChoices([], [], ['tojas']);
		expect(lineKind(line('tojas', 1), choices)).toBe('excluded');
		expect(isBought(line('tojas', 1), choices)).toBe(false);
		expect(quoteLines(withEgg, choices).lines.map((l) => l.ingredient_id)).toEqual(['repa', 'voroshagyma', 'rizs']);
		expect(listSections(withEgg, choices).excluded.map((l) => l.ingredient_id)).toEqual(['tojas']);
	});

	it('also an excluded pantry staple marked "nincs otthon"; one at home just stays at home', () => {
		const choices = lineChoices([], ['napraforgoolaj'], ['napraforgoolaj', 'so']);
		expect(lineKind(line('napraforgoolaj', 1, true), choices)).toBe('excluded');
		expect(quoteLines(LINES, choices).lines.map((l) => l.ingredient_id)).not.toContain('napraforgoolaj');
		expect(lineKind(line('so', 1, true), choices)).toBe('pantry_at_home');
		expect(lineKind(line('napraforgoolaj', 1, true), lineChoices([], ['napraforgoolaj'], ['napraforgoolaj'], ['napraforgoolaj']))).toBe(
			'pantry_missing'
		);
	});

	it('"mégis megveszem" puts it back on this list and into the quote', () => {
		const choices = lineChoices([], [], ['tojas'], ['tojas']);
		expect(lineKind(line('tojas', 1), choices)).toBe('buy');
		expect(isIncludedExclusion(line('tojas', 1), choices)).toBe(true);
		expect(quoteLines(withEgg, choices).lines.map((l) => l.ingredient_id)).toContain('tojas');
		expect(isIncludedExclusion(line('repa', 1), choices)).toBe(false);
	});

	it('an "included" id that is not excluded changes nothing, and removing wins', () => {
		expect(lineKind(line('repa', 1), lineChoices([], [], [], ['repa']))).toBe('buy');
		expect(lineKind(line('tojas', 1), lineChoices(['tojas'], [], ['tojas'], ['tojas']))).toBe('removed');
		expect(isIncludedExclusion(line('tojas', 1), lineChoices(['tojas'], [], ['tojas'], ['tojas']))).toBe(false);
	});
});

describe('tap water', () => {
	it('is never bought, even when marked "nincs otthon"', () => {
		expect(NEVER_BOUGHT.has('viz')).toBe(true);
		expect(canBeBought('viz')).toBe(false);
		expect(canBeBought('so')).toBe(true);
		const water = line('viz', 4.832, true, 'egyeb');
		const choices = lineChoices([], ['viz']);
		expect(lineKind(water, choices)).toBe('pantry_at_home');
		expect(quoteLines([...LINES, water], choices).lines.map((l) => l.ingredient_id)).not.toContain('viz');
		// Not even if a list ever sent it as a non-pantry line.
		expect(lineKind(line('viz', 1), lineChoices([], []))).toBe('pantry_at_home');
	});
});

describe('listSections', () => {
	it('splits into buy, pantry, excluded and removed, keeping the list order', () => {
		const sections = listSections(LINES, lineChoices(['voroshagyma'], ['napraforgoolaj'], ['rizs']));
		expect(sections.buy.map((l) => l.ingredient_id)).toEqual(['repa']);
		expect(sections.pantry.map((l) => l.ingredient_id)).toEqual(['so', 'napraforgoolaj']);
		expect(sections.excluded.map((l) => l.ingredient_id)).toEqual(['rizs']);
		expect(sections.removed.map((l) => l.ingredient_id)).toEqual(['voroshagyma']);
	});
});

describe('quoteLines', () => {
	it('sends the bought lines only: no removed line, no pantry line unless it is "nincs otthon"', () => {
		const result = quoteLines(LINES, lineChoices(['rizs'], ['napraforgoolaj']));
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
		const result = quoteLines(LINES, lineChoices([], []));
		expect(result.lines.map((l) => l.ingredient_id)).toEqual(['repa', 'voroshagyma', 'rizs']);
	});

	it('sends each ingredient once', () => {
		const result = quoteLines([line('repa', 0.5), line('repa', 0.7)], lineChoices([], []));
		expect(result.lines).toEqual([{ ingredient_id: 'repa', qty: 0.5 }]);
	});

	it('skips quantities outside 0 < qty <= 1000 and invalid ids, and reports them', () => {
		const result = quoteLines(
			[line('nulla', 0), line('negativ', -1), line('sok', 1000.5), line('nan', Number.NaN), line('Rossz-ID', 1), line('ok', 1000)],
			lineChoices([], [])
		);
		expect(result.lines).toEqual([{ ingredient_id: 'ok', qty: 1000 }]);
		expect(result.skipped).toEqual(['nulla', 'negativ', 'sok', 'nan', 'Rossz-ID']);
	});

	it('caps the quote at 200 lines and reports the rest', () => {
		const many = Array.from({ length: 205 }, (_, i) => line(`tetel_${String(i).padStart(3, '0')}`, 1));
		const result = quoteLines(many, lineChoices([], []));
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
			store_ids: ['synthetic-aldi-1', 'synthetic-lidl-1'],
			include_loyalty: false
		});
		expect(JSON.stringify(request)).not.toMatch(/lat|lon|47\.5|19\.05/);
	});

	it('is null without lines or without stores', () => {
		expect(buildQuoteRequest([], ['synthetic-lidl-1'])).toBeNull();
		expect(buildQuoteRequest(lines, [])).toBeNull();
		expect(buildQuoteRequest(lines, ['bad id!'])).toBeNull();
	});

	it('de-duplicates store ids, drops invalid ones and keeps the first 25 of the given order, sorted by id', () => {
		const ids = ['s-1', 's-1', 'bad id', ...Array.from({ length: 30 }, (_, i) => `s-${i + 2}`)];
		const request = buildQuoteRequest(lines, ids);
		const kept = Array.from({ length: 25 }, (_, i) => `s-${i + 1}`);
		expect(request?.store_ids).toHaveLength(25);
		expect(new Set(request?.store_ids)).toEqual(new Set(kept));
		expect(request?.store_ids).toEqual([...kept].sort());
	});

	it('sends the same body for the same stores in any order (the order never reveals the position)', () => {
		// Nearest-first lists of the same stores, as seen from two different origins.
		const fromNorth = ['synthetic-spar-2', 'synthetic-lidl-1', 'synthetic-aldi-3', 'synthetic-penny-1'];
		const fromSouth = ['synthetic-penny-1', 'synthetic-aldi-3', 'synthetic-lidl-1', 'synthetic-spar-2'];
		const north = buildQuoteRequest(lines, fromNorth);
		const south = buildQuoteRequest(lines, fromSouth);
		expect(JSON.stringify(north)).toBe(JSON.stringify(south));
		expect(north?.store_ids).toEqual([...fromNorth].sort());
		expect(fromNorth[0]).toBe('synthetic-spar-2'); // the input is not changed
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
