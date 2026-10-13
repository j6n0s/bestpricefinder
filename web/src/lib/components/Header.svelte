<!--
	App header: name, the price data date from /api/meta (with a warning when the data is stale) and the
	language switch. The data date is shown on every page, so the user always knows how fresh prices are.
-->
<script lang="ts">
	import { formatDate } from '$lib/format';
	import { i18n, setLanguage, t } from '$lib/i18n';
	import { getMeta } from '$lib/meta.svelte';
	import Badge from './Badge.svelte';
	import Spinner from './Spinner.svelte';

	const meta = getMeta();
	const dataDate = $derived(formatDate(meta.data?.data_date ?? null));
	const otherLang = $derived(i18n.lang === 'hu' ? 'en' : 'hu');

	function toggleLanguage(): void {
		setLanguage(otherLang);
	}
</script>

<header class="header">
	<div class="bar">
		<a class="brand" href="/">
			<svg class="logo" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
				<path d="M7.5 9.5 10.5 4M16.5 9.5 13.5 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
				<path d="M3 9.5h18l-2 10.5H5z" fill="currentColor" />
			</svg>
			<span>{t('core.app_name')}</span>
		</a>
		<button type="button" class="btn btn-secondary lang" lang={otherLang} onclick={toggleLanguage}>
			{t('core.lang_toggle_text')}
		</button>
	</div>
	<div class="status small" data-testid="data-status">
		{#if meta.status === 'ready' && meta.data}
			{#if dataDate}
				<span>{t('core.data_date', { date: dataDate })}</span>
				{#if meta.data.stale}
					<Badge kind="stale" />
				{/if}
			{:else}
				<span>{t('core.data_none')}</span>
			{/if}
		{:else if meta.status === 'error'}
			<span>{t('core.data_unavailable')}</span>
			<button type="button" class="btn btn-secondary retry" onclick={() => meta.reload()}>{t('core.retry')}</button>
		{:else}
			<Spinner label={t('core.data_loading')} showLabel />
		{/if}
	</div>
	{#if meta.status === 'ready' && meta.data?.stale && dataDate}
		<p class="notice notice-warning small stale" role="status">
			<strong>{t('core.data_stale')}.</strong>
			{t('core.data_stale_detail', { date: dataDate })}
		</p>
	{/if}
</header>

<style>
	.header {
		background: var(--color-surface);
		border-bottom: 1px solid var(--color-border-subtle);
		padding: var(--space-2) var(--space-4);
		padding-top: max(var(--space-2), env(safe-area-inset-top));
	}

	.bar,
	.status,
	.stale {
		max-width: var(--content-max);
		margin-inline: auto;
	}

	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
	}

	.brand {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		min-height: var(--tap);
		color: var(--color-text);
		font-weight: 700;
		font-size: var(--font-size-lg);
		text-decoration: none;
	}

	.logo {
		width: 1.75rem;
		height: 1.75rem;
		color: var(--color-primary);
	}

	.lang {
		flex: none;
	}

	.status {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2);
		min-height: var(--tap);
		color: var(--color-text-muted);
	}

	.retry {
		padding-block: 0;
	}

	.stale {
		margin-top: var(--space-2);
		margin-bottom: 0;
	}
</style>
