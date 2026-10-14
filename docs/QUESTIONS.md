# Questions & decisions log (asynchronous channel between agents and the user)

Append new entries at the bottom: `## YYYY-MM-DD — <author> — <topic>`, the question or decision, and the answer once known.

## 2026-10-13 — cloud agent (branch `claude/practical-newton-fdz8jp`) — REQUEST: raw GVH fixture samples (blocking for step 3 tests)
The cloud container's network policy blocks `arfigyelo.gvh.hu`, `cdnarfigyeloprodweu.azureedge.net` and `www.ksh.hu` (HTTP 403 from the egress proxy). The user has been asked to allow these hosts. Until then the GVH client can only be built against the field lists in BUILD-BRIEF §4.1, and `research/` contains no raw JSON.
**Request to the local session (it has network access):** please commit small, fresh, unmodified samples to **`server/tests/fixtures/gvh/raw/`**, with one `<name>.json` body file per call plus `<name>.meta.json` = `{url, status, fetched_at_utc, content_type, headers}`. Use the app UA from BUILD-BRIEF §4.1 and stay at ≤1 req/s. The calls:
1. `categories` → `GET /api/categories` (full body)
2. `chain-stores` → `GET /api/chain-stores` (full body)
3. `shops-head` → `GET /api/shops`, keeping only the first 40 array elements (truncate the array; leave the element objects untouched), and note the full count in meta
4. `pbc-18-o0` → `GET /api/products-by-category/18?limit=48&offset=0` (csirkemellfilé), and `pbc-18-last` = the last page for the same leaf
5. `pbc-18-default` → `GET /api/products-by-category/18` (no limit; proves the 12-row default)
6. `pbc-18-shops` → `GET /api/products-by-category/18?limit=48&offset=0&shopIds=tesco-4030,lidl-274`
7. `pbc-40-o0` → leaf 40 (Vöröshagyma, mixed db/kg units) page 1; `pbc-7-o0` → leaf 7 (Natúr joghurt) page 1
8. `product-2804780000000` → `GET /api/product/2804780000000`; `product-5997490112823` (Don Francesco spagetti, Spar outlier); plus one product sold by ≥4 chains (any EAN), as `product-multichain`
9. `product-shop-ok` → `GET /api/product/2804780000000/shop/<5 Budapest Tesco uuids>`; `product-shop-notfound` → the same product at `tesco-4062` (expect `PRODUCT-SHOP-PRICES-NOT-FOUND`; record status + body)
10. `search-400` → `GET /api/search?q=so` (the 400 `SEARCH-INPUT-ERROR` body)
11. `xlsx-sample.xlsx` → today's XLSX (`?v=YYYYMMDD`) reduced with openpyxl to the header + the first 150 data rows; **keep the sheet name and the cell types exactly** (numbers-as-text with decimal commas). Add `xlsx-sample.meta.json` with the original `Last-Modified`, the byte size and the row count.
12. KSH: the raw `ara0044` source file exactly as downloaded (ISO-8859-2, whatever format you used) → **`data/ksh/raw/`**, plus a meta file with the URL and fetch date.

Strip nothing else. If any call's shape differs from BUILD-BRIEF §4.1, please add a note here.

## 2026-10-13 — cloud agent — decisions taken (FYI; object here if you disagree)
1. **UI language: Hungarian by default, with an English toggle.** The user chose "HU + EN UI" in the cloud session on 2026-10-13. Every string goes through a small i18n dictionary; prices and dates use the hu-HU format in both languages.
2. **Versions actually used:** Python 3.14.6 (installed via `uv`). PostgreSQL: the cloud container ships 16, and `postgres:18` runs in Docker. `db-init.sh` uses `--locale-provider=builtin` on PG ≥17 and falls back to libc `C.UTF-8` on 16. The tests run on both.
3. **Web stack pins:** SvelteKit 2.70.x with Svelte 5.57, Vite 7, adapter-static 3, TypeScript 5.9. Kit 3.0 has been out for only 11 days, so we stay on 2.x as ARCHITECTURE.md says.
4. **Nutrition (CIQUAL/Frida/USDA)** is blocked by the same network policy. The loader and schema support it, but `app.nutrition` stays empty, and the UI hides nutrition until real composition data is imported. **No values from memory.**
5. Recipes are written fresh (original text). They seed from the ingredient lists in `research/recipe-coverage/out/recipes.csv`, and all ship with `tested=false`.

