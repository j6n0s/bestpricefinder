/**
 * Texts for the weekly rule checks and the suggestion warnings of /api/plan/suggest and /api/plan/check.
 *
 * The API reports each check with Hungarian `value` and `limit` strings ("2 hal", "≥ 1", "450 g/fő",
 * "≤ 600 g/fő", "n/a", …; server/bpf/planner/rules.py). The numbers are read out of them and put into the
 * UI language's own words, formatted hu-HU: a tile of the rule's name, the value and the target ("Hal", "2",
 * "legalább 1"). When a string does not have the expected shape, the server's own text is shown instead
 * (`plan.check_fallback_target`), never a guess.
 * The wording is neutral and factual (no health claims, BUILD-BRIEF §8.7).
 */
import { SLOTS, type RuleCheckOut, type RuleName, type Slot } from '../api/types';
import { formatMoney, formatNumber } from '../format';
import { translate, translatePlural, type PlainKey } from '../i18n/messages';
import type { Lang } from '../storage';

/** The order the API reports rules in, used for display. */
export const RULE_ORDER: readonly RuleName[] = [
	'fish',
	'legume',
	'meat_free_day',
	'red_meat',
	'potato',
	'sweets',
	'variety',
	'budget'
];

/** Count rules (fish, legume, meat-free day) are assessed only for weeks of at least this many days. */
export const COUNT_RULE_MIN_DAYS = 4;
/** The API's value for a count rule in a shorter week. */
const NOT_APPLICABLE = 'n/a';

const RULE_LABEL: Readonly<Record<RuleName, PlainKey>> = {
	fish: 'plan.rule_fish',
	legume: 'plan.rule_legume',
	meat_free_day: 'plan.rule_meat_free_day',
	red_meat: 'plan.rule_red_meat',
	potato: 'plan.rule_potato',
	sweets: 'plan.rule_sweets',
	variety: 'plan.rule_variety',
	budget: 'plan.rule_budget'
};

function ruleRank(rule: string): number {
	const index = (RULE_ORDER as readonly string[]).indexOf(rule);
	return index === -1 ? RULE_ORDER.length : index;
}

/** The checks of one week (0-based), in RULE_ORDER. */
export function checksForWeek(checks: readonly RuleCheckOut[], week: number): RuleCheckOut[] {
	return checks.filter((check) => check.week === week).sort((a, b) => ruleRank(a.rule) - ruleRank(b.rule));
}

/** The first whole number in a text ("≤ 600 g/fő" -> 600), or null. */
export function firstInt(text: string): number | null {
	const match = /\d+/.exec(text);
	return match ? Number(match[0]) : null;
}

export function ruleLabel(rule: RuleName, lang: Lang): string {
	return translate(lang, RULE_LABEL[rule]);
}

/** The count rules are not checked in a week shorter than COUNT_RULE_MIN_DAYS days ("n/a"). */
export function notApplicable(check: RuleCheckOut): boolean {
	return check.value.trim() === NOT_APPLICABLE;
}

/** A weekly check as the week summary shows it: the rule's name, its value and the target. */
export interface CheckParts {
	label: string;
	value: string;
	target: string;
}

/** The check's parts in `lang`, e.g. { label: "Hal", value: "2", target: "legalább 1" }. */
export function checkParts(check: RuleCheckOut, lang: Lang): CheckParts {
	const label = Object.hasOwn(RULE_LABEL, check.rule) ? ruleLabel(check.rule, lang) : check.rule;
	const fallback = (): CheckParts => ({
		label,
		value: check.value,
		target: translate(lang, 'plan.check_fallback_target', { limit: check.limit })
	});
	const value = firstInt(check.value);
	const limit = firstInt(check.limit);

	switch (check.rule) {
		case 'fish':
		case 'legume':
		case 'meat_free_day':
			if (notApplicable(check)) {
				return { label, value: '–', target: translate(lang, 'plan.check_not_applicable_target', { days: COUNT_RULE_MIN_DAYS }) };
			}
			if (value === null || limit === null) return fallback();
			return { label, value: formatNumber(value), target: translate(lang, 'plan.check_target_at_least', { min: formatNumber(limit) }) };
		case 'red_meat':
			if (value === null || limit === null) return fallback();
			return {
				label,
				value: translate(lang, 'plan.check_red_meat_value', { value: formatNumber(value) }),
				target: translate(lang, 'plan.check_red_meat_target', { max: formatNumber(limit) })
			};
		case 'potato':
			if (value === null || limit === null) return fallback();
			return {
				label,
				value: translatePlural(lang, 'plan.check_potato_value', value),
				target: translate(lang, 'plan.check_potato_target', { max: formatNumber(limit) })
			};
		case 'sweets':
			if (value === null || limit === null) return fallback();
			return { label, value: formatNumber(value), target: translate(lang, 'plan.check_target_at_most', { max: formatNumber(limit) }) };
		case 'variety': {
			const windows = [...check.limit.matchAll(/(\d+) napon belül/g)].map((match) => Number(match[1]));
			const [days, snackDays] = windows;
			if (value === null || days === undefined) return fallback();
			return {
				label,
				value: translatePlural(lang, 'plan.check_variety_value', value),
				target:
					snackDays === undefined
						? translate(lang, 'plan.check_variety_target', { days })
						: translate(lang, 'plan.check_variety_snacks_target', { days, snack_days: snackDays })
			};
		}
		case 'budget': {
			if (value === null || limit === null) return fallback();
			const unpriced = /\+\s*(\d+)/.exec(check.value);
			const money = formatMoney(value);
			return {
				label,
				value: unpriced
					? translatePlural(lang, 'plan.check_budget_unpriced_value', Number(unpriced[1]), { value: money })
					: money,
				target: translate(lang, 'plan.check_target_at_most', { max: formatMoney(limit) })
			};
		}
		default:
			return fallback();
	}
}

