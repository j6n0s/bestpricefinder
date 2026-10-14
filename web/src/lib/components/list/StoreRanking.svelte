<!--
	The nearby stores ranked by what the list costs there (POST /api/quote `ranking`), cheapest first. The
	ranking is always shown with the server's scope note ("a kiválasztott boltok közül, a … GVH-adatok
	alapján", BUILD-BRIEF §8.6). Tied stores share a rank, are all marked as tied and are ordered by distance,
	never by chain or store name (trap 13). Chain names are plain text (no logos). How "Fizetendő" and the order
	are worked out is behind a closed "Hogyan számoljuk?" disclosure.
-->
<script lang="ts">
	import type { ChainSlug, QuoteResponse, StoreId, StoreOut } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import HowCalculated from '$lib/components/HowCalculated.svelte';
	import { formatDistance, formatMoney } from '$lib/format';
	import { i18n, t, tp } from '$lib/i18n';
	import { hasPenalty, scopeNote, type RankRow } from '$lib/list/ranking';
	import { chainLabel, storeAddress } from '$lib/list/stores';

	interface Props {
		quote: QuoteResponse;
		rows: readonly RankRow[];
		stores: ReadonlyMap<StoreId, StoreOut>;
		names: ReadonlyMap<ChainSlug, string>;
		chosenStoreId: StoreId | null;
		onchoose: (storeId: StoreId) => void;
	}

	let { quote, rows, stores, names, chosenStoreId, onchoose }: Props = $props();
	const id = $props.id();
</script>

<section class="ranking" aria-labelledby="{id}-title" data-testid="store-ranking">
	<h3 id="{id}-title">{t('list.ranking_title')}</h3>
	<p data-testid="ranking-scope">{t('list.ranking_scope', { note: scopeNote(quote, i18n.lang) })}</p>
	<HowCalculated testid="ranking-how"><p>{t('list.ranking_basis')}</p></HowCalculated>

	<ol class="ranks">
		{#each rows as row (row.storeId)}
			{@const chain = chainLabel(row.chain, names)}
			{@const address = storeAddress(stores.get(row.storeId))}
			{@const chosen = row.storeId === chosenStoreId}
			<li class="card rank-card" class:chosen data-testid="rank-row" data-store-id={row.storeId}>
				<div class="head">
					<span class="rank" data-testid="rank">{t('list.rank', { rank: row.rank })}</span>
					<span class="chain">{chain}</span>
					{#if row.tied}
						<Badge tone="info">{t('list.tie')}</Badge>
					{/if}
					{#if chosen}
						<Badge tone="success">{t('list.chosen_store')}</Badge>
					{/if}
				</div>
				<p class="where small">
					{address}{#if row.distanceKm !== null}{address ? ' · ' : ''}<span class="distance">{formatDistance(row.distanceKm)}</span>{/if}
				</p>
				{#if hasPenalty(row)}
					<!-- The figure the order uses comes first, so the order never looks wrong next to a lower
					     "Fizetendő" of a store where more items are missing. -->
					<p class="total" data-testid="rank-penalized">
						{t('list.penalized_label')}: <strong>{formatMoney(row.penalizedTotal)}</strong>
					</p>
					<p class="paid">
						<span>{t('list.total_label')}: <strong data-testid="rank-total">{formatMoney(row.checkoutTotal)}</strong></span>
						<Badge tone="warning">{tp('list.missing', row.missingCount)}</Badge>
					</p>
				{:else}
					<p class="total">
						{t('list.total_label')}: <strong data-testid="rank-total">{formatMoney(row.checkoutTotal)}</strong>
					</p>
					{#if row.missingCount > 0}
						<p><Badge tone="warning">{tp('list.missing', row.missingCount)}</Badge></p>
					{/if}
				{/if}
				{#if row.assumedCount > 0}
					<p class="small muted">{tp('list.assumed', row.assumedCount)}</p>
				{/if}
				<button
					type="button"
					class="btn"
					class:btn-primary={!chosen}
					class:btn-secondary={chosen}
					aria-pressed={chosen}
					aria-label={t('list.choose_store_named', { store: address ? `${chain}, ${address}` : chain })}
					onclick={() => onchoose(row.storeId)}>{t('list.choose_store')}</button
				>
			</li>
		{/each}
	</ol>
</section>

<style>
	.ranks {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: var(--space-3);
	}

	.rank-card > * {
		margin: 0 0 var(--space-2);
	}

	.rank-card > :last-child {
		margin-bottom: 0;
	}

	.chosen {
		border-color: var(--color-primary);
		border-width: 2px;
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
	}

	.rank {
		font-weight: 700;
		font-size: var(--font-size-lg);
	}

	.chain {
		font-weight: 700;
		font-size: var(--font-size-lg);
	}

	.where {
		color: var(--color-text-muted);
	}

	.distance {
		white-space: nowrap;
	}

	.total strong {
		font-size: var(--font-size-lg);
	}

	.paid {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-2);
	}

	@media (min-width: 48rem) {
		.ranks {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
