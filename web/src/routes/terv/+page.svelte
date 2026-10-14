<!--
	Weekly plan ("Heti terv"): plan the rest of the month week by week.
	- "Terv készítése" / "Új javaslat" call POST /api/plan/suggest with the household settings from
	  $lib/storage (people, slots, exclusions) and a seed. "Terv készítése" uses a fresh random seed (never the
	  current plan's): the planner is deterministic and gets no date, so a fixed seed would repeat the same week
	  every week. "Új javaslat" uses the next seed; both are stored with the plan, so retry and undo work.
	- Another tab may change or delete the plan: the page reloads it (onExternalChange), and edits start from
	  the stored plan, never from a stale copy.
	- Focus never drops to <body>: the buttons stay focusable while a plan is being made (aria-disabled), a
	  failed suggestion moves focus to "Újra", and a status region says "Terv készítése…".
	- The plan is personal data: it is kept only in localStorage (StoredState.plan), never on the server.
	- Every edit (change or remove a meal) re-checks the weekly rules with POST /api/plan/check, using the
	  plan's own no_repeat_days.
	- Recipe prices are chain-typical estimates: the page shows the GVH source line with the data date.
	- No intro or method paragraphs: the title, the form's labels and buttons and the numbers say what to do.
	  Whether a recipe is untested is shown on its detail page.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { getRecipes, postPlanCheck, postPlanSuggest } from '$lib/api/client';
	import type { RecipeSummary, RecipesResponse, RuleCheckOut, Slot } from '$lib/api/types';
	import Attribution from '$lib/components/Attribution.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import DayCard from '$lib/components/plan/DayCard.svelte';
	import MealPicker from '$lib/components/plan/MealPicker.svelte';
	import PlanChecks from '$lib/components/plan/PlanChecks.svelte';
	import PlanForm from '$lib/components/plan/PlanForm.svelte';
	import PlanWarnings from '$lib/components/plan/PlanWarnings.svelte';
	import { formatDate } from '$lib/format';
	import { i18n, t, tp } from '$lib/i18n';
	import { getMeta } from '$lib/meta.svelte';
	import { checksForWeek, slotLabelLower, uniqueWarnings } from '$lib/plan/checks';
	import { isCalendarDate, todayInBudapest } from '$lib/plan/dates';
	import { dayLabel } from '$lib/plan/labels';
	import {
		DEFAULT_NO_REPEAT_DAYS,
		buildCheckRequest,
		buildSuggestRequest,
		clearMeal,
		dayDate,
		mealAt,
		freshSeed,
		nextSeed,
		planFromResponse,
		planLengthDays,
		planWeeks,
		setMeal,
		unknownPlanRecipeIds,
		type PlanLength
	} from '$lib/plan/plan';
	import { chainNameMap } from '$lib/plan/recipes';
	import { isPersistent, load, onExternalChange, update, type StoredPlan } from '$lib/storage';

	type CheckStatus = 'idle' | 'loading' | 'ready' | 'error';
	type Notice = 'replaced' | 'cleared' | 'restored';
	interface SuggestArgs {
		seed: number;
		startDate: string;
		days: number;
	}

	const meta = getMeta();

	let settings = $state(load());
	let persistent = $state(isPersistent());
	const plan = $derived(settings.plan);

	let recipes = $state<RecipesResponse | null>(null);
	let recipesError = $state<unknown>(null);
	let recipesLoading = $state(true);

	let startDate = $state(todayInBudapest());
	let length = $state<PlanLength>('week');

	let suggesting = $state(false);
	let suggestError = $state<unknown>(null);
	let lastSuggest: SuggestArgs | null = null;
	let suggestController: AbortController | null = null;
	let suggestSeq = 0;
	let warnings = $state<string[]>([]);

	let checks = $state<RuleCheckOut[]>([]);
	let checkStatus = $state<CheckStatus>('idle');
	let checkError = $state<unknown>(null);
	let checkController: AbortController | null = null;
	let checkSeq = 0;

	let picker = $state<{ dayIndex: number; slot: Slot } | null>(null);
	let notice = $state<Notice | null>(null);
	let previousPlan = $state<StoredPlan | null>(null);

	let planHeading = $state<HTMLElement>();
	let undoButton = $state<HTMLButtonElement>();
	let suggestRetry = $state<HTMLButtonElement>();

	const recipeById = $derived(new Map<string, RecipeSummary>((recipes?.recipes ?? []).map((r) => [r.id, r])));
	const knownIds = $derived(recipes ? new Set(recipes.recipes.map((r) => r.id)) : null);
	const names = $derived(chainNameMap(meta.data?.chains));
	const weeks = $derived(plan ? planWeeks(plan) : []);
	const unknownIds = $derived(plan && recipes ? unknownPlanRecipeIds(plan, recipes.recipes) : []);
	const exclusionCount = $derived(settings.exclusions.tags.length + settings.exclusions.ingredients.length);
	/** "2026. 10. 13. – 2026. 10. 19.", or one date when both ends are the same day; "" when undated. */
	function rangeText(first: string | null | undefined, last: string | null | undefined): string {
		const from = formatDate(first);
		const to = formatDate(last);
		if (!from || !to) return '';
		return from === to ? from : t('plan.plan_range', { from, to });
	}

	const planRange = $derived.by(() => {
		if (!plan || plan.startDate === null) return '';
		const last = plan.days.reduce((max, day) => Math.max(max, day.index), 0);
		return rangeText(plan.startDate, dayDate(plan, last));
	});
	const pickerTarget = $derived.by(() => {
		if (!picker || !plan) return null;
		const day = weeks.flatMap((week) => week.days).find((d) => d.index === picker?.dayIndex);
		if (!day) return null;
		return {
			...picker,
			label: t('plan.picker_target', { day: dayLabel(day, i18n.lang), slot: slotLabelLower(picker.slot, i18n.lang) }),
			currentId: mealAt(plan, picker.dayIndex, picker.slot) ?? null
		};
	});

	function savePlan(next: StoredPlan | null): void {
		settings = update({ plan: next });
		persistent = isPersistent();
	}

	function stopChecking(): void {
		checkController?.abort();
		checkController = null;
		checkSeq += 1;
	}

	async function loadRecipes(): Promise<void> {
		recipesLoading = true;
		recipesError = null;
		try {
			recipes = await getRecipes();
		} catch (error) {
			recipesError = error;
		} finally {
			recipesLoading = false;
		}
	}

	async function runCheck(): Promise<void> {
		stopChecking();
		const current = settings.plan;
		if (!current) {
			checks = [];
			checkStatus = 'idle';
			return;
		}
		const controller = new AbortController();
		checkController = controller;
		const seq = checkSeq;
		checkStatus = 'loading';
		checkError = null;
		try {
			const response = await postPlanCheck(buildCheckRequest(current, settings.people, knownIds), {
				signal: controller.signal
			});
			if (seq !== checkSeq) return;
			checks = response.checks;
			checkStatus = 'ready';
		} catch (error) {
			if (seq !== checkSeq) return;
			checkError = error;
			checkStatus = 'error';
		}
	}

	/** Leaving the page cancels a pending suggestion, so it can never overwrite a later edit. */
	function stopSuggesting(): void {
		suggestController?.abort();
		suggestController = null;
		suggestSeq += 1;
	}

	async function suggest(args: SuggestArgs): Promise<void> {
		lastSuggest = args;
		stopSuggesting();
		const controller = new AbortController();
		suggestController = controller;
		const seq = suggestSeq;
		suggesting = true;
		suggestError = null;
		const fresh = load();
		settings = fresh;
		try {
			const request = buildSuggestRequest({
				days: args.days,
				slots: fresh.slots,
				people: fresh.people,
				seed: args.seed,
				excludeTags: fresh.exclusions.tags,
				excludeIngredients: fresh.exclusions.ingredients
			});
			const response = await postPlanSuggest(request, { signal: controller.signal });
			if (seq !== suggestSeq) return;
			const next = planFromResponse(response, {
				startDate: args.startDate,
				seed: args.seed,
				slots: fresh.slots,
				noRepeatDays: request.no_repeat_days ?? DEFAULT_NO_REPEAT_DAYS,
				createdAt: new Date().toISOString()
			});
			const before = settings.plan;
			stopChecking();
			savePlan(next);
			checks = response.checks;
			checkStatus = 'ready';
			checkError = null;
			warnings = uniqueWarnings(response.warnings);
			previousPlan = before;
			notice = before ? 'replaced' : null;
			await tick();
			planHeading?.focus();
		} catch (error) {
			if (seq !== suggestSeq) return;
			suggestError = error;
			suggesting = false;
			// The pressed button stays where it was, but the way on is "Újra" in the error above it.
			await tick();
			suggestRetry?.focus();
		} finally {
			if (seq === suggestSeq) suggesting = false;
		}
	}

	function makePlan(): void {
		if (suggesting || !isCalendarDate(startDate)) return;
		void suggest({ seed: freshSeed(load().plan?.seed ?? null), startDate, days: planLengthDays(length, startDate) });
	}

	function newSuggestion(): void {
		if (suggesting || !plan) return;
		void suggest({
			seed: nextSeed(plan.seed),
			startDate: plan.startDate ?? todayInBudapest(),
			days: plan.days.length
		});
	}

	function retrySuggest(): void {
		if (lastSuggest) void suggest(lastSuggest);
	}

	async function clearPlan(): Promise<void> {
		if (suggesting || !plan) return;
		const before = plan;
		stopChecking();
		savePlan(null);
		checks = [];
		checkStatus = 'idle';
		warnings = [];
		picker = null;
		previousPlan = before;
		notice = 'cleared';
		await tick();
		undoButton?.focus();
	}

	async function undo(): Promise<void> {
		if (!previousPlan) return;
		savePlan(previousPlan);
		previousPlan = null;
		warnings = [];
		notice = 'restored';
		void runCheck();
		await tick();
		planHeading?.focus();
	}

	function editPlan(next: StoredPlan): void {
		if (next === settings.plan) return;
		savePlan(next);
		previousPlan = null;
		notice = null;
		void runCheck();
	}

	async function focusChangeButton(dayIndex: number, slot: Slot): Promise<void> {
		await tick();
		document.getElementById(`meal-change-${dayIndex}-${slot}`)?.focus();
	}

	function openPicker(dayIndex: number, slot: Slot): void {
		picker = { dayIndex, slot };
		// The picker needs the recipe list; after a failed load, try again (it opens once the list is here).
		if (!recipes && !recipesLoading) void loadRecipes();
	}

	function closePicker(): void {
		const target = picker;
		picker = null;
		if (target) void focusChangeButton(target.dayIndex, target.slot);
	}

	function pickMeal(recipeId: string): void {
		const target = picker;
		picker = null;
		// From the stored plan: another tab may have changed or deleted it since this page read it.
		const current = load().plan;
		if (!target || !current) return;
		const next = setMeal(current, target.dayIndex, target.slot, recipeId);
		if (next !== current) editPlan(next);
		void focusChangeButton(target.dayIndex, target.slot);
	}

	function removeMeal(dayIndex: number, slot: Slot): void {
		const current = load().plan;
		if (!current) return;
		const next = clearMeal(current, dayIndex, slot);
		if (next !== current) editPlan(next);
		void focusChangeButton(dayIndex, slot);
	}

	onMount(() => {
		void loadRecipes().then(() => {
			if (settings.plan) void runCheck();
		});
		const stopWatching = onExternalChange((next) => {
			const before = settings.plan;
			settings = next;
			persistent = isPersistent();
			if (!next.plan) picker = null;
			if (next.plan && JSON.stringify(next.plan) !== JSON.stringify(before)) void runCheck();
		});
		return () => {
			stopWatching();
			stopChecking();
			stopSuggesting();
		};
	});
</script>

<svelte:head>
	<title>{t('core.page_title', { page: t('plan.title') })}</title>
</svelte:head>

<h1>{t('plan.title')}</h1>

{#if !persistent}
	<p class="notice notice-warning" role="status">{t('plan.storage_unavailable')}</p>
{/if}

<div class="announce" role="status">
	{#if notice === 'replaced' || notice === 'cleared'}
		<p class="notice notice-success notice-row">
			<span>{notice === 'replaced' ? t('plan.replaced_notice') : t('plan.cleared_notice')}</span>
			{#if previousPlan}
				<button type="button" class="btn btn-secondary" bind:this={undoButton} onclick={undo}>{t('plan.undo')}</button>
			{/if}
		</p>
	{:else if notice === 'restored'}
		<p class="notice notice-success">{t('plan.restored_notice')}</p>
	{/if}
</div>

<p class="visually-hidden" role="status" data-testid="suggest-status">
	{#if suggesting}{t('plan.making_plan')}{/if}
</p>

{#if suggestError}
	<ErrorState
		error={suggestError}
		title={t('plan.suggest_error_title')}
		onretry={retrySuggest}
		bind:retryButton={suggestRetry}
	/>
{/if}

{#if plan}
	<section class="plan" aria-labelledby="plan-heading">
		<div class="plan-head">
			<h2 id="plan-heading" tabindex="-1" bind:this={planHeading}>{t('plan.plan_heading')}</h2>
			<p class="summary" data-testid="plan-summary">
				{planRange || t('plan.plan_undated')},
				{tp('plan.plan_days', plan.days.length)}, {tp('settings.people_value', settings.people)},
				{t('plan.slots_value', { count: plan.slots })}
			</p>
			<div class="btn-row">
				<button type="button" class="btn btn-primary" onclick={newSuggestion} aria-disabled={suggesting}>
					{suggesting ? t('plan.making_plan') : t('plan.new_suggestion')}
				</button>
				<button type="button" class="btn btn-secondary" onclick={clearPlan} aria-disabled={suggesting}>
					{t('plan.clear_plan')}
				</button>
				<a class="btn btn-secondary" href="/lista">{t('plan.to_list')}</a>
			</div>
		</div>

		<details class="other card">
			<summary class="disclosure">{t('plan.other_plan')}</summary>
			<PlanForm
				bind:startDate
				bind:length
				people={settings.people}
				slots={settings.slots}
				exclusions={exclusionCount}
				busy={suggesting}
				onsubmit={makePlan}
			/>
		</details>

		<PlanWarnings codes={warnings} />

		{#if recipesLoading}
			<Spinner showLabel />
		{:else}
			{#if recipesError}
				<ErrorState error={recipesError} title={t('plan.recipes_error_title')} onretry={loadRecipes} />
			{/if}
			{#if unknownIds.length > 0}
				<p class="notice notice-warning">{tp('plan.unknown_recipes', unknownIds.length)}</p>
			{/if}

			<div role="status">
				{#if checkStatus === 'loading'}
					<Spinner label={t('plan.checks_loading')} showLabel />
				{/if}
			</div>
			{#if checkStatus === 'error'}
				<ErrorState error={checkError} title={t('plan.checks_error')} onretry={runCheck} />
			{/if}

			{#each weeks as week (week.week)}
				{@const weekChecks = checksForWeek(checks, week.week)}
				{@const weekRange = rangeText(week.days[0]?.date, week.days.at(-1)?.date)}
				<section class="week" aria-labelledby="week-{week.week}" data-testid="plan-week-{week.week}">
					<h3 id="week-{week.week}">
						{t('plan.week_heading', { week: week.week + 1 })}
						{#if weekRange}
							<span class="range">{weekRange}</span>
						{/if}
					</h3>
					{#if weekChecks.length > 0}
						<div class="checks card" aria-busy={checkStatus === 'loading'}>
							<h4 id="week-{week.week}-checks">{t('plan.checks_title')}</h4>
							<PlanChecks checks={weekChecks} labelledBy="week-{week.week}-checks" />
						</div>
					{/if}
					<div class="days">
						{#each week.days as day (day.index)}
							<DayCard
								{day}
								recipes={recipeById}
								recipesLoaded={recipes !== null}
								{names}
								onchange={openPicker}
								onclear={removeMeal}
							/>
						{/each}
					</div>
				</section>
			{/each}

			{#if recipes}
				<Attribution dataDate={recipes.data_date} chainTypical />
			{/if}
		{/if}
	</section>
{:else}
	<section class="card new-plan" aria-labelledby="new-plan-heading">
		<h2 id="new-plan-heading">{t('plan.form_title')}</h2>
		<p class="muted">{t('plan.empty_title')}.</p>
		<PlanForm
			bind:startDate
			bind:length
			people={settings.people}
			slots={settings.slots}
			exclusions={exclusionCount}
			busy={suggesting}
			onsubmit={makePlan}
		/>
	</section>
{/if}

{#if pickerTarget && recipes}
	<MealPicker
		slot={pickerTarget.slot}
		target={pickerTarget.label}
		recipes={recipes.recipes}
		currentId={pickerTarget.currentId}
		excludedTags={settings.exclusions.tags}
		hasExcludedIngredients={settings.exclusions.ingredients.length > 0}
		{names}
		dataDate={recipes.data_date}
		onpick={pickMeal}
		onclose={closePicker}
	/>
{/if}

<style>
	.announce > :global(p) {
		margin: 0 0 var(--space-4);
	}

	.notice-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
	}

	.plan > :global(* + *) {
		margin-top: var(--space-4);
	}

	.plan-head h2 {
		margin-bottom: var(--space-1);
	}

	.plan-head h2:focus {
		outline: none;
	}

	.plan-head h2:focus-visible {
		outline: var(--focus-ring);
	}

	.summary {
		color: var(--color-text-muted);
	}

	.other {
		padding: 0 var(--space-4);
	}

	.other[open] {
		padding-bottom: var(--space-4);
	}

	summary {
		display: flex;
		align-items: center;
		min-height: var(--tap);
		font-weight: 600;
		cursor: pointer;
	}

	.week > :global(* + *) {
		margin-top: var(--space-3);
	}

	.week h3 {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 var(--space-3);
		margin-top: var(--space-5);
	}

	.range {
		font-size: var(--font-size-base);
		font-weight: 400;
		color: var(--color-text-muted);
	}

	.checks h4 {
		font-size: var(--font-size-base);
		margin: 0 0 var(--space-2);
	}

	.days > :global(* + *) {
		margin-top: var(--space-3);
	}

	.new-plan {
		margin-bottom: var(--space-4);
	}
</style>
