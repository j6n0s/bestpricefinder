# End-to-end tests of the whole system

**Status:** written 2026-10-13 by the cloud agent for docs/PROGRESS.md step 8 ("week plan → list → nearby stores → store totals"). Verified the same day; the results are in "Verification" at the end. Owners: `server/tests/fullstack/`, `server/tests/test_fullstack_api.py`, `web/tests/fullstack/`, `web/playwright.fullstack.config.ts`.

## One command

```sh
cd web && npm run test:fullstack
```

It builds `web/build` (`vite build`). Playwright's global setup then starts the **real stack** with the Python launcher, the browser test runs at two sizes, and the global teardown stops the stack. The whole command takes about **4 minutes**, almost all of it the ingest (see "Verification").

The API-level half, without a browser:

```sh
cd server && uv run pytest tests/test_fullstack_api.py -v
```

## What runs (all on 127.0.0.1, random free ports, torn down at the end)

| # | Component | Real or stand-in | How |
|---|---|---|---|
| 1 | PostgreSQL | **real** | A throwaway cluster made by the real `deploy/local/db-init.sh` and `db-start.sh` (`server/tests/pgcluster.py`). As root, the scripts run as the `bpfpg` OS user via `runuser`. The cluster is migrated with `bpf.migrate`, stopped by `db-stop.sh`, and its directory is then deleted. |
| 2 | GVH Árfigyelő | **stand-in**: `server/tests/fakegvh.py` and its threaded HTTP server | It serves the **real store list** (`research/gvh-location/data/stores.csv`: 1,829 stores with their real ids and coordinates) and the real leaf categories that the ontology uses. **Every product, product id and price is SYNTHETIC** test data from a seeded generator. It is never presented as real and never shipped. The chain uuids are invented. |
| 3 | Ingest | **real** | `python -m bpf.ingest reference`, then `daily` and `availability`, as subprocesses. They run with `BPF_GVH_BASE_URL` and `BPF_GVH_XLSX_URL` pointing at the fake, `BPF_CONTACT_EMAIL=test@example.invalid` and `--date <today in Budapest>`. |
| 4 | Content | **real** | `python -m bpf.content` loads `data/ingredients.json`, `data/recipes/*.json` and `data/ksh/`. |
| 5 | API + SPA | **real** | `python -m bpf.api --host 127.0.0.1 --port <free>` runs with the cluster's env file (`BPF_ENV_FILE`) and `BPF_WEB_BUILD_DIR=web/build`. |
| 6 | Browser | **real** | Playwright's Chromium from `/opt/pw-browsers` (never `playwright install`), with `hu-HU`, Europe/Budapest, and geolocation granted at Nyugati tér (47.5103, 19.0558). |

Nothing inside our own system is mocked:
- no `page.route` answers an `/api` call; the only route aborts requests to other origins;
- the API reads only what the ingest and the content loader wrote.

**Order.** reference → content → daily → availability → API.
- The content loader runs after the reference ingest, so the ontology's leaf ids are checked against `core.category`.
- It runs before the daily ingest, which reads `app.ingredient.leaf_ids` to choose its per-store and availability work.
- A new installation uses the same order.

**Every run must end `ok`.** The launcher stops with an error on any other exit status. It also checks that `ops.ingest_run` holds exactly `reference ok, content ok, daily ok, availability ok`.
- No `partial` reason is accepted: in this world the listing and the XLSX agree on the date, and no request budget is set.
- The runs record these expected warnings, none of which degrades a run:
  - `food_category_missing`: the fake serves only the ontology's leaves, so one food top category is absent;
  - `store_coordinate_outlier`: the real Rossmann Zalaegerszeg coordinate (BUILD-BRIEF §4.1 trap 8);
  - `unknown_unit`: the fake's "csomag" product (trap 5);
  - `availability_stale`: the daily run comes before the first availability run.

**Politeness stays on.** `gvh_min_interval_s` cannot go below 1.0 (pydantic `ge=1.0`), so the ingest runs at the real 1 request per second over real HTTP. The work is kept small instead:
- the fake serves only the 92 leaves that the ontology references;
- it serves **one synthetic product per leaf** by default (`--per-leaf`), which gives 101 products and 212 requests (3 reference, 109 daily, 100 availability).

The API test checks the pacing as the fake received the requests:
- the requests of one run span at least (n − 1) s, less 0.5 s;
- no two arrive less than 0.5 s apart;
- each carries the contact User-Agent.

The client starts its requests at least 1 s apart. The fake's receipt times add scheduling jitter to a single gap (0.874 s was measured once under load), so a single gap is not held to 1 s; the span is.

