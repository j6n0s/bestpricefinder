<!--
	"Kamra", in two parts, both on this device only (StoredState.pantry):
	1. the pantry staples (GET /api/ingredients, `pantry: true`): ticked = "otthon van" (the default), so the
	   staple stays off the shopping list and out of the store prices; unticking stores it in `notAtHome` (the
	   same switch as "nincs otthon" on the list);
	2. "Otthon lévő mennyiségek": any ingredient with GVH store prices (never tap water) with the amount at home,
	   in its own unit on the cart's ladder of round amounts (− / +; at the smallest step − removes it). The list
	   subtracts these amounts on the device ($lib/list/onhand); they are never sent anywhere.
	The group's label says what a tick does; there is no intro paragraph.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import type { IngredientOut } from '$lib/api/types';
	import { approxPieces, buyableGoods, defaultQty, MAX_CART_QTY } from '$lib/cart/cart';
	import QtyStepper from '$lib/components/cart/QtyStepper.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, tp } from '$lib/i18n';
	import { loadIngredients } from '$lib/list/data';
	import { toggleId } from '$lib/list/lines';
	import { setOnHandQty } from '$lib/list/onhand';
	import { pantryIngredients, searchIngredients } from '$lib/list/settings';
	import { validIngredients } from '$lib/list/validate';
	import { isPersistent, load, MAX_ON_HAND_LINES, onExternalChange, update, type StoredState } from '$lib/storage';

	const id = $props.id();

	let settings = $state<StoredState>(load());
	let persistent = $state(isPersistent());
	let query = $state('');
	let searchInput = $state<HTMLInputElement>();
	let onHandList = $state<HTMLUListElement>();

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

	onMount(() => {
		fetchIngredients();
		// Another tab changed or deleted the data: show what is stored now.
		return onExternalChange((next) => {
			settings = next;
			persistent = isPersistent();
		});
	});

	const items = $derived(ingredients.status === 'ready' ? ingredients.items : []);
	const staples = $derived(pantryIngredients(items));
	/** The goods an amount can be given for: GVH-priced, never tap water. */
	const goods = $derived(buyableGoods(items));
	const goodsById = $derived(new Map(goods.map((good) => [good.id, good])));
	const notAtHome = $derived(new Set(settings.pantry.notAtHome));
	const onHand = $derived(settings.pantry.onHand);
	const onHandIds = $derived(new Set(onHand.map((line) => line.ingredientId)));
	/** Stored amounts whose good the catalogue still prices (the rest stay stored but are not shown). */
	const onHandRows = $derived(
		onHand.flatMap((line) => {
			const good = goodsById.get(line.ingredientId);
			return good ? [{ line, good }] : [];
		})
	);
	const results = $derived(searchIngredients(goods, query, onHandIds));
	const full = $derived(onHand.length >= MAX_ON_HAND_LINES);
	const searching = $derived(query.trim().length >= 2);

	function save(pantry: StoredState['pantry']): void {
		settings = update({ pantry });
		persistent = isPersistent();
	}

	function setAtHome(ingredientId: string, atHome: boolean): void {
		const current = load().pantry;
		save({ ...current, notAtHome: toggleId(current.notAtHome, ingredientId, !atHome) });
	}

	function setQty(ingredientId: string, qty: number | null): void {
		const current = load().pantry;
		save({ ...current, onHand: setOnHandQty(current.onHand, ingredientId, qty, MAX_ON_HAND_LINES, MAX_CART_QTY) });
	}

	async function add(good: IngredientOut): Promise<void> {
		const before = load().pantry.onHand.length;
		setQty(good.id, defaultQty(good));
		if (load().pantry.onHand.length === before) return; // at the limit: the notice says so
		query = '';
		await tick();
		searchInput?.focus();
	}

	/** After the bin removed a row, continue at the row that took its place, else the search field. */
	async function change(ingredientId: string, qty: number | null): Promise<void> {
		const index = onHandRows.findIndex((row) => row.line.ingredientId === ingredientId);
		setQty(ingredientId, qty);
		if (qty !== null) return;
		await tick();
		const rows = onHandList ? [...onHandList.querySelectorAll<HTMLElement>('li')] : [];
		const target = rows[Math.min(Math.max(index, 0), rows.length - 1)]?.querySelector<HTMLElement>('button');
		(target ?? searchInput)?.focus();
	}
