/**
 * The ONE place where personal data is kept: the browser's localStorage, on this device only.
 *
 * Nothing in here is ever sent to the server as a whole. Plan, household size, slots, radius, pantry (staples
 * marked "nincs otthon" and the amounts at home, which the list subtracts on the device), exclusions (diet preferences are health data, GDPR Art. 9), location consent, the chosen district or the
 * approximate location, the shopping-list choices (range, and per list the ticks, removed lines, excluded
 * lines bought anyway and the chosen store), the last loaded list and the chosen store's last quote (so the
 * list still works offline in the shop), the cart (the goods picked by hand, their ticks and chosen store) and
 * the UI language, and whether the first-visit question about foods has been answered, all live under ONE key (`hetikosar.state`), as
 * one versioned JSON document. There is no other key: the list choices that used to live under
 * `hetikosar.list` are part of this document now.
 *
 * Robustness rules:
 * - Every localStorage access is wrapped in try/catch: private browsing, disabled site data, a full quota
 *   or a sandboxed frame must never break the app. When saving fails, the state lives on in memory for this
 *   session and `isPersistent()` turns false so the UI can say so.
 * - Reading never trusts the stored JSON: every field is validated and replaced by its default when invalid.
 * - An unknown `version` (newer, older without a migration, or missing) resets everything to the defaults.
 * - "Minden adat törlése" (`clearAll`) removes every `hetikosar.` key AND resets the in-memory copy, so
 *   nothing of the old data is shown again in this session, even when the browser refuses storage.
 * - Another tab can change or delete the document at any time: pages subscribe with `onExternalChange` and
 *   build every change from a fresh `load()`, never from a copy read when the page opened, so a stale tab
 *   cannot write deleted data (a revoked position, a cleared plan) back.
 *
 * Schema changes: adding a field with a default needs no version bump (sanitising fills it in). Changing the
 * meaning or shape of a field needs `STORAGE_VERSION + 1` and a migration step in `MIGRATIONS`.
 */
import {
	ID_PATTERNS,
	RECIPE_TAGS,
	SLOTS,
	type ListLineOut,
	type PlanDayIO,
	type RecipeTag,
	type Slot,
	type StoreQuoteOut
} from './api/types';
import { validListLines, validStoreQuote } from './list/validate';

export const STORAGE_KEY = 'hetikosar.state';
/** Every key this app owns starts with this prefix (clearAll removes them all). */
export const STORAGE_PREFIX = 'hetikosar.';
export const STORAGE_VERSION = 1;

export const LANGS = ['hu', 'en'] as const;
export type Lang = (typeof LANGS)[number];

export const PEOPLE_MIN = 1;
export const PEOPLE_MAX = 12;
export const RADIUS_MIN_KM = 0.5;
export const RADIUS_MAX_KM = 5;
export const RADIUS_STEP_KM = 0.5;
/** Stored approximate positions are rounded to this many decimals (about 100 m). */
export const APPROX_DECIMALS = 3;

const MAX_LIST = 200;
/** Remembered shopping lists (most recently used first); older ones are dropped. */
export const MAX_LIST_ENTRIES = 12;
/** Lines removed by hand, per list. */
export const MAX_REMOVED_LINES = 200;
/** Ticked lines, per list. */
export const MAX_CHECKED_LINES = 500;
/** Lines of the saved last list (offline copy). */
export const MAX_SAVED_LIST_LINES = 500;
/** The request body a saved answer belongs to (a JSON string). */
const MAX_SAVED_BODY_CHARS = 65_536;
/** A list key (`listKey(plan, range)`): 1–80 printable ASCII characters. */
const LIST_KEY_PATTERN = /^[\x20-\x7e]{1,80}$/;
const MAX_EXCLUDED_TAGS = 20;
const MAX_EXCLUDED_INGREDIENTS = 50;
const MAX_PLAN_DAYS = 31;
const DISTRICT_ID = /^(0[1-9]|1\d|2[0-3])$/;
/** Goods in the cart (src/lib/cart/cart.ts MAX_CART_LINES) and their largest quantity (the API's bound). */
const MAX_CART_LINES = 100;
const MAX_CART_QTY = 1000;
/** Ingredients with an amount at home (StoredState.pantry.onHand): the API's list limit. */
export const MAX_ON_HAND_LINES = 200;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** "Ez a hét", "Jövő hét", "Az egész terv" (src/lib/list/range.ts). */
export const LIST_RANGES = ['this_week', 'next_week', 'whole'] as const;
export type ListRange = (typeof LIST_RANGES)[number];

