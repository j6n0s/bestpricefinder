/**
 * Minimal static server for the e2e tests. It serves web/build the way FastAPI will (docs/API.md "Static
 * hosting"): files from the build, the SPA fallback index.html for other non-/api paths, the CSP from the
 * fallback page's <meta> repeated as a header plus frame-ancestors, the security headers and the cache
 * headers. /api/* is answered by an optional handler (the SYNTHETIC mocks); otherwise 404.
 */
import { readFileSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http';
import { extname, join, resolve, sep } from 'node:path';

export type ApiHandler = (method: string, url: string, body: string) => { status: number; body: unknown };

const TYPES: Readonly<Record<string, string>> = {
	'.html': 'text/html; charset=utf-8',
	'.js': 'text/javascript; charset=utf-8',
	'.css': 'text/css; charset=utf-8',
	'.json': 'application/json; charset=utf-8',
	'.webmanifest': 'application/manifest+json; charset=utf-8',
	'.png': 'image/png',
	'.svg': 'image/svg+xml',
	'.txt': 'text/plain; charset=utf-8'
};

const SECURITY_HEADERS: Readonly<Record<string, string>> = {
	'X-Content-Type-Options': 'nosniff',
	'Referrer-Policy': 'no-referrer',
	'X-Frame-Options': 'DENY',
	'Cross-Origin-Opener-Policy': 'same-origin',
	'Cross-Origin-Resource-Policy': 'same-origin',
	'Permissions-Policy': 'geolocation=(self), camera=(), microphone=(), payment=(), usb=()'
};

/** The policy SvelteKit wrote into the fallback page's <meta http-equiv="content-security-policy">. */
export function cspFromHtml(html: string): string {
	const match = /<meta http-equiv="content-security-policy" content="([^"]+)"/i.exec(html);
	if (!match?.[1]) throw new Error('build/index.html has no CSP meta tag');
	return match[1];
}

function readBody(req: IncomingMessage): Promise<string> {
	return new Promise((resolveBody, reject) => {
		const chunks: Buffer[] = [];
		let size = 0;
		req.on('data', (chunk: Buffer) => {
			size += chunk.length;
			if (size > 65_536) {
				reject(new Error('body too large'));
				req.destroy();
				return;
			}
			chunks.push(chunk);
		});
		req.on('end', () => resolveBody(Buffer.concat(chunks).toString('utf8')));
		req.on('error', reject);
	});
}

function send(res: ServerResponse, status: number, headers: Record<string, string>, body: Buffer | string): void {
	res.writeHead(status, { ...SECURITY_HEADERS, ...headers });
	res.end(body);
}

export function startStaticServer(root: string, port: number, api?: ApiHandler): Promise<Server> {
	const base = resolve(root);
	const indexHtml = readFileSync(join(base, 'index.html'));
	const htmlCsp = `${cspFromHtml(indexHtml.toString('utf8'))}; frame-ancestors 'none'`;

	async function handle(req: IncomingMessage, res: ServerResponse): Promise<void> {
		const url = new URL(req.url ?? '/', 'http://localhost');
		const method = req.method ?? 'GET';
		let path: string;
		try {
			path = decodeURIComponent(url.pathname);
		} catch {
			send(res, 400, { 'Content-Type': 'text/plain' }, 'bad request');
			return;
		}

		if (path.startsWith('/api/')) {
			const json = { 'Content-Type': 'application/json; charset=utf-8', 'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'" };
			if (!api) {
				send(res, 404, json, JSON.stringify({ error: 'not_found', fields: [] }));
				return;
			}
			const body = method === 'POST' ? await readBody(req) : '';
			const result = api(method, `${url.pathname}${url.search}`, body);
			const cache = url.pathname === '/api/health' || method === 'POST' ? 'no-store' : 'public, max-age=300';
			send(res, result.status, { ...json, 'Cache-Control': cache }, JSON.stringify(result.body));
			return;
		}

		if (method !== 'GET' && method !== 'HEAD') {
			send(res, 405, { 'Content-Type': 'text/plain' }, 'method not allowed');
			return;
		}

		const file = resolve(base, `.${path}`);
		if (file !== base && !file.startsWith(base + sep)) {
			send(res, 404, { 'Content-Type': 'text/plain' }, 'not found');
			return;
		}
		const isFile = await stat(file).then((s) => s.isFile()).catch(() => false);
		if (isFile) {
			const type = TYPES[extname(file)] ?? 'application/octet-stream';
			const headers: Record<string, string> = { 'Content-Type': type };
			if (path.startsWith('/_app/immutable/')) headers['Cache-Control'] = 'public, max-age=31536000, immutable';
			else headers['Cache-Control'] = 'no-cache';
			if (type.startsWith('text/html')) headers['Content-Security-Policy'] = htmlCsp;
			send(res, 200, headers, method === 'HEAD' ? '' : await readFile(file));
			return;
		}
		if (extname(path) !== '') {
			send(res, 404, { 'Content-Type': 'text/plain' }, 'not found');
			return;
		}
		// SPA fallback for every other path.
		send(
			res,
			200,
			{ 'Content-Type': TYPES['.html'] ?? 'text/html', 'Cache-Control': 'no-cache', 'Content-Security-Policy': htmlCsp },
			method === 'HEAD' ? '' : indexHtml
		);
	}

	const server = createServer((req, res) => {
		handle(req, res).catch(() => {
			if (!res.headersSent) send(res, 500, { 'Content-Type': 'text/plain' }, 'internal error');
			else res.end();
		});
	});
	return new Promise((resolveServer, reject) => {
		server.once('error', reject);
		server.listen(port, '127.0.0.1', () => resolveServer(server));
	});
}
