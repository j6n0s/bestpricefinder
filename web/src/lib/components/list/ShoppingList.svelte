<!--
	The shopping list itself: the lines to buy grouped by shop section (docs/DATA.md order) with check-off
	boxes, the "valószínűleg otthon van" section with a "nincs otthon" toggle per staple (none for tap water),
	the ingredients excluded in the settings (with "mégis megveszem"), and the lines removed by hand. No prices
	here (so no attribution is needed); the prices are in "Hol a legolcsóbb a közelben?". Every change is
	reported to the page, which saves it on this device only. Ingredient names come from the content, which is
	Hungarian only, so they carry lang="hu" (WCAG 3.1.2) in the English UI too.
-->
<script lang="ts">
	import { tick } from 'svelte';
	import type { ListLineOut } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import { i18n, t, tp } from '$lib/i18n';
	import { groupLabelKey, groupLines } from '$lib/list/groups';
	import { canBeBought, isBought, isIncludedExclusion, lineKind, listSections, type LineChoices } from '$lib/list/lines';
	import { formatAmount } from '$lib/list/packs';

	interface Props {
		lines: readonly ListLineOut[];
		choices: LineChoices;
		checked: ReadonlySet<string>;
		ontogglecheck: (ingredientId: string, on: boolean) => void;
		onclearchecks: () => void;
		onremove: (ingredientId: string) => void;
		onrestore: (ingredientId: string) => void;
		onnotathome: (ingredientId: string, notAtHome: boolean) => void;
		/** "Mégis megveszem": an ingredient excluded in the settings goes on this list after all. */
		oninclude: (ingredientId: string) => void;
	}

	let { lines, choices, checked, ontogglecheck, onclearchecks, onremove, onrestore, onnotathome, oninclude }: Props =
		$props();
	const id = $props.id();

	let root = $state<HTMLDivElement>();
	let summaryLine = $state<HTMLParagraphElement>();

	const sections = $derived(listSections(lines, choices));
	/** Lines to buy: the non-pantry lines plus the staples marked "nincs otthon", grouped by section. */
	const bought = $derived(lines.filter((line) => isBought(line, choices)));
	const groups = $derived(groupLines(bought));
	const doneCount = $derived(bought.filter((line) => checked.has(line.ingredient_id)).length);

	function amount(line: ListLineOut): string {
		return formatAmount(line.qty, line.unit, i18n.lang);
	}

	async function remove(ingredientId: string): Promise<void> {
		const checks = root ? [...root.querySelectorAll<HTMLInputElement>('input[data-line-check]')] : [];
		const index = checks.findIndex((input) => input.dataset.lineCheck === ingredientId);
		onremove(ingredientId);
		await tick();
		// Focus the line that took the removed line's place, else the previous one, else the removed section.
		const after = root ? [...root.querySelectorAll<HTMLElement>('input[data-line-check]')] : [];
		const target = after[Math.min(Math.max(index, 0), after.length - 1)] ?? root?.querySelector<HTMLElement>('summary');
		target?.focus();
	}

	/** After "Pipák törlése" the button is gone: focus the first box (or the summary), never <body>. */
	async function clearChecks(): Promise<void> {
		onclearchecks();
		await tick();
		const target = root?.querySelector<HTMLElement>('input[data-line-check]') ?? summaryLine;
		target?.focus();
	}

	async function include(ingredientId: string): Promise<void> {
		oninclude(ingredientId);
		await tick();
		const target =
			root?.querySelector<HTMLElement>(`input[data-line-check="${CSS.escape(ingredientId)}"]`) ?? summaryLine;
		target?.focus();
	}

	async function restore(ingredientId: string): Promise<void> {
		onrestore(ingredientId);
		await tick();
		const target =
			root?.querySelector<HTMLElement>(`input[data-line-check="${CSS.escape(ingredientId)}"]`) ??
			root?.querySelector<HTMLElement>('summary');
		target?.focus();
	}
</script>

