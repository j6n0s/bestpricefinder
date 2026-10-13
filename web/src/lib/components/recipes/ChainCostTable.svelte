<!--
	Chain cost comparison of one recipe: an accessible table (caption, column and row headers) with a simple
	bar per chain, cheapest first. Equal whole-forint costs are a tie: they share a rank and are labelled
	"holtverseny"; no chain of a tie is singled out (BUILD-BRIEF §4.1 trap 13). Only chains that price at least
	90 % of the cost are ranked (contract v1.2); the others are shown after them as "részleges ár", unranked,
	with a note. The bars are SVG rectangles sized by an attribute, so no inline style is needed (CSP
	style-src 'self').
-->
<script lang="ts">
	import type { ChainCostOut, ChainSlug, RecipeLineOut } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import { formatMoney } from '$lib/format';
	import { t } from '$lib/i18n';
	import { chainCostRows } from '$lib/plan/recipes';

	interface Props {
		costs: readonly ChainCostOut[];
		lines: readonly RecipeLineOut[];
		names: ReadonlyMap<ChainSlug, string>;
	}

	let { costs, lines, names }: Props = $props();

	const rows = $derived(chainCostRows(costs, names));
	const hasPartial = $derived(rows.some((row) => row.partial));
	const ingredientNames = $derived(new Map(lines.map((line) => [line.ingredient_id, line.ingredient_name])));

	function missingNames(ids: readonly string[]): string {
		return [...new Set(ids)].map((id) => ingredientNames.get(id) ?? id).join(', ');
	}
</script>

{#if rows.length === 0}
	<p class="muted">{t('recipes.costs_none')}</p>
{:else}
	<div class="scroll">
		<table data-testid="chain-costs">
			<caption>{t('recipes.costs_caption')}</caption>
			<thead>
				<tr>
					<th scope="col">{t('recipes.costs_col_chain')}</th>
					<th scope="col">{t('recipes.costs_col_price')}</th>
				</tr>
			</thead>
			<tbody>
				{#each rows as row (row.chain)}
					<tr data-testid="chain-cost-{row.chain}">
						<th scope="row">
							{#if row.rank !== null}
								<span class="rank">{t('recipes.costs_rank', { rank: row.rank })}</span>
							{/if}
							<span class="chain">{row.name}</span>
							{#if row.tied}
								<Badge tone="neutral">{t('recipes.costs_tie')}</Badge>
							{/if}
							{#if row.partial}
								<Badge tone="warning">{t('recipes.costs_partial')}</Badge>
							{/if}
						</th>
						<td>
							{#if row.costPerServing !== null}
								<span class="amount">{formatMoney(row.costPerServing)}</span>
								<svg class="bar" viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true" focusable="false">
									<rect class="track" x="0" y="0" width="100" height="8" rx="2" />
									<rect class="fill" x="0" y="0" width={row.barPercent} height="8" rx="2" />
								</svg>
								<span class="detail">{t('recipes.coverage', { percent: row.coveragePercent })}</span>
							{:else}
								<Badge kind="no_price" />
							{/if}
							{#if row.missing.length > 0}
								<span class="missing small"
									>{t('recipes.costs_missing')} <span lang="hu">{missingNames(row.missing)}</span></span
								>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if hasPartial}
		<p class="small muted" data-testid="chain-costs-partial-note">{t('recipes.costs_partial_note')}</p>
	{/if}
{/if}

<style>
	.scroll {
		overflow-x: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--font-size-sm);
	}

	caption {
		text-align: left;
		color: var(--color-text-muted);
		padding-bottom: var(--space-2);
	}

	th,
	td {
		padding: var(--space-2);
		text-align: left;
		vertical-align: top;
		border-bottom: 1px solid var(--color-border-subtle);
		overflow-wrap: break-word;
	}

	thead th {
		border-bottom-color: var(--color-border);
	}

	tbody th {
		width: 40%;
		font-weight: 600;
	}

	.rank {
		color: var(--color-text-muted);
		margin-right: var(--space-1);
	}

	.chain {
		margin-right: var(--space-1);
	}

	tbody th :global(.badge) {
		white-space: nowrap;
	}

	.amount {
		display: block;
		font-weight: 600;
		white-space: nowrap;
	}

	.bar {
		display: block;
		width: 100%;
		min-width: 3rem;
		height: 0.5rem;
		margin-top: var(--space-1);
	}

	.track {
		fill: var(--color-surface-alt);
	}

	.fill {
		fill: var(--color-primary);
	}

	.detail {
		display: block;
		margin-top: var(--space-1);
	}

	.missing {
		display: block;
		color: var(--color-text-muted);
		margin-top: var(--space-1);
	}
</style>
