/**
 * What the "Hol vásárolj?" card shows, from a POST /api/quote answer, the store list and the starting point
 * (all on the device). Pure, so the page logic is tested without a browser.
 */
import type { QuoteResponse, StoreId, StoreOut } from '../api/types';
import type { LatLon } from '../geo';
import {
	planShopping,
	type JourneyOptions,
	type JourneyStore,
	type ShoppingOptions,
	type ShoppingPlan
} from './journey';

export interface StopView {
	storeId: StoreId;
	chain: string;
	point: LatLon;
	/** 1, 2, 3 in walking order. */
	number: number;
	items: string[];
	subtotal: number;
	legKm: number;
}

export interface SingleView {
	storeId: StoreId;
	chain: string;
	point: LatLon;
	total: number;
	/** Lines this store lacks that some other nearby store sells. */
	missing: string[];
	routeKm: number;
}

export interface JourneyView {
	stops: StopView[];
	total: number;
	/** Lines the route lacks that some other nearby store sells (only possible when maxStops is reached). */
	missing: string[];
	routeKm: number;
	returnKm: number;
	/** How many more lines than the single store (≥ 0). */
	moreItems: number;
	/** single total − route total, Ft (negative when the route buys more and so costs more). */
	saving: number;
	/** route km − single store round trip km. */
	extraKm: number;
}

export interface OptionsView {
	/** The quoted lines, in the order of the request. */
	lineIds: string[];
	/** Lines no nearby store prices (not sold, no price, or only a KSH estimate). */
	nowhere: string[];
	single: SingleView | null;
	journey: JourneyView | null;
	/** With no journey: what the best multi-store route would have saved (same coverage), when it would. */
	notWorth: { saving: number } | null;
}

/** The checkout cost of every priced line, per quoted store with coordinates. */
export function journeyStores(quote: QuoteResponse, stores: ReadonlyMap<StoreId, StoreOut>): JourneyStore[] {
	const out: JourneyStore[] = [];
	for (const quoted of quote.stores) {
		const info = stores.get(quoted.store_id);
		if (!info || info.lat === null || info.lon === null) continue;
		const costs = new Map<string, number>();
		for (const line of quoted.lines) {
			if (line.status === 'priced' && line.checkout_cost !== null && Number.isFinite(line.checkout_cost)) {
				costs.set(line.ingredient_id, line.checkout_cost);
			}
		}
		out.push({ id: quoted.store_id, point: { lat: info.lat, lon: info.lon }, costs });
	}
	return out;
}

function lineOrder(quote: QuoteResponse): string[] {
	const seen = new Set<string>();
	for (const store of quote.stores) for (const line of store.lines) seen.add(line.ingredient_id);
	return [...seen];
}

export function shoppingView(
	quote: QuoteResponse,
	stores: ReadonlyMap<StoreId, StoreOut>,
	origin: LatLon,
	options: Partial<JourneyOptions> = {}
): OptionsView | null {
	const candidates = journeyStores(quote, stores);
	const lineIds = lineOrder(quote);
	let planned: ShoppingOptions;
	try {
		planned = planShopping(origin, lineIds, candidates, options);
	} catch {
		return null; // an invalid starting point: nothing to show (never a wrong answer)
	}
	const sold = new Set(candidates.flatMap((store) => [...store.costs.keys()]));
	const nowhere = lineIds.filter((id) => !sold.has(id));
	const elsewhere = (missing: readonly string[]): string[] => missing.filter((id) => sold.has(id));
	const chainOf = new Map(quote.stores.map((store) => [store.store_id, store.chain]));
	const pointOf = new Map(candidates.map((store) => [store.id, store.point]));

	const singleStop = planned.single?.stops[0];
	const single: SingleView | null =
		planned.single && singleStop
			? {
					storeId: singleStop.storeId,
					chain: chainOf.get(singleStop.storeId) ?? '',
					point: pointOf.get(singleStop.storeId) as LatLon,
					total: planned.single.total,
					missing: elsewhere(planned.single.missing),
					routeKm: planned.single.routeKm
				}
			: null;

	const journeyOf = (plan: ShoppingPlan): JourneyView => ({
		stops: plan.stops.map((stop, index) => ({
			storeId: stop.storeId,
			chain: chainOf.get(stop.storeId) ?? '',
			point: pointOf.get(stop.storeId) as LatLon,
			number: index + 1,
			items: stop.items,
			subtotal: stop.subtotal,
			legKm: stop.legKm
		})),
		total: plan.total,
		missing: elsewhere(plan.missing),
		routeKm: plan.routeKm,
		returnKm: plan.returnKm,
		moreItems: planned.single ? planned.single.missing.length - plan.missing.length : 0,
		saving: planned.single ? planned.single.total - plan.total : 0,
		extraKm: planned.single ? plan.routeKm - planned.single.routeKm : plan.routeKm
	});

	let notWorth: OptionsView['notWorth'] = null;
	if (!planned.journey && planned.single && planned.bestMulti) {
		const multi = planned.bestMulti;
		const saving = planned.single.total - multi.total;
		if (multi.missing.length === planned.single.missing.length && saving >= 1) notWorth = { saving };
		else if (multi.missing.length === planned.single.missing.length) notWorth = { saving: 0 };
	}

	return {
		lineIds,
		nowhere,
		single,
		journey: planned.journey ? journeyOf(planned.journey) : null,
		notWorth
	};
}

/** A link that shows the store's public position on OpenStreetMap (opened by the user, in a new tab). */
export function osmLink(point: LatLon): string {
	const lat = point.lat.toFixed(5);
	const lon = point.lon.toFixed(5);
	return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=18/${lat}/${lon}`;
}
