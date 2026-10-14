<!--
	A recipe in the list: title (link to the detail page), time, the "kipróbálatlan recept" badge for
	tested=false, tags, summary, and the chain-typical price per serving ("≈ 313 Ft/adag-tól (Aldi, Lidl)").
	The page renders the source line (<Attribution>) once for all cards.
-->
<script lang="ts">
	import type { ChainSlug, RecipeSummary } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import { tp } from '$lib/i18n';
	import RecipePrice from './RecipePrice.svelte';
	import TagList from './TagList.svelte';

	interface Props {
		recipe: RecipeSummary;
		names: ReadonlyMap<ChainSlug, string>;
		/** false when the page says once that every recipe shown is untested. */
		showUntested?: boolean;
	}

	let { recipe, names, showUntested = true }: Props = $props();
</script>

<article class="card recipe" aria-labelledby="recipe-{recipe.id}" data-testid="recipe-card">
	<h2 id="recipe-{recipe.id}"><a href="/receptek/{encodeURIComponent(recipe.id)}" lang="hu">{recipe.title}</a></h2>
	<p class="meta small">
		{#if recipe.minutes !== null}
			<span>{tp('recipes.minutes', recipe.minutes)}</span>
		{/if}
		<span>{tp('recipes.servings', recipe.servings)}</span>
		{#if showUntested && !recipe.tested}
			<Badge kind="untested" />
		{/if}
	</p>
	{#if recipe.summary}
		<p class="summary" lang="hu">{recipe.summary}</p>
	{/if}
	<TagList tags={recipe.tags} />
	<p class="price-line">
		<RecipePrice {recipe} {names} />
	</p>
</article>

<style>
	.recipe > :global(* + *) {
		margin-top: var(--space-2);
	}

	h2 {
		font-size: var(--font-size-lg);
		margin: 0;
	}

	h2 a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
		margin: 0;
		color: var(--color-text-muted);
	}

	.summary {
		margin: 0;
	}

	.price-line {
		margin: 0;
	}
</style>
