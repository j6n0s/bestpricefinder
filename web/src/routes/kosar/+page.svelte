<!--
	Kosár: browse the goods that have store prices, put them in a cart with − / + amounts, and see where the
	cart is cheapest nearby: in one store, or on a short route through 2–3 stores with a schematic map
	(NearbyPrices + ShoppingOptions, the same as the plan's shopping list).

	- The goods are GET /api/ingredients with `priced_by: "gvh"` (store prices exist); tap water never. They are
	  browsed like a shop's menu: a bar of shop sections and, under a section, its kinds of goods ($lib/cart/
	  categories, from the ingredient tags); or searched by name across every section.
	- The cart is personal data: it stays on this device (StoredState.cart). Only ingredient ids and amounts
	  are sent to POST /api/quote, with the nearby store ids; never a position. Goods that lost their store
	  price are written out of the cart when the catalogue arrives (with a notice), so the header's count agrees.
	- Another tab may change the cart: the page reloads it (onExternalChange), and every change starts from a
	  fresh load(), so a stale tab never writes old data back.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import type { IngredientOut, StoreId } from '$lib/api/types';
	import { MAX_CART_LINES, approxPieces, buyableGoods, buyableLines, cartListLines, cartQuoteInput, defaultQty, searchGoods, setLineQty, type CartLine } from '$lib/cart/cart';
	import { categoriesOf, selectGoods, subcategoryLabelKey, type Selection } from '$lib/cart/categories';
	import QtyStepper from '$lib/components/cart/QtyStepper.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import NearbyPrices from '$lib/components/list/NearbyPrices.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, tp } from '$lib/i18n';
	import { loadIngredients } from '$lib/list/data';
	import { groupLabelKey, groupLines, type ListGroup } from '$lib/list/groups';
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
	/**
	 * Goods without store prices any more leave the stored cart as soon as the catalogue says so (not only at
	 * the next change), so the header's count and this page's agree; the notice stays until the next change.
	 */
	let dropped = $state(0);
	$effect(() => {
		if (catalogue.status !== 'ready') return;
		const current = load().cart;
		const kept = buyableLines(current.lines, byId);
		if (kept.length === current.lines.length) return;
		dropped = current.lines.length - kept.length;
		patch({ cart: { ...current, lines: kept } });
	});
	const quoteInput = $derived(cartQuoteInput(listLines));
	const checked = $derived(new Set(cart.checked));

	let query = $state('');
	/** The section (and kind of goods) chosen on the bar; a search looks through every section instead. */
	let selected = $state<Selection | null>(null);
	let openMenu = $state<ListGroup | null>(null);
	const categories = $derived(categoriesOf(goods));
	const openCategory = $derived(categories.find((category) => category.group === openMenu) ?? null);
	const searching = $derived(query.trim() !== '');
	const shown = $derived(searching ? searchGoods(goods, query) : selected ? selectGoods(goods, selected) : goods);
	const shownGroups = $derived(groupLines(shown));
	const chosenLabel = $derived.by(() => {
		if (!selected) return '';
		const group = t(groupLabelKey(selected.group));
		return selected.sub === null ? group : t('cart.category_heading', { group, sub: t(subcategoryLabelKey(selected.sub)) });
	});
	// The goods list starts open when the cart is empty; the user opens and closes it after that.
	let browseOpen = $state(load().cart.lines.length === 0);
	let fullNotice = $state(false);
	let undoLines = $state<CartLine[] | null>(null);
	let undoButton = $state<HTMLButtonElement>();
	let searchInput = $state<HTMLInputElement>();
	let cartTitle = $state<HTMLElement>();
	let browseList = $state<HTMLElement>();
	let categoriesNav = $state<HTMLElement>();
	let categoryButtons = $state<Record<string, HTMLButtonElement | undefined>>({});
	let chosenHeading = $state<HTMLHeadingElement>();

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
		dropped = 0;
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

	/** Typing a search looks through every section: the chosen category no longer applies. */
	function searchTyped(event: Event & { currentTarget: HTMLInputElement }): void {
		if (event.currentTarget.value.trim() !== '') {
			selected = null;
			openMenu = null;
		}
	}

	function toggleMenu(group: ListGroup): void {
		openMenu = openMenu === group ? null : group;
	}

	function closeMenu(refocus: boolean): void {
		const group = openMenu;
		openMenu = null;
		if (refocus && group !== null) categoryButtons[group]?.focus();
	}

	/** Chooses a section (sub: null) or one kind of its goods; the search is dropped, focus goes to the heading. */
	async function choose(group: ListGroup, sub: Selection['sub']): Promise<void> {
		selected = { group, sub };
		openMenu = null;
		query = '';
		await tick();
		chosenHeading?.focus();
	}

	/** Back to every section; focus continues at the bar's button of the section just left. */
	async function showAll(): Promise<void> {
		const group = selected?.group ?? null;
		selected = null;
		await tick();
		if (group !== null) categoryButtons[group]?.focus();
	}

	/** Escape closes the open menu, wherever focus is, and returns to the menu's button. */
	function documentKeys(event: KeyboardEvent): void {
		if (event.key === 'Escape' && openMenu !== null) {
			event.preventDefault();
			closeMenu(true);
		}
	}

	/** A click outside the categories closes the open menu (on wide screens it lies over the goods). */
	function documentClick(event: MouseEvent): void {
		if (openMenu !== null && categoriesNav && !categoriesNav.contains(event.target as Node)) closeMenu(false);
	}
