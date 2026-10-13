<!--
	"Új terv": start date (default today) and length (one week, or up to the end of the month), plus the
	household settings the suggestion uses. Submitting calls `onsubmit`; the page talks to the API.
-->
<script lang="ts">
	import { i18n, t, tp } from '$lib/i18n';
	import { isCalendarDate, weekdayIndex } from '$lib/plan/dates';
	import { dayLabel } from '$lib/plan/labels';
	import { planLengthDays, type PlanLength, type SlotCount } from '$lib/plan/plan';

	interface Props {
		startDate: string;
		length: PlanLength;
		people: number;
		slots: SlotCount;
		exclusions: number;
		busy: boolean;
		onsubmit: () => void;
	}

	let {
		startDate = $bindable(),
		length = $bindable(),
		people,
		slots,
		exclusions,
		busy,
		onsubmit
	}: Props = $props();

	const valid = $derived(isCalendarDate(startDate));
	const monthDays = $derived(valid ? planLengthDays('month', startDate) : null);
	/** The chosen date in hu-HU form ("Kedd, 2026. 10. 13."): the native date field uses the browser's format. */
	const chosen = $derived(valid ? dayLabel({ index: 0, date: startDate, weekday: weekdayIndex(startDate) }, i18n.lang) : '');

	function submit(event: SubmitEvent): void {
		event.preventDefault();
		if (valid && !busy) onsubmit();
	}
</script>

<form class="plan-form" onsubmit={submit} novalidate data-testid="plan-form">
	<div class="field">
		<label for="plan-start">{t('plan.start_label')}</label>
		<input
			id="plan-start"
			class="input"
			type="date"
			bind:value={startDate}
			required
			aria-invalid={!valid}
			aria-describedby={valid ? 'plan-start-chosen' : 'plan-start-error'}
		/>
		{#if valid}
			<p id="plan-start-chosen" class="small muted" data-testid="plan-start-chosen">{chosen}</p>
		{:else}
			<p id="plan-start-error" class="error small">{t('plan.start_invalid')}</p>
		{/if}
	</div>

	<fieldset class="choice-group">
		<legend>{t('plan.length_label')}</legend>
		<label class="choice">
			<input type="radio" name="plan-length" value="week" bind:group={length} />
			<span>{t('plan.length_week')}</span>
		</label>
		<label class="choice">
			<input type="radio" name="plan-length" value="month" bind:group={length} disabled={monthDays === null} />
			<span>{monthDays === null ? t('plan.length_month_other', { count: '–' }) : tp('plan.length_month', monthDays)}</span>
		</label>
	</fieldset>

	<p class="household">
		<strong>{t('plan.household_label')}:</strong>
		{tp('settings.people_value', people)}, {t('plan.slots_value', { count: slots })}{#if exclusions > 0}, {tp(
				'plan.exclusions_value',
				exclusions
			)}{/if}.
		<a href="/beallitasok">{t('plan.settings_link')}</a>
	</p>

	<!-- aria-disabled, not disabled: a disabled button loses focus (to <body>) the moment it is pressed. -->
	<button type="submit" class="btn btn-primary" aria-disabled={busy || !valid}>
		{busy ? t('plan.making_plan') : t('plan.make_plan')}
	</button>
</form>

<style>
	.plan-form > :global(* + *) {
		margin-top: var(--space-4);
	}

	.field p {
		margin: 0;
	}

	.error {
		color: var(--color-danger);
	}

	.household {
		margin-bottom: 0;
	}

	.household a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}
</style>
