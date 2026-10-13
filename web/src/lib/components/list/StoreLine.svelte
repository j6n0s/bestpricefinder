<!--
	One line of the list at the chosen store: the products to buy (plain-text names, never images), the packs
	("2 × 175 g"), the checkout cost, the leftover, the price labels and the alternatives. "nincs ebben a
	boltban", "nincs ár" and the labelled KSH estimate (never part of the total) for lines without a store price.
-->
<script lang="ts">
	import type { PackOptionOut, QuoteLineOut } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import { formatMoney } from '$lib/format';
	import { i18n, t, tp } from '$lib/i18n';
	import { formatAmount, leftoverText, packsText, unitPriceText } from '$lib/list/packs';
	import { priceScopeKey, priceTypeKey } from '$lib/list/ranking';

	interface Props {
		line: QuoteLineOut;
		name: string;
		checked: boolean;
		ontogglecheck: (ingredientId: string, on: boolean) => void;
	}

	let { line, name, checked, ontogglecheck }: Props = $props();

	const lang = $derived(i18n.lang);
	const leftover = $derived(leftoverText(line.leftover_qty, line.unit, lang));

	function typeText(option: PackOptionOut): string | null {
		const key = priceTypeKey(option.price_type);
		return key ? t(key) : null;
	}

	function alternativeText(option: PackOptionOut): string {
		if (option.pack_size === null) {
			return t('list.alternative_weight', { price: unitPriceText(option.unit_price, line.unit, lang) });
		}
		const pack = t('list.alternative_pack', {
			pack: formatAmount(option.pack_size, line.unit, lang),
			price: formatMoney(option.pack_price)
		});
		return `${pack} ${t('list.unit_price', { price: unitPriceText(option.unit_price, line.unit, lang) })}`;
	}
</script>

<li class="line" class:done={checked} data-testid="store-line" data-ingredient-id={line.ingredient_id}>
	<div class="head">
		<label class="check">
			<input
				type="checkbox"
				{checked}
				onchange={(event) => ontogglecheck(line.ingredient_id, event.currentTarget.checked)}
			/>
			<span class="name">{name}</span>
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
					<span class="product">{pick.option.product_name}</span>
					<span class="pack">
						{packs ?? t('list.by_weight', { qty: formatAmount(pick.qty, line.unit, lang) })} · {formatMoney(pick.cost)}
					</span>
					<span class="labels">
						<Badge tone="neutral">{t(priceScopeKey(pick.option.price_scope))}</Badge>
						{#if pick.option.availability === 'assumed'}
							<Badge kind="assumed" />
						{/if}
						{#if type}
							<span class="small">{type}</span>
						{/if}
					</span>
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
							<span class="product">{option.product_name}</span>
							<span class="pack">{alternativeText(option)}</span>
							<span class="labels">
								<Badge tone="neutral">{t(priceScopeKey(option.price_scope))}</Badge>
								{#if option.availability === 'assumed'}
									<Badge kind="assumed" />
								{/if}
								{#if type}
									<span class="small">{type}</span>
								{/if}
							</span>
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

	.labels {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-2);
	}

	.alternatives summary {
		padding: 10px 0;
		cursor: pointer;
		color: var(--color-primary);
		font-weight: 600;
	}
</style>
