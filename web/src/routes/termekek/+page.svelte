<!--
	Termékek: find the goods that have store prices and put them in the cart. The goods are browsed like a
	shop's menu (a bar of shop sections and, under a section, its kinds of goods: $lib/cart/categories, from
	the ingredient tags) or searched by name across every section. "Kosárba" puts a good in the cart at a
	sensible first amount; the row then shows the − amount + control. The cart itself (the list of the chosen
	goods, and where it is cheapest) is the Kosár page, reached from the header's basket and from the link
	under the title. The state is shared with that page through $lib/cart/session.svelte.ts; whichever page
	loads the catalogue first writes the goods without a store price out of the cart, and says so.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import type { IngredientOut } from '$lib/api/types';
	import { MAX_CART_LINES, approxPieces, searchGoods } from '$lib/cart/cart';
	import { categoriesOf, selectGoods, subcategoryLabelKey, type Selection } from '$lib/cart/categories';
	import { CartSession } from '$lib/cart/session.svelte';
	import QtyStepper from '$lib/components/cart/QtyStepper.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, tp } from '$lib/i18n';
	import { groupLabelKey, groupLines, type ListGroup } from '$lib/list/groups';

	const session = new CartSession();

	onMount(() => session.start());

	let query = $state('');
	/** The section (and kind of goods) chosen on the bar; a search looks through every section instead. */
	let selected = $state<Selection | null>(null);
	let openMenu = $state<ListGroup | null>(null);
	const categories = $derived(categoriesOf(session.goods));
	const openCategory = $derived(categories.find((category) => category.group === openMenu) ?? null);
	const searching = $derived(query.trim() !== '');
	const shown = $derived(
		searching ? searchGoods(session.goods, query) : selected ? selectGoods(session.goods, selected) : session.goods
	);
	const shownGroups = $derived(groupLines(shown));
	const chosenLabel = $derived.by(() => {
		if (!selected) return '';
		const group = t(groupLabelKey(selected.group));
		return selected.sub === null ? group : t('cart.category_heading', { group, sub: t(subcategoryLabelKey(selected.sub)) });
	});

	let searchInput = $state<HTMLInputElement>();
	let goodsList = $state<HTMLElement>();
	let categoriesNav = $state<HTMLElement>();
	let categoryButtons = $state<Record<string, HTMLButtonElement | undefined>>({});
	let chosenHeading = $state<HTMLHeadingElement>();

	/**
	 * Keeps the keyboard focus on the good just changed when its controls were swapped ("Kosárba" <-> − amount +):
	 * the button pressed no longer exists, and focus would fall back to the page.
	 */
	async function keepFocus(ingredientId: string): Promise<void> {
		await tick();
		const active = document.activeElement;
		if (active !== null && active !== document.body) return; // the pressed button is still there
		const row = goodsList?.querySelector(`[data-ingredient-id="${CSS.escape(ingredientId)}"]`);
		const buttons = row?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
		buttons?.[buttons.length - 1]?.focus(); // "+" after adding, "Kosárba" after removing
	}

	function setQty(ingredientId: string, qty: number | null): void {
		session.setQty(ingredientId, qty);
		void keepFocus(ingredientId);
	}

	function add(good: IngredientOut): void {
		if (session.add(good)) void keepFocus(good.id);
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
	<title>{t('core.page_title', { page: t('cart.goods_title') })}</title>
</svelte:head>

<h1>{t('cart.goods_title')}</h1>

{#if !session.persistent}
	<p class="notice notice-warning" role="status">{t('list.storage_unavailable')}</p>
{/if}

{#if session.catalogue.status === 'idle' || session.catalogue.status === 'loading'}
	<Spinner label={t('cart.loading')} showLabel />
{:else if session.catalogue.status === 'error'}
	<ErrorState error={session.catalogue.error} title={t('cart.error_title')} onretry={() => session.fetchCatalogue()} />
{:else}
	<!-- The way to the cart, with how many goods it holds (the header's basket says the same). -->
	<p class="cart-link">
		<a href="/kosar" data-testid="goods-cart-link">{t('cart.open_cart', { items: tp('cart.cart_count', session.listLines.length) })}</a>
	</p>

	<section class="card goods" aria-labelledby="goods-title" data-testid="goods">
		<h2 id="goods-title" class="visually-hidden">{t('cart.goods_title')}</h2>
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
		{#if session.fullNotice}
			<p class="notice notice-warning" role="status">{t('cart.full', { max: MAX_CART_LINES })}</p>
		{/if}
		{#if session.dropped > 0}
			<p class="notice notice-warning" role="status" data-testid="cart-dropped">{tp('cart.dropped', session.dropped)}</p>
		{/if}
		{#if shown.length === 0}
			<div class="notice notice-info">
				<p>{t('cart.no_results')}</p>
				<button type="button" class="btn btn-secondary" onclick={clearSearch}>{t('cart.clear_search')}</button>
			</div>
		{:else}
			<div bind:this={goodsList}>
				{#each shownGroups as group (group.group)}
					{#if !selected || searching}
						<h3 class="group">{t(groupLabelKey(group.group))}</h3>
					{/if}
					<ul class="rows">
						{#each group.lines as good (good.id)}
							{@const qty = session.qtyById.get(good.id)}
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
										<QtyStepper name={good.name_hu} {qty} unit={good.unit} onchange={(next) => setQty(good.id, next)} />
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
	</section>
{/if}

<style>
	.cart-link {
		margin: 0 0 var(--space-3);
	}

	.cart-link a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
		font-weight: 600;
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

	/* Bold: the goods already in the cart. */
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

	.field {
		margin-top: var(--space-3);
	}

	/* The shop's menu: the sections in one bar (wrapping on narrow screens), the chosen one underlined. */
	.categories {
		position: relative;
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
</style>
