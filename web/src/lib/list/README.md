# `src/lib/list/`: shopping list and nearby-store prices

Pure TypeScript helpers for `/lista` and the pantry and exclusion settings. The components are in
`src/lib/components/list/` and `src/lib/components/settings/`.

| Module | What it does |
|---|---|
| `range.ts` | "Ez a hét" / "Jövő hét" / "Az egész terv": the plan's 7-day blocks around today (Budapest date). |
| `request.ts` | The POST /api/list body from the stored plan (`planToListItems` from `$lib/plan/plan`), the list key. |
| `lines.ts` | Buy / pantry ("valószínűleg otthon van") / excluded (settings; "mégis megveszem" per list) / removed lines, tap water never bought, the POST /api/quote body (ids, quantities and store ids only, store ids sorted by id so their order says nothing about distances). No on-hand quantities: a staple is at home or "nincs otthon". |
| `groups.ts` | Shop sections in the docs/DATA.md order, with Hungarian and English names. |
| `stores.ts` | Candidate stores ON THE DEVICE (`pickNearestPerChain`: grocery, has data, ≤3 per chain, ≤25), wider radius, labels. |
| `ranking.ts` | Ranking rows (ties ordered by distance, never by name), split parts and the lines neither split store sells, price labels (DISCOUNTED is never an "akció" badge). |
| `storeview.ts` | The chosen store's lines grouped by section; whether some line costs a fraction of a forint (rounding note). |
| `packs.ts` | "2 × 175 g", "1,5 kg", "2 990 Ft/kg" (hu-HU numbers). |
| `prefs.ts` | Range, and per list the ticks, removed lines, excluded lines bought anyway and the chosen store: `StoredState.list` in the one stored document of `$lib/storage` (key `hetikosar.state`; no key of its own). |
| `offline.ts` | The last list and the chosen store's last quote, kept in the stored document and shown, dated, when a request fails for lack of a connection. |
| `locate.ts` | The device position for the list: `requestApproxPosition({ timeoutMs: 10_000 })` from `$lib/location` (low accuracy, rounded, never sent). |
| `data.ts` | GET /api/stores, /api/ingredients and /api/recipes, fetched once and kept in memory. |
| `validate.ts` | Shape checks of the /api/list, /api/quote and /api/ingredients answers. |
| `settings.ts` | Pantry and exclusion helpers (excludable tags, accent-insensitive ingredient search). |

## Test data is SYNTHETIC

Every ingredient, recipe, store, address, product name and price in the unit tests of this folder
(`*.test.ts`) and in `tests/e2e/list.spec.ts` is **invented test data**: ids start with `synthetic-` or
`minta-`, addresses are `Minta utca …`, and product names say "Szintetikus". None of it is GVH Árfigyelő or
KSH data, none of it is a real price, and it must never be presented as real. Only the chain names and slugs
(`lidl`, `aldi`, …) match the real chain list, because the app's logic keys on them.
