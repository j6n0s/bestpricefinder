# Content report (`data/`)

**As of:** 2026-10-13, written by the cloud agent's content QA pass (part 3 of the content pipeline).
**Covers:** `data/ingredients.json` (162 ingredients), `data/recipes/main.json` (25 recipes), `data/recipes/small.json` (16 recipes) and `data/ksh/ara0044.csv` (61 rows).

> **Every recipe ships with `tested: false`.** None of the 41 recipes has been cooked by a human yet. Each one must be cook-tested, and its `tested` flag set to `true` only by the founder, before it is published (BUILD-BRIEF §5). Test the baked items first: the apple cake batter (`almas-joghurtos-kevert-suti`), the casserole (`rakott-brokkoli-csirkemellel`) and the carp (`racponty`).

## 1. Summary

| Check | Result |
|---|---|
| Validation (`python -m bpf.content --dry-run --coverage-report`) | 162 ingredients, 41 recipes, 61 KSH rows; **41 recipes, 0 failing** |
| Coverage rule (≥ 90 % of the cost in GVH-mapped ingredients) | every recipe **100.0 %** (see §4) |
| Planner, default rules, 2 people, seeds 0–49, 7 and 28 days, 3 and 5 slots | **every weekly check passes** (500 of 500 per rule); no warnings, no empty slots (see §6) |
| Load into a throwaway PostgreSQL cluster as `bpf_ingest` | first load: 162 ingredients, 41 recipes, 61 KSH rows inserted; second load: "no changes"; both `ops.ingest_run` rows `content ok`; every recipe field and line read back exactly through the `api.*` views (see §7) |
| Recipes with `tested: true` | **0 of 41** |

## 2. Recipes by slot

| Slot | Recipes | `hal` | `huvelyes` | `husmentes` | `ket_napos` | `edes` | with a potato line |
|---|---|---|---|---|---|---|---|
| reggeli | 9 | 0 | 0 | 9 | 0 | 0 | 0 |
| tizorai | 7 | 0 | 0 | 7 | 1 | 1 | 0 |
| ebed | 25 | 4 | 5 | 13 | 6 | 0 | 6 |
| uzsonna | 7 | 0 | 0 | 7 | 1 | 1 | 0 |
| vacsora | 25 | 4 | 5 | 13 | 6 | 0 | 6 |

- Every lunch/dinner recipe has the slots `ebed` and `vacsora`. Every snack has `tizorai` and `uzsonna`. Breakfasts have only `reggeli`.
- The minimums are met: the main-meal pools have at least 5 recipes (reggeli 9, ebed 25, vacsora 25), and the snack pools at least 4 (7 each).
- Lunch and dinner (25):
  - by course: 6 soups (`leves`), 4 főzeléks (`fozelek`) and 15 mains (`foetel`; the lentil salad is also `salata`);
  - by protein: 4 fish, 4 poultry, 3 pork, 1 beef, and 13 meat-free (5 of them lentil dishes).
- Breakfasts (9): 5 warm (`reggeli_meleg`) and 4 cold (`reggeli_hideg`). 4 contain eggs and 5 do not.

## 3. Recipes by tag

| Tag | Recipes | Tag | Recipes |
|---|---|---|---|
| husmentes | 29 | huvelyes | 5 |
| vegetarianus | 29 | reggeli_meleg | 5 |
| gyors (≤ 25 min) | 16 | baromfi | 4 |
| foetel | 15 | fozelek | 4 |
| gyerekbarat | 10 | hal | 4 |
| ket_napos | 7 | reggeli_hideg | 4 |
| snack | 7 | salata | 4 |
| leves | 6 | sertes | 3 |
| | | edes | 1 |
| | | marha | 1 |

- No recipe uses `koret`.
- `olcso` is computed by the app and never set by hand.
- `vegetarianus` is descriptive and lacto-ovo: some cheeses may be made with animal rennet.
- `gyerekbarat` is descriptive only (a simple, mild dish children commonly eat). It is never put on a recipe with a required `nut_seed` line (whole or chopped nuts or seeds), so the peanut-topped `joghurtos-gyumolcstal-foldimogyoroval` does not carry it. The loader does not check this yet; `server/tests/test_content_shipped_tags.py` guards the shipped data.

