<!--
	Recipe list ("Receptek"). PLACEHOLDER for the recipes feature agent.
	TODO(recipes agent):
	- GET /api/recipes (slot/tag/q filters) through $lib/api/client;
	- <Badge kind="untested" /> for recipes with tested === false, <Badge kind="no_price" /> when
	  cost_per_serving_from is null;
	- the per-serving price is chain-typical: show <Attribution dataDate={response.data_date} /> on the page.
-->
<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { t } from '$lib/i18n';
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('recipes.title') })}</title>
</svelte:head>

<h1>{t('recipes.title')}</h1>
<EmptyState message={t('recipes.placeholder')} />