**One test-only setting.** The API runs with `BPF_API_RATE_LIMIT_PER_MINUTE=6000`.
- The default of 120 per minute (burst 30) is sized for one phone.
- The suite is two browsers plus the test's own reference calls, all from 127.0.0.1 and in parallel: about 30 `/api` requests within a few seconds, right at the burst limit.
- Nothing else differs from the production defaults.

## What the browser test checks (`web/tests/fullstack/fullstack.spec.ts`)

One flow per project, `phone-390` (390×844, touch) and `desktop-1280` (1280×800), run in parallel.

- **a. `/terv`:**
  - "Terv készítése" posts `{days: 7, slots: 3, people: 2}` to the real planner.
  - All 21 slots are filled, each with the right recipe title.
  - The 7 rule chips of week 1 (the rules of docs/API.md) match the server's `checks` (`data-ok`).
- **b. `/lista`:**
  - The `/api/list` request is exactly the plan's recipes at 2 servings per meal, with no `on_hand`.
  - The page shows every non-pantry line of the response (by ingredient id) and the count.
  - The "Valószínűleg otthon van" section lists the pantry lines, none marked "nincs otthon".
- **c. "Hol a legolcsóbb a közelben?":**
  - The consent card comes first, and nothing is fetched and no position is asked for before the click.
  - "Saját helyzetem használata" then calls geolocation exactly once.
  - The test recomputes the store ids sent, independently, from `/api/stores` and `/api/meta`: grocery chains, `has_data`, within 1.5 km of the rounded position, the nearest 3 per chain, nearest first.
  - Each id sent is checked against the research CSV: a real Budapest store with the same coordinates. Nearby grocery stores without data (in the fake world `spar-193`, Andrássy út 30) are left out, and the page says how many.
  - The **rendered ranking equals the captured `/api/quote` response**: the same stores, ranks, whole-forint totals, tie labels exactly where a rank is shared, missing counts and penalized totals.
  - Competition ranks are consistent, a tie is ordered by distance, and at least one tie exists (in the fake world Aldi, Lidl and Penny charge one price in every store).
  - Replaying the same request returns identical JSON.
  - The scope note, "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), <data date>" and the disclaimer are shown, and "akció" appears nowhere.
- **d. The cheapest store:**
  - Choosing rank 1 shows "Lista: <lánc>" and "Fizetendő" equal to its `checkout_total`, and that total is the sum of the priced lines.
  - The lines are grouped by shop section in the docs/DATA.md order, under the Hungarian headings, each section in list order.
  - Each line's status is rendered:
    - products, `N × pack` or "mérve", and pick costs;
    - "bolti ár" or "lánc ár";
    - "nincs ebben a boltban" or "nincs ár".
  - KSH lines are labelled "becsült országos átlagár (KSH)" and "nincs benne a fizetendő összegben", with the KSH source line. With today's content the browser never meets one (see "Known limits"); the API test covers them.
- **e. `/receptek` and a recipe:**
  - The card count matches `/api/recipes`.
  - The first planned lunch's detail shows "kipróbálatlan recept".
  - Its chain table matches `/api/recipes/{id}`: chains, server ranks, ranked rows first, tie and "részleges ár" labels, whole-forint cost per serving, and "nincs ár".
- **f. Throughout:**
  - no console errors, no uncaught errors and no CSP violations (a `securitypolicyviolation` listener);
  - no request to another origin from the whole browser context, popups included (any such request is aborted and fails the test);
  - every HTML document (`/terv`, `/lista`, `/receptek`) has a `Content-Security-Policy` header that carries every directive of the build's meta policy plus `frame-ancestors 'none'`, and no `unsafe-inline`.
- **g. Never a coordinate:** no request URL or body contains `47.51…`, `19.05…`, `19.06…`, `latitude`, `longitude`, `"lat"` or `"lon"`.

The console, CSP-violation, origin, coordinate and "akció" checks are soft assertions, so a failure lists every problem, not only the first; the test still fails.

Service workers are blocked (`serviceWorkers: 'block'`) so that the test sees every request of the page. `tests/e2e/smoke.spec.ts` covers the offline behaviour. Each project writes `lista-store.png`, `recipe-detail.png` and a `summary.json` attachment into `web/test-results/fullstack/`, and prints the summary.

## What the API test checks (`server/tests/test_fullstack_api.py`, marker `db`)

It brings up steps 1 to 5 in-process (`tests.fullstack.FullStack`, with the API serving `web/build`) and checks:
- every step ran for real and ended `ok`, and the request pacing and User-Agent are as described above;
- no password appears in the state or in any log;
- `/api/health` is `ok` with the fake's data date, and `/api/meta` has that `data_date`, the disclaimer and the attributions;
- `/api/stores` is exactly the real list with its coordinates;
- **`has_data` follows the rule** (docs/ENGINE.md):
  - after the availability run, it is true exactly for the stores that carry a synthetic product;
  - it is false for the no-data stores (`spar-171`, `spar-193`, `tesco-1008`);
  - it matches `has_data_date` in the database;
