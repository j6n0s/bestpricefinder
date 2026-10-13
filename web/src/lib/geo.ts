/**
 * Distances and nearby-store selection, computed ON THE DEVICE (BUILD-BRIEF §6.3, §8.8).
 * Coordinates never leave the browser: only the selected store ids are sent to /api/quote.
 */
import type { ChainSlug, StoreOut } from './api/types';

/** Mean Earth radius (IUGG), km. */
export const EARTH_RADIUS_KM = 6371.0088;

/** The six GVH grocery chains; used when /api/meta (ChainOut.is_grocery) is not available. */
export const DEFAULT_GROCERY_CHAINS: ReadonlySet<ChainSlug> = new Set(['aldi', 'auchan', 'lidl', 'penny', 'spar', 'tesco']);

/** /api/quote accepts at most 25 store ids. */
export const MAX_QUOTE_STORES = 25;

export interface LatLon {
	lat: number;
	lon: number;
}

export interface StoreDistance {
	store: StoreOut;
	distanceKm: number;
}

function assertLatLon(point: LatLon, name: string): void {
	if (!Number.isFinite(point.lat) || !Number.isFinite(point.lon) || Math.abs(point.lat) > 90 || Math.abs(point.lon) > 180) {
		throw new RangeError(`${name} is not a valid latitude/longitude`);
	}
}

const toRad = (deg: number): number => (deg * Math.PI) / 180;

/** Great-circle distance in km (haversine formula). Throws RangeError for invalid coordinates. */
export function haversineKm(a: LatLon, b: LatLon): number {
	assertLatLon(a, 'a');
	assertLatLon(b, 'b');
	const dLat = toRad(b.lat - a.lat);
	const dLon = toRad(b.lon - a.lon);
	const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
	// Clamp: rounding can push h a hair above 1 for antipodal points, and asin(>1) is NaN.
	return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h))));
}

function storePoint(store: StoreOut): LatLon | null {
	const { lat, lon } = store;
	if (lat === null || lon === null || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;
	if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
	return { lat, lon };
}

function byDistanceThenId(x: StoreDistance, y: StoreDistance): number {
	return x.distanceKm - y.distanceKm || (x.store.id < y.store.id ? -1 : x.store.id > y.store.id ? 1 : 0);
}

/**
 * Stores whose distance from `origin` is at most `radiusKm` (inclusive), nearest first (ties: store id).
 * Stores without valid coordinates are skipped.
 */
export function storesWithinRadius(origin: LatLon, stores: readonly StoreOut[], radiusKm: number): StoreDistance[] {
	assertLatLon(origin, 'origin');
	if (!Number.isFinite(radiusKm) || radiusKm < 0) throw new RangeError('radiusKm must be a finite number >= 0');
	const out: StoreDistance[] = [];
	for (const store of stores) {
		const point = storePoint(store);
		if (point === null) continue;
		const distanceKm = haversineKm(origin, point);
		if (distanceKm <= radiusKm) out.push({ store, distanceKm });
	}
	return out.sort(byDistanceThenId);
}

export interface PickOptions {
	radiusKm: number;
	/** At most this many stores per chain (default 3). */
	maxPerChain?: number;
	/** At most this many stores in total (default 25, the /api/quote limit; larger values are capped). */
	maxTotal?: number;
	/** Keep only grocery chains (default true). */
	groceryOnly?: boolean;
	/** Drop stores with `has_data: false` (default true). */
	hasDataOnly?: boolean;
	/** Grocery chain slugs, normally from /api/meta `chains[].is_grocery`; defaults to DEFAULT_GROCERY_CHAINS. */
	groceryChains?: ReadonlySet<ChainSlug>;
}

function positiveInt(value: number, name: string): number {
	if (!Number.isInteger(value) || value < 1) throw new RangeError(`${name} must be an integer >= 1`);
	return value;
}

/**
 * The N nearest stores per chain within the radius (BUILD-BRIEF §6.3), at most `maxTotal` in all.
 *
 * When the per-chain picks exceed `maxTotal`, every chain's nearest store is kept before any chain's second
 * nearest, and so on (round-robin by rank within the chain, nearer first within a round), so a dense chain
 * cannot crowd the others out. The result is sorted nearest first (ties: store id).
 */
export function pickNearestPerChain(origin: LatLon, stores: readonly StoreOut[], options: PickOptions): StoreDistance[] {
	const maxPerChain = positiveInt(options.maxPerChain ?? 3, 'maxPerChain');
	const maxTotal = Math.min(positiveInt(options.maxTotal ?? MAX_QUOTE_STORES, 'maxTotal'), MAX_QUOTE_STORES);
	const groceryOnly = options.groceryOnly ?? true;
	const hasDataOnly = options.hasDataOnly ?? true;
	const grocery = options.groceryChains ?? DEFAULT_GROCERY_CHAINS;

	const candidates = storesWithinRadius(origin, stores, options.radiusKm).filter(
		({ store }) => (!groceryOnly || grocery.has(store.chain)) && (!hasDataOnly || store.has_data)
	);

	const rankInChain = new Map<ChainSlug, number>();
	const ranked: { pick: StoreDistance; rank: number }[] = [];
	for (const pick of candidates) {
		const rank = rankInChain.get(pick.store.chain) ?? 0;
		if (rank >= maxPerChain) continue;
		rankInChain.set(pick.store.chain, rank + 1);
		ranked.push({ pick, rank });
	}

	ranked.sort((x, y) => x.rank - y.rank || byDistanceThenId(x.pick, y.pick));
	return ranked
		.slice(0, maxTotal)
		.map(({ pick }) => pick)
		.sort(byDistanceThenId);
}

/** Grocery chain slugs from /api/meta chains, or the default six when the list is empty. */
export function groceryChainSet(chains: readonly { slug: ChainSlug; is_grocery: boolean }[]): ReadonlySet<ChainSlug> {
	const slugs = chains.filter((chain) => chain.is_grocery).map((chain) => chain.slug);
	return slugs.length > 0 ? new Set(slugs) : DEFAULT_GROCERY_CHAINS;
}
