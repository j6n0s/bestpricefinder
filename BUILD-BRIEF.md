# Build brief: healthy weekly meal planner with local grocery prices (Budapest)

**For:** the coding agent or session that will build this, and the founder.
**Status:** research finished 2026-10-12/13. Everything below is grounded in the research files under [`research/`](research/). Section 12 indexes them.
**Read first:** sections 1 (what to build), 4 (data API and traps) and 8 (legal guardrails). They are non-negotiable.

---

## 0. The idea in one paragraph

A phone-first app for a Budapest household that:
1. plans healthy meals week by week for the rest of the month;
2. shows a simple price comparison of each recipe's ingredients across grocery chains;
3. offers basic healthy recipes;
4. uses the phone's location to show what the week costs at the user's nearby stores.

The goal is to **put it into real use quickly**: the founder first, then a small beta.

## 1. What to build (and what not to): decisions from the research

**Competitive reality (verified 2026-10-12).** The generic "weekly meal plan + chain prices" app already exists in Budapest:
- **NomNom: Budget Meal Planner** (Z Gen Kibernetika Kft). Launched 2026-07-23. Built on GVH Árfigyelő and store prices; dinners only (36 recipes); no location. 703 HU ratings; #1 Top Grossing in HU Food & Drink. 1,490 Ft/month or 7,990 Ft/year.
- **Lefőzlek** (iOS, 2026-10-01). Recipes, weekly plan and price per portion.
- **Kifli Séf**. About 3,400 recipes priced for Kifli only, with add-to-cart.
- **Price-only tools**: Árnéni (web), Cashmap, and GVH's own site.

**Therefore the product's angle is (build towards this):**
- **Health-first, whole-day planning.** Optional 5 Hungarian meal slots: reggeli, tízórai, ebéd, uzsonna, vacsora. Not dinners only. App reviews explicitly ask for breakfast and snacks, and complain about AI-written, repetitive recipes.
- **Human-tested Hungarian recipes designed around what GVH can price.** See section 5. This is both a quality differentiator and a data necessity.
- **Month-aware planning.** Plan several weeks ahead, reuse leftovers, and size packs across the week. Buying single-recipe packs costs about 2.1× the used ingredients; grouping meals into weeks cut perishables by about 21%.
- **Location as "where does MY week cost least, among the stores near me, and can I actually buy it there".** Not micro store-level price arbitrage (explained in section 3).

**Non-goals for the MVP:**
- Multi-store route optimisation. Cherry-picking adds only about 4–5% within 2 km and costs time.
- Leaflet/flyer image extraction.
- Scraping any retailer site.
- Receipt crowdsourcing (NAV e-receipts are not viable before about 2028).
- Nutri-Score.
- Disease-specific diets.
- Product images.

**The riskiest assumption is not technical.** It is whether people will choose and pay roughly 1,000–1,500 Ft/month for this over NomNom and free options. Building for the founder's own use is cheap and fine. Before a public launch, the founder should run the fake-door test described in `research/gap-demand-wtp-evidence/notes_demand_wtp.md`. **Do not block the personal-use build on it.**

## 2. MVP milestones

| Milestone | Scope | Done when |
|---|---|---|
| **M0: personal use** (target 1–2 weeks) | Daily GVH ingest into a DB with history. About 30–40 GVH-native recipes. Pick meals for a week → aggregated shopping list → cost of that list at each nearby store (radius chosen by the user, default 1.5 km) → pick a store → list grouped by category. Works on the founder's phone as an installable PWA. | The founder plans and shops one real week with it. Prices shown match the GVH site for the chosen stores on that day. |
| **M1: friends beta** | Rule-based planner: legumes ≥1×/week, fish ≥1×/week, one meat-free day, red-meat cap, variety/no-repeat window, optional 5 slots. Pack-size and leftover optimisation across the week. Per-serving nutrition. "nincs ár" plus KSH fallback. Pantry ("probably at home") list. Price-history sparkline from own archive. Grows to about 100 recipes. | 5–10 testers use it for 4 weeks; the weekly plan + list flow takes under 5 minutes. |
| **M2: public** | All legal guardrails in section 8. Impresszum, privacy policy, consent flows. Per-store availability. Tesco/Spar store-level prices. Monitoring. Optionally a native wrapper (Expo/Capacitor) after the Apple 5.2.2 authorisation pack exists. | The founder has filed the GVH re-use request, and the go/no-go from the fake-door test is positive. |