export function isListRange(value: unknown): value is ListRange {
	return typeof value === 'string' && (LIST_RANGES as readonly string[]).includes(value);
}

/** The choices for one shopping list (one plan and range). */
export interface ListEntry {
	/** `listKey(plan, range)` from src/lib/list/request.ts. */
	key: string;
	/**
	 * Ingredient ids ticked off on THIS list. Per list, so a new plan (a new `createdAt`) or another range
	 * starts with no ticks, while undoing "Terv törlése" brings the old plan's ticks back.
	 */
	checked: string[];
	/** Ingredient ids removed from this list by hand. */
	removed: string[];
	/** Excluded ingredients (StoredState.exclusions) the user chose to buy anyway on this list. */
	included: string[];
	/** The store chosen for this list, or null. */
	storeId: string | null;
}

export interface StoredList {
	/** The range the user last chose. */
	range: ListRange;
	/** The most recently used lists first, at most MAX_LIST_ENTRIES. */
	entries: ListEntry[];
}

/** The last list POST /api/list returned, kept so the list still opens without a connection. */
export interface SavedList {
	/** The request body (JSON) the lines answer; the copy is used only for exactly this request. */
	body: string;
	/** When it was loaded (ISO date-time). */
	savedAt: string;
	lines: ListLineOut[];
}

/** The chosen store's part of the last POST /api/quote answer, for the store list without a connection. */
export interface SavedQuote {
	/** The request body (JSON) the quote answers. */
	body: string;
	savedAt: string;
	/** The GVH data date of the prices (BUILD-BRIEF §8: a source and a date on every price). */
	dataDate: string;
	store: StoreQuoteOut;
}

export interface StoredPlan {
	/** When the plan was made (ISO date-time). */
	createdAt: string;
	/** The calendar date of day index 0 ("YYYY-MM-DD"), or null when undated. */
	startDate: string | null;
	seed: number;
	slots: 3 | 5;
	noRepeatDays: number;
	days: PlanDayIO[];
}

export type LocationConsent = 'unset' | 'granted' | 'declined';
export type LocationSource = 'none' | 'device' | 'district' | 'map';

export interface ApproxPosition {
	/** Rounded to APPROX_DECIMALS. */
	lat: number;
	lon: number;
	/** When the position was taken (ISO date-time). */
	at: string;
}

export interface StoredLocation {
	/** "unset": never asked or revoked; "granted": the user agreed and the browser gave a position. */
	consent: LocationConsent;
	/** Which origin the distances are computed from. */
	source: LocationSource;
	/** Budapest district "01".."23" (src/lib/data/districts.json), or null. */
	districtId: string | null;
	/** Only with consent "granted"; never sent anywhere. */
	approx: ApproxPosition | null;
	/**
	 * A point the user chose on the map (src/lib/components/MapPicker.svelte), not a sensor position, so no
	 * consent is involved; the origin when `source` is "map". Kept on this device only, never sent anywhere.
	 */
	manual: ApproxPosition | null;
}

/** One good in the cart, in its ingredient's unit (kg, l, db). */
export interface StoredCartLine {
	ingredientId: string;
	qty: number;
}

/** The cart ("Kosár"): goods picked by hand, independent of the plan. */
export interface StoredCart {
	/** In the order they were added. */
	lines: StoredCartLine[];
	/** Goods ticked off in the shop. */
	checked: string[];
	/** The store chosen for the cart's list, or null. */
	storeId: string | null;
}

export interface StoredState {
	version: typeof STORAGE_VERSION;
	language: Lang;
	people: number;
	slots: 3 | 5;
	radiusKm: number;
	plan: StoredPlan | null;
	pantry: {
		/**
		 * Pantry staples ("valószínűleg otthon van") the user marked "nincs otthon": staples are either at home
		 * (the default) or bought.
		 */
		notAtHome: string[];
		/**
		 * Amounts at home of any ingredient ("Otthon lévő mennyiségek"), in the ingredient's own unit. The list
		 * subtracts them ON THE DEVICE (src/lib/list/onhand.ts applyOnHand); the app never sends `on_hand`.
		 */
		onHand: StoredCartLine[];
	};
	exclusions: {
		tags: RecipeTag[];
		ingredients: string[];
	};
	/** The first-visit question "Mit nem eszel?" was saved; from then on the exclusions are edited in Settings. */
	preferencesAsked: boolean;
	location: StoredLocation;
	/** Shopping-list choices: the range, and per list the ticks, removed lines and the chosen store. */
	list: StoredList;
	/** The last loaded shopping list (offline copy), or null. */
	lastList: SavedList | null;
	/** The chosen store's last quote (offline copy), or null. */
	lastQuote: SavedQuote | null;
	cart: StoredCart;
}

