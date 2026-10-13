// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { GeolocationLike } from '../location';
import { LIST_GEO_TIMEOUT_MS, locateForList, withTimeout } from './locate';

type Outcome = { coords: { latitude: number; longitude: number } } | { code: number };

function fakeGeolocation(outcome: Outcome): GeolocationLike & { calls: (PositionOptions | undefined)[] } {
	const calls: (PositionOptions | undefined)[] = [];
	return {
		calls,
		getCurrentPosition(success, error, options) {
			calls.push(options);
			if ('coords' in outcome) success(outcome);
			else error?.(outcome);
		}
	};
}

describe('withTimeout', () => {
	it('asks for low accuracy with a 10 s timeout, whatever the caller passed', () => {
		const geo = fakeGeolocation({ coords: { latitude: 47.5, longitude: 19.05 } });
		withTimeout(geo).getCurrentPosition(
			() => undefined,
			() => undefined,
			{ enableHighAccuracy: true, timeout: 60_000, maximumAge: 600_000 }
		);
		expect(LIST_GEO_TIMEOUT_MS).toBe(10_000);
		expect(geo.calls).toEqual([{ enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 }]);
	});
});

describe('locateForList', () => {
	it('returns the position rounded to about 100 m', async () => {
		const geo = fakeGeolocation({ coords: { latitude: 47.4995123, longitude: 19.0518987 } });
		const result = await locateForList({ geolocation: withTimeout(geo), secure: true });
		expect(result).toEqual({ ok: true, position: { lat: 47.5, lon: 19.052 } });
		expect(geo.calls[0]).toMatchObject({ enableHighAccuracy: false, timeout: 10_000 });
	});

	it('maps refusals, timeouts and missing support to reasons, without throwing', async () => {
		await expect(locateForList({ geolocation: fakeGeolocation({ code: 1 }), secure: true })).resolves.toEqual({
			ok: false,
			reason: 'denied'
		});
		await expect(locateForList({ geolocation: fakeGeolocation({ code: 3 }), secure: true })).resolves.toEqual({
			ok: false,
			reason: 'timeout'
		});
		await expect(locateForList({ geolocation: fakeGeolocation({ code: 2 }), secure: true })).resolves.toEqual({
			ok: false,
			reason: 'unavailable'
		});
		await expect(locateForList({ geolocation: null, secure: true })).resolves.toEqual({ ok: false, reason: 'unsupported' });
		await expect(locateForList({ geolocation: fakeGeolocation({ code: 1 }), secure: false })).resolves.toEqual({
			ok: false,
			reason: 'insecure'
		});
	});

	it('does not ask when there is no browser environment', async () => {
		await expect(locateForList()).resolves.toMatchObject({ ok: false });
	});
});
