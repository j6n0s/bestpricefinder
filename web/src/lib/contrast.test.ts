import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

/** WCAG 2.x checks of the colour tokens in src/app.css, for the light and the dark theme. */

const css = readFileSync(fileURLToPath(new URL('../app.css', import.meta.url)), 'utf8');

function tokens(block: string): Map<string, string> {
	const out = new Map<string, string>();
	for (const match of block.matchAll(/--(color-[a-z0-9-]+):\s*(#[0-9a-f]{6})\s*;/gi)) {
		out.set(match[1] ?? '', (match[2] ?? '').toLowerCase());
	}
	return out;
}

function block(source: string, start: number): string {
	const open = source.indexOf('{', start);
	let depth = 0;
	for (let i = open; i < source.length; i += 1) {
		if (source[i] === '{') depth += 1;
		if (source[i] === '}') {
			depth -= 1;
			if (depth === 0) return source.slice(open + 1, i);
		}
	}
	throw new Error('unbalanced CSS');
}

const light = tokens(block(css, css.indexOf(':root')));
const darkMedia = css.indexOf('@media (prefers-color-scheme: dark)');
const dark = new Map([...light, ...tokens(block(css, darkMedia))]);

function luminance(hex: string): number {
	const channel = (i: number): number => {
		const c = Number.parseInt(hex.slice(i, i + 2), 16) / 255;
		return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
	};
	return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

export function contrast(a: string, b: string): number {
	const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
	return (hi + 0.05) / (lo + 0.05);
}

/** [foreground, background, minimum ratio] */
const PAIRS: readonly [string, string, number][] = [
	['color-text', 'color-bg', 4.5],
	['color-text', 'color-surface', 4.5],
	['color-text', 'color-surface-alt', 4.5],
	['color-text-muted', 'color-bg', 4.5],
	['color-text-muted', 'color-surface', 4.5],
	['color-text-muted', 'color-surface-alt', 4.5],
	['color-primary', 'color-bg', 4.5],
	['color-primary', 'color-surface', 4.5],
	['color-primary', 'color-surface-alt', 4.5],
	['color-primary-hover', 'color-bg', 4.5],
	['color-primary-hover', 'color-surface', 4.5],
	['color-on-primary', 'color-primary', 4.5],
	['color-on-primary', 'color-primary-hover', 4.5],
	['color-on-danger', 'color-danger', 4.5],
	['color-danger', 'color-surface', 4.5],
	['color-danger', 'color-bg', 4.5],
	['color-danger-text', 'color-danger-bg', 4.5],
	['color-warning-text', 'color-warning-bg', 4.5],
	['color-info-text', 'color-info-bg', 4.5],
	['color-success-text', 'color-success-bg', 4.5],
	['color-neutral-text', 'color-neutral-bg', 4.5],
	// Non-text contrast (WCAG 1.4.11): form-control borders and the focus indicator.
	['color-border', 'color-surface', 3],
	['color-border', 'color-bg', 3],
	['color-focus', 'color-bg', 3],
	['color-focus', 'color-surface', 3],
	['color-focus', 'color-surface-alt', 3]
];

describe.each([
	['light', light],
	['dark', dark]
] as const)('%s theme', (_name, theme) => {
	it('defines every token used by the checks', () => {
		for (const [fg, bg] of PAIRS) {
			expect(theme.get(fg), fg).toMatch(/^#[0-9a-f]{6}$/);
			expect(theme.get(bg), bg).toMatch(/^#[0-9a-f]{6}$/);
		}
	});

	it.each(PAIRS)('%s on %s reaches %s:1', (fg, bg, min) => {
		const ratio = contrast(theme.get(fg) ?? '#000000', theme.get(bg) ?? '#000000');
		expect(ratio).toBeGreaterThanOrEqual(min);
	});
});

describe('contrast()', () => {
	it('matches the WCAG reference values', () => {
		expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 5);
		expect(contrast('#ffffff', '#ffffff')).toBeCloseTo(1, 5);
		expect(contrast('#767676', '#ffffff')).toBeCloseTo(4.54, 2);
	});

	it('the dark block overrides every light colour token', () => {
		const darkOnly = tokens(block(css, darkMedia));
		expect([...darkOnly.keys()].sort()).toEqual([...light.keys()].sort());
	});
});
