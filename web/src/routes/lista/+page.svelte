<!--
	Shopping list ("Bevásárlólista") and "Hol a legolcsóbb a közelben?".

	- The list is made from the plan stored on this device (StoredState.plan) for the chosen days: every planned
	  meal is `people` servings, summed per recipe (planToListItems), sent to POST /api/list. Only recipe ids
	  and servings leave the device (no on-hand quantities: a pantry staple is at home or "nincs otthon").
	- Ticks (StoredState.checkedItems), "nincs otthon" (StoredState.pantry.notAtHome), the range, the removed
	  lines and the chosen store per list (StoredState.list, helpers in $lib/list/prefs) stay on this device,
	  in the one document of $lib/storage.
	- Prices: see NearbyPrices (store ids only, never coordinates; source, date and scope note on every price).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError, postList } from '$lib/api/client';
	import type { ListLineOut, ListRequest, RecipeId, StoreId } from '$lib/api/types';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import NearbyPrices from '$lib/components/list/NearbyPrices.svelte';
	import RangePicker from '$lib/components/list/RangePicker.svelte';
	import ShoppingList from '$lib/components/list/ShoppingList.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, tp } from '$lib/i18n';
	import { loadRecipes } from '$lib/list/data';
	import { lineChoices, quoteLines, toggleId } from '$lib/list/lines';
	import { listEntry, withListEntry, type ListEntry } from '$lib/list/prefs';
	import { effectiveRange, type ListRange } from '$lib/list/range';
	import { buildListRequest, listKey } from '$lib/list/request';
	import { recipeIds, validListLines } from '$lib/list/validate';
	import { todayInBudapest } from '$lib/plan/dates';
	import { isPersistent, load, update, type StatePatch, type StoredLocation, type StoredState } from '$lib/storage';

	let settings = $state<StoredState>(load());
	let persistent = $state(isPersistent());
	const today = todayInBudapest();
	const prefs = $derived(settings.list);

	const plan = $derived(settings.plan);
	const range = $derived(plan ? effectiveRange(plan, prefs.range, today) : prefs.range);
	const key = $derived(plan ? listKey(plan, range) : null);
	const entry = $derived(key ? listEntry(prefs, key) : null);

	type RecipesState =
		| { status: 'idle' | 'loading' }
		| { status: 'ready'; ids: RecipeId[] }
		| { status: 'error'; error: unknown };
	let recipes = $state<RecipesState>({ status: 'idle' });

	function fetchRecipes(): void {
		recipes = { status: 'loading' };
		loadRecipes()
			.then((data) => {
				recipes = Array.isArray(data.recipes)
					? { status: 'ready', ids: recipeIds(data.recipes) }
					: { status: 'error', error: new ApiError({ kind: 'invalid_response' }) };
			})
			.catch((error: unknown) => {
				recipes = { status: 'error', error };
			});
	}

	onMount(() => {
		if (settings.plan) fetchRecipes();
	});

	const listPlan = $derived(
		plan && recipes.status === 'ready'
			? buildListRequest(
					plan,
					range,
					today,
					recipes.ids.map((recipeId) => ({ id: recipeId })),
					settings.people
				)
			: null
	);
	// A string, so ticking a box (which replaces `settings`) never fetches the list again.
	const listBody = $derived(listPlan?.request ? JSON.stringify(listPlan.request) : null);

	interface ListState {
		status: 'idle' | 'loading' | 'ready' | 'error';
		lines: ListLineOut[];
		error: unknown;
	}
	let listState = $state<ListState>({ status: 'idle', lines: [], error: null });
	let listAttempt = $state(0);

	$effect(() => {
		const body = listBody;
		void listAttempt; // "Újra" asks again for the same list
		if (body === null) {
			listState = { status: 'idle', lines: [], error: null };
			return;
		}
		const controller = new AbortController();
		listState = { status: 'loading', lines: [], error: null };
		postList(JSON.parse(body) as ListRequest, { signal: controller.signal })
			.then((raw) => {
				if (controller.signal.aborted) return;
				const lines = validListLines(raw);
				listState = lines
					? { status: 'ready', lines, error: null }
					: { status: 'error', lines: [], error: new ApiError({ kind: 'invalid_response' }) };
			})
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				listState = { status: 'error', lines: [], error };
			});
		return () => controller.abort();
	});

	const lines = $derived(listState.status === 'ready' ? listState.lines : []);
	const choices = $derived(lineChoices(entry?.removed ?? [], settings.pantry.notAtHome));
	const quote = $derived(quoteLines(lines, choices));
	const checked = $derived(new Set(settings.checkedItems));

	function patch(next: StatePatch): void {
		settings = update(next);
		persistent = isPersistent();
	}

	function saveEntry(next: ListEntry): void {
		patch({ list: withListEntry(prefs, next) });
	}

	function chooseRange(next: ListRange): void {
		patch({ list: { range: next, entries: prefs.entries } });
	}

	function toggleCheck(ingredientId: string, on: boolean): void {
		patch({ checkedItems: toggleId(settings.checkedItems, ingredientId, on) });
	}

	function clearChecks(): void {
		const onList = new Set(lines.map((line) => line.ingredient_id));
		patch({ checkedItems: settings.checkedItems.filter((ingredientId) => !onList.has(ingredientId)) });
	}

	function removeLine(ingredientId: string): void {
		if (entry) saveEntry({ ...entry, removed: toggleId(entry.removed, ingredientId, true) });
	}

	function restoreLine(ingredientId: string): void {
		if (entry) saveEntry({ ...entry, removed: toggleId(entry.removed, ingredientId, false) });
	}

	function setNotAtHome(ingredientId: string, notAtHome: boolean): void {
		patch({ pantry: { ...settings.pantry, notAtHome: toggleId(settings.pantry.notAtHome, ingredientId, notAtHome) } });
	}

	function chooseStore(storeId: StoreId): void {
		if (entry) saveEntry({ ...entry, storeId });
	}

	function setLocation(next: StoredLocation): void {
		patch({ location: next });
	}

	function setRadius(radiusKm: number): void {
		patch({ radiusKm });
	}
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('list.title') })}</title>
</svelte:head>

