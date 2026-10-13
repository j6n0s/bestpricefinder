<!-- Sources and privacy: attribution, licences, and exactly what stays on the device and what is sent. -->
<script lang="ts">
	import Attribution from '$lib/components/Attribution.svelte';
	import Disclaimer from '$lib/components/Disclaimer.svelte';
	import { formatDate, formatMonth } from '$lib/format';
	import { t } from '$lib/i18n';
	import { getMeta } from '$lib/meta.svelte';
	import { GVH_URL, KSH_LICENSE_URL, safeKshUrl } from '$lib/sources';

	const meta = getMeta();
	const dataDate = $derived(meta.data?.data_date ?? null);
	const kshPeriod = $derived(formatMonth(meta.data?.ksh_period ?? null));
	const kshUrl = $derived(safeKshUrl(meta.data?.attribution.ksh.url));
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('sources.title') })}</title>
</svelte:head>

<h1>{t('sources.title')}</h1>

<section class="card" aria-labelledby="src-prices">
	<h2 id="src-prices">{t('sources.prices_title')}</h2>
	<p>{t('sources.prices_text')}</p>
	{#if dataDate}
		<p>{t('sources.prices_date', { date: formatDate(dataDate) })}</p>
	{/if}
	<p>{t('sources.prices_scope')}</p>
	<p>
		<a href={GVH_URL} rel="noopener noreferrer" target="_blank">{t('sources.gvh_link')}</a>
	</p>
	<Attribution {dataDate} showDisclaimer={false} />
</section>

<section class="card" aria-labelledby="src-ksh">
	<h2 id="src-ksh">{t('sources.ksh_title')}</h2>
	<p>{t('sources.ksh_text')}</p>
	<p>{t('sources.ksh_license')}</p>
	{#if kshPeriod}
		<p>{t('sources.ksh_period', { period: kshPeriod })}</p>
	{/if}
	<ul class="links">
		<li>
			<a href={kshUrl} rel="noopener noreferrer" target="_blank">
				{kshPeriod ? t('core.attribution_ksh_period', { period: kshPeriod }) : t('core.attribution_ksh')}
			</a>
			({t('sources.ksh_link')})
		</li>
		<li><a href={KSH_LICENSE_URL} rel="noopener noreferrer" target="_blank">{t('sources.ksh_license_link')}</a></li>
	</ul>
</section>

<section class="card" aria-labelledby="src-nutrition">
	<h2 id="src-nutrition">{t('sources.nutrition_title')}</h2>
	<p>{t('sources.nutrition_text')}</p>
</section>

<section class="card" aria-labelledby="src-recipes">
	<h2 id="src-recipes">{t('sources.recipes_title')}</h2>
	<p>{t('sources.recipes_text')}</p>
</section>

<section class="card" aria-labelledby="src-privacy">
	<h2 id="src-privacy">{t('sources.privacy_title')}</h2>

	<h3>{t('sources.device_title')}</h3>
	<ul>
		<li>{t('sources.device_plan')}</li>
		<li>{t('sources.device_household')}</li>
		<li>{t('sources.device_pantry')}</li>
		<li>{t('sources.device_location')}</li>
		<li>{t('sources.device_language')}</li>
	</ul>
	<p>{t('sources.device_cache')}</p>

	<h3>{t('sources.server_title')}</h3>
	<ul>
		<li>{t('sources.server_recipes')}</li>
		<li>{t('sources.server_ingredients')}</li>
		<li>{t('sources.server_stores')}</li>
		<li>{t('sources.server_plan')}</li>
	</ul>
	<p><strong>{t('sources.server_never')}</strong></p>

	<h3>{t('sources.cookies_title')}</h3>
	<p>{t('sources.cookies_text')}</p>
	<p>
		{t('sources.delete_text')}
		<a href="/beallitasok">{t('sources.delete_link')}</a>
	</p>
</section>

<section class="card" aria-labelledby="src-contact">
	<h2 id="src-contact">{t('sources.contact_title')}</h2>
	<!-- TODO(founder): contact address / impresszum before any public release (BUILD-BRIEF §8.10). -->
	<p>{t('sources.contact_text')}</p>
</section>

<section class="card" aria-labelledby="src-disclaimer">
	<h2 id="src-disclaimer">{t('sources.disclaimer_title')}</h2>
	<Disclaimer />
</section>

<style>
	section + section {
		margin-top: var(--space-4);
	}

	h3 {
		margin-top: var(--space-4);
	}

	ul {
		padding-left: var(--space-5);
	}

	.links a {
		display: inline-block;
		padding: var(--space-2) 0;
	}
</style>
