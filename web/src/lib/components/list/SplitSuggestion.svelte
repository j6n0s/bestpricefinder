<!--
	The optional 2-store split from POST /api/quote (`split`, offered by the server only when it saves at
	least 1,500 Ft against the best single store): "Két boltban x Ft-tal olcsóbb", with which line goes where.
	The server leaves the lines that neither store sells out of the split's total and assignment, so the card
	names them and says the total does not include them.
-->
<script lang="ts">
	import type { SplitOut, StoreId, StoreQuoteOut } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import { formatMoney } from '$lib/format';
	import { t, tp } from '$lib/i18n';
	import { splitMissing, splitParts } from '$lib/list/ranking';

	interface Props {
		split: SplitOut;
		/** The quote's stores (their `missing` lines). */
		stores: readonly StoreQuoteOut[];
		/** Plain-text label of a store ("Lidl, 1051 Budapest, …"). */
		storeLabel: (storeId: StoreId) => string;
		/** Display name of an ingredient. */
		lineName: (ingredientId: string) => string;
	}

	let { split, stores, storeLabel, lineName }: Props = $props();

	const parts = $derived(splitParts(split));
	const missing = $derived(splitMissing(split, stores));
</script>

<div class="notice notice-info split" data-testid="split">
	<p><strong>{t('list.split_title', { saving: formatMoney(split.saving) })}</strong></p>
	<p>
		{t('list.split_text', {
			first: storeLabel(split.store_ids[0]),
			second: storeLabel(split.store_ids[1]),
			total: formatMoney(split.total)
		})}
		{#if missing.length > 0}
			{tp('list.split_total_excludes', missing.length)}
		{/if}
	</p>
	{#if missing.length > 0}
		<p data-testid="split-missing">
			<Badge tone="warning">{tp('list.split_missing', missing.length)}</Badge>
			<span lang="hu">{missing.map(lineName).join(', ')}</span>
		</p>
	{/if}
	<details>
		<summary>{t('list.split_details')}</summary>
		{#each parts as part (part.storeId)}
			<p>
				<strong>{t('list.split_store', { store: storeLabel(part.storeId) })}</strong>
				<span lang="hu">{part.ingredientIds.map(lineName).join(', ')}</span>
			</p>
		{/each}
	</details>
</div>

<style>
	.split p {
		margin: 0 0 var(--space-2);
	}

	summary {
		padding: 10px 0;
		cursor: pointer;
		font-weight: 600;
	}
</style>