## 4. Coverage per recipe

**Rule (docs/DATA.md):** at least 90 % of each recipe's estimated cost must be in GVH-mapped ingredients.

**What counts:**
- Pantry and optional lines are left out of the share.
- Every required, non-pantry line in the library is GVH-mapped, so every share is 100 % whatever the prices are.

**Prices used here:** research reference prices (`research/gap-healthy-plan-priceability/data/ingredient_reference_prices.csv`, median of the GVH chain minimum prices of 2026-10-12). No database prices exist yet.
- Rerun `python -m bpf.content --coverage-report` after the first daily ingest to use real chain prices.
- The Ft columns are internal estimates for this check, not store prices. Never show them in the app.

| id | title | file | slots | serv. | min | tags | GVH share | GVH Ft | total Ft | Ft/serv. |
|---|---|---|---|---|---|---|---|---|---|---|
| `csirkeraguleves-zoldborsoval` | Csirkeraguleves zöldborsóval | main | ebed, vacsora | 4 | 50 | leves, baromfi, gyerekbarat | 100.0 % | 1311 | 1311 | 328 |
| `gulyasleves` | Gulyásleves marhalábszárból | main | ebed, vacsora | 6 | 150 | leves, marha, ket_napos | 100.0 % | 2818 | 2818 | 470 |
| `harcsapaprikas-tojasos-tesztaval` | Harcsapaprikás tojásos tésztával | main | ebed, vacsora | 4 | 45 | foetel, hal | 100.0 % | 3547 | 3547 | 887 |
| `kaposztas-teszta` | Káposztás tészta | main | ebed, vacsora | 4 | 50 | foetel, husmentes, vegetarianus | 100.0 % | 508 | 508 | 127 |
| `kelkaposzta-fozelek-sult-fasirttal` | Kelkáposzta-főzelék sült fasírttal | main | ebed, vacsora | 4 | 70 | fozelek, sertes | 100.0 % | 1671 | 1671 | 418 |
| `krumplifozelek-tukortojassal` | Krumplifőzelék tükörtojással | main | ebed, vacsora | 4 | 45 | fozelek, husmentes, vegetarianus | 100.0 % | 704 | 704 | 176 |
| `krumplileves` | Tejfölös krumplileves | main | ebed, vacsora | 4 | 45 | leves, husmentes, vegetarianus | 100.0 % | 595 | 595 | 149 |
| `lencsefasirt-joghurtos-uborkasalataval` | Lencsefasírt joghurtos uborkasalátával | main | ebed, vacsora | 4 | 75 | foetel, huvelyes, husmentes, vegetarianus | 100.0 % | 1026 | 1026 | 257 |
| `lencsefozelek-fott-tojassal` | Lencsefőzelék főtt tojással | main | ebed, vacsora | 4 | 60 | fozelek, huvelyes, husmentes, vegetarianus, ket_napos | 100.0 % | 665 | 665 | 166 |
| `lencseleves` | Lencseleves | main | ebed, vacsora | 6 | 70 | leves, huvelyes, husmentes, vegetarianus, ket_napos | 100.0 % | 684 | 684 | 114 |
| `lencseragus-spagetti` | Lencseragus spagetti | main | ebed, vacsora | 4 | 55 | foetel, huvelyes, husmentes, vegetarianus | 100.0 % | 1411 | 1411 | 353 |
| `lencsesalata-fetaval` | Lencsesaláta fetával és friss zöldségekkel | main | ebed, vacsora | 4 | 40 | salata, foetel, huvelyes, husmentes, vegetarianus | 100.0 % | 1702 | 1702 | 425 |
| `paprikas-csirke-nokedlivel` | Paprikás csirke nokedlivel | main | ebed, vacsora | 4 | 75 | foetel, baromfi, ket_napos | 100.0 % | 1690 | 1690 | 422 |
| `paradicsomleves` | Paradicsomleves friss paradicsomból, betűtésztával | main | ebed, vacsora | 4 | 45 | leves, husmentes, vegetarianus, gyerekbarat | 100.0 % | 1101 | 1101 | 275 |
| `paradicsomos-tokehal-rizzsel` | Paradicsomos-paprikás tőkehal rizzsel | main | ebed, vacsora | 4 | 40 | foetel, hal | 100.0 % | 2411 | 2411 | 603 |
| `racponty` | Rácponty (rakott ponty burgonyával) | main | ebed, vacsora | 4 | 85 | foetel, hal | 100.0 % | 4430 | 4430 | 1107 |
| `rakott-brokkoli-csirkemellel` | Rakott brokkoli csirkemellel | main | ebed, vacsora | 4 | 65 | foetel, baromfi | 100.0 % | 2560 | 2560 | 640 |
| `sertesporkolt-tesztaval` | Sertéspörkölt tésztával | main | ebed, vacsora | 4 | 110 | foetel, sertes, ket_napos | 100.0 % | 1574 | 1574 | 394 |
| `sult-lazac-brokkolis-rizzsel` | Sült lazac citromos-brokkolis rizzsel | main | ebed, vacsora | 4 | 35 | foetel, hal | 100.0 % | 4114 | 4114 | 1028 |
| `tepsis-pulykamell-zoldsegekkel` | Tepsis pulykamell zöldségekkel | main | ebed, vacsora | 4 | 60 | foetel, baromfi | 100.0 % | 2402 | 2402 | 600 |
| `tojasos-lecso` | Tojásos lecsó | main | ebed, vacsora | 4 | 40 | foetel, husmentes, vegetarianus | 100.0 % | 1689 | 1689 | 422 |
| `toltott-paprika` | Töltött paprika paradicsommártásban | main | ebed, vacsora | 4 | 105 | foetel, sertes, ket_napos | 100.0 % | 2647 | 2647 | 662 |
| `turos-csusza-piritott-hagymaval` | Túrós csusza pirított hagymával | main | ebed, vacsora | 4 | 35 | foetel, husmentes, vegetarianus | 100.0 % | 1298 | 1298 | 324 |
| `zoldborsofozelek-tukortojassal` | Zöldborsófőzelék tükörtojással | main | ebed, vacsora | 4 | 25 | fozelek, husmentes, vegetarianus, gyors, gyerekbarat | 100.0 % | 1016 | 1016 | 254 |
| `zoldsegleves` | Zöldségleves apró tésztával | main | ebed, vacsora | 4 | 45 | leves, husmentes, vegetarianus, gyerekbarat | 100.0 % | 847 | 847 | 212 |
| `almas-joghurtos-kevert-suti` | Almás-fahéjas joghurtos kevert süti | small | tizorai, uzsonna | 4 | 65 | snack, edes, ket_napos, husmentes, vegetarianus, gyerekbarat | 100.0 % | 277 | 277 | 69 |
| `bananos-kefir` | Banános kefir | small | tizorai, uzsonna | 2 | 5 | snack, husmentes, vegetarianus, gyors, gyerekbarat | 100.0 % | 368 | 368 | 184 |
| `bundas-kenyer-friss-zoldseggel` | Bundás kenyér friss paradicsommal és uborkával | small | reggeli | 2 | 25 | reggeli_meleg, husmentes, vegetarianus, gyors, gyerekbarat | 100.0 % | 635 | 635 | 318 |
| `joghurtos-gyumolcstal-foldimogyoroval` | Joghurtos gyümölcstál pirított földimogyoróval | small | reggeli | 2 | 15 | reggeli_hideg, husmentes, vegetarianus, gyors | 100.0 % | 446 | 446 | 223 |
| `korozott-rozskenyerrel` | Körözött rozskenyérrel és zöldpaprikával | small | reggeli | 2 | 15 | reggeli_hideg, husmentes, vegetarianus, gyors | 100.0 % | 559 | 559 | 280 |
| `kortes-narancsos-joghurt` | Körtés-narancsos joghurtkehely | small | tizorai, uzsonna | 2 | 10 | snack, husmentes, vegetarianus, gyors, gyerekbarat | 100.0 % | 353 | 353 | 177 |
| `kortes-turokrem-piritoson` | Fahéjas-körtés túrókrém pirított rozskenyéren | small | reggeli | 2 | 15 | reggeli_hideg, husmentes, vegetarianus, gyors | 100.0 % | 499 | 499 | 250 |
| `lagytojas-piritossal` | Lágy tojás vajas pirítóssal és friss zöldséggel | small | reggeli | 2 | 15 | reggeli_meleg, husmentes, vegetarianus, gyors | 100.0 % | 526 | 526 | 263 |
| `paradicsom-mozzarellaval` | Paradicsom mozzarellával és bazsalikommal | small | tizorai, uzsonna | 2 | 10 | snack, salata, husmentes, vegetarianus, gyors | 100.0 % | 588 | 588 | 294 |
| `paradicsomos-rantotta` | Paradicsomos rántotta teljes kiőrlésű kenyérrel | small | reggeli | 2 | 20 | reggeli_meleg, husmentes, vegetarianus, gyors | 100.0 % | 457 | 457 | 229 |
| `paradicsomsalata-fetaval` | Paradicsomos-uborkás saláta fetával és teljes kiőrlésű kenyérrel | small | reggeli | 2 | 15 | reggeli_hideg, salata, husmentes, vegetarianus, gyors | 100.0 % | 1046 | 1046 | 523 |
| `repas-almas-salata` | Répás-almás saláta citrommal | small | tizorai, uzsonna | 2 | 10 | snack, salata, husmentes, vegetarianus, gyors, gyerekbarat | 100.0 % | 210 | 210 | 105 |
| `sajtos-paprikas-omlett` | Sajtos-paprikás omlett | small | reggeli | 2 | 20 | reggeli_meleg, husmentes, vegetarianus, gyors | 100.0 % | 527 | 527 | 263 |
| `sajtos-paradicsomos-melegszendvics` | Sajtos-paradicsomos melegszendvics | small | reggeli | 2 | 20 | reggeli_meleg, husmentes, vegetarianus, gyors, gyerekbarat | 100.0 % | 400 | 400 | 200 |
| `tojasos-zoldseges-szendvics` | Tojásos-zöldséges szendvics | small | tizorai, uzsonna | 2 | 25 | snack, husmentes, vegetarianus, gyors | 100.0 % | 381 | 381 | 190 |
| `turokrem-zoldseghasabokkal` | Fokhagymás túrókrém zöldséghasábokkal | small | tizorai, uzsonna | 2 | 15 | snack, husmentes, vegetarianus, gyors | 100.0 % | 559 | 559 | 280 |

