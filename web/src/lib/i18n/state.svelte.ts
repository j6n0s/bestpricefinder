/**
 * The current UI language as Svelte 5 `$state`, persisted through the storage module.
 *
 * `t()` reads the state, so any template or `$derived` that calls it re-renders when the language changes.
 */
import { isLang, load, update, type Lang } from '../storage';
import {
	translate,
	translatePlural,
	type MessageKey,
	type ParamArgs,
	type PluralArgs,
	type PluralKey
} from './messages';

let current = $state<Lang>(load().language);

/** Reactive read access: `i18n.lang`. */
export const i18n = {
	get lang(): Lang {
		return current;
	}
};

/** Sets <html lang> (screen readers, hyphenation). Safe outside the browser. */
export function syncDocumentLang(lang: Lang = current): void {
	if (typeof document !== 'undefined') document.documentElement.lang = lang;
}

/** Switches the UI language and stores the choice on this device. */
export function setLanguage(lang: Lang): void {
	if (!isLang(lang)) return;
	current = lang;
	update({ language: lang });
	syncDocumentLang(lang);
}

/** Re-reads the stored language (after "minden adat törlése" it is Hungarian again). */
export function reloadLanguage(): void {
	current = load().language;
	syncDocumentLang(current);
}

/** Translates `key` into the current language, filling its {placeholders} from `params`. */
export function t<K extends MessageKey>(key: K, ...args: ParamArgs<K>): string {
	return translate(current, key, ...args);
}

/** Plural form of `<base>_one` / `<base>_other` for `count` (available as {count}) in the current language. */
export function tp<B extends PluralKey>(base: B, count: number, ...args: PluralArgs<B>): string {
	return translatePlural(current, base, count, ...args);
}
