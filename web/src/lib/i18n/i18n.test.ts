import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { STORAGE_KEY, resetForTests } from '../storage';
import { DICTIONARIES, EN, HU, NAMESPACES, allKeys, interpolate, lookup, placeholders, pluralKey, translate, translatePlural } from './messages';

describe('dictionary parity', () => {
	it('has the eight namespaces', () => {
		expect([...NAMESPACES].sort()).toEqual(['cart', 'core', 'journey', 'list', 'plan', 'recipes', 'settings', 'sources']);
	});

	it('hu and en have identical key sets', () => {
		expect(allKeys('en')).toEqual(allKeys('hu'));
		for (const ns of NAMESPACES) expect(Object.keys(EN[ns]).sort(), ns).toEqual(Object.keys(HU[ns]).sort());
	});

	it('every message is a non-empty string without surrounding whitespace', () => {
		for (const lang of ['hu', 'en'] as const) {
			for (const ns of NAMESPACES) {
				for (const [key, text] of Object.entries(DICTIONARIES[lang][ns])) {
					expect(typeof text, `${lang}.${ns}.${key}`).toBe('string');
					expect(text.trim(), `${lang}.${ns}.${key}`).toBe(text);
					expect(text.length, `${lang}.${ns}.${key}`).toBeGreaterThan(0);
				}
			}
		}
	});

	it('hu and en use the same placeholders in every message', () => {
		for (const ns of NAMESPACES) {
			for (const [key, text] of Object.entries(HU[ns])) {
				const en = (EN[ns] as Record<string, string>)[key] ?? '';
				expect(placeholders(en), `${ns}.${key}`).toEqual(placeholders(text));
			}
		}
	});

	it('never puts a full stop after a date: hu-HU dates already end with one ("2026. 10. 13.")', () => {
		for (const lang of ['hu', 'en'] as const) {
			for (const ns of NAMESPACES) {
				for (const [key, text] of Object.entries(DICTIONARIES[lang][ns])) {
					expect(text, `${lang}.${ns}.${key}`).not.toMatch(/\{(date|period)\}\./);
				}
			}
		}
	});

	it('keys are snake_case', () => {
		for (const key of allKeys('hu')) expect(key).toMatch(/^[a-z]+\.[a-z0-9_]+$/);
	});

	it('every plural message has both forms', () => {
		for (const key of allKeys('hu')) {
			if (key.endsWith('_one')) expect(allKeys('hu')).toContain(key.replace(/_one$/, '_other'));
			if (key.endsWith('_other')) expect(allKeys('hu')).toContain(key.replace(/_other$/, '_one'));
		}
	});
});

describe('legal texts (BUILD-BRIEF §8)', () => {
	it('carries the exact Hungarian disclaimer', () => {
		expect(translate('hu', 'core.disclaimer')).toBe(
			'Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal.'
		);
	});

	it('carries the exact GVH attribution format', () => {
		expect(translate('hu', 'core.attribution_gvh', { date: '2026. 10. 13.' })).toBe(
			'Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), 2026. 10. 13.'
		);
	});

	it('labels KSH estimates and missing prices as required', () => {
		expect(translate('hu', 'core.badge_ksh_estimate')).toBe('becsült országos átlagár (KSH)');
		expect(translate('hu', 'core.attribution_ksh')).toBe('Forrás: KSH');
		expect(translate('hu', 'core.badge_no_price')).toBe('nincs ár');
		expect(translate('hu', 'core.badge_untested')).toBe('kipróbálatlan recept');
		expect(translate('hu', 'core.price_discounted')).toBe('kedvezményes ár (GVH-jelölés)');
	});

	it('names the app neutrally, without GVH or Árfigyelő in the name', () => {
		for (const lang of ['hu', 'en'] as const) {
			expect(translate(lang, 'core.app_name')).toBe('Heti kosár');
			expect(translate(lang, 'core.app_name')).not.toMatch(/gvh|árfigyelő|arfigyelo/i);
		}
	});

	it('makes no health claims and never names MDOSZ or OKOSTÁNYÉR', () => {
		const banned = /egészséges|egeszseges|healthy|fogyaszt|diéta|méregtelenít|immun|gyógy|betegség|mdosz|okostányér|okostanyer/i;
		for (const lang of ['hu', 'en'] as const) {
			for (const ns of NAMESPACES) {
				for (const [key, text] of Object.entries(DICTIONARIES[lang][ns])) {
					expect(text, `${lang}.${ns}.${key}`).not.toMatch(banned);
				}
			}
		}
	});
});

