<!--
	The list for the chosen store, grouped by shop section (docs/DATA.md order): what to pick up, the packs and
	what it costs there. The total is the server's checkout total; KSH estimates are labelled and never added
	to it. Store prices and chain-typical prices are labelled apart (BUILD-BRIEF §8.6; what the two labels mean
	is behind a closed "Hogyan számoljuk?" disclosure), and the GVH source with its data date and the disclaimer
	close the view (§8.1–8.2).
	The shop sections are plain groups under h4 headings, not landmarks: the shopping list above already has a
	named region per section, and two regions with the same name would be indistinguishable.
-->
<script lang="ts">
	import type { ListLineOut, StoreOut, StoreQuoteOut } from '$lib/api/types';
	import Attribution from '$lib/components/Attribution.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import HowCalculated from '$lib/components/HowCalculated.svelte';
	import { formatDistance, formatMoney } from '$lib/format';
	import { t, tp } from '$lib/i18n';
	import { groupLabelKey } from '$lib/list/groups';
	import { hasKshEstimate, storeGroups } from '$lib/list/storeview';
	import { storeAddress } from '$lib/list/stores';
	import StoreLine from './StoreLine.svelte';

	interface Props {
		store: StoreQuoteOut;
		storeInfo: StoreOut | undefined;
		chainName: string;
		distanceKm: number | null;
		listLines: readonly ListLineOut[];
		checked: ReadonlySet<string>;
		ontogglecheck: (ingredientId: string, on: boolean) => void;
		dataDate: string;
		kshPeriod: string | null;
		kshUrl: string | null;
		/** Bound by the parent to move focus here when a store is chosen. */
		heading?: HTMLHeadingElement;
	}

	let {
		store,
		storeInfo,
		chainName,
		distanceKm,
		listLines,
		checked,
		ontogglecheck,
		dataDate,
		kshPeriod,
		kshUrl,
		heading = $bindable()
	}: Props = $props();
	const id = $props.id();

	const groups = $derived(storeGroups(store, listLines));
	const address = $derived(storeAddress(storeInfo));
	const ksh = $derived(hasKshEstimate(store));
</script>

<section class="store-list" aria-labelledby="{id}-title" data-testid="store-list">
	<h3 id="{id}-title" tabindex="-1" bind:this={heading}>{t('list.store_title', { store: chainName })}</h3>
	{#if address || distanceKm !== null}
		<p class="muted">
			{address}{#if distanceKm !== null}{address ? ' · ' : ''}<span class="distance">{formatDistance(distanceKm)}</span>{/if}
		</p>
	{/if}
	<p class="total" data-testid="store-total">{t('list.store_total', { total: formatMoney(store.checkout_total) })}</p>
	{#if store.missing.length > 0}
		<p><Badge tone="warning">{tp('list.missing', store.missing.length)}</Badge></p>
	{/if}
	{#if store.assumed_count > 0}
		<p class="small muted">{tp('list.assumed', store.assumed_count)}</p>
	{/if}
	{#if store.ksh_estimate_total > 0}
		<p class="small" data-testid="ksh-total">{t('list.ksh_total', { total: formatMoney(store.ksh_estimate_total) })}</p>
	{/if}
	<HowCalculated testid="scope-how"><p>{t('list.scope_legend')}</p></HowCalculated>

	{#each groups as group (group.group)}
		<div class="group">
			<h4>{t(groupLabelKey(group.group))}</h4>
			<ul class="lines">
				{#each group.lines as view, index (index)}
					<StoreLine
						line={view.line}
						name={view.name}
						checked={checked.has(view.line.ingredient_id)}
						{ontogglecheck}
					/>
				{/each}
			</ul>
		</div>
	{/each}

	<Attribution {dataDate} {ksh} {kshPeriod} {kshUrl} />
</section>

<style>
	h3:focus {
		outline: none;
	}

	h3:focus-visible {
		outline: var(--focus-ring);
	}

	.store-list {
		border-top: 1px solid var(--color-border-subtle);
		padding-top: var(--space-4);
	}

	.store-list > p {
		margin: 0 0 var(--space-2);
	}

	.total {
		font-size: var(--font-size-lg);
		font-weight: 700;
	}

	.distance {
		white-space: nowrap;
	}

	.group {
		margin-top: var(--space-4);
	}

	h4 {
		font-size: var(--font-size-base);
		margin: 0 0 var(--space-2);
	}

	.lines {
		list-style: none;
		margin: 0;
		padding: 0;
		background: var(--color-surface);
		border: 1px solid var(--color-border-subtle);
		border-radius: var(--radius-lg);
	}

	/* The rows are StoreLine components. */
	.lines > :global(li + li) {
		border-top: 1px solid var(--color-border-subtle);
	}
</style>
