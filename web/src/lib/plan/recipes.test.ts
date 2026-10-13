import { describe, expect, it } from 'vitest';
import type { ChainCostOut, RecipeSummary, Slot } from '../api/types';
import {
	SERVINGS_MAX,
	SERVINGS_MIN,
	chainCostRows,
	chainList,
	chainName,
	chainNameMap,
	clampServings,
	coveragePercent,
	eligibleRecipes,
	filterRecipes,
	foldText,
	foldedQuery,
	hasExcludedTag,
	roundScaled,
	scaleDisplay,
	tagLabelKey
} from './recipes';

const NBSP = ' ';

function recipe(id: string, title: string, slots: Slot[], tags: string[]): RecipeSummary {
	return {
		id,
		title,
		summary: null,
		slots,
		servings: 4,
		minutes: 30,
		tags,
		tested: false,
		cost_per_serving_from: null,
		cheapest_chains: [],
		priced_share: 0
	};
}

const RECIPES = [
	recipe('lencse', 'Lencsefőzelék főtt tojással', ['ebed', 'vacsora'], ['fozelek', 'huvelyes', 'husmentes']),
	recipe('harcsa', 'Rántott harcsa burgonyával', ['ebed'], ['foetel', 'hal']),
	recipe('turos', 'Túrós kenyér retekkel', ['reggeli', 'uzsonna'], ['reggeli_hideg', 'husmentes']),
	recipe('cukkini', 'Cukkinis tészta', ['vacsora'], ['foetel', 'husmentes']),
	recipe('csirke', 'Csirkepaprikás', ['ebed', 'vacsora'], ['foetel', 'baromfi'])
];

describe('accent-insensitive search (like the server’s fold_name)', () => {
	it('folds case, accents and whitespace', () => {
		expect(foldText('  Lencsefőzelék   Főtt\tTojással ')).toBe('lencsefozelek fott tojassal');
		expect(foldText('ŐŰÁÉÍÓÖÚÜ őűáéíóöúü')).toBe('ouaeioouu ouaeioouu');
	});

	it('ignores searches shorter than 2 characters and caps them at 40', () => {
		expect(foldedQuery('  l ')).toBeNull();
		expect(foldedQuery('')).toBeNull();
		expect(foldedQuery(null)).toBeNull();
		expect(foldedQuery('Fő')).toBe('fo');
		expect(foldedQuery('x'.repeat(50))).toHaveLength(40);
	});

	it('matches with or without accents, in any case', () => {
		const titles = (q: string): string[] => filterRecipes(RECIPES, { q }).map((r) => r.id);
		expect(titles('fozelek')).toEqual(['lencse']);
		expect(titles('FŐZELÉK')).toEqual(['lencse']);
		expect(titles('turos')).toEqual(['turos']);
		expect(titles('rántott   HARCSA')).toEqual(['harcsa']);
		expect(titles('t')).toHaveLength(5);
		expect(titles('nincs ilyen')).toEqual([]);
	});
});

describe('filterRecipes', () => {
	it('combines slot, tag and search', () => {
		const ids = (filter: Parameters<typeof filterRecipes>[1]): string[] => filterRecipes(RECIPES, filter).map((r) => r.id);
		expect(ids({ slot: 'reggeli' })).toEqual(['turos']);
		expect(ids({ slot: 'vacsora', tag: 'husmentes' })).toEqual(['lencse', 'cukkini']);
		expect(ids({ tag: 'hal' })).toEqual(['harcsa']);
		expect(ids({ slot: 'ebed', tag: 'foetel', q: 'csirke' })).toEqual(['csirke']);
		expect(ids({})).toEqual(['lencse', 'harcsa', 'turos', 'cukkini', 'csirke']);
	});

	it('ignores values outside the vocabulary (e.g. from a hand-edited URL)', () => {
		expect(filterRecipes(RECIPES, { slot: 'brunch' as Slot, tag: 'nope' as 'hal' })).toHaveLength(5);
	});
});

describe('eligibleRecipes (the meal picker)', () => {
	it('keeps the slot’s recipes without excluded tags, sorted by Hungarian collation', () => {
		expect(eligibleRecipes(RECIPES, 'vacsora', []).map((r) => r.title)).toEqual([
			// Hungarian: "c" sorts before "cs".
			'Cukkinis tészta',
			'Csirkepaprikás',
			'Lencsefőzelék főtt tojással'
		]);
		expect(eligibleRecipes(RECIPES, 'vacsora', ['baromfi']).map((r) => r.id)).toEqual(['cukkini', 'lencse']);
		expect(eligibleRecipes(RECIPES, 'ebed', [], 'harcsa').map((r) => r.id)).toEqual(['harcsa']);
		expect(eligibleRecipes(RECIPES, 'tizorai', [])).toEqual([]);
		expect(hasExcludedTag(RECIPES[1] as RecipeSummary, ['hal'])).toBe(true);
	});
});