## 3. What the data says (numbers the product logic relies on)

**Coverage.** GVH Árfigyelő covers 6 grocery chains (Aldi, Auchan, Lidl, Penny, Spar, Tesco) and 3 drugstores (dm, Rossmann, Müller).
- Food: 120 leaf categories, 4,332 SKUs. All categories: 161 leaves, 16,040 SKUs.
- 1,829 stores, all with GPS. 419 are in Budapest; 282 of those are grocery stores (Spar 114, Aldi 48, Lidl 46, Tesco 39, Penny 30, Auchan 5).
- Not covered: CBA, Coop, Príma, Reál, Spar partner stores, Kifli, Metro.

**Location effect.** Price differences come mainly from which chains are near you.
- Aldi and Penny charge one national price, and Lidl nearly so.
- Store-level price differences exist mainly at **Tesco** (about 40% of food items vary; Budapest Expressz stores run about +3.5%) and **Spar** (promotions in some stores only, plus assortment).
- Small Spar and Tesco formats lack many products. Only about 25–29% of their food items are in at least 80% of their stores, against 87–100% for Aldi, Lidl and Penny. **Per-store availability matters as much as price.**
- At 4 of 5 Budapest test points, the nearest grocery store is a Spar whose basket costs **21–27% more** than a Lidl within 1 km. That gap is the user-visible win.

**Basket economics (healthy week, 2 adults, 25 items).**
- Best single chain is about 13.5k Ft (Lidl); priciest is about +22–25% (Tesco).
- Cherry-picking across all chains saves 5–10% versus the best single chain.
- Realistic household saving is about 3–8k Ft/month: store choice plus cheaper equivalent products plus less waste.
- Picking a cheaper equivalent product *within* the chosen store is worth more than switching chains. Build a "cheaper swap" suggestion.

**Stability** (fact-checked on 2026-10-13).
- Lidl was the cheapest chain for a 20-item core basket on all 8 sampled dates since 2025-03-07. The lead is thin: 3.8% (391 Ft) on 2026-10-13, and a single banana price change moved it by 2 points. Never hard-code a "cheapest chain".
- Between 1.2% and 2.6% of food product×chain prices change per day (3 observed days), and 13–19% per week. Most chains start promotions on Thursday or Monday, but Penny and Tesco also change prices on other weekdays.
- **Ties are common.** 8–9 of the 20 core items are exact cross-chain ties on a given day; for example, own-label carrots cost 489 Ft at Aldi, Lidl and Spar. Any "cheapest chain for this item" logic must be **tie-aware**: show all tied chains and never break ties alphabetically. Counting ties properly, 12–16 of 20 items keep their cheapest chain week to week. Recompute weekly lists from fresh data.

**Promotions** (fact-checked on 2026-10-13).
- Every priced food promotion inside GVH's categories at Penny, Lidl and Aldi in the week of 2026-10-08 (26 of 26, the whole population) appeared in GVH at the promo price. It applied chain-wide and in every Budapest store tested.
  - Day-one capture is proven for Monday-start offers (13/13). Thursday-start offers were only observed from day 4 onwards; confirm them with your own Thursday snapshots.
  - Penny and Lidl report `DISCOUNTED` = promo price and `NORMAL` = pre-promo price.
  - **Aldi never uses `DISCOUNTED`**: 0 of 420 Aldi food entries. Its promos appear only as a lower `NORMAL`.
  - Penny card prices appear as `LOYALTY`.