<h1>{t('list.title')}</h1>

{#if !persistent}
	<p class="notice notice-warning" role="status">{t('list.storage_unavailable')}</p>
{/if}

{#if !plan}
	<EmptyState title={t('list.no_plan_title')} message={t('list.no_plan_text')}>
		<a class="btn btn-primary" href="/terv">{t('list.to_plan')}</a>
	</EmptyState>
{:else}
	<p class="muted">{t('list.intro')}</p>

	<div class="card range-card">
		<RangePicker {plan} {today} value={range} onchange={chooseRange} />
	</div>

	{#if listPlan && listPlan.unknownRecipeIds.length > 0}
		<p class="notice notice-warning">{tp('list.unknown_recipes', listPlan.unknownRecipeIds.length)}</p>
	{/if}

	<div class="list-area">
		{#if recipes.status === 'idle' || recipes.status === 'loading'}
			<Spinner label={t('list.loading')} showLabel />
		{:else if recipes.status === 'error'}
			<ErrorState error={recipes.error} title={t('list.error_title')} onretry={fetchRecipes} />
		{:else if listPlan && listPlan.request === null}
			<p class="notice notice-info">{t('list.range_no_meals')}</p>
		{:else if listState.status === 'error'}
			<ErrorState error={listState.error} title={t('list.error_title')} onretry={() => (listAttempt += 1)} />
		{:else if listState.status === 'ready'}
			<ShoppingList
				{lines}
				{choices}
				{checked}
				ontogglecheck={toggleCheck}
				onclearchecks={clearChecks}
				onremove={removeLine}
				onrestore={restoreLine}
				onnotathome={setNotAtHome}
			/>
			{#if lines.length > 0}
				<NearbyPrices
					listLines={lines}
					quoteInput={quote.lines}
					skipped={quote.skipped}
					location={settings.location}
					radiusKm={settings.radiusKm}
					chosenStoreId={entry?.storeId ?? null}
					{checked}
					onlocation={setLocation}
					onradius={setRadius}
					onchoosestore={chooseStore}
					ontogglecheck={toggleCheck}
				/>
			{/if}
		{:else}
			<Spinner label={t('list.loading')} showLabel />
		{/if}
	</div>
{/if}

<style>
	.range-card {
		margin: var(--space-4) 0;
	}

	.list-area {
		margin-top: var(--space-4);
	}
</style>
