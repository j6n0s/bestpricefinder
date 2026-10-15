/**
 * Location helpers. The position is requested only after the explanation screen (LocationExplainer), with
 * `enableHighAccuracy: false`, rounded to about 100 m and stored on the device only. It is never sent to
 * the server: distances are computed by src/lib/geo.ts and only store ids leave the device.
 * The alternatives need no permission: a Budapest district, or a point the user picks on the on-device map
 * (MapPicker; `StoredLocation.manual`, source "map"), also kept on the device only.
 */
import { districtById } from './districts';
import type { LatLon } from './geo';
import { APPROX_DECIMALS, roundCoordinate, type StoredLocation } from './storage';

export const GEO_TIMEOUT_MS = 15_000;
/** A cached browser position up to 10 minutes old is good enough for "stores near me". */
export const GEO_MAX_AGE_MS = 10 * 60 * 1000;

export type LocateFailure = 'unsupported' | 'insecure' | 'denied' | 'unavailable' | 'timeout';

export type LocateResult = { ok: true; position: LatLon } | { ok: false; reason: LocateFailure };

/** The subset of the Geolocation API this module uses (injectable for tests). */
export interface GeolocationLike {
	getCurrentPosition(
		success: (position: { coords: { latitude: number; longitude: number } }) => void,
		error?: (error: { code: number }) => void,
		options?: PositionOptions
	): void;
}

export interface LocateEnvironment {
	geolocation?: GeolocationLike | null;
	secure?: boolean;
}

export interface LocateOptions {
	/** How long the browser may take, in ms (default GEO_TIMEOUT_MS; the list uses 10 s). */
	timeoutMs?: number;
}

function defaultEnvironment(): LocateEnvironment {
	try {
		return {
			geolocation: typeof navigator !== 'undefined' && 'geolocation' in navigator ? navigator.geolocation : null,
			secure: typeof window === 'undefined' ? true : window.isSecureContext
		};
	} catch {
		return { geolocation: null, secure: true };
	}
}

/** GeolocationPositionError codes: 1 PERMISSION_DENIED, 2 POSITION_UNAVAILABLE, 3 TIMEOUT. */
export function failureFromCode(code: number): LocateFailure {
	if (code === 1) return 'denied';
	if (code === 3) return 'timeout';
	return 'unavailable';
}

/** A usable geolocation timeout: a positive whole number of ms up to 60 s, else the default. */
export function geoTimeout(timeoutMs: number | undefined): number {
	return typeof timeoutMs === 'number' && Number.isFinite(timeoutMs) && timeoutMs >= 1
		? Math.min(Math.round(timeoutMs), 60_000)
		: GEO_TIMEOUT_MS;
}

/**
 * Asks the browser once for an approximate position (`enableHighAccuracy: false`, `options.timeoutMs`, a
 * cached position up to GEO_MAX_AGE_MS old). Never rejects. Call it only from a user action on an
 * explanation card (LocationExplainer or the list's OriginChooser). The returned coordinates are already
 * rounded to APPROX_DECIMALS. `env` is injectable for tests; it defaults to the browser's own API.
 */
export function requestApproxPosition(
	options: LocateOptions = {},
	env: LocateEnvironment = defaultEnvironment()
): Promise<LocateResult> {
	const geolocation = env.geolocation ?? null;
	const timeout = geoTimeout(options.timeoutMs);
	if (env.secure === false) return Promise.resolve({ ok: false, reason: 'insecure' });
	if (geolocation === null) return Promise.resolve({ ok: false, reason: 'unsupported' });
	return new Promise((resolve) => {
		try {
			geolocation.getCurrentPosition(
				({ coords }) => {
					const { latitude, longitude } = coords;
					if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
						resolve({ ok: false, reason: 'unavailable' });
						return;
					}
					resolve({
						ok: true,
						position: { lat: roundCoordinate(latitude, APPROX_DECIMALS), lon: roundCoordinate(longitude, APPROX_DECIMALS) }
					});
				},
				(error) => resolve({ ok: false, reason: failureFromCode(error.code) }),
				{ enableHighAccuracy: false, timeout, maximumAge: GEO_MAX_AGE_MS }
			);
		} catch {
			resolve({ ok: false, reason: 'unavailable' });
		}
	});
}

