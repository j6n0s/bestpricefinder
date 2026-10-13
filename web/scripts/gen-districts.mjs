#!/usr/bin/env node
// @ts-check
/**
 * Generates src/lib/data/districts.json, the Budapest district picker data, from the research store list
 * research/gvh-location/data/stores.csv (GVH Árfigyelő /shops, 2026-10-12 snapshot).
 *
 * - District = digits 2-3 of a Budapest postal code 1xxx ("1114" -> XI.), districts 1..23.
 * - Centroid = the median latitude and the median longitude of all stores in that district (any chain),
 *   rounded half-up to 5 decimals (about 1 m) with exact decimal arithmetic. The median ignores the odd
 *   misplaced coordinate.
 *
 * Usage: node scripts/gen-districts.mjs           (writes the file)
 *        node scripts/gen-districts.mjs --check   (exits 1 when the committed file is out of date)
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
export const CSV_PATH = resolve(HERE, '../../research/gvh-location/data/stores.csv');
export const OUT_PATH = resolve(HERE, '../src/lib/data/districts.json');
export const SOURCE = 'research/gvh-location/data/stores.csv';
export const DISTRICT_COUNT = 23;
/** Generous bounding box around Budapest; a centroid outside it means bad input. */
const BBOX = { latMin: 47.34, latMax: 47.62, lonMin: 18.92, lonMax: 19.34 };

/**
 * RFC 4180 CSV parser (quoted fields, doubled quotes, CRLF or LF). Returns rows of raw strings.
 * @param {string} text
 * @returns {string[][]}
 */
export function parseCsv(text) {
	/** @type {string[][]} */
	const rows = [];
	/** @type {string[]} */
	let row = [];
	let field = '';
	let quoted = false;
	for (let i = 0; i < text.length; i += 1) {
		const ch = text[i];
		if (quoted) {
			if (ch === '"') {
				if (text[i + 1] === '"') {
					field += '"';
					i += 1;
				} else {
					quoted = false;
				}
			} else {
				field += ch;
			}
		} else if (ch === '"') {
			quoted = true;
		} else if (ch === ',') {
			row.push(field);
			field = '';
		} else if (ch === '\n' || ch === '\r') {
			if (ch === '\r' && text[i + 1] === '\n') i += 1;
			row.push(field);
			rows.push(row);
			row = [];
			field = '';
		} else {
			field += ch;
		}
	}
	if (quoted) throw new Error('CSV: unterminated quoted field');
	if (field !== '' || row.length > 0) {
		row.push(field);
		rows.push(row);
	}
	return rows.filter((r) => !(r.length === 1 && r[0] === ''));
}

/** Decimal places kept when parsing coordinates (the CSV has at most 15). */
const SCALE_DIGITS = 15;
const SCALE = 10n ** BigInt(SCALE_DIGITS);

/**
 * Exact decimal string -> integer scaled by 10^15 ("47.5" -> 47500000000000000n); null when not a plain
 * decimal number or when it has more than 15 decimals. Exact integers avoid float rounding surprises.
 * @param {string} text
 * @returns {bigint | null}
 */
export function parseScaled(text) {
	const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(text.trim());
	if (!match) return null;
	const [, sign, whole = '0', frac = ''] = match;
	if (frac.length > SCALE_DIGITS) return null;
	const value = BigInt(whole) * SCALE + BigInt(frac.padEnd(SCALE_DIGITS, '0'));
	return sign === '-' ? -value : value;
}

/**
 * Twice the median of a non-empty list of scaled integers (twice, so an even count stays exact).
 * @param {readonly bigint[]} values
 * @returns {bigint}
 */
export function twiceMedian(values) {
	if (values.length === 0) throw new Error('median of an empty list');
	const sorted = [...values].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
	const mid = Math.floor(sorted.length / 2);
	const upper = /** @type {bigint} */ (sorted[mid]);
	return sorted.length % 2 === 1 ? 2n * upper : /** @type {bigint} */ (sorted[mid - 1]) + upper;
}

/**
 * Median of scaled integers, rounded half away from zero to `digits` decimals, as a Number.
 * @param {readonly bigint[]} values
 * @param {number} digits
 * @returns {number}
 */
export function medianRounded(values, digits) {
	const twice = twiceMedian(values);
	const divisor = 2n * 10n ** BigInt(SCALE_DIGITS - digits);
	const magnitude = twice < 0n ? -twice : twice;
	const rounded = (magnitude + divisor / 2n) / divisor;
	return Number(twice < 0n ? -rounded : rounded) / 10 ** digits;
}

