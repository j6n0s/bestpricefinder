<!--
	Modal picker for one meal: the recipes eligible for the slot (without the user's excluded tags), with an
	accent-insensitive title search. A native <dialog> opened with showModal(): focus stays inside, Escape
	closes it, and the page behind is inert. The list shows prices, so the source line is repeated here.
	The search field is type="text", not "search": in a search field Chrome uses the first Escape to clear
	the text, and Escape must close the dialog.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import type { ChainSlug, RecipeSummary, Slot } from '$lib/api/types';
	import Attribution from '$lib/components/Attribution.svelte';
	import RecipePrice from '$lib/components/recipes/RecipePrice.svelte';
	import { t, tp } from '$lib/i18n';
	import { eligibleRecipes } from '$lib/plan/recipes';

	interface Props {
		slot: Slot;
		/** "Kedd, 2026. 10. 14., ebéd" */
		target: string;
		recipes: readonly RecipeSummary[];
		currentId: string | null;
		excludedTags: readonly string[];
		hasExcludedIngredients: boolean;
		names: ReadonlyMap<ChainSlug, string>;
		dataDate: string | null;
		onpick: (recipeId: string) => void;
		onclose: () => void;
	}

	let { slot, target, recipes, currentId, excludedTags, hasExcludedIngredients, names, dataDate, onpick, onclose }: Props =
		$props();

	let dialog = $state<HTMLDialogElement>();
	let search = $state<HTMLInputElement>();
	let query = $state('');

	const options = $derived(eligibleRecipes(recipes, slot, excludedTags, query));

	onMount(() => {
		if (dialog && !dialog.open) dialog.showModal();
		search?.focus();
		return () => {
			if (dialog?.open) dialog.close();
		};
	});

	/** Reports the choice first, so it never depends on when the dialog's `close` event fires. */
	function pick(recipeId: string): void {
		onpick(recipeId);
		dialog?.close();
	}
</script>

<dialog bind:this={dialog} class="dialog picker" aria-labelledby="picker-title" aria-describedby="picker-target" onclose={onclose}>
	<div class="head">
		<div>
			<h2 id="picker-title">{t('plan.picker_title')}</h2>
			<p id="picker-target" class="muted">{target}</p>
		</div>
		<button type="button" class="btn btn-secondary" onclick={() => dialog?.close()}>{t('plan.picker_close')}</button>
	</div>

	<div class="field">
		<label for="picker-search">{t('plan.picker_search_label')}</label>
		<input
			id="picker-search"
			class="input"
			type="text"
			maxlength="40"
			enterkeyhint="search"
			autocomplete="off"
			spellcheck="false"
			bind:this={search}
			bind:value={query}
			aria-controls="picker-options"
		/>
	</div>

	{#if excludedTags.length > 0}
		<p class="small muted">{t('plan.picker_excluded_tags')}</p>
	{/if}
	{#if hasExcludedIngredients}
		<p class="small muted">{t('plan.picker_excluded_ingredients')}</p>
	{/if}

	<p class="count small" role="status">{tp('plan.picker_results', options.length)}</p>

	{#if options.length > 0}
		<ul class="options" id="picker-options">
			{#each options as recipe (recipe.id)}
				<li>
					<button
						type="button"
						class="option"
						aria-current={recipe.id === currentId ? 'true' : undefined}
						onclick={() => pick(recipe.id)}
					>
						<span class="title" lang="hu">{recipe.title}</span>
						<span class="meta small">
							{#if recipe.minutes !== null}
								<span>{tp('recipes.minutes', recipe.minutes)}</span>
							{/if}
							{#if recipe.id === currentId}
								<span class="muted">({t('plan.picker_current')})</span>
							{/if}
						</span>
						<span class="small"><RecipePrice {recipe} {names} compact /></span>
					</button>
				</li>
			{/each}
		</ul>
	{:else}
		<p id="picker-options">{t('plan.picker_none')}</p>
	{/if}

	<Attribution {dataDate} chainTypical />
</dialog>

<style>
	.picker {
		width: min(36rem, calc(100vw - 2rem));
		max-height: calc(100dvh - 2rem);
		overflow-y: auto;
		padding: var(--space-4);
		background: var(--color-surface);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
	}

	.picker::backdrop {
		background: rgb(0 0 0 / 0.55);
	}

	.picker > :global(* + *) {
		margin-top: var(--space-3);
	}

	.head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--space-3);
	}

	.head h2 {
		margin-bottom: var(--space-1);
	}

	.head p {
		margin: 0;
	}

	.count {
		margin-bottom: 0;
	}

	.options {
		list-style: none;
		margin-bottom: 0;
		padding: 0;
	}

	.options li + li {
		margin-top: var(--space-2);
	}

	.option {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--space-1);
		width: 100%;
		min-height: var(--tap);
		padding: var(--space-2) var(--space-3);
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		text-align: left;
		cursor: pointer;
	}

	.option:hover {
		background: var(--color-surface-alt);
	}

	.option[aria-current='true'] {
		border-width: 2px;
		border-color: var(--color-primary);
	}

	.title {
		font-weight: 600;
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
	}
</style>
