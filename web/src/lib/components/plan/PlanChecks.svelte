<!--
	One week's rule checks as a grid of equal tiles: the rule's name, the value and the target ("Hal", "2",
	"legalább 1"). A met target has a green border; a missed or not checked one is a plain tile, not coloured.
	No icons. Screen readers hear "teljesül" / "nem teljesül". Neutral, factual wording: no health claims
	(BUILD-BRIEF §8.7).
-->
<script lang="ts">
	import type { RuleCheckOut } from '$lib/api/types';
	import { i18n, t } from '$lib/i18n';
	import { checkParts, notApplicable } from '$lib/plan/checks';

	interface Props {
		checks: readonly RuleCheckOut[];
		/** id of the heading that labels the list */
		labelledBy: string;
	}

	let { checks, labelledBy }: Props = $props();
</script>

<ul class="checks" aria-labelledby={labelledBy}>
	{#each checks as check (check.rule)}
		{@const parts = checkParts(check, i18n.lang)}
		<li class="check" class:met={check.ok && !notApplicable(check)} data-testid="check-{check.rule}" data-ok={check.ok}>
			<span class="label">{parts.label}</span>
			<span class="value">{parts.value}</span>
			<span class="target">{parts.target}</span>
			<span class="visually-hidden">({check.ok ? t('plan.check_ok') : t('plan.check_not_ok')})</span>
		</li>
	{/each}
</ul>

<style>
	.checks {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 8.5rem), 1fr));
		gap: var(--space-2);
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.check {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
		padding: var(--space-2) var(--space-3);
		border: 2px solid var(--color-border-subtle);
		border-radius: var(--radius-md);
		background: var(--color-surface);
		color: var(--color-text);
	}

	.met {
		border-color: var(--color-success-border);
	}

	.label {
		font-size: var(--font-size-sm);
		font-weight: 600;
	}

	.value {
		font-size: var(--font-size-lg);
		font-weight: 700;
		line-height: 1.25;
	}

	.target {
		font-size: var(--font-size-sm);
		color: var(--color-text-muted);
	}
</style>
