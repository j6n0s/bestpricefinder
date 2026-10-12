# Recipe ingredient coverage and recipe cost (stream: recipe-coverage)

Research date: 2026-10-12 (all prices read this day). Author: research agent.
Labels: **VERIFIED** = read from a source (URL given); **COMPUTED** = calculated from data pulled here (method given); **ESTIMATE** = my reasoning/assumption.

## 0. TL;DR

* GVH Árfigyelő prices **71% of ingredient lines exactly (74% incl. close substitutes)** in 24 realistic 2-serving weeknight recipes, but only **54–57% of their cost**. It works for *traditional Hungarian* cooking (86–88% of lines, 87–90% of cost) and poorly for *modern healthy* cooking (58–60% of lines, 37–40% of cost; 47% if the uncovered items are re-priced at discounter level). COMPUTED.
* Only **2/24 recipes (strict) or 4/24 (accepting substitutes)** are fully priceable from GVH (excluding salt, pepper and water). If spices and pantry items are treated as "already at home", it is **7/24 or 9/24**. COMPUTED.
* The ~10 missing items with the most weight (red bell pepper, fresh spinach, fresh parsley, canned tomatoes, canned tuna, sweet potato, mushrooms, canned chickpeas, parmesan-type cheese, ground paprika) would lift cost coverage from 57% to about 87%. The top 20 would lift it to about 98%. COMPUTED.
* Median cost at the cheapest chain is **672 Ft/serving** (traditional 378, modern 727). The median gap between the cheapest and dearest chain on the GVH-priced part is **21%**. Lidl is cheapest for 13 of the 24 recipes. Splitting one recipe's shopping across chains saves only about 5% more than using the single cheapest chain. COMPUTED.
* Pack sizes dominate real spend. Buying one recipe on its own costs a median **2.1× the "used" cost** (3.5× with spices and pantry items). Shopping per week (6 dinners) still leaves 25–57% of non-pantry spend as leftovers. **Re-grouping the same 24 recipes into weeks that share perishables cut the perishable basket by 21%** (leftover share 42% → 26%). COMPUTED.
* GVH carries few promotions: 2.5% of chain-price entries have a DISCOUNTED price and 2.9% a LOYALTY price. Aldi has 0 discounted entries and Lidl has 0 loyalty entries. Where promotions exist they cut the recipe cost by 4–20%. COMPUTED.

## 1. Data pulled (method)

* GVH API (no auth, polite, ~1.6 req/s, UA `market-research-bot/0.1`):
  * `GET https://arfigyelo.gvh.hu/api/categories` and `/api/chain-stores` gave the category tree (161 leaves, of which **120 are in the 6 food top-categories**) and 9 chains. VERIFIED.
  * `GET /api/products-by-category/{leafId}?offset=N` for all 120 food leaves took 416 requests and gave **4,332 food SKUs and 5,370 chain-price entries**. Raw JSON is in `raw_gvh/leaves/`. COMPUTED. Without a limit parameter the default page size was **12** (e.g. lencse: 12 of 24 on offset 0). 416 requests matches 12/page exactly. COMPUTED.
  * `GET /api/search?q=` for 34 ingredient terms (`raw_gvh/search/`). Search returns the **same product universe** as the categories. It finds nothing outside the leaves, so it cannot extend coverage. VERIFIED.
