<!--
	"Hozzáadás a tervhez": puts the recipe into one day and slot of the plan stored on this device
	($lib/storage). Only the plan's slots that the recipe is meant for are offered. Without a plan, adding
	starts a 7-day plan from today with every other meal empty.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import type { RecipeSummary, Slot } from '$lib/api/types';
	import { i18n, t } from '$lib/i18n';
	import { slotLabelLower } from '$lib/plan/checks';
	import { todayInBudapest } from '$lib/plan/dates';
	import { dayLabel } from '$lib/plan/labels';
	import {
		DEFAULT_NO_REPEAT_DAYS,
		PLAN_WEEK_DAYS,
		emptyPlan,
		mealAt,
		planWeeks,
		setMeal,
		slotsFor,
		type SlotCount
	} from '$lib/plan/plan';
	import { isPersistent, load, onExternalChange, update, type StoredPlan } from '$lib/storage';

	interface Props {
		recipe: Pick<RecipeSummary, 'id' | 'slots'>;
	}

	let { recipe }: Props = $props();

	let stored = $state(load());
	let persistent = $state(isPersistent());
	let done = $state<{ day: string; slot: string } | null>(null);

	// Another tab changed or deleted the plan: show what is stored now (adding always starts from load()).
	onMount(() =>
		onExternalChange((next) => {
			stored = next;
			persistent = isPersistent();
		})
	);

	function newPlan(slots: SlotCount, createdAt: string): StoredPlan {
		return emptyPlan(
			{ startDate: todayInBudapest(), seed: 0, slots, noRepeatDays: DEFAULT_NO_REPEAT_DAYS, createdAt },
			PLAN_WEEK_DAYS
		);
	}

	/** The plan the choice applies to: the stored one, or the 7-day plan that adding would start. */
	const target = $derived(stored.plan ?? newPlan(stored.slots, new Date(0).toISOString()));
	const days = $derived(planWeeks(target).flatMap((week) => week.days));
	const slotOptions = $derived(slotsFor(target.slots).filter((slot) => recipe.slots.includes(slot)));

	function initialDay(): number {
		const today = todayInBudapest();
		return days.find((day) => day.date === today)?.index ?? days[0]?.index ?? 0;
	}

	function initialSlot(): Slot | null {
		return slotOptions[0] ?? null;
	}

	let dayIndex = $state(initialDay());
	let slot = $state<Slot | null>(initialSlot());

	const selectedDay = $derived(days.find((day) => day.index === dayIndex) ?? days[0]);
	const selectedSlot = $derived(slot !== null && slotOptions.includes(slot) ? slot : (slotOptions[0] ?? null));
	const current = $derived(
		selectedDay && selectedSlot ? mealAt(target, selectedDay.index, selectedSlot) : undefined
	);
	const recipeSlots = $derived(recipe.slots.map((s) => slotLabelLower(s, i18n.lang)).join(', '));

	function add(): void {
		if (!selectedDay || !selectedSlot) return;
		const fresh = load();
		const base = fresh.plan ?? newPlan(fresh.slots, new Date().toISOString());
		const next = setMeal(base, selectedDay.index, selectedSlot, recipe.id);
		const label = { day: dayLabel(selectedDay, i18n.lang), slot: slotLabelLower(selectedSlot, i18n.lang) };
		if (next === base) {
			// Unchanged: the recipe is already there, or the plan (or the settings) changed in another tab and the
			// chosen day or slot no longer exists. Nothing is saved; the choices are refreshed from storage.
			stored = fresh;
			done = mealAt(base, selectedDay.index, selectedSlot) === recipe.id ? label : null;
			return;
		}
		stored = update({ plan: next });
		persistent = isPersistent();
		done = label;
	}
</script>

<div class="add" data-testid="add-to-plan">
	{#if !persistent}
		<p class="notice notice-warning" role="status">{t('plan.storage_unavailable')}</p>
	{/if}
	{#if slotOptions.length === 0}
		<p>{t('recipes.add_no_slot', { slots: recipeSlots })}</p>
		<p class="muted">{t('recipes.add_no_slot_hint')} <a href="/beallitasok">{t('plan.settings_link')}</a></p>
	{:else}
		{#if !stored.plan}
			<p class="muted">{t('recipes.add_no_plan')}</p>
		{/if}
		<div class="grid">
			<div class="field">
				<label for="add-day">{t('recipes.add_day_label')}</label>
				<select id="add-day" class="select" bind:value={dayIndex} onchange={() => (done = null)}>
					{#each days as day (day.index)}
						<option value={day.index}>{dayLabel(day, i18n.lang)}</option>
					{/each}
				</select>
			</div>
			<div class="field">
				<label for="add-slot">{t('recipes.add_slot_label')}</label>
				<select id="add-slot" class="select" bind:value={slot} onchange={() => (done = null)}>
					{#each slotOptions as option (option)}
						<option value={option}>{slotLabelLower(option, i18n.lang)}</option>
					{/each}
				</select>
			</div>
		</div>
		{#if current === recipe.id}
			<p class="small muted">{t('recipes.add_already')}</p>
		{:else if typeof current === 'string'}
			<p class="small muted">{t('recipes.add_replaces')}</p>
		{/if}
		<button type="button" class="btn btn-primary" onclick={add}>
			{t('recipes.add_button')}
		</button>
	{/if}
	<div role="status">
		{#if done}
			<p class="notice notice-success done">
				<span>{t('recipes.add_done', done)}</span>
				<a href="/terv">{t('recipes.add_open_plan')}</a>
			</p>
		{/if}
	</div>
</div>

<style>
	.add > :global(* + *) {
		margin-top: var(--space-3);
	}

	.add p {
		margin-bottom: 0;
	}

	.grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--space-3);
	}

	@media (min-width: 40rem) {
		.grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	.done {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-3);
	}

	.done a {
		color: inherit;
		font-weight: 600;
	}

	.add a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}
</style>
