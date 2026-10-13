# Content data (`data/`)

**Status:** contract v1.2, 2026-10-13 (cloud agent). The loader is the package `server/bpf/content/`, run as `python -m bpf.content [--dry-run]` (options: docs/ENGINE.md). It runs as `bpf_ingest`, validates **everything** before writing anything, upserts in one transaction, and records an `ops.ingest_run` row of kind `content`. The domain types it produces are in [`server/bpf/pricing/model.py`](../server/bpf/pricing/model.py).

All files are UTF-8 JSON (2-space indent, keys in the order below, stable sort by `id`) except the KSH CSV. Content is **ours**:
- recipe text is original;
- ingredient lists come from our own research (`research/recipe-coverage/out/`);
- no text is copied from recipe sites or OKOSTÁNYÉR (BUILD-BRIEF §5, §8).

## `data/ingredients.json`: the ingredient ontology
```json
{"version": 1, "ingredients": [ {
  "id": "csirkemellfile",            // ^[a-z0-9_]{2,40}$, ASCII, stable forever (recipes reference it)
  "name_hu": "csirkemellfilé",
  "list_group": "hus_hal",           // shopping-list section, one of the groups listed below
  "unit": "kg",                      // canonical unit: kg | l | db
  "piece_weight_kg": null,           // required when unit=db or when db products are allowed (db<->kg)
  "density_kg_per_l": null,          // only if l<->kg conversion is acceptable for this ingredient
  "pantry": false,                   // true = "valószínűleg otthon van" (salt, spices, oil…); see rules below
  "leaf_ids": [18],                  // GVH leaf category ids (checked against research/…/leaf_categories.csv)
  "include_patterns": ["csirkemell"],// regexes on fold_name(product name); ANY must match (if non-empty)
  "exclude_patterns": ["panir", "fustolt", "tokany", "felezett", "csontos"],  // NONE may match
  "product_units": ["kg"],           // allowed GVH product units; [] = any convertible unit
  "ksh_code": null,                  // KSH ara0044 row code, for non-GVH ingredients (fallback estimate)
  "nutrition_code": null,            // app.nutrition.code (stays null until composition data is imported)
  "tags": ["poultry"],               // IngredientTag vocabulary (model.py / migration 0002)
  "perishable_days": 3,              // null = shelf-stable
  "notes": "Tesco counter names are accent-less ('CSIRKEMELL FILE PULTOS QQ'); patterns are folded ASCII."
} ] }
```
Validation (the loader fails loudly):
- Ids are unique.
- Every `leaf_ids` entry is a GVH food leaf (`core.category.is_leaf AND is_food` when the DB has categories; otherwise checked against `research/gap-gvh-promo-and-stability/data/leaf_categories.csv`).
- Every regex compiles, is ≤120 characters and is lower-case ASCII (`fold_name` output never contains upper case or accents).
- `unit=db` or a `db` in `product_units` requires `piece_weight_kg`.
- `pantry=true` marks staples listed under "valószínűleg otthon van". A pantry ingredient may keep `leaf_ids` (oil, flour); it is then priced whenever the client includes it in a quote. A pantry ingredient without `leaf_ids` is never priced (its `ksh_code` is ignored in quotes).
- `ksh_code` must exist in the KSH file.
- Tags are from the vocabulary.

`list_group` vocabulary, in shopping-list order: `zoldseg_gyumolcs`, `pekaru`, `tejtermek_tojas`, `hus_hal`, `szaraz_tartos`, `fagyasztott`, `fuszer_olaj`, `egyeb`.

## `data/recipes/*.json`: original recipes
Recipes may be split across several files (for example `main.json` and `small.json`), all in the same format. The loader reads every `data/recipes/*.json` in name order. Ids must be unique across files.
```json
{"version": 1, "recipes": [ {
  "id": "lencsefozelek-tojassal",    // ^[a-z0-9-]{2,60}$, stable
  "title": "Lencsefőzelék főtt tojással",
  "summary": "Sűrű, fűszeres lencsefőzelék, mellé főtt tojás.",   // ≤400 chars, descriptive, no health claims
  "slots": ["ebed", "vacsora"],      // subset of reggeli|tizorai|ebed|uzsonna|vacsora
  "servings": 4,                     // 1..12; quantities below are for this many servings
  "minutes": 45,
  "tags": ["fozelek", "huvelyes", "husmentes"],   // RecipeTag vocabulary (model.py)
  "lines": [ {"ingredient_id": "lencse", "qty": 0.4, "display": "40 dkg", "optional": false} ],
  "steps": ["…original Hungarian instruction text…"],
  "tested": false                    // true only after a human cooked it (founder's call)
} ] }
```
Validation:
- Every `ingredient_id` exists.
- `qty` > 0, in the ingredient's canonical unit, for `servings` servings.
- 1–60 lines and 1–20 steps; each step 10–600 characters.
- Tags must be consistent with the ingredients:
  - `husmentes`: no line with the tag `red_meat`, `processed_meat`, `poultry` or `fish`;
  - `hal`: at least one `fish` line;
  - `huvelyes`: at least one `legume` line;
  - `baromfi`, `sertes` and `marha` likewise;
  - `gyors`: `minutes ≤ 25`.
