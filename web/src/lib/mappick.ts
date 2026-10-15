/**
 * The map picker's geography ("Pont választása a térképen", MapPicker.svelte): what the on-device schematic map
 * shows (a centre and a width in km), how it zooms, and how a picked point is described in words. No map
 * tiles and no request to any other site (the CSP allows none): the landmarks are the stores' positions
 * (GET /api/stores, public data) and the Budapest districts' centroids. Pure helpers.
 */
import type { StoreOut } from './api/types';
import { DISTRICTS, type District } from './districts';
import { EARTH_RADIUS_KM, haversineKm, type LatLon } from './geo';

export interface MapView {
	centre: LatLon;
	/** Kilometres across the map's width. */
	spanKm: number;
}

/** Zoom limits: a few streets, and the whole country with room to spare. */
export const MIN_SPAN_KM = 0.5;
export const MAX_SPAN_KM = 1000;
/** Width : height of the picker's map. */
export const VIEW_ASPECT = 4 / 3;
/** A tap on the map is accurate to about 1/400 of the width: zoom in from here before picking finely. */
export const FINE_SPAN_KM = 4;
/** District labels are shown up to this width; store labels up to `STORE_LABEL_SPAN_KM`. */
export const DISTRICT_LABEL_SPAN_KM = 60;
export const STORE_LABEL_SPAN_KM = 3;

const KM_PER_DEGREE = (EARTH_RADIUS_KM * Math.PI) / 180;

/** A view that shows every point (at least one), with a margin, at least `minSpanKm` wide. */
export function fitView(points: readonly LatLon[], minSpanKm = MIN_SPAN_KM, margin = 1.15): MapView {
	if (points.length === 0) throw new RangeError('fitView needs at least one point');
	const lats = points.map((p) => p.lat);
	const lons = points.map((p) => p.lon);
	const centre = { lat: (Math.min(...lats) + Math.max(...lats)) / 2, lon: (Math.min(...lons) + Math.max(...lons)) / 2 };
	const kmPerLon = KM_PER_DEGREE * Math.cos((centre.lat * Math.PI) / 180);
	const widthKm = (Math.max(...lons) - Math.min(...lons)) * kmPerLon;
	const heightKm = (Math.max(...lats) - Math.min(...lats)) * KM_PER_DEGREE;
	const spanKm = Math.max(minSpanKm, widthKm, heightKm * VIEW_ASPECT) * margin;
	return { centre, spanKm: clampSpan(spanKm) };
}

export function clampSpan(spanKm: number): number {
	if (!Number.isFinite(spanKm)) return MAX_SPAN_KM;
	return Math.min(MAX_SPAN_KM, Math.max(MIN_SPAN_KM, spanKm));
}

/** Budapest: the districts' centroids with a margin (about 30 km across). */
export const BUDAPEST_VIEW: Readonly<MapView> = Object.freeze(fitView(DISTRICTS, 20, 1.2));

/** The stores that have a position. */
export function storePoints(stores: readonly Pick<StoreOut, 'lat' | 'lon'>[]): LatLon[] {
	return stores.flatMap((store) =>
		store.lat !== null && store.lon !== null && Number.isFinite(store.lat) && Number.isFinite(store.lon)
			? [{ lat: store.lat, lon: store.lon }]
			: []
	);
}

/** The whole store network (every store with a position); Budapest when there is none. */
export function countryView(stores: readonly Pick<StoreOut, 'lat' | 'lon'>[]): MapView {
	const points = storePoints(stores);
	return points.length > 0 ? fitView(points, 50, 1.1) : { ...BUDAPEST_VIEW };
}

/** The view `factor` times wider (2) or narrower (0.5), centred on `around` when given. */
export function zoomView(view: MapView, factor: number, around: LatLon | null = null): MapView {
	return { centre: around ?? view.centre, spanKm: clampSpan(view.spanKm * factor) };
}

/** `point` moved by `dx` steps east and `dy` steps north, a step being 1/20 of the view's width. */
export function nudge(point: LatLon, view: MapView, dx: number, dy: number): LatLon {
	const stepKm = view.spanKm / 20;
	const kmPerLon = KM_PER_DEGREE * Math.cos((point.lat * Math.PI) / 180);
	return {
		lat: Math.max(-89, Math.min(89, point.lat + (dy * stepKm) / KM_PER_DEGREE)),
		lon: point.lon + (dx * stepKm) / kmPerLon
	};
}

/** True when `point` lies inside the view (with the frame's aspect ratio). */
export function inView(point: LatLon, view: MapView): boolean {
	const kmPerLon = KM_PER_DEGREE * Math.cos((view.centre.lat * Math.PI) / 180);
	const dx = Math.abs(point.lon - view.centre.lon) * kmPerLon;
	const dy = Math.abs(point.lat - view.centre.lat) * KM_PER_DEGREE;
	return dx <= view.spanKm / 2 && dy <= view.spanKm / VIEW_ASPECT / 2;
}

export type PlaceHint =
	| { kind: 'district'; district: District }
	| { kind: 'city'; city: string }
	| { kind: 'nowhere' };

/** Stores farther than this from the point do not name its city. */
const CITY_HINT_KM = 40;
/** A district centroid farther than this does not name the point's district. */
const DISTRICT_HINT_KM = 8;

/**
 * Where the point is, in words: the nearest Budapest district (by centroid, within 8 km), else the nearest
 * store's city (within 40 km), else nothing. A hint, not an address: the point itself is never shown.
 */
export function describePoint(point: LatLon, stores: readonly Pick<StoreOut, 'lat' | 'lon' | 'city'>[]): PlaceHint {
	let best: { district: District; km: number } | null = null;
	for (const district of DISTRICTS) {
		const km = haversineKm(point, district);
		if (best === null || km < best.km) best = { district, km };
	}
	if (best !== null && best.km <= DISTRICT_HINT_KM) return { kind: 'district', district: best.district };
	let nearest: { city: string; km: number } | null = null;
	for (const store of stores) {
		if (store.lat === null || store.lon === null || !store.city) continue;
		const km = haversineKm(point, { lat: store.lat, lon: store.lon });
		if (nearest === null || km < nearest.km) nearest = { city: store.city, km };
	}
	if (nearest !== null && nearest.km <= CITY_HINT_KM) return { kind: 'city', city: nearest.city };
	return { kind: 'nowhere' };
}
