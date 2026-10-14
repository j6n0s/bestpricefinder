<!--
	App shell: skip link, header (data status), offline notice, page content, footer (disclaimer + sources link)
	and the bottom navigation. /api/meta is loaded once here and shared with every page via context
	(`getMeta()` from $lib/meta.svelte).
-->
<script lang="ts">
	import '../app.css';
	import { onMount, type Snippet } from 'svelte';
	import { dev } from '$app/environment';
	import BottomNav from '$lib/components/BottomNav.svelte';
	import Disclaimer from '$lib/components/Disclaimer.svelte';
	import Header from '$lib/components/Header.svelte';
	import { i18n, syncDocumentLang, t } from '$lib/i18n';
	import { MetaStore, provideMeta } from '$lib/meta.svelte';

	let { children }: { children: Snippet } = $props();

	const meta = provideMeta(new MetaStore());
	let online = $state(true);

	$effect(() => {
		syncDocumentLang(i18n.lang);
	});

	function registerServiceWorker(): void {
		// Offline support is optional: a refused registration (private mode, blocked) must not break the app.
		navigator.serviceWorker.register('/service-worker.js', { type: 'classic' }).catch(() => undefined);
	}

	onMount(() => {
		void meta.load();
		online = navigator.onLine;
		const onConnectivity = (): void => {
			online = navigator.onLine;
			if (online && meta.status === 'error') void meta.reload();
		};
		addEventListener('online', onConnectivity);
		addEventListener('offline', onConnectivity);

		if (!dev && 'serviceWorker' in navigator) {
			if (document.readyState === 'complete') registerServiceWorker();
			else addEventListener('load', registerServiceWorker, { once: true });
		}

		return () => {
			removeEventListener('online', onConnectivity);
			removeEventListener('offline', onConnectivity);
			removeEventListener('load', registerServiceWorker);
		};
	});
</script>

<a class="skip-link" href="#main">{t('core.skip_to_content')}</a>

<div class="shell">
	<Header />
	<BottomNav />
	{#if !online}
		<p class="notice notice-warning offline" role="status">{t('core.offline')}</p>
	{/if}
	<main id="main" tabindex="-1">
		{@render children()}
	</main>
	<footer class="footer">
		<Disclaimer />
		<p><a href="/forrasok">{t('core.footer_sources')}</a></p>
	</footer>
</div>

<style>
	.shell {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		min-height: 100dvh;
		/* viewport-fit=cover: keep content clear of notches in landscape. */
		padding-left: env(safe-area-inset-left);
		padding-right: env(safe-area-inset-right);
	}

	main {
		flex: 1;
		width: 100%;
		max-width: var(--content-max);
		margin: 0 auto;
		padding: var(--space-5) var(--space-4);
	}

	main:focus {
		outline: none;
	}

	.offline {
		max-width: var(--content-max);
		margin: var(--space-3) auto 0;
		width: calc(100% - 2 * var(--space-4));
	}

	.footer {
		max-width: var(--content-max);
		width: 100%;
		margin: 0 auto;
		padding: var(--space-4);
		border-top: 1px solid var(--color-border-subtle);
		font-size: var(--font-size-sm);
	}

	.footer p {
		margin: var(--space-2) 0 0;
	}

	/* A page that shows the disclaimer itself (the sources page) hides the footer's copy, so it is not repeated a
	   few lines below. Every other page, the price views included, shows it once, in the footer. */
	.shell:global(:has(main [data-testid='disclaimer'])) .footer :global([data-testid='disclaimer']) {
		display: none;
	}

	.footer a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}

	/* Narrow screens: keep content clear of the fixed bottom tab bar. */
	@media (max-width: 47.99rem) {
		.shell {
			/* --nav-reserved: the bar's measured height (BottomNav), e.g. with enlarged text. */
			padding-bottom: var(--nav-reserved, calc(var(--nav-height) + env(safe-area-inset-bottom)));
		}
	}
</style>