- **`DISCOUNTED` ≠ "weekly deal".** It also flags long-running reductions that are not in any leaflet, and GVH even carries promos the chain's own site doesn't list. A "deal" badge must come from **our own daily archive** (price below the recent typical price), not from the flag.
- Missing from GVH:
  - Lidl Plus app prices: 0 of 385 Lidl food entries have `LOYALTY`. Lidl describes these as automatically applied card prices, so this looks like a reporting gap, not a legal exclusion.
  - Coupon and multi-buy prices (excluded by law, §57(1) bc).
  - Items sold for at most 1 month (exempt, §66(5)), e.g. "Csak most!" items.
  - Anything outside GVH categories. Only about 5–26% of a chain's weekly offers fall in GVH at all.
- **No leaflet data needed for the MVP.**

**Recipe priceability (the hardest constraint).** GVH prices a recipe's *cost* only partly:
- About 87–90% for traditional Hungarian dishes built on chicken, pork, eggs, dairy, potato, cabbage, carrots, rice or pasta.
- About 37–47% for "modern healthy" recipes.
- About 47–59% for real OKOSTÁNYÉR recipes. Breakfasts are worst: 0 of 25 fully priceable.
- Missing in GVH:
  - oats, chickpeas and beans (dry beans, sárgaborsó);
  - spinach, zucchini (főzőtök), mushrooms, sweet potato, red bell pepper, eggplant, zöldbab;
  - canned tomatoes or passata, savanyú káposzta;
  - nuts and seeds other than peanuts, mák, tuna;
  - fresh herbs, spices (incl. pirospaprika!), salad leaves, berries, tortillas.
- Present but easy to miss: **salmon is inside "Tengeri halfilé"** (mixed with pollock); **Greek yoghurt is inside "Natúr joghurt"**.

## 4. Data sources: exact usage and traps

### 4.1 GVH Árfigyelő (primary; public by statute, Act L of 2025 §70)

Base: `https://arfigyelo.gvh.hu/api`. The API is undocumented; it was reverse-engineered from the site's JS bundle `/assets/index-*.js`.

| Endpoint | Use |
|---|---|
| `GET /categories` | Tree: 9 top / 42 level-2 / 161 leaf. Nodes `{id,name,path,categoryNodes}`. Food = top categories "Tejtermék, sajt, tojás", "Hús, hal, felvágott", "Zöldség, gyümölcs", "Pékáru", "Tartós élelmiszerek, italok", "Speciális étrend". |
| `GET /chain-stores` | 9 chains `{uuid,name,imageUrl}`. |
| `GET /shops` | 1,829 stores `{uuid,postalCode,city,address,chainStoreUuid,location{latitude,longitude},openingTime}`. |
| `GET /products-by-category/{leafOrL2Id}?limit=48&offset=N[&shopIds=a,b]` | `{products,count}`. **Default page size is 12. Always pass `limit=48` (server max) and loop offset by 48 until `count`.** With `shopIds`, it returns only products those stores carry, at their store prices. |
| `GET /product/{id}` | Detail for **all** chains: per chain `prices` (min per type), `pricesMax`, `priceSameEverywhere` (literal), **`availableInShops`** (store uuids carrying it). |
| `GET /product/{id}/shop/{uuid1,uuid2,…}` | **Real per-store prices** `{shops:[{shopUuid,prices:[{type,amount,unitAmount}]}]}`. Up to 200 ids per call works. Returns `PRODUCT-SHOP-PRICES-NOT-FOUND` where the product isn't sold. |
| `GET /search?q=…` | Fuzzy and accent-insensitive, minimum 3 characters. **Not usable for ingredient matching**: oats, spinach, chickpeas and passata return baby food or soap. Use the ontology (section 5). |

