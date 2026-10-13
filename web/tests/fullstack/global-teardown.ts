/**
 * Stops the stack started by global-setup.ts: SIGTERM to the launcher, which stops the API, the fake GVH and
 * the PostgreSQL cluster (deploy/local/db-stop.sh) and deletes the cluster directory, then writes
 * teardown.json. Fails the run when the teardown was not clean.
 */
import type { LauncherGlobal } from './global-setup';
import { readTeardown, type TeardownState } from './stack';

const STOP_TIMEOUT_MS = 120_000;

export default async function globalTeardown(): Promise<void> {
	const child = (globalThis as LauncherGlobal).__fullstackLauncher;
	if (!child) return; // the setup never started it
	if (child.exitCode === null && child.signalCode === null) {
		const exited = new Promise<boolean>((resolve) => child.once('exit', () => resolve(true)));
		const timedOut = new Promise<boolean>((resolve) => setTimeout(() => resolve(false), STOP_TIMEOUT_MS).unref());
		child.kill('SIGTERM');
		if (!(await Promise.race([exited, timedOut]))) {
			child.kill('SIGKILL');
			throw new Error(`the launcher did not stop within ${STOP_TIMEOUT_MS / 1000} s and was killed; its cluster may be left over`);
		}
	}
	child.stdin?.destroy();
	let teardown: TeardownState;
	try {
		teardown = readTeardown();
	} catch {
		throw new Error(`the launcher left no teardown.json (exit code ${child.exitCode}, signal ${child.signalCode})`);
	}
	console.log(`[fullstack] torn down in ${teardown.timings.teardown ?? '?'} s: clean=${teardown.clean}`);
	if (!teardown.clean || child.exitCode !== 0) {
		throw new Error(`the stack teardown was not clean (exit code ${child.exitCode}): ${JSON.stringify(teardown)}`);
	}
}
