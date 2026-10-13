/**
 * Starts the REAL stack for the full-stack suite: `python -m tests.fullstack` (server/tests/fullstack) brings up
 * PostgreSQL (deploy/local/db-init.sh), the fake GVH (REAL store list, SYNTHETIC products and prices), the real
 * ingest, the content loader and the real API serving web/build, then prints one "FULLSTACK-READY {json}" line.
 *
 * The launcher keeps running until global-teardown.ts sends SIGTERM. Its stdin stays a pipe from this process:
 * if the Playwright runner dies, the pipe closes and the launcher tears everything down by itself.
 */
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createInterface } from 'node:readline';
import { BUILD_DIR, READY_PREFIX, RUN_DIR, SERVER_DIR, type StackState } from './stack';

/** The ingest runs at the GVH politeness floor of 1 request per second: about 4 minutes in all. */
const START_TIMEOUT_MS = Number(process.env.FULLSTACK_START_TIMEOUT_MS ?? 20 * 60_000);

export interface LauncherGlobal {
	__fullstackLauncher?: ChildProcess;
}

function serverPython(): string {
	const probe = spawnSync('uv', ['run', 'python', '-c', 'import sys; print(sys.executable)'], {
		cwd: SERVER_DIR,
		encoding: 'utf-8'
	});
	const python = probe.stdout?.trim().split('\n').at(-1) ?? '';
	if (probe.status !== 0 || !python) {
		throw new Error(`cannot resolve the server's Python with uv (cd server && uv run python): ${probe.stderr ?? probe.error}`);
	}
	return python;
}

function launcherLogTail(lines = 30): string {
	try {
		return readFileSync(join(RUN_DIR, 'launcher.log'), 'utf-8').trimEnd().split('\n').slice(-lines).join('\n');
	} catch {
		return '(no launcher.log)';
	}
}

function waitForReady(child: ChildProcess): Promise<StackState> {
	return new Promise<StackState>((resolve, reject) => {
		const timer = setTimeout(() => reject(new Error(`the stack was not ready within ${START_TIMEOUT_MS / 1000} s`)), START_TIMEOUT_MS);
		const onExit = (code: number | null, signal: NodeJS.Signals | null): void => {
			clearTimeout(timer);
			reject(new Error(`the launcher exited before the stack was ready (code ${code}, signal ${signal})\n${launcherLogTail()}`));
		};
		child.once('exit', onExit);
		if (!child.stdout) {
			reject(new Error('no stdout pipe to the launcher'));
			return;
		}
		const lines = createInterface({ input: child.stdout });
		lines.on('line', (line) => {
			if (!line.startsWith(READY_PREFIX)) return;
			clearTimeout(timer);
			child.off('exit', onExit);
			resolve(JSON.parse(line.slice(READY_PREFIX.length)) as StackState);
		});
	});
}

async function stop(child: ChildProcess): Promise<void> {
	if (child.exitCode !== null || child.signalCode !== null) return;
	const exited = new Promise<void>((resolve) => child.once('exit', () => resolve()));
	child.kill('SIGTERM');
	await exited;
}

export default async function globalSetup(): Promise<void> {
	if (!existsSync(join(BUILD_DIR, 'index.html'))) {
		throw new Error('web/build/index.html is missing: run `npm run build` first (`npm run test:fullstack` does).');
	}
	mkdirSync(RUN_DIR, { recursive: true });
	const python = serverPython();
	const began = Date.now();
	const args = ['-m', 'tests.fullstack', '--run-dir', RUN_DIR, '--web-build', BUILD_DIR];
	if (process.env.FULLSTACK_PER_LEAF) args.push('--per-leaf', process.env.FULLSTACK_PER_LEAF);
	const child = spawn(python, args, {
		cwd: SERVER_DIR,
		stdio: ['pipe', 'pipe', 'inherit']
	});
	(globalThis as LauncherGlobal).__fullstackLauncher = child;
	let state: StackState;
	try {
		state = await waitForReady(child);
	} catch (error) {
		await stop(child);
		throw error;
	}
	// Read by the specs (workers start after this and inherit the environment).
	process.env.FULLSTACK_RUN_DIR = RUN_DIR;
	process.env.FULLSTACK_BASE_URL = state.base_url;
	const steps = state.steps.map((step) => `${step.name} ${step.status} ${step.seconds.toFixed(1)} s (${step.requests} req)`).join(', ');
	console.log(`[fullstack] ready in ${((Date.now() - began) / 1000).toFixed(0)} s at ${state.base_url}, data date ${state.data_date}: ${steps}`);
}
