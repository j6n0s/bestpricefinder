/**
 * /api/meta, loaded once by the root layout and shared with every page through Svelte context:
 *
 *   const meta = getMeta();          // in any component below +layout.svelte
 *   meta.data?.data_date             // reactive
 */
import { createContext } from 'svelte';
import { getMeta as fetchMeta, isApiError, ApiError, type RequestOptions } from './api/client';
import type { MetaResponse } from './api/types';

export type MetaStatus = 'idle' | 'loading' | 'ready' | 'error';

export class MetaStore {
	status = $state<MetaStatus>('idle');
	data = $state<MetaResponse | null>(null);
	error = $state<ApiError | null>(null);
	#inflight: Promise<void> | null = null;
	readonly #fetch: RequestOptions['fetch'];

	constructor(fetchImpl?: RequestOptions['fetch']) {
		this.#fetch = fetchImpl;
	}

	/** Loads /api/meta unless it is already loaded or loading. Never throws. */
	load(): Promise<void> {
		if (this.status === 'ready') return Promise.resolve();
		return this.reload();
	}

	/** Fetches /api/meta again (the retry button). Concurrent calls share one request. Never throws. */
	reload(): Promise<void> {
		if (this.#inflight) return this.#inflight;
		this.status = 'loading';
		this.error = null;
		this.#inflight = fetchMeta(this.#fetch ? { fetch: this.#fetch } : {})
			.then((data) => {
				this.data = data;
				this.status = 'ready';
			})
			.catch((error: unknown) => {
				this.error = isApiError(error) ? error : new ApiError({ kind: 'network' });
				this.status = 'error';
			})
			.finally(() => {
				this.#inflight = null;
			});
		return this.#inflight;
	}
}

const [getMetaContext, setMetaContext] = createContext<MetaStore>();

/** The shared MetaStore (call during component initialisation, below the root layout). */
export function getMeta(): MetaStore {
	return getMetaContext();
}

/** Called once by the root layout. */
export function provideMeta(store: MetaStore): MetaStore {
	return setMetaContext(store);
}
