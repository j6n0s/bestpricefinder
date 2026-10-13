/**
 * The offline copies of the shopping list (BUILD-BRIEF §2: the list is used in the shop, often without a
 * signal). The last list POST /api/list returned and the chosen store's part of the last POST /api/quote
 * answer are kept in the one stored document ($lib/storage: `lastList`, `lastQuote`), on this device only,
 * and are wiped by "Minden adat törlése". They are NEVER cached by the service worker (its caches hold
 * public data only).
 *
 * A copy is used only for exactly the request it answers (the JSON body), and only when the request failed
 * for lack of a connection (offline, network error, timeout). Every saved price keeps its GVH data date.
 */
import { ApiError } from '../api/client';
import type { ListLineOut, StoreQuoteOut } from '../api/types';
import { load, update, type SavedList, type SavedQuote } from '../storage';

/** True for the failures a saved copy may stand in for: no connection, not a server answer. */
export function isConnectionError(error: unknown): boolean {
	return error instanceof ApiError && (error.kind === 'offline' || error.kind === 'network' || error.kind === 'timeout');
}

/** A plain copy (the page keeps answers in Svelte `$state`, whose proxies cannot be structured-cloned). */
function plain<T>(value: T): T {
	return JSON.parse(JSON.stringify(value)) as T;
}

/** Remembers the lines of a successful POST /api/list for `body`. Never throws. */
export function saveLastList(body: string, lines: readonly ListLineOut[], now: Date = new Date()): void {
	try {
		update({ lastList: { body, savedAt: now.toISOString(), lines: plain([...lines]) } });
	} catch {
		// An offline copy is a convenience: failing to keep it must never break the list.
	}
}

/** The saved list for `body`, when `error` is a connection failure; else null. */
export function savedListFor(body: string, error: unknown): SavedList | null {
	if (!isConnectionError(error)) return null;
	const saved = load().lastList;
	return saved && saved.body === body ? saved : null;
}

/**
 * Remembers the chosen store of a successful POST /api/quote for `body` (skipped when that exact copy is
 * already stored, so re-renders do not rewrite the document). Never throws.
 */
export function saveLastQuote(body: string, dataDate: string, store: StoreQuoteOut, now: Date = new Date()): void {
	try {
		const current = load().lastQuote;
		if (current && current.body === body && current.store.store_id === store.store_id && current.dataDate === dataDate) {
			return;
		}
		update({ lastQuote: { body, savedAt: now.toISOString(), dataDate, store: plain(store) } });
	} catch {
		// See saveLastList.
	}
}

/** The saved store quote for `body`, when `error` is a connection failure; else null. */
export function savedQuoteFor(body: string, error: unknown): SavedQuote | null {
	if (!isConnectionError(error)) return null;
	const saved = load().lastQuote;
	return saved && saved.body === body ? saved : null;
}
