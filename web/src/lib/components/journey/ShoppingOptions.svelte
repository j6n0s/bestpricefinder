<!--
	"Hol vásárolj?": the answer first, in two options (src/lib/journey):
	- "Egy boltban": the store where the most of the list can be bought, cheapest among those, walking counted;
	- "Körút": the best route through 2–3 nearby stores, when it gets more of the list or saves more than the
	  extra walk and stop are worth. Its stops are numbered in walking order, drawn on a schematic map (no map
	  tiles, nothing sent anywhere) and linked to OpenStreetMap one by one (the store's public position only).
	When no route is worth it, the card says so and why. Prices are the server's per-line checkout costs; the
	scope note with the data date ("A sétát is beszámítva, a kiválasztott boltok közül, a … GVH-adatok
	alapján") is in the page's one "Hogyan számoljuk?" disclosure at the bottom, and the ranking below states
	its scope and date (BUILD-BRIEF §8.6); the source line with the date closes the page (§8.2). How the options are chosen is in the "Hogyan számoljuk?" disclosure after the ranking
	(NearbyPrices). Ties are never broken by name.
-->
<script lang="ts">
	import type { ChainSlug, QuoteResponse, StoreId, StoreOut } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import StoreLine from '$lib/components/list/StoreLine.svelte';
	import { formatDistance, formatMoney } from '$lib/format';
	import type { LatLon } from '$lib/geo';
	import { t, tp } from '$lib/i18n';
	import { osmLink, shoppingView } from '$lib/journey/view';
	import { SHARED_NOTE, sharedNoteKeys } from '$lib/list/ranking';
	import { chainLabel, storeAddress } from '$lib/list/stores';
	import JourneyMap from './JourneyMap.svelte';

	interface Props {
		quote: QuoteResponse;
		stores: ReadonlyMap<StoreId, StoreOut>;
		names: ReadonlyMap<ChainSlug, string>;
		origin: LatLon;
		lineNames: ReadonlyMap<string, string>;
		chosenStoreId: StoreId | null;
		checked: ReadonlySet<string>;
		onchoose: (storeId: StoreId) => void;
		ontogglecheck: (ingredientId: string, on: boolean) => void;
	}

	let { quote, stores, names, origin, lineNames, chosenStoreId, checked, onchoose, ontogglecheck }: Props = $props();
	const id = $props.id();

	const view = $derived(shoppingView(quote, stores, origin));
	let showLists = $state(false);

	function nameOf(ingredientId: string): string {
		return lineNames.get(ingredientId) ?? ingredientId;
	}

	function itemNames(ids: readonly string[]): string {
		return ids.map(nameOf).join(', ');
	}

	function storeText(storeId: StoreId, chain: ChainSlug): string {
		const address = storeAddress(stores.get(storeId));
		const label = chainLabel(chain, names);
		return address ? `${label}, ${address}` : label;
	}

	function quotedLine(storeId: StoreId, ingredientId: string) {
		return quote.stores.find((store) => store.store_id === storeId)?.lines.find((line) => line.ingredient_id === ingredientId);
	}

	const others = $derived.by(() => {
		const onRoute = new Set(view?.journey?.stops.map((stop) => stop.storeId) ?? []);
		const out: LatLon[] = [];
		for (const quoted of quote.stores) {
			const info = stores.get(quoted.store_id);
			if (!onRoute.has(quoted.store_id) && info && info.lat !== null && info.lon !== null) {
				out.push({ lat: info.lat, lon: info.lon });
			}
		}
		return out;
	});
</script>

{#if view && view.single}
	{@const single = view.single}
	{@const journey = view.journey}
	<section class="options" aria-labelledby="{id}-title" data-testid="shopping-options">
		<h3 id="{id}-title">{t('journey.title')}</h3>

		{#if view.nowhere.length > 0}
			<p class="notice notice-warning" data-testid="nowhere">
				{tp('journey.nowhere', view.nowhere.length)} <span lang="hu">{itemNames(view.nowhere)}</span>
			</p>
		{/if}

		<div class="cards">
			<article class="card option" aria-labelledby="{id}-single" data-testid="option-single" data-store-id={single.storeId}>
				<h4 id="{id}-single">{t('journey.single_title')}</h4>
				<p class="store">
					<strong>{chainLabel(single.chain, names)}</strong>
					<span class="muted">{storeAddress(stores.get(single.storeId))}</span>
				</p>
				<p class="total">
					{t('journey.total_label')}: <strong data-testid="single-total">{formatMoney(single.total)}</strong>
				</p>
				{#if single.missing.length > 0}
					<p>
						<Badge tone="warning">{tp('journey.single_missing', single.missing.length)}</Badge>
						<span class="small" lang="hu">{itemNames(single.missing)}</span>
					</p>
				{:else}
					<p class="small">{view.nowhere.length > 0 ? t('journey.single_all_available') : t('journey.single_all')}</p>
				{/if}
				<p class="small muted">{t('journey.walk_round', { distance: formatDistance(single.routeKm) })}</p>
				<button
					type="button"
					class="btn"
					class:btn-primary={single.storeId !== chosenStoreId}
					class:btn-secondary={single.storeId === chosenStoreId}
					aria-pressed={single.storeId === chosenStoreId}
					aria-label={t('list.choose_store_named', { store: storeText(single.storeId, single.chain) })}
					onclick={() => onchoose(single.storeId)}>{t('list.choose_store')}</button
				>
			</article>

			{#if journey}
				<article class="card option journey" aria-labelledby="{id}-journey" data-testid="option-journey">
					<h4 id="{id}-journey">{tp('journey.journey_title', journey.stops.length)}</h4>
					<p class="total">
						{t('journey.journey_total_label')}: <strong data-testid="journey-total">{formatMoney(journey.total)}</strong>
					</p>
					{#if journey.moreItems > 0}
						<p><Badge tone="success">{tp('journey.journey_more', journey.moreItems)}</Badge></p>
					{/if}
					{#if journey.saving >= 1}
						<p><Badge tone="success">{t('journey.journey_saving', { saving: formatMoney(journey.saving) })}</Badge></p>
					{/if}
					{#if journey.missing.length > 0}
						<p>
							<Badge tone="warning">{tp('journey.journey_missing', journey.missing.length)}</Badge>
							<span class="small" lang="hu">{itemNames(journey.missing)}</span>
						</p>
					{:else if journey.moreItems > 0}
						<p class="small">{view.nowhere.length > 0 ? t('journey.journey_all_available') : t('journey.journey_all')}</p>
					{/if}
					<p class="small muted" data-testid="journey-walk">
						{journey.extraKm > 0.005
							? t('journey.walk_journey_longer', {
									distance: formatDistance(journey.routeKm),
									extra: formatDistance(journey.extraKm)
								})
							: t('journey.walk_journey_shorter', { distance: formatDistance(journey.routeKm) })}
					</p>

					<JourneyMap
						{origin}
						stops={journey.stops.map((stop) => ({
							point: stop.point,
							number: stop.number,
							label: storeText(stop.storeId, stop.chain)
						}))}
						{others}
					/>

					<h5>{t('journey.stops_title')}</h5>
					<ol class="stops" data-testid="journey-stops">
						{#each journey.stops as stop (stop.storeId)}
							<li class="stop" data-store-id={stop.storeId}>
								<span class="stop-number" aria-hidden="true">{stop.number}</span>
								<div class="stop-body">
									<p class="stop-name">
										<strong>{chainLabel(stop.chain, names)}</strong>
										<span class="muted">{storeAddress(stores.get(stop.storeId))}</span>
									</p>
									<p class="small muted">
										{stop.number === 1
											? t('journey.leg_first', { distance: formatDistance(stop.legKm) })
											: t('journey.leg_next', { distance: formatDistance(stop.legKm) })},
										{tp('journey.stop_items', stop.items.length, { subtotal: formatMoney(stop.subtotal) })}
									</p>
									<p class="small" lang="hu">{itemNames(stop.items)}</p>
									<a
										class="map-link small"
										href={osmLink(stop.point)}
										target="_blank"
										rel="noopener noreferrer"
										aria-label={t('journey.open_map_named', { store: storeText(stop.storeId, stop.chain) })}
										>{t('journey.open_map')}</a
									>
								</div>
							</li>
						{/each}
					</ol>
					<p class="small muted">{t('journey.leg_back', { distance: formatDistance(journey.returnKm) })}</p>

					<button
						type="button"
						class="btn btn-secondary"
						aria-expanded={showLists}
						aria-controls="{id}-lists"
						onclick={() => (showLists = !showLists)}
						>{showLists ? t('journey.hide_lists') : t('journey.show_lists')}</button
					>
				</article>
			{:else if view.notWorth}
				<p class="notice notice-info not-worth" data-testid="no-journey">
					{view.notWorth.saving >= 1
						? t('journey.no_journey_saving', { saving: formatMoney(view.notWorth.saving) })
						: t('journey.no_journey_cheaper')}
				</p>
			{/if}
		</div>

		{#if journey && showLists}
			<section id="{id}-lists" class="lists" aria-labelledby="{id}-lists-title" data-testid="journey-lists">
				<h4 id="{id}-lists-title">{t('journey.lists_title')}</h4>
				{#each journey.stops as stop (stop.storeId)}
					{@const lines = stop.items.flatMap((ingredientId) => quotedLine(stop.storeId, ingredientId) ?? [])}
					{@const shared = sharedNoteKeys(lines)}
					<div class="card stop-list">
						<h5>
							{t('journey.stop_heading', { number: stop.number, store: storeText(stop.storeId, stop.chain) })}
						</h5>
						<p class="small muted">{tp('journey.stop_items', stop.items.length, { subtotal: formatMoney(stop.subtotal) })}</p>
						{#if shared.length > 0}
							<p class="small muted" data-testid="store-notes">{shared.map((key) => t(SHARED_NOTE[key])).join(' ')}</p>
						{/if}
						<ul class="lines">
							{#each lines as line (line.ingredient_id)}
								<StoreLine {line} name={nameOf(line.ingredient_id)} checked={checked.has(line.ingredient_id)} {ontogglecheck} omit={shared} />
							{/each}
						</ul>
					</div>
				{/each}
			</section>
		{/if}

	</section>
{/if}

<style>
	.options > :global(* + *) {
		margin-top: var(--space-3);
	}

	.cards {
		display: grid;
		gap: var(--space-3);
	}

	@media (min-width: 48rem) {
		.cards {
			grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
			align-items: start;
		}
	}

	.option > :global(*) {
		margin: 0 0 var(--space-2);
	}

	.option > :global(:last-child) {
		margin-bottom: 0;
	}

	.option h4 {
		font-size: var(--font-size-lg);
	}

	.store {
		display: flex;
		flex-direction: column;
	}

	.total strong {
		font-size: var(--font-size-lg);
	}

	h5 {
		font-size: var(--font-size-base);
		margin: var(--space-3) 0 var(--space-2);
	}

	.stops {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: var(--space-3);
	}

	.stop {
		display: flex;
		gap: var(--space-3);
		align-items: flex-start;
	}

	.stop-number {
		flex: none;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		background: var(--color-primary);
		color: var(--color-on-primary);
		font-weight: 700;
	}

	.stop-body > :global(*) {
		margin: 0 0 var(--space-1);
	}

	.stop-name {
		display: flex;
		flex-direction: column;
	}

	.map-link {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}

	.lists > :global(* + *) {
		margin-top: var(--space-3);
	}

	.stop-list h5 {
		margin-top: 0;
	}

	.lines {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.lines > :global(li + li) {
		border-top: 1px solid var(--color-border-subtle);
	}
</style>
