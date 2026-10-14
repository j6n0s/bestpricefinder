<!--
	− amount + for one good in the cart. The amount moves along the unit's ladder of round amounts
	($lib/cart/cart.ts stepQty); − below the smallest amount removes the good. Every button names the good,
	and the amount is announced politely when it changes.
-->
<script lang="ts">
	import type { Unit } from '$lib/api/types';
	import { atMaximum, stepQty } from '$lib/cart/cart';
	import { i18n, t } from '$lib/i18n';
	import { formatAmount } from '$lib/list/packs';

	interface Props {
		name: string;
		qty: number;
		unit: Unit;
		/** "kb. 3 db" for goods sold by weight that have a typical piece weight. */
		pieces?: number | null;
		onchange: (qty: number | null) => void;
	}

	let { name, qty, unit, pieces = null, onchange }: Props = $props();
	const amount = $derived(formatAmount(qty, unit, i18n.lang));
</script>

<div class="stepper" role="group" aria-label={name}>
	<button type="button" class="btn btn-secondary step" aria-label={t('cart.less_named', { name })} onclick={() => onchange(stepQty(qty, unit, -1))}>
		<span aria-hidden="true">−</span>
	</button>
	<output class="amount" aria-live="polite" aria-label={t('cart.qty_named', { name, qty: amount })}>
		<span class="qty">{amount}</span>
		{#if pieces !== null}
			<span class="pieces small muted">{t('cart.pieces', { count: pieces })}</span>
		{/if}
	</output>
	<button
		type="button"
		class="btn btn-secondary step"
		aria-label={t('cart.more_named', { name })}
		disabled={atMaximum(qty, unit)}
		onclick={() => onchange(stepQty(qty, unit, 1))}
	>
		<span aria-hidden="true">+</span>
	</button>
</div>

<style>
	.stepper {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
	}

	.step {
		min-width: var(--tap);
		padding: 0;
		font-size: var(--font-size-lg);
		font-weight: 700;
	}

	.amount {
		display: inline-flex;
		flex-direction: column;
		align-items: center;
		min-width: 4.5rem;
		text-align: center;
		line-height: 1.2;
	}

	.qty {
		font-weight: 600;
		white-space: nowrap;
	}

	.pieces {
		white-space: nowrap;
	}
</style>
