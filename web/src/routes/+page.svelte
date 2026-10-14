<!-- Home: the title and the three ways in (plan, recipes, cart). No health or price claims. -->
<script lang="ts">
	import { t } from '$lib/i18n';
</script>

<svelte:head>
	<title>{t('core.app_name')}</title>
</svelte:head>

<section class="stack">
	<h1>{t('core.home_title')}</h1>
	<div class="btn-row">
		<a class="btn btn-primary" href="/terv">{t('core.home_cta_plan')}</a>
		<a class="btn btn-secondary" href="/receptek">{t('core.home_cta_recipes')}</a>
		<a class="btn btn-secondary" href="/kosar">{t('core.home_cta_cart')}</a>
	</div>
</section>
