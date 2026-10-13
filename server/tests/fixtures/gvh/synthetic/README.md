# SYNTHETIC GVH fixtures: not real data

Every file in this folder was **generated** by `server/tests/fakegvh.py` (`python -m tests.fakegvh
--write-fixtures`, run from `server/`). They are test fixtures in the shapes the client *assumes*
(`server/bpf/gvh/ASSUMPTIONS.md`). They are **not** responses recorded from arfigyelo.gvh.hu, and none of
the products or prices in them is real.

| Part | Origin |
|---|---|
| Store ids, postal codes, cities, addresses, coordinates, opening times (`shops-head.json`) | Real: `research/gvh-location/data/stores.csv` (first 40 stores) |
| Category ids, names and tree (`categories.json`) | Real: `research/gap-gvh-promo-and-stability/data/leaf_categories.csv`; paths from `research/recipe-coverage/out/gvh_leaf_categories.csv` |
| Chain names | Real (from `stores.csv`) |
| Chain uuids | **Invented** (uuid5 of the chain name) |
| Product ids, names, units, pack sizes, every price, `availableInShops` lists | **Synthetic** (seeded generator; magnitudes from `research/gap-healthy-plan-priceability/data/ingredient_reference_prices.csv`) |
| `xlsx-sample.xlsx` (header + 150 rows) | **Synthetic** rows in the documented 14-column layout, all values as text with decimal commas |

File names mirror the raw samples requested in `docs/QUESTIONS.md` (2026-10-13), so the same tests run over
these files and, once someone commits them, over the real samples in `../raw/`. Each `<name>.meta.json`
holds the HTTP status (`product-shop-notfound` is a 404 carrying `PRODUCT-SHOP-PRICES-NOT-FOUND`).

Do not edit these files by hand: change the generator and regenerate. `tests/test_gvh_fixtures.py` checks
that they still match the generator and that every parser accepts them without schema drift.