None of the shares is a lower bound: every GVH-mapped line used had a reference price.
- `teszta_tojasos` is priced through the research key `teszta`, and `tv_paprika` through `zoldpaprika` (`REFERENCE_ALIASES` in `bpf/content/coverage.py`).

## 5. Ingredients used (72 of 162)

The library has 408 recipe lines, 21 of them optional.

**GVH-mapped, required in at least one recipe (50).** These are:
- alma, banan, brokkoli, burgonya, citrom;
- csirkecomb, csirkemell, daralt_sertes;
- edami, feta, fokhagyma, harcsa, joghurt, kaposzta, karfiol, kefir, kelkaposzta;
- kenyer_felbarna, kenyer_rozs, kenyer_tk;
- korte, lazac, lencse, marha, mogyoro, mozzarella, narancs, paradicsom, petrezselyemgyoker, ponty, pulykamell, rizs, sargarepa, sertescomb, tej, tejfol12, tejfol20, teszta, teszta_tojasos, tojas, tokehal, trappista, turo, tv_paprika, uborka, vaj, voroshagyma, zoldborso, zoldpaprika, zsemle.

**Pantry ingredients ("valószínűleg otthon van").**
- **With a GVH mapping (4): cukor, finomliszt, olaj, olivaolaj.** They are priced only when the user says they are not at home.
- **Without a GVH mapping (14), never priced:** baberlevel, bazsalikom, bors, ecet, fahej, komenymag, majoranna, mustar (optional only), oregano, pirospaprika, rozmaring, so, sutopor, viz.

