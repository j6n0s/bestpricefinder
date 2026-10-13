// @ts-check
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/**
 * Content-Security-Policy written by SvelteKit into the HTML as a <meta> tag (mode "hash": the inline
 * bootstrap script is allowed by its sha256 hash, so no 'unsafe-inline' is needed anywhere).
 * The directives are the ones in docs/API.md "Static hosting". The server copies this policy into a header
 * and adds frame-ancestors (a meta tag cannot carry it).
 * @type {import('@sveltejs/kit').CspDirectives}
 */
const directives = {
	'default-src': ['self'],
	'script-src': ['self'],
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
