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
