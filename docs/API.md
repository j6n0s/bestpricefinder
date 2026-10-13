# HTTP API (`/api`)

**Status:** contract v1, written 2026-10-13 by the cloud agent before implementation. The machine-readable source of truth is [`server/bpf/api/schemas.py`](../server/bpf/api/schemas.py). The OpenAPI document generated from it (`docs/openapi.json`, written by `python -m bpf.api.openapi`) drives the web client's TypeScript types. If this file and the models disagree, the models win; fix this file.

## Principles

- **Stateless and read-only.** There are no accounts, no cookies and no sessions. The server stores nothing about a request. Request bodies are never logged.
- **No personal data in.** No coordinates, addresses or identifiers. The client computes distances on the device and sends only the store ids it picked. Diet exclusions in `/api/plan/suggest` are used only for that computation and never stored or logged.
- **Same origin.** The SPA and the API share one origin, and no CORS headers are sent unless `BPF_ALLOWED_ORIGINS` is configured.
- **Every price carries its source and data date.** Responses carry `data_date` and `attribution`. "Cheapest" statements are always scoped by `scope_note_hu`: "a kiválasztott boltok közül, a {date} GVH-adatok alapján".
- **Chains are identified by `slug`** (`aldi`, `auchan`, `lidl`, `penny`, `spar`, `tesco`, plus the drugstores `dm`, `rossmann`, `muller`).
- **Numbers.** Money is in HUF as a JSON number with at most 2 decimals; the UI shows whole forints. Quantities are in the ingredient's canonical unit (`kg`, `l` or `db`) with at most 3 decimals. Request quantities are rounded half-up to 0.001.

## Common behaviour

