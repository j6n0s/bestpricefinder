// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { ListLineOut, QuoteLineOut } from '../api/types';
import { hasKshEstimate, storeGroups, storeLines } from './storeview';

function listLine(id: string, name: string, group: string): ListLineOut {
	return { ingredient_id: id, name_hu: name, qty: 1, unit: 'kg', list_group: group, pantry: false, recipe_ids: [] };
}

function quoteLine(id: string, status: QuoteLineOut['status'] = 'priced', ksh: number | null = null): QuoteLineOut {
	return {
		ingredient_id: id,
		qty: 1,
		unit: 'kg',
		status,
		picks: [],
		checkout_cost: status === 'priced' ? 100 : null,
		used_cost: status === 'priced' ? 100 : null,
		leftover_qty: null,
		ksh_estimate: ksh,
		alternatives: []
	};
}

const LIST = [
	listLine('repa', 'sárgarépa', 'zoldseg_gyumolcs'),
	listLine('kenyer', 'kenyér', 'pekaru'),
	listLine('csirke', 'csirkemell', 'hus_hal'),
	listLine('alma', 'alma', 'zoldseg_gyumolcs')
];

describe('storeLines', () => {
	it('follows the list order and names, whatever the quote order', () => {
		const lines = storeLines({ lines: [quoteLine('csirke'), quoteLine('alma'), quoteLine('repa')] }, LIST);
		expect(lines.map((l) => [l.line.ingredient_id, l.name, l.list_group])).toEqual([
			['repa', 'sárgarépa', 'zoldseg_gyumolcs'],
			['csirke', 'csirkemell', 'hus_hal'],
			['alma', 'alma', 'zoldseg_gyumolcs']
		]);
	});

	it('puts lines the list no longer has last, named by id, in "egyeb"', () => {
		const lines = storeLines({ lines: [quoteLine('ismeretlen'), quoteLine('kenyer')] }, LIST);
		expect(lines.map((l) => [l.name, l.list_group])).toEqual([
			['kenyér', 'pekaru'],
			['ismeretlen', 'egyeb']
		]);
	});
});

describe('storeGroups', () => {
	it('groups by list section in the DATA.md order', () => {
		const groups = storeGroups({ lines: [quoteLine('csirke'), quoteLine('kenyer'), quoteLine('alma'), quoteLine('repa')] }, LIST);
		expect(groups.map((g) => [g.group, g.lines.map((l) => l.line.ingredient_id)])).toEqual([
			['zoldseg_gyumolcs', ['repa', 'alma']],
			['pekaru', ['kenyer']],
			['hus_hal', ['csirke']]
		]);
	});
});

describe('hasKshEstimate', () => {
	it('is true only when a KSH estimate is shown', () => {
		expect(hasKshEstimate({ lines: [quoteLine('a'), quoteLine('b', 'ksh_estimate', 420)] })).toBe(true);
		expect(hasKshEstimate({ lines: [quoteLine('a'), quoteLine('b', 'unpriced')] })).toBe(false);
		expect(hasKshEstimate({ lines: [quoteLine('b', 'ksh_estimate', null)] })).toBe(false);
	});
});
