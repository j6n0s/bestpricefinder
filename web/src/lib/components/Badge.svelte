<!--
	Small status label. Use `kind` for the app's standard badges so their wording stays consistent:
	  <Badge kind="no_price" />      "nincs ár" (unpriced line)
	  <Badge kind="untested" />      "kipróbálatlan recept" (recipe.tested === false)
	  <Badge kind="ksh_estimate" />  "becsült országos átlagár (KSH)"
	or pass your own text as children with a `tone`.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { t, type PlainKey } from '$lib/i18n';

	type Kind =
		| 'no_price'
		| 'untested'
		| 'ksh_estimate'
		| 'no_store_data'
		| 'unavailable'
		| 'pantry'
		| 'stale';
	type Tone = 'neutral' | 'info' | 'warning' | 'danger' | 'success';

	interface Props {
		kind?: Kind;
		tone?: Tone;
		children?: Snippet;
	}

	const KINDS: Record<Kind, { key: PlainKey; tone: Tone }> = {
		no_price: { key: 'core.badge_no_price', tone: 'neutral' },
		untested: { key: 'core.badge_untested', tone: 'warning' },
		ksh_estimate: { key: 'core.badge_ksh_estimate', tone: 'info' },
		no_store_data: { key: 'core.badge_no_store_data', tone: 'neutral' },
		unavailable: { key: 'core.badge_unavailable', tone: 'danger' },
		pantry: { key: 'core.badge_pantry', tone: 'success' },
		stale: { key: 'core.badge_stale', tone: 'warning' }
	};

	let { kind, tone, children }: Props = $props();
	const resolved = $derived<Tone>(tone ?? (kind ? KINDS[kind].tone : 'neutral'));
</script>

<span
	class="badge"
	class:neutral={resolved === 'neutral'}
	class:info={resolved === 'info'}
	class:warning={resolved === 'warning'}
	class:danger={resolved === 'danger'}
	class:success={resolved === 'success'}
>
	{#if children}
		{@render children()}
	{:else if kind}
		{t(KINDS[kind].key)}
	{/if}
</span>

<style>
	.badge {
		display: inline-block;
		padding: 0.125rem var(--space-2);
		border-radius: var(--radius-pill);
		border: 1px solid transparent;
		font-size: var(--font-size-sm);
		font-weight: 600;
		line-height: 1.4;
		white-space: normal;
		vertical-align: middle;
	}

	.neutral {
		background: var(--color-neutral-bg);
		color: var(--color-neutral-text);
	}

	.info {
		background: var(--color-info-bg);
		color: var(--color-info-text);
	}

	.warning {
		background: var(--color-warning-bg);
		color: var(--color-warning-text);
		border-color: var(--color-warning-border);
	}

	.danger {
		background: var(--color-danger-bg);
		color: var(--color-danger-text);
	}

	.success {
		background: var(--color-success-bg);
		color: var(--color-success-text);
	}
</style>