describe('scaleDisplay (real display texts from data/recipes)', () => {
	it('returns the text unchanged at the recipe’s own servings or for an invalid factor', () => {
		expect(scaleDisplay('40 dkg', 1)).toBe('40 dkg');
		expect(scaleDisplay('40 dkg', 0)).toBe('40 dkg');
		expect(scaleDisplay('40 dkg', Number.NaN)).toBe('40 dkg');
		expect(scaleDisplay('40 dkg', -2)).toBe('40 dkg');
	});

	it('scales whole numbers and decimal commas', () => {
		expect(scaleDisplay('40 dkg', 0.5)).toBe('20 dkg');
		expect(scaleDisplay('1,2 kg érett paradicsom', 0.5)).toBe('0,6 kg érett paradicsom');
		expect(scaleDisplay('1,5 l', 2)).toBe('3 l');
		expect(scaleDisplay('kb. 7,5 dl', 0.5)).toBe('kb. 3,8 dl');
		expect(scaleDisplay('2 gerezd', 0.75)).toBe('1,5 gerezd');
		expect(scaleDisplay('1 teáskanál', 0.25)).toBe('0,25 teáskanál');
	});

	it('scales every amount, also inside parentheses', () => {
		expect(scaleDisplay('3 evőkanál (1 a rizshez, 2 a mártáshoz)', 2)).toBe('6 evőkanál (2 a rizshez, 4 a mártáshoz)');
		expect(scaleDisplay('42 dkg (40 dkg a nokedlihez, 2 dkg a habaráshoz)', 0.5)).toBe(
			'21 dkg (20 dkg a nokedlihez, 1 dkg a habaráshoz)'
		);
		expect(scaleDisplay('4 egész comb (kb. 1,2 kg)', 0.5)).toBe('2 egész comb (kb. 0,6 kg)');
	});

	it('scales ranges and keeps their dash', () => {
		expect(scaleDisplay('1–2 teáskanál', 2)).toBe('2–4 teáskanál');
		expect(scaleDisplay('3–4 db (30 dkg)', 0.5)).toBe('1,5–2 db (15 dkg)');
		expect(scaleDisplay('2-3 db', 2)).toBe('4-6 db');
	});

	it('understands "fél" and "másfél" as whole words only', () => {
		expect(scaleDisplay('fél fej', 2)).toBe('1 fej');
		expect(scaleDisplay('fél citrom leve', 3)).toBe('1,5 citrom leve');
		expect(scaleDisplay('másfél fej (1 a főzelékbe, fél a fasírtba)', 2)).toBe('3 fej (2 a főzelékbe, 1 a fasírtba)');
		expect(scaleDisplay('1,5 l és fél dl', 2)).toBe('3 l és 1 dl');
		expect(scaleDisplay('Fél teáskanál', 2)).toBe('1 teáskanál');
		expect(scaleDisplay('félbevágott dió', 2)).toBe('félbevágott dió');
		expect(scaleDisplay('felezett', 2)).toBe('felezett');
	});

	it('leaves text without an amount, percentages and suffixed numbers alone', () => {
		expect(scaleDisplay('ízlés szerint', 3)).toBe('ízlés szerint');
		expect(scaleDisplay('2,8%-os tej', 2)).toBe('2,8%-os tej');
		expect(scaleDisplay('2-es méret', 2)).toBe('2-es méret');
		expect(scaleDisplay('B12 vitamin', 2)).toBe('B12 vitamin');
	});

	it('formats large results with hu-HU grouping', () => {
		expect(scaleDisplay('600 g', 3)).toBe(`1${NBSP}800 g`);
	});
});

describe('roundScaled', () => {
	it('rounds to kitchen precision', () => {
		expect(roundScaled(52.5)).toBe(53);
		expect(roundScaled(10)).toBe(10);
		expect(roundScaled(9.96)).toBe(10);
		expect(roundScaled(1.65)).toBe(1.7);
		expect(roundScaled(1.04)).toBe(1);
		expect(roundScaled(0.125)).toBe(0.13);
		expect(roundScaled(0.001)).toBe(0.01);
		expect(roundScaled(0)).toBe(0);
		expect(roundScaled(-1)).toBe(0);
		expect(roundScaled(Number.POSITIVE_INFINITY)).toBe(0);
	});
});

