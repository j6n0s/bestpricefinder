<!--
	One line of the list at the chosen store: the products to buy (plain-text names, never images), each pick as
	price per amount ("1 000 Ft / 500 g", "700 Ft / 2 × 175 g"), the checkout cost, the leftover, the price notes
	and the alternatives. "nincs ebben a boltban", "nincs ár" and the labelled KSH estimate (never part of the
	total) for lines without a store price.
-->
<script lang="ts">
	import type { PackOptionOut, QuoteLineOut } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import { formatMoney } from '$lib/format';
	import { i18n, t, tp } from '$lib/i18n';
	import { formatAmount, leftoverText, packsText, unitPriceText } from '$lib/list/packs';
	import { priceNoteKeys, priceTypeKey, type NoteKey } from '$lib/list/ranking';

	interface Props {
		line: QuoteLineOut;
		name: string;
		checked: boolean;
		ontogglecheck: (ingredientId: string, on: boolean) => void;
		/** Notes said once for the whole store (every product there shares them), so not on this line. */
		omit?: readonly NoteKey[];
	}

	let { line, name, checked, ontogglecheck, omit = [] }: Props = $props();

	const lang = $derived(i18n.lang);
	const leftover = $derived(leftoverText(line.leftover_qty, line.unit, lang));

	function typeText(option: PackOptionOut): string | null {
		const key = priceTypeKey(option.price_type);
		return key ? t(key) : null;
	}

	function alternativeText(option: PackOptionOut): string {
		if (option.pack_size === null) return unitPriceText(option.unit_price, line.unit, lang);
		const pack = t('list.alternative_pack', {
			pack: formatAmount(option.pack_size, line.unit, lang),
			price: formatMoney(option.pack_price)
		});
		return `${pack} ${t('list.unit_price', { price: unitPriceText(option.unit_price, line.unit, lang) })}`;
	}
</script>

<!-- The price notes in plain words ("A lánc ára, itt eltérhet.", "Nem biztos, hogy itt kapható.") and the GVH
     price label (loyalty or reduced price); nothing for the store's own normal price. -->
{#snippet notes(option: PackOptionOut, type: string | null)}
	{@const keys = priceNoteKeys(option).filter((key) => !omit.includes(key))}
	{#if keys.length > 0 || type}
		<span class="notes small muted">
			{#each keys as key (key)}<span>{t(key)}</span>{/each}
			{#if type}<span>{type}</span>{/if}
		</span>
	{/if}
{/snippet}

<li class="line" class:done={checked} data-testid="store-line" data-ingredient-id={line.ingredient_id}>
	<div class="head">
		<label class="check">
			<input
				type="checkbox"
				{checked}
				onchange={(event) => ontogglecheck(line.ingredient_id, event.currentTarget.checked)}
			/>
			<span class="name" lang="hu">{name}</span>
		</label>
		<span class="cost">
			{#if line.status === 'priced' && line.checkout_cost !== null}
				<strong data-testid="line-cost">{formatMoney(line.checkout_cost)}</strong>
			{:else if line.status === 'unavailable'}
				<Badge kind="unavailable" />
			{:else if line.status === 'ksh_estimate' && line.ksh_estimate !== null}
				<Badge kind="ksh_estimate" />
			{:else}
				<Badge kind="no_price" />
			{/if}
		</span>
	</div>

	<p class="need small muted">{t('list.need', { qty: formatAmount(line.qty, line.unit, lang) })}</p>

	{#if line.status === 'priced'}
		<ul class="picks">
			{#each line.picks as pick, index (index)}
				{@const packs = packsText(pick, line.unit, lang)}
				{@const type = typeText(pick.option)}
				<li>
					<span class="product" lang="hu">{pick.option.product_name}</span>
					<span class="pack">
						{t('list.price_per', { price: formatMoney(pick.cost), qty: packs ?? formatAmount(pick.qty, line.unit, lang) })}
					</span>
					{@render notes(pick.option, type)}
				</li>
			{/each}
		</ul>
		{#if leftover}
			<p class="small muted">{t('list.leftover', { qty: leftover })}</p>
		{/if}
		{#if line.alternatives.length > 0}
			<details class="alternatives">
				<summary>{tp('list.alternatives', line.alternatives.length)}</summary>
				<ul>
					{#each line.alternatives as option, index (index)}
						{@const type = typeText(option)}
						<li>
							<span class="product" lang="hu">{option.product_name}</span>
							<span class="pack">{alternativeText(option)}</span>
							{@render notes(option, type)}
						</li>
					{/each}
				</ul>
			</details>
		{/if}
	{:else if line.status === 'ksh_estimate' && line.ksh_estimate !== null}
		<p class="small" data-testid="ksh-value">{t('list.ksh_value', { price: formatMoney(line.ksh_estimate) })}</p>
	{/if}
</li>

<style>
	.line {
		padding: var(--space-2) var(--space-3);
	}

	.line > * {
		margin: 0 0 var(--space-1);
	}

	.line > :last-child {
		margin-bottom: 0;
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-1) var(--space-3);
	}

	.check {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		flex: 1 1 10rem;
		min-height: var(--tap);
		min-width: 0;
		cursor: pointer;
	}

	.check input {
		width: 1.25rem;
		height: 1.25rem;
		margin: 0;
		flex: none;
		accent-color: var(--color-primary);
	}

	.name {
		font-weight: 600;
	}

	.done .name {
		text-decoration: line-through;
		color: var(--color-text-muted);
	}

	.cost {
		white-space: nowrap;
	}

	.picks,
	.alternatives ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.picks li,
	.alternatives li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-2);
		padding: var(--space-1) 0;
	}

	.product {
		flex: 1 1 100%;
	}

	.pack {
		color: var(--color-text-muted);
	}

	.notes {
		display: inline-flex;
		flex-wrap: wrap;
		gap: 0 var(--space-2);
	}

	.alternatives summary {
		padding: 10px 0;
		cursor: pointer;
		color: var(--color-primary);
		font-weight: 600;
	}
</style>
