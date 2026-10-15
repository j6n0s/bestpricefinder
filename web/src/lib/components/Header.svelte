<!--
	App header: the app's name (the way to the home page) and, at the right, the theme switch, the language
	switch and the cart (with how many goods it holds; the bottom bar has no cart tab). The price data date is
	not repeated here: every view that shows prices carries the source line with the date (Attribution,
	BUILD-BRIEF §8.2). The header speaks only when something is wrong: the prices are stale, there is no price
	data yet, or /api/meta failed.
	The cart count is read from the stored cart and follows every write (this tab's through `onChange`, another
	tab's through `onExternalChange`); goods that lost their store price are still counted until the cart page
	drops them.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { formatDate } from '$lib/format';
	import { i18n, setLanguage, t, tp } from '$lib/i18n';
	import { getMeta } from '$lib/meta.svelte';
	import { load, onChange, onExternalChange } from '$lib/storage';
	import { theme, toggleTheme } from '$lib/theme.svelte';

	const meta = getMeta();
	const dataDate = $derived(formatDate(meta.data?.data_date ?? null));
	const otherLang = $derived(i18n.lang === 'hu' ? 'en' : 'hu');
	const dark = $derived(theme.effective === 'dark');
	const cartActive = $derived(page.url.pathname === '/kosar' || page.url.pathname.startsWith('/kosar/'));

	let cartCount = $state(load().cart.lines.length);

	onMount(() => {
		cartCount = load().cart.lines.length;
		const follow = (state: { cart: { lines: unknown[] } }): void => {
			cartCount = state.cart.lines.length;
		};
		const stopOwn = onChange(follow);
		const stopOther = onExternalChange(follow);
		return () => {
			stopOwn();
			stopOther();
		};
	});

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
		<div class="controls">
			<!-- The switch names the theme it turns on; the icon is a sun for light, a crescent for dark. -->
			<button
				type="button"
				class="btn btn-secondary icon"
				aria-label={dark ? t('core.theme_to_light') : t('core.theme_to_dark')}
				onclick={toggleTheme}
				data-testid="theme-toggle"
			>
				{#if dark}
					<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
						<circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.8" />
						<path
							d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8"
							fill="none"
							stroke="currentColor"
							stroke-width="1.8"
							stroke-linecap="round"
						/>
					</svg>
				{:else}
					<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
						<path
							d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"
							fill="none"
							stroke="currentColor"
							stroke-width="1.8"
							stroke-linejoin="round"
						/>
					</svg>
				{/if}
			</button>
			<button type="button" class="btn btn-secondary lang" lang={otherLang} onclick={toggleLanguage}>
				{t('core.lang_toggle_text')}
			</button>
			<a
				href="/kosar"
				class="btn btn-secondary icon cart"
				class:active={cartActive}
				aria-current={cartActive ? 'page' : undefined}
				aria-label="{t('core.nav_cart')}, {tp('cart.cart_count', cartCount)}"
				data-testid="header-cart"
			>
				<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
					<path
						d="M3 4.5h2.4l2.4 10.5h10.4l2.1-7.5H6.2M10 19.5m-1.3 0a1.3 1.3 0 1 0 2.6 0a1.3 1.3 0 1 0-2.6 0M17 19.5m-1.3 0a1.3 1.3 0 1 0 2.6 0a1.3 1.3 0 1 0-2.6 0"
						fill="none"
						stroke="currentColor"
						stroke-width="1.8"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
				</svg>
				{#if cartCount > 0}
					<span class="count" aria-hidden="true" data-testid="header-cart-count">{cartCount}</span>
				{/if}
			</a>
		</div>
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

	/* The name at the left, the controls at the right; on the narrowest screens the controls take a second row. */
	.bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2) var(--space-3);
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

	.controls {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		margin-left: auto;
	}

	.lang {
		flex: none;
		padding-inline: var(--space-3);
	}

	/* The icon buttons: a 44 px square, the icon alone (its name is the accessible label). */
	.icon {
		flex: none;
		width: var(--tap);
		padding: 0;
	}

	.icon svg {
		width: 1.5rem;
		height: 1.5rem;
	}

	.cart {
		position: relative;
	}

	.cart.active {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	/* How many goods: a small pill on the basket's corner. */
	.count {
		position: absolute;
		top: -6px;
		right: -6px;
		min-width: 1.25rem;
		height: 1.25rem;
		padding: 0 0.3rem;
		border-radius: var(--radius-pill);
		background: var(--color-primary);
		color: var(--color-on-primary);
		font-size: 0.6875rem;
		font-weight: 700;
		line-height: 1.25rem;
		text-align: center;
	}

	@media (max-width: 29.99rem) {
		.brand {
			font-size: var(--font-size-lg);
		}
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
