<!--
	"Hogyan számoljuk?": a method note kept out of the way. The page itself shows only labels and numbers; the
	explanation sits behind a native disclosure that starts closed, so it is one tap away for whoever wants it.
	The summary is a 44 px touch target.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n';

	interface Props {
		children: Snippet;
		testid?: string;
	}

	let { children, testid }: Props = $props();
</script>

<details class="how small" data-testid={testid}>
	<summary class="muted">{t('core.how_calculated')}</summary>
	<div class="body muted">{@render children()}</div>
</details>

<style>
	summary {
		/* list-item keeps the disclosure marker; min-height and padding make a 44 px target. */
		min-height: var(--tap);
		padding: var(--space-3) 0;
		cursor: pointer;
	}

	.body > :global(p) {
		margin: 0 0 var(--space-2);
	}
</style>
