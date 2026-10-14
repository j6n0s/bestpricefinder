/**
 * Where to buy a basket: the best SINGLE store and the best JOURNEY through up to three nearby stores.
 *
 * Computed ON THE DEVICE from the POST /api/quote answer (only store ids were sent) and the stores' public
 * coordinates; the starting point (the rounded device position or a district centre) never leaves the browser.
 *
 * - A line can be bought at a store when the store prices it (`status: "priced"` with a checkout cost).
 * - A plan buys every line at the cheapest of its stores and walks origin → stops → origin (as the crow flies;
 *   the order of the stops is the shortest round trip, found by trying every order).
 * - Plans are compared by, in this order:
 *   1. fewer lines that none of the plan's stores sells (getting everything matters most);
 *   2. the lower SCORE = checkout total + `perKmFt` × route km + `extraStopFt` × (stops − 1), so an extra stop
 *      has to pay for itself (default: 500 Ft per extra store and 150 Ft per km walked);
 *   3. the shorter route, then fewer stops;
 *   4. the stores' coordinates (south first, then west): a neutral, repeatable order. Ties are NEVER broken
 *      by chain or store name (BUILD-BRIEF §4.1 trap 13).
 * - `single`: the best plan with one store. `journey`: the best plan overall when it has two or more stops
 *   (otherwise one store is best and `journey` is null; `bestMulti` then says what the best multi-store plan
 *   would have saved, so the page can explain why no journey is suggested).
 */
import { haversineKm, type LatLon } from '../geo';

export interface JourneyStore {
	id: string;
	point: LatLon;
	/** Checkout cost per line id, for the lines this store PRICES (no entry: not sold or no price). */
	costs: ReadonlyMap<string, number>;
}

export interface JourneyOptions {
	/** At most this many stores in one plan (1–4). */
	maxStops: number;
	/** What one extra store has to save, in Ft. */
	extraStopFt: number;
	/** What one extra km of walking has to save, in Ft. */
	perKmFt: number;
}

export const DEFAULT_JOURNEY_OPTIONS: Readonly<JourneyOptions> = { maxStops: 3, extraStopFt: 500, perKmFt: 150 };

/** The hard upper bound of `maxStops`: 25 stores choose 4 is 12,650 plans, each with 24 orders. */
export const MAX_JOURNEY_STOPS = 4;

export interface StopPlan {
	storeId: string;
	/** The line ids bought here, in the order of the input lines. */
	items: string[];
	subtotal: number;
	/** Distance from the previous point (the origin for the first stop), km. */
	legKm: number;
}

export interface ShoppingPlan {
	/** In walking order. */
	stops: StopPlan[];
	total: number;
	/** Line ids none of the stops sells, in the order of the input lines. */
	missing: string[];
	/** origin → stops → origin, km. */
	routeKm: number;
	/** The last stop → origin, km. */
	returnKm: number;
	/** total + perKmFt × routeKm + extraStopFt × (stops − 1). */
	score: number;
}

export interface ShoppingOptions {
	single: ShoppingPlan | null;
	/** Null when one store is best (or fewer than two stores can be compared). */
	journey: ShoppingPlan | null;
	/** With `journey` null: the best plan with two or more stops, if any, for the explanation. */
	bestMulti: ShoppingPlan | null;
}

const EPSILON = 1e-6;

interface Prepared {
	id: string;
	point: LatLon;
	fromOrigin: number;
	/** Cost per input line (Infinity: cannot be bought here). */
	cost: Float64Array;
}

function validPoint(point: LatLon): boolean {
	return (
		Number.isFinite(point.lat) && Number.isFinite(point.lon) && Math.abs(point.lat) <= 90 && Math.abs(point.lon) <= 180
	);
}

/** Stores with a valid position and at least one priced line, each id once (the first one wins). */
function prepare(origin: LatLon, lineIds: readonly string[], stores: readonly JourneyStore[]): Prepared[] {
	const seen = new Set<string>();
	const out: Prepared[] = [];
	for (const store of stores) {
		if (seen.has(store.id) || !validPoint(store.point)) continue;
		seen.add(store.id);
		const cost = new Float64Array(lineIds.length).fill(Infinity);
		let any = false;
		lineIds.forEach((lineId, index) => {
			const value = store.costs.get(lineId);
			if (value !== undefined && Number.isFinite(value) && value >= 0) {
				cost[index] = value;
				any = true;
			}
		});
		if (any) out.push({ id: store.id, point: store.point, fromOrigin: haversineKm(origin, store.point), cost });
	}
	return out;
}

