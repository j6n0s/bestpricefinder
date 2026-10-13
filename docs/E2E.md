# End-to-end tests of the whole system

**Status:** written 2026-10-13 by the cloud agent for docs/PROGRESS.md step 8 ("week plan → list → nearby stores → store totals"). Owners: `server/tests/fullstack/`, `server/tests/test_fullstack_api.py`, `web/tests/fullstack/`, `web/playwright.fullstack.config.ts`.

## One command

```sh
cd web && npm run test:fullstack
```

It builds `web/build` (`vite build`), then Playwright's global setup starts the **real stack** with the Python launcher, runs the browser test at two sizes, and the global teardown stops the stack. About **4 minutes** in all, almost all of it the ingest (see "Timings").

The API-level half, without a browser:

```sh
cd server && uv run pytest tests/test_fullstack_api.py -v
```

## What runs (all on 127.0.0.1, random free ports, torn down at the end)

| # | Component | Real or stand-in | How |
|---|---|---|---|
| 1 | PostgreSQL | **real** | A throwaway cluster made by the real `deploy/local/db-init.sh` and `db-start.sh` (`server/tests/pgcluster.py`; as root, the scripts run as the `bpfpg` OS user via `runuser`). Migrated with `bpf.migrate`. Stopped by `db-stop.sh`, then its directory is deleted. |
| 2 | GVH Árfigyelő | **stand-in** (`server/tests/fakegvh.py`, its threaded HTTP server) | Serves the **real store list** (`research/gvh-location/data/stores.csv`, 1,829 stores with their real ids and coordinates) and the real leaf categories that the ontology uses. **Every product, product id and price is SYNTHETIC** test data from a seeded generator. It is never presented as real and never shipped. The chain uuids are invented. |
| 3 | Ingest | **real** | `python -m bpf.ingest reference`, then `daily` and `availability`, as subprocesses, with `BPF_GVH_BASE_URL` / `BPF_GVH_XLSX_URL` pointing at the fake, `BPF_CONTACT_EMAIL=test@example.invalid` and `--date <today in Budapest>`. |
| 4 | Content | **real** | `python -m bpf.content`: `data/ingredients.json`, `data/recipes/*.json`, `data/ksh/`. |
| 5 | API + SPA | **real** | `python -m bpf.api --host 127.0.0.1 --port <free>` with the cluster's env file (`BPF_ENV_FILE`) and `BPF_WEB_BUILD_DIR=web/build`. |
| 6 | Browser | **real** | Playwright's Chromium from `/opt/pw-browsers` (never `playwright install`), `hu-HU`, Europe/Budapest, geolocation granted at Nyugati tér (47.5103, 19.0558). |

Nothing inside our own system is mocked: no `page.route` answers an `/api` call, and the API reads only what the ingest and the content loader wrote.

**Order.** reference → content → daily → availability → API. The content loader runs after the reference ingest, so the ontology's leaf ids are checked against `core.category`, and before the daily ingest, which reads `app.ingredient.leaf_ids` to choose its per-store and availability work. On a new installation the same order applies.

**Every run must end `ok`.** The launcher stops with an error on any other status and checks that `ops.ingest_run` holds exactly `reference ok, content ok, daily ok, availability ok`. No `partial` reason is accepted: in this world the listing and the XLSX agree on the date and no request budget is set. The runs do record these expected, non-degrading warnings: `food_category_missing` (the fake serves only the ontology's leaves, so one food top category is absent), `store_coordinate_outlier` (the real Rossmann Zalaegerszeg coordinate, BUILD-BRIEF §4.1 trap 8), `unknown_unit` (the fake's "csomag" product, trap 5) and `availability_stale` (the daily run comes before the first availability run).

**Politeness stays on.** `gvh_min_interval_s` cannot go below 1.0 (pydantic `ge=1.0`), so the ingest runs at the real 1 request per second over real HTTP. The work is kept small instead: the fake serves only the 92 leaves that the ontology references, with **one synthetic product per leaf** (`--per-leaf`, default 1), which makes about 210 requests. The API test checks that consecutive requests of one run are at least 0.9 s apart and that each carries the contact User-Agent.

**One test-only setting.** The API runs with `BPF_API_RATE_LIMIT_PER_MINUTE=6000`. The default of 120 per minute (burst 30) is sized for one phone; the suite is two browsers plus the test's own reference calls from 127.0.0.1, in parallel. Nothing else differs from production defaults.

