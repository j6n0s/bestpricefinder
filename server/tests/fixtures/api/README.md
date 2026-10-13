# API test fixtures: SYNTHETIC DATA ONLY

Everything in this folder is **synthetic test data** for `tests/test_api_*.py`. None of it is a real price,
product, store, chain, KSH row or nutrient value, and none of it may be shown to users or used as a data
source.

- `seed.py` inserts a small hand-made catalogue into a throwaway PostgreSQL cluster **as `bpf_ingest`**
  (the same role the real ingest uses), through the real migrations' tables:
  - four fictional chains (`alfa`, `beta`, `gamma` grocery; `delta` drugstore) and six fictional stores;
  - a handful of fictional products in fictional GVH leaves (ids 99001-99004), with prices chosen as round
    numbers so that every expected total in the tests can be computed by hand (the computations are
    written out in the test docstrings and comments);
  - a fictional KSH row (`zz-paprika`, 4,000 Ft/kg) and one fictional nutrition row (`zz-nut-rizs`,
    round made-up values, source label `ciqual` only to exercise the attribution code path);
  - five short recipes whose step texts were written for these tests (they are not recipes to cook);
  - two `ops.ingest_run` rows: the daily run of the data date (2026-10-12) and an availability run two days
    earlier, so the `Store.has_data` rule (docs/ENGINE.md, read through `api.ingest_latest`) applies.
- `memory.py` builds the same synthetic catalogue in memory (no database) for the middleware, static-file
  and unit tests; the DB tests compare it with what the API loads from the views.
- `asgi.py` calls the app with an exact ASGI scope and raw body chunks (traversal paths, chunked bodies).
- The static-site tests build a fake `web/build` in a temporary directory at test time (an `index.html` with
  a made-up CSP meta tag, a fake hashed asset, a fake service worker); nothing from the real web build is used.
