<!--
	Recipe detail: GET /api/recipes/{id}. Ingredients with display quantities scaled by a servings stepper
	(pantry staples marked), steps, the chain cost comparison (table + bars, cheapest first, tie-aware) with the
	GVH source line, nutrition only when the API has it (null until composition data is imported), and
	"Hozzáadás a tervhez", which writes to the plan stored on this device.

	Headings: the recipe title is the page's h1 (the small "Recept" label above it is a plain paragraph) and
	every section is an h2. While loading and on an error the h1 is "Recept", so the page always has one.
-->
<script lang="ts">
	import { page } from '$app/state';
	import { ApiError, getRecipe } from '$lib/api/client';
	import { ID_PATTERNS, type RecipeDetail } from '$lib/api/types';
	import Attribution from '$lib/components/Attribution.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import AddToPlan from '$lib/components/recipes/AddToPlan.svelte';
	import ChainCostTable from '$lib/components/recipes/ChainCostTable.svelte';
	import IngredientList from '$lib/components/recipes/IngredientList.svelte';
	import NutritionTable from '$lib/components/recipes/NutritionTable.svelte';
	import RecipePrice from '$lib/components/recipes/RecipePrice.svelte';
	import ServingsStepper from '$lib/components/recipes/ServingsStepper.svelte';
	import TagList from '$lib/components/recipes/TagList.svelte';
	import { t, tp } from '$lib/i18n';
	import { getMeta } from '$lib/meta.svelte';
	import { chainNameMap, clampServings } from '$lib/plan/recipes';
	import { load } from '$lib/storage';

	const meta = getMeta();
	const excluded = load().exclusions.ingredients;

	const id = $derived(page.params.id ?? '');
	let detail = $state<RecipeDetail | null>(null);
	let error = $state<unknown>(null);
	let loading = $state(true);
	let servings = $state(1);

	const names = $derived(chainNameMap(meta.data?.chains));
	const factor = $derived(detail && detail.servings > 0 ? servings / detail.servings : 1);
	const notFound = $derived(error instanceof ApiError && error.code === 'not_found');

	async function loadRecipe(recipeId: string, signal?: AbortSignal): Promise<void> {
		loading = true;
		error = null;
		detail = null;
		if (!ID_PATTERNS.recipe.test(recipeId)) {
			error = new ApiError({ kind: 'http', status: 404, code: 'not_found' });
			loading = false;
			return;
		}
		try {
			const result = await getRecipe(recipeId, signal ? { signal } : {});
			if (signal?.aborted) return;
			detail = result;
			servings = clampServings(result.servings);
		} catch (caught) {
			if (signal?.aborted) return;
			error = caught;
		} finally {
			if (!signal?.aborted) loading = false;
		}
	}

	$effect(() => {
		const recipeId = id;
		const controller = new AbortController();
		void loadRecipe(recipeId, controller.signal);
		return () => controller.abort();
	});
</script>

<svelte:head>
	<title>{t('core.page_title', { page: detail?.title ?? t('recipes.detail_title') })}</title>
</svelte:head>

<p class="back"><a href="/receptek">{t('recipes.back')}</a></p>

{#if loading || error || !detail}
	<h1 class="title">{t('recipes.detail_title')}</h1>
	{#if loading}
		<Spinner showLabel />
	{:else if error}
		<ErrorState
			{error}
			title={t('recipes.detail_error_title')}
			onretry={notFound ? undefined : () => void loadRecipe(id)}
		/>
	{/if}
{:else}
	<article class="recipe" aria-labelledby="recipe-title">
		<header class="intro">
			<p class="kind">{t('recipes.detail_title')}</p>
			<h1 id="recipe-title" class="title">{detail.title}</h1>
			<p class="meta">
				{#if detail.minutes !== null}
					<span>{tp('recipes.minutes', detail.minutes)}</span>
				{/if}
				<span>{tp('recipes.servings', detail.servings)}</span>
				{#if !detail.tested}
					<Badge kind="untested" />
				{/if}
			</p>
			{#if detail.summary}
				<p class="summary">{detail.summary}</p>
			{/if}
			<TagList tags={detail.tags} />
			<p class="price"><RecipePrice recipe={detail} {names} /></p>
		</header>

		<section class="card" aria-labelledby="ingredients-title">
			<h2 id="ingredients-title">{t('recipes.ingredients_title')}</h2>
			<ServingsStepper value={servings} onchange={(value) => (servings = value)} />
			{#if servings !== detail.servings}
				<p class="small muted" data-testid="scaled-note">
					{tp('recipes.scaled_note', servings, { original: detail.servings })}
				</p>
			{/if}
			<IngredientList lines={detail.lines} {factor} {excluded} />
		</section>

		<section class="card" aria-labelledby="steps-title">
			<h2 id="steps-title">{t('recipes.steps_title')}</h2>
			<ol class="steps">
				{#each detail.steps as step, index (index)}
					<li>{step}</li>
				{/each}
			</ol>
		</section>

		<section class="card" aria-labelledby="costs-title">
			<h2 id="costs-title">{t('recipes.costs_title')}</h2>
			<ChainCostTable costs={detail.chain_costs} lines={detail.lines} {names} />
			<p class="small muted">{t('recipes.price_note')}</p>
			<Attribution dataDate={detail.data_date} />
		</section>

		{#if detail.nutrition}
			<section class="card" aria-labelledby="nutrition-title">
				<h2 id="nutrition-title">{t('recipes.nutrition_title')}</h2>
				<NutritionTable nutrition={detail.nutrition} source={meta.data?.attribution.nutrition} />
			</section>
		{/if}

		<section class="card" aria-labelledby="add-title">
			<h2 id="add-title">{t('recipes.add_title')}</h2>
			{#key detail.id}
				<AddToPlan recipe={detail} />
			{/key}
		</section>
	</article>
{/if}

<style>
	.back a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}

	.kind {
		font-size: var(--font-size-base);
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: var(--space-1);
	}

	.title {
		font-size: var(--font-size-2xl);
	}

	.intro .kind + .title {
		margin-top: 0;
	}

	.recipe > :global(* + *) {
		margin-top: var(--space-4);
	}

	.intro > :global(* + *) {
		margin-top: var(--space-2);
	}

	.intro p {
		margin-bottom: 0;
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-3);
		color: var(--color-text-muted);
	}

	.summary {
		font-size: var(--font-size-lg);
	}

	section > :global(* + *) {
		margin-top: var(--space-3);
	}

	.steps {
		padding-left: var(--space-5);
		margin-bottom: 0;
	}

	.steps li + li {
		margin-top: var(--space-2);
	}
</style>
