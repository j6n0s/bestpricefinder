import { describe, expect, it } from 'vitest';
import type { RuleCheckOut, RuleName } from '../api/types';
import { checkText, checksForWeek, firstInt, slotLabelLower, uniqueWarnings, warningText } from './checks';

const NBSP = ' ';

function check(rule: RuleName, value: string, limit: string, ok = true, week = 0): RuleCheckOut {
	return { week, rule, ok, value, limit };
}

describe('checkText (value and limit strings as server/bpf/planner/rules.py writes them)', () => {
	it('count rules: "Hal: 2 (cél: legalább 1)"', () => {
		expect(checkText(check('fish', '2 hal', '≥ 1'), 'hu')).toBe('Hal: 2 (cél: legalább 1)');
		expect(checkText(check('legume', '0 hüvelyes', '≥ 1', false), 'hu')).toBe('Hüvelyes: 0 (cél: legalább 1)');
		expect(checkText(check('meat_free_day', '1 húsmentes nap', '≥ 1'), 'hu')).toBe('Húsmentes nap: 1 (cél: legalább 1)');
		expect(checkText(check('fish', '2 hal', '≥ 1'), 'en')).toBe('Fish: 2 (target: at least 1)');
	});

	it('count rules in a week shorter than 4 days are not assessed', () => {
		expect(checkText(check('fish', 'n/a', '≥ 1'), 'hu')).toBe('Hal: nem értékeljük, mert ez a hét 4 napnál rövidebb');
		expect(checkText(check('meat_free_day', 'n/a', '≥ 1'), 'en')).toBe(
			'Meat-free day: not assessed, this week is shorter than 4 days'
		);
	});

	it('red meat in grams per person, formatted hu-HU', () => {
		expect(checkText(check('red_meat', '450 g/fő', '≤ 600 g/fő'), 'hu')).toBe('Vörös hús: 450 g/fő (cél: legfeljebb 600 g/fő)');
		expect(checkText(check('red_meat', '1250 g/fő', '≤ 257 g/fő', false), 'en')).toBe(
			`Red meat: 1${NBSP}250 g/person (target: at most 257 g/person)`
		);
	});

	it('potato runs, with English plurals', () => {
		expect(checkText(check('potato', '2 nap egymás után', '≤ 1 nap egymás után', false), 'hu')).toBe(
			'Burgonya: 2 nap egymás után (cél: legfeljebb 1)'
		);
		expect(checkText(check('potato', '1 nap egymás után', '≤ 1 nap egymás után'), 'en')).toBe(
			'Potato: 1 day in a row (target: at most 1)'
		);
		expect(checkText(check('potato', '0 nap egymás után', '≤ 1 nap egymás után'), 'en')).toBe(
			'Potato: 0 days in a row (target: at most 1)'
		);
	});

	it('sweets', () => {
		expect(checkText(check('sweets', '3 édes', '≤ 2', false), 'hu')).toBe('Édesség: 3 (cél: legfeljebb 2)');
		expect(checkText(check('sweets', '0 édes', '≤ 2'), 'en')).toBe('Sweets: 0 (target: at most 2)');
	});

	it('variety, with and without the snack window', () => {
		expect(checkText(check('variety', '0 ismétlés', '0 ismétlés 5 napon belül'), 'hu')).toBe(
			'Változatosság: 0 ismétlés (cél: 0 ismétlés 5 napon belül)'
		);
		expect(
			checkText(check('variety', '1 ismétlés', '0 ismétlés 5 napon belül, tízórai/uzsonna 2 napon belül', false), 'hu')
		).toBe('Változatosság: 1 ismétlés (cél: 0 ismétlés 5 napon belül, tízórainál és uzsonnánál 2 napon belül)');
		expect(checkText(check('variety', '1 ismétlés', '0 ismétlés 1 napon belül', false), 'en')).toBe(
			'Variety: 1 repeat (target: none within a 1-day window)'
		);
		expect(checkText(check('variety', '3 ismétlés', '0 ismétlés 5 napon belül, tízórai/uzsonna 2 napon belül', false), 'en')).toBe(
			'Variety: 3 repeats (target: none within a 5-day window, 2-day window for snacks)'
		);
	});

	it('budget in forints, with meals that have no price', () => {
		expect(checkText(check('budget', '12345 Ft', '≤ 20000 Ft'), 'hu')).toBe(
			`Keret: 12${NBSP}345${NBSP}Ft (cél: legfeljebb 20${NBSP}000${NBSP}Ft)`
		);
		expect(checkText(check('budget', '9000 Ft + 2 ár nélküli étel', '≤ 20000 Ft', false), 'hu')).toBe(
			`Keret: 9${NBSP}000${NBSP}Ft és 2 ár nélküli étel (cél: legfeljebb 20${NBSP}000${NBSP}Ft)`
		);
		expect(checkText(check('budget', '9000 Ft + 1 ár nélküli étel', '≤ 20000 Ft', false), 'en')).toBe(
			`Budget: 9${NBSP}000${NBSP}Ft and 1 meal without a price (target: at most 20${NBSP}000${NBSP}Ft)`
		);
	});

	it('falls back to the server’s own text when a string has an unexpected shape', () => {
		expect(checkText(check('fish', 'sok hal', 'legalább egy'), 'hu')).toBe('Hal: sok hal (cél: legalább egy)');
		expect(checkText(check('variety', '0 ismétlés', 'nincs ablak'), 'hu')).toBe('Változatosság: 0 ismétlés (cél: nincs ablak)');
		const unknown = { week: 0, rule: 'salt' as RuleName, ok: true, value: '1', limit: '≤ 2' };
		expect(checkText(unknown, 'hu')).toBe('salt: 1 (cél: ≤ 2)');
	});

	it('reads the first whole number', () => {
		expect(firstInt('≤ 600 g/fő')).toBe(600);
		expect(firstInt('n/a')).toBeNull();
	});
});

