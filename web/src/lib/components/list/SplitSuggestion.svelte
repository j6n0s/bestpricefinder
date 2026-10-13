<!--
	The optional 2-store split from POST /api/quote (`split`, offered by the server only when it saves at
	least 1,500 Ft against the best single store): "Két boltban x Ft-tal olcsóbb", with which line goes where.
-->
<script lang="ts">
	import type { SplitOut, StoreId } from '$lib/api/types';
	import { formatMoney } from '$lib/format';
	import { t } from '$lib/i18n';
	import { splitParts } from '$lib/list/ranking';

	interface Props {
		split: SplitOut;
		/** Plain-text label of a store ("Lidl, 1051 Budapest, …"). */
		storeLabel: (storeId: StoreId) => string;
		/** Display name of an ingredient. */
		lineName: (ingredientId: string) => string;
	}

	let { split, storeLabel, lineName }: Props = $props();

	const parts = $derived(splitParts(split));
</script>

<div class="notice notice-info split" data-testid="split">
	<p><strong>{t('list.split_title', { saving: formatMoney(split.saving) })}</strong></p>
	<p>
		{t('list.split_text', {
			first: storeLabel(split.store_ids[0]),
			second: storeLabel(split.store_ids[1]),
			total: formatMoney(split.total)
		})}
	</p>
	<details>
		<summary>{t('list.split_details')}</summary>
		{#each parts as part (part.storeId)}
			<p>
				<strong>{t('list.split_store', { store: storeLabel(part.storeId) })}</strong>
				{part.ingredientIds.map(lineName).join(', ')}
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
