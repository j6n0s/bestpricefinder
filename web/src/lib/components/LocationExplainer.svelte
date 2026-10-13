<!--
	Location consent flow (BUILD-BRIEF §8.8): the browser is asked for a position ONLY after this explanation
	and an explicit "OK". The position is approximate (enableHighAccuracy: false), rounded to about 100 m,
	stored on this device only and never sent to the server. Choosing a district is offered as the alternative.

	The component saves the outcome through the storage module and reports the new StoredLocation.
-->
<script lang="ts">
	import { tick } from 'svelte';
	import { t, type PlainKey } from '$lib/i18n';
	import { declinedLocation, grantedLocation, requestApproxPosition, type LocateFailure } from '$lib/location';
	import { load, update, type StoredLocation } from '$lib/storage';
	import Spinner from './Spinner.svelte';

	interface Props {
		onchange?: (location: StoredLocation) => void;
	}

	let { onchange }: Props = $props();
	const id = $props.id();

	type Phase = 'closed' | 'explain' | 'pending' | 'done' | 'failed';
	let phase = $state<Phase>('closed');
	let failure = $state<LocateFailure | null>(null);
	let openButton = $state<HTMLButtonElement>();
	let heading = $state<HTMLHeadingElement>();

	const FAILURE_KEYS: Record<LocateFailure, PlainKey> = {
		denied: 'core.location_error_denied',
		unavailable: 'core.location_error_unavailable',
		timeout: 'core.location_error_timeout',
		unsupported: 'core.location_error_unsupported',
		insecure: 'core.location_error_insecure'
	};

	async function open(): Promise<void> {
		failure = null;
		phase = 'explain';
		await tick();
		heading?.focus();
	}

	async function finish(next: Phase): Promise<void> {
		phase = next;
		await tick();
		openButton?.focus();
	}

	function cancel(): void {
		void finish('closed');
	}

	async function allow(): Promise<void> {
		phase = 'pending';
		const result = await requestApproxPosition();
		const previous = load().location;
		if (result.ok) {
			const next = update({ location: grantedLocation(previous, result.position) }).location;
			onchange?.(next);
			await finish('done');
			return;
		}
		failure = result.reason;
		if (result.reason === 'denied') {
			onchange?.(update({ location: declinedLocation(previous) }).location);
		}
		await finish('failed');
	}
</script>

<div class="locator">
	{#if phase === 'explain'}
		<section class="card explain" aria-labelledby="{id}-title">
			<h3 id="{id}-title" tabindex="-1" bind:this={heading}>{t('core.location_title')}</h3>
			<p>{t('core.location_why')}</p>
			<p>{t('core.location_device_only')}</p>
			<p>{t('core.location_approx')}</p>
			<p class="muted">{t('core.location_alternative')}</p>
			<div class="btn-row">
				<button type="button" class="btn btn-primary" onclick={allow}>{t('core.location_allow')}</button>
				<button type="button" class="btn btn-secondary" onclick={cancel}>{t('core.location_cancel')}</button>
			</div>
		</section>
	{:else if phase === 'pending'}
		<Spinner label={t('core.location_pending')} showLabel />
	{:else}
		<button type="button" class="btn btn-secondary" bind:this={openButton} onclick={open}>
			{t('core.location_open')}
		</button>
	{/if}

	<div role="status" class="feedback">
		{#if phase === 'done'}
			<p class="notice notice-success">{t('core.location_done')}</p>
		{:else if phase === 'failed' && failure}
			<p class="notice notice-warning">{t(FAILURE_KEYS[failure])}</p>
		{/if}
	</div>
</div>

<style>
	/* The status region is always rendered (never display:none) so screen readers announce its updates. */
	.feedback {
		margin-top: var(--space-3);
	}

	.feedback:empty {
		margin-top: 0;
	}

	h3:focus {
		outline: none;
	}

	h3:focus-visible {
		outline: var(--focus-ring);
	}

	.feedback p {
		margin: 0;
	}
</style>
