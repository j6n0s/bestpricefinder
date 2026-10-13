import type { IncomingMessage } from 'node:http';
import { sveltekit } from '@sveltejs/kit/vite';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';
import { handleMockApi } from './tests/mocks/api';

const API_TARGET = 'http://127.0.0.1:8000';
const MAX_MOCK_BODY_BYTES = 65_536;

function readBody(req: IncomingMessage): Promise<string> {
	return new Promise((resolve, reject) => {
		let size = 0;
		const chunks: Buffer[] = [];
		req.on('data', (chunk: Buffer) => {
			size += chunk.length;
			if (size > MAX_MOCK_BODY_BYTES) {
				reject(new Error('mock API: body too large'));
				req.destroy();
				return;
			}
			chunks.push(chunk);
		});
		req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
		req.on('error', reject);
	});
}

const ANNOUNCER_STYLE =
	'style="position: absolute; left: 0; top: 0; clip: rect(0 0 0 0); clip-path: inset(50%); overflow: hidden; white-space: nowrap; width: 1px; height: 1px"';

/**
 * SvelteKit's generated root component gives its route announcer (#svelte-announcer) an inline style
 * attribute, which our CSP (style-src 'self', no 'unsafe-inline', docs/API.md) refuses: the browser logs a
 * violation and the announcer becomes visible. Swap the attribute for a class styled in src/app.css. The
 * build fails loudly if a SvelteKit upgrade changes the markup, so the patch can never silently go stale.
 */
function cspSafeAnnouncer(): Plugin {
	return {
		name: 'heti-kosar-csp-safe-announcer',
		enforce: 'pre',
		transform(code, id) {
			const file = (id.split('?')[0] ?? '').replaceAll('\\', '/');
			if (!file.endsWith('/.svelte-kit/generated/root.svelte') || !code.includes('svelte-announcer')) return null;
			if (!code.includes(ANNOUNCER_STYLE)) {
				this.error('SvelteKit changed the route announcer markup: update cspSafeAnnouncer() in vite.config.ts');
			}
			const patched = code.replace(ANNOUNCER_STYLE, 'class="sveltekit-announcer"');
			if (/\sstyle=/.test(patched)) this.error('root.svelte still contains an inline style attribute');
			return { code: patched, map: null };
		}
	};
}

/** `npm run dev:mock`: answer /api/* from the SYNTHETIC mocks in tests/mocks (no server needed). */
function mockApi(): Plugin {
	return {
		name: 'heti-kosar-mock-api',
		apply: 'serve',
		configureServer(server) {
			server.middlewares.use((req, res, next) => {
				if (!req.url?.startsWith('/api/')) {
					next();
					return;
				}
				readBody(req)
					.then((body) => {
						const result = handleMockApi(req.method ?? 'GET', req.url ?? '/', body);
						res.statusCode = result.status;
						res.setHeader('content-type', 'application/json; charset=utf-8');
						res.setHeader('x-mock-data', 'synthetic');
						res.end(JSON.stringify(result.body));
					})
					.catch(() => {
						res.statusCode = 413;
						res.setHeader('content-type', 'application/json; charset=utf-8');
						res.end(JSON.stringify({ error: 'payload_too_large', fields: [] }));
					});
			});
		}
	};
}

export default defineConfig(({ mode }) => {
	const mock = mode === 'mock';
	return {
		// cspSafeAnnouncer must come before sveltekit() so it sees the Svelte source of root.svelte.
		plugins: [cspSafeAnnouncer(), sveltekit(), ...(mock ? [mockApi()] : [])],
		server: {
			host: '127.0.0.1',
			// The API runs separately in development (python -m bpf.api on 127.0.0.1:8000).
			proxy: mock ? undefined : { '/api': { target: API_TARGET, changeOrigin: false } }
		},
		preview: { host: '127.0.0.1' },
		test: {
			include: ['src/**/*.test.ts', 'tests/mocks/**/*.test.ts'],
			environment: 'node'
		}
	};
});