* kifli.hu (robots.txt allows product pages and blocks only `/regal/*`; VERIFIED https://www.kifli.hu/robots.txt). I read 46 public product pages (1 every 1.5 s), using the **regular** price and ignoring the personal "-10% neked" price. I also read 1 public recipe page and the sitemaps. Raw HTML is in `raw_shops/`.
* bevasarlas.tesco.hu returned **HTTP 403 "Access Denied" (Akamai)** to a plain request, even for robots.txt. I did not use it and did not try to get around it. VERIFIED (response saved in `raw_shops/tesco_robots.txt`).
* Scripts: `scripts/` (dl_leaves.py, search.py, kifli_fetch.py, kifli_parse2.py, data_defs.py = recipes + ontology + kifli prices, compute.py, ingredient_spread.py, week_regroup.py).

### Output files (all under this folder)
| File | Content |
|---|---|
| `out/recipes.csv` | 24 recipes × ingredient lines (2 servings), own lists |
| `out/ingredient_mapping.csv` | ingredient → GVH leaf ids + include/exclude rules, level E/S/N, #SKUs, chains, min price, kifli fallback + URL |
| `out/recipe_line_costs.csv` | every line: cost at the recipe's cheapest chain, SKU used, pack bought, leftover, source URL |
| `out/recipe_costs.csv` | per recipe: coverage, cheapest/priciest chain, spread, Ft/serving, cost share, pack cost |
| `out/missing_ingredients_ranked.csv` | uncovered items ranked by frequency × cost |
| `out/ingredient_chain_spread.csv` | per ingredient: cheapest vs dearest chain unit price |
| `out/kifli_prices_uncovered.csv` | price + URL for every non-GVH item |
| `out/kifli_vs_gvh_calibration.csv` | kifli premium vs GVH cheapest on 6 identical generic items |
| `out/week_plan_summary.csv`, `out/week_plan_pack_optimisation.csv`, `out/week_regroup_experiment.json` | weekly pack-size optimisation |
| `out/coverage_metrics.json`, `out/extra_metrics.json` | all headline metrics, data-quality stats |
| `out/gvh_leaf_categories.csv` | all 161 leaves with path/top category |

## 2. Corrections and additions to the "already established" facts

1. **Salmon *is* covered.** The leaf *Tengeri halfilé* (93) contains about 40 salmon SKUs: Aldi "MSC vadlazac filé 250g" 4,796 Ft/kg, Lidl "Bőrös lazacfilé" 7,199 Ft/kg, Auchan, Spar, Tesco and Penny fresh and frozen fillets. Search "lazac" returns 54 hits. VERIFIED (API, leaf 93). Because it sits in a generic "sea fish" leaf, salmon must be picked out by product name.
2. **Greek yoghurt** sits inside *Natúr joghurt* (7), but only at **Tesco and Spar**: "RN NATÚR GÖRÖG LIGHT JOGHURT 1 kg QQ" 996 Ft/kg, "DANONE GÖRÖG STILUSU 375 g", "Koliós … görög joghurt 200 g". VERIFIED.
3. **Coconut milk substitute**: leaf 83 *Tejszín helyettesítésére szolgáló növényi krém* has coconut cooking cream at Tesco, Auchan, dm and Müller (e.g. "The Bridge … bio kókusz főzőtejszín 200 ml" 559 Ft at Tesco). It has no canned coconut milk. VERIFIED.
4. *Száraztészta* (50) includes **wholemeal pasta** (Aldi, Penny, Tesco, dm, Müller, Auchan), but **no Hungarian shapes**: no nagykocka, csusza, széles metélt, tarhonya or cérnametélt. These appear only as gluten-free products in leaf 80. It has mainly spaghetti, penne, fusilli/orsó and makaróni, plus "4 tojásos" variants. VERIFIED (regex scan of all 4,332 names). This is a coverage gap for traditional dishes such as káposztás tészta and túrós csusza.
5. *Paradicsom* (34) includes cherry tomatoes and *Vöröshagyma* (40) includes "Salátahagyma". **Red onion, red/yellow bell pepper ("kaliforniai paprika") and lettuce are absent.** VERIFIED (searches return 0).
6. Confirmed **not covered** (search = 0 food hits, or only baby food, gluten-free flour/pasta or cosmetics): oats (only GF oat flour), chickpeas (only GF flour/pasta), zucchini, spinach, sweet potato (baby food only), mushrooms, **all spices including ground paprika** ("pirospaprika" = 0 hits), canned tomatoes, passata, tomato paste, tuna, parmesan, quinoa, bulgur, avocado, tahini, kidney beans/any canned beans, fresh ginger, fresh herbs, walnuts, honey, vinegar, stock cubes. VERIFIED (`raw_gvh/search/*.json`).
7. **Rice at Aldi, Greek yoghurt at Aldi, Lidl and Penny, and lean (≤20%) minced pork at Auchan and Spar are missing from GVH.** These are chain-level gaps, not category gaps. They make some recipes "incomplete" at some chains (see §4). VERIFIED.
8. Only 2.5% of chain-price entries carry a DISCOUNTED price and 2.9% a LOYALTY price (Auchan 6.5% loyalty, Tesco 3.8%; Aldi 0% discounted; Lidl 0% loyalty). Weekly leaflet promotions are therefore mostly **not** in the data. COMPUTED (5,370 entries).

## 3. Recipes (own lists, 2 servings)
12 lighter traditional Hungarian (T01–T12) and 12 modern healthy (M01–M12) recipes. Full quantities are in `out/recipes.csv`. Salt, pepper and water are listed but excluded from the metrics.
T01 Lencsefőzelék főtt tojással · T02 Paprikás csirke joghurttal, rizzsel · T03 Rakott karfiol (sovány darálthús) · T04 Zöldborsóleves + teljes kiőrlésű kenyér · T05 Brokkolis csirkemell rizzsel · T06 Töltött paprika light + főtt burgonya · T07 Káposztás tészta · T08 Rakott krumpli light · T09 Zöldséges csirkeragu rizzsel · T10 Túrós csusza light · T11 Alma-körte gyümölcsleves joghurttal · T12 Sült pulykamell tepsis zöldségekkel · M01 Zabkása gyümölccsel, dióval · M02 Csicseriborsós-spenótos curry rizzsel · M03 Sült lazac édesburgonyával, brokkolival · M04 Quinoa saláta fetával · M05 Shakshuka + teljes kiőrlésű kenyér · M06 Spenótos teljes kiőrlésű tészta · M07 Gombás rizottó · M08 Chili sin carne rizzsel · M09 Buddha bowl barna rizzsel · M10 Tonhalas saláta tojással · M11 Cukkinis-paradicsomos teljes kiőrlésű spagetti fetával · M12 Görög joghurtos csirkemell bulgurral, tzatzikivel.
In total: 246 lines, of which 204 count after excluding salt, pepper and water. They use 81 distinct ingredients.

## 4. Mapping method and levels
* An **ingredient ontology** (`scripts/data_defs.py`, `ONT`) maps each ingredient to GVH leaf id(s), with name include/exclude regexes, a base unit (kg / l / db), an optional piece weight and a pantry flag.
  * **E (exact)**: the product type is in a GVH leaf.
  * **S (substitute)**: GVH has only a close culinary substitute (lilahagyma → vöröshagyma; nagykocka/csusza → 4-tojásos száraztészta; kókusztej → kókusz főzőtejszín), priced at GVH.
  * **N (not covered)**: priced from kifli.hu.
  * Arborio vs. B rice, red bell pepper vs. TV paprika and brown vs. white rice were deliberately classed **N**, not S. The price and the dish change too much (arborio 1,898 Ft/kg at kifli vs. 529 Ft/kg B rice), so a substitute would mislead users.
* **Price per chain** = the minimum, over matching SKUs, of the NORMAL `unitAmount` converted to the ingredient's base unit. Pieces are converted to kg with ESTIMATE piece weights: onion 120 g, garlic head 67 g (COMPUTED from the "Fokhagyma 200g = 3 db" SKUs at Aldi and Lidl), TV paprika 110 g (COMPUTED from Lidl 3 db 265 Ft vs 829 Ft/kg), carrot or parsley root 80 g, lemon 100 g, apple or pear 180 g, banana 170 g, cucumber 350 g (Lidl "min. 300g"), cauliflower 750 g.
* "Used cost" = quantity × unit price. It is the right basis for cost per serving.
* "Pack cost" = the cheapest whole-pack purchase covering the quantity. Variable-weight (Ft/kg, `unitTitle = kg`) items are assumed to be bought at the exact weight.
* A chain counts as **complete** for a recipe only if it has every E/S line. The cheapest/priciest chain and the spread are computed over complete chains, on the GVH-priced part only. N lines are a constant add-on from kifli.

## 5. Coverage results (COMPUTED from out/recipe_line_costs.csv)

| Metric | All 24 | Traditional (12) | Modern (12) |
|---|---|---|---|
| Ingredient lines (excl. salt/pepper/water) | 204 | 98 | 106 |
| % lines exact (E) | **71.1%** | 85.7% | 57.5% |
| % lines E+S | **73.5%** | 87.8% | 60.4% |
| Recipes fully covered, strict (E only) | **2 (8%)** | 2 | 0 |
| Recipes fully covered, E+S | **4 (17%)** | 4 | 0 |
| Fully covered if spices/pantry assumed at home, strict / E+S | 7 / 9 | – | – |
| % of cost covered, E | **54.4%** | 87.4% | 36.7% |
| % of cost covered, E+S | **57.1%** | 89.8% | 39.6% |
| % cost E+S if uncovered items re-priced at discounter level (kifli ÷ 1.35) | 64.3% | – | 46.9% |
| Median recipe cost share E+S | 73.5% | – | – |

Distinct ingredients: 81 = 43 E + 4 S + 34 N. Of the 34 N, 12 are spices or pantry items (paprika, bay leaf, vinegar, cinnamon, rosemary, honey, curry, cumin, chili, oregano, nutmeg, stock cube) and 22 are "real" foods.

Fully covered recipes: T05 Brokkolis csirkemell, T08 Rakott krumpli (strict), plus T07 Káposztás tészta and T10 Túrós csusza (with the pasta-shape substitute).

## 6. Recipe cost per serving and chain spread (COMPUTED; GVH NORMAL prices + kifli regular prices, 2026-10-12)

"Spread" = (priciest complete chain − cheapest complete chain) / cheapest, on the GVH-priced part only.

| ID | Recipe | E/S/N lines | Cheapest chain | GVH part cheapest Ft | Priciest complete chain | GVH part priciest Ft | Spread % | Uncovered (kifli) Ft | Ft/serving cheapest | Ft/serving priciest | Cost share E% / E+S% | Pack cost single purchase Ft |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T01 | Lencsefőzelék főtt tojással | 8/0/3 | Lidl | 333 | Auchan | 438 | 31.3 | 37 | 185 | 237 | 89.9 / 89.9 | 3612 |
| T02 | Paprikás csirke joghurttal, rizzsel | 8/0/1 | Lidl | 759 | Penny | 866 | 14.1 | 70 | 415 | 468 | 91.5 / 91.5 | 3042 |
| T03 | Rakott karfiol (sovány darálthússal) | 9/0/1 | Lidl | 1809 | Tesco | 1893 | 4.7 | 18 | 913 | 956 | 99.0 / 99.0 | 5043 |
| T04 | Zöldborsóleves teljes kiőrlésű kenyérrel | 7/0/1 | Spar | 407 | Tesco | 602 | 47.8 | 184 | 296 | 393 | 68.9 / 68.9 | 2354 |
| T05 | Brokkolis csirkemell rizzsel | 7/0/0 | Lidl | 1370 | Tesco | 1474 | 7.6 | 0 | 685 | 737 | 100.0 / 100.0 | 2826 |
| T06 | Töltött paprika (light) főtt burgonyával | 10/0/2 | Lidl | 987 | Tesco | 1075 | 8.9 | 333 | 660 | 704 | 74.8 / 74.8 | 4363 |
| T07 | Káposztás tészta | 4/1/0 | Aldi | 251 | Penny | 281 | 12.0 | 0 | 125 | 141 | 54.7 / 100.0 | 1520 |
| T08 | Rakott krumpli light | 6/0/0 | Lidl | 684 | Spar | 800 | 16.9 | 0 | 342 | 400 | 100.0 / 100.0 | 1863 |
| T09 | Zöldséges csirkeragu rizzsel | 9/0/2 | Lidl | 1015 | Tesco | 1166 | 14.9 | 392 | 703 | 779 | 72.1 / 72.1 | 4279 |
| T10 | Túrós csusza light | 3/1/0 | Lidl | 577 | Auchan | 792 | 37.4 | 0 | 288 | 396 | 75.4 / 100.0 | 819 |
| T11 | Alma-körte gyümölcsleves joghurttal | 6/0/1 | Spar | 317 | Penny | 400 | 26.3 | 16 | 166 | 208 | 95.2 / 95.2 | 997 |
| T12 | Sült pulykamell tepsis zöldségekkel | 7/0/1 | Lidl | 1233 | Spar | 1335 | 8.3 | 62 | 647 | 698 | 95.2 / 95.2 | 4884 |
| M01 | Zabkása gyümölccsel és dióval | 3/0/4 | Lidl | 229 | Tesco | 301 | 31.5 | 327 | 278 | 314 | 41.2 / 41.2 | 5784 |
| M02 | Csicseriborsós-spenótos curry rizzsel | 4/1/5 | Tesco | 680 | Auchan | 715 | 5.1 | 989 | 835 | 852 | 7.3 / 40.7 | 5226 |
| M03 | Sült lazac édesburgonyával és brokkolival | 5/0/1 | Aldi | 1919 | Penny | 3506 | 82.7 | 600 | 1259 | 2053 | 76.2 / 76.2 | 5759 |
| M04 | Quinoa saláta fetával | 5/1/3 | Lidl | 936 | Tesco | 1122 | 19.8 | 889 | 912 | 1005 | 50.8 / 51.3 | 7831 |
| M05 | Shakshuka teljes kiőrlésű kenyérrel | 6/0/5 | Auchan | 549 | Tesco | 770 | 40.2 | 921 | 735 | 846 | 37.4 / 37.4 | 6441 |
| M06 | Spenótos teljes kiőrlésű tészta | 4/0/3 | Aldi | 354 | Auchan | 485 | 36.9 | 925 | 639 | 705 | 27.7 / 27.7 | 5319 |
| M07 | Gombás rizottó | 4/0/5 | Aldi | 99 | Spar | 120 | 21.8 | 1278 | 688 | 699 | 7.2 / 7.2 | 6527 |
| M08 | Chili sin carne rizzsel | 6/0/5 | Lidl | 312 | Auchan | 338 | 8.3 | 1076 | 694 | 707 | 22.5 / 22.5 | 4547 |
| M09 | Buddha bowl barna rizzsel | 4/0/6 | Lidl | 253 | Tesco | 327 | 29.5 | 1634 | 943 | 981 | 13.4 / 13.4 | 10721 |
| M10 | Tonhalas saláta tojással | 7/1/2 | Spar | 672 | Tesco | 854 | 27.1 | 2798 | 1735 | 1826 | 19.1 / 19.4 | 6464 |
| M11 | Cukkinis-paradicsomos teljes kiőrlésű spagetti fetával | 6/0/1 | Auchan | 675 | Penny | 703 | 4.2 | 640 | 657 | 671 | 51.3 / 51.3 | 3855 |
| M12 | Görög joghurtos csirkemell bulgurral és tzatzikivel | 7/0/2 | Tesco | 1316 | Spar | 1340 | 1.8 | 124 | 720 | 732 | 91.4 / 91.4 | 5317 |

Summary (COMPUTED):
* Ft/serving at the cheapest chain: median **672**, mean 647. Traditional median **378**, modern median **727**. The range runs from 125 Ft (káposztás tészta) to 1,735 Ft (tuna salad, of which 2,199 Ft for 2 servings is a branded tuna can at kifli).
* Spread between cheapest and priciest chain: median **20.8%** (traditional mean 24.5%, modern 25.7%). Extreme cases come from single SKUs:
  * M03 is +83%: the Aldi frozen MSC wild salmon is 4,796 Ft/kg vs Penny's fresh "Gran mare lazacfilé" at 9,997 Ft/kg.
  * T04 is +48%: Tesco's only wholemeal bread in GVH is a premium multigrain loaf at 1,778 Ft/kg vs 448 Ft/kg at Aldi.
* Cheapest chain counts: Lidl 13, Aldi 4, Spar 3, Tesco 2, Auchan 2. Penny and Tesco are never or rarely cheapest. The median ratio to the cheapest complete chain is Aldi 1.03, Auchan 1.05, Spar 1.07, Penny 1.12, Tesco 1.16.
* Chain index on the 7 recipes complete at all 6 chains, excluding the salmon outlier: Lidl 100, Aldi 105, Spar 111, Penny 112, Tesco 114, Auchan 115.
* Chain completeness (out of 24 recipes): Tesco 24, Penny 22, Spar 19, Auchan 17, Lidl 17, Aldi 16. The gaps come from GVH data, not from real shelves. Examples: rice at Aldi; Greek yoghurt only at Tesco and Spar; coconut cream only at Tesco and Auchan; Lidl's wholemeal bread is hidden in a mixed SKU, "Kemencés kedvencek (teljes kiőrlésű kenyér és félbarna…)".
* Cherry-picking every line across all chains saves a median **4.9%** on the GVH part compared with the single cheapest chain.
* Using DISCOUNTED and LOYALTY prices where present lowers the GVH part of 9/24 recipes, by 4–20% (e.g. M01 229 → 184 Ft at Spar, T02 759 → 657 at Spar, M12 1,316 → 1,135 at Tesco). The median effect is 0%.
* Per-ingredient chain spread (`out/ingredient_chain_spread.csv`): median max/min of the chain-cheapest unit price is **1.32**.
  * Staples are price-matched across discounters and private labels: tejföl 12% 450 g is 359–360 Ft at all 6 chains; flour, sunflower oil, frozen peas, broccoli and turkey breast are within 5% at all 6.
  * Large differences are in produce, meat and fish, olive oil and bread: cauliflower 399 Ft/db at Auchan vs 999 at Lidl, Penny, Spar and Tesco; tomatoes 429 Ft/kg "Paradicsom 1kg" at Lidl vs 879 Ft/kg "fürtös" at Aldi. These are often *different quality grades hidden under one leaf*.

### Uncovered-item price source and its bias
46 kifli.hu pages were read. Every non-GVH price, with its URL, is in `out/kifli_prices_uncovered.csv`.
Calibration on 6 identical generic items: kifli regular price vs. GVH cheapest. COMPUTED; kifli URLs are in `out/kifli_vs_gvh_calibration.csv`.

| Item | kifli Ft/kg | GVH cheapest Ft/kg (chain) | kifli premium |
|---|---|---|---|
| csirkemellfilé | 2,558 | 1,859 (Lidl) | +38% |
| vöröshagyma | 219 | 190 (Lidl) | +16% |
| tejföl 12% | 1,075 | 798 (Spar) | +35% |
| rizs | 799 | 529 (Tesco) | +51% |
| lencse | 998 | 738 (Tesco) | +35% |
| durum spagetti | 770 | 588 (Spar) | +31% |

The median premium is **+35%**. The uncovered part is therefore probably overstated. Spot items look notably high: branded tuna 2,199 Ft/can, organic avocado 559 Ft, imported fresh spinach 2,798 Ft/kg, yellow zucchini 1,599 Ft/kg (no green zucchini listed), tri-colour bell pepper 3,098 Ft/kg. ESTIMATE: discounter prices for these are typically 20–50% lower. They were not verified because no discounter source was read.

## 7. Missing ingredients ranked by frequency × cost (COMPUTED, out/missing_ingredients_ranked.csv)

| Rank | Ingredient | Level | # recipes (of 24) | Used cost in 24 recipes Ft | freq x cost | Pantry/spice |
|---|---|---|---|---|---|---|
| 1 | kaliforniai (piros) paprika | N | 3 | 1394 | 4182 | False |
| 2 | friss spenót | N | 3 | 1147 | 3442 | False |
| 3 | petrezselyemzöld (friss) | N | 5 | 645 | 3224 | False |
| 4 | aprított/hámozott paradicsom konzerv | N | 3 | 915 | 2745 | False |
| 5 | tonhal konzerv (natúr) | N | 1 | 2199 | 2199 | False |
| 6 | édesburgonya | N | 2 | 959 | 1918 | False |
| 7 | csiperkegomba | N | 2 | 899 | 1798 | False |
| 8 | csicseriborsó konzerv | N | 2 | 430 | 860 | False |
| 9 | kókusztej | S | 1 | 850 | 850 | False |
| 10 | parmezán / grana típusú kemény sajt | N | 2 | 419 | 839 | False |
| 11 | őrölt fűszerpaprika | N | 5 | 149 | 747 | True |
| 12 | cukkini | N | 1 | 640 | 640 | False |
| 13 | jégsaláta | N | 1 | 599 | 599 | False |
| 14 | avokádó | N | 1 | 559 | 559 | False |
| 15 | passata / paradicsompüré | N | 1 | 315 | 315 | False |
| 16 | arborio rizottó rizs | N | 1 | 304 | 304 | False |
| 17 | vörösbab konzerv | N | 1 | 249 | 249 | False |
| 18 | quinoa | N | 1 | 240 | 240 | False |
| 19 | tahini | N | 1 | 189 | 189 | False |
| 20 | dióbél | N | 1 | 164 | 164 | False |
| 21 | currypor | N | 1 | 160 | 160 | True |
| 22 | barna rizs | N | 1 | 144 | 144 | False |
| 23 | őrölt római kömény | N | 2 | 66 | 133 | True |
| 24 | csusza / széles metélt | S | 1 | 128 | 128 | False |

Coverage uplift if GVH (or a second source) added the top-N N-items by this ranking (COMPUTED):
| Added | Cost coverage | Line coverage | Recipes fully covered |
|---|---|---|---|
| none | 57.1% | 73.5% | 4 |
| top 5 | 77.4% | 80.9% | 5 |
| top 10 | 86.6% | 87.3% | 9 |
| top 20 | 97.6% | 92.2% | 13 |

Even with the top 20 added, only 13/24 recipes are complete, because low-cost spices remain. **Spices and pantry items need a "probably at home" rule** (Kifli does exactly this, see §9), not price coverage.

ESTIMATE (general Hungarian home cooking, beyond this sample). These are the ~20 items most worth sourcing:
1. őrölt pirospaprika
2. friss petrezselyem (and other fresh herbs)
3. csiperkegomba
4. paradicsomkonzerv / passata / sűrített paradicsom
5. kaliforniai paprika
6. spenót (fresh or frozen)
7. cukkini
8. zabpehely
9. canned beans and chickpeas
10. tonhal konzerv
11. édesburgonya
12. sütőtök
13. zeller
14. póréhagyma / újhagyma
15. savanyú káposzta
16. fejes saláta / jégsaláta
17. parmezán-típusú sajt
18. dió
19. méz
20. common spices (babérlevél, kömény, majoránna, bors)

Hungarian pasta shapes (nagykocka, csusza, tarhonya, cérnametélt) are a special case: GVH covers the product family but not the shape.

## 8. Product-matching problems — concrete examples from the GVH data (VERIFIED unless marked)

**A. Pack size vs recipe quantity, and leftovers.** The source is `out/recipe_line_costs.csv`: for each line, the pack bought at the recipe's cheapest chain and the leftover.
* Tejföl 12%:
  * T01 needs 60 g; the smallest pack is 175 g (149 Ft) or 450 g (359 Ft).
  * T03 needs 200 g, which means 2 × 175 g (298 Ft) or 450 g (359 Ft) with 250 g left over.
* Eggs: T03 and T06 need 1 egg, but packs are 10 or 30. Lidl "Friss Tojás 10 db S" costs 455 Ft for a 45.5 Ft need.
* Feta: M05 needs 50 g; packs are 200 g (899 Ft at Aldi, Lidl and Tesco).
* Főzőtejszín 10%: recipes need 100–150 ml; packs are 200 ml and 500 ml.
* Csemegekukorica: recipes need 100–140 g; cans are 340 g with 285 g drained weight, and GVH `packaging` gives the drained 0.285 kg.
* Brokkoli: M03 needs 250 g; the pack is 500 g.
* Non-GVH items:
  * friss gyömbér: 10 g needed vs a 300 g pack (899 Ft);
  * spenót: 60 g vs 500 g (1,399 Ft);
  * petrezselyem: 5–10 g vs a 26 g bunch (479 Ft);
  * spices: 0.4–2 g vs 5–100 g packs.
* Result: buying one recipe on its own costs a median **2.06×** its used cost excluding pantry items (**3.49×** including them). COMPUTED.

**B. Variable-weight produce and meat.**
* 54.5% of fresh meat, fish and produce SKUs have `unitTitle = "kg"`: a Ft/kg price, with the final pack price unknown until weighed. COMPUTED (617 fresh SKUs).
* Some per-piece items have no weight at all:
  * "Karfiol db" (999 Ft/db) and "Kígyóuborka db" are priced per piece.
  * "Étkezési paprika 5 db/csomag" has `unitAmount` = 88 Ft/**db**.
  * "Sárgarépa csomós" has `unit = db`, `unitTitle = kg`.
* **21 of 120 food leaves mix price units** (kg vs db vs l) within the same leaf: Zöldpaprika, Fokhagyma, Vöröshagyma, Sárgarépa, Petrezselyemgyökér, Citrom, Alma, Banán, Főzőtejszín (l vs kg), and others. COMPUTED (`extra_metrics.json`).
* So `minUnitPrice` / `unitAmount` cannot be compared within a leaf without piece-weight conversions. This is ESTIMATE-dependent: piece weights were assumed.

**C. Product names (counter and abbreviated names).**
* Tesco counter products carry numbered, accent-stripped names:
  * "16. SERTES COMB pultos QQ"
  * "14. FRISS CSIRKEMELL FILE PULTOS QQ"
  * "12. FRISS CSIRKE COMB PULTOS QQ"
  * "18. SERTES KARAJ CSONT NELKUL PULTOS QQ"
  * "25. MARHA LABSZAR CSONT NELKUL"
  * "27. FRISS PULYKAMELL FILE PULTOS"
* 175 of 1,123 Tesco SKUs end in "QQ". COMPUTED.
* Truncated or abbreviated names: "TS SPAGETTI DURU M TESZT 500G", "TO TELJK. SPAGETTI 500G", "Pro görnatjog 1 kg QQ" (= Greek natural yoghurt), "TELJ.K.TÖBBMAGV. KENYÉR 500G", "Petrezs.gyök.500g girbe-gurba".
* Auchan uses long descriptive names instead: "Auchan Kedvenc Friss Sertés Tarja csont nélkül szupermarket Húspultban kapható Ft/kg".

**D. Brand vs private label; identity across chains.**
* Only **16.2% of SKUs are listed by more than one chain**. COMPUTED.
* Private labels have chain-internal ids (955 SKUs with `aldi-`, `lidl-`, `penny-` or `spar-` prefixes; 327 in-store codes starting with 2). Cross-chain equivalence therefore cannot rely on the EAN. It must be done at the "generic product" level (e.g. "tejföl 12% 450 g, private label"). COMPUTED.
* One SKU can stand for several products:
  * "BON-RI zöld lencse/vörös lencse 500g": 5 Aldi ids aldi-194057001…005;
  * "Kemencés Kedvencek fehér kenyér vagy teljeskiőrlésű kenyér";
  * "Milsani/Milfina tejföl 12% 450g";
  * "Gyulai/Csabai pároskolbász";
  * "Hazánk Kincsei Paprikás szárazkolbász, több ízben";
  * "Milbona Natúr joghurt, 2féle".
  * In total there are 47 such multi-variant private-label SKUs in the food leaves. COMPUTED (regex on "többféle | / | vagy | 2féle").
* The same EAN can carry very different prices by chain:
  * "Globus párolt csemegekukorica 340 g": Spar 319 Ft vs Auchan and Tesco 659 Ft.
  * "Bertolli Originale EVOO 500 ml": Spar 2,999 vs Tesco 4,919.
  * "Barilla Spaghetti 1 kg": Spar 869 vs Auchan 1,429.
  * "Farmer UHT tej 1,5%": Spar 155 vs Lidl 265.

**E. Mis-categorisation and grade mixing inside leaves.**
* "Tejmalom érlelt trappista db" sits in *Natúr joghurt*.
* "TOLLE LIGHT TRAP. FÉL SAJT" sits in *Feta*, and "Fitaki" and "Apetina" (non-feta white cheeses) sit there too.
* "Cheeseland füstölt edami" sits in *Trappista tömbsajt*.
* "Csirkemell tokány" and bone-in "Felezett csirkemell" sit in *Csirkemellfilé*.
* "Spar … hegykői vegyeszöldség 1kg" sits in *Petrezselyemgyökér*.
* Grades are mixed: fresh vs frozen and wild vs farmed salmon in one leaf; "Paradicsom 1kg" vs "fürtös"; 7%, 20% and 30% fat minced pork in one leaf. Recipe specs therefore need attributes such as fat %, form and grade, or the "cheapest" match silently changes the dish.

**F. Data errors in pack and unit fields.**
* "Koronás kristálycukor 1 kg" has `packaging` = 0.5.
* "Magyar főzőtejszín 21%" is 0.18 kg at 399 Ft (Aldi) vs 839 Ft (Auchan).
* The name "Lidl Kígyóuborka 2db" shows a different pack than its "db" price.
* `unitAmount` deviates more than 5% from amount ÷ packaging in only **25 of 5,370 packaged price entries (0.5%)**, mostly Spar teas where `unitAmount` equals the pack price. COMPUTED. Unit prices are mostly internally consistent; the problems are semantic (units, grades, multi-variant SKUs), not arithmetic.
* `priceSameEverywhere = false` on 9.5% of chain-price entries. COMPUTED. The cheapest "national" price may not be the price in the user's nearby store; the store-level endpoint is needed (the gvh-location stream covers this).

## 9. How existing products solve it

* **Kifli.hu / Rohlik "Séf" recipes.** VERIFIED from a public page, https://www.kifli.hu/sef/10240-rakott-krumpli, embedded data read 2026-10-12.
  * Each recipe line is an **ingredient node** (`ingredientId`, e.g. 70 "Tejföl", 74 "Tojássárgája", 6 "Burgonya") with a **curated list of candidate SKUs**. Each candidate carries an integer **pack count** (`"products":[{"productId":96853,"amount":2,"selected":true},{"productId":28039,"amount":3,…}]` for "400 ml tejföl"), and there are `alternativesCount` swaps.
  * **Strategy presets**: "Ajánlott – A séf választása" 5,737.60 Ft; "Legolcsóbb – Spórolj akár 19%-ot" −1,078.17 Ft; "BIO/Organikus – Prémium alapanyagok" +1,177.40 Ft.
  * **Portion scaling** ("Adagok növelése/csökkentése", default 8 portions).
  * A **"Valószínűleg otthon van"** (probably at home) group for salt, which is unselected by default ("selectedIngredientsCount 5 of 6").
  * Two prices are shown: **"Adagonkénti ár" 474.59 Ft**, computed on used quantity, and the **basket total** 5,737.60 Ft, computed on whole packs. 474.59 × 8 = 3,797 vs 5,738, so the pack basket is **1.51×** the used cost for this 8-portion recipe. COMPUTED.
  * The kifli sitemap lists about **3,504 `/sef/` recipe URLs**. COMPUTED (sitemap_base.xml). The "2 ks tojássárgája" ("ks" is Czech for "pieces") shows the Rohlik platform is reused.
  * Rohlik has offered recipe-based shopping since 2019 with several price variants per ingredient (https://www.mediaguru.cz/clanky/2019/03/rohlik-cz-nove-nabizi-nakup-podle-receptu-romana-vanka/) and publishes an MCP server for AI assistants (https://rohlik.cz/mcp-docs). VERIFIED via search snippets only.
* **Instacart Developer Platform.** VERIFIED: https://docs.instacart.com/developer_platform_api/api/products/create_recipe_page.
  * Each recipe ingredient has `name` (used as the **search term** for matching), optional `product_ids` or `upcs` (UPCs act as ordered fallbacks), `measurements` (quantity + unit, with "each" recommended for countables), and `filters` (`brand_filters`, `health_filters` such as ORGANIC or GLUTEN_FREE).
  * The retailer catalogue does the matching. The docs say nothing explicit about pack-size optimisation.
* **Whisk / Samsung Food.**
  * A "Food Genome": NLP that parses recipe text into ingredients and relates them to category, nutrition, perishability and availability. It merges duplicate ingredients across recipe components on the shopping list and scales servings. VERIFIED: https://venturebeat.com/ai/how-whisk-is-using-its-food-genome-to-turn-recipes-into-smart-shopping-lists.
  * It links to 30+ online grocers, uses a daily store inventory feed with Sainsbury's, and was rebranded Samsung Food in 2023. Per search snippets of press releases (https://www.businesswire.com/news/home/20210126005433/en): plausible but not re-read in full.
* **Jow (FR/US).**
  * It works through the grocer's own site "in the background", builds the cart from the chosen recipes, syncs it to the grocer cart and shows grocer prices. VERIFIED: https://jow.com/pages/legal-information/how-does-it-work.
  * The help pages claim the list holds only the quantities the recipe needs. I found no public description of its pack-size logic.
  * Trade press says Jow fills about 70% of the basket algorithmically and picks products partly with grocer input (https://grocerydive.com/news/kroger-jow-shoppable-recipes-grocery-ecommerce-profitability/706931; search snippet only).
* Common pattern (ESTIMATE, synthesised from the above): **ingredient ontology node → retailer-specific candidate SKU list (curated or search-based, with filters) → integer pack quantity → user-switchable strategy (cheapest / recommended / organic) → pantry exclusion**. None of these systems publicly documents cross-recipe leftover optimisation, which leaves room to differentiate.

## 10. Weekly pack-size optimisation (COMPUTED)

**Set-up.** The 24 recipes were split into 4 weeks of 6 dinners. For each week, the quantities of each ingredient were summed across its recipes. The cheapest **combination** of pack sizes covering each total was found with a covering-knapsack DP (combinations such as 450 g + 175 g allowed). Each week has one primary chain; items missing there are filled from the cheapest other chain, and N items come from kifli. Files: `out/week_plan_summary.csv`, `out/week_plan_pack_optimisation.csv`.

| Week | Recipes | Primary chain | Used cost (non-pantry) | Each recipe bought separately | Aggregated weekly basket | Saving from aggregation | Leftover share of basket |
|---|---|---|---|---|---|---|---|
| W1 | T01,T02,T05,M03,M10,M01 | Auchan (+1 fill-in) | 8,979 | 15,767 | 14,667 | 7.0% | 38.8% |
| W2 | T03,T07,T11,M02,M06,M12 | Auchan (+4) | 6,001 | 12,717 | 10,719 | 15.7% | 44.0% |
| W3 | T04,T06,T10,M04,M08,M11 | Spar (+2) | 7,028 | 14,196 | 10,690 | 24.7% | 34.3% |
| W4 | T08,T09,T12,M05,M07,M09 | Auchan (+1) | 7,928 | 21,336 | 18,592 | 12.9% | 57.4% |

The "leftover" share includes storable staples (rice, pasta, lentils), so it is not all waste.

**Perishables only.** The leftover share is 25–44% per week. The largest leftovers:
* fresh spinach: 60 g used of a 500 g pack;
* red pepper: 150 g of 500 g;
* ginger: 10 g of 300 g;
* parmesan: 30 g of 100 g;
* eggs: 1 of 10;
* feta: 50 g of 150–200 g;
* cooking cream: 100 ml of 200 ml;
* cucumber: 150 g of a whole cucumber.

**Regrouping experiment** (`scripts/week_regroup.py`, simulated annealing over swaps of recipes between weeks; perishables only; cheapest-unit chain per ingredient). Keeping the **same 24 meals** but grouping recipes that share perishables:
* the perishable basket fell from 35,824 to **28,147 Ft (−21.4%)**;
* the leftover share fell from 42.1% to **26.4%**;
* the saving vs buying every recipe separately (42,417 Ft) is **−33.6%**.

The optimiser clustered, for example, the tejföl/egg recipes (T03, T08, T06, T10, T01) into one week and the spinach/cream recipes (M02, M06, M09, T05, T09) into another. Caveat: this is in-sample, has no variety or nutrition constraints, and does not carry pantry over between weeks. It still suggests a **leftover-aware planner is worth about 20% of the perishable grocery bill**, which is a larger saving than switching chain (median spread 21%) and much larger than cherry-picking stores (about 5%).

## 11. Proposed approach (ESTIMATE / design recommendation)

1. **Ingredient ontology (~300–500 nodes for Hungarian home cooking).** Each node carries:
   * attributes: form (fresh/frozen/canned/dried), fat %, cut (filé/comb/csontos), grade (fürtös/koktél), private-label-ok;
   * conversions: piece weight, density, drained weight;
   * pantry flag and perishability (shelf life after opening);
   * substitutes with an acceptability score, e.g. lilahagyma → vöröshagyma (0.9), arborio → B rice (0.3).
2. **Node → GVH leaf → SKU rules.** Start each node from one or more leaf ids, then apply include/exclude regex or attribute filters and an optional manual SKU whitelist or blacklist (see `out/ingredient_mapping.csv`; 47 nodes were mapped in under a day). Add classifiers for:
   * multi-variant SKUs ("többféle", "/", "vagy");
   * mis-filed items (simple name classifier per leaf);
   * per-piece vs per-kg prices (piece-weight table);
   * same-EAN price outliers (flag a chain-to-chain ratio above 1.8).
   Store a confidence score per match and show "≈" badges when a substitute or estimate is used.
3. **Two prices per recipe**, as Kifli shows:
   * "Ft/adag", on used quantity, for planning and comparison;
   * "kosár ár", on whole packs at the chosen store, for the shopping list.
4. **Week planner with pack-size optimisation.** Choose recipes and pack SKUs to minimise the basket (packs) plus a waste penalty. Constraints: the user's preferences, nutrition targets and variety (e.g. ≤2 recipes sharing a main protein). Carry a pantry or leftover ledger across weeks for shelf-stable items. This is a small MILP or greedy plus local search; the experiment above shows about 20% upside on perishables.
5. **Store choice.** Default to the single cheapest *complete* nearby store; the GVH `/shops` endpoint gives locations. Offer a second store only if the saving exceeds a threshold (cherry-picking adds only about 5%). Handle chain-level GVH gaps with fallbacks: rice at Aldi, Greek yoghurt outside Tesco and Spar.
6. **Sources for non-GVH items.**
   * Tier 1: get the top-20 list in §7 priced, through a partnership, Kifli or Rohlik feeds, leaflet extraction (as Árnéni does), or a small manual weekly price panel.
   * Tier 2: show "estimated price" for spices and pantry items, or exclude them as "probably at home".
   * Recipe design lever: the app can **prefer recipes built from GVH-covered ingredients** (this traditional set is 86–88% covered by lines), which raises accuracy at no data cost.
7. **Promotions.** GVH carries almost none (2.5% DISCOUNTED, 2.9% LOYALTY entries), so "best weekly deal" features need leaflet data. The core "cheapest store for my week" can run on NORMAL prices.

## 12. Implications for build / data strategy

* GVH alone is **enough for an MVP focused on traditional or "everyday Hungarian" healthy-ish recipes**: about 90% of cost is priced and store comparison is meaningful. It is **not enough for a "modern healthy" (bowls, quinoa, salmon, avocado, legumes, spinach) positioning**: only 37–47% of cost is priced.
* Recipe and menu design should be **data-aware**: build the recipe library from covered ingredients first and add a tier-1 non-GVH price source for about 20 items.
* The differentiator vs Árnéni (prices only) and Kifli (recipes but one retailer) is **multi-chain recipe pricing plus leftover-aware weekly planning**. Store switching alone saves about 5–20%. Leftover-aware planning showed about 20% on perishables in this test.
* Matching needs a curated ontology and rules layer plus QA. Naive leaf-minimum pricing would mislead users (frozen wild salmon vs fresh, 30% vs 7% mince, multi-variant SKUs, per-piece vs per-kg).

## 13. Open questions
* Store-level prices (`/product/{id}/shop/{storeId}`): how often does the local price differ from the chain price for these 47 nodes? (9.5% of entries are not the same everywhere.)
* Can Kifli/Rohlik or the chains provide feeds for the top-20 uncovered items? Is reading kifli product pages acceptable under Kifli's ÁSZF (terms not checked here)?
* What are discounter prices for the uncovered items (Lidl/Aldi leaflets or websites)? This would shrink the +35% kifli bias.
* GVH coverage over time: does the 140→161 category list keep growing (e.g. toward canned tomatoes, oats, spices)?
* Piece weights and drained weights are estimates. A small measured table (or Open Food Facts weights) is needed.
* User research: do target users accept substitutes (B rice for arborio) or "≈ estimated" prices?

## 14. Sources
* GVH Árfigyelő API (read 2026-10-12): https://arfigyelo.gvh.hu/api/categories, https://arfigyelo.gvh.hu/api/chain-stores, https://arfigyelo.gvh.hu/api/products-by-category/{id}, https://arfigyelo.gvh.hu/api/search?q=…
* kifli.hu robots.txt and sitemaps: https://www.kifli.hu/robots.txt, https://www.kifli.hu/sitemap_products.xml, https://www.kifli.hu/sitemap_base.xml
* kifli.hu product pages: the 46 URLs in `out/kifli_prices_uncovered.csv` and `out/kifli_vs_gvh_calibration.csv`
* kifli.hu recipe page: https://www.kifli.hu/sef/10240-rakott-krumpli
* Tesco online 403: https://bevasarlas.tesco.hu/robots.txt
* Instacart IDP: https://docs.instacart.com/developer_platform_api/api/products/create_recipe_page
* Whisk: https://venturebeat.com/ai/how-whisk-is-using-its-food-genome-to-turn-recipes-into-smart-shopping-lists ; https://www.businesswire.com/news/home/20210126005433/en
* Jow: https://jow.com/pages/legal-information/how-does-it-work ; https://grocerydive.com/news/kroger-jow-shoppable-recipes-grocery-ecommerce-profitability/706931
* Rohlik: https://www.mediaguru.cz/clanky/2019/03/rohlik-cz-nove-nabizi-nakup-podle-receptu-romana-vanka/ ; https://rohlik.cz/mcp-docs
