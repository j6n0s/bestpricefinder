<!--
	"Melyik napokra vásárolsz?": this week, next week or the whole plan (the plan's own 7-day blocks, see
	$lib/list/range). A range without planned days is shown but cannot be chosen.
-->
<script lang="ts">
	import { formatDate } from '$lib/format';
	import { t, tp, type PlainKey } from '$lib/i18n';
	import { LIST_RANGES, rangeInfo, type ListRange, type RangeInfo } from '$lib/list/range';
	import type { StoredPlan } from '$lib/storage';

	interface Props {
		plan: StoredPlan;
		/** "YYYY-MM-DD" in Budapest. */
		today: string;
		value: ListRange;
		onchange: (range: ListRange) => void;
	}

	let { plan, today, value, onchange }: Props = $props();
	const id = $props.id();

	const LABELS: Record<ListRange, PlainKey> = {
		this_week: 'list.range_this_week',
		next_week: 'list.range_next_week',
		whole: 'list.range_whole'
	};

	const options = $derived(LIST_RANGES.map((range) => rangeInfo(plan, range, today)));

	function detail(info: RangeInfo): string {
		const days = info.dayIndexes.length;
		if (days === 0) return t('list.range_empty');
		const count = tp('list.range_days', days);
		if (info.from === null || info.to === null) return count;
		return `${t('list.range_dates', { from: formatDate(info.from), to: formatDate(info.to) })} · ${count}`;
	}
</script>

<fieldset class="choice-group range">
	<legend>{t('list.range_label')}</legend>
	{#each options as info (info.range)}
		<label class="choice" class:empty={info.dayIndexes.length === 0}>
			<input
				type="radio"
				name="{id}-range"
				value={info.range}
				checked={value === info.range}
				disabled={info.dayIndexes.length === 0}
				onchange={() => onchange(info.range)}
			/>
			<span class="text">
				<span class="label">{t(LABELS[info.range])}</span>
				<span class="detail small">{detail(info)}</span>
			</span>
		</label>
	{/each}
</fieldset>

<style>
	.text {
		display: flex;
		flex-direction: column;
	}

	.label {
		font-weight: 600;
	}

	.detail {
		color: var(--color-text-muted);
	}

	.empty {
		cursor: not-allowed;
	}

	.empty:hover {
		background: transparent;
	}
</style>
