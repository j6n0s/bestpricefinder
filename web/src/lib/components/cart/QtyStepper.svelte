<!--
	− amount + for one good in the cart, as one rounded control. The amount moves along the unit's ladder of
	round amounts ($lib/cart/cart.ts stepQty). At the smallest amount the − becomes a bin: pressing it takes the
	good out. Every button names the good, and the amount is announced politely when it changes.
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
		onchange: (qty: number | null) => void;
		/** The bin's label ("Törlés a kosárból: {name}" by default; the pantry has its own). */
		removeKey?: 'cart.remove_named' | 'list.on_hand_remove_named';
	}

	let { name, qty, unit, onchange, removeKey = 'cart.remove_named' }: Props = $props();
	const amount = $derived(formatAmount(qty, unit, i18n.lang));
	const less = $derived(stepQty(qty, unit, -1));
</script>

<div class="stepper" role="group" aria-label={name}>
	<button
		type="button"
		class="step"
		aria-label={less === null ? t(removeKey, { name }) : t('cart.less_named', { name })}
		onclick={() => onchange(less)}
	>
		{#if less === null}
			<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">
				<path
					d="M4 7h16M9 7V4.5h6V7M6.5 7l.8 12.2a1.5 1.5 0 0 0 1.5 1.3h6.4a1.5 1.5 0 0 0 1.5-1.3L17.5 7M10 11v6M14 11v6"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
		{:else}
			<span aria-hidden="true">−</span>
		{/if}
	</button>
	<output class="amount" aria-live="polite" aria-label={t('cart.qty_named', { name, qty: amount })}>{amount}</output>
	<button
		type="button"
		class="step"
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
		flex: none;
		align-items: center;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: var(--color-surface);
	}

	.step {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--tap);
		height: var(--tap);
		padding: 0;
		border: 0;
		border-radius: 999px;
		background: transparent;
		color: var(--color-primary);
		font-size: var(--font-size-lg);
		font-weight: 700;
		line-height: 1;
		cursor: pointer;
	}

	@media (hover: hover) {
		.step:hover:not(:disabled) {
			background: var(--color-surface-alt);
		}
	}

	.step:disabled {
		color: var(--color-text-muted);
		cursor: not-allowed;
	}

	.amount {
		min-width: 4rem;
		text-align: center;
		font-weight: 600;
		white-space: nowrap;
	}
</style>
