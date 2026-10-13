/**
 * "Saját helyzetem használata" on the list page: one approximate position from the browser, asked only after
 * the explanation card, with `enableHighAccuracy: false` and a 10 s timeout. It reuses
 * `requestApproxPosition` from $lib/location (rounding to about 100 m, error mapping, never rejects); this
 * adapter only shortens that function's timeout. The position stays on the device: distances are computed by
 * $lib/geo and only store ids are sent to /api/quote.
 */
import { requestApproxPosition, type GeolocationLike, type LocateEnvironment, type LocateResult } from '../location';

export const LIST_GEO_TIMEOUT_MS = 10_000;

/** Wraps a Geolocation so every request is low accuracy with the given timeout. */
export function withTimeout(geolocation: GeolocationLike, timeoutMs: number = LIST_GEO_TIMEOUT_MS): GeolocationLike {
	return {
		getCurrentPosition(success, error, options) {
			geolocation.getCurrentPosition(success, error, { ...options, enableHighAccuracy: false, timeout: timeoutMs });
		}
	};
}

function browserEnvironment(): LocateEnvironment {
	try {
		const geolocation = typeof navigator !== 'undefined' && 'geolocation' in navigator ? navigator.geolocation : null;
		return {
			geolocation: geolocation ? withTimeout(geolocation) : null,
			secure: typeof window === 'undefined' ? true : window.isSecureContext
		};
	} catch {
		return { geolocation: null, secure: true };
	}
}

/** Asks the browser once (call only from the user's click on the explanation card). Never rejects. */
export function locateForList(env: LocateEnvironment = browserEnvironment()): Promise<LocateResult> {
	return requestApproxPosition(env);
}
