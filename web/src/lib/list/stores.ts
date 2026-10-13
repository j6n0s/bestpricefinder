/**
 * Candidate stores for "Hol a legolcsóbb a közelben?", chosen ON THE DEVICE (BUILD-BRIEF §6.3, §8.8): the
 * nearest grocery stores with price data within the radius, at most 3 per chain and 25 in all (the
 * /api/quote limit). Only the store ids leave the device; the distances stay here.
 */
import type { ChainSlug, StoreId, StoreOut } from '../api/types';
import { pickNearestPerChain, storesWithinRadius, type LatLon, type StoreDistance } from '../geo';
import { RADIUS_MAX_KM, RADIUS_STEP_KM } from '../storage';

export const MAX_STORES_PER_CHAIN = 3;
/** Fewer stores than this in range: suggest a wider radius (a ranking needs something to compare). */
export const MIN_STORES_TO_COMPARE = 2;

export interface Candidates {
	/** Nearest first. */
	picks: StoreDistance[];
	/** Fewer than MIN_STORES_TO_COMPARE stores: the page suggests a wider radius. */
	tooFew: boolean;
	/** Grocery stores in range that are hidden because they have no price data ("nincs áradat"). */
	withoutData: number;
}

export function nearbyCandidates(
	origin: LatLon,
	stores: readonly StoreOut[],
	radiusKm: number,
	groceryChains: ReadonlySet<ChainSlug>
): Candidates {
	const picks = pickNearestPerChain(origin, stores, {
		radiusKm,
		maxPerChain: MAX_STORES_PER_CHAIN,
		groceryOnly: true,
		hasDataOnly: true,
		groceryChains
	});
	const withoutData = storesWithinRadius(origin, stores, radiusKm).filter(
		({ store }) => groceryChains.has(store.chain) && !store.has_data
	).length;
	return { picks, tooFew: picks.length < MIN_STORES_TO_COMPARE, withoutData };
}

/** The next radius step up (0.5 km), or null at the maximum (5 km). */
export function widerRadius(radiusKm: number): number | null {
	if (!Number.isFinite(radiusKm)) return null;
	const next = Math.round((radiusKm + RADIUS_STEP_KM) / RADIUS_STEP_KM) * RADIUS_STEP_KM;
	return next <= RADIUS_MAX_KM ? next : null;
}

/** store id -> distance in km (kept on the device, used to label and to order ties). */
export function distanceMap(picks: readonly StoreDistance[]): Map<StoreId, number> {
	return new Map(picks.map((pick) => [pick.store.id, pick.distanceKm]));
}

/** "1051 Budapest, Minta utca 1." from the parts that exist ("" when none). */
export function storeAddress(store: Pick<StoreOut, 'postal_code' | 'city' | 'address'> | undefined): string {
	if (!store) return '';
	const place = [store.postal_code, store.city].filter((part): part is string => Boolean(part?.trim())).join(' ');
	return [place, store.address?.trim() ?? ''].filter((part) => part.length > 0).join(', ');
}

/** A chain's display name from /api/meta, or its slug when the name is not known (plain text, no logo). */
export function chainLabel(slug: ChainSlug, names: ReadonlyMap<ChainSlug, string>): string {
	return names.get(slug) ?? slug;
}

export function chainNames(chains: readonly { slug: ChainSlug; name: string }[] | null | undefined): Map<ChainSlug, string> {
	return new Map((chains ?? []).map((chain) => [chain.slug, chain.name]));
}
