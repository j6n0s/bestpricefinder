# SYNTHETIC API mocks

**Everything in this folder is synthetic test data.** Store ids (`synthetic-…`), addresses (`Minta utca …`),
products, recipes (`minta-…`, titles ending in "(szintetikus)") and every price are invented. They are not
GVH Árfigyelő or KSH data, are not real prices, and must never be presented as real.

Only the chain names and slugs (`aldi`, `lidl`, …) match the real chain list, because the app's logic keys
on them.

Used by:
- `npm run dev:mock` (vite.config.ts serves `/api/*` from `handleMockApi`; responses carry
  `x-mock-data: synthetic`);
- the Playwright smoke test (`tests/e2e/`), through `page.route` and the test static server;
- the unit test `api.test.ts` in this folder.

The data is typed against `src/lib/api/types.ts` (aliases over the types generated from `docs/openapi.json`),
so a contract change shows up as a type error here.

The handler behaves like the contract where the app depends on it: competition ranks with ties in quotes,
quantities only as JSON numbers (a string is a 422), an unknown root field reported as `body`, and
POST /api/plan/check computing the weekly rule results from the request (`computeMockChecks`, the server's
string format) with a 422 for an unknown recipe id. A spec that serves its own recipes passes them as
`handleMockApi(method, url, body, { recipes })`.