export function defaultState(): StoredState {
	return {
		version: STORAGE_VERSION,
		language: 'hu',
		people: 2,
		slots: 3,
		radiusKm: 1.5,
		plan: null,
		pantry: { notAtHome: [], onHand: [] },
		exclusions: { tags: [], ingredients: [] },
		preferencesAsked: false,
		location: { consent: 'unset', source: 'none', districtId: null, approx: null, manual: null },
		list: { range: 'this_week', entries: [] },
		lastList: null,
		lastQuote: null,
		cart: { lines: [], checked: [], storeId: null }
	};
}

// ───────────────────────────── validation helpers ─────────────────────────────

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
	return typeof value === 'number' && Number.isFinite(value);
}

function isIsoDateTime(value: unknown): value is string {
	return typeof value === 'string' && value.length <= 40 && !Number.isNaN(Date.parse(value));
}

/** Unique strings matching `pattern`, in their first-seen order, at most `max`. */
function idList(value: unknown, pattern: RegExp, max: number): string[] {
	if (!Array.isArray(value)) return [];
	const out: string[] = [];
	const seen = new Set<string>();
	for (const item of value) {
		if (out.length >= max) break;
		if (typeof item === 'string' && pattern.test(item) && !seen.has(item)) {
			seen.add(item);
			out.push(item);
		}
	}
	return out;
}

export function isLang(value: unknown): value is Lang {
	return typeof value === 'string' && (LANGS as readonly string[]).includes(value);
}

export function clampPeople(value: unknown): number | null {
	return isFiniteNumber(value) && Number.isInteger(value) && value >= PEOPLE_MIN && value <= PEOPLE_MAX ? value : null;
}

/** A radius in [0.5, 5] km snapped to the 0.5 km step, or null when invalid. */
export function normaliseRadius(value: unknown): number | null {
	if (!isFiniteNumber(value) || value < RADIUS_MIN_KM || value > RADIUS_MAX_KM) return null;
	return Math.round(value / RADIUS_STEP_KM) * RADIUS_STEP_KM;
}

export function roundCoordinate(value: number, decimals: number = APPROX_DECIMALS): number {
	const factor = 10 ** decimals;
	return Math.round(value * factor) / factor;
}

function sanitiseMeals(value: unknown): PlanDayIO['meals'] | null {
	if (!isRecord(value)) return null;
	const meals: PlanDayIO['meals'] = {};
	for (const [key, recipe] of Object.entries(value)) {
		if (!(SLOTS as readonly string[]).includes(key)) return null;
		if (recipe !== null && !(typeof recipe === 'string' && ID_PATTERNS.recipe.test(recipe))) return null;
		meals[key as Slot] = recipe;
	}
	return meals;
}

function sanitisePlan(value: unknown): StoredPlan | null {
	if (!isRecord(value)) return null;
	const { createdAt, startDate, seed, slots, noRepeatDays, days } = value;
	if (!isIsoDateTime(createdAt)) return null;
	if (startDate !== null && !(typeof startDate === 'string' && ISO_DATE.test(startDate))) return null;
	if (!isFiniteNumber(seed) || !Number.isInteger(seed) || seed < 0 || seed > 2 ** 31 - 1) return null;
	if (slots !== 3 && slots !== 5) return null;
	if (!isFiniteNumber(noRepeatDays) || !Number.isInteger(noRepeatDays) || noRepeatDays < 0 || noRepeatDays > 14) {
		return null;
	}
	if (!Array.isArray(days) || days.length < 1 || days.length > MAX_PLAN_DAYS) return null;
	const outDays: PlanDayIO[] = [];
	const seenIndex = new Set<number>();
	for (const day of days) {
		if (!isRecord(day)) return null;
		const index = day.index;
		if (!isFiniteNumber(index) || !Number.isInteger(index) || index < 0 || index > 30 || seenIndex.has(index)) {
			return null;
		}
		const meals = sanitiseMeals(day.meals);
		if (meals === null) return null;
		seenIndex.add(index);
		outDays.push({ index, meals });
	}
	return { createdAt, startDate, seed, slots, noRepeatDays, days: outDays };
}

