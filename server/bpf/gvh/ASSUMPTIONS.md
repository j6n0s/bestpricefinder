# GVH Árfigyelő: shape assumptions of `bpf.gvh`

The API is undocumented. Everything below comes from BUILD-BRIEF §4.1 and `research/gvh-location/notes.md`
§1–2, §5–6 (corrected by `verify.md`), `research/gap-gvh-promo-and-stability/notes.md` (corrected by its
`verify.md`, the 2026-10-13 fact-check) and `research/competitors/verify.md`. **No real response has been
checked by this code yet** (the cloud container cannot reach GVH; samples were requested in
`docs/QUESTIONS.md`, 2026-10-13).

**How to check:** put the samples in `server/tests/fixtures/gvh/raw/` (names as in QUESTIONS.md) and run
`uv run pytest tests/test_gvh_fixtures.py`. A schema error means an assumption below is wrong; an "unknown
field" failure means a field to review and declare in `models.py`. Then update this file.

Legend: **R** = required (the ingest uses it; missing or wrong type → `GvhSchemaError`), **O** = optional
(documented, unused, may be absent), **N** = may be `null`. Models are strict: a JSON string where a number is
expected (or the reverse), `true` for a number, an unknown enum value or `NaN`/`Infinity` is an error.
Unknown extra fields are accepted and recorded as drift warnings (`Model.field`).

## Transport

| # | Assumption | Source / note |
|---|---|---|
| T1 | Base URL `https://arfigyelo.gvh.hu/api`; every endpoint answers `GET` with a JSON body (UTF-8). | notes §1 (bundle) |
| T2 | No gzip, no ETag, no rate limit observed; responses are uncompressed. The client still sends `Accept-Encoding`. | notes §6 |
| T3 | An unknown path under `/api` returns the SPA's `index.html` with **200** → treated as "not JSON" (`GvhSchemaError`). | notes §6 (`robots.txt` → SPA) |
| T4 | Errors are 4xx with a JSON body that contains an upper-case, dash-separated code (e.g. `SEARCH-INPUT-ERROR`). Only the code is kept; the body is never logged. | notes §1 (search 400) |
| T5 | No redirects are needed; 3xx is treated as an error. | assumption |

## `GET /categories`

| # | Field | Type | | Note |
|---|---|---|---|---|
| C1 | root | array of top-level nodes | R | not an object wrapper |
| C2 | `id` | integer | R | leaves 1–163, level 2 `2xxx`, top `1xxx` |
| C3 | `name` | string | R | the six food tops are matched by name (accent/case-folded): "Tejtermék, sajt, tojás", "Hús, hal, felvágott", "Zöldség, gyümölcs", "Pékáru", "Tartós élelmiszerek, italok", "Speciális étrend" |
| C4 | `path` | string | R | ≤ 300 chars; format assumed like `tejtermek_sajt_tojas/tej/esl_28` (`research/recipe-coverage/out/gvh_leaf_categories.csv`) |
| C5 | `categoryNodes` | array of nodes | O N | children; a leaf has `[]`, `null` or no key |
| C6 | depth | 3 levels (9 / 42 / 161) | | > 5 levels fails the run |

## `GET /chain-stores`

| # | Field | Type | | Note |
|---|---|---|---|---|
| H1 | root | array | R | 9 chains |
| H2 | `uuid` | string | R | referenced by `/shops.chainStoreUuid` and by the listing's `pricesOfChainStores[].id` |
| H3 | `name` | string | R | slug derived from it ("Müller" → `muller`); the XLSX `Üzletlánc név` is mapped to a chain through the same slug rule |
| H4 | `imageUrl` | string | O N | a logo: never stored or shown (BUILD-BRIEF §8.3) |

## `GET /shops`

| # | Field | Type | | Note |
|---|---|---|---|---|
| S1 | root | array | R | 1,829 stores |
| S2 | `uuid` | string | R | e.g. `spar-110`, `aldi-J179`, `tesco-4062`, `mueller-5253` |
| S3 | `chainStoreUuid` | string | R | |
| S4 | `postalCode` | **string** | R N | `"1011"`; a JSON number would fail (check!) |
| S5 | `city`, `address` | string | R N | |
| S6 | `location` | object `{latitude, longitude}` | R N | both **numbers** (not strings); a store without location is skipped |
| S7 | `openingTime` | string | O N | only Lidl (and 2 others) fill it, e.g. `Nyitvatartás: 06:30-21:30#…` |

## `GET /products-by-category/{id}?limit=48&offset=N[&shopIds=a,b]`

