<!--
	Main navigation: a fixed bottom tab bar on narrow screens, a plain row under the header on wide ones.
	Icons are simple original line drawings; every tab has a visible text label. Four tabs: the home page is
	reached through the app name in the header, and the cart through the header's basket button.
	While the bar is fixed, its real height (it grows when the user enlarges text or spacing) is published as
	`--nav-reserved` on <html>, so the layout's bottom padding and scroll padding keep content clear of it.
	(A CSSOM write, which the CSP allows; no style attribute in the markup.)
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { t, type PlainKey } from '$lib/i18n';

	interface Item {
		href: string;
		label: PlainKey;
		/** SVG path data on a 24×24 grid, stroked. */
		icon: string;
	}

	const ITEMS: readonly Item[] = [
		{ href: '/terv', label: 'core.nav_plan', icon: 'M4 6h16v14H4zM4 10h16M8.5 3.5v4M15.5 3.5v4M8 14h3M13 14h3M8 17h3' },
		{
			href: '/receptek',
			label: 'core.nav_recipes',
			icon: 'M12 6.5C10 5 7 4.5 4 5v13.5c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5V5c-3-.5-6 0-8 1.5zM12 6.5V20'
		},
		{ href: '/lista', label: 'core.nav_list', icon: 'M10 6.5h10M10 12h10M10 17.5h10M4 6.5l1.5 1.5L8 5.5M4.5 12h2M4.5 17.5h2' },
		{
			href: '/beallitasok',
			label: 'core.nav_settings',
			icon: 'M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4'
		}
	];

	let nav = $state<HTMLElement>();

	onMount(() => {
		const element = nav;
		if (!element || typeof ResizeObserver === 'undefined') return;
		const root = document.documentElement;
		const publish = (): void => {
			if (getComputedStyle(element).position === 'fixed') {
				root.style.setProperty('--nav-reserved', `${Math.ceil(element.getBoundingClientRect().height)}px`);
			} else {
				root.style.removeProperty('--nav-reserved');
			}
		};
		const observer = new ResizeObserver(publish);
		observer.observe(element);
		publish();
		return () => {
			observer.disconnect();
			root.style.removeProperty('--nav-reserved');
		};
	});

	function isActive(href: string, pathname: string): boolean {
		if (href === '/') return pathname === '/';
		return pathname === href || pathname.startsWith(`${href}/`);
	}
</script>

<nav class="nav" aria-label={t('core.nav_label')} bind:this={nav}>
	<ul>
		{#each ITEMS as item (item.href)}
			{@const active = isActive(item.href, page.url.pathname)}
			<li>
				<a href={item.href} class:active aria-current={active ? 'page' : undefined}>
					<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
						<path
							d={item.icon}
							fill="none"
							stroke="currentColor"
							stroke-width="1.8"
							stroke-linecap="round"
							stroke-linejoin="round"
						/>
					</svg>
					<span class="label">{t(item.label)}</span>
				</a>
			</li>
		{/each}
	</ul>
</nav>

<style>
	.nav {
		background: var(--color-surface);
		border-top: 1px solid var(--color-border-subtle);
	}

	ul {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		max-width: var(--content-max);
		margin: 0 auto;
		padding: 0;
		list-style: none;
	}

	a {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		min-height: var(--nav-height);
		min-width: var(--tap);
		padding: var(--space-1) 0;
		color: var(--color-text-muted);
		font-size: 0.75rem;
		line-height: 1.2;
		text-align: center;
		text-decoration: none;
	}

	@media (hover: hover) {
		a:hover {
			color: var(--color-text);
			background: var(--color-surface-alt);
		}
	}

	a:focus-visible {
		outline-offset: -3px;
	}

	a.active {
		color: var(--color-primary);
		font-weight: 700;
	}

	svg {
		width: 1.5rem;
		height: 1.5rem;
		flex: none;
	}

	/*
	 * Labels wrap between words. A word breaks (hyphenated where the browser can, html lang="hu") only when it
	 * cannot fit its cell at all: with user text spacing (WCAG 1.4.12) or text-only zoom, "Beállítások" must
	 * not be cut off or run into the next tab. At default metrics every word fits (the e2e tests check both).
	 */
	.label {
		max-width: 100%;
		overflow-wrap: anywhere;
		hyphens: auto;
	}

	@media (max-width: 22.49rem) {
		a {
			font-size: 0.6875rem;
			letter-spacing: -0.01em;
		}
	}

	/* Narrow screens: fixed bottom tab bar (the layout reserves its height). */
	@media (max-width: 47.99rem) {
		.nav {
			position: fixed;
			left: 0;
			right: 0;
			bottom: 0;
			z-index: 10;
			padding: 0 env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
		}
	}

	/* Wide screens: a row of tabs under the header. */
	@media (min-width: 48rem) {
		.nav {
			border-top: 0;
			border-bottom: 1px solid var(--color-border-subtle);
		}

		a {
			flex-direction: row;
			gap: var(--space-2);
			min-height: var(--tap);
			font-size: var(--font-size-sm);
		}

		a.active {
			box-shadow: inset 0 -3px 0 var(--color-primary);
		}
	}
</style>
