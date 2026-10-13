# Progress and hand-off (read this first, cloud agent)

**Last updated:** 2026-10-13 01:50 CEST by the local research session "Meal planning app idea analysis".
**Decision by the user (2026-10-13):** a **cloud-based agent writes the code**. The local session did the research and laid the foundation below, then pushed.
**Communication:** the local session and the cloud agent cannot message each other. Use the repo:
- questions and decisions go in `docs/QUESTIONS.md` (append; date and sign each entry);
- update this file's checklist as you finish items;
- describe each change in its PR or commit.

The user relays anything urgent.

## Read in this order
1. [`BUILD-BRIEF.md`](../BUILD-BRIEF.md). The spec. §1 what to build, §4 the data API and its 12 traps, §8 the **binding legal guardrails**.
2. [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). The stack and the security model (already decided; change only with a reason recorded in QUESTIONS.md).
3. [`db/migrations/0001_init.sql`](../db/migrations/0001_init.sql). The schema (done and tested, see below).
4. `research/`. Evidence and data. Each stream's `verify.md` corrects its `notes.md`.

## Done
- [x] Research, 7 streams + 4 gap-fills, adversarially fact-checked (`research/`).
- [x] BUILD-BRIEF.md, ARCHITECTURE.md, AGENTS.md, .gitignore.
- [x] `db/migrations/0001_init.sql`. **Tested on PostgreSQL 18.6** in a throwaway cluster on 2026-10-13. Results:
  - The migration applies in one transaction as `bpf_migrator` after `SET ROLE bpf_owner`.
  - `bpf_api` can SELECT `api.*` views only. It is denied on `core`, `app` and `ops`, and every INSERT fails.
  - `bpf_ingest` can INSERT and UPDATE data. `CREATE TABLE` is denied, `DELETE` on price history is denied, and UPDATE of a past day's prices is blocked by the append-only trigger. Today's rows stay correctable.
  - `api.latest` and `api.product_chain_latest` resolve the latest successful daily run.
- [x] Python 3.14 dependency check: fastapi 0.143.0, starlette 1.7.0, uvicorn 0.54.0, pydantic 2.14.1, pydantic-settings 2.15.0, psycopg[binary,pool] 3.3.6 / psycopg-pool 3.3.3, httpx 0.28.1, openpyxl 3.1.5 and pytest 9.1.1 all install and import on macOS arm64.

## Next steps (in order). Tick them off here.
- [x] **1. Local DB tooling** _(done 2026-10-13 by the cloud agent: `deploy/local/`, `.env.example`; 58 tests pass on PostgreSQL 16.15 and 18.6, incl. automated role-privilege tests; see `deploy/local/README.md`)_: `deploy/local/db-init.sh`, `db-start.sh`, `db-stop.sh`, `.env.example`. Follow ARCHITECTURE.md "Database security model":
  - a dedicated cluster on port 5544, listening on localhost only;
  - `initdb --auth-local=scram-sha-256 --auth-host=scram-sha-256 --locale-provider=builtin --builtin-locale=C.UTF-8`;
  - a strict `pg_hba.conf`;
  - the roles `bpf_owner` (NOLOGIN), `bpf_migrator` (IN ROLE bpf_owner), `bpf_ingest` and `bpf_api`, with `ALTER ROLE … SET` for read-only mode, timeouts and search_path;
  - `REVOKE ALL ON DATABASE … FROM PUBLIC`;
  - random passwords written to `.env.local` with chmod 600. Pass them via `\getenv`, never on the command line.

  ⚠️ On macOS, `export LC_ALL=en_US.UTF-8` before `pg_ctl start`, or the postmaster aborts with "became multithreaded during startup". Unix socket paths must be under 103 bytes. In a cloud container, use the distro's PostgreSQL 16+ or a `postgres:18` container.
- [x] **2. `server/` skeleton** _(done 2026-10-13 by the cloud agent: `server/pyproject.toml` + `uv.lock`, `bpf/config.py`, `bpf/db.py`, `bpf/migrate.py`, test harness `server/tests/pgcluster.py`)_: `pyproject.toml` with pinned deps; `bpf/config.py` (pydantic-settings reading `.env.local`); `bpf/db.py` (psycopg_pool, one pool per role); `bpf/migrate.py`, which:
  - applies `db/migrations/*.sql` in order inside one transaction each, prefixed with `SET ROLE bpf_owner`;
  - records version and sha256 in `public.schema_migrations`;
  - refuses to run if an applied file's checksum changed.
