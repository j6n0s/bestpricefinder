<!--
	Nutrition per serving: factual numbers only, with the data coverage and the composition table's source.
	The recipe page renders this only when the API returns nutrition (it is null until composition data is
	imported). No health claims and no judgement of the values (BUILD-BRIEF §8.7).
-->
<script lang="ts">
	import type { AttributionOut, NutritionOut } from '$lib/api/types';
	import { formatNumber } from '$lib/format';
	import { i18n, t, type PlainKey } from '$lib/i18n';
	import { coveragePercent } from '$lib/plan/recipes';

	interface Props {
		nutrition: NutritionOut;
		source: AttributionOut | null | undefined;
	}

	let { nutrition, source }: Props = $props();

	const ROWS: readonly { key: PlainKey; field: Exclude<keyof NutritionOut, 'coverage'>; unit: string; sub?: boolean }[] = [
		{ key: 'recipes.nutrition_kcal', field: 'kcal', unit: 'kcal' },
		{ key: 'recipes.nutrition_protein', field: 'protein_g', unit: 'g' },
		{ key: 'recipes.nutrition_carb', field: 'carb_g', unit: 'g' },
		{ key: 'recipes.nutrition_sugar', field: 'sugar_g', unit: 'g', sub: true },
		{ key: 'recipes.nutrition_fat', field: 'fat_g', unit: 'g' },
		{ key: 'recipes.nutrition_satfat', field: 'satfat_g', unit: 'g', sub: true },
		{ key: 'recipes.nutrition_fiber', field: 'fiber_g', unit: 'g' },
		{ key: 'recipes.nutrition_salt', field: 'salt_g', unit: 'g' }
	];

	function amount(value: number, unit: string): string {
		const rounded = unit === 'kcal' ? Math.round(value) : Math.round(value * 10) / 10;
		return `${formatNumber(rounded)} ${unit}`;
	}

	const sourceUrl = $derived(source && /^https:\/\//.test(source.url) ? source.url : null);
	const sourceText = $derived(source ? (i18n.lang === 'en' ? source.text_en : source.text_hu) : '');
	const percent = $derived(coveragePercent(nutrition.coverage));
</script>

<table data-testid="nutrition">
	<thead>
		<tr>
			<th scope="col">{t('recipes.nutrition_col_nutrient')}</th>
			<th scope="col">{t('recipes.nutrition_col_amount')}</th>
		</tr>
	</thead>
	<tbody>
		{#each ROWS as row (row.field)}
			<tr>
				<th scope="row" class:sub={row.sub}>{t(row.key)}</th>
				<td>{amount(nutrition[row.field], row.unit)}</td>
			</tr>
		{/each}
	</tbody>
</table>
{#if percent < 100}
	<p class="small muted">{t('recipes.nutrition_coverage', { percent })}</p>
{/if}
{#if source && sourceText}
	<p class="small muted">
		{#if sourceUrl}
			<a href={sourceUrl} rel="noopener noreferrer" target="_blank">{sourceText}</a>
		{:else}
			{sourceText}
		{/if}
	</p>
{/if}

<style>
	table {
		width: 100%;
		border-collapse: collapse;
	}

	th,
	td {
		padding: var(--space-2);
		text-align: left;
		border-bottom: 1px solid var(--color-border-subtle);
	}

	td {
		text-align: right;
		white-space: nowrap;
	}

	thead th:last-child {
		text-align: right;
	}

	tbody th {
		font-weight: 400;
	}

	.sub {
		padding-left: var(--space-5);
	}

	p {
		margin: var(--space-2) 0 0;
	}

	a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}
</style>
