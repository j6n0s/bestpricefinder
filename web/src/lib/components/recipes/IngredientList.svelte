<!--
	A recipe's ingredients with their display quantities, scaled to the chosen servings. Pantry staples get
	the "valószínűleg otthon van" badge; ingredients the user excluded in the settings are marked.
-->
<script lang="ts">
	import type { RecipeLineOut } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import { t } from '$lib/i18n';
	import { scaleDisplay } from '$lib/plan/recipes';

	interface Props {
		lines: readonly RecipeLineOut[];
		/** wanted servings / recipe servings */
		factor: number;
		excluded: readonly string[];
	}

	let { lines, factor, excluded }: Props = $props();

	const sorted = $derived([...lines].sort((a, b) => a.line_no - b.line_no));
</script>

<ul class="ingredients">
	{#each sorted as line (line.line_no)}
		<li data-testid="ingredient-{line.ingredient_id}">
			<span class="qty" data-testid="ingredient-qty" lang="hu">{scaleDisplay(line.display, factor)}</span>
			<span class="name" lang="hu">{line.ingredient_name}</span>
			{#if line.optional}
				<span class="muted small">({t('recipes.optional')})</span>
			{/if}
			{#if line.pantry}
				<Badge kind="pantry" />
			{/if}
			{#if excluded.includes(line.ingredient_id)}
				<Badge tone="warning">{t('recipes.excluded')}</Badge>
			{/if}
		</li>
	{/each}
</ul>

<style>
	.ingredients {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	li {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-1) var(--space-2);
		padding: var(--space-2) 0;
		border-bottom: 1px solid var(--color-border-subtle);
	}

	li:last-child {
		border-bottom: 0;
	}

	.qty {
		font-weight: 600;
	}
</style>