/** -1/0/1 comparing two stores by position only (south first, then west). */
function byPosition(a: Prepared, b: Prepared): number {
	return a.point.lat - b.point.lat || a.point.lon - b.point.lon;
}

function permutations<T>(items: readonly T[]): T[][] {
	if (items.length <= 1) return [items.slice()];
	const out: T[][] = [];
	items.forEach((item, index) => {
		const rest = items.filter((_, other) => other !== index);
		for (const tail of permutations(rest)) out.push([item, ...tail]);
	});
	return out;
}

interface Route {
	/** The stores in walking order, each with the distance from the previous point. */
	legs: { store: Prepared; km: number }[];
	/** The last store → origin. */
	back: number;
	length: number;
}

/** -1/0/1 comparing two walking orders by the stores' positions, stop by stop. */
function compareOrders(a: Route, b: Route): number {
	for (const [index, leg] of a.legs.entries()) {
		const other = b.legs[index];
		if (!other) return 0;
		const diff = byPosition(leg.store, other.store);
		if (diff !== 0) return diff;
	}
	return 0;
}

/** The shortest round trip origin → stores → origin; equal lengths: the first stop nearer, then by position. */
function bestRoute(origin: LatLon, stores: readonly Prepared[]): Route {
	let best: Route | null = null;
	for (const order of permutations(stores)) {
		const legs: Route['legs'] = [];
		let previous = origin;
		for (const store of order) {
			legs.push({ store, km: haversineKm(previous, store.point) });
			previous = store.point;
		}
		const back = haversineKm(previous, origin);
		const route: Route = { legs, back, length: legs.reduce((sum, leg) => sum + leg.km, 0) + back };
		if (best === null || route.length < best.length - EPSILON) {
			best = route;
		} else if (Math.abs(route.length - best.length) <= EPSILON) {
			const byFirst = (route.legs[0]?.store.fromOrigin ?? 0) - (best.legs[0]?.store.fromOrigin ?? 0);
			if (byFirst < -EPSILON || (Math.abs(byFirst) <= EPSILON && compareOrders(route, best) < 0)) best = route;
		}
	}
	if (best === null) throw new Error('bestRoute needs at least one store');
	return best;
}

/** True when buying a line at `store` for `value` beats `current` at `currentValue`: cheaper, else nearer the
 * origin, else by position (never by name). */
function prefer(store: Prepared, value: number, current: Prepared, currentValue: number): boolean {
	const diff = value - currentValue;
	if (diff < -EPSILON) return true;
	if (diff > EPSILON) return false;
	const nearer = store.fromOrigin - current.fromOrigin;
	if (nearer < -EPSILON) return true;
	if (nearer > EPSILON) return false;
	return byPosition(store, current) < 0;
}

/** One plan for the stores of `subset`, or null when one of them would buy nothing (a dominated plan). */
function evaluate(
	origin: LatLon,
	lineIds: readonly string[],
	subset: readonly Prepared[],
	options: JourneyOptions
): ShoppingPlan | null {
	const bought = new Map<string, { items: string[]; subtotal: number }>(
		subset.map((store) => [store.id, { items: [], subtotal: 0 }])
	);
	const missing: string[] = [];
	for (const [line, lineId] of lineIds.entries()) {
		let best: Prepared | null = null;
		let bestValue = Infinity;
		for (const store of subset) {
			const value = store.cost[line] ?? Infinity;
			if (!Number.isFinite(value)) continue;
			if (best === null || prefer(store, value, best, bestValue)) {
				best = store;
				bestValue = value;
			}
		}
		const slot = best === null ? undefined : bought.get(best.id);
		if (slot === undefined) {
			missing.push(lineId);
		} else {
			slot.items.push(lineId);
			slot.subtotal += bestValue;
		}
	}
	if ([...bought.values()].some((slot) => slot.items.length === 0)) return null;
	const route = bestRoute(origin, subset);
	const stops: StopPlan[] = route.legs.map(({ store, km }) => {
		const slot = bought.get(store.id) ?? { items: [], subtotal: 0 };
		return { storeId: store.id, items: slot.items, subtotal: slot.subtotal, legKm: km };
	});
	const total = stops.reduce((sum, stop) => sum + stop.subtotal, 0);
	const score = total + options.perKmFt * route.length + options.extraStopFt * (subset.length - 1);
	return { stops, total, missing, routeKm: route.length, returnKm: route.back, score };
}

