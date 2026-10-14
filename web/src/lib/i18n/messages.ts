/**
 * Dictionaries and the pure `translate` function (no runes, no globals): testable in plain Node.
 *
 * Keys are "<namespace>.<key>", e.g. "core.app_name". Hungarian is the source language: its dictionaries
 * define the keys and the placeholders ({name}); every English dictionary must have exactly the same keys
 * (enforced by the `Messages<>` type and by src/lib/i18n/i18n.test.ts, which also compares placeholders).
 *
 * Plurals: a message pair "<key>_one" / "<key>_other" is chosen with Intl.PluralRules (see `pluralKey`).
 */
import type { Lang } from '../storage';
import { cartEn } from './cart.en';
import { cartHu } from './cart.hu';
import { coreEn } from './core.en';
import { coreHu } from './core.hu';
import { journeyEn } from './journey.en';
import { journeyHu } from './journey.hu';
import { listEn } from './list.en';
import { listHu } from './list.hu';
import { planEn } from './plan.en';
import { planHu } from './plan.hu';
import { recipesEn } from './recipes.en';
import { recipesHu } from './recipes.hu';
import { settingsEn } from './settings.en';
import { settingsHu } from './settings.hu';
import { sourcesEn } from './sources.en';
import { sourcesHu } from './sources.hu';
import type { Messages, ParamNames, ParamValue } from './types';

export const HU = {
	core: coreHu,
	plan: planHu,
	recipes: recipesHu,
	list: listHu,
	journey: journeyHu,
	cart: cartHu,
	settings: settingsHu,
	sources: sourcesHu
} as const;

type Source = typeof HU;
export type Namespace = keyof Source;

export const EN: { readonly [N in Namespace]: Messages<Source[N]> } = {
	core: coreEn,
	plan: planEn,
	recipes: recipesEn,
	list: listEn,
	journey: journeyEn,
	cart: cartEn,
	settings: settingsEn,
	sources: sourcesEn
};

export const DICTIONARIES: Readonly<Record<Lang, { readonly [N in Namespace]: Readonly<Record<string, string>> }>> = {
	hu: HU,
	en: EN
};

export const NAMESPACES = Object.keys(HU) as Namespace[];

export type MessageKey = {
	[N in Namespace]: `${N}.${Extract<keyof Source[N], string>}`;
}[Namespace];

type SourceText<K extends MessageKey> = K extends `${infer N extends Namespace}.${infer Key}`
	? Key extends keyof Source[N]
		? Source[N][Key] extends string
			? Source[N][Key]
			: never
		: never
	: never;

/** The placeholder names of a message key, from its Hungarian source text. */
export type ParamsOf<K extends MessageKey> = ParamNames<SourceText<K>>;

/** Keys whose message has no placeholder: safe to pass to `t()` when the key is chosen at run time. */
export type PlainKey = { [K in MessageKey]: [ParamsOf<K>] extends [never] ? K : never }[MessageKey];

/** `[]` for messages without placeholders, else `[params]` with every placeholder required. */
export type ParamArgs<K extends MessageKey> = [ParamsOf<K>] extends [never]
	? [params?: Record<string, never>]
	: [params: Record<ParamsOf<K>, ParamValue>];

/** Base keys that have both a "_one" and an "_other" form. */
export type PluralKey = {
	[K in MessageKey]: K extends `${infer Base}_one` ? (`${Base}_other` extends MessageKey ? Base : never) : never;
}[MessageKey];

type PluralParams<B extends PluralKey> = Exclude<
	ParamsOf<Extract<`${B}_one` | `${B}_other`, MessageKey>>,
	'count'
>;

export type PluralArgs<B extends PluralKey> = [PluralParams<B>] extends [never]
	? [params?: Record<string, never>]
	: [params: Record<PluralParams<B>, ParamValue>];

const PLACEHOLDER = /\{([a-z_][a-z0-9_]*)\}/gi;

/** Fills {name} placeholders; a missing parameter leaves its placeholder visible (never "undefined"). */
export function interpolate(text: string, params?: Readonly<Record<string, ParamValue>>): string {
	if (!params) return text;
	return text.replace(PLACEHOLDER, (whole: string, name: string) => {
		const value = Object.hasOwn(params, name) ? params[name] : undefined;
		return value === undefined ? whole : String(value);
	});
}

/** The raw message text in `lang` (falls back to Hungarian, then to the key itself). */
export function lookup(lang: Lang, key: string): string {
	const dot = key.indexOf('.');
	if (dot < 1) return key;
	const ns = key.slice(0, dot);
	const name = key.slice(dot + 1);
	const fromLang = (DICTIONARIES[lang] as Readonly<Record<string, Readonly<Record<string, string>>>>)[ns];
	if (fromLang && Object.hasOwn(fromLang, name)) return fromLang[name] ?? key;
	const fromHu = (DICTIONARIES.hu as Readonly<Record<string, Readonly<Record<string, string>>>>)[ns];
	if (fromHu && Object.hasOwn(fromHu, name)) return fromHu[name] ?? key;
	return key;
}

/** Pure translation in an explicit language. */
export function translate<K extends MessageKey>(lang: Lang, key: K, ...args: ParamArgs<K>): string {
	return interpolate(lookup(lang, key), args[0] as Readonly<Record<string, ParamValue>> | undefined);
}

const pluralRules: Record<Lang, Intl.PluralRules> = {
	hu: new Intl.PluralRules('hu'),
	en: new Intl.PluralRules('en')
};

/** "<base>_one" or "<base>_other" for `count` in `lang` (both languages only have these two categories). */
export function pluralKey<B extends PluralKey>(lang: Lang, base: B, count: number): MessageKey {
	const category = pluralRules[lang].select(count);
	return (category === 'one' ? `${base}_one` : `${base}_other`) as MessageKey;
}

/** Pure plural translation: the message gets `{count}` plus `params`. */
export function translatePlural<B extends PluralKey>(lang: Lang, base: B, count: number, ...args: PluralArgs<B>): string {
	const params: Record<string, ParamValue> = { ...(args[0] ?? {}), count };
	return interpolate(lookup(lang, pluralKey(lang, base, count)), params);
}

/** Every key of a language's dictionaries, as "<namespace>.<key>" (used by the parity test). */
export function allKeys(lang: Lang): string[] {
	const dicts = DICTIONARIES[lang];
	return NAMESPACES.flatMap((ns) => Object.keys(dicts[ns]).map((key) => `${ns}.${key}`)).sort();
}

/** The sorted placeholder names in a text. */
export function placeholders(text: string): string[] {
	return [...text.matchAll(PLACEHOLDER)].map((match) => match[1] ?? '').sort();
}
