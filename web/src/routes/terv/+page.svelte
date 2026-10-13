<!--
	Weekly plan ("Heti terv"). PLACEHOLDER for the plan feature agent.
	TODO(plan agent):
	- POST /api/plan/suggest with people/slots/exclusions from $lib/storage (never coordinates), store the
	  result as StoredState.plan, re-check edits with POST /api/plan/check (same no_repeat_days);
	- map PlanResponse.warnings to text with the plan.warning_* keys (codes in docs/API.md);
	- any view that shows prices must render <Attribution dataDate=… /> (BUILD-BRIEF §8.2).
-->
<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { t } from '$lib/i18n';
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('plan.title') })}</title>
</svelte:head>

<h1>{t('plan.title')}</h1>
<EmptyState message={t('plan.placeholder')} />
