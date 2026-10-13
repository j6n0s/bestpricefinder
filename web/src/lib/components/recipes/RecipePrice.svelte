<!--
	A recipe's chain-typical price per serving: "≈ 313 Ft/adag-tól (Aldi, Lidl)". Every chain of a tie is
	named, in the server's order (never one chain singled out); "nincs ár" when the recipe cannot be priced.
	The view that shows this must also render <Attribution dataDate=… /> (BUILD-BRIEF §8.2).
-->
<script lang="ts">
	import type { ChainSlug, RecipeSummary } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import { formatMoney } from '$lib/format';
	import { t } from '$lib/i18n';
	import { chainList, coveragePercent } from '$lib/plan/recipes';

	interface Props {
		recipe: Pick<RecipeSummary, 'cost_per_serving_from' | 'cheapest_chains' | 'priced_share'>;
		names: ReadonlyMap<ChainSlug, string>;
		/** Also say how much of the ingredients the price covers when it is below 100 %. */
		showCoverage?: boolean;
	}

	let { recipe, names, showCoverage = true }: Props = $props();

	const cost = $derived(recipe.cost_per_serving_from);
	const chains = $derived(chainList(recipe.cheapest_chains, names));
	const percent = $derived(coveragePercent(recipe.priced_share));
</script>

{#if cost === null || !Number.isFinite(cost)}
	<Badge kind="no_price" />
{:else}
	<span class="price" data-testid="recipe-price">
		{chains
			? t('recipes.price_from', { price: formatMoney(cost), chains })
			: t('recipes.price_from_plain', { price: formatMoney(cost) })}
	</span>
	{#if showCoverage && percent < 100}
		<span class="coverage small muted">{t('recipes.coverage', { percent })}</span>
	{/if}
{/if}

<style>
	.price {
		font-weight: 600;
	}

	.coverage {
		display: block;
	}
</style>
