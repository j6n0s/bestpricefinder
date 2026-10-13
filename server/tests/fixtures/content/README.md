# Content test fixtures (`server/tests/fixtures/content/`)

Used by `server/tests/test_content_*.py`.

| File | What it is |
|---|---|
| `ingredients.json`, `ksh.csv`, `reference_prices.csv`, `recipes/*.json` | **SYNTHETIC** test data written for the tests. The prices are made-up round numbers, not real prices; the recipe texts are short original sentences written for the tests, not real recipes. Leaf ids and KSH codes are real identifiers, used only so that the validation rules can be exercised. |
| `gvh_product_names.csv` | **Real** GVH Árfigyelő product names (with their leaf id and unit), copied from the research CSVs named in the `source` column (surrounding spaces trimmed) (`research/gvh-location/data/*.csv`, `research/gap-gvh-promo-and-stability/data/promo_capture_sample_2026-10-12.csv`; snapshots of 2024–2026). Some names are truncated to 60 characters as in the research files. Names only: no prices, no images. Used to check the ontology's include/exclude rules against real naming. |
