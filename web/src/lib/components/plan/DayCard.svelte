<!--
	One plan day: every planned slot with its recipe (linked), the recipe's price hint, and buttons to change
	or remove the meal. Whether a recipe is untested is shown on its detail page, not on every meal. The change button keeps its id when the slot is empty ("Választás") or filled
	("Csere"), so focus can return to it after the picker closes.
-->
<script lang="ts">
	import type { ChainSlug, RecipeSummary, Slot } from '$lib/api/types';
	import RecipePrice from '$lib/components/recipes/RecipePrice.svelte';
	import { i18n, t } from '$lib/i18n';
	import { slotLabel, slotLabelLower } from '$lib/plan/checks';
	import { dayLabel } from '$lib/plan/labels';
	import type { PlanDayView } from '$lib/plan/plan';

	interface Props {
		day: PlanDayView;
		recipes: ReadonlyMap<string, RecipeSummary>;
		/** false while the recipe list is not available (titles unknown, not "no longer available"). */
		recipesLoaded: boolean;
		names: ReadonlyMap<ChainSlug, string>;
		onchange: (dayIndex: number, slot: Slot) => void;
		onclear: (dayIndex: number, slot: Slot) => void;
	}

	let { day, recipes, recipesLoaded, names, onchange, onclear }: Props = $props();

	const label = $derived(dayLabel(day, i18n.lang));
	const titleId = $derived(`plan-day-${day.index}`);
</script>

<article class="card day" aria-labelledby={titleId} data-testid="plan-day-{day.index}">
	<h4 id={titleId}>{label}</h4>
	<ul class="meals">
		{#each day.meals as meal (meal.slot)}
			{@const recipe = meal.recipeId === null ? undefined : recipes.get(meal.recipeId)}
			{@const target = t('plan.meal_target', { day: label, slot: slotLabelLower(meal.slot, i18n.lang) })}
			<li class="meal" data-testid="meal-{day.index}-{meal.slot}">
				<span class="slot">{slotLabel(meal.slot, i18n.lang)}</span>
				<div class="body">
					{#if meal.recipeId === null}
						<span class="muted">{t('plan.meal_empty')}</span>
					{:else if recipe}
						<a class="title" href="/receptek/{encodeURIComponent(recipe.id)}" lang="hu">{recipe.title}</a>
						<span class="hint small"><RecipePrice {recipe} {names} compact /></span>
					{:else if recipesLoaded}
						<span class="title">{meal.recipeId}</span>
						<span class="hint small warn">{t('plan.meal_unknown')}</span>
					{:else}
						<a class="title" href="/receptek/{encodeURIComponent(meal.recipeId)}">{meal.recipeId}</a>
					{/if}
				</div>
				<div class="actions">
					<button
						type="button"
						class={meal.recipeId === null ? 'btn btn-secondary' : 'btn btn-ghost'}
						id="meal-change-{day.index}-{meal.slot}"
						onclick={() => onchange(day.index, meal.slot)}
					>
						{meal.recipeId === null ? t('plan.meal_choose') : t('plan.meal_change')}
						<span class="visually-hidden">{target}</span>
					</button>
					{#if meal.recipeId !== null}
						<button type="button" class="btn btn-ghost" onclick={() => onclear(day.index, meal.slot)}>
							{t('plan.meal_clear')}
							<span class="visually-hidden">{target}</span>
						</button>
					{/if}
				</div>
			</li>
		{/each}
	</ul>
</article>

<style>
	h4 {
		font-size: var(--font-size-lg);
		margin: 0 0 var(--space-2);
	}

	.meals {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.meal {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--space-2);
		padding: var(--space-3) 0;
		border-top: 1px solid var(--color-border-subtle);
	}

	.slot {
		font-size: var(--font-size-sm);
		font-weight: 700;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.body {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-2);
		min-width: 0;
	}

	.title {
		font-weight: 600;
	}

	a.title {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}

	.hint {
		flex-basis: 100%;
	}

	.warn {
		color: var(--color-danger);
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
	}

	@media (min-width: 40rem) {
		.meal {
			grid-template-columns: 7rem minmax(0, 1fr) auto;
			align-items: center;
		}
	}
</style>
