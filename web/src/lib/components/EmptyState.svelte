<!-- Shown when a list or page has nothing to display. Optional actions go in the children snippet. -->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n';

	interface Props {
		title?: string;
		message?: string;
		children?: Snippet;
	}

	let { title, message, children }: Props = $props();
</script>

<div class="empty card">
	<p class="title">{title ?? t('core.empty_title')}</p>
	{#if message}
		<p class="muted">{message}</p>
	{/if}
	{#if children}
		<div class="btn-row">{@render children()}</div>
	{/if}
</div>

<style>
	.empty {
		text-align: center;
		padding: var(--space-5) var(--space-4);
	}

	.title {
		font-weight: 600;
		font-size: var(--font-size-lg);
	}

	.btn-row {
		justify-content: center;
	}
</style>
