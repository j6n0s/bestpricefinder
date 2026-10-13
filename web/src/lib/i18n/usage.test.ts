/**
 * Every dictionary key must be used: referenced as a quoted literal ('ns.key', or 'ns.base' for a plural
 * pair base_one/base_other) somewhere in src/ outside the dictionaries and the tests, or listed in ALLOWED
 * below with the exact source text that uses it. A key that nothing renders is dead text that still has to
 * be translated and reviewed (legal wording included), so it is deleted instead.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { RECIPE_TAGS } from '../api/types';
import { allKeys } from './messages';

const SRC = fileURLToPath(new URL('../..', import.meta.url));

interface Allowed {
	/** The keys this entry covers. */
	keys: readonly string[];
	/** File (relative to src/) and the exact text in it that uses the keys without a quoted literal. */
	file: string;
	evidence: string;
	why: string;
}

/** Keys that are used, but not through a quoted literal. Keep this list short and exact. */
const ALLOWED: readonly Allowed[] = [
	{
		keys: RECIPE_TAGS.map((tag) => `recipes.tag_${tag}`),
		file: 'lib/plan/recipes.ts',
		evidence: '`recipes.tag_${tag}`',
		why: 'tag labels are looked up by the tag value (tagLabelKey)'
	},
	{
		keys: ['core.unit_kg', 'core.unit_l', 'core.unit_db'],
		file: 'lib/format.ts',
		evidence: 'dict.unit_kg',
		why: 'unitName() reads the unit names straight from the core dictionaries'
	}
];

function sourceFiles(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return sourceFiles(path);
		return /\.(ts|js|svelte)$/.test(entry.name) ? [path] : [];
	});
}

const isDictionary = (path: string): boolean => /[/\\]lib[/\\]i18n[/\\][a-z]+\.(hu|en)\.ts$/.test(path);
const isTest = (path: string): boolean => /\.test\.ts$/.test(path);

const files = sourceFiles(SRC).filter((path) => !isDictionary(path) && !isTest(path));
const code = files.map((path) => readFileSync(path, 'utf8')).join('\n');

function quoted(key: string): boolean {
	return [`'${key}'`, `"${key}"`, `\`${key}\``].some((literal) => code.includes(literal));
}

function referenced(key: string): boolean {
	const plural = /^(.+)_(one|other)$/.exec(key);
	return quoted(key) || (plural !== null && quoted(plural[1] ?? ''));
}

describe('i18n key usage', () => {
	const keys = allKeys('hu');
	const allowed = new Set(ALLOWED.flatMap((entry) => entry.keys));

	it('scans the app source (and not the dictionaries or the tests)', () => {
		expect(files.length).toBeGreaterThan(50);
		expect(files.some(isDictionary)).toBe(false);
		expect(files.map((path) => relative(SRC, path).split(sep).join('/'))).toContain('lib/components/Attribution.svelte');
	});

	it('every key is referenced in src/ or explicitly allowed', () => {
		const unused = keys.filter((key) => !referenced(key) && !allowed.has(key));
		expect(unused, 'delete these keys from both dictionaries, or use them').toEqual([]);
	});

	it('the allow-list is exact: existing keys only, each one really used that way and not quoted elsewhere', () => {
		for (const entry of ALLOWED) {
			const text = readFileSync(join(SRC, entry.file), 'utf8');
			expect(text, `${entry.file}: ${entry.why}`).toContain(entry.evidence);
			for (const key of entry.keys) {
				expect(keys, `${key} (${entry.why})`).toContain(key);
				expect(referenced(key), `${key} is quoted somewhere: drop it from ALLOWED`).toBe(false);
			}
		}
	});

	it('has a label for every recipe tag and no label for a tag that does not exist', () => {
		const tagKeys = keys.filter((key) => key.startsWith('recipes.tag_'));
		expect(tagKeys.sort()).toEqual(RECIPE_TAGS.map((tag) => `recipes.tag_${tag}`).sort());
	});
});