**KSH-priced lines: none.**
- Two pantry ingredients carry a KSH code: pirospaprika (15202) and so (15204). docs/DATA.md says a pantry ingredient without `leaf_ids` is never priced, so these codes are ignored in quotes.
- The non-pantry KSH ingredients in the ontology are not used by any recipe: dio, gomba, gorogdinnye, lekvar, mez, szarazbab.

**Unpriced ("nincs ár"), on optional garnish lines only (4).**
- These are kapor, petrezselyemzold, salata and zeller.
- GVH has no leaf for fresh herbs, salad leaves or celeriac, and KSH ara0044 has no row for them.
- They show as "nincs ár" when a shopping list includes optional lines, which is the default.

**Unused ontology rows (90).** These are kept for future recipes. Among them:
- the meat cuts sertes_karaj, sertes_tarja, csirkeszarny, egesz_csirke, daralt_marha and feherpecsenye;
- the processed meats parizsi, virsli, sonka, pulykasonka, teliszalami, kolbasz and szalonna;
- the non-GVH vegetables, legumes and oats (zabpehely, csicseri, voros_bab_konzerv, sargaborso…).

## 6. Planner feasibility (`bpf.planner.suggest_plan` on the real library)

**Setup:**
- 2 people, default rules: red-meat cap 600 g/person/week and `no_repeat_days` 5.
- Seeds 0–49, for 7 and 28 days, with `SLOTS_3` (reggeli, ebed, vacsora) and `SLOTS_5`.
- Each plan was re-checked independently with `check_plan`, and the results were identical.
- The "Passes per rule" column counts weekly checks: 50 for a 7-day plan, 200 for a 28-day plan (4 weeks × 50 seeds).