/**
 * 1..3999 -> Roman numeral.
 * @param {number} n
 * @returns {string}
 */
export function toRoman(n) {
	if (!Number.isInteger(n) || n < 1 || n > 3999) throw new RangeError(`cannot write ${n} as a Roman numeral`);
	/** @type {[number, string][]} */
	const table = [
		[1000, 'M'],
		[900, 'CM'],
		[500, 'D'],
		[400, 'CD'],
		[100, 'C'],
		[90, 'XC'],
		[50, 'L'],
		[40, 'XL'],
		[10, 'X'],
		[9, 'IX'],
		[5, 'V'],
		[4, 'IV'],
		[1, 'I']
	];
	let rest = n;
	let out = '';
	for (const [value, symbol] of table) {
		while (rest >= value) {
			out += symbol;
			rest -= value;
		}
	}
	return out;
}

/**
 * Budapest district number from a postal code ("1114" -> 11), or null when not a Budapest district code.
 * @param {string} postalCode
 * @returns {number | null}
 */
export function districtOf(postalCode) {
	const match = /^1(\d{2})\d$/.exec(postalCode.trim());
	if (!match) return null;
	const n = Number(match[1]);
	return n >= 1 && n <= DISTRICT_COUNT ? n : null;
}

/**
 * @typedef {{ id: string, number: number, roman: string, lat: number, lon: number, stores: number }} District
 * @typedef {{ version: 1, source: string, method: string, districts: District[] }} DistrictFile
 */

/**
 * Builds the district file from the CSV text. Throws when any district is missing or implausible.
 * @param {string} csvText
 * @returns {DistrictFile}
 */
export function buildDistricts(csvText) {
	const [header, ...rows] = parseCsv(csvText);
	if (!header) throw new Error('CSV: empty file');
	const col = (/** @type {string} */ name) => {
		const index = header.indexOf(name);
		if (index < 0) throw new Error(`CSV: missing column ${name}`);
		return index;
	};
	const iPostal = col('postalCode');
	const iLat = col('lat');
	const iLon = col('lon');

	/** @type {Map<number, { lats: bigint[], lons: bigint[] }>} */
	const byDistrict = new Map();
	for (const row of rows) {
		const district = districtOf(row[iPostal] ?? '');
		if (district === null) continue;
		const lat = parseScaled(row[iLat] ?? '');
		const lon = parseScaled(row[iLon] ?? '');
		if (lat === null || lon === null) continue;
		const entry = byDistrict.get(district) ?? { lats: [], lons: [] };
		entry.lats.push(lat);
		entry.lons.push(lon);
		byDistrict.set(district, entry);
	}

	/** @type {District[]} */
	const districts = [];
	for (let n = 1; n <= DISTRICT_COUNT; n += 1) {
		const entry = byDistrict.get(n);
		if (!entry || entry.lats.length === 0) throw new Error(`district ${n} has no store with coordinates`);
		const lat = medianRounded(entry.lats, 5);
		const lon = medianRounded(entry.lons, 5);
		if (lat < BBOX.latMin || lat > BBOX.latMax || lon < BBOX.lonMin || lon > BBOX.lonMax) {
			throw new Error(`district ${n} centroid ${lat},${lon} is outside Budapest`);
		}
		districts.push({ id: String(n).padStart(2, '0'), number: n, roman: toRoman(n), lat, lon, stores: entry.lats.length });
	}
	return {
		version: 1,
		source: SOURCE,
		method: 'postal code digits 2-3; centroid = median lat/lon of the district stores (all chains)',
		districts
	};
}

/**
 * @param {DistrictFile} file
 * @returns {string}
 */
export function serialise(file) {
	return `${JSON.stringify(file, null, '\t')}\n`;
}

function main() {
	const output = serialise(buildDistricts(readFileSync(CSV_PATH, 'utf8')));
	if (process.argv.includes('--check')) {
		let current = '';
		try {
			current = readFileSync(OUT_PATH, 'utf8');
		} catch {
			current = '';
		}
		if (current !== output) {
			console.error('districts.json is out of date: run npm run gen:districts');
			process.exit(1);
		}
		console.log('districts.json is up to date');
		return;
	}
	writeFileSync(OUT_PATH, output);
	console.log(`wrote ${OUT_PATH}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main();
