<!--
	Loading indicator. The rotation is a plain CSS animation in this component's stylesheet (emitted as a
	.css file at build time, so it needs no inline style and no injected <style>); it stops under
	prefers-reduced-motion.
-->
<script lang="ts">
	import { t } from '$lib/i18n';

	interface Props {
		/** Announced to screen readers; defaults to "Betöltés…". */
		label?: string;
		/** Show the label next to the ring instead of only to screen readers. */
		showLabel?: boolean;
	}

	let { label, showLabel = false }: Props = $props();
	const text = $derived(label ?? t('core.loading'));
</script>

<span class="spinner" role="status">
	<span class="ring" aria-hidden="true"></span>
	<span class:visually-hidden={!showLabel}>{text}</span>
</span>

<style>
	.spinner {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		color: var(--color-text-muted);
	}

	.ring {
		width: 1.25rem;
		height: 1.25rem;
		flex: none;
		border: 3px solid var(--color-border-subtle);
		border-top-color: var(--color-primary);
		border-radius: 50%;
		animation: spin 0.9s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.ring {
			animation: none;
			border-style: dotted;
			border-color: var(--color-primary);
		}
	}
</style>
