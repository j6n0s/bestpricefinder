<!--
	Kosár: the list of the goods chosen on the Termékek page, with their amounts (− / +; at the smallest amount
	the − removes the good), and where the cart is cheapest nearby: in one store, or on a short route through
	2–3 stores with a schematic map (NearbyPrices + ShoppingOptions, the same as the plan's shopping list).
	Goods are found and added on the Termékek page ("További termékek" leads there); the state is shared with
	it through $lib/cart/session.svelte.ts.

	- The cart is personal data: it stays on this device (StoredState.cart). Only ingredient ids and amounts
	  are sent to POST /api/quote, with the nearby store ids; never a position.
	- Goods that lost their store price are written out of the cart when the catalogue arrives (with a notice).
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { approxPieces } from '$lib/cart/cart';
	import { CartSession } from '$lib/cart/session.svelte';
	import QtyStepper from '$lib/components/cart/QtyStepper.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import NearbyPrices from '$lib/components/list/NearbyPrices.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, tp } from '$lib/i18n';
	import { groupLabelKey, groupLines } from '$lib/list/groups';

	const session = new CartSession();

	onMount(() => session.start());

	const cartGroups = $derived(groupLines(session.listLines));

	let undoButton = $state<HTMLButtonElement>();
	let cartTitle = $state<HTMLElement>();

	/** After the − removed a line, its button is gone: the focus continues at the cart's heading, never at <body>. */
	async function setQty(ingredientId: string, qty: number | null): Promise<void> {
		session.setQty(ingredientId, qty);
		await tick();
		const active = document.activeElement;
		if (active === null || active === document.body) cartTitle?.focus();
	}

	async function clearCart(): Promise<void> {
		session.clearCart();
		await tick();
		undoButton?.focus();
	}

	/** "Visszavonás" removes itself with its notice: the focus continues at the cart's heading, never at <body>. */
	async function undoClear(): Promise<void> {
		session.undoClear();
		await tick();
		cartTitle?.focus();
	}
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('cart.title') })}</title>
</svelte:head>

<h1>{t('cart.title')}</h1>

{#if !session.persistent}
	<p class="notice notice-warning" role="status">{t('list.storage_unavailable')}</p>
{/if}

{#if session.catalogue.status === 'idle' || session.catalogue.status === 'loading'}
	<Spinner label={t('cart.loading')} showLabel />
{:else if session.catalogue.status === 'error'}
	<ErrorState error={session.catalogue.error} title={t('cart.error_title')} onretry={() => session.fetchCatalogue()} />
{:else}
	<section class="card cart" aria-labelledby="cart-title" data-testid="cart">
		<h2 id="cart-title" tabindex="-1" bind:this={cartTitle}>
			{t('cart.cart_title')}
			<span class="count" data-testid="cart-count">{tp('cart.cart_count', session.listLines.length)}</span>
		</h2>
		{#if session.undoLines}
			<div class="notice notice-info undo" role="status">
				<p>{t('cart.cleared')}</p>
				<button type="button" class="btn btn-secondary" bind:this={undoButton} onclick={undoClear}>
					{t('cart.undo')}
				</button>
			</div>
		{/if}
		{#if session.dropped > 0}
			<p class="notice notice-warning" data-testid="cart-dropped">{tp('cart.dropped', session.dropped)}</p>
		{/if}
		{#if session.listLines.length === 0}
			<p class="muted">{t('cart.cart_empty')}</p>
			<div class="btn-row">
				<a class="btn btn-primary" href="/termekek">{t('cart.find_goods')}</a>
			</div>
		{:else}
			{#each cartGroups as group (group.group)}
				<h3 class="group">{t(groupLabelKey(group.group))}</h3>
				<ul class="rows">
					{#each group.lines as line (line.ingredient_id)}
						{@const ingredient = session.byId.get(line.ingredient_id)}
						{@const pieces = ingredient ? approxPieces(line.qty, ingredient) : null}
						<li class="row" data-testid="cart-line" data-ingredient-id={line.ingredient_id}>
							<span class="name">
								<span lang="hu">{line.name_hu}</span>
								{#if pieces !== null}
									<span class="pieces small muted">{t('cart.pieces', { count: pieces })}</span>
								{/if}
							</span>
							<span class="control">
								<QtyStepper name={line.name_hu} qty={line.qty} unit={line.unit} onchange={(qty) => setQty(line.ingredient_id, qty)} />
							</span>
						</li>
					{/each}
				</ul>
			{/each}
			<div class="btn-row">
				<a class="btn btn-primary" href="#hol-a-legolcsobb">{t('cart.to_prices')}</a>
				<a class="btn btn-secondary" href="/termekek">{t('cart.browse_more')}</a>
				<button type="button" class="btn btn-secondary" onclick={clearCart}>{t('cart.clear')}</button>
			</div>
		{/if}
	</section>

	{#if session.listLines.length > 0}
		<div id="hol-a-legolcsobb" class="nearby-anchor" tabindex="-1">
			<NearbyPrices
				listLines={session.listLines}
				quoteInput={session.quoteInput}
				skipped={[]}
				location={session.stored.location}
				radiusKm={session.stored.radiusKm}
				chosenStoreId={session.cart.storeId}
				checked={session.checked}
				onlocation={(next) => session.setLocation(next)}
				onradius={(km) => session.setRadius(km)}
				onchoosestore={(storeId) => session.chooseStore(storeId)}
				ontogglecheck={(id, on) => session.toggleCheck(id, on)}
			/>
		</div>
	{/if}
{/if}

<style>
	.cart {
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

	/* The name, with the piece count under it; the − amount + control on the right. */
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

	.nearby-anchor:focus {
		outline: none;
	}
</style>
