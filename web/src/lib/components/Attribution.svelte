<!--
	Source line required on EVERY view that shows prices (BUILD-BRIEF §8.2):
	  "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), <data date>"
	plus, when the view shows a KSH estimate, "Forrás: KSH" with the link and the period, and by default the
	disclaimer. Pass the data date of the response the prices came from (e.g. QuoteResponse.data_date).
	`chainTypical` starts the line with "Lánc-jellemző árak." where every price shown is a chain-typical one
	(recipes and plan, BUILD-BRIEF §8.6).
-->
<script lang="ts">
	import { formatDate, formatMonth } from '$lib/format';
	import { t } from '$lib/i18n';
	import { safeKshUrl } from '$lib/sources';
	import Disclaimer from './Disclaimer.svelte';

	interface Props {
		/** "YYYY-MM-DD" of the price data shown. */
		dataDate: string | null;
		/** The view shows at least one "becsült országos átlagár (KSH)" value. */
		ksh?: boolean;
		/** KSH period "YYYY-MM-01" (MetaResponse.ksh_period). */
		kshPeriod?: string | null;
		/** KSH link from MetaResponse.attribution.ksh.url (defaults to the ara0044 table). */
		kshUrl?: string | null;
		showDisclaimer?: boolean;
		/** Every price in the view is a chain-typical price (recipes, plan). */
		chainTypical?: boolean;
	}

	let { dataDate, ksh = false, kshPeriod = null, kshUrl = null, showDisclaimer = true, chainTypical = false }: Props = $props();

	const date = $derived(formatDate(dataDate));
	const period = $derived(formatMonth(kshPeriod));
	const kshHref = $derived(safeKshUrl(kshUrl));
</script>

<div class="attribution small muted" data-testid="attribution">
	<p data-testid="attribution-gvh">
		{#if chainTypical}{t('core.attribution_chain_typical')}{' '}{/if}{date
			? t('core.attribution_gvh', { date })
			: t('core.attribution_gvh_undated')}
	</p>
	{#if ksh}
		<p data-testid="attribution-ksh">
			<span>{t('core.attribution_ksh_label')}.</span>
			<a href={kshHref} rel="noopener noreferrer" target="_blank">
				{period ? t('core.attribution_ksh_period', { period }) : t('core.attribution_ksh')}
			</a>
		</p>
	{/if}
	{#if showDisclaimer}
		<Disclaimer compact />
	{/if}
</div>

<style>
	.attribution {
		color: var(--color-text-muted);
		border-top: 1px solid var(--color-border-subtle);
		padding-top: var(--space-2);
		margin-top: var(--space-4);
	}

	.attribution p {
		margin: 0 0 var(--space-1);
	}

	a {
		display: inline-block;
		padding: var(--space-1) 0;
	}
</style>
