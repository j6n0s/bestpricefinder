<!-- Shows an API (or any) error in plain words, with an optional retry button. -->
<script lang="ts">
	import { errorMessageKey } from '$lib/errors';
	import { t } from '$lib/i18n';

	interface Props {
		error: unknown;
		onretry?: () => void;
		title?: string;
		/** Bound by a page that moves focus to "Újra" after a failed action (so focus never drops to <body>). */
		retryButton?: HTMLButtonElement;
	}

	let { error, onretry, title, retryButton = $bindable() }: Props = $props();
	const message = $derived(t(errorMessageKey(error)));
</script>

<div class="notice notice-danger error" role="alert">
	<p class="title">{title ?? t('core.error_title')}</p>
	<p>{message}</p>
	{#if onretry}
		<button type="button" class="btn btn-secondary" bind:this={retryButton} onclick={onretry}>{t('core.retry')}</button>
	{/if}
</div>

<style>
	.title {
		font-weight: 700;
		margin-bottom: var(--space-1);
	}
</style>