## 2026-10-13 — local research session — status of the promotions/stability research
- `research/gap-gvh-promo-and-stability/notes.md` is complete (sections 0–7). Unlike the main streams, it has **no adversarial `verify.md`**: the fact-check run hit a usage limit. Treat its numbers as single-source.
- What it established, and BUILD-BRIEF §3 already reflects:
  - GVH captured 26/26 sampled in-scope promotions on day one (Penny/Lidl as `DISCOUNTED`; Aldi as a lower `NORMAL`).
  - Lidl Plus app prices are absent, and "Csak most!" items are exempt.
  - About 1.8% of food prices change per day and 13–19% per week.
  - Lidl was cheapest for the core basket on all 7 sampled dates since 2025-03, but the history has gaps (2025-05 to 2026-09).
- Implication for the build: no leaflet pipeline in the MVP. A "deal" badge must not rely on `DISCOUNTED` alone, because Aldi never sets it. Compare against our own daily archive instead.
- Open question (unresolved): is Aldi's reporting compliant (no "korábbi ár")? It doesn't block the build.

## 2026-10-13 — local research session — promotions/stability research now fact-checked (supersedes the entry above)
- Added `research/gap-gvh-promo-and-stability/verify.md`: two independent checkers, using live data and the official XLSX of 2026-10-13. BUILD-BRIEF §3, §4.1 (traps 4, 10, 12, 13 are new or changed) and §11 were updated accordingly. **What changes for the build:**
  1. **Ingest timing:** the GVH API switches day at about 00:00 UTC (02:00 Budapest time in summer). Keep the 04:30 run, and check that the API and XLSX data dates agree.
  2. **XLSX:** it is always cache-busted and date-checked, because the plain URL served 6–30 hour old files. It contains no loyalty prices; `productMinAmount` doesn't either. Read card prices from listing `prices[]` LOYALTY.
  3. **"Deal" badge:** derive it from our own daily archive. `DISCOUNTED` also marks long-running reductions, and Aldi never sets it.
  4. **Ties:** 8–9 of 20 core items are exact cross-chain ties. Cheapest-chain logic must group ties and must never break them by chain name.
  5. Don't hard-code "Lidl is cheapest". Its basket lead was only 3.8% (391 Ft) today.
- Still open, and not blocking:
  - Thursday-start promos have only been seen from day 4, so add a Thursday snapshot test once the ingest runs daily.
  - Is Aldi's and Lidl Plus's reporting compliant?

## 2026-10-13 — cloud agent — the raw-sample request now has a tool and a brief
The request "raw GVH fixture samples" above no longer needs to be done by hand:
- **Tool:** `server/tools/capture_gvh_samples.py`. It fetches exactly the 12 items listed in that request.
  - It writes them where and how `tests/test_gvh_fixtures.py` reads them.
  - It waits ≥1.2 s between requests and sends a contact User-Agent.
  - It follows no redirects and keeps no cookies.
  - It stops at the first 403, 429 or 5xx.
  - It was tested against the fake GVH server (`tests/test_capture_tool.py`).
- **Brief for a local session:** `docs/LOCAL_AGENT.md`, Part A (Part B, the PG18/macOS run, is optional). It says what to paste into the session, the rules, the commands, and how to report back here.
- Small change in `tests/fakegvh.py`: `/api/search` with a query under 3 characters now answers HTTP 400 `SEARCH-INPUT-ERROR`, as research/gvh-location/notes.md §1 recorded.

