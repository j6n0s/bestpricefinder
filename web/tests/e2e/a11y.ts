/**
 * Accessibility checks shared by the e2e specs, run on the rendered page (light and dark, every width):
 * - heading order: exactly one h1, first; no heading more than one level deeper than the one before;
 * - every visible control has an accessible name, and nothing uses a positive tabindex (focus order = DOM);
 * - text contrast as rendered: 4.5:1, or 3:1 for large text (WCAG 1.4.3), against the first opaque
 *   background behind it (src/lib/contrast.test.ts checks the colour tokens themselves);
 * - touch targets of at least 44×44 px.
 */
import { expect, type Page } from '@playwright/test';

export async function expectHeadingOrder(page: Page, where: string): Promise<void> {
	const headings = await page.getByRole('heading').evaluateAll((elements) =>
		elements.map((el) => {
			const aria = el.getAttribute('aria-level');
			return { level: aria ? Number(aria) : Number(el.tagName.slice(1)), text: (el.textContent ?? '').trim().slice(0, 50) };
		})
	);
	const outline = headings.map((h) => `h${h.level} ${h.text}`);
	expect(headings.filter((h) => h.level === 1), `${where}: exactly one h1 (${outline.join(' | ')})`).toHaveLength(1);
	expect(headings[0]?.level, `${where}: the first heading is the h1`).toBe(1);
	const skips = headings.flatMap((h, i) => {
		const before = headings[i - 1];
		return before && h.level > before.level + 1 ? [`h${before.level} "${before.text}" -> h${h.level} "${h.text}"`] : [];
	});
	expect(skips, `${where}: skipped heading levels`).toEqual([]);
}

export async function expectNamedControls(page: Page, where: string): Promise<void> {
	const problems = await page
		.locator('a[href], button, input:not([type="hidden"]), select, textarea, summary, [role="button"], [tabindex]')
		.evaluateAll((elements) => {
			const clean = (text: string | null | undefined): string => (text ?? '').replace(/\s+/g, ' ').trim();
			const out: string[] = [];
			for (const el of elements) {
				const tabindex = Number(el.getAttribute('tabindex') ?? '0');
				if (tabindex > 0) out.push(`positive tabindex: ${el.outerHTML.slice(0, 90)}`);
				if (!el.checkVisibility()) continue;
				if (el.getAttribute('tabindex') !== null && !el.matches('a, button, input, select, textarea, summary, [role]')) continue;
				const byIds = (el.getAttribute('aria-labelledby') ?? '')
					.split(/\s+/)
					.filter(Boolean)
					.map((id) => clean(document.getElementById(id)?.textContent))
					.join(' ');
				const labels = 'labels' in el && el.labels ? [...(el.labels as NodeListOf<HTMLLabelElement>)].map((l) => clean(l.textContent)).join(' ') : '';
				const ownText = el.matches('a, button, summary, [role="button"]') ? clean(el.textContent) : '';
				const name = clean(el.getAttribute('aria-label')) || clean(byIds) || clean(labels) || ownText || clean(el.getAttribute('title'));
				if (name === '') out.push(`no accessible name: ${el.outerHTML.slice(0, 90)}`);
			}
			return out;
		});
	expect(problems, where).toEqual([]);
}

export async function expectTextContrast(page: Page, where: string): Promise<void> {
	const result = await page.evaluate(() => {
		type Rgba = [number, number, number, number];
		const parse = (value: string): Rgba | null => {
			const match = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/.exec(value.trim());
			if (!match) return null;
			const alphaText = match[4];
			const alpha = alphaText === undefined ? 1 : alphaText.endsWith('%') ? Number.parseFloat(alphaText) / 100 : Number(alphaText);
			return [Number(match[1]), Number(match[2]), Number(match[3]), alpha];
		};
		const luminance = ([r, g, b]: Rgba): number => {
			const channel = (c: number): number => {
				const s = c / 255;
				return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
			};
			return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
		};
		const ratio = (a: Rgba, b: Rgba): number => {
			const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
			return (hi + 0.05) / (lo + 0.05);
		};
		/** The first opaque background behind `el`; null when a translucent one is in the way. */
		const background = (el: Element): Rgba | null => {
			for (let node: Element | null = el; node; node = node.parentElement) {
				const bg = parse(getComputedStyle(node).backgroundColor);
				if (bg && bg[3] > 0) return bg[3] >= 1 ? bg : null;
			}
			return parse(getComputedStyle(document.documentElement).backgroundColor) ?? [255, 255, 255, 1];
		};
		const failures: string[] = [];
		let checked = 0;
		let unparsed = 0;
		const seen = new Set<Element>();
		const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
		while (walker.nextNode()) {
			const node = walker.currentNode;
			const el = node.parentElement;
			if (!el || seen.has(el) || (node.textContent ?? '').trim() === '') continue;
			seen.add(el);
			if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
			// Hidden from sight (screen-reader text), or an inactive control (WCAG 1.4.3 exempts those).
			if (el.closest('.visually-hidden, .sveltekit-announcer, [aria-hidden="true"], [aria-disabled="true"], :disabled')) continue;
			const style = getComputedStyle(el);
			const fg = parse(style.color);
			const bg = background(el);
			if (!fg || !bg) {
				unparsed += 1;
				continue;
			}
			checked += 1;
			const size = Number.parseFloat(style.fontSize);
			const large = size >= 24 || (Number(style.fontWeight) >= 700 && size >= 18.66);
			const value = ratio(fg, bg);
			if (value < (large ? 3 : 4.5)) {
				failures.push(`${value.toFixed(2)}:1 "${(node.textContent ?? '').trim().slice(0, 40)}" ${style.color} on ${bg.join(',')}`);
			}
		}
		return { failures, checked, unparsed };
	});
	expect(result.checked, `${where}: text checked for contrast`).toBeGreaterThan(5);
	expect(result.unparsed, `${where}: colours the check could not read`).toBe(0);
	expect(result.failures, `${where}: text below the WCAG AA contrast`).toEqual([]);
}

export async function expectTouchTargets(page: Page, where: string): Promise<void> {
	const small = await page.evaluate(() => {
		const targets = document.querySelectorAll<HTMLElement>(
			'button, select, input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"]), nav a, .btn, label.choice, .skip-link'
		);
		return [...targets]
			.filter((el) => el.checkVisibility() || el.classList.contains('skip-link'))
			.map((el) => ({ el, rect: el.getBoundingClientRect() }))
			.filter(({ rect }) => rect.width < 44 || rect.height < 44)
			.map(({ el, rect }) => `${el.tagName}.${el.className} "${el.textContent?.trim().slice(0, 40)}" ${rect.width}x${rect.height}`);
	});
	expect(small, `${where}: touch targets under 44×44 px`).toEqual([]);
}

/** All four checks. */
export async function expectAccessible(page: Page, where: string): Promise<void> {
	await expectHeadingOrder(page, where);
	await expectNamedControls(page, where);
	await expectTextContrast(page, where);
	await expectTouchTargets(page, where);
}
