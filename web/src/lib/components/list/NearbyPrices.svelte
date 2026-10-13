<!--
	"Hol a legolcsóbb a közelben?" (BUILD-BRIEF §6.3):
	1. the explanation card first, then the device's approximate position or a Budapest district;
	2. GET /api/stores once (kept in memory) and, ON THE DEVICE, the nearest grocery stores with price data
	   within the radius (at most 3 per chain, 25 in all); fewer than 2: suggest a wider radius;
	3. POST /api/quote with the bought lines and the store ids ONLY (never coordinates; sorted by id, so their
	   order says nothing about distances);
	4. the ranking with the scope note and the source, the optional 2-store split, and the list for the chosen
	   store. Without a connection, the chosen store's last list ($lib/list/offline), dated.

	Screen readers: one status region that always exists (`nearby-status`) says what happened after each step
	(how many stores, too few stores, the cheapest stores, prices updating), WCAG 4.1.3. The stored device
	position is shown with its time, and one over a day old is flagged; the browser is never asked again
	without a click.
-->
<script lang="ts">
	import { tick, untrack } from 'svelte';
	import { ApiError, postQuote } from '$lib/api/client';
	import type { ListLineOut, QtyLineIn, QuoteRequest, QuoteResponse, StoreId, StoreOut } from '$lib/api/types';
	import Attribution from '$lib/components/Attribution.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { districtById } from '$lib/districts';
	import { formatDateTime, formatDistance, formatMoney } from '$lib/format';
	import { groceryChainSet } from '$lib/geo';
	import { i18n, t, tp } from '$lib/i18n';
	import { loadStores } from '$lib/list/data';
	import { buildQuoteRequest } from '$lib/list/lines';
	import { saveLastQuote, savedQuoteFor } from '$lib/list/offline';
	import { rankingRows, scopeNote } from '$lib/list/ranking';
	import { chainLabel, chainNames, distanceMap, nearbyCandidates, storeAddress, widerRadius } from '$lib/list/stores';
	import { validQuote, validStores } from '$lib/list/validate';
	import { isStale, originFromLocation } from '$lib/location';
	import { getMeta } from '$lib/meta.svelte';
	import type { SavedQuote, StoredLocation } from '$lib/storage';
	import OriginChooser from './OriginChooser.svelte';
	import SplitSuggestion from './SplitSuggestion.svelte';
	import StoreList from './StoreList.svelte';
	import StoreRanking from './StoreRanking.svelte';

	interface Props {
		/** Every line of the list (names and sections for the store view). */
		listLines: readonly ListLineOut[];
		/** The bought lines, as sent to /api/quote. */
		quoteInput: readonly QtyLineIn[];
		/** Bought lines that could not be sent (over the limits). */
		skipped: readonly string[];
		location: StoredLocation;
		radiusKm: number;
		chosenStoreId: StoreId | null;
		checked: ReadonlySet<string>;
		onlocation: (next: StoredLocation) => void;
		onradius: (radiusKm: number) => void;
		onchoosestore: (storeId: StoreId) => void;
		ontogglecheck: (ingredientId: string, on: boolean) => void;
	}

	let {
		listLines,
		quoteInput,
		skipped,
		location,
		radiusKm,
		chosenStoreId,
		checked,
		onlocation,
		onradius,
		onchoosestore,
		ontogglecheck
	}: Props = $props();

	const id = $props.id();
	const meta = getMeta();
	/** Waits for the user to finish ticking "nincs otthon" or removing lines before asking for new prices. */
	const QUOTE_DEBOUNCE_MS = 300;

	const origin = $derived(originFromLocation(location));
	/** A device position over a day old: shown as such, and the chooser opens so it can be updated. */
	const stale = $derived(origin?.source === 'device' && isStale(location.approx));
	let choosing = $state(
		untrack(() => originFromLocation(location) === null || (location.source === 'device' && isStale(location.approx)))
	);
	let originHeading = $state<HTMLHeadingElement>();
	let originLine = $state<HTMLParagraphElement>();
	let storeHeading = $state<HTMLHeadingElement>();

	type StoresState =
		| { status: 'idle' | 'loading' }
		| { status: 'ready'; stores: StoreOut[] }
		| { status: 'error'; error: unknown };
	let storesState = $state<StoresState>({ status: 'idle' });

	function fetchStores(): void {
		storesState = { status: 'loading' };
		loadStores()
			.then((data) => {
				const valid = validStores(data);
				storesState = valid
					? { status: 'ready', stores: valid }
					: { status: 'error', error: new ApiError({ kind: 'invalid_response' }) };
			})
			.catch((error: unknown) => {
				storesState = { status: 'error', error };
			});
	}

	// The store list is fetched only once a starting point exists (and then only once per session).
	$effect(() => {
		if (origin === null) return;
		untrack(() => {
			if (storesState.status === 'idle') fetchStores();
		});
	});

	const grocery = $derived(groceryChainSet(meta.data?.chains ?? []));
	const names = $derived(chainNames(meta.data?.chains));
	const stores = $derived(storesState.status === 'ready' ? storesState.stores : null);
	const storesById = $derived(new Map((stores ?? []).map((store) => [store.id, store])));
	const candidates = $derived(origin && stores ? nearbyCandidates(origin, stores, radiusKm, grocery) : null);
	const distances = $derived(candidates ? distanceMap(candidates.picks) : new Map<StoreId, number>());
	const wider = $derived(widerRadius(radiusKm));
	const radiusText = $derived(formatDistance(radiusKm));
	const request = $derived(
		candidates ? buildQuoteRequest(quoteInput, candidates.picks.map((pick) => pick.store.id)) : null
	);
	// A string, so the quote is fetched again only when the request really changes.
	const requestBody = $derived(request ? JSON.stringify(request) : null);

	interface QuoteState {
		status: 'idle' | 'loading' | 'ready' | 'error' | 'offline';
		quote: QuoteResponse | null;
		/** The request the shown quote answers (it is outdated while this differs from `requestBody`). */
		body: string | null;
		error: unknown;
		/** status 'offline': the chosen store's last list for this very request. */
		saved?: SavedQuote | null;
	}
	let quoteState = $state<QuoteState>({ status: 'idle', quote: null, body: null, error: null });
	let quoteAttempt = $state(0);

	$effect(() => {
		const body = requestBody;
		void quoteAttempt; // "Újra" asks again for the same request
		if (body === null) {
			untrack(() => {
				quoteState = { status: 'idle', quote: null, body: null, error: null };
			});
			return;
		}
		const controller = new AbortController();
		const timer = setTimeout(() => {
			quoteState = { ...quoteState, status: 'loading', error: null };
			postQuote(JSON.parse(body) as QuoteRequest, { signal: controller.signal })
				.then((raw) => {
					if (controller.signal.aborted) return;
					const quote = validQuote(raw);
					quoteState = quote
						? { status: 'ready', quote, body, error: null }
						: { status: 'error', quote: null, body: null, error: new ApiError({ kind: 'invalid_response' }) };
				})
				.catch((error: unknown) => {
					if (controller.signal.aborted) return;
					// No connection (in the shop): the chosen store's list as last loaded, with its data date.
					const saved = savedQuoteFor(body, error);
					quoteState = saved
						? { status: 'offline', quote: null, body, error, saved }
						: { status: 'error', quote: null, body: null, error };
				});
		}, QUOTE_DEBOUNCE_MS);
		return () => {
			clearTimeout(timer);
			controller.abort();
		};
	});

	const quote = $derived(quoteState.quote);
	const updating = $derived(quote !== null && (quoteState.status === 'loading' || quoteState.body !== requestBody));
	const rows = $derived(quote ? rankingRows(quote, distances) : []);
	const chosenStore = $derived(
		quote && chosenStoreId ? (quote.stores.find((store) => store.store_id === chosenStoreId) ?? null) : null
	);
	const lineNames = $derived(new Map(listLines.map((line) => [line.ingredient_id, line.name_hu])));
	const savedQuote = $derived(quoteState.status === 'offline' ? (quoteState.saved ?? null) : null);

	// Keep the chosen store's list of the current quote on the device, for the shop without a signal.
	$effect(() => {
		const current = quoteState;
		const store = chosenStore;
		if (current.status !== 'ready' || !current.quote || current.body === null || current.body !== requestBody || !store) {
			return;
		}
		const body = current.body;
		const dataDate = current.quote.data_date;
		untrack(() => saveLastQuote(body, dataDate, $state.snapshot(store)));
	});

	/** What the status region says: the outcome of the last step, never a price the server did not send. */
	const statusText = $derived.by(() => {
		if (origin === null) return '';
		if (storesState.status === 'idle' || storesState.status === 'loading') return t('list.stores_loading');
		if (storesState.status === 'error' || !candidates) return '';
		const parts = [tp('list.candidates', candidates.picks.length, { radius: radiusText })];
		if (candidates.withoutData > 0) parts.push(tp('list.without_data', candidates.withoutData));
		if (candidates.tooFew) {
			parts.push(
				candidates.picks.length === 0
					? t('list.no_stores_in_range', { radius: radiusText })
					: t('list.one_store_in_range', { radius: radiusText })
			);
		}
		if (quoteState.status === 'offline' && savedQuote) {
			parts.push(t('list.offline_quote', { time: formatDateTime(savedQuote.savedAt) }));
		} else if (quoteState.status !== 'error' && quote && request) {
			if (updating) {
				parts.push(t('list.quote_updating'));
			} else {
				// Every store of the first tie group, in the shown order (by distance), never one chain alone.
				const first = rows.filter((row) => row.rank === rows[0]?.rank);
				const stores = first.map((row) => `${storeLabel(row.storeId)} (${formatMoney(row.checkoutTotal)})`).join('; ');
				if (stores) parts.push(t('list.status_cheapest', { note: scopeNote(quote, i18n.lang), stores }));
			}
		} else if (quoteState.status !== 'error' && request) {
			parts.push(t('list.quote_loading'));
		}
		return parts.join(' ');
	});
	const district = $derived(origin?.source === 'district' ? districtById(origin.districtId) : null);
	const districtName = $derived(district ? t('core.district_name', { roman: district.roman }) : '');

	function storeLabel(storeId: StoreId): string {
		const info = storesById.get(storeId);
		const chain = chainLabel(info?.chain ?? quote?.stores.find((s) => s.store_id === storeId)?.chain ?? storeId, names);
		const address = storeAddress(info);
		return address ? `${chain}, ${address}` : chain;
	}

	function lineName(ingredientId: string): string {
		return lineNames.get(ingredientId) ?? ingredientId;
	}

	function retryQuote(): void {
		quoteAttempt += 1;
	}

	async function openChooser(): Promise<void> {
		choosing = true;
		await tick();
		originHeading?.focus();
	}

	async function closeChooser(): Promise<void> {
		choosing = false;
		await tick();
		originLine?.focus();
	}

	async function chooseStore(storeId: StoreId): Promise<void> {
		onchoosestore(storeId);
		await tick();
		storeHeading?.focus();
	}
