/**
 * Shopping-list choices that $lib/storage's StoredState has no field for yet: the chosen range, and per list
 * (plan + range, see `listKey`) the lines removed by hand and the store the user picked.
 *
 * Like $lib/storage it is ONE versioned JSON document in localStorage, on this device only, under a key with
 * the app's prefix (`hetikosar.list`), so "minden adat törlése" (storage.clearAll) deletes it too. Every
 * access is wrapped in try/catch; when the browser refuses storage (private mode, full quota) the choices
 * live in memory for this session. The stored JSON is never trusted: every field is validated, and an unknown
 * version resets to the defaults. Nothing here is ever sent to the server.
 *
 * TODO(contract change requested by the list feature): move these fields into StoredState and make this
 * module a thin wrapper around $lib/storage.
 */
import { ID_PATTERNS } from '../api/types';
import { STORAGE_PREFIX } from '../storage';
import { isListRange, type ListRange } from './range';

export const LIST_PREFS_KEY = `${STORAGE_PREFIX}list`;
export const LIST_PREFS_VERSION = 1;
/** Remembered lists (most recently used first); older ones are dropped. */
export const MAX_REMEMBERED_LISTS = 12;
const MAX_REMOVED = 200;
const LIST_KEY_PATTERN = /^[\x20-\x7e]{1,80}$/;

export interface ListEntry {
	/** `listKey(plan, range)`. */
	key: string;
	/** Ingredient ids removed from this list by hand. */
	removed: string[];
	/** The store chosen for this list, or null. */
	storeId: string | null;
}

export interface ListPrefs {
	version: typeof LIST_PREFS_VERSION;
	range: ListRange;
	lists: ListEntry[];
}

export function defaultListPrefs(): ListPrefs {
	return { version: LIST_PREFS_VERSION, range: 'this_week', lists: [] };
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function sanitiseEntry(value: unknown): ListEntry | null {
	if (!isRecord(value)) return null;
	const { key, removed, storeId } = value;
	if (typeof key !== 'string' || !LIST_KEY_PATTERN.test(key)) return null;
	const ids: string[] = [];
	if (Array.isArray(removed)) {
		for (const id of removed) {
			if (ids.length >= MAX_REMOVED) break;
			if (typeof id === 'string' && ID_PATTERNS.ingredient.test(id) && !ids.includes(id)) ids.push(id);
		}
	}
	const store = typeof storeId === 'string' && ID_PATTERNS.store.test(storeId) ? storeId : null;
	return { key, removed: ids, storeId: store };
}

/** Any stored value -> valid prefs; an unknown or missing version gives the defaults. */
export function sanitiseListPrefs(raw: unknown): ListPrefs {
	if (!isRecord(raw) || raw.version !== LIST_PREFS_VERSION) return defaultListPrefs();
	const lists: ListEntry[] = [];
	const seen = new Set<string>();
	if (Array.isArray(raw.lists)) {
		for (const value of raw.lists) {
			if (lists.length >= MAX_REMEMBERED_LISTS) break;
			const entry = sanitiseEntry(value);
			if (entry && !seen.has(entry.key)) {
				seen.add(entry.key);
				lists.push(entry);
			}
		}
	}
	return { version: LIST_PREFS_VERSION, range: isListRange(raw.range) ? raw.range : 'this_week', lists };
}

/**
 * Plain copies. Not structuredClone: the page keeps the prefs in Svelte `$state`, whose proxies cannot be
 * structured-cloned (DataCloneError).
 */
function copyEntry(entry: ListEntry): ListEntry {
	return { key: entry.key, removed: [...entry.removed], storeId: entry.storeId };
}

function copyPrefs(prefs: ListPrefs): ListPrefs {
	return { version: prefs.version, range: prefs.range, lists: prefs.lists.map(copyEntry) };
}

let memory: ListPrefs | null = null;
/** True while `memory` holds changes that could not be written (they win over the stored copy). */
let unsaved = false;

function backend(): Storage | null {
	try {
		return globalThis.localStorage ?? null;
	} catch {
		return null;
	}
}

/** The current prefs (always a fresh copy). Never throws. */
export function loadListPrefs(): ListPrefs {
	if (unsaved && memory) return copyPrefs(memory);
	const storage = backend();
	let raw: string | null | undefined;
	try {
		raw = storage ? storage.getItem(LIST_PREFS_KEY) : undefined;
	} catch {
		raw = undefined;
	}
	if (raw === undefined) return copyPrefs(memory ?? defaultListPrefs());
	if (raw === null) {
		memory = null;
		return defaultListPrefs();
	}
	let parsed: unknown = null;
	try {
		parsed = JSON.parse(raw);
	} catch {
		parsed = null;
	}
	memory = sanitiseListPrefs(parsed);
	return copyPrefs(memory);
}

/** Validates and stores the prefs. Returns false when they could only be kept in memory. Never throws. */
export function saveListPrefs(prefs: ListPrefs): boolean {
	const clean = sanitiseListPrefs(prefs);
	memory = clean;
	const storage = backend();
	try {
		if (!storage) throw new Error('no localStorage');
		storage.setItem(LIST_PREFS_KEY, JSON.stringify(clean));
		unsaved = false;
		return true;
	} catch {
		unsaved = true;
		return false;
	}
}

/** The remembered entry of a list (an empty one when the list is new). */
export function listEntry(prefs: ListPrefs, key: string): ListEntry {
	const found = prefs.lists.find((entry) => entry.key === key);
	return found ? copyEntry(found) : { key, removed: [], storeId: null };
}

/** The prefs with `entry` stored as the most recently used list (the input is never changed). */
export function withListEntry(prefs: ListPrefs, entry: ListEntry): ListPrefs {
	const others = prefs.lists.filter((existing) => existing.key !== entry.key);
	return { ...prefs, lists: [copyEntry(entry), ...others].slice(0, MAX_REMEMBERED_LISTS) };
}

/** Test hook: forget the in-memory copy. */
export function resetListPrefsForTests(): void {
	memory = null;
	unsaved = false;
}
