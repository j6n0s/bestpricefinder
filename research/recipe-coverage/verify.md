# Adversarial fact-check: "Recipe ingredient coverage and recipe cost" (stream: recipe-coverage)

Checked on 2026-10-12 by the fact-checker. Labels: **VERIFIED** (read from a source; URL given), **COMPUTED** (calculated here; method given), **ESTIMATE** (reasoning).

**What I did**
* Re-read the stream's notes, outputs and scripts.
* Re-ran `compute.py` in a sandbox copy (`verify_rerun/`). `coverage_metrics.json` came out byte-identical.
* Re-pulled from the GVH API (about 30 requests, 1 per second or slower, UA "market-research-bot/0.1 (fact-check)"): `/api/categories`, 12 `/api/search` terms, page-size tests, `/api/shops` and one store-filtered listing.
* Re-read Kifli's robots.txt, sitemap, recipe page and its ÁSZF (PDF, effective 2026-09-26), and re-tested Tesco.
* Ran three robustness experiments.

**Where things are**
* Raw downloads: `verify_raw/`. My scripts: `verify_scripts/`. Sandbox re-runs: `verify_rerun/` and `verify_rerun2/`.
* The web-search budget for this run ran out partway through. Later checks used direct fetches of primary pages only.

---

## Verdicts (8 load-bearing items)

### 1. Line coverage: 71.1% exact / 73.5% with substitutes (204 lines); traditional 85.7/87.8%, modern 57.5/60.4%
**Verdict: CONFIRMED (for this recipe sample).**

**Reproduction.** COMPUTED from `out/recipe_line_costs.csv`, and again by re-running `compute.py`:
* 145 E, 5 S and 54 N lines out of 204, after excluding 42 salt, pepper and water lines.
* Traditional 85.7 / 87.8%, modern 57.5 / 60.4%. These are identical to the stream's figures.

**Fresh GVH check.**
* The category tree is unchanged: 161 leaves, 120 of them in the 6 food top categories. VERIFIED, https://arfigyelo.gvh.hu/api/categories.
* A name scan of all 4,332 food SKUs found no red bell pepper, spinach, mushrooms, tuna, parmesan, canned tomatoes or passata, chickpeas or beans, zucchini, sweet potato, quinoa, bulgur or avocado. COMPUTED.
* Fresh searches confirm the same gaps (see item 4).

**Caveat.** The numbers describe this agent-authored set of 24 recipes, not Hungarian cooking in general (see item 2).

### 2. Implication: "GVH alone can support an 'everyday Hungarian' MVP" (traditional 86–88% of lines, 87–90% of cost)
**Verdict: PARTLY TRUE.**

The traditional set was curated toward "lighter" dishes built on chicken, pork, egg, dairy and potato.

**Independent test.** I wrote ingredient lists for 16 very common Hungarian home dishes (gulyás, csirkepaprikás, pörkölt, lecsó, tök-, spenót-, zöldbab- and sárgaborsó-főzelék, babgulyás, töltött káposzta, paradicsomleves, rántott csirke with rizibizi, halászlé, fasírt, gombapaprikás, mákos tészta) and mapped them by hand to the 120 GVH food leaves. Script: `verify_scripts/classic_sample.py`. Results:
* **Line coverage is 71.8% E and 73.5% E+S**, against the stream's 86–88% for "traditional". Excluding spices and vinegar it is 84.8% / 86.9%. ESTIMATE (my recipe lists), COMPUTED (counts).
* **In 9 of the 16 dishes the main ingredient is not in GVH**: főzőtök, spenót, zöldbab, sárgaborsó, szárazbab, savanyú káposzta, paradicsompüré, csiperke and mák. That includes the főzelék family, which is the most typical "healthy everyday Hungarian" category.
* **0 of the 16 dishes are fully priceable.** 5 of 16 are if spices are assumed to be at home.
* Ground paprika (N) appears in 11 of the 16.

