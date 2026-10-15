<!--
	Settings. Everything here is personal data and is saved immediately, on this device only, through
	$lib/storage (never sent to the server). Every change starts from the stored state (load()), and the page
	reloads it when another tab changes or deletes it (onExternalChange), so a stale tab never writes deleted
	data back.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import DistrictPicker from '$lib/components/DistrictPicker.svelte';
	import LocationExplainer from '$lib/components/LocationExplainer.svelte';
	import MapPicker from '$lib/components/MapPicker.svelte';
	import ExclusionSettings from '$lib/components/settings/ExclusionSettings.svelte';
	import PantrySettings from '$lib/components/settings/PantrySettings.svelte';
	import { districtById } from '$lib/districts';
	import { formatDateTime, formatDistance, formatNumber } from '$lib/format';
	import { i18n, reloadLanguage, setLanguage, t, tp, type Lang, type PlainKey } from '$lib/i18n';
	import type { LatLon } from '$lib/geo';
	import { clearedMapLocation, districtLocation, mapLocation, revokedLocation } from '$lib/location';
	import { reloadTheme, setTheme, theme } from '$lib/theme.svelte';

	const THEME_LABELS: Readonly<Record<Theme, PlainKey>> = {
		system: 'settings.theme_system',
		light: 'settings.theme_light',
		dark: 'settings.theme_dark'
	};
	import { resetRecipeFilters } from '$lib/plan/filters.svelte';
	import {
		clearAll,
		isPersistent,
		load,
		onExternalChange,
		update,
		PEOPLE_MAX,
		PEOPLE_MIN,
		RADIUS_MAX_KM,
		RADIUS_MIN_KM,
		RADIUS_STEP_KM,
		THEMES,
		type StatePatch,
		type StoredLocation,
		type StoredState,
		type Theme
	} from '$lib/storage';

	let settings = $state<StoredState>(load());
	let persistent = $state(isPersistent());
	let notice = $state<'revoked' | 'cleared' | 'cleared_session' | null>(null);
	let resets = $state(0);
	let dialog = $state<HTMLDialogElement>();
	let cancelButton = $state<HTMLButtonElement>();
	let locateButton = $state<HTMLButtonElement>();
	// The map disclosure starts open only when the map point is the origin already.
	let mapOpen = $state(load().location.source === 'map');

	onMount(() =>
		onExternalChange((next) => {
			settings = next;
			persistent = isPersistent();
		})
	);

	const loc = $derived(settings.location);
	const district = $derived(districtById(loc.districtId));

	function save(patch: StatePatch): void {
		settings = update(patch);
		persistent = isPersistent();
		notice = null;
	}

	function changePeople(delta: number): void {
		const next = load().people + delta;
		if (next < PEOPLE_MIN || next > PEOPLE_MAX) return;
		save({ people: next });
	}

	function changeRadius(event: Event & { currentTarget: HTMLInputElement }): void {
		const value = Number(event.currentTarget.value);
		if (Number.isFinite(value)) save({ radiusKm: value });
	}

	function chooseLanguage(lang: Lang): void {
		setLanguage(lang);
		settings = load();
		persistent = isPersistent();
	}

	function chooseTheme(choice: Theme): void {
		setTheme(choice);
		settings = load();
		persistent = isPersistent();
	}

	function locationChanged(next: StoredLocation): void {
		settings = { ...settings, location: next };
		persistent = isPersistent();
		notice = null;
	}

	async function revoke(): Promise<void> {
		save({ location: revokedLocation(load().location) });
		notice = 'revoked';
		// The revoke button is gone: continue at "Helyzet használata…", never at <body>.
		await tick();
		locateButton?.focus();
	}

	function chooseDistrict(districtId: string | null): void {
		save({ location: districtLocation(load().location, districtId) });
	}

	function pickPoint(point: LatLon): void {
		save({ location: mapLocation(load().location, point) });
	}

	function clearPoint(): void {
		save({ location: clearedMapLocation(load().location) });
	}

	/** The stored map point becomes the origin again (after a district or the device position was chosen). */
	function useMapPoint(): void {
		const current = load().location;
		if (current.manual) save({ location: { ...current, source: 'map' } });
	}

	async function askClear(): Promise<void> {
		dialog?.showModal();
		await tick();
		cancelButton?.focus();
	}

	function confirmClear(): void {
		// clearAll resets the in-memory copy too; false = the stored copy could not be reached or deleted.
		const removed = clearAll();
		// Other personal data held in memory for this tab: the language, the theme and the recipe filters (a
		// filter such as "húsmentes" is a diet preference).
		reloadLanguage();
		reloadTheme();
		resetRecipeFilters();
		settings = load();
		persistent = isPersistent();
		resets += 1;
		dialog?.close();
		notice = removed ? 'cleared' : 'cleared_session';
	}
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('settings.title') })}</title>
</svelte:head>