</script>

<div class="pantry-settings" data-testid="pantry-settings">
	{#if !persistent}
		<p class="notice notice-warning" role="status">{t('list.storage_unavailable')}</p>
	{/if}

	{#if ingredients.status === 'loading'}
		<Spinner label={t('list.pantry_settings_loading')} showLabel />
	{:else if ingredients.status === 'error'}
		<ErrorState error={ingredients.error} onretry={fetchIngredients} />
	{:else}
		{#if staples.length === 0}
			<p class="muted">{t('list.pantry_settings_empty')}</p>
		{:else}
			<fieldset class="choice-group">
				<legend>{t('list.pantry_settings_legend')}</legend>
				<div class="options">
					{#each staples as ingredient (ingredient.id)}
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

		<section class="on-hand" aria-labelledby="{id}-on-hand" data-testid="on-hand-settings">
			<h3 id="{id}-on-hand">{t('list.on_hand_title')}</h3>
			<p class="small muted">{t('list.on_hand_hint')}</p>
			{#if onHandRows.length === 0}
				<p class="muted">{t('list.on_hand_empty')}</p>
			{:else}
				<ul class="rows" bind:this={onHandList}>
					{#each onHandRows as row (row.line.ingredientId)}
						{@const pieces = approxPieces(row.line.qty, row.good)}
						<li class="row" data-ingredient-id={row.line.ingredientId}>
							<span class="name">
								<span lang="hu">{row.good.name_hu}</span>
								{#if pieces !== null}
									<span class="pieces small muted">{t('cart.pieces', { count: pieces })}</span>
								{/if}
							</span>
							<span class="control">
								<QtyStepper
									name={row.good.name_hu}
									qty={row.line.qty}
									unit={row.good.unit}
									removeKey="list.on_hand_remove_named"
									onchange={(qty) => change(row.line.ingredientId, qty)}
								/>
							</span>
						</li>
					{/each}
				</ul>
			{/if}

			{#if full}
				<p class="notice notice-info">{t('list.on_hand_limit', { max: MAX_ON_HAND_LINES })}</p>
			{:else}
				<div class="field">
					<label for="{id}-search">{t('list.on_hand_search_label')}</label>
					<input
						id="{id}-search"
						class="input"
						type="search"
						autocomplete="off"
						spellcheck="false"
						maxlength={40}
						bind:value={query}
						bind:this={searchInput}
					/>
				</div>
				<p class="visually-hidden" role="status">
					{#if searching}{tp('list.on_hand_results', results.length)}{/if}
				</p>
				{#if searching && results.length === 0}
					<p class="muted">{t('list.on_hand_no_results')}</p>
				{:else if results.length > 0}
					<ul class="results">
						{#each results as good (good.id)}
							<li>
								<span lang="hu">{good.name_hu}</span>
								<button
									type="button"
									class="btn btn-secondary"
									aria-label={t('list.on_hand_add_named', { name: good.name_hu })}
									onclick={() => add(good)}>{t('list.on_hand_add')}</button
								>
							</li>
						{/each}
					</ul>
				{/if}
			{/if}
		</section>
	{/if}
</div>

<style>
	.pantry-settings > :global(* + *) {
		margin-top: var(--space-4);
	}

	.pantry-settings p {
		margin-bottom: 0;
	}

	.options {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 12rem), 1fr));
		gap: 0 var(--space-3);
	}

	h3 {
		font-size: var(--font-size-base);
		margin-bottom: var(--space-1);
	}

	.on-hand > :global(* + *) {
		margin-top: var(--space-3);
	}

	.rows,
	.results {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	/* One framed list, one row per good: the name (with the piece count under it) and the − amount + control. */
	.rows {
		border: 1px solid var(--color-border-subtle);
		border-radius: var(--radius-md);
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2) var(--space-3);
		padding: var(--space-2) var(--space-3);
	}

	/* A name too long for one line keeps its words: the control moves under it, to the right. */
	.control {
		flex: none;
		margin-left: auto;
	}

	.row + .row {
		border-top: 1px solid var(--color-border-subtle);
	}

	.name {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-width: 0;
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	.pieces {
		font-weight: 400;
	}

	.results li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
		padding: var(--space-1) 0;
	}

	.results li + li {
		border-top: 1px solid var(--color-border-subtle);
	}
</style>
