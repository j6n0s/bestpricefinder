import { describe, expect, it } from 'vitest';
import {
	POSITION_STALE_MS,
	isStale,
	GEO_MAX_AGE_MS,
	GEO_TIMEOUT_MS,
	declinedLocation,
	districtLocation,
	failureFromCode,
	geoTimeout,
	grantedLocation,
	mapLocation,
	clearedMapLocation,
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
			approx: { lat: 47.477, lon: 19.047, at: '2026-10-13T08:00:00.000Z' },
			manual: null
		});
		expect(originFromLocation(next)).toEqual({ lat: 47.477, lon: 19.047, source: 'device', districtId: null });
		// The storage sanitiser accepts it unchanged.
		expect(migrate({ ...defaultState(), location: next }).location).toEqual(next);
	});

	it('declining or revoking deletes the position and keeps the district', () => {
		const granted = grantedLocation({ ...base(), districtId: '05' }, { lat: 47.5, lon: 19.05 }, now);
		expect(declinedLocation(granted)).toEqual({ consent: 'declined', source: 'district', districtId: '05', approx: null, manual: null });
		expect(revokedLocation(granted)).toEqual({ consent: 'unset', source: 'district', districtId: '05', approx: null, manual: null });
		expect(revokedLocation(grantedLocation(base(), { lat: 47.5, lon: 19.05 }, now))).toEqual(base());
	});

	it('choosing a district makes its centroid the origin; clearing it falls back', () => {
		const withDistrict = districtLocation(base(), '11');
		expect(withDistrict).toEqual({ consent: 'unset', source: 'district', districtId: '11', approx: null, manual: null });
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
			originFromLocation({ consent: 'declined', source: 'device', districtId: null, approx: { lat: 47.5, lon: 19, at: '' }, manual: null })
		).toBeNull();
	});

	it('a point picked on the map is the origin, rounded; it survives declining and revoking', () => {
		const picked = mapLocation(base(), { lat: 47.49876, lon: 19.05432 }, now);
		expect(picked).toEqual({
			consent: 'unset',
			source: 'map',
			districtId: null,
			approx: null,
			manual: { lat: 47.499, lon: 19.054, at: '2026-10-13T08:00:00.000Z' }
		});
		expect(originFromLocation(picked)).toEqual({ lat: 47.499, lon: 19.054, source: 'map', districtId: null });
		expect(migrate({ ...defaultState(), location: picked }).location).toEqual(picked);
		// Declining or revoking the device position falls back to the map point when there is no district.
		const granted = grantedLocation(picked, { lat: 47.5, lon: 19.05 }, now);
		expect(granted.source).toBe('device');
		expect(declinedLocation(granted)).toMatchObject({ source: 'map', manual: picked.manual });
		expect(revokedLocation(granted)).toMatchObject({ source: 'map', manual: picked.manual });
		expect(revokedLocation(grantedLocation({ ...picked, districtId: '05' }, { lat: 47.5, lon: 19.05 }, now)).source).toBe('district');
		// Choosing a district switches to it and keeps the point; clearing the district comes back to the point.
		const district = districtLocation(picked, '11');
		expect(district).toMatchObject({ source: 'district', manual: picked.manual });
		expect(districtLocation(district, null)).toMatchObject({ source: 'map', districtId: null });
	});

	it('clearing the map point falls back to the device position, else the district, else none', () => {
		const picked = mapLocation(base(), { lat: 47.5, lon: 19.05 }, now);
		expect(clearedMapLocation(picked)).toEqual(base());
		expect(clearedMapLocation(mapLocation({ ...base(), districtId: '05' }, { lat: 47.5, lon: 19.05 }, now))).toMatchObject({
			source: 'district',
			manual: null
		});
		const withDevice = mapLocation(grantedLocation(base(), { lat: 47.5, lon: 19.05 }, now), { lat: 47.6, lon: 19.1 }, now);
		expect(withDevice.source).toBe('map');
		expect(clearedMapLocation(withDevice)).toMatchObject({ source: 'device', manual: null });
		// Clearing a point that is not the origin changes nothing else.
		const district = districtLocation(picked, '11');
		expect(clearedMapLocation(district)).toEqual({ ...district, manual: null });
	});
});

describe('isStale (a stored device position)', () => {
	const now = new Date('2026-10-13T08:00:00.000Z');
	const at = (ms: number) => ({ at: new Date(now.getTime() - ms).toISOString() });

	it('is fresh up to 24 hours, stale after', () => {
		expect(POSITION_STALE_MS).toBe(86_400_000);
		expect(isStale(at(0), now)).toBe(false);
		expect(isStale(at(POSITION_STALE_MS), now)).toBe(false);
		expect(isStale(at(POSITION_STALE_MS + 1), now)).toBe(true);
		expect(isStale(at(3 * POSITION_STALE_MS), now)).toBe(true);
	});

	it('treats a missing or invalid time as stale, a future time as fresh, no position as not stale', () => {
		expect(isStale({ at: 'yesterday' }, now)).toBe(true);
		expect(isStale({ at: '' }, now)).toBe(true);
		expect(isStale(at(-60_000), now)).toBe(false);
		expect(isStale(null, now)).toBe(false);
		expect(isStale(undefined, now)).toBe(false);
	});
});