</script>

<section class="nearby" aria-labelledby="{id}-title">
	<h2 id="{id}-title">{t('list.nearby_title')}</h2>
	<p class="visually-hidden" role="status" data-testid="nearby-status">{statusText}</p>

	{#if choosing || origin === null}
		<OriginChooser
			{location}
			hasOrigin={origin !== null}
			{onlocation}
			ondone={closeChooser}
			bind:heading={originHeading}
		/>
	{/if}

	{#if origin}
		<div class="origin">
			<p tabindex="-1" bind:this={originLine} data-testid="origin">
				{origin.source === 'device'
					? t('list.origin_device', { time: formatDateTime(location.approx?.at) })
					: t('list.origin_district', { district: districtName })}
				{t('list.radius_info', { radius: radiusText })}
			</p>
			{#if stale}
				<p class="notice notice-warning" data-testid="position-stale">{t('list.position_stale')}</p>
			{/if}
			<div class="btn-row">
				{#if !choosing}
					{#if origin.source === 'device'}
						<button type="button" class="btn btn-secondary" onclick={openChooser}>{t('list.refresh_position')}</button>
					{/if}
					<button type="button" class="btn btn-secondary" onclick={openChooser}>{t('list.change_origin')}</button>
				{/if}
				<a class="btn btn-secondary" href="/beallitasok">{t('list.radius_settings')}</a>
			</div>
		</div>

		{#if storesState.status === 'idle' || storesState.status === 'loading'}
			<Spinner label={t('list.stores_loading')} showLabel announce={false} />
		{:else if storesState.status === 'error'}
			<ErrorState error={storesState.error} title={t('list.stores_error_title')} onretry={fetchStores} />
		{:else if candidates}
			<p class="small muted" data-testid="candidates">
				{tp('list.candidates', candidates.picks.length, { radius: radiusText })}
				{#if candidates.withoutData > 0}
					{tp('list.without_data', candidates.withoutData)}
				{/if}
			</p>

			{#if candidates.tooFew}
				<div class="notice notice-warning" data-testid="too-few">
					<p>
						{candidates.picks.length === 0
							? t('list.no_stores_in_range', { radius: radiusText })
							: t('list.one_store_in_range', { radius: radiusText })}
					</p>
					{#if wider !== null}
						<button type="button" class="btn btn-secondary" onclick={() => onradius(wider)}>
							{t('list.widen_radius', { radius: formatDistance(wider) })}
						</button>
					{:else}
						<p>{t('list.radius_max')}</p>
					{/if}
				</div>
			{/if}

			{#if quoteInput.length === 0}
				<p class="notice notice-info">{t('list.nothing_to_quote')}</p>
			{/if}
			{#if skipped.length > 0}
				<p class="notice notice-warning">{tp('list.skipped', skipped.length)}</p>
			{/if}

			{#if quoteState.status === 'error'}
				<ErrorState error={quoteState.error} title={t('list.quote_error_title')} onretry={retryQuote} />
			{:else if savedQuote}
				<div class="notice notice-warning offline-copy" data-testid="quote-offline">
					<p>{t('list.offline_quote', { time: formatDateTime(savedQuote.savedAt) })}</p>
					<button type="button" class="btn btn-secondary" onclick={retryQuote}>{t('core.retry')}</button>
				</div>
				<StoreList
					store={savedQuote.store}
					storeInfo={storesById.get(savedQuote.store.store_id)}
					chainName={chainLabel(savedQuote.store.chain, names)}
					distanceKm={distances.get(savedQuote.store.store_id) ?? null}
					{listLines}
					{checked}
					{ontogglecheck}
					dataDate={savedQuote.dataDate}
					kshPeriod={meta.data?.ksh_period ?? null}
					kshUrl={meta.data?.attribution.ksh.url ?? null}
					bind:heading={storeHeading}
				/>
			{:else if quote && request}
				{#if updating}
					<Spinner label={t('list.quote_updating')} showLabel announce={false} />
				{/if}
				<div class="results" aria-busy={updating}>
					<StoreRanking {quote} {rows} stores={storesById} {names} {chosenStoreId} onchoose={chooseStore} />
					{#if quote.split}
						<SplitSuggestion split={quote.split} stores={quote.stores} {storeLabel} {lineName} />
					{/if}
					<Attribution dataDate={quote.data_date} />
					{#if chosenStore}
						<StoreList
							store={chosenStore}
							storeInfo={storesById.get(chosenStore.store_id)}
							chainName={chainLabel(chosenStore.chain, names)}
							distanceKm={distances.get(chosenStore.store_id) ?? null}
							{listLines}
							{checked}
							{ontogglecheck}
							dataDate={quote.data_date}
							kshPeriod={meta.data?.ksh_period ?? null}
							kshUrl={meta.data?.attribution.ksh.url ?? null}
							bind:heading={storeHeading}
						/>
					{/if}
				</div>
			{:else if request}
				<Spinner label={t('list.quote_loading')} showLabel announce={false} />
			{/if}
		{/if}
	{/if}
</section>

<style>
	.nearby {
		margin-top: var(--space-6);
		padding-top: var(--space-4);
		border-top: 1px solid var(--color-border-subtle);
	}

	.nearby > :global(* + *) {
		margin-top: var(--space-4);
	}

	.origin p {
		margin: 0 0 var(--space-2);
	}

	.origin p:focus {
		outline: none;
	}

	.origin p:focus-visible {
		outline: var(--focus-ring);
	}

	.notice p {
		margin: 0 0 var(--space-2);
	}

	.offline-copy {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2) var(--space-3);
	}

	.offline-copy p {
		margin: 0;
	}

	.results > :global(* + *) {
		margin-top: var(--space-5);
	}
</style>
