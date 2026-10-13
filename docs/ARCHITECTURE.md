# Architecture: bestpricefinder

Spec: [../BUILD-BRIEF.md](../BUILD-BRIEF.md). Every component is free, open-source software.

## Shape

```
 phone browser (PWA, Svelte)            ── all personal data stays here (localStorage):
   │  geolocation → nearest stores         plan, household size, pantry, diet prefs, location
   │  computed ON DEVICE; only store ids
   │  are sent to the server
   ▼ HTTPS, same origin
 FastAPI (Python 3.14, uvicorn)          ── read-only public data + stateless computation
   ├─ /api/*  JSON (docs/API.md)            no accounts, no cookies, no personal data
   └─ /*      static SPA build (web/build)
   │  psycopg 3 pool, role bpf_api (SELECT-only, read-only transactions, statement timeout)
   ▼ localhost / private unix socket only
 PostgreSQL 18 (dedicated cluster for this app)
   ▲  role bpf_ingest (INSERT/UPDATE on data tables only)
 ingest job (Python, daily ~04:30 Europe/Budapest)
   └─ GVH Árfigyelő API + daily XLSX (polite: ≤1 req/s, descriptive UA)
```

## Decisions (and why)

| Area | Choice | Reason |
|---|---|---|
| Frontend | **SvelteKit 2 + Svelte 5 + TypeScript**, `adapter-static` SPA, installable PWA | Small bundles and fast on phones; static output has no server-side rendering attack surface; offline app shell. |
| Backend | **Python 3.14 + FastAPI + Pydantic v2 + psycopg 3** | Strict input validation, automatic OpenAPI, mature data tooling for ingest (openpyxl, httpx). |
| Database | **PostgreSQL 18**, a dedicated local cluster for this app | Fast, ACID, row-level privileges. A separate cluster leaves the user's existing Homebrew cluster untouched, and it can be hardened from `initdb` onwards. |
| Personal data | **Kept on the device only.** The server holds only public price data and our own recipes. | The safest data is data you never store. It also keeps health data (diets, allergies; GDPR Art. 9) and raw GPS off the server. |
| Deploy (local) | One uvicorn process serving API + SPA, behind a reverse proxy when exposed (Caddy, automatic HTTPS) | Simple. Geolocation needs HTTPS on the phone (localhost is exempt on the dev machine). |

## Database security model (defence in depth)

1. **Network:** `listen_addresses = 'localhost'`, a non-default port (5544), and the unix socket in a private directory (mode 0700). Nothing is exposed to the LAN.
2. **Authentication:** `scram-sha-256` for every connection (local and host) from `initdb` onwards; there is no `trust` anywhere. `password_encryption = scram-sha-256`.
3. **Least privilege:**
   - `bpf_owner` (NOLOGIN) owns all objects.
   - `bpf_migrator` (LOGIN, member of the owner) runs migrations only.
   - `bpf_ingest` gets INSERT/UPDATE/SELECT on data tables only. It has no DDL and no DELETE on price history.
   - `bpf_api` gets SELECT on the `api` schema views only, with `default_transaction_read_only = on`, `statement_timeout = 3s` and a connection limit.
   - `PUBLIC` has no CONNECT, no CREATE and no default schema access.
4. **Secrets:** random 32-byte passwords are generated at init and stored in `.env.local` (chmod 600, git-ignored). They are never in code or logs.
5. **Integrity:** price history is append-only (no UPDATE or DELETE grants for app roles), with CHECK constraints on units and prices and foreign keys everywhere.
6. **Injection:** parameterised queries only (psycopg placeholders), and no dynamic SQL from user input. API inputs are bounded (max list sizes and string lengths) and validated by Pydantic.
7. **Observability:** `log_connections`, `log_disconnections`, and logging of statements slower than 500 ms. Each ingest run is recorded in `ops.ingest_run`.
8. **Backups:** `pg_dump -Fc` via a script; encrypt the dumps (e.g. `age`) before they leave the machine.

## API security

- Stateless and read-only: no auth, no cookies, so CSRF does not apply.
- Strict CORS (same origin only).
- Security headers: CSP, HSTS behind TLS, `X-Content-Type-Options`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (geolocation=self).
- Per-IP rate limiting and a request body size limit.
- Generic error bodies that never echo internals.
- `/api/quote` takes store ids, never coordinates.

## Data flow (daily)

1. Ingest at about 04:30 Budapest time.
   1. Fetch `/categories`, `/chain-stores` and `/shops`, and upsert the reference tables.
   2. Fetch the XLSX (cache-busted, with its sheet date verified) for chain min/max and store counts.
   3. Fetch the listing for the food leaves (`limit=48`) for `productMinAmount`, price types and flags.
   4. Fetch per-store prices only for pairs with XLSX min < max, in Budapest stores, in leaves used by the ingredient ontology.
   5. Weekly: refresh availability via `/product/{id}`.
2. Everything lands in append-only daily tables keyed by `data_date`. The API reads the **latest successful** data date.
3. Pricing: ingredient → candidate SKUs (leaf + name rules) → availability at the store → store price (per-store row if one exists, else the chain-uniform price) → pack optimisation → totals.

## Repository layout

```
db/migrations/        numbered SQL migrations (schema + grants)
deploy/local/         db-init.sh, db-start.sh, db-stop.sh, run scripts
server/bpf/           Python package: config, db, gvh client, ingest, pricing, planner, api
server/tests/         pytest (unit + DB integration against a throwaway database)
data/                 ingredients.json (ontology), recipes/*.json (original recipes), ksh/ (CC BY 4.0)
web/                  SvelteKit PWA
docs/                 ARCHITECTURE.md, API.md, DATA.md, PROGRESS.md
research/             research evidence (read-only)
```