- a **quote over 5 real stores at Nyugati tér** (`spar-8251`, `tesco-4062`, `lidl-274`, `aldi-J067`, `penny-293`), for a planner week's list:
  - the totals add up, and KSH stays out of them;
  - `missing` lists the unavailable lines, and the competition ranks are consistent;
  - the scope note is dated, and the answer is deterministic;
- a **KSH-priced line** (all 6 KSH-priced ingredients, quoted directly):
  - its status is `ksh_estimate`;
  - its estimate is the real `data/ksh/ara0044.csv` average times the quantity;
  - it is not in `checkout_total` or `missing`;
  - the KSH attribution is "Forrás: KSH", CC BY 4.0;
- a quote body with `lat`/`lon` is rejected (422);
- the SPA HTML carries the CSP header with `frame-ancestors 'none'`.

The test is **skipped automatically** in three cases:
- `node` is not on the PATH;
- `web/build/index.html` is missing (`cd web && npm run build`);
- no PostgreSQL ≥ 16 is installed.

It takes about 3.5 minutes, so `uv run pytest -m "not db"` stays fast.

## Running the stack by hand

```sh
cd server && uv run python -m tests.fullstack --run-dir /tmp/bpf-e2e --no-stdin-watch   # Ctrl-C to stop
```

- Options:
  - `--no-web`: API only;
  - `--web-build DIR`;
  - `--per-leaf N`: more synthetic products. Each one adds about 2 s of ingest (more for leaves with several chains).
- Once everything is up, the launcher prints `FULLSTACK-READY {json}` and writes `stack.json`. The JSON holds the base URL, the data date, each step's status, time and request count, and the `ops.ingest_run` summary. It holds no secrets.
- It tears everything down on SIGTERM, SIGINT or SIGHUP, or when stdin closes (unless `--no-stdin-watch` is given). It then writes `teardown.json` (`clean: true`).
- Stop signals are held back while the teardown runs, so a second Ctrl-C cannot cut it short. A signal that arrives during start-up stops the start and tears down what was started.
- Exit codes:
  - 0 after a clean teardown;
  - 1 when a step failed or the teardown was not clean;
  - 2 for a usage error;
  - 130 when interrupted while starting.
