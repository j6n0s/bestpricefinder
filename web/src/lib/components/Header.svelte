<!--
	App header: the app's name and the language switch. The price data date is not repeated here: every view
	that shows prices carries the source line with the date (Attribution, BUILD-BRIEF §8.2). The header speaks
	only when something is wrong: the prices are stale, there is no price data yet, or /api/meta failed.
-->
<script lang="ts">
	import { formatDate } from '$lib/format';
	import { i18n, setLanguage, t } from '$lib/i18n';
	import { getMeta } from '$lib/meta.svelte';

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
	{#if meta.status === 'ready' && meta.data && !dataDate}
		<p class="status small" data-testid="data-status">{t('core.data_none')}</p>
	{:else if meta.status === 'error'}
		<div class="status small" data-testid="data-status">
			<span>{t('core.data_unavailable')}</span>
			<button type="button" class="btn btn-secondary retry" onclick={() => meta.reload()}>{t('core.retry')}</button>
		</div>
	{/if}
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
		/* The same column as <main> (whose padding is inside its max-width). */
		max-width: calc(var(--content-max) - 2 * var(--space-4));
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
		font-family: var(--font-title);
		font-weight: 700;
		font-size: var(--font-size-xl);
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