Official daily bulk file: `https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx`.
- About 2.1 MB; regenerated about 02:00 UTC daily.
- One row per product×chain (about 25,400 rows).
- Columns include product id, name, category id and name, chain, unit, packaging, min/max price, min/max unit price, number of chains, number of stores carrying the product, and the chain's store count.
- Daily price includes DISCOUNTED and excludes LOYALTY. No per-store prices.

Product objects carry: `id, name, imageUrl, unit, unitTitle, bulk, packaging, categoryPath, minUnitPrice, pricesOfChainStores[{id,name,priceSameEverywhere,productMinAmount,prices[{type: NORMAL|DISCOUNTED|LOYALTY, amount, unitAmount, sameAmountEverywhere}]}]`.

**Traps. Each one has bitten the research; write tests for them.** Items 4, 10, 12 and 13 were refined by the 2026-10-13 fact-check in `research/gap-gvh-promo-and-stability/verify.md`.
1. **Which price is "the chain price".**
   - `prices[].amount` in the listing is the **cheapest single store's** price; it may come from 1–2 stores. Example: Spar spaghetti listed at 294 Ft while 296 stores charge 699.
   - **`productMinAmount`** is the daily price charged by **≥80% of the chain's carrying stores**. It is what GVH's site displays.
   - Use `productMinAmount` for "typical chain price" and the per-store endpoint for "your store".
2. **The listing shows at most 3 chains per product.** For completeness use `/product/{id}` or the XLSX.
3. The listing's `priceSameEverywhere` follows the 80% rule; the detail flag is literal. Don't treat either as proof that every store is identical.
4. **The XLSX CDN serves stale copies.** The plain URL returned files 6–30+ hours old, varying by `Accept-Encoding`, despite `max-age=3600`.
   - Always add a unique cache-busting query (`?v=<date+run id>`).
   - Verify the sheet name `Napi feltöltések - YYYY-MM-DD` equals today; otherwise retry later and never ingest it as today.
   - Numbers are text with a decimal comma.
   - **The XLSX excludes `LOYALTY` prices**, and so does `productMinAmount`. Card prices exist only in the listing's `prices[]` (`type: LOYALTY`) and the per-store endpoint. A pipeline that reads only the XLSX misses them.
5. **Units are mixed.** 21 of 120 food leaves mix per-piece (`db`) and per-kg/l products, and 55% of fresh SKUs are sold by weight. Normalise with explicit per-piece weight assumptions per ingredient (e.g. 1 db kígyóuborka ≈ 0.4 kg; 1 fej fokhagyma ≈ 0.05 kg). Unit-price rows are inconsistent in 0.5% of cases (`unitAmount ≠ amount/packaging`); recompute and validate.
6. **Mis-filed and off-scope SKUs.** Examples: trappista inside "Natúr joghurt"; non-extra-virgin "olívaolaj" in the extra-virgin leaf; breaded fish in fish fillets; salmon and pollock in one leaf. Apply include/exclude name rules per ingredient.
7. **Product ids are mixed**: EAN-13 (about 70% of food SKUs), in-store weight codes starting with `2`, chain-internal ids (`lidl-0080000`, `aldi-320458`, `penny-108`). 84% of food SKUs are sold by only one chain, so **compare by ingredient/category, not by barcode.**
8. **Stores.**
   - About 19 Budapest grocery stores have no price data (17 Spar incl. Árkád Örs, 2 Tesco). Flag or hide them.
   - Opening hours exist only for Lidl.
   - There is no store name or format field. Tesco `tesco-1xxx` = hyper/large, `tesco-4xxx` = Expressz.
   - One coordinate is wrong: Rossmann Zalaegerszeg is about 111 km off.
9. **No history.** The law archives prices the day after they change, and archives are closed to the public. **Snapshot daily from day one (append-only).** That archive becomes your price history and an asset.
10. **Timing** (measured 2026-10-11 to 13).
    - Retailers upload day-D prices by the end of D-1 (§66(1)).
    - The **API switches at about 00:00 UTC**, which is 02:00 Budapest time in summer and 01:00 in winter, not at Budapest midnight. Until then it still serves the previous day.
    - The XLSX is regenerated at 02:00:12 UTC (04:00 Budapest time in summer).
    - **Run the ingest at about 04:30 Budapest time**, log the data date, and check that the API and the XLSX agree on it.