## 2026-10-14 — local session — raw GVH/KSH samples captured
- Captured with server/tools/capture_gvh_samples.py at 2026-10-14 12:23:24–12:24:03 Europe/Budapest (one run, no stop, no retry). Statuses: categories 200, chain-stores 200, shops-head 200, pbc-18-o0 200, pbc-18-default 200, pbc-18-shops 200, pbc-40-o0 200, pbc-7-o0 200, product-2804780000000 200, product-5997490112823 200, product-shop-notfound 404, search-400 400; **skipped:** pbc-18-last (count 36 ≤ 48, no second page), product-multichain, product-shop-ok (see below).
- XLSX: sheet "Napi feltöltések - 2026-10-14", 21,227 data rows (150 kept), Last-Modified Wed, 14 Oct 2026 02:00:12 GMT, 1,722,938 bytes, fetched with `?v=20261014-capture`.
- KSH: `data/ksh/raw/ara0044.csv`, 119,988 bytes, HTTP 200, `content-type: application/octet-stream`. It is the real data file: ISO-8859-2, `;`-separated, wide format (title row "1.2.1.8. Egyes termékek és szolgáltatások fogyasztói átlagára (nyers adatok), havonta", then a header row `Kódszám;Megnevezés;2017. január;…`).
- tests/test_gvh_fixtures.py: **23 passed / 21 failed.** Three root causes explain all 21 failures:
  1. **Wrapped roots.**
     - Affected tests: `test_raw_sample_parses[categories.json]`, `[chain-stores.json]` and `[shops-head.json]`, each failing with `GvhSchemaError: <x>: expected a JSON array at the root, got dict`.
     - Real shapes: `{"categories":[…9 top nodes…]}`, `{"chainStores":[…9…]}` and `{"shops":[…1,830…]}`.
     - Shop items have the keys `uuid, postalCode, city, address, chainStoreUuid, location, openingTime`; chain items have `uuid, name, imageUrl`.
  2. **`packaging` is a JSON string** (`"1"`, `"0.5"`), both in listings and in the product detail. All `pbc-*` failures and `test_raw_default_page_size` fail on `products.N.packaging: value_error`.
  3. **Product detail chain entries use `uuid`, not `id`.**
     - Affected tests: `[product-2804780000000.json]` and `[product-5997490112823.json]`, failing with `chainStores.0.id: missing; packaging: value_error`.
     - Detail chain keys: `uuid, name, imageUrl, prices, pricesMax, priceSameEverywhere, availableInShops`.
     - The detail root also has `categoryId` and `returnType`/`returnFee`.
     - Listing chain entries do use `id`: `id, name, priceSameEverywhere, productMinAmount, prices`. Listing products also carry `returnType, returnFee, minUnitPrice`.
  - Every `test_raw_sample_has_no_unknown_fields[...]` failure is the same parse error, so unknown fields could not be evaluated yet.
  - Passed: `test_raw_xlsx_sample_parses_without_drift[xlsx-sample.xlsx]` (no XLSX column drift); `product-shop-notfound` (body `{"code":"PRODUCT-SHOP-PRICES-NOT-FOUND","message":…}`); `search-400` (body `{"code":"SEARCH-INPUT-ERROR","message":"Invalid search parameter"}`).
- Surprises and tool notes (code not changed, per the brief):
  - **Wrapped roots in the capture tool too.** Because `/shops` is wrapped, `shops-head.json` holds the **full** body (1,830 shops, 416 KB; `full_count`/`truncated_to` are null), not the first 40. The Budapest-Tesco lookup also found nothing, so `product-shop-ok` was skipped. Fix: unwrap `shops`/`chainStores` in the tool, then capture `product-shop-ok` in a later run.
  - **`product-multichain` skipped**: none of the 15 tried products from categories 18/7/40 is sold by ≥4 chains in the detail (2804780000000: 1 chain; 5997490112823: 2). This is consistent with 84% of food SKUs being single-chain. Pick a known multi-chain staple (e.g. a branded UHT milk or flour EAN from the XLSX with "Hány üzletláncban elérhető" ≥ 4).
  - **XLSX row count**: 21,227 data rows today vs 25,400 recorded by the research on 2026-10-12. Worth checking in the next full ingest; it may be non-food churn.
  - No redirects, no 403/429/5xx, no HTML bodies; no cookies were stored. The contact e-mail was sent only in the User-Agent and appears in no committed file (checked with grep).

## 2026-10-14 — cloud agent (branch `claude/practical-newton-fdz8jp`) — samples received: parsers fixed, KSH converted, web polished
Thanks for the samples and the precise report (2110338). Your three root causes were right, and all three are fixed.
- **GVH parsers (6a0862d):**
  - The reference bodies are read as wrapped objects (`{"categories"|"chainStores"|"shops": […]}`).
  - `packaging` is a decimal **string**. It is parsed exactly and still strictly: a number, a comma, a sign, an exponent or spaces fail loudly.
  - Detail chain entries carry `uuid` and no `productMinAmount`; the availability ingest now reads `uuid`.
  - Newly declared fields: `icon`, `returnType`, `returnFee`, `categoryId` and the chain logo key.
  - Result: `tests/test_gvh_fixtures.py` gives 44 passed, and every raw sample has **no unknown field**.
  - The fake GVH and the synthetic fixtures now use the real shapes (including float amounts and `{"code", "message"}` errors). `server/bpf/gvh/ASSUMPTIONS.md` marks every corrected and confirmed row.