export interface Origin extends LatLon {
	source: 'device' | 'district' | 'map';
	districtId: string | null;
}

/** Where distances are measured from, per the stored choice; null when nothing usable is stored. */
export function originFromLocation(location: StoredLocation): Origin | null {
	if (location.source === 'device' && location.consent === 'granted' && location.approx) {
		return { lat: location.approx.lat, lon: location.approx.lon, source: 'device', districtId: null };
	}
	if (location.source === 'district') {
		const district = districtById(location.districtId);
		if (district) return { lat: district.lat, lon: district.lon, source: 'district', districtId: district.id };
	}
	if (location.source === 'map' && location.manual) {
		return { lat: location.manual.lat, lon: location.manual.lon, source: 'map', districtId: null };
	}
	return null;
}

/** The source to fall back to when the device position is no longer used: the district, else the map point. */
function withoutDevice(previous: StoredLocation): StoredLocation['source'] {
	if (previous.districtId !== null) return 'district';
	return previous.manual !== null ? 'map' : 'none';
}

/** A stored device position older than this is shown as out of date (the list offers to update it). */
export const POSITION_STALE_MS = 24 * 60 * 60 * 1000;

/**
 * True when a stored position is more than POSITION_STALE_MS old, or its time is missing or invalid. A
 * position "from the future" (a wrong device clock) is not stale. The position is still used until the user
 * acts: the browser is never asked again without a click.
 */
export function isStale(approx: { at: string } | null | undefined, now: Date = new Date()): boolean {
	if (!approx) return false;
	const at = Date.parse(approx.at);
	if (Number.isNaN(at)) return true;
	return now.getTime() - at > POSITION_STALE_MS;
}

/** The stored location after the user granted access and the browser returned `position`. */
export function grantedLocation(previous: StoredLocation, position: LatLon, now: Date = new Date()): StoredLocation {
	return {
		consent: 'granted',
		source: 'device',
		districtId: previous.districtId,
		approx: {
			lat: roundCoordinate(position.lat, APPROX_DECIMALS),
			lon: roundCoordinate(position.lon, APPROX_DECIMALS),
			at: now.toISOString()
		},
		manual: previous.manual
	};
}

/** The stored location after the user declined on the explanation screen or the browser refused. */
export function declinedLocation(previous: StoredLocation): StoredLocation {
	return {
		consent: 'declined',
		source: withoutDevice(previous),
		districtId: previous.districtId,
		approx: null,
		manual: previous.manual
	};
}

/** Revoking deletes the stored position; the district choice and the map point (not sensor data) stay. */
export function revokedLocation(previous: StoredLocation): StoredLocation {
	return {
		consent: 'unset',
		source: withoutDevice(previous),
		districtId: previous.districtId,
		approx: null,
		manual: previous.manual
	};
}

/** Choosing a district (or none) makes it the origin; a stored device position is kept but not used. */
export function districtLocation(previous: StoredLocation, districtId: string | null): StoredLocation {
	const district = districtById(districtId);
	if (!district) {
		return {
			...previous,
			districtId: null,
			source: previous.source === 'district' ? (previous.approx ? 'device' : previous.manual ? 'map' : 'none') : previous.source
		};
	}
	return { ...previous, districtId: district.id, source: 'district' };
}

/**
 * A point chosen on the map becomes the origin (rounded like a device position, about 100 m); a stored device
 * position and the district choice are kept but not used.
 */
export function mapLocation(previous: StoredLocation, point: LatLon, now: Date = new Date()): StoredLocation {
	return {
		...previous,
		source: 'map',
		manual: {
			lat: roundCoordinate(point.lat, APPROX_DECIMALS),
			lon: roundCoordinate(point.lon, APPROX_DECIMALS),
			at: now.toISOString()
		}
	};
}

/** Deleting the map point; the origin falls back to the device position, else the district, else none. */
export function clearedMapLocation(previous: StoredLocation): StoredLocation {
	const device = previous.consent === 'granted' && previous.approx !== null;
	return {
		...previous,
		manual: null,
		source: previous.source === 'map' ? (device ? 'device' : previous.districtId !== null ? 'district' : 'none') : previous.source
	};
}
