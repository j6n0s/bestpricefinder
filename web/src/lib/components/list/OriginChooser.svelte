<!--
	Where the nearby stores are measured from (BUILD-BRIEF §8.8). The card's title says what the position is
	for and one line before the button says it stays on the device (with a link to the privacy page); the
	browser is asked for a position only when the user presses "Saját helyzetem használata" (low accuracy, 10 s
	timeout, rounded to about 100 m, kept on this device; only store ids are ever sent). The Budapest district
	picker and a point picked on the on-device map (MapPicker, behind a closed disclosure) are the alternatives.
	The outcome is reported through `onlocation`; the page saves it with $lib/storage.
	Every new location is built from the STORED one (load()), not from the `location` prop: another tab may have
	revoked the position or deleted everything since this page read it, and that must never be written back.
-->
<script lang="ts">
	import { tick, untrack } from 'svelte';
	import DistrictPicker from '$lib/components/DistrictPicker.svelte';
	import LocationPrivacy from '$lib/components/LocationPrivacy.svelte';
	import MapPicker from '$lib/components/MapPicker.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import type { LatLon } from '$lib/geo';
	import { t, type PlainKey } from '$lib/i18n';
	import { locateForList } from '$lib/list/locate';
	import {
		clearedMapLocation,
		declinedLocation,
		districtLocation,
		grantedLocation,
		mapLocation,
		type LocateFailure
	} from '$lib/location';
	import { load, type StoredLocation } from '$lib/storage';

	interface Props {
		location: StoredLocation;
		/** A usable starting point exists (shows the "Kész" button). */
		hasOrigin: boolean;
		onlocation: (next: StoredLocation) => void;
		/** The device position was stored, or the user pressed "Kész". */
		ondone: () => void;
		/** Bound by the parent to move focus here when the card opens. */
		heading?: HTMLHeadingElement;
	}

	let { location, hasOrigin, onlocation, ondone, heading = $bindable() }: Props = $props();
	const id = $props.id();

	let pending = $state(false);
	let failure = $state<LocateFailure | null>(null);
	let locateButton = $state<HTMLButtonElement>();
	// The map disclosure starts open only when the map point is the origin already.
	let mapOpen = $state(untrack(() => location.source === 'map'));

	const FAILURE_KEYS: Record<LocateFailure, PlainKey> = {
		denied: 'core.location_error_denied',
		unavailable: 'core.location_error_unavailable',
		timeout: 'core.location_error_timeout',
		unsupported: 'core.location_error_unsupported',
		insecure: 'core.location_error_insecure'
	};

	async function useMyLocation(): Promise<void> {
		if (pending) return;
		failure = null;
		pending = true;
		const result = await locateForList();
		pending = false;
		if (result.ok) {
			onlocation(grantedLocation(load().location, result.position));
			ondone();
			return;
		}
		failure = result.reason;
		if (result.reason === 'denied') onlocation(declinedLocation(load().location));
		await tick();
		locateButton?.focus();
	}

	function chooseDistrict(districtId: string | null): void {
		failure = null;
		onlocation(districtLocation(load().location, districtId));
	}

	function pickPoint(point: LatLon): void {
		failure = null;
		onlocation(mapLocation(load().location, point));
	}

	function clearPoint(): void {
		onlocation(clearedMapLocation(load().location));
	}
</script>

<section class="card origin" aria-labelledby="{id}-title">
	<h3 id="{id}-title" tabindex="-1" bind:this={heading}>{t('list.origin_title')}</h3>

	<div class="locate">
		<LocationPrivacy />
		{#if pending}
			<Spinner label={t('core.location_pending')} showLabel />
		{:else}
			<button type="button" class="btn btn-primary" bind:this={locateButton} onclick={useMyLocation}>
				{t('list.use_my_location')}
			</button>
		{/if}
	</div>

	<div role="status" class="feedback">
		{#if failure}
			<p class="notice notice-warning">{t(FAILURE_KEYS[failure])}</p>
		{/if}
	</div>

	<div class="or">
		<DistrictPicker
			label={t('list.or_district')}
			value={location.source === 'district' ? location.districtId : null}
			onchange={chooseDistrict}
		/>
	</div>

	<details class="map" bind:open={mapOpen} data-testid="origin-map">
		<summary class="disclosure">{t('core.map_pick_open')}</summary>
		<!-- Mounted only while open: the picker loads the store list, which the closed chooser never needs. -->
		{#if mapOpen}
			<MapPicker point={location.manual} onpick={pickPoint} onclear={clearPoint} />
		{/if}
	</details>

	{#if hasOrigin}
		<div class="btn-row done">
			<button type="button" class="btn btn-secondary" onclick={ondone}>{t('list.origin_done')}</button>
		</div>
	{/if}
</section>

<style>
	h3:focus {
		outline: none;
	}

	h3:focus-visible {
		outline: var(--focus-ring);
	}

	.locate {
		margin: var(--space-3) 0 var(--space-2);
	}

	.locate :global([data-testid='location-privacy']) {
		margin: 0 0 var(--space-2);
	}

	.feedback p {
		margin: 0 0 var(--space-3);
	}

	.or {
		margin-top: var(--space-4);
	}

	.done {
		margin-top: var(--space-4);
	}

	.map {
		margin-top: var(--space-3);
	}

	.map summary {
		display: flex;
		align-items: center;
		min-height: var(--tap);
		cursor: pointer;
		font-weight: 600;
	}
</style>
