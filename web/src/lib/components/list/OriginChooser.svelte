<!--
	Where the nearby stores are measured from (BUILD-BRIEF §8.8). The card's title says what the position is
	for and one line beside the button says it stays on the device (with a link to the privacy page); the
	browser is asked for a position only when the user presses "Saját helyzetem használata" (low accuracy, 10 s
	timeout, rounded to about 100 m, kept on this device; only store ids are ever sent). The Budapest district
	picker is the alternative. The outcome is reported through `onlocation`; the page saves it with $lib/storage.
	Every new location is built from the STORED one (load()), not from the `location` prop: another tab may have
	revoked the position or deleted everything since this page read it, and that must never be written back.
-->
<script lang="ts">
	import { tick } from 'svelte';
	import DistrictPicker from '$lib/components/DistrictPicker.svelte';
	import LocationPrivacy from '$lib/components/LocationPrivacy.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, type PlainKey } from '$lib/i18n';
	import { locateForList } from '$lib/list/locate';
	import {
		declinedLocation,
		districtLocation,
		grantedLocation,
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
</script>

<section class="card origin" aria-labelledby="{id}-title">
	<h3 id="{id}-title" tabindex="-1" bind:this={heading}>{t('list.origin_title')}</h3>

	<div class="locate">
		{#if pending}
			<Spinner label={t('core.location_pending')} showLabel />
		{:else}
			<button type="button" class="btn btn-primary" bind:this={locateButton} onclick={useMyLocation}>
				{t('list.use_my_location')}
			</button>
		{/if}
		<LocationPrivacy />
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
		margin: var(--space-2) 0 0;
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
</style>
