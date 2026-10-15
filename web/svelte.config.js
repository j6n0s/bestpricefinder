// @ts-check
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/**
 * The one inline script of src/app.html (it applies the stored theme before the first paint), allowed by its
 * sha256 hash like SvelteKit's own bootstrap script. The hash is computed from the file at build time, so an
 * edit of the script never leaves a stale hash behind.
 */
function themeScriptHash() {
	const html = readFileSync(new URL('./src/app.html', import.meta.url), 'utf8');
	const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
	if (scripts.length !== 1) throw new Error(`src/app.html: expected exactly one inline <script>, found ${scripts.length}`);
	return createHash('sha256')
		.update(scripts[0]?.[1] ?? '')
		.digest('base64');
}

/**
 * Content-Security-Policy written by SvelteKit into the HTML as a <meta> tag (mode "hash": the inline
 * bootstrap script and the theme script of app.html are allowed by their sha256 hashes, so no 'unsafe-inline'
 * is needed anywhere). The directives are the ones in docs/API.md "Static hosting". The server copies this
 * policy into a header and adds frame-ancestors (a meta tag cannot carry it).
 * @type {import('@sveltejs/kit').CspDirectives}
 */
const directives = {
	'default-src': ['self'],
	'script-src': ['self', `sha256-${themeScriptHash()}`],
	'style-src': ['self'],
	'img-src': ['self', 'data:'],
	'connect-src': ['self'],
	'manifest-src': ['self'],
	'worker-src': ['self'],
	'object-src': ['none'],
	'base-uri': ['self'],
	'form-action': ['self']
};

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	vitePlugin: {
		// Runes mode for every component of this app (Svelte 5 syntax only); libraries keep their own mode.
		dynamicCompileOptions({ filename }) {
			return filename.includes('node_modules') ? undefined : { runes: true };
		}
	},
	kit: {
		// SPA: every route is rendered on the client; FastAPI serves build/index.html for unknown paths.
		adapter: adapter({ pages: 'build', assets: 'build', fallback: 'index.html', precompress: false, strict: true }),
		// Absolute asset paths: the fallback page is served for deep links such as /receptek/abc.
		paths: { base: '', relative: false },
		csp: { mode: 'hash', directives },
		// Registered by the root layout (production builds only), so a failed registration is handled.
		serviceWorker: { register: false },
		typescript: {
			config(tsconfig) {
				tsconfig.include.push('../playwright.config.ts', '../scripts/**/*.mjs');
				return tsconfig;
			}
		}
	}
};

export default config;