describe('translate', () => {
	it('fills placeholders', () => {
		expect(translate('hu', 'core.district_name', { roman: 'XI' })).toBe('XI. kerület');
		expect(translate('en', 'core.district_name', { roman: 'XI' })).toBe('District XI');
	});

	it('leaves a missing placeholder visible instead of printing undefined', () => {
		expect(interpolate('A {x} és {y}', { x: 1 })).toBe('A 1 és {y}');
		expect(interpolate('A {x}', {})).toBe('A {x}');
		expect(interpolate('A {x}')).toBe('A {x}');
	});

	it('does not read inherited properties as parameters', () => {
		expect(interpolate('{toString}', {})).toBe('{toString}');
	});

	it('inserts parameter values literally', () => {
		expect(interpolate('{a}', { a: '$& {b}' })).toBe('$& {b}');
	});

	it('falls back to Hungarian, then to the key', () => {
		expect(lookup('en', 'core.app_name')).toBe('Heti kosár');
		expect(lookup('en', 'core.no_such_key')).toBe('core.no_such_key');
		expect(lookup('hu', 'nonamespace')).toBe('nonamespace');
		expect(lookup('hu', 'core.__proto__')).toBe('core.__proto__');
	});
});

describe('plurals', () => {
	it('chooses one/other per language', () => {
		expect(pluralKey('en', 'settings.people_value', 1)).toBe('settings.people_value_one');
		expect(pluralKey('en', 'settings.people_value', 2)).toBe('settings.people_value_other');
		expect(translatePlural('en', 'settings.people_value', 1)).toBe('1\u00a0person');
		expect(translatePlural('en', 'settings.people_value', 3)).toBe('3\u00a0people');
		expect(translatePlural('hu', 'settings.people_value', 1)).toBe('1\u00a0fő');
		expect(translatePlural('hu', 'settings.people_value', 12)).toBe('12\u00a0fő');
	});
});

describe('current language state', () => {
	beforeEach(() => {
		resetForTests();
		vi.resetModules();
		const map = new Map<string, string>();
		vi.stubGlobal('localStorage', {
			get length() {
				return map.size;
			},
			key: (i: number) => [...map.keys()][i] ?? null,
			getItem: (k: string) => map.get(k) ?? null,
			setItem: (k: string, v: string) => void map.set(k, v),
			removeItem: (k: string) => void map.delete(k),
			clear: () => map.clear()
		} satisfies Storage);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		resetForTests();
	});

	it('defaults to Hungarian and persists the switch to English', async () => {
		const { i18n, setLanguage, t } = await import('./index');
		expect(i18n.lang).toBe('hu');
		expect(t('core.nav_settings')).toBe('Beállítások');
		setLanguage('en');
		expect(i18n.lang).toBe('en');
		expect(t('core.nav_settings')).toBe('Settings');
		expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')).toMatchObject({ language: 'en' });
	});

	it('starts in the stored language and ignores invalid values', async () => {
		localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, language: 'en' }));
		const { i18n, setLanguage, tp } = await import('./index');
		expect(i18n.lang).toBe('en');
		expect(tp('settings.people_value', 2)).toBe('2\u00a0people');
		setLanguage('de' as 'hu');
		expect(i18n.lang).toBe('en');
	});

	it('reloadLanguage returns to Hungarian after the data is cleared', async () => {
		const { i18n, setLanguage, reloadLanguage } = await import('./index');
		const storage = await import('../storage');
		setLanguage('en');
		storage.clearAll();
		reloadLanguage();
		expect(i18n.lang).toBe('hu');
	});
});