## What the browser test checks (`web/tests/fullstack/fullstack.spec.ts`)

One flow per project: `phone-390` (390×844, touch) and `desktop-1280` (1280×800), in parallel.

- **a. `/terv`:** "Terv készítése" posts `{days: 7, slots: 3, people: 2}` to the real planner. All 21 slots are filled, each with the right recipe title, and the 7 rule chips of week 1 match the server's `checks` (`data-ok`).
- **b. `/lista`:** the `/api/list` request is exactly the plan's recipes at 2 servings per meal, with no `on_hand`. The page shows every non-pantry line of the response (by ingredient id) and the count. The "Valószínűleg otthon van" section lists the pantry lines.
- **c. "Hol a legolcsóbb a közelben?":**
  - the consent card comes first, and nothing is fetched or asked before the click;
  - "Saját helyzetem használata" then calls geolocation exactly once;
  - the store ids sent are recomputed independently from `/api/stores` and `/api/meta`: grocery chains, `has_data`, within 1.5 km of the rounded position, the nearest 3 per chain, nearest first;
  - each sent id is checked against the research CSV: a real Budapest store with the same coordinates. Nearby grocery stores without data (in the fake world `spar-193`, Andrássy út 30) are left out, and the page says how many;
  - the **rendered ranking equals the captured `/api/quote` response**: the same stores, ranks, whole-forint totals, tie labels exactly where a rank is shared, missing counts and penalized totals;
  - competition ranks are consistent, a tie is ordered by distance, and at least one tie exists (in the fake world Aldi, Lidl and Penny charge one price in every store);
  - replaying the same request returns an identical JSON;
  - the scope note, "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), <data date>" and the disclaimer are shown, and "akció" appears nowhere.
- **d. The cheapest store:** choosing rank 1 shows "Lista: <lánc>" and "Fizetendő" equal to its `checkout_total`. The total is checked against the sum of the priced lines. Each line's status is rendered: products, `N × pack` or "mérve", pick costs, "bolti ár"/"lánc ár", "nincs ebben a boltban", "nincs ár". KSH lines, when the plan has any, are labelled "becsült országos átlagár (KSH)", "nincs benne a fizetendő összegben", with the KSH source line.
- **e. `/receptek` and a recipe:** the card count matches `/api/recipes`. The first planned lunch's detail shows "kipróbálatlan recept", and its chain table matches `/api/recipes/{id}`: chains, server ranks, ranked rows first, tie and "részleges ár" labels, whole-forint cost per serving, and "nincs ár".
- **f. Throughout:**
  - no console errors, no uncaught errors and no CSP violations (a `securitypolicyviolation` listener);
  - no request to another origin (any such request would be aborted and fail the test);
  - the HTML's `Content-Security-Policy` header carries every directive of the build's meta policy plus `frame-ancestors 'none'`, and no `unsafe-inline`.
- **g. Never a coordinate:** no request URL or body contains `47.51…`, `19.05…`, `19.06…`, `latitude`, `longitude`, `"lat"` or `"lon"`.

Service workers are blocked (`serviceWorkers: 'block'`) so that every request of the page is visible to the test. The offline behaviour is covered by `tests/e2e/smoke.spec.ts`. Each project writes `lista-store.png`, `recipe-detail.png` and a `summary.json` attachment into `web/test-results/fullstack/` and prints the summary.

## What the API test checks (`server/tests/test_fullstack_api.py`, marker `db`)

It brings up steps 1 to 5 in-process (`tests.fullstack.FullStack`, API serving `web/build`) and checks:
- every step ran for real and ended `ok`, the request pacing, and the User-Agent;
- no password in the state or in any log;
- `/api/health` is `ok` with the fake's data date, and `/api/meta` has that `data_date`, the disclaimer and the attributions;
- `/api/stores` is exactly the real list with its coordinates. **`has_data` follows the rule** (docs/ENGINE.md): after the availability run, it is true exactly for the stores that carry a synthetic product and false for the no-data stores (`spar-171`, `spar-193`, `tesco-1008`), and it matches `has_data_date` in the database;
- a **quote over 5 real stores at Nyugati tér** (`spar-8251`, `tesco-4062`, `lidl-274`, `aldi-J067`, `penny-293`), for a planner week's list:
  - totals add up and KSH stays out of them;
  - `missing` lists the unavailable lines, and competition ranks are consistent;
  - the scope note is dated, and the answer is deterministic;
