# web/: Heti kosár PWA

SvelteKit 2 + Svelte 5 (runes only) + TypeScript (strict), built with `adapter-static` as a single-page app
(`ssr = false`, `prerender = false`, fallback `build/index.html`). FastAPI serves `web/build` at `/` and the
API at `/api` (docs/ARCHITECTURE.md, docs/API.md "Static hosting").

Pinned toolchain (exact versions, `package-lock.json` committed): @sveltejs/kit 2.70.3, svelte 5.57.2,
@sveltejs/adapter-static 3.0.10, @sveltejs/vite-plugin-svelte 6.2.4, vite 7.3.7, typescript 5.9.3,
svelte-check 4.7.6, vitest 3.2.7, @playwright/test 1.56.1 (matches the preinstalled Chromium build 1194),
@types/node 22.20.4. Node ≥ 22.12.

## Commands

Run them from `web/`.

| Command | What it does |
|---|---|
| `npm ci` | Install exactly the locked dependencies. |
| `npm run dev` | Dev server on http://127.0.0.1:5173. `/api` is proxied to the API on http://127.0.0.1:8000 (`python -m bpf.api`). |
| `npm run dev:mock` | Dev server with `/api` answered by the **synthetic** mocks in `tests/mocks/` (no server needed; responses carry `x-mock-data: synthetic`). |
| `npm run build` | Production build into `web/build/` (`index.html` is the SPA fallback; `service-worker.js`; hashed assets under `_app/immutable/`). |
| `npm run preview` | Vite preview of the build (note: the e2e tests use their own static server instead). |
| `npm run check` | `svelte-check` (types + Svelte a11y rules) over `src/`, `tests/`, `scripts/` and the configs; fails on any error **or warning**. |
| `npm test` | Vitest unit tests (`src/**/*.test.ts`, `tests/mocks/*.test.ts`). |
| `npm run test:e2e` | Builds, then runs the Playwright smoke tests in `tests/e2e/` against `web/build`. |
| `npm run gen:districts` | Regenerates `src/lib/data/districts.json` from `research/gvh-location/data/stores.csv` (`node scripts/gen-districts.mjs --check` verifies it is current). |
| `npm run gen:icons` | Redraws the app icon and renders the PNGs in `static/icons/` with the local Chromium. |

E2E options: `E2E_SCREENSHOT_DIR` (default `test-results/screenshots`, git-ignored) and `E2E_PORT` (default
4317). Playwright uses the browsers under `PLAYWRIGHT_BROWSERS_PATH`; never run `playwright install` here.

## What the e2e smoke test checks

Every route at 320×640, 360×740 and 1280×800 with all `/api` calls mocked: no console errors, no uncaught
errors, no CSP violations (`securitypolicyviolation` listener), no request to another origin, no horizontal
scroll, nav labels that fit, the disclaimer and the data date on every page; plus the CSP meta tag, the GVH
attribution text, language switch and persistence, settings persistence, "minden adat törlése" with its
confirmation, storage refused by the browser, the location consent flow (no geolocation call before the
explanation; `enableHighAccuracy: false`; position rounded to about 100 m; no request ever contains it;
revoke), a refused permission, keyboard skip link, 44×44 px touch targets, accessible names, dark mode,
`prefers-reduced-motion`, API error/retry, stale and "no data yet" states, and offline use through the service
worker with the server shut down. The test server (`tests/e2e/static-server.ts`) mimics FastAPI: SPA fallback,
the CSP copied from the meta tag into a header plus `frame-ancestors 'none'`, and the security headers.

## Layout

