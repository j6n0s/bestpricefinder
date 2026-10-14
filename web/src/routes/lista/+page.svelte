<!--
	Shopping list ("Bevásárlólista") and "Hol a legolcsóbb a közelben?".

	- The list is made from the plan stored on this device (StoredState.plan) for the chosen days: every planned
	  meal is `people` servings, summed per recipe (planToListItems), sent to POST /api/list. Only recipe ids
	  and servings leave the device (no on-hand quantities: a pantry staple is at home or "nincs otthon").
	- "nincs otthon" (StoredState.pantry.notAtHome), the range, and per list (plan + range: a new plan or
	  range starts afresh) the ticks, the removed lines, the excluded lines bought anyway and the chosen store
	  (StoredState.list, helpers in $lib/list/prefs) stay on this device, in the one document of $lib/storage.
	- Ingredients excluded in the settings (StoredState.exclusions.ingredients) are not bought and not priced
	  unless the user chooses "mégis megveszem" for this list ($lib/list/lines).
	- Offline (in the shop): the last list is kept on the device ($lib/list/offline) and shown, dated, when
	  POST /api/list fails for lack of a connection.
	- Another tab may change or delete the stored data: the page reloads it (onExternalChange) and builds every
	  change from a fresh load(), so it never writes deleted data back.
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
	import { formatDateTime } from '$lib/format';
	import { t, tp } from '$lib/i18n';
	import { loadRecipes } from '$lib/list/data';
	import { lineChoices, quoteLines, toggleId } from '$lib/list/lines';
	import { saveLastList, savedListFor } from '$lib/list/offline';
	import { listEntry, withListEntry, type ListEntry } from '$lib/list/prefs';
	import { effectiveRange, type ListRange } from '$lib/list/range';
	import { buildListRequest, listKey } from '$lib/list/request';
	import { recipeIds, validListLines } from '$lib/list/validate';
	import { todayInBudapest } from '$lib/plan/dates';
	import {
		isPersistent,
		load,
		onExternalChange,
		update,
		type StatePatch,
		type StoredLocation,
		type StoredState
	} from '$lib/storage';

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
		// Another tab changed or deleted the data ("Minden adat törlése", a revoked position, a new plan).
		return onExternalChange((next) => {
			settings = next;
			persistent = isPersistent();
			if (next.plan && recipes.status === 'idle') fetchRecipes();
		});
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
		/** Set when the lines are the offline copy: when they were loaded. */
		savedAt: string | null;
	}
	let listState = $state<ListState>({ status: 'idle', lines: [], error: null, savedAt: null });
	let listAttempt = $state(0);

	$effect(() => {
		const body = listBody;
		void listAttempt; // "Újra" asks again for the same list
		if (body === null) {
			listState = { status: 'idle', lines: [], error: null, savedAt: null };
			return;
		}
		const controller = new AbortController();
		listState = { status: 'loading', lines: [], error: null, savedAt: null };
		postList(JSON.parse(body) as ListRequest, { signal: controller.signal })
			.then((raw) => {
				if (controller.signal.aborted) return;
				const lines = validListLines(raw);
				if (lines) saveLastList(body, lines);
				listState = lines
					? { status: 'ready', lines, error: null, savedAt: null }
					: { status: 'error', lines: [], error: new ApiError({ kind: 'invalid_response' }), savedAt: null };
			})
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				// No connection (in the shop): the same list as last loaded, dated.
				const saved = savedListFor(body, error);
				listState = saved
					? { status: 'ready', lines: saved.lines, error: null, savedAt: saved.savedAt }
					: { status: 'error', lines: [], error, savedAt: null };
			});
		return () => controller.abort();
	});

	const lines = $derived(listState.status === 'ready' ? listState.lines : []);
	const choices = $derived(
		lineChoices(entry?.removed ?? [], settings.pantry.notAtHome, settings.exclusions.ingredients, entry?.included ?? [])
	);
	const quote = $derived(quoteLines(lines, choices));
	// Ticks belong to THIS list: a new plan or another range starts with none.
	const checked = $derived(new Set(entry?.checked ?? []));

	function patch(next: StatePatch): void {
		settings = update(next);
		persistent = isPersistent();
	}

	/**
	 * Changes this list's entry. Built from a fresh load(), never from the copy this page read earlier: another
	 * tab may have changed or deleted the data in the meantime.
	 */
	function changeEntry(change: (current: ListEntry) => ListEntry): void {
		if (!key) return;
		const stored = load().list;
		patch({ list: withListEntry(stored, change(listEntry(stored, key))) });
	}

	function chooseRange(next: ListRange): void {
		patch({ list: { range: next, entries: load().list.entries } });
	}

	function toggleCheck(ingredientId: string, on: boolean): void {
		changeEntry((current) => ({ ...current, checked: toggleId(current.checked, ingredientId, on) }));
	}

	function clearChecks(): void {
		changeEntry((current) => ({ ...current, checked: [] }));
	}

	function removeLine(ingredientId: string): void {
		changeEntry((current) => ({ ...current, removed: toggleId(current.removed, ingredientId, true) }));
	}

	function restoreLine(ingredientId: string): void {
		changeEntry((current) => ({ ...current, removed: toggleId(current.removed, ingredientId, false) }));
	}

	function includeLine(ingredientId: string): void {
		changeEntry((current) => ({ ...current, included: toggleId(current.included, ingredientId, true) }));
	}

	function setNotAtHome(ingredientId: string, notAtHome: boolean): void {
		const pantry = load().pantry;
		patch({ pantry: { ...pantry, notAtHome: toggleId(pantry.notAtHome, ingredientId, notAtHome) } });
	}

	function chooseStore(storeId: StoreId): void {
		changeEntry((current) => ({ ...current, storeId }));
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
	<EmptyState title={t('list.no_plan_title')}>
		<a class="btn btn-primary" href="/terv">{t('list.to_plan')}</a>
	</EmptyState>
{:else}
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
			{#if listState.savedAt}
				<div class="notice notice-warning offline-copy" data-testid="list-offline">
					<p>{t('list.offline_list', { time: formatDateTime(listState.savedAt) })}</p>
					<button type="button" class="btn btn-secondary" onclick={() => (listAttempt += 1)}>{t('core.retry')}</button>
				</div>
			{/if}
			<ShoppingList
				{lines}
				{choices}
				{checked}
				ontogglecheck={toggleCheck}
				onclearchecks={clearChecks}
				onremove={removeLine}
				onrestore={restoreLine}
				onnotathome={setNotAtHome}
				oninclude={includeLine}
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

	.offline-copy {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2) var(--space-3);
		margin-bottom: var(--space-4);
	}

	.offline-copy p {
		margin: 0;
	}
</style>
