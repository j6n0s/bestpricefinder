<!--
	Recipe list ("Receptek"): GET /api/recipes once, then filtered on the device by slot, tag and an
	accent-insensitive title search (the same folding as the API's `q`). Prices are chain-typical estimates,
	so the page carries the GVH source line with the data date (BUILD-BRIEF §8.2). No intro or method note:
	the title, the filters and the cards speak for themselves; "kipróbálatlan recept" is on the detail page.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { getRecipes } from '$lib/api/client';
	import { RECIPE_TAGS, SLOTS, type RecipesResponse } from '$lib/api/types';
	import Attribution from '$lib/components/Attribution.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import RecipeCard from '$lib/components/recipes/RecipeCard.svelte';
	import { i18n, t, tp } from '$lib/i18n';
	import { getMeta } from '$lib/meta.svelte';
	import { slotLabel } from '$lib/plan/checks';
	import { recipeFilters, resetRecipeFilters } from '$lib/plan/filters.svelte';
	import { chainNameMap, filterRecipes, tagLabelKey } from '$lib/plan/recipes';

	const meta = getMeta();

	let response = $state<RecipesResponse | null>(null);
	let error = $state<unknown>(null);
	let loading = $state(true);

	const names = $derived(chainNameMap(meta.data?.chains));
	const recipes = $derived(response?.recipes ?? []);
	const filtered = $derived(
		filterRecipes(recipes, {
			slot: recipeFilters.slot || null,
			tag: recipeFilters.tag || null,
			q: recipeFilters.q
		})
	);
	/** Tags that occur in the library (vocabulary order), plus the selected one. */
	const tagOptions = $derived(
		RECIPE_TAGS.flatMap((tag) => {
			const key = tagLabelKey(tag);
			return key && (tag === recipeFilters.tag || recipes.some((r) => r.tags.includes(tag))) ? [{ tag, key }] : [];
		})
	);
	const active = $derived(recipeFilters.slot !== '' || recipeFilters.tag !== '' || recipeFilters.q.trim() !== '');

	async function loadRecipes(): Promise<void> {
		loading = true;
		error = null;
		try {
			response = await getRecipes();
		} catch (caught) {
			error = caught;
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		void loadRecipes();
	});

	/** "Szűrők törlése" removes itself: continue at the search field, never at <body>. */
	async function resetFilters(): Promise<void> {
		resetRecipeFilters();
		await tick();
		document.getElementById('filter-q')?.focus();
	}
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('recipes.title') })}</title>
</svelte:head>

<h1>{t('recipes.title')}</h1>

<form class="filters card" role="search" aria-labelledby="filters-title" onsubmit={(event) => event.preventDefault()}>
	<h2 id="filters-title" class="visually-hidden">{t('recipes.filters_title')}</h2>
	<div class="grid">
		<div class="field">
			<label for="filter-slot">{t('recipes.filter_slot_label')}</label>
			<select id="filter-slot" class="select" bind:value={recipeFilters.slot}>
				<option value="">{t('recipes.filter_all')}</option>
				{#each SLOTS as slot (slot)}
					<option value={slot}>{slotLabel(slot, i18n.lang)}</option>
				{/each}
			</select>
		</div>
		<div class="field">
			<label for="filter-tag">{t('recipes.filter_tag_label')}</label>
			<select id="filter-tag" class="select" bind:value={recipeFilters.tag}>
				<option value="">{t('recipes.filter_all')}</option>
				{#each tagOptions as option (option.tag)}
					<option value={option.tag}>{t(option.key)}</option>
				{/each}
			</select>
		</div>
		<div class="field search">
			<label for="filter-q">{t('recipes.search_label')}</label>
			<input
				id="filter-q"
				class="input"
				type="search"
				maxlength="40"
				autocomplete="off"
				spellcheck="false"
				bind:value={recipeFilters.q}
			/>
		</div>
	</div>
	{#if active}
		<button type="button" class="btn btn-secondary" onclick={resetFilters}>{t('recipes.filters_reset')}</button>
	{/if}
</form>

{#if loading}
	<Spinner showLabel />
{:else if error}
	<ErrorState {error} title={t('recipes.error_title')} onretry={loadRecipes} />
{:else if response}
	<p class="count" role="status" data-testid="recipe-count">{tp('recipes.results', filtered.length)}</p>
	{#if filtered.length === 0}
		<EmptyState title={t('recipes.no_results')}>
			{#if active}
				<button type="button" class="btn btn-secondary" onclick={resetFilters}>{t('recipes.filters_reset')}</button>
			{/if}
		</EmptyState>
	{:else}
		<ul class="list">
			{#each filtered as recipe (recipe.id)}
				<li><RecipeCard {recipe} {names} /></li>
			{/each}
		</ul>
	{/if}
	<Attribution dataDate={response.data_date} chainTypical />
{/if}

<style>
	.filters {
		margin-bottom: var(--space-4);
	}

	.filters > :global(* + *) {
		margin-top: var(--space-3);
	}

	.grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--space-3);
	}

	@media (min-width: 40rem) {
		.grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.search {
			grid-column: 1 / -1;
		}
	}

	.count {
		font-weight: 600;
	}

	.list {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.list li + li {
		margin-top: var(--space-3);
	}
</style>