/** Negative when `a` is the better plan (see the module comment for the order). */
export function comparePlans(a: ShoppingPlan, b: ShoppingPlan, positions: ReadonlyMap<string, LatLon>): number {
	if (a.missing.length !== b.missing.length) return a.missing.length - b.missing.length;
	if (Math.abs(a.score - b.score) > EPSILON) return a.score - b.score;
	if (Math.abs(a.routeKm - b.routeKm) > EPSILON) return a.routeKm - b.routeKm;
	if (a.stops.length !== b.stops.length) return a.stops.length - b.stops.length;
	const key = (plan: ShoppingPlan): LatLon[] =>
		plan.stops
			.map((stop) => positions.get(stop.storeId) as LatLon)
			.slice()
			.sort((x, y) => x.lat - y.lat || x.lon - y.lon);
	const kb = key(b);
	for (const [index, pa] of key(a).entries()) {
		const pb = kb[index];
		if (!pb) return 0;
		const diff = pa.lat - pb.lat || pa.lon - pb.lon;
		if (diff !== 0) return diff;
	}
	return 0;
}

function* subsets<T>(items: readonly T[], size: number, start = 0, prefix: T[] = []): Generator<T[]> {
	if (prefix.length === size) {
		yield prefix.slice();
		return;
	}
	for (let index = start; index <= items.length - (size - prefix.length); index++) {
		prefix.push(items[index] as T); // index < items.length: never undefined
		yield* subsets(items, size, index + 1, prefix);
		prefix.pop();
	}
}

function checkedOptions(options: Partial<JourneyOptions>): JourneyOptions {
	const merged = { ...DEFAULT_JOURNEY_OPTIONS, ...options };
	const maxStops = Math.trunc(merged.maxStops);
	if (!(maxStops >= 1 && maxStops <= MAX_JOURNEY_STOPS)) throw new RangeError('maxStops must be 1–4');
	if (!(Number.isFinite(merged.extraStopFt) && merged.extraStopFt >= 0)) throw new RangeError('extraStopFt');
	if (!(Number.isFinite(merged.perKmFt) && merged.perKmFt >= 0)) throw new RangeError('perKmFt');
	return { maxStops, extraStopFt: merged.extraStopFt, perKmFt: merged.perKmFt };
}

/**
 * The best single store and the best journey for the lines `lineIds` (unique ids, in display order).
 * Throws RangeError for an invalid origin or options.
 */
export function planShopping(
	origin: LatLon,
	lineIds: readonly string[],
	stores: readonly JourneyStore[],
	options: Partial<JourneyOptions> = {}
): ShoppingOptions {
	if (!validPoint(origin)) throw new RangeError('origin is not a valid latitude/longitude');
	const opts = checkedOptions(options);
	const uniqueLines = [...new Set(lineIds)];
	const prepared = prepare(origin, uniqueLines, stores);
	const positions = new Map(prepared.map((store) => [store.id, store.point]));
	let single: ShoppingPlan | null = null;
	let best: ShoppingPlan | null = null;
	let bestMulti: ShoppingPlan | null = null;
	const maxSize = Math.min(opts.maxStops, prepared.length);
	for (let size = 1; size <= maxSize; size++) {
		for (const subset of subsets(prepared, size)) {
			const plan = evaluate(origin, uniqueLines, subset, opts);
			if (plan === null) continue;
			if (size === 1 && (single === null || comparePlans(plan, single, positions) < 0)) single = plan;
			if (size >= 2 && (bestMulti === null || comparePlans(plan, bestMulti, positions) < 0)) bestMulti = plan;
			if (best === null || comparePlans(plan, best, positions) < 0) best = plan;
		}
	}
	const journey = best !== null && best.stops.length >= 2 ? best : null;
	return { single, journey, bestMulti: journey === null ? bestMulti : null };
}

/** What a journey saves against the single store, in Ft (positive = cheaper), or null without both. */
export function journeySaving(options: ShoppingOptions): number | null {
	if (!options.single || !options.journey) return null;
	return options.single.total - options.journey.total;
}
