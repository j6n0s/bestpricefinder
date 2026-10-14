<!--
	Source line required on EVERY view that shows prices (BUILD-BRIEF §8.2), once per page, at the bottom:
	a closed "Források" disclosure whose one visible line still names the source and the data date
	("Források: GVH Árfigyelő, 2026. 10. 13."; ", KSH" when a KSH estimate is shown). Opened, it gives the full
	line "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), <data date>", "Lánc-jellemző árak." where every price is
	chain-typical (§8.6), and "Forrás: KSH" with the link and the period. The disclaimer (§8.1) is in the page
	footer, once per page. `collapsible={false}` shows the lines open (the sources page).
	Pass the data date of the response the prices came from (e.g. QuoteResponse.data_date).
-->
<script lang="ts">
	import { formatDate, formatMonth } from '$lib/format';
	import { t } from '$lib/i18n';
	import { safeKshUrl } from '$lib/sources';

	interface Props {
		/** "YYYY-MM-DD" of the price data shown. */
		dataDate: string | null;
		/** The view shows at least one "becsült országos átlagár (KSH)" value. */
		ksh?: boolean;
		/** KSH period "YYYY-MM-01" (MetaResponse.ksh_period). */
		kshPeriod?: string | null;
		/** KSH link from MetaResponse.attribution.ksh.url (defaults to the ara0044 table). */
		kshUrl?: string | null;
		/** Every price in the view is a chain-typical price (recipes, plan). */
		chainTypical?: boolean;
		/** false: the lines are shown open, without the disclosure (the sources page). */
		collapsible?: boolean;
	}

	let { dataDate, ksh = false, kshPeriod = null, kshUrl = null, chainTypical = false, collapsible = true }: Props = $props();

	const date = $derived(formatDate(dataDate));
	const period = $derived(formatMonth(kshPeriod));
	const kshHref = $derived(safeKshUrl(kshUrl));
	const summary = $derived(
		`${date ? t('core.sources_summary', { date }) : t('core.sources_summary_undated')}${ksh ? t('core.sources_summary_ksh') : ''}`
	);
</script>

{#snippet lines()}
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
{/snippet}

{#if collapsible}
	<details class="attribution small" data-testid="attribution">
		<summary class="muted" data-testid="attribution-summary">{summary}</summary>
		<div class="body muted">{@render lines()}</div>
	</details>
{:else}
	<div class="attribution small muted" data-testid="attribution">{@render lines()}</div>
{/if}

<style>
	/* Same look as "Hogyan számoljuk?" (HowCalculated): a muted one-line disclosure. */
	.attribution {
		margin-top: var(--space-4);
	}

	summary {
		/* list-item keeps the disclosure marker; min-height and padding make a 44 px target. */
		min-height: var(--tap);
		padding: var(--space-3) 0;
		cursor: pointer;
	}

	.attribution p {
		margin: 0 0 var(--space-1);
	}

	a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}
</style>
