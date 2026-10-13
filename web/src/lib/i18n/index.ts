/**
 * i18n entry point: `import { t, tp, i18n, setLanguage } from '$lib/i18n'`.
 *
 * Hungarian by default, with an English toggle (user decision, docs/QUESTIONS.md). Every user-visible string
 * goes through `t()`. Numbers, prices and dates are formatted hu-HU in both languages (src/lib/format.ts).
 *
 * Adding text: put the Hungarian string in `<namespace>.hu.ts` and the English one in `<namespace>.en.ts`
 * (the `Messages<>` type makes a missing or extra English key a compile error).
 */
export { i18n, reloadLanguage, setLanguage, syncDocumentLang, t, tp } from './state.svelte';
export {
	DICTIONARIES,
	NAMESPACES,
	translate,
	translatePlural,
	type MessageKey,
	type Namespace,
	type PlainKey,
	type PluralKey
} from './messages';
export { LANGS, type Lang } from '../storage';