- [ ] **3. GVH client + ingest** (`bpf/gvh/`, `bpf/ingest/`). Handle every trap in BUILD-BRIEF §4.1:
  - `limit=48` paging;
  - `productMinAmount` vs `prices[]`;
  - the 3-chain listing cap;
  - a cache-busted XLSX with its sheet-date check and decimal-comma numbers;
  - unit validation;
  - ≤1 req/s with a descriptive UA;
  - pydantic validation that fails loudly on schema drift.

  The daily run order is in ARCHITECTURE.md. Record each run in `ops.ingest_run`. Tests use recorded fixture JSON; take small fresh samples, and never commit large raw dumps.
- [ ] **4. Content** in `data/`, with `docs/DATA.md` documenting the formats:
  - `ingredients.json`: ontology rows matching `app.ingredient`. Seed from `research/recipe-coverage/out/ingredient_mapping.csv`, then verify the leaf ids against live `/api/categories`.
  - `recipes.json`: 30–40 **original**, GVH-native Hungarian recipes. Each needs ≥90% of its cost in GVH-priced ingredients; breakfasts are built from bread, túró, joghurt, eggs, vegetables and fruit; mark them `tested=false` until a human cooks them.
  - `ksh/ara0044.csv`: CC BY 4.0, ISO-8859-2 source.
  - A loader (`bpf/content.py`) that validates and upserts as `bpf_ingest`.

  Never copy recipe text from recipe sites or OKOSTÁNYÉR.
- [ ] **5. Pricing engine + planner** (`bpf/pricing/`, `bpf/planner/`): the algorithms are in BUILD-BRIEF §6. Write pure functions with unit tests: unit normalisation (db↔kg via `piece_weight_kg`), name include/exclude rules, store availability, store-vs-chain price choice, pack optimisation, store ranking, cheaper swaps, and planner weekly rules.
- [ ] **6. API** (`bpf/api/`): write `docs/API.md` first. Proposed contract:
  - `GET /api/health` → `{status, db, data_date}`.
  - `GET /api/meta` → `{data_date, ingested_at, chains[], attribution{gvh,ksh,nutrition}, disclaimer}`.
  - `GET /api/stores` → all stores (id, chain, address, lat/lon, format, has_data). ETag; cacheable for a day. **The client computes distances itself.**
  - `GET /api/ingredients` and `GET /api/recipes?slot=&tag=&q=`. `GET /api/recipes/{id}` returns lines, steps and per-serving nutrition.
  - `POST /api/quote` → request `{lines:[{ingredient_id, qty}] (≤200), store_ids:[…] (≤25)}`. Response: per store, the lines (product, pack, packs, checkout cost, used cost, price type, `price_scope: store|chain`), totals, the missing items and the data date; plus labelled KSH estimates and the attribution. **Never accept coordinates.**
  - `POST /api/plan/suggest` → `{days, slots, people, exclude_tags, seed}` gives a rule-compliant plan.
  - `GET /api/ingredients/{id}/history?chain=&days=` returns history from our own archive.

  Security: pydantic bounds on every input, per-IP rate limit, body size limit, strict CORS, security headers, generic errors, the `bpf_api` role only.
- [ ] **7. `web/`**: SvelteKit 2 + Svelte 5 + TS, `adapter-static` SPA, PWA (manifest + service worker), Hungarian UI, mobile-first.
  - Pages: Heti terv, Receptek (+ részletek), Bevásárlólista + "Hol a legolcsóbb a közelben?", Beállítások (location consent, radius, people, slots 3/5, pantry, excluded ingredients), Források és adatvédelem.
  - Personal data lives in localStorage only.
  - Configure `kit.csp` with `mode: 'hash'` so no `unsafe-inline` script is needed.
  - Show the disclaimer and "Forrás: GVH Árfigyelő, [dátum]" on every price view.
- [ ] **8. Integration**: FastAPI serves `web/build` plus `/api`. Run an end-to-end test of a week plan → list → nearby stores → store totals. Add a daily scheduler entry (launchd or cron) for the ingest.
- [ ] **9. Security review**: dependency audit (`pip-audit`, `npm audit`), the role-privilege tests above as automated tests, an input-fuzz test of the API, a CSP check, and a secrets scan before every push.

## Founder-only items (agents must not do these)
- File the GVH re-use request; the draft is in `research/gap-gvh-reuse-legal-route/request_draft_hu.txt`.
- The fake-door willingness-to-pay test. Partnerships with MDOSZ and Kifli.
