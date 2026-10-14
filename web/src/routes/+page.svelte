<!-- Home: what the app does, in plain words, and the way into the weekly plan. No health or price claims. -->
<script lang="ts">
	import { t } from '$lib/i18n';
</script>

<svelte:head>
	<title>{t('core.app_name')}</title>
</svelte:head>

<section class="stack">
	<h1>{t('core.home_title')}</h1>
	<p class="lead">{t('core.home_lead')}</p>
	<div class="btn-row">
		<a class="btn btn-primary" href="/terv">{t('core.home_cta_plan')}</a>
		<a class="btn btn-secondary" href="/receptek">{t('core.home_cta_recipes')}</a>
		<a class="btn btn-secondary" href="/kosar">{t('core.home_cta_cart')}</a>
	</div>
</section>

<section class="card steps" aria-labelledby="home-steps">
	<h2 id="home-steps">{t('core.home_steps_title')}</h2>
	<ol>
		<li>{t('core.home_step_plan')}</li>
		<li>{t('core.home_step_list')}</li>
		<li>{t('core.home_step_stores')}</li>
	</ol>
</section>

<p class="cart-note">{t('core.home_cart_note')}</p>

<p class="muted privacy">{t('core.home_privacy')}</p>

<style>
	.lead {
		font-size: var(--font-size-lg);
	}

	.steps {
		margin-top: var(--space-5);
	}

	ol {
		padding-left: var(--space-5);
	}

	li + li {
		margin-top: var(--space-2);
	}

	.cart-note,
	.privacy {
		margin-top: var(--space-4);
	}
</style>