/** The check in one line, e.g. "Hal: 2 (legalább 1)". */
export function checkText(check: RuleCheckOut, lang: Lang): string {
	const { label, value, target } = checkParts(check, lang);
	return `${label}: ${value} (${target})`;
}

const PLAIN_WARNINGS: Readonly<Record<string, PlainKey>> = {
	no_fish_recipe_available: 'plan.warning_no_fish_recipe_available',
	no_legume_recipe_available: 'plan.warning_no_legume_recipe_available',
	red_meat_cap_unreachable: 'plan.warning_red_meat_cap_unreachable',
	sweets_cap_unreachable: 'plan.warning_sweets_cap_unreachable',
	budget_unreachable: 'plan.warning_budget_unreachable',
	recipe_cost_missing: 'plan.warning_recipe_cost_missing'
};

type SlotWarningKey =
	| 'plan.warning_slot_pool_empty'
	| 'plan.warning_slot_pool_too_small'
	| 'plan.warning_no_meat_free_recipe_available'
	| 'plan.warning_no_potato_free_recipe_available';

const SLOT_WARNINGS: Readonly<Record<string, SlotWarningKey>> = {
	slot_pool_empty: 'plan.warning_slot_pool_empty',
	slot_pool_too_small: 'plan.warning_slot_pool_too_small',
	no_meat_free_recipe_available: 'plan.warning_no_meat_free_recipe_available',
	no_potato_free_recipe_available: 'plan.warning_no_potato_free_recipe_available'
};

const SLOT_LABEL: Readonly<Record<Slot, PlainKey>> = {
	reggeli: 'core.slot_reggeli',
	tizorai: 'core.slot_tizorai',
	ebed: 'core.slot_ebed',
	uzsonna: 'core.slot_uzsonna',
	vacsora: 'core.slot_vacsora'
};

export function isSlot(value: unknown): value is Slot {
	return typeof value === 'string' && (SLOTS as readonly string[]).includes(value);
}

/** "Reggeli" / "Breakfast". */
export function slotLabel(slot: Slot, lang: Lang): string {
	return translate(lang, SLOT_LABEL[slot]);
}

/** The slot name inside a sentence: "reggeli" / "breakfast". */
export function slotLabelLower(slot: Slot, lang: Lang): string {
	return slotLabel(slot, lang).toLocaleLowerCase(lang === 'hu' ? 'hu-HU' : 'en');
}

/** A warning code of /api/plan/suggest as a sentence; unknown or malformed codes are named as such. */
export function warningText(code: string, lang: Lang): string {
	const colon = code.indexOf(':');
	const name = colon === -1 ? code : code.slice(0, colon);
	const arg = colon === -1 ? null : code.slice(colon + 1);
	if (arg === null && Object.hasOwn(PLAIN_WARNINGS, name)) {
		const key = PLAIN_WARNINGS[name];
		if (key) return translate(lang, key);
	}
	if (arg !== null && isSlot(arg) && Object.hasOwn(SLOT_WARNINGS, name)) {
		const key = SLOT_WARNINGS[name];
		if (key) return translate(lang, key, { slot: slotLabelLower(arg, lang) });
	}
	return translate(lang, 'plan.warning_unknown', { code });
}

/** Warning codes without duplicates, in their first-seen order. */
export function uniqueWarnings(codes: readonly string[]): string[] {
	return [...new Set(codes)];
}
