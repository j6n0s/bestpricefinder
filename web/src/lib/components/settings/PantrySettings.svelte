<!--
	"Kamra": the pantry staples (GET /api/ingredients, `pantry: true`). Ticked = "otthon van" (the default):
	the staple stays off the shopping list and out of the store prices. Unticking stores it in
	StoredState.pantry.notAtHome (the same switch as "nincs otthon" on the list), on this device only.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import type { IngredientOut } from '$lib/api/types';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t } from '$lib/i18n';
	import { loadIngredients } from '$lib/list/data';
	import { toggleId } from '$lib/list/lines';
	import { pantryIngredients } from '$lib/list/settings';
	import { validIngredients } from '$lib/list/validate';
	import { isPersistent, load, onExternalChange, update, type StoredState } from '$lib/storage';

	let settings = $state<StoredState>(load());
	let persistent = $state(isPersistent());

	type LoadState =
		| { status: 'loading' }
		| { status: 'ready'; items: IngredientOut[] }
		| { status: 'error'; error: unknown };
	let ingredients = $state<LoadState>({ status: 'loading' });

	function fetchIngredients(): void {
		ingredients = { status: 'loading' };
		loadIngredients()
			.then((data) => {
				ingredients = { status: 'ready', items: pantryIngredients(validIngredients(data)) };
			})
			.catch((error: unknown) => {
				ingredients = { status: 'error', error };
			});
	}

	onMount(() => {
		fetchIngredients();
		// Another tab changed or deleted the data: show what is stored now.
		return onExternalChange((next) => {
			settings = next;
			persistent = isPersistent();
		});
	});

	const notAtHome = $derived(new Set(settings.pantry.notAtHome));

	function setAtHome(ingredientId: string, atHome: boolean): void {
		const current = load();
		settings = update({
			pantry: { ...current.pantry, notAtHome: toggleId(current.pantry.notAtHome, ingredientId, !atHome) }
		});
		persistent = isPersistent();
	}
</script>

<div class="pantry-settings" data-testid="pantry-settings">
	<p>{t('list.pantry_settings_intro')}</p>
	<p class="small muted">{t('list.device_only')}</p>
	{#if !persistent}
		<p class="notice notice-warning" role="status">{t('list.storage_unavailable')}</p>
	{/if}

	{#if ingredients.status === 'loading'}
		<Spinner label={t('list.pantry_settings_loading')} showLabel />
	{:else if ingredients.status === 'error'}
		<ErrorState error={ingredients.error} onretry={fetchIngredients} />
	{:else if ingredients.items.length === 0}
		<p class="muted">{t('list.pantry_settings_empty')}</p>
	{:else}
		<fieldset class="choice-group">
			<legend>{t('list.pantry_settings_legend')}</legend>
			<div class="options">
				{#each ingredients.items as ingredient (ingredient.id)}
					<label class="choice">
						<input
							type="checkbox"
							checked={!notAtHome.has(ingredient.id)}
							onchange={(event) => setAtHome(ingredient.id, event.currentTarget.checked)}
						/>
						<span lang="hu">{ingredient.name_hu}</span>
					</label>
				{/each}
			</div>
		</fieldset>
	{/if}
</div>

<style>
	.pantry-settings > :global(* + *) {
		margin-top: var(--space-3);
	}

	.pantry-settings p {
		margin-bottom: 0;
	}

	.options {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 12rem), 1fr));
		gap: 0 var(--space-3);
	}
</style>