| Slots | Days | Plans failing any rule | Passes per rule (fish, legume, meat_free_day, red_meat, potato, sweets, variety) | Warnings | Empty slots | Slowest plan |
|---|---|---|---|---|---|---|
| SLOTS_3 | 7 | 0 / 50 | 50 / 50 each | none | 0 | 72 ms |
| SLOTS_3 | 28 | 0 / 50 | 200 / 200 each | none | 0 | 150 ms |
| SLOTS_5 | 7 | 0 / 50 | 50 / 50 each | none | 0 | 117 ms |
| SLOTS_5 | 28 | 0 / 50 | 200 / 200 each | none | 0 | 167 ms |

**Extra variants, same seeds and both slot sets, all rules passing with no warnings:**
- eggs excluded (`exclude_ingredients: tojas`);
- pork and beef excluded (`exclude_tags: sertes, marha`);
- sweets excluded (`edes`);
- túró excluded;
- burgonya excluded;
- `no_repeat_days` 7 (7 and 28 days) and 9 (28 days);
- 31 days;
- 1 and 4 people (28 days).

**Variants that fail.** These are library gaps (§8), not planner bugs:

| Variant | Result |
|---|---|
| eggs excluded **and** `no_repeat_days` 7 (7 and 28 days) | `variety` fails in every week (and `potato` in 1 of 200 weeks with 3 slots); `slot_pool_too_small:reggeli` (only 5 egg-free breakfasts) |
| `no_repeat_days` 10, 28 days (the API allows up to 14) | `slot_pool_too_small:reggeli` (9 breakfasts); variety passes in 68/200 (3 slots) and 81/200 (5 slots) weeks |
| `no_repeat_days` 14, 28 days | also `slot_pool_too_small:ebed` and `:vacsora` |
| all dairy excluded (tej, túró, joghurt, kefir, both tejföls, trappista, edami, feta, mozzarella, vaj; 7 and 28 days) | `no_legume_recipe_available` and every slot pool too small, because all 5 lentil recipes have a required dairy line; also a few `red_meat` and `potato` failures |
| fish excluded (`exclude_tags: hal`, 7 days) | `no_fish_recipe_available`, as designed |

**What the plans look like.** Weekly averages over the 28-day default plans (seeds 0–49):