<h1>{t('settings.title')}</h1>

{#if !persistent}
	<p class="notice notice-warning" role="status">{t('settings.storage_unavailable')}</p>
{/if}

<div role="status" class="announce">
	{#if notice === 'cleared'}
		<p class="notice notice-success">{t('settings.clear_done')}</p>
	{:else if notice === 'cleared_session'}
		<p class="notice notice-warning">{t('settings.clear_partial')}</p>
	{:else if notice === 'revoked'}
		<p class="notice notice-success">{t('settings.location_revoked')}</p>
	{/if}
</div>

<section class="card" aria-labelledby="set-household">
	<h2 id="set-household">{t('settings.household_title')}</h2>

	<div class="field">
		<span class="field-label" id="people-label">{t('settings.people_label')}</span>
		<div class="stepper" role="group" aria-labelledby="people-label">
			<button
				type="button"
				class="btn btn-secondary"
				aria-label={t('settings.people_decrease')}
				aria-disabled={settings.people <= PEOPLE_MIN}
				onclick={() => changePeople(-1)}>−</button
			>
			<output aria-live="polite" data-testid="people-value">{tp('settings.people_value', settings.people)}</output>
			<button
				type="button"
				class="btn btn-secondary"
				aria-label={t('settings.people_increase')}
				aria-disabled={settings.people >= PEOPLE_MAX}
				onclick={() => changePeople(1)}>+</button
			>
		</div>
	</div>

	<fieldset class="choice-group">
		<legend>{t('settings.slots_label')}</legend>
		<label class="choice">
			<input type="radio" name="slots" value="3" checked={settings.slots === 3} onchange={() => save({ slots: 3 })} />
			<span>{t('settings.slots_3')}</span>
		</label>
		<label class="choice">
			<input type="radio" name="slots" value="5" checked={settings.slots === 5} onchange={() => save({ slots: 5 })} />
			<span>{t('settings.slots_5')}</span>
		</label>
	</fieldset>
</section>

<section class="card" aria-labelledby="set-stores">
	<h2 id="set-stores">{t('settings.stores_title')}</h2>
	<div class="field">
		<label for="radius">{t('settings.radius_label')}: <output for="radius">{formatDistance(settings.radiusKm)}</output></label>
		<input
			id="radius"
			class="range"
			type="range"
			min={RADIUS_MIN_KM}
			max={RADIUS_MAX_KM}
			step={RADIUS_STEP_KM}
			value={settings.radiusKm}
			aria-valuetext={formatDistance(settings.radiusKm)}
			aria-describedby="radius-hint"
			oninput={changeRadius}
		/>
		<p id="radius-hint" class="muted small">
			{t('settings.radius_hint', { min: formatNumber(RADIUS_MIN_KM), max: formatNumber(RADIUS_MAX_KM) })}
		</p>
	</div>
</section>

<section class="card" aria-labelledby="set-language">
	<h2 id="set-language">{t('settings.language_title')}</h2>
	<fieldset class="choice-group">
		<legend class="visually-hidden">{t('settings.language_title')}</legend>
		<label class="choice" lang="hu">
			<input type="radio" name="language" value="hu" checked={i18n.lang === 'hu'} onchange={() => chooseLanguage('hu')} />
			<span>{t('settings.language_hu')}</span>
		</label>
		<label class="choice" lang="en">
			<input type="radio" name="language" value="en" checked={i18n.lang === 'en'} onchange={() => chooseLanguage('en')} />
			<span>{t('settings.language_en')}</span>
		</label>
	</fieldset>
</section>

<section class="card" aria-labelledby="set-theme">
	<h2 id="set-theme">{t('settings.theme_title')}</h2>
	<fieldset class="choice-group">
		<legend class="visually-hidden">{t('settings.theme_title')}</legend>
		{#each THEMES as choice (choice)}
			<label class="choice">
				<input type="radio" name="theme" value={choice} checked={theme.preference === choice} onchange={() => chooseTheme(choice)} />
				<span>{t(THEME_LABELS[choice])}</span>
			</label>
		{/each}
	</fieldset>
</section>

<section class="card" aria-labelledby="set-location">
	<h2 id="set-location">{t('settings.location_title')}</h2>
	<p data-testid="location-status">
		<strong>{t('settings.location_status_label')}:</strong>
		{#if loc.consent === 'granted' && loc.approx}
			{t('settings.location_status_granted', { time: formatDateTime(loc.approx.at) })}
		{:else if loc.consent === 'declined'}
			{t('settings.location_status_declined')}
		{:else}
			{t('settings.location_status_unset')}
		{/if}
	</p>

	<div class="btn-row">
		{#key resets}
			<LocationExplainer onchange={locationChanged} bind:openButton={locateButton} />
		{/key}
		{#if loc.consent === 'granted'}
			<button type="button" class="btn btn-secondary" onclick={revoke}>{t('settings.location_revoke')}</button>
		{/if}
	</div>

	<DistrictPicker value={loc.districtId} onchange={chooseDistrict} />

	<details class="map" bind:open={mapOpen} data-testid="settings-map">
		<summary class="disclosure">{t('core.map_pick_open')}</summary>
		{#key resets}
			{#if mapOpen}
				<MapPicker point={loc.manual} onpick={pickPoint} onclear={clearPoint} />
			{/if}
		{/key}
	</details>

	<p data-testid="location-source">
		{t('settings.location_source_label')}
		{#if loc.source === 'device'}
			{t('settings.location_source_device')}
		{:else if loc.source === 'district' && district}
			{t('core.district_name', { roman: district.roman })}.
		{:else if loc.source === 'map' && loc.manual}
			{t('settings.location_source_map')}
		{:else}
			{t('settings.location_source_none')}
		{/if}
	</p>
	<div class="btn-row">
		{#if loc.source !== 'district' && district}
			<button type="button" class="btn btn-secondary" onclick={() => chooseDistrict(district.id)}>
				{t('settings.location_use_district')}
			</button>
		{/if}
		{#if loc.source !== 'map' && loc.manual}
			<button type="button" class="btn btn-secondary" onclick={useMapPoint}>{t('settings.location_use_map')}</button>
		{/if}
	</div>
</section>

<section class="card" aria-labelledby="set-pantry">
	<h2 id="set-pantry">{t('settings.pantry_title')}</h2>
	{#key resets}
		<PantrySettings />
	{/key}
</section>

<section class="card" aria-labelledby="set-exclusions">
	<h2 id="set-exclusions">{t('settings.exclusions_title')}</h2>
	{#key resets}
		<ExclusionSettings />
	{/key}
</section>

<section class="card" aria-labelledby="set-clear">
	<h2 id="set-clear">{t('settings.clear_title')}</h2>
	<button type="button" class="btn btn-danger" onclick={askClear}>{t('settings.clear_button')}</button>
</section>

<dialog bind:this={dialog} class="dialog" aria-labelledby="clear-title" aria-describedby="clear-text">
	<h2 id="clear-title">{t('settings.clear_confirm_title')}</h2>
	<p id="clear-text">{t('settings.clear_confirm_text')}</p>
	<div class="btn-row">
		<button type="button" class="btn btn-secondary" bind:this={cancelButton} onclick={() => dialog?.close()}>
			{t('settings.clear_confirm_no')}
		</button>
		<button type="button" class="btn btn-danger" onclick={confirmClear}>{t('settings.clear_confirm_yes')}</button>
	</div>
</dialog>

<style>
	section + section {
		margin-top: var(--space-4);
	}

	section > :global(* + *) {
		margin-top: var(--space-4);
	}

	.announce > :global(p) {
		margin: var(--space-3) 0;
	}

	.stepper {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}

	.stepper .btn {
		font-size: var(--font-size-xl);
		padding: 0;
		width: var(--tap);
	}

	.stepper .btn[aria-disabled='true'] {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.stepper output {
		/* Pixels: room for "12 fő" at every text size without pushing "+" off a narrow screen at 200 %. */
		min-width: 96px;
		text-align: center;
		font-weight: 600;
	}

	.range {
		width: 100%;
		min-height: var(--tap);
		margin: 0;
		accent-color: var(--color-primary);
	}

	.dialog {
		width: min(28rem, calc(100vw - 2rem));
		max-height: calc(100dvh - 2rem);
		overflow-y: auto;
		padding: var(--space-5);
		background: var(--color-surface);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
	}

	.dialog::backdrop {
		background: rgb(0 0 0 / 0.55);
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