| Topic | Behaviour |
|---|---|
| Content type | Requests to POST endpoints must be `application/json` (else 415). Responses are `application/json; charset=utf-8`. |
| Body size | At most `BPF_API_MAX_BODY_BYTES` (default 65,536). Larger bodies get 413 before parsing. |
| Rate limit | Per client IP, token bucket, `BPF_API_RATE_LIMIT_PER_MINUTE` (default 120) with a burst of 30. The client IP is the socket peer. `X-Forwarded-For` is used only when `BPF_TRUST_PROXY_HEADERS=true` (behind Caddy), and then only the right-most entry. Over the limit: 429 with `Retry-After`. |
| Errors | Body `{"error": <code>, "fields": [...]}`. Codes: `invalid_request` (422; `fields` = dotted paths, never values), `not_found` (404), `method_not_allowed` (405), `payload_too_large` (413), `unsupported_media_type` (415), `rate_limited` (429), `no_data` (503, no successful ingest yet), `internal` (500, no details). |
| Caching | GET responses carry `ETag` (a hash of data date + payload) and honour `If-None-Match` with 304. `Cache-Control`: `/api/stores` and `/api/ingredients` `public, max-age=3600`; `/api/meta`, `/api/recipes*` and history `public, max-age=300`; `/api/health` `no-store`. POST responses: `no-store`. |
| Security headers | On every response: `Content-Security-Policy` (see "Static hosting"), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Resource-Policy: same-origin`, `Permissions-Policy: geolocation=(self), camera=(), microphone=(), payment=(), usb=()`. Behind TLS (`BPF_HSTS=true`): `Strict-Transport-Security: max-age=31536000; includeSubDomains`. |
| Methods | Only the methods listed below; everything else is 405. `OPTIONS` is 405 unless CORS is configured. |
| Database | The API connects only as `bpf_api`: SELECT on `api.*` views, read-only transactions, 3 s statement timeout. |

## Endpoints

### `GET /api/health`
`200 {"status": "ok"|"degraded", "db": true, "data_date": "2026-10-13"|null}`. The status is `degraded` when the latest data is older than yesterday (Budapest time) or there has been no ingest yet. If the DB is unreachable: `503 {"status": "down", "db": false, "data_date": null}`.

### `GET /api/meta`
Data date, ingest time, a `stale` flag, the KSH period, the chain list, attribution texts and links (GVH, KSH, and nutrition when present), and the disclaimer in HU and EN. The HU disclaimer is exactly: "Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal."

### `GET /api/stores`
`{"data_date", "stores": [{id, chain, postal_code, city, address, lat, lon, format, is_budapest, has_data}]}`. Every store of every chain, about 1,829 rows. `has_data=false` means the store had no product on the latest data date; the UI must hide it or label it "nincs áradat". The client filters to grocery chains and computes distances itself.

### `GET /api/ingredients`
`{"ingredients": [{id, name_hu, list_group, unit, piece_weight_kg, pantry, priced_by: "gvh"|"ksh"|"none", tags}]}`.

### `GET /api/recipes?slot=&tag=&q=`
Optional filters:
- `slot`: one of the 5 slots;
- `tag`: one recipe tag;
- `q`: 2–40 characters, accent-insensitive substring search over the title.

Each item has: `id, title, summary, slots, servings, minutes, tags, tested, cost_per_serving_from, cheapest_chains, priced_share`. `cheapest_chains` lists **every** grocery chain tied at the minimum (equal after rounding to whole forints). It is a tie group, never an order; the UI must not single out one chain of a tie. `cost_per_serving_from` is the cheapest **chain-typical** used cost per serving across the grocery chains (the `productMinAmount` price, used quantities, pantry lines excluded). It is null when nothing can be priced.

### `GET /api/recipes/{id}`
The summary fields plus:
- `data_date`;
- `steps`;
- `lines`: `line_no, ingredient_id, ingredient_name, qty, unit, display, optional, pantry`;
- `chain_costs`: per grocery chain, `cost_per_serving`, `priced_share` and the `missing` ingredient ids;
- `nutrition`: per serving, or `null` until composition data is imported.

Unknown id: 404.

### `POST /api/list`
Request: `{"items": [{"recipe_id", "servings"}] (1–200), "on_hand": [{"ingredient_id", "qty"}] (≤200), "include_optional": true}`.
For each recipe, the line quantities are scaled by `servings / recipe.servings` and summed per ingredient. `on_hand` quantities are subtracted, and lines that drop to ≤0 are removed. Pantry ingredients stay in the list with `pantry: true`, so the UI can show "valószínűleg otthon van".
Response: `{"lines": [{ingredient_id, name_hu, qty, unit, list_group, pantry, recipe_ids}]}`, sorted by `list_group`, then `name_hu`. An unknown recipe id gives 422 with that field path.

### `POST /api/quote`
Request: `{"lines": [{"ingredient_id", "qty"}] (1–200, unique), "store_ids": [...] (1–25, unique), "include_loyalty": false}`.
For each store, every line is priced like this:
1. Candidate products: the ingredient's GVH leaves, filtered by its name rules and unit rules.
2. Keep the products this store carries: an explicit store price row, or the latest `availableInShops` list. With no availability data, the product is `assumed` available when the chain sells it.
3. Take the store's price: the per-store row if it exists (`price_scope: "store"`), else the chain's `productMinAmount` (`"chain"`). LOYALTY prices are used only when `include_loyalty` is set.
4. Choose the combination of whole packs that minimises the **checkout cost** for the quantity. Sold-by-weight products are bought at the exact weight.

Per line the response gives:
- `status`;
- `picks`;
- `checkout_cost` (packs paid) and `used_cost` (quantity × unit price);
- `leftover_qty`;
- up to 3 `alternatives`;
- a `ksh_estimate`, for KSH-priced ingredients only. It is labelled and **never** added to `checkout_total`.

Statuses: `priced`, `pantry` (a pantry staple with no GVH mapping, such as spices; never priced), `unavailable` ("nincs ebben a boltban"), `ksh_estimate`, `unpriced` ("nincs ár"). Pantry staples that *are* GVH-mapped (oil, flour) are priced normally when sent. By default the client leaves pantry lines out of the quote unless the user marks them "nincs otthon".

Per store: `checkout_total`, `used_total`, `missing`, `assumed_count`, `ksh_estimate_total`.
- `ranking`: sorted by `penalized_total` = `checkout_total` + for each missing line the median checkout cost of that line at the other requested stores that have it. **Ties share a rank** (1, 1, 3): equal whole-forint penalized totals and equal missing counts. The order inside a tie group carries no meaning; the client orders it by distance. Ties are never broken by chain or store name (BUILD-BRIEF §4.1 trap 13).
- `split`: the best 2-store split, only if it saves at least 1,500 Ft against the best single store; otherwise `null`.
- Also: `scope_note_hu` / `scope_note_en`, `attribution`, `data_date`.

Unknown store or ingredient: 422 with the field path. No successful ingest yet: 503 `no_data`.

### `POST /api/plan/suggest`
Request: `{days: 1–31 (7), slots: 3|5 (3), people: 1–12 (2), seed, exclude_tags[], exclude_ingredients[], red_meat_g_per_person_week (600), no_repeat_days (5), weekly_budget|null}`.
Response:
- `days`: `[{index, meals: {slot: recipe_id|null}}]`;
- `checks`: per 7-day week, rule results:
  - `fish ≥1`;
  - `legume ≥1`;
  - `meat_free_day ≥1`;
  - `red_meat ≤ g/person`;
  - `potato` (at most every second day);
  - `sweets ≤2`;
  - `variety` (no repeat inside `no_repeat_days` except `ket_napos` recipes on the next day);
  - `budget`, when set;
- `warnings`: machine codes; the client maps them to HU/EN text. The codes are `slot_pool_empty:<slot>`, `slot_pool_too_small:<slot>`, `no_fish_recipe_available`, `no_legume_recipe_available`, `no_meat_free_recipe_available:<slot>`, `no_potato_free_recipe_available:<slot>`, `red_meat_cap_unreachable`, `sweets_cap_unreachable`, `budget_unreachable` and `recipe_cost_missing`. The rule details are in docs/ENGINE.md.

The same `seed` and input always give the same plan.

### `POST /api/plan/check`
Request: `{days: [{index, meals}], people, red_meat_g_per_person_week, no_repeat_days, weekly_budget}`. Response: `{checks}`. The client uses it to re-check a plan the user edited, passing the same `no_repeat_days` it used for the suggestion.

### `GET /api/ingredients/{id}/history?chain=&days=`
Our own daily archive. Per chain, the cheapest matching product's chain-typical unit price per day, in the ingredient's canonical unit.
- `chain`: an optional slug.
- `days`: 7–365, default 30.

Response: `{ingredient_id, unit, days, series: [{chain, points: [{date, unit_price}]}]}`.

## Price types and "deals"
`price_type` is reported for transparency only. `DISCOUNTED` is **not** a weekly-deal flag: Aldi never sets it, and it also marks long-running reductions (BUILD-BRIEF §3). The UI may show "kedvezményes ár (GVH-jelölés)" as plain text, but must not show an "akció"/deal badge based on it. A future deal badge will compare against our own daily archive.

## Static hosting (the SPA)
- FastAPI serves `web/build` (adapter-static) at `/`, and the SPA fallback page for unknown non-`/api` paths.
- Hashed assets under `/_app/immutable/` get `Cache-Control: public, max-age=31536000, immutable`.
- `index.html` and `service-worker.js` get `no-cache`.
- **CSP:** SvelteKit (`kit.csp`, `mode: 'hash'`) writes a `<meta http-equiv="content-security-policy">` into the HTML, with the hash of its inline bootstrap script. At startup the server reads that policy from the fallback HTML and sends it as the HTML's `Content-Security-Policy` **header**, adding `frame-ancestors 'none'` (a meta tag cannot carry that). API JSON responses get `default-src 'none'; frame-ancestors 'none'`.
- The web build's policy is `default-src 'self'`, `script-src 'self' <hashes>`, `style-src 'self'` (plus `'unsafe-inline'` only if Svelte transitions need it; prefer none), `img-src 'self' data:`, `connect-src 'self'`, `manifest-src 'self'`, `worker-src 'self'`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`.
