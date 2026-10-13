<!--
	Where the nearby stores are measured from (BUILD-BRIEF §8.8). The explanation comes first; the browser is
	asked for a position only when the user presses "Saját helyzetem használata" (low accuracy, 10 s timeout,
	rounded to about 100 m, kept on this device; only store ids are ever sent). The Budapest district picker
	is the alternative. The outcome is reported through `onlocation`; the page saves it with $lib/storage.
-->
<script lang="ts">
	import { tick } from 'svelte';
	import DistrictPicker from '$lib/components/DistrictPicker.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { t, type PlainKey } from '$lib/i18n';
	import { locateForList } from '$lib/list/locate';
	import {
		declinedLocation,
		districtLocation,
		grantedLocation,
		type LocateFailure
	} from '$lib/location';
	import type { StoredLocation } from '$lib/storage';

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
			onlocation(grantedLocation(location, result.position));
			ondone();
			return;
		}
		failure = result.reason;
		if (result.reason === 'denied') onlocation(declinedLocation(location));
		await tick();
		locateButton?.focus();
	}

	function chooseDistrict(districtId: string | null): void {
		failure = null;
		onlocation(districtLocation(location, districtId));
	}
</script>

<section class="card origin" aria-labelledby="{id}-title">
	<h3 id="{id}-title" tabindex="-1" bind:this={heading}>{t('list.origin_title')}</h3>
	<p>{t('list.nearby_why')}</p>
	<p>{t('core.location_device_only')}</p>
	<p class="small muted">{t('core.location_approx')}</p>

	<div class="locate">
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

	<p class="or">{t('list.or_district')}</p>
	<DistrictPicker value={location.source === 'district' ? location.districtId : null} onchange={chooseDistrict} />

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
		margin: var(--space-4) 0 var(--space-2);
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
