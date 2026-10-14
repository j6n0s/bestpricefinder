#!/usr/bin/env node
// @ts-check
/**
 * Draws the app icon (an original, simple shopping basket; no third-party artwork, no GVH reference) and
 * renders the PNG sizes with the Playwright Chromium already installed on the machine.
 *
 * Output (static/icons/): icon.svg (favicon), icon-192.png, icon-512.png (purpose "any", transparent
 * corners), icon-maskable-512.png (purpose "maskable": full-bleed background, artwork inside the 80 % safe
 * zone: every point within 40 % of the size from the centre) and apple-touch-icon.png (180 px, full-bleed).
 *
 * Usage: node scripts/gen-icons.mjs   (never downloads browsers; set PLAYWRIGHT_BROWSERS_PATH if needed)
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = resolve(HERE, '../static/icons');

const GREEN = '#2a7a4b';
const WHITE = '#ffffff';

/** The basket on a 512 grid, centred on (256, 256). */
const BASKET = [
	`<path d="M176 211 C176 117 336 117 336 211" fill="none" stroke="${WHITE}" stroke-width="30" stroke-linecap="round"/>`,
	`<rect x="88" y="196" width="336" height="44" rx="22" fill="${WHITE}"/>`,
	// The body starts under the rim (y 228 < 240) so no anti-aliasing seam shows between them.
	`<path d="M113 228 H399 L366 376 Q361 396 340 396 H172 Q151 396 146 376 Z" fill="${WHITE}"/>`,
	`<path d="M206 270 V366 M256 270 V366 M306 270 V366" stroke="${GREEN}" stroke-width="20" stroke-linecap="round"/>`
].join('');

/**
 * @param {{ fullBleed: boolean, scale: number }} options
 * @returns {string}
 */
export function iconSvg({ fullBleed, scale }) {
	const background = fullBleed
		? `<rect width="512" height="512" fill="${GREEN}"/>`
		: `<rect width="512" height="512" rx="112" fill="${GREEN}"/>`;
	const offset = 256 * (1 - scale);
	return (
		`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">` +
		`${background}<g transform="translate(${offset} ${offset}) scale(${scale})">${BASKET}</g></svg>`
	);
}

/** @type {{ file: string, size: number, fullBleed: boolean, scale: number }[]} */
const PNGS = [
	{ file: 'icon-192.png', size: 192, fullBleed: false, scale: 1 },
	{ file: 'icon-512.png', size: 512, fullBleed: false, scale: 1 },
	{ file: 'icon-maskable-512.png', size: 512, fullBleed: true, scale: 0.9 },
	{ file: 'apple-touch-icon.png', size: 180, fullBleed: true, scale: 0.86 }
];

async function main() {
	mkdirSync(OUT_DIR, { recursive: true });
	writeFileSync(resolve(OUT_DIR, 'icon.svg'), `${iconSvg({ fullBleed: false, scale: 1 })}\n`);
	const browser = await chromium.launch();
	try {
		for (const png of PNGS) {
			const page = await browser.newPage({ viewport: { width: png.size, height: png.size }, deviceScaleFactor: 1 });
			const svg = iconSvg({ fullBleed: png.fullBleed, scale: png.scale }).replace(
				'width="512" height="512"',
				`width="${png.size}" height="${png.size}"`
			);
			await page.setContent(`<!doctype html><html><body style="margin:0;background:transparent">${svg}</body></html>`);
			await page.screenshot({ path: resolve(OUT_DIR, png.file), omitBackground: !png.fullBleed });
			await page.close();
			console.log(`wrote static/icons/${png.file}`);
		}
	} finally {
		await browser.close();
	}
}

main().catch((error) => {
	console.error(error);
	process.exit(1);
});
