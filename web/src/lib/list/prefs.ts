/**
 * Shopping-list choices: the chosen range, and per list (plan + range, see `listKey`) the ticked lines, the
 * lines removed by hand, the excluded lines bought anyway and the store the user picked.
 *
 * They are part of the ONE stored document of $lib/storage (`StoredState.list`, key `hetikosar.state`), so
 * they share its validation (key ≤ 80 printable ASCII characters, ≤ 12 lists, ticked, removed and included
 * ids and store ids matching the API's id patterns, ≤ 500 ticked and ≤ 200 removed ids per list), its
 * in-memory fallback when the browser refuses storage, and "minden adat törlése". Nothing here is ever sent
 * to the server.
 *
 * The separate `hetikosar.list` document of earlier builds is retired; it was never shipped to users, and
 * `clearAll` removes any leftover copy with the rest of the `hetikosar.` keys.
 */
import { MAX_LIST_ENTRIES, load, save, type ListEntry, type StoredList } from '../storage';

export type { ListEntry } from '../storage';
/** The list choices as stored (`StoredState.list`). */
export type ListPrefs = StoredList;
/** Remembered lists (most recently used first); older ones are dropped. */
export const MAX_REMEMBERED_LISTS = MAX_LIST_ENTRIES;

export function defaultListPrefs(): ListPrefs {
	return { range: 'this_week', entries: [] };
}

/**
 * Plain copies. Not structuredClone: the page keeps the choices in Svelte `$state`, whose proxies cannot be
 * structured-cloned (DataCloneError).
 */
function copyEntry(entry: ListEntry): ListEntry {
	// Tolerates entries shaped by an older build (no `checked` / `included`): the storage module validates
	// whatever is saved, so a missing list simply becomes [].
	const ids = (value: readonly string[] | undefined): string[] => (Array.isArray(value) ? [...value] : []);
	return {
		key: entry.key,
		checked: ids(entry.checked),
		removed: ids(entry.removed),
		included: ids(entry.included),
		storeId: entry.storeId
	};
}

/** The current list choices (a fresh copy). Never throws. */
export function loadListPrefs(): ListPrefs {
	return load().list;
}

/** Validates and stores the list choices. Returns false when they could only be kept in memory. Never throws. */
export function saveListPrefs(prefs: ListPrefs): boolean {
	return save({ ...load(), list: { range: prefs.range, entries: prefs.entries.map(copyEntry) } });
}

/** The remembered entry of a list (an empty one when the list is new). */
export function listEntry(prefs: ListPrefs, key: string): ListEntry {
	const found = prefs.entries.find((entry) => entry.key === key);
	return found ? copyEntry(found) : { key, checked: [], removed: [], included: [], storeId: null };
}

/** The choices with `entry` stored as the most recently used list (the input is never changed). */
export function withListEntry(prefs: ListPrefs, entry: ListEntry): ListPrefs {
	const others = prefs.entries.filter((existing) => existing.key !== entry.key).map(copyEntry);
	return { range: prefs.range, entries: [copyEntry(entry), ...others].slice(0, MAX_REMEMBERED_LISTS) };
}
