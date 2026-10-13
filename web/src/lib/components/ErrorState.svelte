<!-- Shows an API (or any) error in plain words, with an optional retry button. -->
<script lang="ts">
	import { errorMessageKey } from '$lib/errors';
	import { t } from '$lib/i18n';

	interface Props {
		error: unknown;
		onretry?: () => void;
		title?: string;
	}

	let { error, onretry, title }: Props = $props();
	const message = $derived(t(errorMessageKey(error)));
</script>

<div class="notice notice-danger error" role="alert">
	<p class="title">{title ?? t('core.error_title')}</p>
	<p>{message}</p>
	{#if onretry}
		<button type="button" class="btn btn-secondary" onclick={onretry}>{t('core.retry')}</button>
	{/if}
</div>

<style>
	.title {
		font-weight: 700;
		margin-bottom: var(--space-1);
	}
</style>