| Slots | Lunch/dinner meals | `husmentes` | `huvelyes` | `hal` | `baromfi` | `sertes` | `marha` | Red meat (g/person) |
|---|---|---|---|---|---|---|---|---|
| SLOTS_3 | 14 | 10.52 | 4.71 | 1.34 | 0.82 | 1.26 | 0.06 | 193 |
| SLOTS_5 | 14 | 10.82 | 4.91 | 1.25 | 0.65 | 1.22 | 0.06 | 185 |

**Every recipe is used**, but the use is uneven: out of 14,000 planned meals over all default runs, from 885 (`lencseleves`) down to 18 (`rakott-brokkoli-csirkemellel`).
- The planner minimises the number of distinct perishable ingredients per week.
- So recipes with few perishables (lentil, egg, pasta and cabbage dishes) are picked far more often than poultry, fish and beef dishes with fresh meat and broccoli.
- This is planner scoring, not a rule failure. It is reported here for the planner owner and the founder.

## 7. Database load check

**What was run:** the real `data/` files, loaded through `python -m bpf.content` (`main([])`, role `bpf_ingest`) into a throwaway cluster from `server/tests/pgcluster.py`. The script was a scratch pytest file, not committed.

**Results:**
- First load: `ingredients_inserted=162, recipes_inserted=41, ksh_inserted=61`.
- Second load: `no changes`.
- `ops.ingest_run` holds 2 rows, both `content ok`.

**Read back as `bpf_api`:**
- `api.ingredient`: all 162 rows equal the loaded `Ingredient` objects, field by field.
- `api.recipe` and `api.recipe_line`: all 41 recipes and 408 lines equal the loaded `Recipe` objects. That covers title, summary, slots, servings, minutes, tags, steps, `tested` and every line (`line_no`, `ingredient_id`, `qty`, `display`, `optional`).
- `api.ksh_latest`: 61 rows.
- `suggest_plan` on the recipes read back from the database gave a 7-day, 5-slot plan with every rule passing.

## 8. Known gaps and follow-ups

1. **Cook-testing.** All 41 recipes are `tested: false` (see the top of this file).
2. **Legume variety.** The 5 `huvelyes` recipes are all lentil dishes. Dry beans, chickpeas and sárgaborsó are not priceable in GVH (BUILD-BRIEF §3), so the plans repeat lentils often (§6).
3. **Dairy-free households.** All 5 lentil recipes have a required dairy line (tejföl, joghurt, trappista or feta), so a dairy-free exclusion leaves no legume recipe. Options for M1:
   - a dairy-free lentil dish;
   - making the cheese topping of `lencseragus-spagetti` optional.
4. **Pool sizes for longer no-repeat windows.** 9 breakfasts support `no_repeat_days` up to 9, and only 5 breakfasts are egg-free.
   - Aim for at least 14 breakfasts (at least 7 egg-free) and more lunch/dinner recipes, towards the M1 size of about 100–150 (BUILD-BRIEF §5).
5. **Chain coverage of required GVH lines.** The research listing of 2026-10-12 shows these ingredients at fewer than 6 grocery chains:
   - ponty (3: Auchan, Lidl, Tesco);
   - zsemle (3: Auchan, Spar, Tesco; used in both fasírt recipes);
   - kenyer_rozs (5, no Tesco);
   - fokhagyma (5, no Lidl);
   - kaposzta and uborka (5, no Auchan);
   - rizs (no Aldi).

   These lines show as unavailable at the missing chains. Recheck with real data after the first ingest.
6. **Pasta shapes.** GVH has no Hungarian pasta shapes. Betűtészta, levestészta, csiga, nagykocka and csusza are priced through the generic `teszta` and `teszta_tojasos` rows. The shopping list then shows one pasta line per row, while the recipe line text names the shape.
7. **Unverified name rules.** Recipes use edami, harcsa, kelkaposzta, marha and sertescomb, and the ontology pass had no real GVH product names for their leaves. Check `candidate_products` for these after the first daily ingest.
8. **Unpriced garnishes.** kapor, petrezselyemzold, salata and zeller are optional lines only, and they show as "nincs ár".
9. **Nutrition.** `data/nutrition/` is empty: CIQUAL, Frida and USDA are blocked here. The API returns `nutrition: null` until composition data is imported.
10. **Coverage prices.** The shares in §4 use research reference prices. The share stays 100 % whatever the prices are, but per-chain `priced_share` depends on real availability (item 5).
11. **Title overlap.** "Tojásos lecsó" is also the title of an OKOSTÁNYÉR recipe in the research statistics (`research/gap-healthy-plan-priceability/data/recipe_coverage.csv`). It is the generic name of a traditional dish. Our ingredient amounts and all of the text are our own; no MDOSZ or OKOSTÁNYÉR content is used.
    - No other title of ours equals one of the 139 titles in the research files (94 OKOSTÁNYÉR, 45 Penny).
    - Two generic dish names of ours appear inside longer titles there: "Tejfölös krumplileves" (Penny) and "Lencseleves" (OKOSTÁNYÉR).
