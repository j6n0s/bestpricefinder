<!--
	Kosár: browse the goods that have store prices, put them in a cart with − / + amounts, and see where the
	cart is cheapest nearby: in one store, or on a short route through 2–3 stores with a schematic map
	(NearbyPrices + ShoppingOptions, the same as the plan's shopping list).

	- The goods are GET /api/ingredients with `priced_by: "gvh"` (store prices exist); tap water never.
	- The cart is personal data: it stays on this device (StoredState.cart). Only ingredient ids and amounts
	  are sent to POST /api/quote, with the nearby store ids; never a position.
	- Another tab may change the cart: the page reloads it (onExternalChange), and every change starts from a
	  fresh load(), so a stale tab never writes old data back.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import type { IngredientOut, StoreId } from '$lib/api/types';
	import { MAX_CART_LINES, approxPieces, buyableGoods, buyableLines, cartListLines, cartQuoteInput, defaultQty, searchGoods, setLineQty, type CartLine } from '$lib/cart/cart';
	import QtyStepper from '$lib/components/cart/QtyStepper.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import NearbyPrices from '$lib/components/list/NearbyPrices.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, tp } from '$lib/i18n';
	import { loadIngredients } from '$lib/list/data';
	import { groupLabelKey, groupLines } from '$lib/list/groups';
	import { toggleId } from '$lib/list/lines';
	import { isPersistent, load, onExternalChange, update, type StatePatch, type StoredCart, type StoredLocation, type StoredState } from '$lib/storage';

	let stored = $state<StoredState>(load());
	let persistent = $state(isPersistent());

	type CatalogueState =
		| { status: 'idle' | 'loading' }
		| { status: 'ready'; ingredients: IngredientOut[] }
		| { status: 'error'; error: unknown };
	let catalogue = $state<CatalogueState>({ status: 'idle' });

	function fetchCatalogue(): void {
		catalogue = { status: 'loading' };
		loadIngredients()
			.then((data) => {
				catalogue = Array.isArray(data?.ingredients)
					? { status: 'ready', ingredients: data.ingredients }
					: { status: 'error', error: new ApiError({ kind: 'invalid_response' }) };
			})
			.catch((error: unknown) => {
				catalogue = { status: 'error', error };
			});
	}

	onMount(() => {
		fetchCatalogue();
		return onExternalChange((next) => {
			stored = next;
			persistent = isPersistent();
		});
	});

	const ingredients = $derived(catalogue.status === 'ready' ? catalogue.ingredients : []);
	const byId = $derived(new Map(ingredients.map((ingredient) => [ingredient.id, ingredient])));
	const goods = $derived(buyableGoods(ingredients));
	const cart = $derived(stored.cart);
	const qtyById = $derived(new Map(cart.lines.map((line) => [line.ingredientId, line.qty])));
	const listLines = $derived(catalogue.status === 'ready' ? cartListLines(cart.lines, byId) : []);
	const cartGroups = $derived(groupLines(listLines));
	const dropped = $derived(catalogue.status === 'ready' ? cart.lines.length - listLines.length : 0);
	const quoteInput = $derived(cartQuoteInput(listLines));
	const checked = $derived(new Set(cart.checked));

	let query = $state('');
	const shown = $derived(searchGoods(goods, query));
	const shownGroups = $derived(groupLines(shown));
	// The goods list starts open when the cart is empty; the user opens and closes it after that.
	let browseOpen = $state(load().cart.lines.length === 0);
	let fullNotice = $state(false);
	let undoLines = $state<CartLine[] | null>(null);
	let undoButton = $state<HTMLButtonElement>();
	let searchInput = $state<HTMLInputElement>();
	let cartTitle = $state<HTMLElement>();
	let browseList = $state<HTMLElement>();

	function patch(next: StatePatch): void {
		stored = update(next);
		persistent = isPersistent();
	}

	/** Changes the cart, starting from a fresh load(): another tab may have changed it meanwhile. */
	function changeCart(change: (current: StoredCart) => StoredCart): void {
		patch({ cart: change(load().cart) });
	}

	/**
	 * Keeps the keyboard focus near the good just changed when its controls were swapped ("Kosárba" <-> − amount +)
	 * or its cart line went away: the button pressed no longer exists, and focus would fall back to the page.
	 */
	async function keepFocus(ingredientId: string, from: 'cart' | 'browse'): Promise<void> {
		await tick();
		const active = document.activeElement;
		if (active !== null && active !== document.body) return; // the pressed button is still there
		if (from === 'cart') {
			cartTitle?.focus();
			return;
		}
		const row = browseList?.querySelector(`[data-ingredient-id="${CSS.escape(ingredientId)}"]`);
		const buttons = row?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
		buttons?.[buttons.length - 1]?.focus(); // "+" after adding, "Kosárba" after removing
	}

	function setQty(ingredientId: string, qty: number | null, from: 'cart' | 'browse'): void {
		undoLines = null;
		changeCart((current) => {
			// Goods without store prices any more (the notice says so) leave the cart with this change.
			const lines = setLineQty(buyableLines(current.lines, byId), ingredientId, qty);
			const checkedNow = qty === null ? toggleId(current.checked, ingredientId, false) : current.checked;
			return { ...current, lines, checked: checkedNow };
		});
		void keepFocus(ingredientId, from);
	}

	function add(good: IngredientOut): void {
		const lines = buyableLines(load().cart.lines, byId);
		if (lines.length >= MAX_CART_LINES && !lines.some((line) => line.ingredientId === good.id)) {
			fullNotice = true;
			return;
		}
		fullNotice = false;
		setQty(good.id, defaultQty(good), 'browse');
	}

	async function clearCart(): Promise<void> {
		const current = load().cart;
		undoLines = current.lines;
		patch({ cart: { lines: [], checked: [], storeId: current.storeId } });
		await tick();
		undoButton?.focus();
	}

	function undoClear(): void {
		const lines = undoLines;
		undoLines = null;
		if (lines) changeCart((current) => ({ ...current, lines }));
	}

	function toggleCheck(ingredientId: string, on: boolean): void {
		changeCart((current) => ({ ...current, checked: toggleId(current.checked, ingredientId, on) }));
	}

	function chooseStore(storeId: StoreId): void {
		changeCart((current) => ({ ...current, storeId }));
	}

	function setLocation(next: StoredLocation): void {
		patch({ location: next });
	}

	function setRadius(radiusKm: number): void {
		patch({ radiusKm });
	}

	async function clearSearch(): Promise<void> {
		query = '';
		await tick();
		searchInput?.focus();
	}
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('cart.title') })}</title>
</svelte:head>

