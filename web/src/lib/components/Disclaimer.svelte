<!--
	The mandatory disclaimer (BUILD-BRIEF §8.1). The Hungarian sentence is always shown verbatim; in the English
	UI its translation follows it.
-->
<script lang="ts">
	import { i18n, t, translate } from '$lib/i18n';
</script>

<p class="disclaimer" data-testid="disclaimer">
	<span lang="hu">{translate('hu', 'core.disclaimer')}</span>
	{#if i18n.lang !== 'hu'}
		<span>{t('core.disclaimer')}</span>
	{/if}
</p>

<style>
	.disclaimer {
		color: var(--color-text-muted);
		margin: 0;
	}
</style>