12. **Runny yolks.** `lagytojas-piritossal` (6-minute eggs) and the two tükörtojás főzeléks keep the yolk runny.
    - The soft-boiled egg recipe offers 9–10 minutes for a set yolk.
    - The tükörtojás steps fry until the whites are fully set.
    - No health wording was added.

## 9. QA performed in this pass

**Validation and loader.** Full validation and coverage over both recipe files. The content tests (444) pass, and the throwaway database load passes (§7).

**Ingredient additions requested by the earlier content agents: none.** Their reports asked for no ontology rows, so `data/ingredients.json` is unchanged.
- The open items they raised (garnish herbs, celery and salad leaves without a price; pasta shapes) have no GVH leaf and no KSH row.
- The research leaf list and `data/ksh/ara0044.csv` were checked to confirm this.

**Proofreading of every recipe:**
- **Language:** Hungarian spelling and grammar.
- **Quantities:**
  - per-serving amounts were computed for all 408 lines; none is off by 10×;
  - each line's `display` matches its `qty` in the canonical unit (dkg, dl, l, db and piece weights);
  - the water and oil splits in the steps add up to the line totals.
- **Steps:**
  - every line is used in the steps;
  - doneness checks are given for poultry, pork, beef and fish;
  - the six two-day main dishes say to cool the leftovers and refrigerate them within two hours, then reheat to boiling; the two-day cake keeps covered at room temperature;
  - times are plausible;
  - tags are consistent (`gyors` ≤ 25 minutes; every `ket_napos` recipe has a storage step; no `gyerekbarat` recipe has a required `nut_seed` line).
- **Claims:** no health or nutrition claims.
- **Originality:** the research files hold titles, URLs and ingredient lists, but no recipe instruction text. No text of ours reads like a known recipe-site phrasing.

**Text fixes, all in `data/recipes/main.json`, keeping the authors' intent:**

| Recipe | Fix |
|---|---|
| `zoldsegleves` | Summary: "Tiszta, könnyű zöldségleves" → "Tiszta levű zöldségleves". "Könnyű" can read as the regulated "light" nutrition claim (Reg. 1924/2006; BUILD-BRIEF §8.7). |
| `paprikas-csirke-nokedlivel` | The serving instruction was missing ("…és a nokedlivel tálald"). The two-day storage step now says to cool the dish and refrigerate it within two hours, like the other two-day main dishes. |
| `rakott-brokkoli-csirkemellel` | The bake step now states the doneness check: the topping is set in the middle and the chicken is cooked through. |
| `csirkeraguleves-zoldborsoval` | Grammar: "…a húskockák pedig a közepükön is teljesen fehérek **lesznek**". |
| `zoldsegleves` | The optional celery is marked as optional in step 2 as well ("(ha használsz) a zellert"). |
| `lencsefasirt-joghurtos-uborkasalataval`, `lencsesalata-fetaval` | The optional bread line is now mentioned in the serving step. |

## 10. How to re-run these checks

```sh
cd server
uv run python -m bpf.content --dry-run --coverage-report   # validation + coverage (reference prices)
uv run python -m bpf.content --coverage-report             # coverage with DB chain prices, when a DB is configured
uv run pytest tests/test_content_*.py -q                   # content tests, including the DB load tests
```

The planner sweep in §6 calls `bpf.planner.suggest_plan` with `load_content()` recipes for seeds 0–49, using the settings listed there.