describe('servings and coverage', () => {
	it('clamps servings to the stepper range', () => {
		expect(clampServings(0)).toBe(SERVINGS_MIN);
		expect(clampServings(4)).toBe(4);
		expect(clampServings(4.4)).toBe(4);
		expect(clampServings(99)).toBe(SERVINGS_MAX);
		expect(clampServings(Number.NaN)).toBe(SERVINGS_MIN);
	});

	it('rounds the priced share down, so partial coverage never reads 100 %', () => {
		expect(coveragePercent(0.92)).toBe(92);
		expect(coveragePercent(0.29)).toBe(29);
		expect(coveragePercent(0.57)).toBe(57);
		expect(coveragePercent(0.999)).toBe(99);
		expect(coveragePercent(1)).toBe(100);
		expect(coveragePercent(0)).toBe(0);
		expect(coveragePercent(1.5)).toBe(100);
		expect(coveragePercent(-0.1)).toBe(0);
		expect(coveragePercent(Number.NaN)).toBe(0);
	});
});

describe('chain names and tags', () => {
	const names = chainNameMap([
		{ id: 'c1', slug: 'aldi', name: 'Aldi', is_grocery: true },
		{ id: 'c2', slug: 'lidl', name: 'Lidl', is_grocery: true }
	]);

	it('shows names from /api/meta and falls back to the slug', () => {
		expect(chainName('lidl', names)).toBe('Lidl');
		expect(chainName('penny', names)).toBe('penny');
		expect(chainNameMap(null).size).toBe(0);
	});

	it('lists every chain of a tie, in the server’s order', () => {
		expect(chainList(['lidl', 'aldi'], names)).toBe('Lidl, Aldi');
		expect(chainList([], names)).toBe('');
	});

	it('has a label key for every vocabulary tag only', () => {
		expect(tagLabelKey('ket_napos')).toBe('recipes.tag_ket_napos');
		expect(tagLabelKey('ismeretlen')).toBeNull();
	});
});

describe('chainCostRows (tie-aware, BUILD-BRIEF §4.1 trap 13)', () => {
	const names = chainNameMap([
		{ id: 'c1', slug: 'aldi', name: 'Aldi', is_grocery: true },
		{ id: 'c2', slug: 'lidl', name: 'Lidl', is_grocery: true },
		{ id: 'c3', slug: 'spar', name: 'Spar', is_grocery: true },
		{ id: 'c4', slug: 'tesco', name: 'Tesco', is_grocery: true },
		{ id: 'c5', slug: 'penny', name: 'Penny', is_grocery: true }
	]);
	const cost = (chain: string, value: number | null, share = 1, missing: string[] = []): ChainCostOut => ({
		chain,
		cost_per_serving: value,
		priced_share: share,
		missing
	});

	it('sorts cheapest first, unpriced chains last', () => {
		const rows = chainCostRows(
			[cost('aldi', 330), cost('auchan', null, 0, ['a']), cost('spar', 400.2, 0.92, ['b']), cost('tesco', 290)],
			names
		);
		expect(rows.map((r) => [r.chain, r.rank, r.tied])).toEqual([
			['tesco', 1, false],
			['aldi', 2, false],
			['spar', 3, false],
			['auchan', null, false]
		]);
		expect(rows[2]).toMatchObject({ name: 'Spar', coveragePercent: 92, missing: ['b'], costPerServing: 400.2 });
		expect(rows[3]).toMatchObject({ name: 'auchan', costPerServing: null, barPercent: 0, coveragePercent: 0 });
	});

	it('treats equal whole-forint costs as a tie that shares a rank (1, 1, 3), never re-ordered by name', () => {
		const rows = chainCostRows([cost('lidl', 312.4), cost('penny', 350), cost('aldi', 312.3), cost('spar', 312.6)], names);
		expect(rows.map((r) => [r.chain, r.rank, r.tied])).toEqual([
			// Lidl stays before Aldi: the server's order inside the tie, not the alphabet.
			['lidl', 1, true],
			['aldi', 1, true],
			// 312.6 rounds to 313 Ft: not part of the tie.
			['spar', 3, false],
			['penny', 4, false]
		]);
	});

	it('gives bar lengths relative to the most expensive priced chain', () => {
		const rows = chainCostRows([cost('aldi', 100), cost('lidl', 400), cost('spar', 2), cost('penny', 0)], names);
		expect(Object.fromEntries(rows.map((r) => [r.chain, r.barPercent]))).toEqual({ aldi: 25, lidl: 100, spar: 1, penny: 0 });
	});

	it('is empty for no chain costs', () => {
		expect(chainCostRows([], names)).toEqual([]);
	});
});
