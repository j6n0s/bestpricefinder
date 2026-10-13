// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import { translate } from '../i18n/messages';
import { FALLBACK_GROUP, LIST_GROUP_ORDER, displayGroup, groupLabelKey, groupLines, isListGroup } from './groups';

const line = (id: string, group: string): { id: string; list_group: string } => ({ id, list_group: group });

describe('LIST_GROUP_ORDER', () => {
	it('is the docs/DATA.md shopping-list order', () => {
		expect(LIST_GROUP_ORDER).toEqual([
			'zoldseg_gyumolcs',
			'pekaru',
			'tejtermek_tojas',
			'hus_hal',
			'szaraz_tartos',
			'fagyasztott',
			'fuszer_olaj',
			'egyeb'
		]);
	});

	it('has a distinct Hungarian and English section name for every group', () => {
		const hu = LIST_GROUP_ORDER.map((group) => translate('hu', groupLabelKey(group)));
		const en = LIST_GROUP_ORDER.map((group) => translate('en', groupLabelKey(group)));
		expect(new Set(hu).size).toBe(LIST_GROUP_ORDER.length);
		expect(new Set(en).size).toBe(LIST_GROUP_ORDER.length);
		expect(hu).toEqual([
			'Zöldség, gyümölcs',
			'Pékáru',
			'Tejtermék, tojás',
			'Hús, hal',
			'Száraz és tartós élelmiszer',
			'Fagyasztott',
			'Fűszer, olaj',
			'Egyéb'
		]);
		for (const text of [...hu, ...en]) expect(text).not.toMatch(/^list\./);
	});
});

describe('groupLines', () => {
	it('orders sections by the DATA.md order whatever the input order, keeping the order inside a section', () => {
		const lines = [
			line('so', 'fuszer_olaj'),
			line('csirkemell', 'hus_hal'),
			line('alma', 'zoldseg_gyumolcs'),
			line('tej', 'tejtermek_tojas'),
			line('borso', 'fagyasztott'),
			line('kenyer', 'pekaru'),
			line('rizs', 'szaraz_tartos'),
			line('repa', 'zoldseg_gyumolcs'),
			line('folia', 'egyeb')
		];
		const groups = groupLines(lines);
		expect(groups.map((g) => g.group)).toEqual([...LIST_GROUP_ORDER]);
		expect(groups[0]?.lines.map((l) => l.id)).toEqual(['alma', 'repa']);
	});

	it('leaves out empty sections', () => {
		const groups = groupLines([line('a', 'hus_hal'), line('b', 'pekaru')]);
		expect(groups.map((g) => g.group)).toEqual(['pekaru', 'hus_hal']);
	});

	it('returns nothing for no lines', () => {
		expect(groupLines([])).toEqual([]);
	});

	it('shows unknown groups in "egyeb" after its own lines, sorted by group name and stable', () => {
		const groups = groupLines([
			line('x2', 'zz_new'),
			line('e1', 'egyeb'),
			line('x1', 'aa_new'),
			line('x3', 'zz_new'),
			line('v1', 'zoldseg_gyumolcs')
		]);
		expect(groups.map((g) => g.group)).toEqual(['zoldseg_gyumolcs', 'egyeb']);
		expect(groups[1]?.lines.map((l) => l.id)).toEqual(['e1', 'x1', 'x2', 'x3']);
	});

	it('creates the "egyeb" section for unknown groups alone', () => {
		expect(groupLines([line('x', 'new_group')])).toEqual([{ group: 'egyeb', lines: [line('x', 'new_group')] }]);
	});

	it('never changes the input', () => {
		const lines = [line('b', 'zz'), line('a', 'aa')];
		const copy = structuredClone(lines);
		groupLines(lines);
		expect(lines).toEqual(copy);
	});
});

describe('displayGroup / isListGroup', () => {
	it('maps unknown or empty groups to the fallback', () => {
		expect(displayGroup('hus_hal')).toBe('hus_hal');
		expect(displayGroup('')).toBe(FALLBACK_GROUP);
		expect(displayGroup('HUS_HAL')).toBe(FALLBACK_GROUP);
		expect(isListGroup('pekaru')).toBe(true);
		expect(isListGroup('toString')).toBe(false);
		expect(isListGroup(null)).toBe(false);
	});
});