11. **No gzip, no ETag, no observed rate limit.**
    - Be polite anyway: ≤1–1.5 req/s.
    - Use a descriptive User-Agent with a contact address for the app.
    - Cache aggressively.
    - Fail loudly on schema changes, because the API is undocumented and can change.
12. **Promo semantics** (section 3):
    - Aldi promos look like `NORMAL` drops.
    - `DISCOUNTED` also marks long-running reductions.
    - Lidl Plus prices are absent.
    - Derive "deal" from our own archive.
13. **Ties.** Many items cost exactly the same at several chains. Ranking and "cheapest" logic must keep ties (sort by price, then *group*). Never use the chain name as a tie-breaker.

**Recommended daily ingest (about 1–1.7k requests, about 15 MB):**
- XLSX (1 request).
- Food listing for the 120 food leaves with `limit=48`: about 159 requests. This adds `productMinAmount` and LOYALTY.
- `/product/{id}/shop/{Budapest store uuids}` **only for pairs where the XLSX min < max**: about 600 pairs, mostly Tesco and Spar.
- Weekly: `/product/{id}` for all food SKUs (about 4.3k calls) to refresh `availableInShops`.
- For M0 you may restrict per-store work to Budapest and to ingredients used by your recipes.

### 4.2 Fallbacks and gaps (allowed)
- **KSH STADAT ara0044**: monthly national average prices, 175 items, about 86 food (mushrooms, dry beans, walnuts, honey, ground paprika…). <https://www.ksh.hu/stadat_files/ara/hu/ara0044.html>, CC BY 4.0; attribution "Forrás: KSH" with a link is mandatory. Show it as **"becsült országos átlagár (KSH)"**, never as a store price. The file is ISO-8859-2 encoded.
- **"nincs ár" badge** for everything else, plus a **pantry / "valószínűleg otthon van"** list for spices, salt, oil and similar.
- Chains' own weekly offer pages (Penny sitemap with validity dates; Lidl offer pages with `data-grid-data` JSON; Aldi "szuper-akciok-mindennap") may be **deep-linked**. Do not extract leaflet images.

### 4.3 Forbidden sources (terms ban it, or bot protection would have to be bypassed)
- Kifli.hu: ÁSZF §3(c) bans automated or manual copying without written permission.
- Wolt (SPAR/Auchan/Tesco/Wolt Market): ÁSZF §12.7–12.8.
- foodora: §12.1.
- Auchan online: personal, non-commercial use only.
- Tesco online and spar.hu: Akamai 403s. Bypassing them risks Btk. 423.
- Bought scraped datasets (Apify/Bright Data Tesco actor).

Partnerships for later, done by the founder: Kifli/Rohlik (basket hand-off; affiliate €5 per new customer), Roksh (runs shop.aldi.hu), Groby.

### 4.4 Nutrition data
- Per-ingredient composition from **CIQUAL 2025** (Etalab 2.0 open licence, 3,484 foods) as the primary source; **Frida 5.5** (CC BY 4.0) and **USDA FoodData Central** (CC0) as fallbacks.
- No open Hungarian table exists.
- **Do not build on Open Food Facts.** About 50% barcode hit rate and about 28% with full nutrition; ODbL share-alike risk.

## 5. Recipes and the ingredient ontology

**Recipes must be original.**
- Every HU recipe site (Nosalty, Mindmegette, Street Kitchen, Sobors, Receptneked, Index) reserves reuse in its terms, and several opt out of text and data mining. Don't scrape or copy them.
- Ingredient lists and cooking methods are not copyrightable; instruction text and photos are.
- Write your own text: LLM-assisted drafting is fine, but each recipe must be cook-tested by a human before "published".
- **OKOSTÁNYÉR® is an MDOSZ trademark and its recipes are MDOSZ copyright.** Use only its public weekly *principles* as planner rules; don't use the name, logo or recipes without an MDOSZ licence.
- `research/gap-healthy-plan-priceability/data/` contains statistics derived from MDOSZ and Penny recipes. **Use those for analysis only; never ship their content.**