<h1>{t('cart.title')}</h1>

{#if !persistent}
	<p class="notice notice-warning" role="status">{t('list.storage_unavailable')}</p>
{/if}

{#if catalogue.status === 'idle' || catalogue.status === 'loading'}
	<Spinner label={t('cart.loading')} showLabel />
{:else if catalogue.status === 'error'}
	<ErrorState error={catalogue.error} title={t('cart.error_title')} onretry={fetchCatalogue} />
{:else}
	<section class="card cart" aria-labelledby="cart-title" data-testid="cart">
		<h2 id="cart-title" tabindex="-1" bind:this={cartTitle}>
			{t('cart.cart_title')}
			<span class="count" data-testid="cart-count">{tp('cart.cart_count', listLines.length)}</span>
		</h2>
		{#if undoLines}
			<div class="notice notice-info undo" role="status">
				<p>{t('cart.cleared')}</p>
				<button type="button" class="btn btn-secondary" bind:this={undoButton} onclick={undoClear}>{t('cart.undo')}</button>
			</div>
		{/if}
		{#if dropped > 0}
			<p class="notice notice-warning" data-testid="cart-dropped">{tp('cart.dropped', dropped)}</p>
		{/if}
		{#if listLines.length === 0}
			<p class="muted">{t('cart.cart_empty')}</p>
		{:else}
			{#each cartGroups as group (group.group)}
				<h3 class="group">{t(groupLabelKey(group.group))}</h3>
				<ul class="rows">
					{#each group.lines as line (line.ingredient_id)}
						{@const ingredient = byId.get(line.ingredient_id)}
						<li class="row" data-testid="cart-line" data-ingredient-id={line.ingredient_id}>
							<span class="name" lang="hu">{line.name_hu}</span>
							<span class="controls">
								<QtyStepper
									name={line.name_hu}
									qty={line.qty}
									unit={line.unit}
									pieces={ingredient ? approxPieces(line.qty, ingredient) : null}
									onchange={(qty) => setQty(line.ingredient_id, qty, 'cart')}
								/>
								<button
									type="button"
									class="btn btn-ghost remove"
									aria-label={t('cart.remove_named', { name: line.name_hu })}
									onclick={() => setQty(line.ingredient_id, null, 'cart')}
								>
									<span aria-hidden="true">×</span>
								</button>
							</span>
						</li>
					{/each}
				</ul>
			{/each}
			<div class="btn-row">
				<a class="btn btn-primary" href="#hol-a-legolcsobb">{t('cart.to_prices')}</a>
				<button type="button" class="btn btn-secondary" onclick={clearCart}>{t('cart.clear')}</button>
			</div>
		{/if}
	</section>

	<details class="card browse" bind:open={browseOpen} data-testid="browse">
		<summary class="disclosure">
			<h2>{listLines.length === 0 ? t('cart.browse_title') : t('cart.browse_more')}</h2>
		</summary>
		<div class="field">
			<label for="goods-search">{t('cart.search_label')}</label>
			<input
				id="goods-search"
				class="input"
				type="search"
				autocomplete="off"
				maxlength="40"
				bind:value={query}
				bind:this={searchInput}
			/>
		</div>
		<p class="small" role="status" data-testid="goods-count">{tp('cart.goods_count', shown.length)}</p>
		{#if fullNotice}
			<p class="notice notice-warning" role="status">{t('cart.full', { max: MAX_CART_LINES })}</p>
		{/if}
		{#if shown.length === 0}
			<div class="notice notice-info">
				<p>{t('cart.no_results')}</p>
				<button type="button" class="btn btn-secondary" onclick={clearSearch}>{t('cart.clear_search')}</button>
			</div>
		{:else}
			<div bind:this={browseList}>
				{#each shownGroups as group (group.group)}
					<h3 class="group">{t(groupLabelKey(group.group))}</h3>
					<ul class="rows">
						{#each group.lines as good (good.id)}
							{@const qty = qtyById.get(good.id)}
							<li class="row" class:in-cart={qty !== undefined} data-testid="good" data-ingredient-id={good.id}>
								<span class="name" lang="hu">{good.name_hu}</span>
								<span class="controls">
									{#if qty !== undefined}
										<QtyStepper
											name={good.name_hu}
											{qty}
											unit={good.unit}
											pieces={approxPieces(qty, good)}
											onchange={(next) => setQty(good.id, next, 'browse')}
										/>
									{:else}
										<button
											type="button"
											class="btn btn-secondary add"
											aria-label={t('cart.add_named', { name: good.name_hu })}
											onclick={() => add(good)}>{t('cart.add')}</button
										>
									{/if}
								</span>
							</li>
						{/each}
					</ul>
				{/each}
			</div>
		{/if}
	</details>

	{#if listLines.length > 0}
		<div id="hol-a-legolcsobb" class="nearby-anchor" tabindex="-1">
			<NearbyPrices
				{listLines}
				{quoteInput}
				skipped={[]}
				location={stored.location}
				radiusKm={stored.radiusKm}
				chosenStoreId={cart.storeId}
				{checked}
				onlocation={setLocation}
				onradius={setRadius}
				onchoosestore={chooseStore}
				ontogglecheck={toggleCheck}
			/>
		</div>
	{/if}
{/if}

<style>
	.cart,
	.browse {
		margin-top: var(--space-4);
	}

	h2 {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2);
	}

	.count {
		font-size: var(--font-size-base);
		font-weight: 400;
		color: var(--color-text-muted);
	}

	.group {
		font-size: var(--font-size-base);
		margin: var(--space-4) 0 var(--space-2);
	}

	/* Each section's goods in one framed list, one row per good, divided by lines. */
	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
		border: 1px solid var(--color-border-subtle);
		border-radius: var(--radius-md);
	}

	.row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2) var(--space-3);
		padding: var(--space-2) var(--space-3);
	}

	.row + .row {
		border-top: 1px solid var(--color-border-subtle);
	}

	/* Bold: the goods in the cart (in the cart and, in the goods list, the ones already added). */
	.cart .name,
	.row.in-cart .name {
		font-weight: 600;
	}

	.name {
		flex: 1 1 auto;
		min-width: 0;
	}

	.controls {
		display: inline-flex;
		flex: none;
		align-items: center;
		justify-content: center;
		gap: var(--space-2);
	}

	/* Phones: the name on its own line, the controls centred under it. */
	@media (max-width: 30rem) {
		.row {
			flex-direction: column;
			align-items: stretch;
			gap: var(--space-1);
			text-align: center;
		}

		.controls {
			align-self: center;
		}
	}

	.remove {
		min-width: var(--tap);
		padding: 0;
		font-size: var(--font-size-lg);
	}

	.undo {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2) var(--space-3);
	}

	.undo p {
		margin: 0;
	}

	.btn-row {
		margin-top: var(--space-4);
	}

	summary {
		cursor: pointer;
		min-height: var(--tap);
		display: flex;
		align-items: center;
	}

	summary h2 {
		display: inline;
		margin: 0;
	}

	.field {
		margin-top: var(--space-3);
	}

	.nearby-anchor:focus {
		outline: none;
	}
</style>
