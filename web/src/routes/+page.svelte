<!--
	Home: the title and the three ways in (plan, recipes, cart). On the first visit it also asks which foods to
	leave out ("Mit nem eszel?"), with the same controls as Settings; the choices are saved on this device as
	they are made (diet preferences are health data, BUILD-BRIEF §8.9). "Mentés" closes the question for good
	(StoredState.preferencesAsked) and points to Settings, where they can be changed. No health or price claims.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import ExclusionSettings from '$lib/components/settings/ExclusionSettings.svelte';
	import { t } from '$lib/i18n';
	import { load, onExternalChange, update } from '$lib/storage';

	let asked = $state(load().preferencesAsked);
	let justSaved = $state(false);
	let savedNote = $state<HTMLParagraphElement>();

	onMount(() =>
		onExternalChange((next) => {
			asked = next.preferencesAsked;
		})
	);

	async function savePreferences(): Promise<void> {
		asked = update({ preferencesAsked: true }).preferencesAsked;
		justSaved = true;
		await tick();
		savedNote?.focus();
	}
</script>

<svelte:head>
	<title>{t('core.app_name')}</title>
</svelte:head>

<section class="stack">
	<h1>{t('core.home_title')}</h1>

	{#if !asked}
		<section class="card stack" aria-labelledby="home-prefs" data-testid="home-preferences">
			<h2 id="home-prefs">{t('core.home_prefs_title')}</h2>
			<ExclusionSettings />
			<div class="btn-row">
				<button type="button" class="btn btn-primary" onclick={savePreferences}>{t('core.home_prefs_save')}</button>
			</div>
		</section>
	{:else if justSaved}
		<p class="notice notice-success" role="status" tabindex="-1" bind:this={savedNote} data-testid="home-preferences-saved">
			{t('core.home_prefs_saved')}
			<a href="/beallitasok#set-exclusions">{t('core.home_prefs_edit')}</a>
		</p>
	{/if}

	<div class="btn-row">
		<a class="btn btn-primary" href="/terv">{t('core.home_cta_plan')}</a>
		<a class="btn btn-secondary" href="/receptek">{t('core.home_cta_recipes')}</a>
		<a class="btn btn-secondary" href="/kosar">{t('core.home_cta_cart')}</a>
	</div>
</section>