**Design rule: GVH-native recipes.** Each recipe should have **≥90% of its ingredient cost in GVH-priced ingredients**. The rest comes from KSH-labelled items or pantry items. Lean on the covered ingredients:
- chicken (mell/comb/egész), pulyka, pork cuts, darált marha/sertés, harcsa/ponty/tengeri halfilé (incl. salmon);
- eggs, túró, joghurt, tejföl, kefir, cheeses, milk;
- lencse, rice, pasta, wholemeal/rye bread, flour, oils;
- tomato, green pepper, carrot, parsley root, cucumber, onion, garlic, potato, cabbage, kelkáposzta, cauliflower, broccoli, frozen peas/broccoli;
- apple, pear, strawberry, banana, lemon, orange.

Breakfast templates should use bread, túró, joghurt, kefir, eggs, cheese, vegetables and fruit. Oats are not priceable yet. Size the library at about 30–40 recipes for M0 and 100–150 for M1; the range depends on two-day cooking and 5-slot planning.

**Ingredient ontology (core data structure).** Map each canonical ingredient (e.g. `csirkemellfilé`, `vöröshagyma`, `natúr joghurt`) to:
- one or more GVH leaf ids;
- `unit` (kg / l / db) and a per-piece weight where needed;
- name include and exclude regexes (e.g. exclude "panírozott", "füstölt"; for extra-virgin olive oil require "extra szűz");
- an optional quality tier (e.g. "S/M ketreces" vs "szabadtartású");
- fallback: a KSH row id, or pantry.

Starter mappings: `research/recipe-coverage/out/ingredient_mapping.csv`, `research/recipe-coverage/out/gvh_leaf_categories.csv`, `research/gap-gvh-promo-and-stability/data/leaf_categories.csv`. The 24 agent-written recipes in `research/recipe-coverage/out/recipes.csv` are our own and may seed the library, but must be cook-tested first.

## 6. Core algorithms

1. **Price an ingredient at a store.**
   - Candidates: SKUs in the mapped leaves → filter by the name rules → keep those available at the store (`availableInShops`, or the per-store endpoint/`shopIds` listing) → take the store's price (per-store if fetched, else `productMinAmount` if the chain is uniform).
   - Compute the unit price in the canonical unit.
   - Return both **"used cost"** (quantity × unit price) and **"checkout cost"**: whole packs, choosing the pack combination that minimises the till total for the week's *aggregated* quantity, not just the cheapest per kg.
2. **Weekly list.** Aggregate quantities across the week's recipes per canonical ingredient, subtract pantry and leftovers, then price.
3. **Nearby store ranking.**
   - The client gets the store list (about 52 KB compressed) and computes distances **on the device**.
   - For the N nearest stores per chain within the radius, compute: checkout cost of the week, number of items unavailable or unpriced, and data date.
   - Rank by cost with availability penalties.
   - Offer an optional "split between 2 stores" saving only if it is above a threshold, e.g. ≥1,500 Ft/week.
4. **Cheaper-swap suggestions** within the chosen store: same ingredient, lower unit price, acceptable tier.
5. **Planner (M1).** Constraint-based selection over the recipe library:
   - Weekly rules: legumes ≥1, fish ≥1, one meat-free day, red meat ≤ cap, potatoes not every day, sweets ≤2.
   - Slots: 3 or 5 per day.
   - No-repeat window; reuse perishables across days.
   - Optional weekly budget; prefer seasonal items.
   - Recompute prices weekly (the item-level cheapest chain changes often).