- `olcso` is never hand-set; it is computed.
- **No health claims** in any text: the loader rejects "egészséges", "fogyaszt", "diéta", "méregtelenít", "immun", "gyógy" and "betegség", matched as accent-folded word stems in any form (so "fogyasztás" is rejected too).
- Stricter rules the loader enforces (v1.2):
  - `husmentes` is **required** when no line is tagged `red_meat`, `processed_meat`, `poultry` or `fish`;
  - the meat check also applies to `vegetarianus`;
  - `hal`, `huvelyes`, `baromfi`, `sertes` and `marha` need a required (non-optional) matching line, and `sertes`/`marha` a `red_meat` line;
  - at least one required line;
  - `qty` has at most 3 decimals;
  - each file is sorted by `id`.
- Ingredient file rules (v1.2):
  - sorted by `id`, and `name_hu` unique after accent folding;
  - `include_patterns`, `exclude_patterns` and `product_units` need `leaf_ids`;
  - mixing `l` and `kg` needs `density_kg_per_l`;
  - a KSH row's unit must convert to the canonical unit;
  - `red_meat`/`processed_meat` must be weighable in kg;
  - regexes may not match the empty string.

**Coverage rule (BUILD-BRIEF §5).** Every recipe needs **≥90 % of its estimated ingredient cost in GVH-mapped ingredients**. Non-GVH lines are KSH-priced or pantry. `python -m bpf.content --coverage-report` prints per recipe:
- the share, using the latest DB prices when they exist, else `research/gap-healthy-plan-priceability/data/ingredient_reference_prices.csv`;
- the failing recipes. They block the load unless `--allow-low-coverage` is passed.

How the share is computed (v1.2):
- Optional and pantry lines are left out, as in `recipe_chain_costs`.
- A GVH-mapped line with no price, in the DB or the reference CSV, is left out and reported; the share is then a **lower bound**.
- A non-GVH line with no price at all (KSH or reference) **fails** the recipe.

## `data/ksh/ara0044.csv`: KSH national average prices (CC BY 4.0)
- **Source:** KSH STADAT ara0044, <https://www.ksh.hu/stadat_files/ara/hu/ara0044.html>. Attribution "Forrás: KSH" with a link, as required.
- **Format:** UTF-8 CSV with the header `code,name,unit,unit_qty,price,period`. `unit` ∈ {kg, l, db} after normalisation (e.g. "Tojás, 10 darab" → unit `db`, unit_qty 10); `period` is `YYYY-MM-01`.
- Rows that are not food, or whose unit cannot be normalised (`pár`, `m²`, `adag`…), are dropped by the converter `python -m bpf.content --convert-ksh <raw file>`. The converter reads the original ISO-8859-2 file and records it in `data/ksh/SOURCE.md` with the URL, the fetch date and the file's sha256.
- **Stored per one unit:** `app.ksh_price` has no `unit_qty` column, so the loader stores `price / unit_qty`, i.e. HUF per ONE `unit` (eggs: 814 Ft / 10 db = 81.40 Ft/db). The API repo therefore builds `KshPrice(unit_qty=1, price=row.price)`. The CSV itself keeps `unit_qty`.
- **History:** for each code in the file, rows of a later period than the file's are deleted; earlier periods, and codes no longer in the file, are kept.
- **Seed:** until a raw KSH file can be fetched (the cloud container cannot reach ksh.hu), the CSV is converted from `research/alt-price-sources/data/ksh_ara0044_latest_avg_prices.csv` (period 2026-09). `SOURCE.md` says so.

## `data/nutrition/` (optional)
This is empty until composition data is imported from CIQUAL 2025 (Etalab 2.0), Frida 5.5 (CC BY 4.0) or USDA FDC (CC0). The converter writes `nutrition.json` (`{"version":1,"rows":[{code, source, name, kcal, protein_g, carb_g, sugar_g, fat_g, satfat_g, fiber_g, salt_g}]}`) from a locally downloaded official file. **No hand-typed or remembered values.** While empty, the API returns `nutrition: null` and the UI hides nutrition.