function sanitisePantry(value: unknown): StoredState['pantry'] {
	if (!isRecord(value)) return defaultState().pantry;
	return {
		notAtHome: idList(value.notAtHome, ID_PATTERNS.ingredient, MAX_LIST),
		onHand: sanitiseQtyLines(value.onHand, MAX_ON_HAND_LINES)
	};
}

function sanitiseListEntry(value: unknown): ListEntry | null {
	if (!isRecord(value)) return null;
	const { key, checked, removed, included, storeId } = value;
	if (typeof key !== 'string' || !LIST_KEY_PATTERN.test(key)) return null;
	return {
		key,
		checked: idList(checked, ID_PATTERNS.ingredient, MAX_CHECKED_LINES),
		removed: idList(removed, ID_PATTERNS.ingredient, MAX_REMOVED_LINES),
		included: idList(included, ID_PATTERNS.ingredient, MAX_EXCLUDED_INGREDIENTS),
		storeId: typeof storeId === 'string' && ID_PATTERNS.store.test(storeId) ? storeId : null
	};
}

function isSavedBody(value: unknown): value is string {
	return typeof value === 'string' && value.length > 0 && value.length <= MAX_SAVED_BODY_CHARS;
}

function sanitiseSavedList(value: unknown): SavedList | null {
	if (!isRecord(value)) return null;
	const { body, savedAt, lines } = value;
	if (!isSavedBody(body) || !isIsoDateTime(savedAt)) return null;
	if (!Array.isArray(lines) || lines.length > MAX_SAVED_LIST_LINES) return null;
	const valid = validListLines({ lines });
	return valid ? { body, savedAt, lines: valid } : null;
}

function sanitiseSavedQuote(value: unknown): SavedQuote | null {
	if (!isRecord(value)) return null;
	const { body, savedAt, dataDate, store } = value;
	if (!isSavedBody(body) || !isIsoDateTime(savedAt)) return null;
	if (typeof dataDate !== 'string' || !ISO_DATE.test(dataDate)) return null;
	if (!validStoreQuote(store) || !ID_PATTERNS.store.test(store.store_id)) return null;
	if (store.lines.length > MAX_SAVED_LIST_LINES) return null;
	return { body, savedAt, dataDate, store };
}

/** The cart: valid, unique goods with 0 < qty <= 1000 (rounded to 0.001), at most 100; invalid lines are dropped. */
/** Unique ingredient ids with a quantity 0 < qty <= MAX_CART_QTY (rounded to 3 decimals), at most `max`. */
function sanitiseQtyLines(value: unknown, max: number): StoredCartLine[] {
	const lines: StoredCartLine[] = [];
	const seen = new Set<string>();
	if (!Array.isArray(value)) return lines;
	for (const item of value) {
		if (lines.length >= max) break;
		if (!isRecord(item)) continue;
		const { ingredientId, qty } = item;
		if (typeof ingredientId !== 'string' || !ID_PATTERNS.ingredient.test(ingredientId) || seen.has(ingredientId)) {
			continue;
		}
		if (!isFiniteNumber(qty)) continue;
		const rounded = Math.round(qty * 1000) / 1000;
		if (!(rounded > 0 && rounded <= MAX_CART_QTY)) continue;
		seen.add(ingredientId);
		lines.push({ ingredientId, qty: rounded });
	}
	return lines;
}

function sanitiseCart(value: unknown): StoredCart {
	if (!isRecord(value)) return defaultState().cart;
	return {
		lines: sanitiseQtyLines(value.lines, MAX_CART_LINES),
		checked: idList(value.checked, ID_PATTERNS.ingredient, MAX_CART_LINES),
		storeId: typeof value.storeId === 'string' && ID_PATTERNS.store.test(value.storeId) ? value.storeId : null
	};
}

/** The list choices: a known range, and at most 12 valid entries with unique keys (the first one wins). */
function sanitiseList(value: unknown): StoredList {
	if (!isRecord(value)) return defaultState().list;
	const entries: ListEntry[] = [];
	const seen = new Set<string>();
	if (Array.isArray(value.entries)) {
		for (const item of value.entries) {
			if (entries.length >= MAX_LIST_ENTRIES) break;
			const entry = sanitiseListEntry(item);
			if (entry && !seen.has(entry.key)) {
				seen.add(entry.key);
				entries.push(entry);
			}
		}
	}
	return { range: isListRange(value.range) ? value.range : 'this_week', entries };
}

