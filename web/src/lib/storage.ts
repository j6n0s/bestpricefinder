/**
 * The ONE place where personal data is kept: the browser's localStorage, on this device only.
 *
 * Nothing in here is ever sent to the server as a whole. Plan, household size, slots, radius, pantry,
 * exclusions (diet preferences are health data, GDPR Art. 9), location consent, the chosen district or the
 * approximate location, checked list items and the UI language all live under one key, as one versioned
 * JSON document.
 *
 * Robustness rules:
 * - Every localStorage access is wrapped in try/catch: private browsing, disabled site data, a full quota
 *   or a sandboxed frame must never break the app. When saving fails, the state lives on in memory for this
 *   session and `isPersistent()` turns false so the UI can say so.
 * - Reading never trusts the stored JSON: every field is validated and replaced by its default when invalid.
 * - An unknown `version` (newer, older without a migration, or missing) resets everything to the defaults.
 *
 * Schema changes: adding a field with a default needs no version bump (sanitising fills it in). Changing the
 * meaning or shape of a field needs `STORAGE_VERSION + 1` and a migration step in `MIGRATIONS`.
 */
import { ID_PATTERNS, RECIPE_TAGS, SLOTS, type PlanDayIO, type RecipeTag, type Slot } from './api/types';

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
const MAX_EXCLUDED_TAGS = 20;
const MAX_EXCLUDED_INGREDIENTS = 50;
const MAX_CHECKED = 500;
const MAX_PLAN_DAYS = 31;
const DISTRICT_ID = /^(0[1-9]|1\d|2[0-3])$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export interface PantryEntry {
	ingredientId: string;
	/** Quantity at home in the ingredient's canonical unit; null = "enough at home". */
	qty: number | null;
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
export type LocationSource = 'none' | 'device' | 'district';

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
}

export interface StoredState {
	version: typeof STORAGE_VERSION;
	language: Lang;
	people: number;
	slots: 3 | 5;
	radiusKm: number;
	plan: StoredPlan | null;
	pantry: {
		/** Ingredients the user has at home. */
		onHand: PantryEntry[];
		/** Pantry staples ("valószínűleg otthon van") the user marked "nincs otthon". */
		notAtHome: string[];
	};
	exclusions: {
		tags: RecipeTag[];
		ingredients: string[];
	};
	location: StoredLocation;
	/** Ingredient ids ticked off on the shopping list. */
	checkedItems: string[];
}

export function defaultState(): StoredState {
	return {
		version: STORAGE_VERSION,
		language: 'hu',
		people: 2,
		slots: 3,
		radiusKm: 1.5,
		plan: null,
		pantry: { onHand: [], notAtHome: [] },
		exclusions: { tags: [], ingredients: [] },
		location: { consent: 'unset', source: 'none', districtId: null, approx: null },
		checkedItems: []
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
	const onHand: PantryEntry[] = [];
	const seen = new Set<string>();
	if (Array.isArray(value.onHand)) {
		for (const entry of value.onHand) {
			if (onHand.length >= MAX_LIST) break;
			if (!isRecord(entry)) continue;
			const { ingredientId, qty } = entry;
			if (typeof ingredientId !== 'string' || !ID_PATTERNS.ingredient.test(ingredientId) || seen.has(ingredientId)) {
				continue;
			}
			if (qty !== null && !(isFiniteNumber(qty) && qty > 0 && qty <= 1000)) continue;
			seen.add(ingredientId);
			onHand.push({ ingredientId, qty });
		}
	}
	return { onHand, notAtHome: idList(value.notAtHome, ID_PATTERNS.ingredient, MAX_LIST) };
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
	let source: LocationSource = value.source === 'device' || value.source === 'district' ? value.source : 'none';
	if (source === 'device' && approx === null) source = districtId !== null ? 'district' : 'none';
	if (source === 'district' && districtId === null) source = approx !== null ? 'device' : 'none';
	return { consent, source, districtId, approx };
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
		location: sanitiseLocation(raw.location),
		checkedItems: idList(raw.checkedItems, ID_PATTERNS.ingredient, MAX_CHECKED)
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

/** Deletes every key this app owns ("minden adat törlése"). The next load() returns the defaults. */
export function clearAll(): boolean {
	memory = null;
	unsaved = false;
	const storage = backend();
	if (!storage) return false;
	try {
		const keys: string[] = [];
		for (let i = 0; i < storage.length; i += 1) {
			const key = storage.key(i);
			if (key !== null && key.startsWith(STORAGE_PREFIX)) keys.push(key);
		}
		for (const key of keys) storage.removeItem(key);
		return true;
	} catch {
		return false;
	}
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