**Corrected statement.** GVH supports a curated "meat, dairy, egg and potato" subset of Hungarian cooking well. It does not cover everyday Hungarian cooking as a whole: főzelékek, bean dishes, savanyú káposzta, mushrooms and tomato soup lack their main ingredient. An "everyday Hungarian" MVP on GVH alone needs a recipe library deliberately restricted to covered ingredients, or a second price source for about 10–15 staples. The staples that matter for this cuisine differ from the stream's list: pirospaprika, savanyú káposzta, főzőtök, zöldbab, sárgaborsó, szárazbab, zeller, kapor, majoránna, zsemlemorzsa, mák and paradicsompüré.

### 3. Cost coverage: 54.4% / 57.1%; traditional 87.4/89.8%, modern 36.7/39.6% (46.9% at kifli ÷ 1.35); top-10 missing → 86.6%, top-20 → 97.6%
**Verdict: PARTLY TRUE.** The numbers reproduce exactly, but the inputs and the ranking are fragile.

**Reproduction.** COMPUTED: 57.1% overall, and 64.3% / 46.9% with kifli ÷ 1.35. Traditional with ÷1.35 is 92.2%, a figure the stream did not report.

**Kifli prices are real but often not from the cited page.**
* I checked the 47 saved Kifli pages. Six "VERIFIED" prices come from *related-product cards* on a different product's page, so the cited URL is not the product's own page:
  * zabpehely (YUTTO 399 Ft, cited URL is Cerbona 839 Ft);
  * méz (Ezercsepp 3,199 Ft, cited URL is MMM 1,299 Ft / 250 g);
  * kaliforniai paprika (Trikolor 500 g 1,549 Ft, cited URL is "étkezési paprika lédig");
  * vörösbab (Kitchin 249 Ft, cited URL is Happy Frucht 699 Ft);
  * jégsaláta (cited URL is the spinach page);
  * pirospaprika (Horváth Rozi 879 Ft regular, cited URL is Hódi 1,799 Ft).
* The tejföl calibration pair has the same problem: "Miil 12% 200 g" is cited to a "Magyar Tejföl 20%" URL.
* I found the card prices in the saved HTML. VERIFIED (`raw_shops/kifli_pages/*.html`). The citations, however, are imprecise.

**Out-of-stock and premium items.**
* **Tuna** is priced from "Twist tonhal natúr lében 240 g", 2,199 Ft, which was **out of stock** and is a premium brand at 13,089 Ft/kg. All tuna on Kifli costs 1,599–2,919 Ft. That single line is 2,199 Ft of the 20,194 Ft modern total.
* Re-pricing tuna at about 800 Ft (ESTIMATE of a discounter can, not verified) moves modern cost coverage from 39.6% to about 42.5%. COMPUTED. The direction holds.
* Chili, nutmeg and passata were also out of stock when read.

**The ranking metric double-counts frequency.** It multiplies the *summed* used cost across recipes by the number of recipes.
* Ranked by cost alone, the top 10 lifts coverage to **89.2%** (not 86.6%), with a different list: tuna, red pepper, spinach, sweet potato, canned tomato, mushroom, parsley, zucchini, iceberg lettuce and avocado. COMPUTED.
* Top-20 coverage is 97.6% either way.

**Corrected statement.** On the stream's 24-recipe sample, GVH prices about 57% of used cost (64% if non-GVH items are deflated by 1.35); traditional is about 90%, modern about 40–47%. Which ~10 items to add depends on the recipe library. For classic Hungarian cooking the list differs from the stream's (see item 2).

### 4. GVH catalogue facts: search = same universe as the category tree; listed items absent; corrections to the brief (salmon, Greek yoghurt, pasta shapes, page size)
**Verdict: CONFIRMED.** The page-size "correction" is a nuance, not a correction.

