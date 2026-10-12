# Gap-fill: can a health-first, all-meals Hungarian plan be priced with GVH plus legal fallbacks?

Stream: gap-healthy-plan-priceability. Research date 2026-10-12. All prices were read on that day.
Labels: **VERIFIED** = read from a primary source (URL given). **COMPUTED** = calculated by me from data pulled here (method given). **ESTIMATE** = my judgement or assumption.
Web search budget for the session ran out early (shared limit). I used direct fetches (curl/WebFetch) of known primary URLs only and reused two sitemap files that the alt-price-sources stream had downloaded (marked).

---

## 0. Verdict (TL;DR)

1. **GVH alone cannot price an OKOSTÁNYÉR-style plan.** For 85 non-dessert OKOSTÁNYÉR dishes (25 breakfasts, 42 lunch dishes, 18 dinners), GVH prices 60.4% of ingredient lines exactly and 67.5% with close substitutes. It covers only **47.0% of the cost exactly and 53.5% with substitutes**. Only **4 of 85 dishes** are fully priceable from GVH. COMPUTED.
2. **KSH adds little.** Adding KSH ara0044 national averages (mushrooms, dry beans, walnuts, honey, jam) lifts cost coverage to **59.4%**. Fully priceable dishes rise to **6/85**, or **14/85 if fresh-herb garnish is treated as optional**. KSH prices are monthly national averages, not store or local prices. COMPUTED.
3. **By meal (OKOSTÁNYÉR, cost coverage GVH exact / with substitutes / with KSH):** breakfast **44.3 / 51.7 / 58.8%**, lunch without desserts **45.6 / 53.0 / 57.9%**, dinner **53.6 / 56.9 / 63.8%**. Breakfast is the weakest: 0 of 25 breakfasts are fully priceable from GVH, because oats, nuts and seeds, berries, cottage-style spreads with vegetables and tortillas are missing. COMPUTED.
4. **Control sample (45 random penny.hu recipes, mainstream rather than health-first):** cost coverage for main meals is **45.4 / 49.0 / 54.0%**, and 0 of 25 are fully priceable from GVH. Mainstream Hungarian supermarket recipes are no better covered than the healthy ones. COMPUTED.
5. **A 4-week plan for 2 adults using only GVH, KSH and pantry ingredients is possible only by rewriting most dishes.** A plan that meets all weekly OKOSTÁNYÉR rules (fish ≥1/week, legumes ≥1/week, one meat-free day, red meat ≤600 g raw per person per week, about 400 g of vegetables a day after a raw-vegetable top-up) can be scheduled. In that plan, **57% of the 100 meal slots are changed dishes** (oats → rice pudding, zucchini → pepper, spinach → broccoli, chickpeas → lentils, bulgur/couscous/millet → rice, trout/busa/tuna → catfish/salmon). **6 OKOSTÁNYÉR dishes have to be dropped.** COMPUTED + ESTIMATE (the swap table is my judgement).
6. **The strict variant fails.** Allowing only dishes that stay as published or need trivial changes (herbs or condiments left out, red onion → onion), the pools are 7 breakfasts, 7 lunch mains, 8 soups and 6 dinners. That pool has **no fish dish at all**, so the weekly fish rule fails in all 4 weeks, and the same menu repeats every week (up to 4–5 repeats in 28 days). COMPUTED.
7. **The residual gap is a long tail, not a few items.** The 9 named residuals (spinach, zucchini, chickpeas and beans, oats, canned tomato, tuna, sweet potato, red pepper, mushrooms) lift OKOSTÁNYÉR cost coverage only from 53.5% to **69.9%**. The **top 20 uncovered items lift it to 87.7% and the top 30 to 92.6%**. COMPUTED.
8. **New GVH categories come by ministerial decree, not by request to GVH.** The list grew from 62 (Jul 2023) to 78 (Jan 2024, 74/2023 GFM rendelet) to 140 (current Annex 1, set by 15/2025 (V.23.) NGM rendelet, in force 2025-05-31). The 2025 expansion added baby food, household and hygiene items, not food. GVH's API shows these 140 legal categories as 161 leaves. No public "request a category" channel was found. VERIFIED (njt.hu, GVH press).
9. **Decision implication.** The MVP is feasible without risky sources only if the app **authors its own healthy recipe set built on the about 95 GVH food categories**. KSH is used, clearly labelled, for mushrooms, dry beans, walnuts and honey, and a visible "nincs ár" (no price) badge marks the rest. Pricing third-party modern healthy recipes at store level needs a partner feed first. The best-positioned candidates are Roksh (Aldi's online shop and a price-comparison platform itself) and Auchan (which needs written permission). Groby's terms carry no reuse ban, but it is a Budapest-only online grocer. ESTIMATE (strategic inference).
10. **Recipe IP.** OKOSTÁNYÉR content is "Copyright MDOSZ. Minden jog fenntartva" (all rights reserved), commercial copying is forbidden, and OKOSTÁNYÉR® is a trademark. The app cannot reuse these recipes or the brand without a licence, which is a partnership opportunity. The Hungarian Wikibooks cookbook is CC BY-SA 4.0 and reusable with attribution and share-alike. VERIFIED.

---

## 1. Sources, robots and terms checked before sampling

| Source | robots.txt | Terms / licence | Use made here |
|---|---|---|---|
| okostanyer.hu (MDOSZ) | `Disallow: /wp-admin/` only; sitemap `wp-sitemap.xml` (VERIFIED https://www.okostanyer.hu/robots.txt) | Impresszum: "Copyright MDOSZ. Minden jog fenntartva… tilos kereskedelmi felhasználás vagy terjesztés céljából lemásolni, módosítani és más honlapokra áthelyezni." It also says the trademarks shown are MDOSZ's (VERIFIED https://www.okostanyer.hu/impresszum/) | Read ingredient lists for statistics only. I stored only canonical ingredient keys and grams, and deleted the raw pages and PDFs after parsing. |
| penny.hu/receptek | Only a `Sitemap:` line (VERIFIED https://www.penny.hu/robots.txt) | The jogi nyilatkozat has no explicit copyright, scraping or reuse clause (keyword search, VERIFIED https://www.penny.hu/joginyilatkozat). Default copyright under Szjt. still applies (INFERENCE). | Random sample of 45 of 546 recipe URLs (seed 20261012). Only JSON-LD `recipeIngredient` and `recipeCategory` were parsed, and the raw HTML was not kept. |
| hu.wikibooks.org Szakácskönyv | Wikimedia robots | "Creative Commons Nevezd meg! – Így add tovább! 4.0" (CC BY-SA 4.0). Category: 117 pages and 45 subcategories (VERIFIED https://hu.wikibooks.org/wiki/Szakácskönyv; API categoryinfo) | Not sampled, because Penny was used as the second sample. Noted as the only legally reusable recipe corpus found. |

**OKOSTÁNYÉR rules used (VERIFIED, https://www.okostanyer.hu/okostanyer-felnott-husok-halak-tojas-tej-es-tejtermekek/ , …-zoldsegek/ , …-gyumolcs/ , …-gabonafelek/):** at least 1 meat-free day a week; red meat at most 350–500 g cooked (500–700 g raw) a week; processed meat only occasionally; fish at least once a week, preferring domestic fish (pisztráng, harcsa, busa); offal at most once a week; complete protein at every main meal; 0.5 l of milk or the equivalent a day; legumes at least once a week (bab, borsó, lencse, csicseriborsó, szója); at least 5 portions of vegetables and fruit a day (3–4 vegetable and 1–2 fruit, at least 1 raw), with potato not counted; potato at most every second day; 3 cereal portions a day, at least 1 wholegrain; 2–3 small handfuls of unsalted nuts or seeds a week.

## 2. Samples (recipes not written by an agent)

- **OKOSTÁNYÉR:** a census of every breakfast, lunch and dinner recipe on the three recipe pages (https://www.okostanyer.hu/receptek-reggeli/ , /receptek-ebed/ , /receptek-vacsora/), plus the 9 most recent monthly recipe PDFs (2025-11 to 2026-09, e.g. https://www.okostanyer.hu/wp-content/uploads/2026/09/2026_09.pdf). Snack-only recipes (tízórai, uzsonna) were excluded. That gives **94 dishes: 25 breakfasts, 51 lunch dishes (of which 9 desserts, 12 soups, 6 sides or starters, 24 mains) and 18 dinners**, with 671 non-pantry ingredient lines. The monthly PDFs are the current 2025–26 series; the category pages are older (about 2019–2022). Coverage is similar in both (cost coverage with substitutes 49.6% vs 54.9%). COMPUTED.
- **Penny control:** 45 random recipes, of which 7 are breakfasts ("Kiadós reggeli receptek"), 25 main meals and 13 desserts. 405 non-pantry lines. COMPUTED.
- **Encoding.** OKOSTÁNYÉR lines were hand-encoded to canonical keys and grams (`scripts/recipes_okos.py`). Penny lines were mapped by regex and quantity parser and then hand-reviewed (`scripts/penny_map.py`). Piece and spoon weights are ESTIMATES (egg 55 g, bread slice 40 g, onion 100 g, garlic clove 5 g, tablespoon of oil 13 g, and so on).

## 3. Mapping and pricing method

- **GVH.** `GET https://arfigyelo.gvh.hu/api/categories`, then `/api/products-by-category/{leaf}?offset=N&limit=48` for all **120 food leaves** in the 6 food top categories. That took **159 requests** at about 0.6 s spacing with UA `market-research-bot/0.1` and returned **4,332 SKUs**, matching the recipe-coverage stream exactly. COMPUTED. Raw JSON is in `dl_gvh/leaves/`.
- **Classes per ingredient line.** E = exact GVH leaf. S = only a close GVH substitute (e.g. Greek yoghurt → natúr joghurt, chicken thigh fillet → whole thigh, Graham bread → wholemeal bread, lilahagyma → vöröshagyma, brown rice → white rice). K = no GVH leaf but a KSH ara0044 row. P = pantry (water, salt, pepper, dried spices and herbs, baking powder, vanilla, vinegar). N = none. Fresh herbs are N with a flag.
- **Reference prices for cost shares.** For E and S: the **median across chains of each chain's cheapest NORMAL unit price**, using only SKUs whose `unit` equals the canonical unit (see the data-quality finding in §6). For K: KSH ara0044, 2026-09. For N: the kifli.hu regular price read by the recipe-coverage stream divided by 1.35, its median kifli premium over GVH (ESTIMATE), or my own ESTIMATE of a discounter price where no kifli price exists. Pantry is excluded from the denominators. The uncovered prices only set the cost shares, so a ±30% error in them moves cost coverage by about ±5–8 pp (ESTIMATE).
- **KSH ara0044** (VERIFIED https://www.ksh.hu/stadat_files/ara/hu/ara0044.html; CSV variant `.csv`). 175 items, latest month **2026-09**, last updated 2026-10-07. **Licence: CC BY 4.0, explicitly including tables, commercial use allowed.** Only data sets extracted on individual request are CC BY-NC (VERIFIED https://www.ksh.hu/copyright).

## 4. Coverage results (COMPUTED; `data/coverage_by_group.csv`)

| Group | Recipes | Lines | Line E | Line E+S | Line +KSH | Line +KSH, herbs optional | Cost E | Cost E+S | Cost +KSH | Fully GVH | Fully GVH+KSH | Fully GVH+KSH, herbs optional |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OKOS breakfast | 25 | 161 | 49.7 | 58.4 | 65.2 | 68.6 | 44.3 | 51.7 | 58.8 | 0 | 1 | 2 |
| OKOS lunch excl. desserts | 42 | 309 | 65.7 | 71.5 | 74.4 | 78.8 | 45.6 | 53.0 | 57.9 | 3 | 4 | 9 |
| OKOS lunch desserts | 9 | 62 | 64.5 | 69.4 | 79.0 | 80.3 | 41.3 | 42.5 | 59.5 | 0 | 0 | 0 |
| OKOS dinner | 18 | 139 | 61.2 | 69.1 | 72.7 | 77.1 | 53.6 | 56.9 | 63.8 | 1 | 1 | 3 |
| **OKOS all excl. desserts** | **85** | **609** | **60.4** | **67.5** | **71.6** | **75.7** | **47.0** | **53.5** | **59.4** | **4** | **6** | **14** |
| OKOS 2025–26 PDFs only | 22 | 141 | 63.1 | 66.7 | 71.6 | 76.5 | 45.8 | 49.6 | 52.5 | 3 | 4 | 6 |
| PENNY breakfast | 7 | 40 | 62.5 | 72.5 | 75.0 | 76.9 | 48.3 | 69.7 | 73.1 | 1 | 1 | 2 |
| PENNY main meals | 25 | 251 | 54.6 | 59.8 | 62.9 | 66.7 | 45.4 | 49.0 | 54.0 | 0 | 1 | 2 |
| PENNY desserts | 13 | 114 | 62.3 | 65.8 | 72.8 | 74.1 | 46.2 | 46.7 | 53.7 | 1 | 1 | 1 |

- Fully GVH-priceable OKOSTÁNYÉR dishes: Brokkolikrémleves, Tojásos lecsó, Kelkáposztás-burgonyás rakottas, Hideg tésztasaláta. With KSH: + Körtés túrókrém pirítóssal, Fejtett bableves. With herbs optional: + Caprese szendvics, Fetás gombafejek, Kapormártás, Paradicsomos csirkemell burgonyapürével, Pulykaraguleves gyöngybabbal, Petrezselymes újburgonya, Kapros túrókrém vacsora, Hideg uborkaleves. COMPUTED.
- **Ingredient-cost level** (used quantities only, no pack waste): median **323 Ft per OKOSTÁNYÉR serving** (excluding desserts) and **541 Ft per Penny main-meal serving**. COMPUTED.
- These numbers agree with the earlier recipe-coverage stream (57% of cost overall, 37–47% for modern healthy recipes). The verifier's point that legume and főzelék staples were missing is only partly true here. Lentils (GVH) and dry beans (KSH) price bableves and lencse dishes, and frozen zöldborsó (GVH) makes zöldborsófőzelék possible. Zöldbabfőzelék, chickpeas and canned beans are not covered. COMPUTED/VERIFIED.

## 5. The 4-week, 3-meals-a-day plan for 2 adults (task 3)

Method: `scripts/plan.py`. Every non-dessert OKOSTÁNYÉR dish is converted to GVH/KSH/pantry-only ingredients using an explicit swap table and then graded. **L0** = as published. **L1** = herb or condiment left out (mustard, mayonnaise, balsamic and stock assumed at home). **L2** = minor swap that keeps the dish's identity. **L3** = identity swap (the dish changes). **L4** = no substitute, dish dropped. A seeded random search then picks, for each week, 7 breakfasts, 7 lunch mains, 4 soups and 7 dinners, minimising repeats and checking the weekly rules. Each day is topped up with raw GVH vegetables (paradicsom, paprika) to reach 400 g and GVH fruit to reach 200 g per person. COMPUTED; swap choices are ESTIMATES.

**Dish grades (COMPUTED, `data/dish_priceability_levels.csv`):**

| Slot | L0 | L1 | L2 | L3 changed | L4 dropped |
|---|---|---|---|---|---|
| Breakfast (25) | 1 | 2 | 4 | 14 | 4 |
| Lunch main (24) | 2 | 4 | 1 | 17 | 0 |
| Soup (12) | 2 | 2 | 4 | 4 | 0 |
| Dinner (18) | 1 | 3 | 2 | 10 | 2 |

**Plan A, changed dishes allowed (L≤3):**
- Rules met in all 4 weeks. Red meat 0–275 g raw per person per week. Fish 1–2 meals a week. Legume meals 2–4 a week. 1 meat-free day a week.
- Vegetables from the dishes average 382–480 g per person per day. 11 of 28 days needed a raw-vegetable top-up, averaging 52 g a day.
- Variety: 20 different breakfasts, 23 lunch mains, 11 soups and 16 dinners. At most 3 repeats in 28 days.
- **The catch: 57 of 100 meal slots are changed dishes, 17 are L2, 17 are L1 and only 9 are as published.**
- **Cost: 69,738 Ft for 28 days for 2 adults, about 1,245 Ft per person per day** for used quantities at GVH median-of-chain-minimum prices. This excludes snacks, drinks, pantry and pack-size waste; the recipe-coverage stream found single-recipe purchases cost about 2.1× the used cost. KSH-priced share of cost: 8.6%. 27 of 100 meal slots use at least one KSH-priced ingredient. COMPUTED.

**Plan B, strict (L≤2):**
- Pools: 7 breakfasts, 7 lunch mains, 8 soups, 6 dinners.
- **There is no fish dish in the pool**, because every fish dish needs an identity swap of the fish or of its spinach or millet side. **The fish rule fails in all 4 weeks.**
- The menu effectively repeats weekly (breakfast and lunch up to 4×, dinner up to 5× in 28 days).
- The meat-free day was met in only 2 of 4 weeks by the search, although the pool does contain enough meat-free dishes. COMPUTED.

**Dishes dropped (no GVH/KSH substitute):** Granola meggyel és joghurttal; Padlizsánkrém; Sült padlizsán reggeli; Tonhalkrém reggeli; Szárnyas májpástétom; Sült padlizsán saláta. COMPUTED.

**Uncovered ingredients most often touched by swaps, by number of dishes:** fresh herbs 33, mustard 11, oats 10, salad leaves 8, celery 7, zucchini 6, beetroot 5, chickpeas 4, rocket 4, leek 4, prunes 4, then sweet potato, spinach, tortilla, red pepper, bulgur, couscous, millet, pumpkin, kohlrabi, Brussels sprouts, apricot, cherries, plums and others. COMPUTED.

**Nutritional side effects of the swaps (ESTIMATE):**
- Oats → rice and bulgur/millet → rice lower the wholegrain content. The daily wholegrain rule then depends on GVH wholemeal and rye bread, and on wholemeal pasta, which only 4 chains carry (11 SKUs; COMPUTED).
- Fruit variety shrinks to GVH's 6 fruits: Idared apple, pear, strawberry (4 SKUs, 3 chains), banana, lemon, orange.
- Nuts reduce to walnuts (KSH) and peanuts (GVH).

## 6. Data-quality findings relevant to pricing (new; COMPUTED unless noted)

1. **Mixed units inside leaves.** 21 of 120 food leaves contain SKUs priced per piece next to SKUs priced per kg or l. Examples: fokhagyma "200 g / 3 db" at 103 Ft per head, shown as the lowest unit price next to Ft/kg SKUs; zöldpaprika 5-pack at 88 Ft per piece; banana 5-pack at 99.8 Ft per banana; zsemle per piece; tea per bag. A naive "cheapest unit price" across a leaf is wrong. The app must normalise by `product.unit` and know piece weights.
2. **Off-scope SKUs inside leaves.** These contradict the decree's own definitions (VERIFIED decree text): Greek yoghurt in "Natúr joghurt" (Annex 1 row 9 says "nem görög"); fruit teas in "Tea" (row 101: green tea and earl grey only); instant coffee capsules in "Őrölt kávé"; basmati rice (Rossmann) in "Rizs" (row 94: white "B" rice, 1 kg).
3. **Decree scopes are narrow**, from Annex 1 of 11/2023 GFM rendelet (VERIFIED https://njt.jog.gov.hu/jogszabaly/2023-11-20-8P, time state 2025-05-31):
   - Alma: "lédig, Idared" only.
   - Paradicsom: "fürtös" only.
   - Uborka: kígyóuborka priced per piece.
   - Burgonya: "piros".
   - Finomliszt: BL-55 only, so no wholemeal flour.
   - Száraztészta: spaghetti, macaroni, penne, fusilli, 2- and 4-egg and durum only.
   - Rizs: white "B", 1 kg.
   - Lencse: 500 g.
   - **Tengeri halfilé: "friss, hűtött és fagyasztott lazac és tőkehal".** So **salmon is covered**. This corrects the "already established" list, as the recipe-coverage stream also found.
   - Fagyasztott zöldség: zöldborsó, brokkoli and hasábburgonya only.
   - Hüvelyes: lencse only.
   - Fruit: alma, körte, földieper, banán, citrom, narancs.

## 7. Residual high-cost ingredients: secondary sources and legal status (task 4)

KSH rows are VERIFIED from ara0044 (2026-09 values). Shop catalogue presence was COMPUTED by counting product-URL slug matches in sitemaps downloaded on 2026-10-12 by the alt-price-sources stream (Groby: 7,883 product URLs; Auchan: 53,034 product URLs, food and non-food). The counts include flavoured or derived products, so read them as presence only.

| Residual | Cost share in OKOS non-dessert sample | GVH | KSH ara0044 row | Groby slugs | Auchan slugs |
|---|---|---|---|---|---|
| Spinach (fresh/frozen) | 2.9% (4 recipes) | no | **no** | 13 | 22 |
| Zucchini | 2.5% (6) | no | **no** | 6 | 6 |
| Chickpeas / canned beans | 0.9% (6) | no (chickpea only as GF flour or pasta) | **dry beans only: 14601 Szárazbab 1,540 Ft/kg**; no chickpea or canned-bean row | chickpea 14; beans 45 | 26; 69 |
| Oats | 0.7% (10 recipes, the most frequent) | no (GF oat flour only) | **no** | 10 | 11 |
| Canned tomato / passata / paste | 0.3% (3) | no | **no** | 33 | 46 |
| Tuna (canned or fresh) | 5.1% (2) | no | **no** | 42 | 54 |
| Sweet potato | 0.4% (2) | no (baby food only) | **no** | 0 | 9 |
| Red / bell pepper (kaliforniai, kápia) | 1.0% (4) | no (zöldpaprika only) | **no** (14108 is zöldpaprika) | 5 | 8 |
| Mushrooms | 2.4% (5) | no | **yes: 14111 Gomba 1,900 Ft/kg** | 25 | 53 |
| *Also important:* fresh herbs | 3.4% (29 recipes) | no | no | 34 | 49 |
| salad leaves and rocket | 3.2% (12) | no | no | – | – |
| walnuts | 1.7% | no | **yes: 14701 Dió 6,180 Ft/kg** | – | – |
| honey | 1.3% | no | **yes: 13910 Akácméz 5,970 Ft/kg** | – | – |

**Legal status of the secondary sources:**

- **KSH ara0044.** CC BY 4.0, commercial use allowed with attribution (VERIFIED https://www.ksh.hu/copyright). Monthly national average only, no store or location dimension. Usable now for mushrooms, dry beans, walnuts, honey, jam and watermelon, labelled "KSH országos átlagár".
- **auchan.hu.** robots.txt is permissive (VERIFIED https://auchan.hu/robots.txt). The Felhasználási feltételek say: "kizárólag személyes, nem kereskedelmi célú tanulmányozását és letöltését engedélyezi … előzetes írásbeli engedélye nélkül tilos a weboldal egészét, vagy részeit bármilyen formában sokszorosítani, másolni, újraközölni" (VERIFIED https://auchan.hu/felhasznalasi-feltetelek). **Needs written permission.** It carries all 9 residuals.
- **groby.hu.** robots.txt is permissive. The ÁSZF (last modified 2019-07-09) has **no anti-scraping, IP or reuse clause** (keyword search, VERIFIED https://www.groby.hu/cikk/aszf). The general law still applies: database sui generis right (CJEU C-762/19, harm to investment) and copyright in photos and texts. **Lowest contractual friction, but Budapest-only online delivery.** It is not a "store near me" price. It lacks sweet potato. A partnership is the clean route (ESTIMATE).
- **shop.aldi.hu (Roksh).** The page title is "ROKSH élelmiszer házhozszállítás" and its meta description presents Roksh as "egy árösszehasonlító oldal" (VERIFIED page source). robots.txt names only Googlebot. **Terms not readable without JavaScript, so not checked; unknown.** aldi.hu's own Felhasználási feltételek (for ALDI account services) say "nem használhatják az ALDI szolgáltatásokat és az azok révén hozzáférhető adatokat kereskedelmi vagy üzleti célokra" (VERIFIED https://www.aldi.hu/customer-services/felhasznalasi-feltetelek). Treat it as **partnership-only** (ESTIMATE). Roksh is also a potential competitor.
- **Penny on foodora.** The foodora ÁSZF v2.7, in force from 2026-02-03, section 12.1 says any use of platform content needs the provider's "előzetes írásbeli engedélyével" (prior written permission) (VERIFIED: the current ÁSZF PDF linked from https://www.foodora.hu/contents/terms-and-conditions). **Contractually off-limits without permission.** Penny is still on foodora: penny.hu jogi nyilatkozat mentions ordering via foodora.hu and says availability varies by area (VERIFIED). penny.hu's own `/products` pages list only the leaflet and promo range (695 products, dated promo prices), so they are not a regular-price source (COMPUTED from the sitemap and one product page).

## 8. How GVH adds categories, and whether there is a request channel (task 5)

- **2023-07-01: 62 categories, 6 chains, about 1,200 stores.** VERIFIED from GVH press of 2024-06-28: https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2024-es-sajtokozlemenyek/hetfon-lesz-egy-eves-az-online-arfigyelo.
- **2023-12-30 announcement: +16 categories (lactose-free, gluten-free and beef) → 78 categories, more than 1,300 products, from mid-January 2024.** These came by "**74/2023. (XII. 29.) GFM rendelet**", in force on the 15th day after promulgation. VERIFIED https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2023-as-sajtokozlemenyek/uj-ev-ujabb-termekkategoriakkal-bovul-az-online-arfigyelo.
- **Current list: 140 categories.** The Annex 1 table has rows 3–142, COMPUTED by parsing njt. The text was **set by 15/2025. (V. 23.) NGM rendelet, in force 2025-05-31**; the njt footnote says "Az 1. melléklet a 15/2025. (V. 23.) NGM rendelet 2. §-ával megállapított szöveg" (VERIFIED njt). By row order, food categories up to about row 111 were added between 2024 and 2025 (cream, fruit yoghurt, minced meat, fish, rice, lentils, broccoli, peanuts, coffee, tea, cocoa, cheese types, olive oil). Rows 112–142 are baby food, household and hygiene. ESTIMATE from row order, because the intermediate amending decrees were not identified.
- **GVH press of 2026-03-10:** "eredetileg 62 … ma már 140 termékkategória … több mint 5000 … 1817 üzletében", and the system is "folyamatos fejlesztés és bővítés alatt" (still being developed and extended). VERIFIED https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2026-os-sajtokozlemenyek/gvh-az-arfigyelo-is-kordaban-tartja-az-elelmiszerarakat.
- **GVH API: 161 leaves (120 food).** GVH splits legal categories further, e.g. trappista into block, cut and sliced; Kemény/Félkemény/Lágy sajt into Emmental, Cheddar, Gouda, Edam, Camembert, Brie, Feta and Mozzarella; olive oil into 2; kakaópor into 2; coffee into ground and beans. COMPUTED.
- **Mechanism.** Categories are set by the minister by decree. That was 163/2023 Korm. rendelet §19 originally, and now Act L of 2025 §72 per the legal stream. The decree preamble names the minister acting "az agrárminiszterrel egyetértésben" (in agreement with the agriculture minister) (VERIFIED njt). GVH runs the system but does not choose the categories. **No public form or process for requesting new categories was found** on gvh.hu or arfigyelo.gvh.hu (checked the press index pages for 2023–2026 and the decree). The only routes are lobbying the Nemzetgazdasági Minisztérium (NGM), commenting in public consultation on a future amending decree, or writing to GVH (ugyfelszolgalat@gvh.hu), which originally proposed the system. INFERENCE. The timing and outcome cannot be planned; the 2025 expansion went to non-food. **Do not build the MVP on future GVH categories.**

## 9. Implications for MVP scope (ESTIMATE / recommendation)

1. **"GVH-native healthy plan" is feasible now.** Write your own OKOSTÁNYÉR-principle recipes using GVH food leaves, KSH-labelled extras (mushrooms, dry beans, walnuts, honey) and pantry. Aim for at least 90% GVH cost coverage per recipe and show "nincs ár" for herbs and extras. Expect a Hungarian-traditional flavour: főzelékek with zöldborsó, lencse, bab and kelkáposzta; lecsó, rakott dishes, soups, chicken, turkey, salmon, cod, catfish, carp, tejberizs. Modern bowls, oats, chickpeas and Mediterranean vegetables will be thin.
2. **Store-level pricing of a modern healthy library needs a partner feed.** The top 20 missing items would lift cost coverage to about 88%. Roksh (Aldi, multi-retailer) and Auchan (written permission needed) are the candidates. Groby is the low-friction but Budapest-only, online-only fallback.
3. **License recipes or the brand from MDOSZ** if OKOSTÁNYÉR credibility matters. Otherwise only apply the public principles and write your own recipes. CC BY-SA Wikibooks recipes are legally reusable but share-alike.
4. **Engineering must normalise GVH units** (piece vs kg) and filter off-scope SKUs before any "cheapest" claim (§6).

## 10. Files (all under this folder)

| File | Content |
|---|---|
| `data/coverage_by_group.csv`, `data/coverage_summary.json` | headline coverage tables |
| `data/recipe_coverage.csv` | per recipe: lines by class, cost per serving by class, fully-priceable flags, URL |
| `data/line_mapping.csv` | per line: canonical key, class, grams per serving, cost, price basis (no recipe text) |
| `data/ingredient_reference_prices.csv` | per canonical ingredient: class, price, basis, GVH SKUs and chains, KSH row |
| `data/residual_ranking_okos.csv` | uncovered and substitute items ranked by cost share |
| `data/dish_priceability_levels.csv` | L0–L4 grade and changes for every non-dessert OKOSTÁNYÉR dish |
| `data/plan_28d.csv`, `data/plan_summary.json` | Plan A (changed dishes allowed) |
| `data/plan_28d_maxlevel2.csv`, `data/plan_summary_maxlevel2.json` | Plan B (strict) |
| `data/ksh_ara0044_latest.csv` | KSH 2026-09 values for all 175 items |
| `data/penny_lines.csv` | Penny sample lines: canonical key and grams only |
| `dl_gvh/` | GVH categories and 120 leaf JSONs (untrusted raw data) |
| `dl_ksh/`, `dl_tos/`, `dl_robots/` | KSH table, terms pages and robots files (raw) |
| `scripts/` | ontology.py, recipes_okos.py, penny_map.py, penny_sample.py, dl_gvh_leaves.py, compute.py, plan.py, parse_okos.py, gvh_grep.py, pdftext.py |

Raw recipe HTML, recipe PDFs and the Penny JSON-LD sample were deleted after parsing, so no recipe text is stored.