- a quote body with `lat`/`lon` is rejected (422);
- the SPA HTML carries the CSP header with `frame-ancestors 'none'`.

The test is **skipped automatically** when `node` or `web/build/index.html` is missing (`cd web && npm run build`), or when no PostgreSQL ≥ 16 is installed. It takes about 4 minutes, so `uv run pytest -m "not db"` stays fast.

## Running the stack by hand

```sh
cd server && uv run python -m tests.fullstack --run-dir /tmp/bpf-e2e --no-stdin-watch   # Ctrl-C to stop
```

- Options:
  - `--no-web`: API only;
  - `--web-build DIR`;
  - `--per-leaf N`: more synthetic products, about 2 s of ingest each.
- Once everything is up, it prints `FULLSTACK-READY {json}` and writes `stack.json`. The JSON holds the base URL, the data date, each step's status, time and request count, and the `ops.ingest_run` summary. It holds no secrets.
- It tears everything down on SIGTERM, SIGINT or SIGHUP, or when stdin closes (without `--no-stdin-watch`), and writes `teardown.json` (`clean: true`).
- Exit codes: 0 after a clean teardown, 1 when a step failed or the teardown was not clean, 130 when interrupted while starting.
- A second signal during the teardown is ignored, so the teardown always completes. This was checked with SIGTERM, SIGINT, a triple signal, stdin EOF and SIGTERM during start-up: each time the teardown was clean, with no cluster directory and no running postgres process left behind.

## Environment variables of the npm command

| Variable | Default | Meaning |
|---|---|---|
| `FULLSTACK_RUN_DIR` | `web/test-results/fullstack-stack` | Launcher logs (`launcher.log`, `logs/NN-<step>.log`, `logs/api-1.log`), `stack.json`, `teardown.json` |
| `FULLSTACK_PER_LEAF` | 1 | Passed to `--per-leaf` |
| `FULLSTACK_START_TIMEOUT_MS` | 1,200,000 | How long the global setup waits for the stack |

## Secrets and data rules

- The database passwords exist only in the cluster's env file. `db-init.sh` writes it with mode 600 inside the throwaway directory, and it is deleted with the cluster.
- Child processes get its path (`BPF_ENV_FILE`), never a password on a command line. The parent's `BPF_*` and `PG*` variables are not passed on.
- The contact address is the non-routable `test@example.invalid`.
- No GVH branding, no product images and no real prices appear: the fake's names ("Mintafarm …", "Próbakert …") and prices are synthetic. Only the store list is real research data, which is already in the repo.

## Timings (this container: PostgreSQL 16.15 from Ubuntu, Python 3.14.6, Node 22.22, Playwright 1.56.1 / Chromium 1194)

| Run | Start-up (cluster + ingest + API) | Browser tests (2 in parallel) | Teardown | Whole command |
|---|---|---|---|---|
| filled in below | | | | |

Per step (stable across runs): cluster about 1 s, reference ingest 3 s (3 requests), content 0.6 s, daily ingest 109 s (109 requests), availability 100 s (100 requests), API 1 s.

## Known limits

- **Sparse prices.** With one synthetic product per leaf, most chains carry only some of a week's ingredients, so many lines are "nincs ebben a boltban" and the ranking leans on the missing-line penalty. That is enough for the plumbing; `FULLSTACK_PER_LEAF=3` gives a denser world (285 products) for about 3.5 more minutes of ingest.
- **KSH lines** appear only when the planned week uses a KSH-priced ingredient. The planner is deterministic (seed 0), but planner changes can change the week. The test checks the KSH labels whenever such lines exist.
- **Data date = today (Budapest).** The ingest gets `--date` explicitly, so a run that crosses midnight does not break the ingest. The plan page itself starts "today" in the browser.
- **A killed launcher** (SIGKILL) cannot clean up. Its throwaway cluster is left under `/tmp/bpfpg-*`. Stop it with `pg_ctl -D /tmp/bpfpg-…/pg stop` as the cluster's owner, then delete the directory.
- PostgreSQL 18 is not installed in the cloud container. `pgcluster.py` uses whatever `deploy/local/_common.sh` discovers (`BPF_PG_BIN` overrides it), and the scripts support 16 to 18.