<div class="shopping-list" bind:this={root}>
	<div class="summary">
		<p tabindex="-1" bind:this={summaryLine} data-testid="list-summary">
			<strong>{tp('list.summary', bought.length)}</strong>
			{#if bought.length > 0}
				<span class="muted">· {t('list.checked_count', { done: doneCount, total: bought.length })}</span>
			{/if}
		</p>
		{#if doneCount > 0}
			<button type="button" class="btn btn-secondary" onclick={clearChecks}>{t('list.clear_checks')}</button>
		{/if}
	</div>

	{#if bought.length === 0}
		<p class="notice notice-info">{t('list.nothing_to_buy')}</p>
	{/if}

	{#each groups as group (group.group)}
		<section class="group" aria-labelledby="{id}-{group.group}">
			<h2 id="{id}-{group.group}">{t(groupLabelKey(group.group))}</h2>
			<ul class="lines">
				{#each group.lines as line (line.ingredient_id)}
					{@const done = checked.has(line.ingredient_id)}
					<li class="line" class:done>
						<label class="check">
							<input
								type="checkbox"
								checked={done}
								data-line-check={line.ingredient_id}
								onchange={(event) => ontogglecheck(line.ingredient_id, event.currentTarget.checked)}
							/>
							<span class="name" lang="hu">{line.name_hu}</span>
							<span class="qty">{amount(line)}</span>
						</label>
						{#if isIncludedExclusion(line, choices)}
							<Badge tone="warning">{t('list.line_excluded')}</Badge>
						{/if}
						{#if lineKind(line, choices) === 'pantry_missing'}
							<Badge tone="neutral">{t('list.line_not_at_home')}</Badge>
						{:else}
							<button
								type="button"
								class="btn btn-secondary icon"
								aria-label={t('list.remove_line', { name: line.name_hu })}
								onclick={() => remove(line.ingredient_id)}
							>
								<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">
									<path
										d="M6 6l12 12M18 6 6 18"
										fill="none"
										stroke="currentColor"
										stroke-width="2"
										stroke-linecap="round"
									/>
								</svg>
							</button>
						{/if}
					</li>
				{/each}
			</ul>
		</section>
	{/each}

	{#if sections.pantry.length > 0}
		<section class="group pantry" aria-labelledby="{id}-pantry">
			<h2 id="{id}-pantry">{t('list.pantry_title')}</h2>
			<p class="small muted">{t('list.pantry_note')}</p>
			<ul class="lines">
				{#each sections.pantry as line (line.ingredient_id)}
					{@const missing = lineKind(line, choices) === 'pantry_missing'}
					<li class="line">
						<span class="item">
							<span class="name" lang="hu">{line.name_hu}</span>
							<span class="qty">{amount(line)}</span>
							{#if missing}
								<Badge tone="info">{t('list.pantry_on_list')}</Badge>
							{/if}
						</span>
						{#if canBeBought(line.ingredient_id)}
							<label class="choice toggle">
								<input
									type="checkbox"
									checked={missing}
									aria-label={t('list.not_at_home_named', { name: line.name_hu })}
									onchange={(event) => onnotathome(line.ingredient_id, event.currentTarget.checked)}
								/>
								<span>{t('list.not_at_home')}</span>
							</label>
						{/if}
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	{#if sections.excluded.length > 0}
		<section class="group excluded" aria-labelledby="{id}-excluded" data-testid="excluded-lines">
			<h2 id="{id}-excluded">{t('list.excluded_title')}</h2>
			<p class="small muted">{t('list.excluded_note')}</p>
			<ul class="lines">
				{#each sections.excluded as line (line.ingredient_id)}
					<li class="line">
						<span class="item">
							<span class="name" lang="hu">{line.name_hu}</span>
							<span class="qty">{amount(line)}</span>
						</span>
						<button
							type="button"
							class="btn btn-secondary"
							aria-label={t('list.buy_anyway_named', { name: line.name_hu })}
							onclick={() => include(line.ingredient_id)}>{t('list.buy_anyway')}</button
						>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	{#if sections.removed.length > 0}
		<details class="removed">
			<summary>{t('list.removed_title', { count: sections.removed.length })}</summary>
			<p class="small muted">{t('list.removed_note')}</p>
			<ul class="lines">
				{#each sections.removed as line (line.ingredient_id)}
					<li class="line">
						<span class="item">
							<span class="name" lang="hu">{line.name_hu}</span>
							<span class="qty">{amount(line)}</span>
						</span>
						<button
							type="button"
							class="btn btn-secondary"
							aria-label={t('list.restore_line_named', { name: line.name_hu })}
							onclick={() => restore(line.ingredient_id)}>{t('list.restore_line')}</button
						>
					</li>
				{/each}
			</ul>
		</details>
	{/if}
</div>

<style>
	.summary {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2) var(--space-3);
		margin-bottom: var(--space-3);
	}

	.summary p {
		margin: 0;
	}

	.summary p:focus {
		outline: none;
	}

	.summary p:focus-visible {
		outline: var(--focus-ring);
	}

	.group {
		margin-top: var(--space-5);
	}

	.group h2 {
		font-size: var(--font-size-lg);
		margin-bottom: var(--space-2);
	}

	.lines {
		list-style: none;
		margin: 0;
		padding: 0;
		background: var(--color-surface);
		border: 1px solid var(--color-border-subtle);
		border-radius: var(--radius-lg);
	}

	.line {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: var(--space-2);
		padding: var(--space-1) var(--space-2) var(--space-1) var(--space-3);
		min-height: var(--tap);
	}

	.line + .line {
		border-top: 1px solid var(--color-border-subtle);
	}

	.check {
		display: flex;
		align-items: center;
		flex: 1 1 12rem;
		gap: var(--space-3);
		min-height: var(--tap);
		min-width: 0;
		cursor: pointer;
	}

	.check input {
		width: 1.25rem;
		height: 1.25rem;
		margin: 0;
		flex: none;
		accent-color: var(--color-primary);
	}

	.item {
		display: flex;
		flex: 1 1 10rem;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1) var(--space-3);
		min-width: 0;
	}

	.name {
		flex: 1 1 auto;
		min-width: 0;
	}

	.qty {
		color: var(--color-text-muted);
		white-space: nowrap;
	}

	.done .name {
		text-decoration: line-through;
		color: var(--color-text-muted);
	}

	.icon {
		padding: 0;
		width: var(--tap);
		flex: none;
	}

	.toggle {
		flex: none;
	}

	.removed {
		margin-top: var(--space-5);
	}

	.removed summary {
		/* list-item keeps the disclosure marker; the padding makes a 44 px target. */
		padding: 10px 0;
		cursor: pointer;
		font-weight: 600;
	}

	.removed .lines {
		margin-top: var(--space-2);
	}
</style>