- Logs go to `<run dir>/launcher.log` and `<run dir>/logs/NN-<step>.log` (the API's in `logs/api-1.log`). A reused run directory loses the previous run's logs.

**Iterating on the specs.** Start the stack by hand in the browser test's default run directory (or in any directory, passed to both as `FULLSTACK_RUN_DIR`). Then run the browser test against it as often as needed; each browser run takes about 10 s. Each line starts from the repository root:

```sh
cd web && npm run build
cd server && uv run python -m tests.fullstack --run-dir ../web/test-results/fullstack-stack --no-stdin-watch   # keep it running
cd web && FULLSTACK_ATTACH=1 npx playwright test --config playwright.fullstack.config.ts                       # another terminal
```

The API reads `web/build/index.html` and its CSP once, at start-up. After a new build, restart the stack.

## Environment variables of the npm command

| Variable | Default | Meaning |
|---|---|---|
| `FULLSTACK_RUN_DIR` | `web/test-results/fullstack-stack` | The launcher's logs (`launcher.log`, `logs/`), `stack.json` and `teardown.json` |
| `FULLSTACK_PER_LEAF` | 1 | Passed to `--per-leaf` |
| `FULLSTACK_START_TIMEOUT_MS` | 1,200,000 | How long the global setup waits for the stack |
| `FULLSTACK_ATTACH` | unset | `1`: use the stack already running from `FULLSTACK_RUN_DIR`, and leave it running |
| `BPF_PG_BIN` | discovered | PostgreSQL binaries for the throwaway cluster (deploy/local/README.md) |

## Secrets and data rules

- The database passwords exist only in the cluster's env file. `db-init.sh` writes it with mode 600 inside the throwaway directory, and it is deleted with the cluster.
- Child processes get the file's path (`BPF_ENV_FILE`), never a password on a command line. The parent's `BPF_*` and `PG*` variables are not passed on.
- The contact address is the non-routable `test@example.invalid`.
- No GVH branding, no product images and no real prices appear. The fake's product names ("Mintafarm …", "Próbakert …") and prices are synthetic. Only the store list is real research data, and it is already in the repo.

## Known limits

- **Sparse prices.** There is one synthetic product per leaf, and 78% of the fake's products are sold by one chain only (84% of real food SKUs are, BUILD-BRIEF §4.1 trap 7). So each store carries only some of a week's ingredients: at the cheapest store near Nyugati tér, 5 of the 29 lines are priced and 23 are "nincs ebben a boltban". The ranking therefore leans on the missing-line penalty. That is enough for the plumbing. `FULLSTACK_PER_LEAF=3` gives a denser world, at the cost of a longer ingest.
- **No KSH line in the browser.** Six ingredients are KSH-priced (`dio`, `gomba`, `gorogdinnye`, `lekvar`, `mez`, `szarazbab`), but no recipe uses one. Pantry spices with KSH data (`pirospaprika`, `so`) come back as `pantry`, which docs/API.md specifies. So no planned week has a KSH line. The browser test checks the KSH labels whenever such a line exists, and the API test checks the KSH estimate directly.
- **The week is fixed.** The page asks for seed 0, and the planner is deterministic. A planner or content change changes the week, and the test follows it (nothing in it names a recipe).
- **Data date = today (Budapest).** The ingest gets `--date` explicitly, so a run that crosses midnight does not break the ingest. The plan page itself starts "today" in the browser.
- **A killed launcher** (SIGKILL) cannot clean up. Its throwaway cluster is left under `/tmp/bpfpg-*`. Stop it with `pg_ctl -D /tmp/bpfpg-…/pg stop` as the cluster's owner, then delete the directory.
- **PostgreSQL version.** `pgcluster.py` uses whatever `deploy/local/_common.sh` discovers; `BPF_PG_BIN` overrides it. The scripts support 16 to 18. The cloud container has 16.

## Verification

Verified on 2026-10-13 in the cloud container. Versions: PostgreSQL 16.15 (Ubuntu), Python 3.14.6, Node 22.22.0, Playwright 1.56.1 with Chromium build 1194.

**`cd web && npm run test:fullstack`, three times:**

| Run | When | Result | Whole command | Stack start-up | Browser tests (2 in parallel) | Teardown |
|---|---|---|---|---|---|---|
| 1 | alone | 2 passed | 235 s | 217 s | 5.6 s / 6.1 s | 0.85 s, clean |
| 2 | right after run 1 | 2 passed | 230 s | 214 s | 5.5 s / 6.0 s | 0.80 s, clean |
| 3 | concurrently with the API test | 2 passed | 232 s | 213 s | 6.1 s / 6.5 s | 1.04 s, clean |

- The rest of the whole command is `vite build` (about 15 s).
- Each step's time hardly varies between runs:
  - cluster 1.2 s (4.5 s once, under load from another agent);
  - reference ingest 2.8 s (3 requests);
  - content 0.5 s;
  - daily ingest 108.6 s (109 requests, spanning 108.0 s);
  - availability 99.7 s (100 requests, spanning 99.0 s);
  - API 0.7 to 0.9 s.
- After each run, no `/tmp/bpfpg-*` directory and no postgres, API or ingest process was left.

**`cd server && uv run pytest tests/test_fullstack_api.py -v`:** 9 passed, twice: in 215 s (alone) and in 216 s (concurrently with run 3). It skips all 9 tests when `node` is not on the PATH, and when there is no web build (checked by pointing the test at a missing build).

**The launcher's teardown,** checked by hand. Each case ended with `teardown.json` `clean: true`, and no cluster directory or child process left:
- SIGTERM once the stack was ready: exit 0;
- stdin closed once the stack was ready: exit 0;
- two SIGTERMs in the middle of the daily ingest: exit 130, and the running ingest was stopped.

**The browser test's detectors,** each checked by making it fail on purpose. A temporary copy of the spec, since deleted, injected one fault per run:
- a wrong rank or total in the rendered ranking;
- a quote JSON that differs from the API's answer;
- a coordinate in a request URL, and one in a request body;
- a fetch to another origin, which the CSP blocks, so it is reported as a CSP violation and a console error;
- an inline script, a `console.error` and the text "Akció";
- a popup and a navigation to another origin.

Each one failed the test with its own message.

**Other checks:**
- `npm run check`: 0 errors, 0 warnings. `tsc` on `playwright.fullstack.config.ts` and `tests/fullstack/*.ts`: no errors.
- `ruff check` and `ruff format --check` pass on `tests/fullstack/` and `tests/test_fullstack_api.py`.
- `uv run pytest -m "not db"`: 2233 passed, 4 skipped (no real GVH samples yet).
- `npx playwright test --config playwright.fullstack.config.ts --list` works without a running stack.

**Not done: a run on PostgreSQL 18.** The `postgres:18` image's binaries would run on this host (they need glibc ≤ 2.39). But the cluster runs as the unprivileged `bpfpg` user, which cannot reach a scratch directory under the root-only `/tmp/claude-0`. On a machine with PostgreSQL 18 installed, `_common.sh` picks it automatically; `BPF_PG_BIN` points it at another installation.
