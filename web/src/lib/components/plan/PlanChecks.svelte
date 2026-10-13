<!--
	One week's rule checks as neutral, factual chips: "Hal: 2 (cél: legalább 1)". A chip whose target is not
	met is marked with "!" and a visible border; screen readers hear "teljesül" / "nem teljesül".
	No health claims (BUILD-BRIEF §8.7).
-->
<script lang="ts">
	import type { RuleCheckOut } from '$lib/api/types';
	import { i18n, t } from '$lib/i18n';
	import { checkText } from '$lib/plan/checks';

	interface Props {
		checks: readonly RuleCheckOut[];
		/** id of the heading that labels the list */
		labelledBy: string;
	}

	let { checks, labelledBy }: Props = $props();
</script>

<ul class="checks" aria-labelledby={labelledBy}>
	{#each checks as check (check.rule)}
		<li class="check" class:miss={!check.ok} data-testid="check-{check.rule}" data-ok={check.ok}>
			<span class="mark" aria-hidden="true">{check.ok ? '✓' : '!'}</span>
			<span class="text">{checkText(check, i18n.lang)}</span>
			<span class="visually-hidden">({check.ok ? t('plan.check_ok') : t('plan.check_not_ok')})</span>
		</li>
	{/each}
</ul>

<style>
	.checks {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.check {
		display: inline-flex;
		align-items: baseline;
		gap: var(--space-2);
		max-width: 100%;
		padding: var(--space-1) var(--space-3);
		border: 1px solid var(--color-border-subtle);
		border-radius: var(--radius-md);
		background: var(--color-neutral-bg);
		color: var(--color-neutral-text);
		font-size: var(--font-size-sm);
	}

	.miss {
		background: var(--color-warning-bg);
		color: var(--color-warning-text);
		border-color: var(--color-warning-border);
	}

	.mark {
		flex: none;
		font-weight: 700;
	}
</style>