</script>

<svelte:document onclick={documentClick} onkeydown={documentKeys} />

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
						{@const pieces = ingredient ? approxPieces(line.qty, ingredient) : null}
						<li class="row" data-testid="cart-line" data-ingredient-id={line.ingredient_id}>
							<span class="name">
								<span lang="hu">{line.name_hu}</span>
								{#if pieces !== null}
									<span class="pieces small muted">{t('cart.pieces', { count: pieces })}</span>
								{/if}
							</span>
							<span class="control">
								<QtyStepper
									name={line.name_hu}
									qty={line.qty}
									unit={line.unit}
									onchange={(qty) => setQty(line.ingredient_id, qty, 'cart')}
								/>
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
		<!-- The shop's menu: a bar of sections; a section with several kinds of goods opens a list of them. -->
		<nav class="categories" aria-label={t('cart.categories_label')} bind:this={categoriesNav} data-testid="categories">
			<ul class="bar">
				{#each categories as category (category.group)}
					{@const active = !searching && selected?.group === category.group}
					<li class:active>
						{#if category.subcategories.length > 1}
							<button
								type="button"
								class="cat"
								aria-expanded={openMenu === category.group}
								onclick={() => toggleMenu(category.group)}
								bind:this={categoryButtons[category.group]}
							>
								{t(groupLabelKey(category.group))}<span class="caret" aria-hidden="true"></span>
							</button>
						{:else}
							<button
								type="button"
								class="cat"
								aria-pressed={active}
								onclick={() => choose(category.group, null)}
								bind:this={categoryButtons[category.group]}
							>
								{t(groupLabelKey(category.group))}
							</button>
						{/if}
					</li>
				{/each}
			</ul>
			{#if openCategory}
				{@const group = openCategory.group}
				<div class="menu" data-testid="category-menu">
					<ul>
						<li>
							<button
								type="button"
								class="sub"
								aria-current={selected?.group === group && selected.sub === null ? 'true' : undefined}
								onclick={() => choose(group, null)}
							>
								<span>{t('cart.category_all')}</span>
								<span class="chevron" aria-hidden="true"></span>
							</button>
						</li>
						{#each openCategory.subcategories as entry (entry.id)}
							<li>
								<button
									type="button"
									class="sub"
									aria-current={selected?.group === group && selected.sub === entry.id ? 'true' : undefined}
									onclick={() => choose(group, entry.id)}
								>
									<span>{t(subcategoryLabelKey(entry.id))} <span class="small muted">({tp('cart.goods_count', entry.count)})</span></span>
									<span class="chevron" aria-hidden="true"></span>
								</button>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</nav>
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
				oninput={searchTyped}
			/>
		</div>
		<p class="small" role="status" data-testid="goods-count">{tp('cart.goods_count', shown.length)}</p>
		{#if selected && !searching}
			<div class="chosen">
				<h3 class="group" tabindex="-1" bind:this={chosenHeading} data-testid="chosen-category">{chosenLabel}</h3>
				<button type="button" class="btn btn-ghost" onclick={showAll}>{t('cart.all_goods')}</button>
			</div>
		{/if}
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
					{#if !selected || searching}
						<h3 class="group">{t(groupLabelKey(group.group))}</h3>
					{/if}
					<ul class="rows">
						{#each group.lines as good (good.id)}
							{@const qty = qtyById.get(good.id)}
							{@const pieces = qty !== undefined ? approxPieces(qty, good) : null}
							<li class="row" class:in-cart={qty !== undefined} data-testid="good" data-ingredient-id={good.id}>
								<span class="name">
									<span lang="hu">{good.name_hu}</span>
									{#if pieces !== null}
										<span class="pieces small muted">{t('cart.pieces', { count: pieces })}</span>
									{/if}
								</span>
								<span class="control">
									{#if qty !== undefined}
										<QtyStepper
											name={good.name_hu}
											{qty}
											unit={good.unit}
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

	/* Tight sides: at 360 px a name of about 14 letters still shares its line with the 154 px control. */
	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
		padding: var(--space-2);
	}

	/* A name too long for one line keeps its words: the control moves under it, to the right. */
	.control {
		flex: none;
		margin-left: auto;
	}

	.row + .row {
		border-top: 1px solid var(--color-border-subtle);
	}

	/* Bold: the goods in the cart (in the cart and, in the goods list, the ones already added). */
	.cart .name,
	.row.in-cart .name {
		font-weight: 600;
	}

	/* The name, with the piece count under it; the − amount + control (or "Kosárba") on the right. */
	.name {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.pieces {
		font-weight: 400;
	}

	/* "Kosárba" is as wide and as round as the − amount + control it turns into. */
	.add {
		flex: none;
		min-width: calc(2 * var(--tap) + 4rem + 2px);
		border-radius: 999px;
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

	/* The shop's menu: the sections in one bar (wrapping on narrow screens), the chosen one underlined. */
	.categories {
		position: relative;
		margin-top: var(--space-3);
	}

	.bar {
		display: flex;
		flex-wrap: wrap;
		list-style: none;
		margin: 0;
		padding: 0 var(--space-1);
		background: var(--color-primary);
		color: var(--color-on-primary);
		border-radius: var(--radius-md);
	}

	.bar li {
		display: flex;
		align-items: stretch;
	}

	.cat {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		min-height: var(--tap);
		padding: var(--space-2) var(--space-3);
		border: 0;
		border-radius: var(--radius-sm);
		background: transparent;
		color: inherit;
		font: inherit;
		font-weight: 600;
		line-height: 1.25;
		text-align: left;
		cursor: pointer;
	}

	.cat:focus-visible {
		outline: 3px solid currentColor;
		outline-offset: -5px;
	}

	.bar .active .cat {
		box-shadow: inset 0 -3px 0 currentColor;
	}

	@media (hover: hover) {
		.cat:hover {
			background: var(--color-primary-hover);
		}
	}

	.caret {
		flex: none;
		width: 0.45em;
		height: 0.45em;
		margin-bottom: 0.2em;
		border-right: 2px solid currentColor;
		border-bottom: 2px solid currentColor;
		transform: rotate(45deg);
	}

	.cat[aria-expanded='true'] .caret {
		margin-top: 0.3em;
		margin-bottom: 0;
		transform: rotate(-135deg);
	}

	/* The section's kinds of goods, one per row with a chevron, like the menu of a shop's site. */
	.menu {
		margin-top: var(--space-2);
		padding: var(--space-2);
		background: var(--color-surface);
		border: 1px solid var(--color-border-subtle);
		border-radius: var(--radius-md);
		box-shadow: var(--shadow-card);
	}

	.menu ul {
		list-style: none;
		margin: 0;
		padding: 0;
		max-width: 24rem;
	}

	.sub {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
		width: 100%;
		min-height: var(--tap);
		padding: var(--space-2) var(--space-3);
		border: 0;
		border-radius: var(--radius-sm);
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.sub[aria-current='true'] {
		font-weight: 600;
		background: var(--color-surface-alt);
	}

	@media (hover: hover) {
		.sub:hover {
			background: var(--color-surface-alt);
		}
	}

	.chevron {
		flex: none;
		width: 0.5em;
		height: 0.5em;
		border-top: 2px solid currentColor;
		border-right: 2px solid currentColor;
		transform: rotate(45deg);
	}

	/* Wide screens: the sections fit in one row with dividers, and the menu drops down over the goods. */
	@media (min-width: 48rem) {
		.bar li + li::before {
			content: '';
			width: 1px;
			margin: var(--space-2) 0;
			background: currentColor;
			opacity: 0.35;
		}

		.menu {
			position: absolute;
			top: 100%;
			left: 0;
			right: 0;
			z-index: 5;
			margin-top: var(--space-1);
		}
	}

	.chosen {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2) var(--space-3);
		margin-top: var(--space-4);
	}

	.chosen .group {
		margin: 0;
	}

	.nearby-anchor:focus {
		outline: none;
	}
</style>