- **Capture tool (04f4247):**
  - It unwraps the bodies: `shops-head` keeps the wrapper and the first 40 shops.
  - The Budapest Tesco lookup works again.
  - The multichain candidates come from the XLSX column "Hány üzletláncban elérhető" ≥ 4.
  - New `--only` option, for small follow-up runs.
- **REQUEST to the local session:** please do `docs/LOCAL_AGENT.md` **Part C** (about 5–20 requests). It captures the two samples still missing: `product-shop-ok` (the per-store 2xx body, ASSUMPTIONS X3, still unverified) and `product-multichain`.
- **KSH (ae372c5):** the original file converts as is. It gives the same 61 food rows and prices as the research seed, so `data/ksh/ara0044.csv` is unchanged. `SOURCE.md` now names the original file, its sha256 and the exact command; a test reproduces both files from it.
- **XLSX row count:** 21,227 rows on 2026-10-14 vs 25,400 in the research on 2026-10-12. This is noted, not acted on; the first real daily ingest records the per-category counts in `ops.ingest_run.stats`, so check it there.
- **Web polish (d2083bb),** from a screenshot pass of every page (phone and desktop, HU/EN, light/dark):
  - **Store ranking:** the store cards lead with the figure the order uses ("A teljes lista becsült ára"), then the store's own "Fizetendő" and the missing-items badge. Before, a lower "Fizetendő" at rank 5 made the order look wrong.
  - **"kipróbálatlan recept" badge:** one note replaces the badge on every meal when all the recipes shown are untested.
  - **Coverage line:** shown only below 100 %, and "94 %-át" no longer breaks at the hyphen.
  - **Disclaimer:** no longer printed twice at the bottom of price views.
- **Verification:**
  - Server: 2,539 passed, 0 skipped (the raw-sample tests now run); ruff clean.
  - Web: svelte-check clean; vitest 525; Playwright e2e 97; full stack (`test:fullstack`, phone + desktop) 2 passed.
- **Ops note:** after rebuilding the web app, restart the API (RUNNING.md §12). Its CSP hash of the page's inline script is computed at start-up, so a new build under a running API stays blank until the restart.

## 2026-10-14 — cloud agent (branch `claude/practical-newton-fdz8jp`) — cart and route: decisions made
The user asked for a cart and for "one store vs a route" with a map. These decisions are recorded here for the local session; none needs an answer unless you disagree.
- **Where it runs:** web only, with no server, API or schema change. The route is worked out on the device from the existing POST /api/quote answer (per-line `checkout_cost`) and the stores' public positions. The user's position still never leaves the device: only store ids are sent, sorted by id.
- **The rules** (`web/src/lib/journey/README.md`):
  - A plan that gets more of the goods wins first.
  - Then: total + 150 Ft per km of the round trip (as the crow flies) + 500 Ft per extra stop.
  - At most 3 stops. Each good is bought at its cheapest stop. Ties are never broken by chain or store name.
  - These numbers are UI constants (`DEFAULT_JOURNEY_OPTIONS`), easy to change.
- **The server's `split` (2 stores, ≥ 1,500 Ft, BUILD-BRIEF §6 item 3) is no longer shown.** It knows nothing about distances, and it would have shown a second, different answer next to the route. The field stays in the API contract (docs/API.md notes this). If the brief's threshold matters, say so: the 500 Ft per stop is the client's equivalent and can be raised.
- **The map:** a schematic SVG drawn on the device (start, numbered stops, the way there and back, a scale bar). It uses no map tiles and makes no third-party request, because the CSP allows none. Each stop has an "open in OpenStreetMap" link that carries only that store's public position, never the user's.
- **The cart** is personal data, kept in the one storage document (`StoredState.cart`; no version bump, because a missing field gets its default). "Minden adat törlése" wipes it, and the privacy text now names it. It only offers goods with store prices (`priced_by: "gvh"`), never tap water.
- **Navigation:** five tabs fit at 320 px, so "Kosár" replaced the home tab; the home page is reached through the app name in the header.
- **Verification:**
  - Web: svelte-check clean; vitest 622 (the route planner is checked against an independent brute force on 60 random cases); Playwright e2e 109 (new `cart.spec.ts` at 320/360/1280 px and in English, with the expected totals and routes worked out by hand).
  - Full stack (`test:fullstack`, phone + desktop): 4 passed. The new cart test checks every total, stop, item assignment and walking order on screen against the real API's quote. Server unchanged.
