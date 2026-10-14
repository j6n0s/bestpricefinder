# `src/lib/journey/`: one store or a route ("Hol vásárolj?")

Pure TypeScript, unit-tested, used by `ShoppingOptions` and `JourneyMap` (`src/lib/components/journey/`) on
`/lista` and `/kosar`. Everything here runs **on the device**: the user's position never leaves it, and the
server only ever sees store ids (POST /api/quote).

| Module | What it does |
|---|---|
| `journey.ts` | `planShopping(origin, lineIds, stores, options)`: the best single store, and the best route through 2..`maxStops` stores. |
| `view.ts` | From a quote and the store list to what the page shows: the goods sold nowhere nearby, the single store, the route (stops in walking order, items per stop, saving, extra walk), or why there is no route. `osmLink()` for a store's own position. |
| `map.ts` | The schematic map: an equirectangular projection fitted to the points, a scale bar, SVG path data. No tiles, no request anywhere (the CSP allows none). |

## The rules

Inputs per store: the quote's `checkout_cost` of each `priced` line (whole packs, what is paid at the till) and
the store's public position. Lines that are `unavailable`, `unpriced`, `pantry` or only a KSH estimate are not
bought there.

1. **Most goods first.** A plan that gets more of the goods always wins, whatever it costs.
2. **Then the score:** total + `perKmFt` × the length of the round trip (start → stops → start, as the crow
   flies) + `extraStopFt` × (stops − 1). Defaults: 150 Ft per km and 500 Ft per extra stop
   (`DEFAULT_JOURNEY_OPTIONS`), at most 3 stops (`MAX_JOURNEY_STOPS` caps the option at 4).
3. On a route, each good is bought at the stop where it is cheapest; a route where a stop would buy nothing
   is never offered (that stop is pointless).
4. The stops are walked in the shortest order (every order is tried; with ≤ 4 stops that is at most 24).
5. **Ties are never broken by chain or store name** (BUILD-BRIEF §4.1 trap 13). A good with the same price at
   two stops goes to the one nearer the start; of two equal plans the one with the shorter walk, then fewer
   stops, wins; anything still equal is decided by position (south first, then west), which says nothing about
   the chains.

The route is shown only when it beats the single store under these rules. Otherwise the page says how much
the best route would have saved, and that it is not worth the extra walk. The server's own `split` (2 stores,
≥ 1,500 Ft) is no longer shown: it knows nothing about distances.

Every combination of up to 3 of the ≤ 25 candidate stores is tried (at most 25 + 300 + 2,300 = 2,625
subsets). This is exact and takes a few milliseconds; `journey.test.ts` checks it against an independent brute
force on 60 random cases and has a timing test for the largest input.

## Test data is SYNTHETIC

Every store, position and price in `*.test.ts` here and in `tests/e2e/cart.spec.ts` and
`tests/e2e/list.spec.ts` is invented test data (ids `synthetic-…`, addresses `Minta utca …`).
