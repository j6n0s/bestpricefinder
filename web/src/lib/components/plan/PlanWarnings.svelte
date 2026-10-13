<!-- The notes (machine warning codes) of the last suggestion, as plain sentences. -->
<script lang="ts">
	import { i18n, t } from '$lib/i18n';
	import { warningText } from '$lib/plan/checks';

	interface Props {
		codes: readonly string[];
	}

	let { codes }: Props = $props();
</script>

{#if codes.length > 0}
	<section class="notice notice-info" aria-labelledby="plan-warnings-title" data-testid="plan-warnings">
		<h3 id="plan-warnings-title" class="title">{t('plan.warnings_title')}</h3>
		<ul>
			{#each codes as code (code)}
				<li>{warningText(code, i18n.lang)}</li>
			{/each}
		</ul>
	</section>
{/if}

<style>
	.title {
		font-size: var(--font-size-base);
		margin-bottom: var(--space-2);
	}

	ul {
		margin: 0;
		padding-left: var(--space-5);
	}
</style>
