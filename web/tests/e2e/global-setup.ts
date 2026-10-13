import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { handleMockApi } from '../mocks/api';
import { E2E_PORT } from './config';
import { startStaticServer } from './static-server';

const BUILD_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../build');

/** Serves web/build (plus the SYNTHETIC mock API) for the whole run; returns the teardown. */
export default async function globalSetup(): Promise<() => Promise<void>> {
	if (!existsSync(join(BUILD_DIR, 'index.html'))) {
		throw new Error('web/build/index.html is missing: run `npm run build` first (`npm run test:e2e` does).');
	}
	const server = await startStaticServer(BUILD_DIR, E2E_PORT, handleMockApi);
	return () =>
		new Promise<void>((done) => {
			server.closeAllConnections();
			server.close(() => done());
		});
}