```
src/app.html, app.css          shell HTML; design tokens (light + dark), base styles, utility classes
src/routes/                    +layout.ts (ssr/prerender off), +layout.svelte (shell, /api/meta once),
                               home, beallitasok (settings), forrasok (sources & privacy),
                               terv, receptek, receptek/[id], lista: placeholders for the feature agents
src/lib/api/types.ts           hand-mirrored types of every model in server/bpf/api/schemas.py (to be replaced
                               by types generated from docs/openapi.json)
src/lib/api/client.ts          typed fetch for every endpoint: JSON only, 15 s timeout, ApiError, offline
src/lib/i18n/                  t()/tp() with typed keys, $state language; dictionaries per namespace,
                               <ns>.hu.ts (source) + <ns>.en.ts
src/lib/storage.ts             the ONE versioned localStorage document for all personal data
src/lib/geo.ts                 haversine, storesWithinRadius, pickNearestPerChain (on the device)
src/lib/location.ts            geolocation request (after consent), stored-location transitions, origin
src/lib/districts.ts           the 23 Budapest districts (generated data/districts.json)
src/lib/format.ts              hu-HU money ("1 234 Ft"), quantities, distances, dates ("2026. 10. 13.")
src/lib/meta.svelte.ts         MetaStore shared through context: getMeta()
src/lib/components/            Header, BottomNav, Attribution, Disclaimer, Badge, EmptyState, ErrorState,
                               Spinner, LocationExplainer, DistrictPicker
src/service-worker.ts          offline support (see below)
static/                        manifest.webmanifest ("Heti kosár" / "Kosár"), icons (original artwork)
scripts/                       gen-districts.mjs, gen-icons.mjs
tests/mocks/                   SYNTHETIC API data (see its README) + handler
tests/e2e/                     Playwright smoke test, static test server
```

## Rules for anyone extending the app

- **Text:** every user-visible string goes through `t('<ns>.<key>', params)`; add the Hungarian string to
  `<ns>.hu.ts` and the English one to `<ns>.en.ts` (a missing key is a type error, and a unit test compares
  keys and placeholders). hu-HU dates end with a full stop, so never write `{date}.` in a message.
- **Numbers:** money, quantities and dates are always formatted with `$lib/format` (hu-HU in both languages).
  Never do arithmetic on money in the client; the server computes totals.
- **Prices:** every view that shows a price renders `<Attribution dataDate={response.data_date} />` (add
  `ksh` when a KSH estimate is shown). Unpriced lines get `<Badge kind="no_price" />`, KSH values
  `<Badge kind="ksh_estimate" />`, untested recipes `<Badge kind="untested" />`. "Legolcsóbb" only with the
  server's `scope_note_hu`. No product images, no retailer logos: chain names as plain text.
- **Personal data** (plan, household, pantry, exclusions, location, ticks, language) is read and written only
  through `$lib/storage`. It never goes to the server, except what an endpoint needs: recipe ids and
  servings, ingredient ids and quantities, store ids, and the plan request fields. **Never send
  coordinates**: compute distances with `$lib/geo` and send store ids only. Ask for location only through
  `<LocationExplainer>`; offer `<DistrictPicker>` as the alternative.
- **CSP:** `kit.csp` mode `hash` with `style-src 'self'` and no `'unsafe-inline'`. So: style with classes
  only (no `style="…"` attributes, no `style:` directives), no Svelte transitions/animations, no
  `{@html}` with untrusted data, no inline event handler attributes (Svelte `onclick={…}` is fine), no
  external requests or fonts. SvelteKit's route announcer has an inline style in its generated root
  component; `vite.config.ts` (`cspSafeAnnouncer`) swaps it for the `.sveltekit-announcer` class and fails
  the build if a SvelteKit upgrade changes that markup.
- **Accessibility:** touch targets ≥ 44 px (`.btn`, `.choice`, `.input`, `.select` already are), visible focus
  (global `:focus-visible`), labels for every control, `prefers-reduced-motion` respected. `npm run check`
  must report 0 errors and 0 warnings.

## Service worker

`src/service-worker.ts`, registered by the root layout in production builds only (a refused registration is
ignored). Cache names carry the build version (`hk-shell-<version>`, `hk-api-<version>`); older caches are
deleted on activation.

| Requests | Strategy |
|---|---|
| Build output, static files, `/` (the app shell) | precached on install; cache first |
| `GET /api/meta`, `GET /api/health` | network first, cached copy when offline (`no-store` answers are not stored) |
| `GET /api/stores`, `/api/ingredients`, `/api/recipes*` | stale-while-revalidate |
| Other `/api` requests, every `POST` | network only, never cached |
| Navigations | network first, the cached app shell when offline |

The caches hold public data only.

## Known issues

- `npm audit` reports advisories in development-only packages: `vitest`/`@vitest/mocker`/`tinypool` (test
  runner) and `cookie` (used by SvelteKit's server runtime, which this static SPA does not ship). The fixes
  need major upgrades (vitest 5, SvelteKit 3) beyond the pinned toolchain.
