import { describe, expect, it } from 'vitest';
import {
	GEO_MAX_AGE_MS,
	GEO_TIMEOUT_MS,
	declinedLocation,
	districtLocation,
	failureFromCode,
	geoTimeout,
	grantedLocation,
	originFromLocation,
	requestApproxPosition,
	revokedLocation,
	type GeolocationLike
} from './location';
import { defaultState, migrate, type StoredLocation } from './storage';

function geolocation(answer: (ok: (lat: number, lon: number) => void, fail: (code: number) => void) => void): {
	geo: GeolocationLike;
	options: PositionOptions[];
} {
	const options: PositionOptions[] = [];
	return {
		options,
		geo: {
			getCurrentPosition(success, error, opts) {
				options.push(opts ?? {});
				answer(
					(lat, lon) => success({ coords: { latitude: lat, longitude: lon } }),
					(code) => error?.({ code })
				);
			}
		}
	};
}

const base = (): StoredLocation => defaultState().location;

describe('requestApproxPosition', () => {
	it('asks for a low-accuracy position and rounds it to 3 decimals', async () => {
		const { geo, options } = geolocation((ok) => ok(47.4774567, 19.0470123));
		await expect(requestApproxPosition({}, { geolocation: geo, secure: true })).resolves.toEqual({
			ok: true,
			position: { lat: 47.477, lon: 19.047 }
		});
		expect(options).toEqual([{ enableHighAccuracy: false, timeout: GEO_TIMEOUT_MS, maximumAge: GEO_MAX_AGE_MS }]);
	});

	it('takes a timeout option and falls back to the default for unusable values', async () => {
		const { geo, options } = geolocation((ok) => ok(47.5, 19.05));
		await requestApproxPosition({ timeoutMs: 10_000 }, { geolocation: geo, secure: true });
		await requestApproxPosition({ timeoutMs: 2500.4 }, { geolocation: geo, secure: true });
		for (const timeoutMs of [0, -5, Number.NaN, Number.POSITIVE_INFINITY, undefined]) {
			await requestApproxPosition({ timeoutMs }, { geolocation: geo, secure: true });
		}
		await requestApproxPosition({ timeoutMs: 600_000 }, { geolocation: geo, secure: true });
		expect(options.map((o) => o.timeout)).toEqual([10_000, 2500, ...Array(5).fill(GEO_TIMEOUT_MS), 60_000]);
		expect(options.every((o) => o.enableHighAccuracy === false && o.maximumAge === GEO_MAX_AGE_MS)).toBe(true);
		expect(geoTimeout(1)).toBe(1);
	});

	it.each([
		[1, 'denied'],
		[2, 'unavailable'],
		[3, 'timeout'],
		[99, 'unavailable']
	] as const)('maps error code %s to %s', async (code, reason) => {
		const { geo } = geolocation((_ok, fail) => fail(code));
		await expect(requestApproxPosition({}, { geolocation: geo, secure: true })).resolves.toEqual({ ok: false, reason });
		expect(failureFromCode(code)).toBe(reason);
	});

	it('does not ask when the page is not a secure context or the API is missing', async () => {
		const { geo, options } = geolocation((ok) => ok(47.5, 19));
		await expect(requestApproxPosition({}, { geolocation: geo, secure: false })).resolves.toEqual({ ok: false, reason: 'insecure' });
		await expect(requestApproxPosition({}, { geolocation: null, secure: true })).resolves.toEqual({
			ok: false,
			reason: 'unsupported'
		});
		expect(options).toHaveLength(0);
	});

	it('never rejects, even when the browser API throws or returns garbage', async () => {
		const throwing: GeolocationLike = {
			getCurrentPosition() {
				throw new Error('boom');
			}
		};
		await expect(requestApproxPosition({}, { geolocation: throwing, secure: true })).resolves.toEqual({
			ok: false,
			reason: 'unavailable'
		});
		const { geo } = geolocation((ok) => ok(Number.NaN, 19));
		await expect(requestApproxPosition({}, { geolocation: geo, secure: true })).resolves.toEqual({ ok: false, reason: 'unavailable' });
	});
});

describe('stored location transitions', () => {
	const now = new Date('2026-10-13T08:00:00.000Z');

	it('granting stores a rounded position and makes it the origin', () => {
		const next = grantedLocation({ ...base(), districtId: '11', source: 'district' }, { lat: 47.47749, lon: 19.04701 }, now);
		expect(next).toEqual({
			consent: 'granted',
			source: 'device',
			districtId: '11',
			approx: { lat: 47.477, lon: 19.047, at: '2026-10-13T08:00:00.000Z' }
		});
		expect(originFromLocation(next)).toEqual({ lat: 47.477, lon: 19.047, source: 'device', districtId: null });
		// The storage sanitiser accepts it unchanged.
		expect(migrate({ ...defaultState(), location: next }).location).toEqual(next);
	});

	it('declining or revoking deletes the position and keeps the district', () => {
		const granted = grantedLocation({ ...base(), districtId: '05' }, { lat: 47.5, lon: 19.05 }, now);
		expect(declinedLocation(granted)).toEqual({ consent: 'declined', source: 'district', districtId: '05', approx: null });
		expect(revokedLocation(granted)).toEqual({ consent: 'unset', source: 'district', districtId: '05', approx: null });
		expect(revokedLocation(grantedLocation(base(), { lat: 47.5, lon: 19.05 }, now))).toEqual(base());
	});

	it('choosing a district makes its centroid the origin; clearing it falls back', () => {
		const withDistrict = districtLocation(base(), '11');
		expect(withDistrict).toEqual({ consent: 'unset', source: 'district', districtId: '11', approx: null });
		const origin = originFromLocation(withDistrict);
		expect(origin).toMatchObject({ source: 'district', districtId: '11' });
		expect(origin?.lat).toBeGreaterThan(47.4);
		expect(origin?.lon).toBeGreaterThan(18.9);

		expect(districtLocation(withDistrict, null)).toEqual(base());
		const granted = grantedLocation(withDistrict, { lat: 47.5, lon: 19.05 }, now);
		const backToDistrict = districtLocation(granted, '11');
		expect(backToDistrict.source).toBe('district');
		expect(districtLocation(backToDistrict, null).source).toBe('device');
	});

	it('ignores unknown district ids', () => {
		expect(districtLocation(base(), '24')).toEqual(base());
		expect(originFromLocation({ ...base(), source: 'district', districtId: '99' })).toBeNull();
	});

	it('has no origin until something is chosen, and none from a position without consent', () => {
		expect(originFromLocation(base())).toBeNull();
		expect(
			originFromLocation({ consent: 'declined', source: 'device', districtId: null, approx: { lat: 47.5, lon: 19, at: '' } })
		).toBeNull();
	});
});
