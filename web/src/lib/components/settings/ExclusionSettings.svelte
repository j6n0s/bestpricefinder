<!--
	"Kizárt alapanyagok és címkék": recipe tags and ingredients left out of the plan suggestions. Diet
	preferences can be health data (GDPR Art. 9, BUILD-BRIEF §8.9): they are stored only on this device
	(StoredState.exclusions) and sent only with POST /api/plan/suggest, which uses them for that computation and
	never stores them. Limits: 20 tags and 50 ingredients (the API's limits).
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { LIMITS, type IngredientOut, type RecipeTag } from '$lib/api/types';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, tp } from '$lib/i18n';
	import { loadIngredients } from '$lib/list/data';
	import { toggleId } from '$lib/list/lines';
	import { EXCLUDABLE_TAGS, excludableTagKey, otherExcludedTags, searchIngredients } from '$lib/list/settings';
	import { validIngredients } from '$lib/list/validate';
	import { isPersistent, load, update, type StoredState } from '$lib/storage';

	const id = $props.id();

	let settings = $state<StoredState>(load());
	let persistent = $state(isPersistent());
	let query = $state('');
	let searchInput = $state<HTMLInputElement>();
	let excludedList = $state<HTMLUListElement>();

	type LoadState =
		| { status: 'loading' }
		| { status: 'ready'; items: IngredientOut[] }
		| { status: 'error'; error: unknown };
	let ingredients = $state<LoadState>({ status: 'loading' });

	function fetchIngredients(): void {
		ingredients = { status: 'loading' };
		loadIngredients()
			.then((data) => {
				ingredients = { status: 'ready', items: validIngredients(data) };
			})
			.catch((error: unknown) => {
				ingredients = { status: 'error', error };
			});
	}

	onMount(fetchIngredients);

	const tags = $derived(new Set<string>(settings.exclusions.tags));
	const otherTags = $derived(otherExcludedTags(settings.exclusions.tags));
	const excludedIds = $derived(settings.exclusions.ingredients);
	const excludedSet = $derived(new Set(excludedIds));
	const items = $derived(ingredients.status === 'ready' ? ingredients.items : []);
	const names = $derived(new Map(items.map((ingredient) => [ingredient.id, ingredient.name_hu])));
	const results = $derived(searchIngredients(items, query, excludedSet));
	const full = $derived(excludedIds.length >= LIMITS.excludeIngredientsMax);
	const searching = $derived(query.trim().length >= 2);

	function save(exclusions: StoredState['exclusions']): void {
		settings = update({ exclusions });
		persistent = isPersistent();
	}

	function setTag(tag: RecipeTag, on: boolean): void {
		const current = load().exclusions;
		const next = toggleId(current.tags, tag, on) as RecipeTag[];
		if (next.length > LIMITS.excludeTagsMax) return;
		save({ ...current, tags: next });
	}

	async function exclude(ingredientId: string): Promise<void> {
		const current = load().exclusions;
		if (current.ingredients.length >= LIMITS.excludeIngredientsMax) return;
		save({ ...current, ingredients: toggleId(current.ingredients, ingredientId, true) });
		await tick();
		searchInput?.focus();
	}

	async function include(ingredientId: string): Promise<void> {
		const before = excludedIds.indexOf(ingredientId);
		const current = load().exclusions;
		save({ ...current, ingredients: toggleId(current.ingredients, ingredientId, false) });
		await tick();
		const buttons = excludedList ? [...excludedList.querySelectorAll<HTMLButtonElement>('button')] : [];
		(buttons[Math.min(Math.max(before, 0), buttons.length - 1)] ?? searchInput)?.focus();
	}

	function nameOf(ingredientId: string): string {
		return names.get(ingredientId) ?? t('list.exclude_unknown', { id: ingredientId });
	}
</script>

<div class="exclusions" data-testid="exclusion-settings">
	<p>{t('list.exclusions_intro')}</p>
	{#if !persistent}
		<p class="notice notice-warning" role="status">{t('list.storage_unavailable')}</p>
	{/if}

	<fieldset class="choice-group">
		<legend>{t('list.exclude_tags_legend')}</legend>
		<div class="options">
			{#each EXCLUDABLE_TAGS as tag (tag)}
				<label class="choice">
					<input type="checkbox" checked={tags.has(tag)} onchange={(event) => setTag(tag, event.currentTarget.checked)} />
					<span>{t(excludableTagKey(tag))}</span>
				</label>
			{/each}
			{#each otherTags as tag (tag)}
				<label class="choice">
					<input type="checkbox" checked onchange={(event) => setTag(tag, event.currentTarget.checked)} />
					<span>{tag}</span>
				</label>
			{/each}
		</div>
	</fieldset>

	<section aria-labelledby="{id}-ingredients">
		<h3 id="{id}-ingredients">{t('list.exclude_ingredients_title')}</h3>
		{#if excludedIds.length === 0}
			<p class="muted">{t('list.excluded_none')}</p>
		{:else}
			<ul class="excluded" bind:this={excludedList}>
				{#each excludedIds as ingredientId (ingredientId)}
					<li>
						<span>{nameOf(ingredientId)}</span>
						<button
							type="button"
							class="btn btn-secondary"
							aria-label={t('list.exclude_remove_named', { name: nameOf(ingredientId) })}
							onclick={() => include(ingredientId)}>{t('list.exclude_remove')}</button
						>
					</li>
				{/each}
			</ul>
		{/if}

		{#if ingredients.status === 'loading'}
			<Spinner label={t('list.pantry_settings_loading')} showLabel />
		{:else if ingredients.status === 'error'}
			<ErrorState error={ingredients.error} onretry={fetchIngredients} />
		{:else if full}
			<p class="notice notice-info">{t('list.exclude_limit', { max: LIMITS.excludeIngredientsMax })}</p>
		{:else}
			<div class="field">
				<label for="{id}-search">{t('list.exclude_search_label')}</label>
				<input
					id="{id}-search"
					class="input"
					type="search"
					autocomplete="off"
					spellcheck="false"
					maxlength={40}
					aria-describedby="{id}-hint"
					bind:value={query}
					bind:this={searchInput}
				/>
				<p id="{id}-hint" class="small muted">{t('list.exclude_search_hint')}</p>
			</div>
			<p class="visually-hidden" role="status">
				{#if searching}{tp('list.exclude_results', results.length)}{/if}
			</p>
			{#if searching && results.length === 0}
				<p class="muted">{t('list.exclude_no_results')}</p>
			{:else if results.length > 0}
				<ul class="results">
					{#each results as ingredient (ingredient.id)}
						<li>
							<span>{ingredient.name_hu}</span>
							<button
								type="button"
								class="btn btn-secondary"
								aria-label={t('list.exclude_add_named', { name: ingredient.name_hu })}
								onclick={() => exclude(ingredient.id)}>{t('list.exclude_add')}</button
							>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</section>
</div>

<style>
	.exclusions > :global(* + *) {
		margin-top: var(--space-4);
	}

	.exclusions p {
		margin-bottom: 0;
	}

	.options {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 12rem), 1fr));
		gap: 0 var(--space-3);
	}

	h3 {
		font-size: var(--font-size-base);
	}

	.excluded,
	.results {
		list-style: none;
		margin: 0 0 var(--space-3);
		padding: 0;
	}

	.excluded li,
	.results li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
		padding: var(--space-1) 0;
	}

	.excluded li + li,
	.results li + li {
		border-top: 1px solid var(--color-border-subtle);
	}
</style>
