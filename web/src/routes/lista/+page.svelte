<!--
	Shopping list ("Bevásárlólista") and "Hol a legolcsóbb a közelben?". PLACEHOLDER for the list agent.
	TODO(list agent):
	- POST /api/list from StoredState.plan; tick items into StoredState.checkedItems;
	- nearby stores: originFromLocation() ($lib/location) -> pickNearestPerChain() ($lib/geo) on GET /api/stores,
	  ON THE DEVICE; ask for location only via <LocationExplainer>, offer <DistrictPicker>;
	- POST /api/quote with ingredient ids, quantities and store ids ONLY (never coordinates);
	- every price view: <Attribution dataDate={quote.data_date} ksh={…} />, "nincs ár" / KSH badges, and
	  "legolcsóbb" only with QuoteResponse.scope_note_hu (BUILD-BRIEF §8.6).
-->
<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { t } from '$lib/i18n';
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('list.title') })}</title>
</svelte:head>

<h1>{t('list.title')}</h1>
<EmptyState message={t('list.placeholder')} />