function sanitiseExclusions(value: unknown): StoredState['exclusions'] {
	if (!isRecord(value)) return defaultState().exclusions;
	const tags = idList(value.tags, /^[a-z_]{1,30}$/, MAX_EXCLUDED_TAGS).filter((tag): tag is RecipeTag =>
		(RECIPE_TAGS as readonly string[]).includes(tag)
	);
	return { tags, ingredients: idList(value.ingredients, ID_PATTERNS.ingredient, MAX_EXCLUDED_INGREDIENTS) };
}

function sanitiseApprox(value: unknown): ApproxPosition | null {
	if (!isRecord(value)) return null;
	const { lat, lon, at } = value;
	if (!isFiniteNumber(lat) || !isFiniteNumber(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
	if (!isIsoDateTime(at)) return null;
	return { lat: roundCoordinate(lat), lon: roundCoordinate(lon), at };
}

function sanitiseLocation(value: unknown): StoredLocation {
	const fallback = defaultState().location;
	if (!isRecord(value)) return fallback;
	const consent: LocationConsent =
		value.consent === 'granted' || value.consent === 'declined' ? value.consent : 'unset';
	const districtId = typeof value.districtId === 'string' && DISTRICT_ID.test(value.districtId) ? value.districtId : null;
	// A stored position without consent is dropped: consent is the precondition for keeping it.
	const approx = consent === 'granted' ? sanitiseApprox(value.approx) : null;
	const manual = sanitiseApprox(value.manual);
	let source: LocationSource =
		value.source === 'device' || value.source === 'district' || value.source === 'map' ? value.source : 'none';
	// A source whose data is missing falls back to another that has data, else to none.
	if (source === 'device' && approx === null) source = districtId !== null ? 'district' : manual !== null ? 'map' : 'none';
	if (source === 'district' && districtId === null) source = approx !== null ? 'device' : manual !== null ? 'map' : 'none';
	if (source === 'map' && manual === null) source = approx !== null ? 'device' : districtId !== null ? 'district' : 'none';
	return { consent, source, districtId, approx, manual };
}

/** Validates a version-1 document field by field; invalid fields fall back to their defaults. */
function sanitiseV1(raw: Record<string, unknown>): StoredState {
	const defaults = defaultState();
	return {
		version: STORAGE_VERSION,
		language: isLang(raw.language) ? raw.language : defaults.language,
		people: clampPeople(raw.people) ?? defaults.people,
		slots: raw.slots === 3 || raw.slots === 5 ? raw.slots : defaults.slots,
		radiusKm: normaliseRadius(raw.radiusKm) ?? defaults.radiusKm,
		plan: sanitisePlan(raw.plan),
		pantry: sanitisePantry(raw.pantry),
		exclusions: sanitiseExclusions(raw.exclusions),
		preferencesAsked: raw.preferencesAsked === true,
		location: sanitiseLocation(raw.location),
		// The global `checkedItems` of earlier builds is dropped: ticks are kept per list (ListEntry.checked).
		list: sanitiseList(raw.list),
		lastList: sanitiseSavedList(raw.lastList),
		lastQuote: sanitiseSavedQuote(raw.lastQuote),
		cart: sanitiseCart(raw.cart)
	};
}

/** Upgrade steps: MIGRATIONS[n] turns a version-n document into a version-(n+1) document. None yet. */
const MIGRATIONS: Readonly<Record<number, (raw: Record<string, unknown>) => Record<string, unknown>>> = {};

/** Any stored value -> a valid current-version state. Unknown versions reset to the defaults. */
export function migrate(raw: unknown): StoredState {
	if (!isRecord(raw) || !isFiniteNumber(raw.version) || !Number.isInteger(raw.version)) return defaultState();
	let doc = raw;
	let version = raw.version;
	while (version < STORAGE_VERSION) {
		const step = MIGRATIONS[version];
		if (!step) return defaultState();
		doc = step(doc);
		version += 1;
	}
	if (version !== STORAGE_VERSION) return defaultState();
	return sanitiseV1(doc);
}

// ───────────────────────────── localStorage access (never throws) ─────────────────────────────

let memory: StoredState | null = null;
/** True while `memory` holds changes that could not be written (they win over the stored copy). */
let unsaved = false;
let persistent = true;

function backend(): Storage | null {
	try {
		const storage = globalThis.localStorage;
		return storage ?? null;
	} catch {
		return null;
	}
}

function readRaw(): string | null | undefined {
	const storage = backend();
	if (!storage) return undefined;
	try {
		return storage.getItem(STORAGE_KEY);
	} catch {
		return undefined;
	}
}

function clone(state: StoredState): StoredState {
	return structuredClone(state);
}

/**
 * The current state. Reads localStorage (so changes made in another tab are seen); when it cannot be read,
 * or when this session holds changes that could not be written, the in-memory copy is used, else the
 * defaults. Always returns a fresh copy.
 */
export function load(): StoredState {
	if (unsaved && memory) return clone(memory);
	const raw = readRaw();
	if (raw === undefined) {
		persistent = false;
		return clone(memory ?? defaultState());
	}
	if (raw === null) {
		// Nothing stored (first visit, or cleared in another tab): the defaults, not a stale session copy.
		memory = null;
		return defaultState();
	}
	let parsed: unknown;
	try {
		parsed = JSON.parse(raw);
	} catch {
		parsed = null;
	}
	const state = migrate(parsed);
	memory = state;
	return clone(state);
}

/** Validates and stores `state`. Returns false when it could only be kept in memory. */
export function save(state: StoredState): boolean {
	const clean = migrate(state);
	memory = clean;
	const storage = backend();
	if (!storage) {
		persistent = false;
		unsaved = true;
		return false;
	}
	try {
		storage.setItem(STORAGE_KEY, JSON.stringify(clean));
		persistent = true;
		unsaved = false;
		return true;
	} catch {
		persistent = false;
		unsaved = true;
		return false;
	}
}

export type StatePatch = Partial<Omit<StoredState, 'version'>>;

/** Shallow-merges `patch` into the current state, validates and saves it, and returns the new state. */
export function update(patch: StatePatch): StoredState {
	const next: StoredState = { ...load(), ...patch, version: STORAGE_VERSION };
	save(next);
	return clone(memory ?? migrate(next));
}

/**
 * "Minden adat törlése": deletes every key this app owns and resets the in-memory copy. Returns false when
 * the stored copy could not be deleted (storage refused); the session then shows the defaults anyway, keeps
 * them in memory only (`isPersistent()` is false), and the next successful save overwrites the old copy.
 */
export function clearAll(): boolean {
	memory = null;
	unsaved = false;
	const storage = backend();
	let removed = false;
	if (storage) {
		try {
			const keys: string[] = [];
			for (let i = 0; i < storage.length; i += 1) {
				const key = storage.key(i);
				if (key !== null && key.startsWith(STORAGE_PREFIX)) keys.push(key);
			}
			for (const key of keys) storage.removeItem(key);
			removed = true;
		} catch {
			removed = false;
		}
	}
	if (!removed) {
		// The old copy may still be readable: the defaults in memory win over it for the rest of the session.
		memory = defaultState();
		unsaved = true;
		persistent = false;
	}
	return removed;
}

/**
 * Calls `onchange` with the new state whenever ANOTHER tab changes or deletes the stored document (the
 * browser's `storage` event; it never fires for this tab's own writes). The in-memory copy is dropped first,
 * so the next `load()` reads what the other tab stored. Returns the unsubscribe function. Never throws.
 */
export function onExternalChange(onchange: (state: StoredState) => void): () => void {
	const target = typeof window === 'undefined' ? null : window;
	if (!target) return () => {};
	const listener = (event: StorageEvent): void => {
		try {
			// key null: the other tab called localStorage.clear().
			if (event.key !== null && event.key !== STORAGE_KEY) return;
			if (event.storageArea !== null && event.storageArea !== backend()) return;
			memory = null;
			unsaved = false;
			onchange(load());
		} catch {
			// A failing subscriber must not break the other tabs' writes or this page.
		}
	};
	try {
		target.addEventListener('storage', listener);
	} catch {
		return () => {};
	}
	return () => {
		try {
			target.removeEventListener('storage', listener);
		} catch {
			// nothing to undo
		}
	};
}

/** False after a read or write failed: the data is then kept only until the tab is closed. */
export function isPersistent(): boolean {
	return persistent;
}

/** Test hook: forget the in-memory copy and the persistence flag. */
export function resetForTests(): void {
	memory = null;
	unsaved = false;
	persistent = true;
}