6. **Nutrition per serving** from composition tables. Show factual numbers and guideline-based tags such as "hüvelyes", "hal", "húsmentes" and "rost" thresholds, never health claims.

## 7. Suggested architecture (a default; change it if you have a reason)

- **`ingest/`**: Python 3.12 daily job at about 04:30 Europe/Budapest. Steps: XLSX (cache-busted, date-checked), then the listing, then per-store calls for varying pairs. Data goes to an **append-only** table. Idempotent per data date, with schema validation (pydantic) and alerting on failures or schema drift. Store raw responses compressed for 30 days for debugging.
- **DB**: Postgres (e.g. Supabase) or SQLite for M0. Tables:
  - `chains`, `stores`, `categories`, `products`;
  - `price_obs(date, product_id, chain_id, store_id NULL, type, amount, unit_amount, product_min_amount)`;
  - `availability(date, product_id, store_id)`;
  - `ingredients`, `ingredient_map`;
  - `recipes`, `recipe_lines`;
  - `plans`, `plan_items`;
  - `ksh_prices`;
  - `composition` (nutrition).
- **API**: thin server (FastAPI or Next.js route handlers). It serves the store list, recipes, and prices for a list of store ids. **Never receive raw GPS coordinates.** The client sends selected store ids.
- **App**: installable **PWA** for M0/M1 (fast to put in use, browser geolocation, no app-store review), e.g. Next.js/React + TypeScript, mobile-first, Hungarian UI. Add a native wrapper only at M2.
- **Tests**:
  - fixture snapshots of API responses: unit normalisation, `productMinAmount` vs `prices[]`, pagination with `limit=48`, stale-XLSX detection, mixed units, name-rule filters, pack optimisation;
  - golden tests for 3 recipes × 3 stores.

## 8. Legal and product guardrails (must-haves; this is research, not legal advice)

1. **No impersonation of GVH.**
   - No "Árfigyelő" or "GVH" name, logo or lookalike UI in the app name, icon, metadata or store listing.
   - Show a disclaimer: "Nem hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal."
   - Context: in 2023 GVH took action against a lookalike app that used its branding and showed false prices.
2. **Attribution on every price:**
   - "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), [adat dátuma]";
   - KSH: "Forrás: KSH" with a link;
   - always show the data date.
3. **No product images from the GVH CDN, no retailer logos.** Images are retailer IP (ÁFF XIV.2). Use plain-text chain names.
4. **Formal permission (founder action).** The founder files a re-use request under **Act CI of 2023** via kozadatportal.hu → SZÜF (KAÜ login). The draft is ready in `research/gap-gvh-reuse-legal-route/request_draft_hu.txt`. The agent must **not** file anything. Before any App Store submission, prepare an Apple 5.2.2 authorisation pack.
5. **No scraping** of the sources in 4.3 and **no bot-protection circumvention**, ever.
6. **"Legolcsóbb" claims must be scoped and dated**: "a kiválasztott közeli boltok közül, a [dátum] GVH-adatok alapján". Distinguish chain-typical prices from store prices. Never present a national average as a local price.
7. **No health claims** (Reg. 1924/2006). Don't put "egészséges" next to products or affiliate links. Use factual nutrients and descriptive tags. No disease-specific plans (medical-device risk).
8. **Location.** Ask for foreground location only after explaining why. An approximate location is enough. Compute nearest stores on the device. Offer manual address or district entry as an alternative.
9. **Diet preferences and allergies are health data** (GDPR Art. 9). Keep them on-device in M0/M1. Server storage needs explicit consent plus a DPIA.
10. Before public release: impresszum (Ekertv. §4), privacy policy, cookie-less or consented analytics, and labelled affiliate links ("hirdetés / partnerlink").
11. **Platform risk.** The Árfigyelő depends on law and politics: there is a new government since May 2026, turmoil in GVH leadership, and the árrésstop margin cap may be phased out. Keep the data layer swappable, keep your own archive, and monitor the endpoints daily.