describe('checksForWeek', () => {
	it('keeps one week and orders the rules like the API', () => {
		const checks = [
			check('variety', '0 ismétlés', '0 ismétlés 5 napon belül', true, 0),
			check('fish', '1 hal', '≥ 1', true, 1),
			check('fish', '0 hal', '≥ 1', false, 0),
			check('red_meat', '0 g/fő', '≤ 600 g/fő', true, 0)
		];
		expect(checksForWeek(checks, 0).map((c) => c.rule)).toEqual(['fish', 'red_meat', 'variety']);
		expect(checksForWeek(checks, 1).map((c) => c.rule)).toEqual(['fish']);
		expect(checksForWeek(checks, 2)).toEqual([]);
	});
});

describe('warningText (codes from docs/API.md)', () => {
	it('maps every documented code', () => {
		expect(warningText('slot_pool_empty:reggeli', 'hu')).toBe('Ehhez az étkezéshez nincs választható recept, ezért üresen maradt: reggeli.');
		expect(warningText('slot_pool_too_small:tizorai', 'hu')).toBe(
			'Ehhez az étkezéshez kevés a választható recept, ezért ismétlődhetnek: tízórai.'
		);
		expect(warningText('no_fish_recipe_available', 'hu')).toBe('Nincs választható halas recept.');
		expect(warningText('no_legume_recipe_available', 'en')).toBe('There is no legume recipe to choose.');
		expect(warningText('no_meat_free_recipe_available:vacsora', 'en')).toBe(
			'There is no meat-free recipe to choose for this meal: dinner.'
		);
		expect(warningText('no_potato_free_recipe_available:ebed', 'hu')).toBe(
			'Ehhez az étkezéshez nincs választható burgonya nélküli recept: ebéd.'
		);
		expect(warningText('red_meat_cap_unreachable', 'hu')).toBe('A vörös hús heti felső határa ezekkel a receptekkel nem tartható.');
		expect(warningText('sweets_cap_unreachable', 'en')).toBe('The weekly limit on sweet dishes cannot be kept with these recipes.');
		expect(warningText('budget_unreachable', 'hu')).toBe('A heti keret ezekkel a receptekkel nem tartható.');
		expect(warningText('recipe_cost_missing', 'hu')).toBe('Nincs elég áradat a heti keret ellenőrzéséhez.');
	});

	it('names malformed or unknown codes instead of guessing', () => {
		expect(warningText('slot_pool_empty', 'hu')).toBe('Ismeretlen figyelmeztetés: slot_pool_empty.');
		expect(warningText('slot_pool_empty:brunch', 'hu')).toBe('Ismeretlen figyelmeztetés: slot_pool_empty:brunch.');
		expect(warningText('no_fish_recipe_available:ebed', 'en')).toBe('Unknown note: no_fish_recipe_available:ebed.');
		expect(warningText('toString', 'hu')).toBe('Ismeretlen figyelmeztetés: toString.');
		expect(warningText('__proto__:ebed', 'hu')).toBe('Ismeretlen figyelmeztetés: __proto__:ebed.');
	});

	it('removes duplicate codes', () => {
		expect(uniqueWarnings(['a', 'b', 'a'])).toEqual(['a', 'b']);
	});

	it('writes slot names in lower case inside a sentence', () => {
		expect(slotLabelLower('uzsonna', 'hu')).toBe('uzsonna');
		expect(slotLabelLower('tizorai', 'en')).toBe('morning snack');
	});
});
