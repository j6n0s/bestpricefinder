/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

/**
 * Offline support. Registered by the root layout in production builds only.
 *
 * - App shell: the build output, the static files and "/" (the SPA fallback page) are precached into a cache
 *   named after the build version; old caches are deleted when a new version activates.
 * - GET /api/meta and /api/health: network first, cached copy when offline.
 * - GET /api/stores, /api/ingredients, /api/recipes*: stale-while-revalidate.
 * - Everything else under /api (POST /api/quote, /api/list, /api/plan/*, history) goes to the network only:
 *   POST requests are never cached.
 * - Navigations: network first, the cached app shell when offline.
 * Only same-origin, complete (200, non-opaque) responses are stored, and never one marked no-store.
 * The caches hold public data only; personal data lives in localStorage ($lib/storage).
 */
import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;

const SHELL_CACHE = `hk-shell-${version}`;
const API_CACHE = `hk-api-${version}`;
const CURRENT_CACHES = new Set([SHELL_CACHE, API_CACHE]);
const APP_SHELL = '/';

const PRECACHE = [APP_SHELL, ...build, ...files];
const PRECACHED_PATHS = new Set([...build, ...files]);

const NETWORK_FIRST = new Set(['/api/meta', '/api/health']);
const STALE_WHILE_REVALIDATE = new Set(['/api/stores', '/api/ingredients', '/api/recipes']);

function isStaleWhileRevalidate(path: string): boolean {
	return STALE_WHILE_REVALIDATE.has(path) || path.startsWith('/api/recipes/');
}

function cacheable(response: Response): boolean {
	if (response.status !== 200 || response.type !== 'basic') return false;
	return !/(^|,)\s*no-store\s*(,|$)/i.test(response.headers.get('cache-control') ?? '');
}

async function put(cacheName: string, request: Request, response: Response): Promise<void> {
	if (!cacheable(response)) return;
	const cache = await caches.open(cacheName);
	await cache.put(request, response);
}

async function networkFirst(request: Request): Promise<Response> {
	try {
		const response = await fetch(request);
		await put(API_CACHE, request, response.clone()).catch(() => undefined);
		return response;
	} catch (error) {
		const cached = await caches.match(request, { cacheName: API_CACHE });
		if (cached) return cached;
		throw error;
	}
}

async function staleWhileRevalidate(event: FetchEvent): Promise<Response> {
	const { request } = event;
	const cache = await caches.open(API_CACHE);
	const cached = await cache.match(request);
	const network = fetch(request).then(async (response) => {
		await put(API_CACHE, request, response.clone()).catch(() => undefined);
		return response;
	});
	if (cached) {
		event.waitUntil(network.then(() => undefined).catch(() => undefined));
		return cached;
	}
	return network;
}

async function cacheFirst(request: Request): Promise<Response> {
	const cached = await caches.match(request, { cacheName: SHELL_CACHE });
	return cached ?? fetch(request);
}

async function navigation(request: Request): Promise<Response> {
	try {
		return await fetch(request);
	} catch (error) {
		const shell = await caches.match(APP_SHELL, { cacheName: SHELL_CACHE });
		if (shell) return shell;
		throw error;
	}
}

sw.addEventListener('install', (event) => {
	event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(PRECACHE)));
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.filter((key) => !CURRENT_CACHES.has(key)).map((key) => caches.delete(key))))
	);
});

sw.addEventListener('fetch', (event) => {
	const { request } = event;
	if (request.method !== 'GET') return;
	const url = new URL(request.url);
	if (url.origin !== sw.location.origin) return;
	if (request.headers.has('range')) return;
	const path = url.pathname;

	if (path.startsWith('/api/')) {
		if (NETWORK_FIRST.has(path)) event.respondWith(networkFirst(request));
		else if (isStaleWhileRevalidate(path)) event.respondWith(staleWhileRevalidate(event));
		return;
	}
	if (PRECACHED_PATHS.has(path)) {
		event.respondWith(cacheFirst(request));
		return;
	}
	if (request.mode === 'navigate') event.respondWith(navigation(request));
});
