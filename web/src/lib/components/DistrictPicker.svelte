<!-- Budapest district select: the manual alternative to device location (BUILD-BRIEF §8.8). -->
<script lang="ts">
	import { DISTRICTS } from '$lib/districts';
	import { t } from '$lib/i18n';

	interface Props {
		/** "01".."23" or null. */
		value: string | null;
		onchange: (districtId: string | null) => void;
	}

	let { value, onchange }: Props = $props();
	const id = $props.id();

	function handleChange(event: Event & { currentTarget: HTMLSelectElement }): void {
		const next = event.currentTarget.value;
		onchange(next === '' ? null : next);
	}
</script>

<div class="field">
	<label for="{id}-district">{t('core.district_picker_label')}</label>
	<select id="{id}-district" class="select" value={value ?? ''} onchange={handleChange}>
		<option value="">{t('core.district_picker_none')}</option>
		{#each DISTRICTS as district (district.id)}
			<option value={district.id}>{t('core.district_name', { roman: district.roman })}</option>
		{/each}
	</select>
</div>