| # | Field | Type | | Note |
|---|---|---|---|---|
| L1 | root | object `{products, count}` | R | |
| L2 | `count` | integer | R | total for the category (all pages) |
| L3 | paging | default page 12; `limit` capped at 48; `offset` is a row offset | | the client always sends `limit=48` and fails on a page shorter than 48 before `count` |
| L4 | `shopIds` | comma-joined store uuids in the query string | | store-level view (only products those stores carry, at their prices) |
| L5 | top-level ids (`1xxx`) | `count: 0` | | level-2 ids (`2xxx`) work too |
| P1 | `products[].id` | **string** | R | EAN-13, in-store `2…` codes, `lidl-0080000`, `aldi-320458`, `penny-108`; a JSON number would fail |
| P2 | `name` | string | R | Tesco counter names are upper-case and accent-less |
| P3 | `unit` | string | R | `kg`, `l`, `db`; anything else is skipped by the ingest with a warning |
| P4 | `unitTitle` | string | R N | `kg` = sold by weight (lédig/counter); `csomag` = fixed pack (model.py docstring) |
| P5 | `packaging` | number | R N | pack size in `unit` (e.g. `0.5`) |
| P6 | `bulk` | boolean | O N | unreliable (differs between listing and detail) |
| P7 | `imageUrl` | string | O N | never used |
| P8 | `categoryPath` | any | O | type unknown; unused |
| P9 | `minUnitPrice` | number | O N | unused |
| P10 | `pricesOfChainStores` | array, **at most 3 chains** | R | the 3-chain cap is completed from the XLSX |
| P11 | `…[].id` | string | R | the chain uuid (= `ChainStore.uuid`); if unknown, the chain is matched by `name` |
| P12 | `…[].name` | string | R | |
| P13 | `…[].priceSameEverywhere` | boolean | R N | listing flag follows the 80 % notion |
| P14 | `…[].productMinAmount` | number | R N | the price charged by ≥ 80 % of carrying stores (what GVH displays) |
| P15 | `…[].prices[]` | array of price entries | R | per type the **minimum** across the chain's stores |
| P16 | price `type` | `NORMAL` \| `DISCOUNTED` \| `LOYALTY` | R | any other value fails loudly |
| P17 | price `amount` | number (HUF, gross) | R | |
| P18 | price `unitAmount` | number | R N | HUF per `unit`; ≈ `amount / packaging` (0.5 % inconsistent; reported, kept as published) |
| P19 | price `sameAmountEverywhere` | boolean | O N | listing only |

## `GET /product/{id}`

| # | Field | Type | | Note |
|---|---|---|---|---|
| D1 | root | object with the product fields (P1–P9, all optional here except `id`) | R | |
| D2 | chain list key | **`chainStores`** (notes §1); `pricesOfChainStores` is accepted too | R | every chain selling the product (no cap) |
| D3 | `chainStores[].id` | string (chain uuid) | R | same as P11 |
| D4 | `chainStores[].name` | string | O N | |
| D5 | `chainStores[].prices[]`, `pricesMax[]` | price entries | O N | min / max per type; `pricesMax` may hold NORMAL only |
| D6 | `chainStores[].priceSameEverywhere` | boolean | O N | literal flag |
| D7 | `chainStores[].productMinAmount` | number | O N | |
| D8 | `chainStores[].availableInShops` | array of store uuid strings | R | stores that report a price (not shelf stock) |
| D9 | unknown product | 4xx (assumed 404) | | recorded as `product_not_found` |

## `GET /product/{id}/shop/{uuid1,uuid2,…}`

| # | Field | Type | | Note |
|---|---|---|---|---|
| X1 | path | the store ids comma-joined and **URL-encoded** (`%2C`), product id URL-encoded | | notes §1 ("comma-joined, URL-encoded") |
| X2 | chunk size | ≤ 200 ids per call (verified up to 200; URL ≈ 2.5 KB) | | |
| X3 | root | object `{shops: [{shopUuid, prices: [{type, amount, unitAmount}]}]}` | R | only stores that carry the product |
| X4 | not sold at any requested store | a body containing `PRODUCT-SHOP-PRICES-NOT-FOUND`; the status is not documented: any error status (4xx, or 5xx, then without retrying) or a 2xx body naming the code without `shops` is accepted | | → empty result |
| X5 | stores not requested in the answer | ignored with a warning | | |

## Daily XLSX `arfigyelo_napi_termekadatok.xlsx`

