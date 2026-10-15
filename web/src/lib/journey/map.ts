/**
 * Geometry for the schematic maps drawn as SVG on the device (no map tiles, no request to any other site): the
 * journey map (`mapFrame`, fitted to its points) and the map picker (`viewFrame`, a centre and a width in km,
 * with the inverse projection for a tap). North is up; an equirectangular projection around the frame's
 * latitude is accurate to well under 1 % over a few kilometres and good enough for a tap on a 30 km view.
 */
import { EARTH_RADIUS_KM, type LatLon } from '../geo';

export interface MapPoint {
	x: number;
	y: number;
}

export interface MapFrame {
	width: number;
	height: number;
	/** SVG user units per km. */
	unitsPerKm: number;
	project(point: LatLon): MapPoint;
	/** The inverse of `project`: the place under an SVG point. */
	unproject(point: MapPoint): LatLon;
}

export interface FrameOptions {
	width: number;
	height: number;
	/** Empty border, in SVG units, so markers at the edge are not cut off. */
	padding: number;
	/** The smallest area shown, km across, so two stores next door do not fill the whole map. */
	minSpanKm: number;
}

export const DEFAULT_FRAME: Readonly<FrameOptions> = { width: 400, height: 300, padding: 36, minSpanKm: 0.4 };

const KM_PER_DEGREE = (EARTH_RADIUS_KM * Math.PI) / 180;

/** A frame that fits every point (at least one) inside the padding, centred. */
export function mapFrame(points: readonly LatLon[], options: FrameOptions = DEFAULT_FRAME): MapFrame {
	if (points.length === 0) throw new RangeError('mapFrame needs at least one point');
	for (const point of points) {
		if (!Number.isFinite(point.lat) || !Number.isFinite(point.lon)) throw new RangeError('invalid point');
	}
	const { width, height, padding, minSpanKm } = options;
	const meanLat = points.reduce((sum, p) => sum + p.lat, 0) / points.length;
	const kmPerLon = KM_PER_DEGREE * Math.cos((meanLat * Math.PI) / 180);
	const east = (p: LatLon): number => p.lon * kmPerLon;
	const north = (p: LatLon): number => p.lat * KM_PER_DEGREE;
	const xs = points.map(east);
	const ys = points.map(north);
	const minX = Math.min(...xs);
	const maxX = Math.max(...xs);
	const minY = Math.min(...ys);
	const maxY = Math.max(...ys);
	const spanX = Math.max(maxX - minX, minSpanKm);
	const spanY = Math.max(maxY - minY, minSpanKm);
	const unitsPerKm = Math.min((width - 2 * padding) / spanX, (height - 2 * padding) / spanY);
	const centreX = (minX + maxX) / 2;
	const centreY = (minY + maxY) / 2;
	return {
		width,
		height,
		unitsPerKm,
		project: (point) => ({
			x: width / 2 + (east(point) - centreX) * unitsPerKm,
			y: height / 2 - (north(point) - centreY) * unitsPerKm
		}),
		unproject: (point) => ({
			lat: (centreY + (height / 2 - point.y) / unitsPerKm) / KM_PER_DEGREE,
			lon: (centreX + (point.x - width / 2) / unitsPerKm) / kmPerLon
		})
	};
}

/** A frame `spanKm` kilometres wide, centred on `centre` (the height follows the frame's aspect ratio). */
export function viewFrame(
	centre: LatLon,
	spanKm: number,
	options: Pick<FrameOptions, 'width' | 'height'> = DEFAULT_FRAME
): MapFrame {
	if (!Number.isFinite(centre.lat) || !Number.isFinite(centre.lon) || !(spanKm > 0)) throw new RangeError('invalid view');
	const { width, height } = options;
	const kmPerLon = KM_PER_DEGREE * Math.cos((centre.lat * Math.PI) / 180);
	const unitsPerKm = width / spanKm;
	const centreX = centre.lon * kmPerLon;
	const centreY = centre.lat * KM_PER_DEGREE;
	return {
		width,
		height,
		unitsPerKm,
		project: (point) => ({
			x: width / 2 + (point.lon * kmPerLon - centreX) * unitsPerKm,
			y: height / 2 - (point.lat * KM_PER_DEGREE - centreY) * unitsPerKm
		}),
		unproject: (point) => ({
			lat: (centreY + (height / 2 - point.y) / unitsPerKm) / KM_PER_DEGREE,
			lon: (centreX + (point.x - width / 2) / unitsPerKm) / kmPerLon
		})
	};
}

const NICE_KM = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10];

/** The longest "nice" distance whose bar is at most `maxUnits` long (at least the shortest one). */
export function scaleBar(frame: Pick<MapFrame, 'unitsPerKm'>, maxUnits: number): { km: number; units: number } {
	let km = 0.05; // NICE_KM[0]: never shorter than 50 m
	for (const candidate of NICE_KM) {
		if (candidate * frame.unitsPerKm <= maxUnits) km = candidate;
	}
	return { km, units: km * frame.unitsPerKm };
}

/** "M x y L x y …" through the points (rounded to 0.1 unit). */
export function pathData(points: readonly MapPoint[]): string {
	return points
		.map((p, index) => `${index === 0 ? 'M' : 'L'}${Math.round(p.x * 10) / 10} ${Math.round(p.y * 10) / 10}`)
		.join(' ');
}
