<!--
	Recipe detail. PLACEHOLDER for the recipes feature agent.
	TODO(recipes agent):
	- GET /api/recipes/{id} (page.params.id); a 404 ApiError (code not_found) shows <ErrorState>;
	- lines with pantry=true: <Badge kind="pantry" />; chain costs with <Attribution dataDate=… />;
	- nutrition is null until composition data exists: hide the section (no health claims, BUILD-BRIEF §8.7).
-->
<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { t } from '$lib/i18n';
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('recipes.detail_title') })}</title>
</svelte:head>

<p><a href="/receptek">{t('recipes.back')}</a></p>
<h1>{t('recipes.detail_title')}</h1>
<EmptyState message={t('recipes.detail_placeholder')} />