| # | Assumption | Note |
|---|---|---|
| Y1 | URL `https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx`; the client adds a cache-buster **unique per run**, `?v=YYYYMMDD-<run id>` (the expected data date, then the `ops.ingest_run` id; outside a run an injectable suffix, by default `x` + 12 random hex digits). Any unknown query value reaches the origin; the edge then caches that copy under it | gap-gvh-promo-and-stability/verify.md "(d) Timing": the plain URL served copies 6–30+ h old (depending on `Accept-Encoding`) despite `max-age=3600`; verify §2(a). A per-day value is not enough: a run before the ~02:00 UTC regeneration would cache yesterday's file under today's value and the scheduler's retry would get it again |
| Y2 | Exactly one sheet named `Napi feltöltések - YYYY-MM-DD` (NFC, whitespace-collapsed); that date must equal the data date, else `StaleXlsxError` | other sheets are ignored |
| Y3 | The first non-empty row is the header; blank rows are skipped | |
| Y4 | 14 headers, located **by exact text** (order changes are reported as drift, unknown extra headers too; a missing or duplicated header fails): `Termék azonosító`, `Termék név`, `Kategória azonosító`, `Kategória név`, `Üzletlánc név`, `Egység`, `Kiszerelés`, `Minimum ár`, `Maximum ár`, `Minimum egységár`, `Maximum egységár`, `Hány üzletláncban elérhető`, `Hány boltban elérhető`, `Üzletlánc összes boltja` | notes §5, verify §2 |
| Y5 | Numbers are **text with a decimal comma** (`"1699,0000"`), no thousands separator; integers may be `"296"` or `"296,0000"`; real numeric cells are accepted too. `"1.699,00"`, `"1 699,00"`, `"1699.00"` are rejected | verify §2(b) |
| Y6 | `Termék azonosító` is a **text** cell (a numeric cell would have lost EAN leading zeros → error) | |
| Y7 | Required non-empty: product id, product name, category id, chain name, unit. Packaging, prices, unit prices and counts may be empty | |
| Y8 | One row per product × chain, all 161 categories; min/max = the daily price (DISCOUNTED included, LOYALTY excluded) across the chain's stores. So `Minimum ár` = min over the chain's stores of min(NORMAL, DISCOUNTED) = min(listing `prices[]` NORMAL, DISCOUNTED) on the same day | notes §5 (22,870 pairs, 23 disagreed = 0.1 %); gap-gvh-promo-and-stability/verify.md "(d) Timing" (100 % of pairs; 1,925/1,925 same-day) |
| Y9 | `Üzletlánc név` matches a chain name from `/chain-stores` under the slug rule (case/accents/extra words ignored) | assumption |

## Semantics the ingest relies on

| # | Assumption | Source |
|---|---|---|
| M1 | `productMinAmount` = price of ≥ 80 % of carrying stores (else the minimum), LOYALTY excluded → `product_min_amount`; `prices[]` minima → `normal_*`/`discounted_*`/`loyalty_*` | verify "biggest correction"; gap-gvh-promo-and-stability/verify.md §7 item 3 |
| M2 | XLSX `min < max` ⇔ the chain's stores charge different daily prices → per-store calls | notes §5, verify §2 |
| M3 | Retailers upload day-D prices by the end of D-1; the **API switches at about 00:00 UTC** (02:00 Budapest in summer, 01:00 in winter), not at Budapest midnight, and carries no date; the XLSX is built at 02:00:12 UTC → the ingest runs at ~04:30 Budapest and the data date is "today in Europe/Budapest" | BUILD-BRIEF §4.1 trap 10; gap-gvh-promo-and-stability/verify.md "(d) Timing" |
| M4 | Tesco store format from the id: `tesco-1xxx` hyper, `tesco-4xxx` Expressz | notes §2 |
| M5 | **Date agreement** (M3 + Y8): on the same day the XLSX `Minimum ár` and the listing's min(NORMAL, DISCOUNTED) agree on ≈ 99.9 % of product × chain pairs (intraday changes); consecutive days differ on 1.2–2.6 %. The daily ingest compares them on every pair present in both (difference > 0.5 Ft = disagreement), always records the agreeing share (stat `api_xlsx_agreement`) and, above 0.6 % disagreeing, records `api_xlsx_date_mismatch` (share, pair count, ≤ 10 examples) and ends `partial`. `productMinAmount` is not comparable (80 % price), LOYALTY neither (Y8) | notes §5; BUILD-BRIEF §3 "Stability", §4.1 trap 10 |
| M6 | **Loyalty prices** exist only in the listing/detail `prices[]` (`type: LOYALTY`) and in the per-store endpoint. The XLSX and `productMinAmount` exclude them, so `loyalty_*` is filled from those two sources only (a pair known only from the XLSX has none). In food, Lidl had no LOYALTY entry (0 of 385: Lidl Plus prices are absent) and Aldi no DISCOUNTED one (0 of 420: its promos are lower NORMAL prices) | gap-gvh-promo-and-stability/verify.md §0 rows b–c, §3–4, §7 item 3, "(d) Timing" |
