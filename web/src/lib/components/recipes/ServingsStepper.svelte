<!--
	Servings stepper (− 4 adag +). At a bound the button stays focusable (aria-disabled) and does nothing,
	like the people stepper in the settings.
-->
<script lang="ts">
	import { t, tp } from '$lib/i18n';
	import { SERVINGS_MAX, SERVINGS_MIN } from '$lib/plan/recipes';

	interface Props {
		value: number;
		onchange: (value: number) => void;
	}

	let { value, onchange }: Props = $props();

	function step(delta: number): void {
		const next = value + delta;
		if (next < SERVINGS_MIN || next > SERVINGS_MAX) return;
		onchange(next);
	}
</script>

<div class="field">
	<span class="field-label" id="servings-label">{t('recipes.servings_label')}</span>
	<div class="stepper" role="group" aria-labelledby="servings-label">
		<button
			type="button"
			class="btn btn-secondary"
			aria-label={t('recipes.servings_decrease')}
			aria-disabled={value <= SERVINGS_MIN}
			onclick={() => step(-1)}>−</button
		>
		<output aria-live="polite" data-testid="servings-value">{tp('recipes.servings', value)}</output>
		<button
			type="button"
			class="btn btn-secondary"
			aria-label={t('recipes.servings_increase')}
			aria-disabled={value >= SERVINGS_MAX}
			onclick={() => step(1)}>+</button
		>
	</div>
</div>

<style>
	.stepper {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}

	.stepper .btn {
		font-size: var(--font-size-xl);
		padding: 0;
		width: var(--tap);
	}

	.stepper .btn[aria-disabled='true'] {
		opacity: 0.6;
		cursor: not-allowed;
	}

	output {
		min-width: 6rem;
		text-align: center;
		font-weight: 600;
	}
</style>