## 9. Open items for the founder (not for the coding agent)
- Try NomNom, Lefőzlek and Kifli Séf for a week and note what is missing for you. That is the cheapest product research.
- Run the fake-door test before public launch: 3 value propositions × 3 prices (990 / 1,490 / 1,990 Ft/month), about 1,800 Budapest visitors, about 150–430k Ft, 2 weeks.
- File the GVH re-use request (draft ready).
- Later: MDOSZ (OKOSTÁNYÉR licence and dietitian credibility), a dietitian review of recipes (about 2–3M Ft at consumer rates), and Kifli/Roksh partnerships.

## 10. Known numbers for sanity checks (snapshot 2026-10-12; they will drift)
- Budapest 25-item healthy weekly basket for 2, median store: Lidl 13,529; Aldi 14,797; Penny 15,446; Auchan 16,137; Spar 16,386; Tesco 16,855 Ft.
- Test points: Nyugati tér (47.5103, 19.0558), Móricz Zsigmond körtér (47.4774, 19.0470), Örs vezér tere (47.5030, 19.1365), Újpest-Központ (47.5603, 19.0906), Határ út (47.4658, 19.1262).
- Full food listing: 159 requests and 2.7 MB at limit=48. The API answers in about 0.4 s per call.

## 11. Corrections to earlier assumptions (so nobody repeats them)
- Salmon *is* covered (inside "Tengeri halfilé").
- The default page size is 12, not 48; 48 is the max with `limit=48`.
- Listing `prices[]` is not the 80% price; `productMinAmount` is.
- Act LXIII of 2012 was repealed on 2024-04-01; the re-use route is Act CI of 2023.
- The SPAR online shop no longer exists; it moved to Wolt in March 2025.
- "No Hungarian app combines recipes and prices" is false (NomNom, Lefőzlek, Kifli Séf).
- These corrections come from the 2026-10-13 fact-check:
  - The GVH API changes day at about 00:00 UTC, not at Budapest midnight.
  - About 1.2–2.6% of prices change per day, not a fixed 1.8%.
  - `DISCOUNTED` is not a weekly-deal flag, and Aldi never uses it.
  - Missing Lidl Plus prices are probably a reporting gap, not a legal exclusion.
  - The XLSX and `productMinAmount` exclude loyalty prices.
  - Per-item "cheapest chain" statistics must be tie-aware.

## 12. Research index (`research/`)
| Folder | What's inside |
|---|---|
| `gvh-location/` | API reverse-engineering, store stats, store-level price variation, baskets, location scenarios. `notes.md` + `verify.md`; data: `stores.csv`, `basket_*.csv`, `location_*.csv`, `store_price_variation.csv` |
| `gap-gvh-promo-and-stability/` | Promotion capture test, day/week stability, chain ranking over time, XLSX daily diff |
| `recipe-coverage/` | 24 recipes, ingredient→GVH mapping, recipe costs, missing-ingredient ranking, pack-size/week experiment |
| `gap-healthy-plan-priceability/` | Priceability of real healthy recipes by meal type, 28-day rule-compliant plan experiment, KSH prices |
| `alt-price-sources/` | Every alternative price source with terms-of-service quotes; source matrix; KSH table |
| `recipes-nutrition/` | Recipe licensing, OKOSTÁNYÉR/MDOSZ, nutrition tables, Open Food Facts coverage test |
| `legal/` + `gap-gvh-reuse-legal-route/` | Legal notes, risk matrix, Act CI 2023 route, **`request_draft_hu.txt`** |
| `competitors/` | NomNom, Lefőzlek, Árnéni, Cashmap, Kifli Séf, international analogs; app store metrics |
| `market-user/` + `gap-demand-wtp-evidence/` | Market size, savings estimates, willingness to pay, review coding, fake-door test design |

Every number in the notes is labelled VERIFIED (source URL), COMPUTED (method) or ESTIMATE. Each stream has an adversarial `verify.md`; prefer its corrections where they conflict with `notes.md`.
