/**
 * Shopping-list sections ("list groups"), in the docs/DATA.md order:
 * zoldseg_gyumolcs, pekaru, tejtermek_tojas, hus_hal, szaraz_tartos, fagyasztott, fuszer_olaj, egyeb.
 *
 * The server sorts /api/list lines the same way (unknown groups last); this module groups any lines (list or
 * quote) for display. A group the client does not know (a future ontology value) is shown in "Egyéb", after
 * that group's own lines, so a new server value never breaks the page or gets an untranslated heading.
 */
import type { PlainKey } from '../i18n/messages';

export const LIST_GROUP_ORDER = [
	'zoldseg_gyumolcs',
	'pekaru',
	'tejtermek_tojas',
	'hus_hal',
	'szaraz_tartos',
	'fagyasztott',
	'fuszer_olaj',
	'egyeb'
] as const;

export type ListGroup = (typeof LIST_GROUP_ORDER)[number];

/** Where lines of an unknown group are shown. */
export const FALLBACK_GROUP: ListGroup = 'egyeb';

const GROUP_KEYS: Readonly<Record<ListGroup, PlainKey>> = {
	zoldseg_gyumolcs: 'list.group_zoldseg_gyumolcs',
	pekaru: 'list.group_pekaru',
	tejtermek_tojas: 'list.group_tejtermek_tojas',
	hus_hal: 'list.group_hus_hal',
	szaraz_tartos: 'list.group_szaraz_tartos',
	fagyasztott: 'list.group_fagyasztott',
	fuszer_olaj: 'list.group_fuszer_olaj',
	egyeb: 'list.group_egyeb'
};

export function isListGroup(value: unknown): value is ListGroup {
	return typeof value === 'string' && (LIST_GROUP_ORDER as readonly string[]).includes(value);
}

/** The section a line is shown in: its own group, or "egyeb" for an unknown one. */
export function displayGroup(group: string): ListGroup {
	return isListGroup(group) ? group : FALLBACK_GROUP;
}

/** The i18n key of a section heading. */
export function groupLabelKey(group: ListGroup): PlainKey {
	return GROUP_KEYS[group];
}

export interface LineGroup<T> {
	group: ListGroup;
	lines: T[];
}

/**
 * Lines grouped into sections in the docs/DATA.md order; empty sections are left out. Inside a section the
 * input order is kept, except that lines of unknown groups come after the "egyeb" lines (sorted by their
 * group name, like the server does), so already sorted /api/list lines keep their order.
 */
export function groupLines<T extends { readonly list_group: string }>(lines: readonly T[]): LineGroup<T>[] {
	const known = new Map<ListGroup, T[]>();
	const unknown: T[] = [];
	for (const line of lines) {
		if (isListGroup(line.list_group)) {
			const bucket = known.get(line.list_group);
			if (bucket) bucket.push(line);
			else known.set(line.list_group, [line]);
		} else {
			unknown.push(line);
		}
	}
	// Stable sort: equal group names keep their input order.
	unknown.sort((a, b) => (a.list_group < b.list_group ? -1 : a.list_group > b.list_group ? 1 : 0));
	if (unknown.length > 0) known.set(FALLBACK_GROUP, [...(known.get(FALLBACK_GROUP) ?? []), ...unknown]);
	return LIST_GROUP_ORDER.flatMap((group) => {
		const bucket = known.get(group);
		return bucket && bucket.length > 0 ? [{ group, lines: bucket }] : [];
	});
}