**Fresh searches** (VERIFIED, https://arfigyelo.gvh.hu/api/search?q=…):
* 0 hits: tonhal, pirospaprika, fűszerpaprika, parmezán, kaliforniai.
* spenót: baby food plus one Barilla tricolore pasta.
* gomba: processed cheese, camembert, one gluten-free pasta.
* zabpehely: gluten-free flour and a soap.
* csicseriborsó: baby food and gluten-free pasta.
* paradicsom: fresh tomato leaf plus baby food.
* Search is a plain substring match: "bab" returns 629 baby products.

**Salmon.** Leaf 93 has 63 SKUs, **41 of them salmon**, across all 6 grocery chains. Lidl also has an MSC wild salmon at 4,796 Ft/kg, tying Aldi. COMPUTED from the raw leaf.

**Greek yoghurt.** In leaf 7 it appears only at Tesco and Spar (4 SKUs). VERIFIED.

**Pasta.** Leaf 50 (162 SKUs) has no nagykocka, csusza, tarhonya, cérnametélt or széles metélt. VERIFIED.

**Page size.**
* Without `limit` the API returns 12 per page: `/products-by-category/96` gives 12 of 24.
* `limit=48` returns 24 of 24. `limit=100` and `limit=500` on leaf 14 return 48 of 89, so 48 is the cap.
* The site's own front end calls the API with `{limit:12, offset:0}` (`/assets/index-5baaf084.js`).
* So both the brief ("max 48") and the stream ("default 12") are right. Using `limit=48` would cut the 416-request full crawl to about 130 requests. COMPUTED (ESTIMATE of the request count).

### 5. Chain comparison: Lidl cheapest for 13/24; median spread cheapest↔priciest 20.8%; buying each line at its cheapest chain saves 4.9%
**Verdict: PARTLY TRUE.** The spread figure is misreported.

**What holds.**
* Lidl 13/24, Aldi 4, Spar 3, Tesco 2, Auchan 2: reproduced. COMPUTED.
* Cherry-picking every line saves a median 4.84–4.92%: reproduced.
* Robustness: Lidl's cheapest csirkemellfilé is "Csirkemell tokány" (1,859 Ft/kg), which the stream itself flags as mis-filed. Excluding it, Lidl is cheapest for **12/24** (Spar 4) and the other metrics do not change. COMPUTED (`verify_rerun2/`).
* Chicken breast is price-matched at every chain anyway: 1,926–1,979 Ft/kg.

**What is wrong.**
* **The median spread is 18.4%, not 20.8%.** The stream's own `coverage_metrics.json` and `recipe_costs.csv` give a median of 18.36% (mean 22.5%).
* The notes' "traditional mean 24.5%" is **19.2%** in the files. The modern mean of 25.7% is correct.
* 20.8% does not appear in any output file. COMPUTED.

**How to read the spread.** It compares different sets of "complete" chains per recipe: M12 has only 2 complete chains and shows 1.8%. It also compares different grades within one leaf: M03's 83% is frozen wild salmon against fresh salmon. Treat it as indicative only.

### 6. Promotions are nearly absent from GVH (2.5% DISCOUNTED, 2.9% LOYALTY), so deal features need leaflet data
**Verdict: PARTLY TRUE.** The counts are right; the interpretation is not established.

**Counts.** 135 / 5,370 DISCOUNTED and 157 / 5,370 LOYALTY entries, reproduced. Aldi has 0 DISCOUNTED and Lidl has 0 LOYALTY. COMPUTED.

**What the law requires.** VERIFIED, GVH ÁFF for retailers (effective 2025-07-20), https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_kereskedo.pdf. Retailers must send, **daily** and by the end of the day before the price applies:
* the **"napi ár"**, defined as the **lowest unit price publicly available to every consumer that day**;
* the **"korábbi ár"**, the price before an announced reduction (4/2009 NFGM-SZMM 2/A);
* the **"törzsvásárlói ár"** (loyalty price).

The front end labels the price types "Ár", "Akciós ár" and "Törzsvásárlói ár". The site also advertises that users can find out about promotional prices and loyalty discounts.

**Alternative explanations the stream did not rule out.** Announced promotions are legally *supposed* to be in the feed. The low share therefore may reflect:
* (a) genuinely few promotions in these staple categories. Many fall under the **árrésstop** margin cap (in force at 2026-10-05; see Missed);
* (b) promotional prices reported as the plain daily price without a "korábbi ár", which would make them invisible in a one-day snapshot (Aldi's 0 is suspicious);
* (c) app coupons such as Lidl Plus that are not reported as loyalty prices.

A single snapshot cannot tell these apart.

**Store-level test.** VERIFIED, `/api/products-by-category/35?limit=48&shopIds=spar-110` (Spar, Budapest I., Batthyány tér):
* "Étkezési paprika lédig" is **853 Ft** there.
* At chain level it shows **NORMAL 815 Ft and DISCOUNTED 399 Ft**.
* So a chain-level promotion may not apply in a given store, and the local base price can differ.

**Corrected statement.** On 2026-10-12, 2.5% of GVH food chain-price entries carried a flagged discount. Whether GVH misses leaflet promotions is unverified. Archive GVH daily and compare against one week of Lidl, Aldi, Spar and Tesco leaflets before deciding that leaflet data is required.

### 7. Pack sizes and weekly planning: single-recipe pack cost 2.06× used; regrouping the same 24 recipes cut the perishable basket 35,824 → 28,147 Ft (−21.4%)
**Verdict: CONFIRMED.** The figures reproduce and survive stress tests. The extrapolation is in-sample.

**Reproduction.** −21.4% and the leftover share 42.1% → 26.4% reproduce exactly. COMPUTED.

**The "perishable" set was too broad.** It includes onions, garlic, potatoes, cabbage, apples, eggs, butter, dry sausage, trappista and parmesan, which keep for weeks. Re-run with only short-shelf-life items (dairy, fresh meat and fish, leafy and soft vegetables, bread, fresh herbs): **−21.1%** (27,768 → 21,920 Ft; leftover share 39.6% → 23.5%). COMPUTED (`verify_rerun/scripts/week_regroup_short.py`).

**Variety constraint.** Keeping 3 traditional + 3 modern dinners per week (the optimiser otherwise builds, for example, an all-tejföl week): **−17.4%** against the original grouping. COMPUTED.

**Baseline check.** The original grouping (35,824 Ft) is close to the mean of 300 random 4×6 week assignments (36,693 Ft; range 31,083–40,245). The constrained optimum is −19.4% against that random mean. COMPUTED.

**Corrected statement.** About 17–21% of the perishable basket, in-sample on these 24 recipes, with no carry-over of leftovers between weeks and recipes fixed in advance. With real user choice and a pantry ledger the gain will be smaller. Treat about 20% as an upper-range ESTIMATE until it is tested out-of-sample.

### 8. Kifli: about 3,500 priced recipes; Kifli's product pages are technically readable as a secondary price source (terms not checked); Tesco online blocks automated reads (HTTP 403)
**Verdict: PARTLY TRUE.**

**Recipe count.** `sitemap_base.xml` has 3,504 `/sef/` URLs:
* **3,373 recipe pages**;
* 119 recipe-category pages;
* 12 ingredient hub pages (e.g. /sef/hozzavalo/106-pirospaprika).

COMPUTED, https://www.kifli.hu/sitemap_base.xml. So the correct figure is about 3,370 recipes, not 3,500.

**Recipe page.** Re-read, VERIFIED, https://www.kifli.hu/sef/10240-rakott-krumpli:
* "pricePerPortion" 474…, "totalPrice" 5 737…, "portions":8;
* "Valószínűleg otthon van";
* "Spórolj akár 19%".

The 1.51× ratio is correct. COMPUTED.

**Robots and terms.**
* robots.txt still disallows only `/regal/*` for `*`, and explicitly *allows* ClaudeBot, GPTBot and others. VERIFIED, https://www.kifli.hu/robots.txt.
* **The ÁSZF (effective 2026-09-26) prohibits automated or manual copying.** Section 3 ("Vásárlóként vállalja", point c), in translation: the customer does not obtain, track or copy the Online Shop's content or information, whether by automated means or manually, without Kifli's prior written permission. Point (d) bans circumventing access restrictions or causing undue load. §11 claims all rights in the site's content, expressly including its databases.
* VERIFIED, https://cdn-kifli.s3.eu-central-1.amazonaws.com/files/terms/260926_A%CC%81ltala%CC%81nos+Szerzo%CC%8Bde%CC%81si+Felte%CC%81telek_final_HU.pdf (text extracted locally: `verify_raw/kifli/aszf_260926.txt`).
* The clause binds registered customers, but together with §11 and the CV-Online sui generis test it rules out systematic Kifli scraping as a production source without a licence.

**Tesco.** A request today again returned **HTTP 403 "Access Denied" (Akamai edgesuite)**, even for robots.txt and with a browser-like UA. VERIFIED. This is a block of plain HTTP clients. It is not proof that every automated access is blocked, and it contradicts the brief's statement that Tesco's robots.txt "doesn't block product pages": the file cannot be read from here.

**Corrected statement.** Kifli has about 3,370 recipe pages with recipe-to-basket pricing. Its prices are publicly visible, but its current ÁSZF forbids automated or manual systematic copying without written permission. Treat Kifli as a partnership or licence target, not a scrape source.

---

## Important things the stream missed

1. **Kifli's ÁSZF prohibits systematic copying, automated or manual**, without written permission (§3(c), effective 2026-09-26), and claims database rights (§11). This changes Kifli from a "secondary price source" to a licence or partnership target. It also affects any plan to use Kifli's 3,373 recipe pages or ingredient nodes.
2. **The árrésstop margin cap is still in force and under review.**
   * As of 2026-10-05 it still covers about 43 food categories, overlapping heavily with GVH's (poultry, pork, dairy, eggs, flour, sugar, potatoes, garlic, apples, pears, cabbage, tomatoes, onions, green peppers, trappista, beef cuts). The Tisza government is publicly considering a phase-out but has not decided. Source (secondary): https://index.hu/gazdasag/2026/10/05/arresstop-elelmiszerarak-inflacio-kiskereskedelem-kisboltok-magyar-peter-hatosagi-ar-elelmiszerinflacio-dragulas-boltok/ ; https://www.portfolio.hu/gazdasag/20261003/tisza-kormany-egesz-hetvegen-ulesezik-a-kormany-fontolora-veszik-az-arresstop-kivezeteset-867082
   * This plausibly explains why staples cost the same everywhere (tejföl 359–360 Ft at all 6 chains; chicken breast 1,926–1,979 Ft/kg) and why few promotions appear. ESTIMATE.
   * If the cap ends, chain spreads, the "Lidl cheapest" result, the "store switching saves little" conclusion and promotion frequency could all change. Re-measure them after any policy change.
3. **GVH reporting rules** (retailer ÁFF): retailers report the daily lowest public price, the pre-reduction price and the loyalty price, daily and in advance. The DISCOUNTED flag therefore means "announced price reduction". A promotion reported only as the daily price would show up as NORMAL and could only be detected with a daily archive. Snapshot data cannot measure promotion coverage.
4. **Store-level pricing is easy to get and does differ from chain level.**
   * `products-by-category/{id}` accepts `shopIds=` (comma-separated). The front end uses this for favourite stores. `/product/{id}/shop/{ids}` also takes several stores.
   * One test store showed a higher base price (853 vs 815 Ft) and no chain promotion.
   * `/api/shops` now lists **1,829** stores (GVH press said 1,817). VERIFIED.
   * The GVH UI itself states that listed prices hold in at least 80% of a chain's stores and that some stores can be cheaper (front-end string "ABOVE_THRESHOLD").
   * The recipe costs should be re-run per store for the "local best price" feature.
5. **Recipe sampling bias.** Both recipe sets were written by the agent. A defensible coverage estimate needs an external sample, such as the top N recipes by popularity from Nosalty or Mindmegette (terms to be checked), or a licensed ingredient-frequency list. Seasonal and classic staples are absent from GVH: tök, zöldbab, sárgaborsó, szárazbab, savanyú káposzta, zeller, kapor, sütőtök, mák.
6. **Citation hygiene.** Several kifli prices are "VERIFIED" from related-product cards on a different product's page; the tuna, chili, nutmeg and passata prices are from out-of-stock items; and the notes misstate two numbers (spread 20.8% instead of 18.4%; traditional mean spread 24.5% instead of 19.2%).
7. **Competitors already claim food-waste savings.** Jow's homepage states that a family using Jow saves on average "381.1 lb food waste / year" (VERIFIED, https://jow.com/). The mechanism is undocumented. "Nobody documents leftover optimisation" may be true, but "leftover-aware planning" is not an uncontested positioning claim.
8. **Single-day snapshot.** All price findings (spreads, cheapest chain, promotions) come from one day. The front end exposes no price-history endpoint; it uses only categories, chain-stores, shops, products-by-category, search, product and product/{id}/shop/{ids}. History needs the app's own daily archive, and should be checked against ÁFF XII.4 (only non-archived data are public).
