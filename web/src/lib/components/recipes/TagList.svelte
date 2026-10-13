<!-- A recipe's tags as small neutral labels (descriptive only, never a health claim). -->
<script lang="ts">
	import { t } from '$lib/i18n';
	import { tagLabelKey } from '$lib/plan/recipes';

	interface Props {
		tags: readonly string[];
	}

	let { tags }: Props = $props();

	// Tags outside the vocabulary are not shown: their wording has not been reviewed.
	const labels = $derived(
		tags.flatMap((tag) => {
			const key = tagLabelKey(tag);
			return key ? [{ tag, key }] : [];
		})
	);
</script>

{#if labels.length > 0}
	<ul class="tags" aria-label={t('recipes.tags_label')}>
		{#each labels as { tag, key } (tag)}
			<li>{t(key)}</li>
		{/each}
	</ul>
{/if}

<style>
	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-2);
		list-style: none;
		margin: 0;
		padding: 0;
	}

	li {
		padding: 0 var(--space-2);
		border-radius: var(--radius-pill);
		background: var(--color-neutral-bg);
		color: var(--color-neutral-text);
		font-size: var(--font-size-sm);
		line-height: 1.6;
	}
</style>
