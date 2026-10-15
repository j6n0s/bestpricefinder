<!--
	A recipe's chain-typical price per serving: "313 Ft/adag-tól (Aldi, Lidl)". Every chain of a tie is
	named, in the server's order (never one chain singled out); "nincs ár" when the recipe cannot be priced.
	When the price covers less than the whole recipe (priced_share < 1) the caveat is ALWAYS shown (contract
	v1.2): in full ("az ár a hozzávalók 94 %-át fedi le") or, with `compact`, short ("részleges ár (94 %)").
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
		/** Short coverage caveat on the same line (plan cards, the meal picker). */
		compact?: boolean;
	}

	let { recipe, names, compact = false }: Props = $props();

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
	{#if percent < 100}
		{#if compact}
			<span class="coverage-short" data-testid="recipe-coverage">{t('recipes.coverage_short', { percent })}</span>
		{:else}
			<span class="coverage small muted" data-testid="recipe-coverage">{t('recipes.coverage', { percent })}</span>
		{/if}
	{/if}
{/if}

<style>
	.price {
		font-weight: 600;
	}

	.coverage {
		display: block;
	}
	/* .coverage-short wraps like any text (the number and its % sign share a no-break space), so it fits
	   a 320 px screen with 200 % text too. */
</style>
