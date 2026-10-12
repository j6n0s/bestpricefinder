# Adversarial fact-check of stream "market-user" (2026-10-12)

Labels: **VERIFIED** = re-opened the primary/secondary source today; **COMPUTED** = my own calculation on data I pulled today (method stated); **ESTIMATE** = reasoning.

What I re-did myself (I did not reuse the stream's downloads for any computation):
- I pulled **all 120 GVH food leaf categories** again (4,332 products) at 1 request/second. Files are in `verify_dl/gvh/food_2026-10-12/` and the log in `verify_dl/gvh/fetch_log.txt`. I also pulled `/api/shops` (1,829 stores, the same count the stream got) and `/api/chain-stores`, plus 4 calls to the store-level endpoint `/api/product/{id}/shop/{shopUuid}`.
- Scripts are in `verify_scripts/`: `fetch_all_food.py`, `flags.py`, `recheck_basket.py`. The output is in `verify_dl/recheck_output.txt`.
- I re-opened these pages: KSH jov0042, bel0005, ker2607 and far2609; the NomNom App Store page and the iTunes lookup API (HU and US); nomnomplanner.com; Index 2026-10-05, VG 2026-10-02, Pénzcentrum 2025-03-11 (the 30-product árrésstop list) and VG 2025-12 (the December extension); RevenueCat SOSA 2026; VIVnetworks' Kifli page; MediaFuture's Shopfully article; the Yazio HU App Store page; aldi.hu offer pages for 2026-10-08 and 2026-10-12.
- The page-size correction holds. With no limit, `products-by-category/18` returns 12 products (count 37), and `&limit=48` returns them all. VERIFIED today.

---

## Verdicts (8 load-bearing items)

### 1. Store-choice savings (27-staple basket, cheapest vs priciest chain, best-in-1-km) — PARTLY TRUE
- The arithmetic reproduces on my independent pull (COMPUTED, `recheck_basket.py`). I used household size 2.054 (1,651,512 / 804,044, KSH jov0042, VERIFIED). The stream's script used **2.1**, not the 2.05 it states, which inflates every Ft figure by about 2%.
  - Cheapest item incl. promo: Lidl 28,373 · Spar 29,310 · Aldi 29,721 · Auchan 30,483 · Tesco 32,233 · Penny 33,238. Gap **4,864 Ft (14.6%)**.
  - Median item: Lidl 35,277 … Spar 45,307. Gap **10,030 (22.1%)**.
  - Best chain within 1 km vs the average nearby chain: **1,731 (cheapest item) to 3,916 (median item)**. Within 2 km: 2.2k to 4.7k.
- **The result is fragile:**
  - **Bread alone is 1,971 Ft (≈40%) of the Lidl–Penny gap.** The comparison is a 400 g "Kemencés kedvencek" discount loaf at Lidl (159 Ft, 397.5 Ft/kg) against 1 kg sliced white bread at Penny (849 Ft/kg). These are not equivalent products, and Penny's cheapest loaf may simply be missing from GVH. Without bread and banana the gap is **2.4k**.
  - Using the **2nd-cheapest** item per chain and category, the gap shrinks to **3,141 Ft (8.7%)**.
  - Using the **25th-percentile** item, the ranking reorders: **Aldi is cheapest and Auchan priciest**, with a gap of 6,066 Ft.
  - Penny is "priciest" only under the min metric. Under the median metric it is second-cheapest.
  - Tomato (Lidl/Auchan "Paradicsom 1 kg" at about 430 vs vine tomatoes at about 880) and banana (the script keeps only the dominant unit, so 499 Ft five-banana bunches sold per piece are dropped) also compare unlike items.
- Not addressed: 40% of shoppers already use a discounter as their main store (NIQ, VERIFIED). For them the store-choice saving is close to zero. The scaling to the full food budget (2–6k) is an untested ESTIMATE.
- **Corrected statement:** On GVH data from 2026-10-12, the cheapest chain beats the priciest by 3–6k Ft/month on staples (8–17%), depending on how the "comparable item" is chosen. Lidl is cheapest under 3 of 4 metrics, and the rest of the ranking is unstable. Best-in-1-km vs average nearby chain is about 1.7–3.9k Ft/month. The 2–6k full-budget figure and the 3–8k total are estimates, and households that already shop at a discounter save little from store choice.

### 2. Cherry-picking is not worth it (1.8–2.9k vs 4.5k time cost) — PARTLY TRUE
- My recomputation: all 6 chains vs the best single chain saves **1.7k (median item), 2.8k (min), 3.4k (p25) or 3.8k (2nd-cheapest)**. The **best 2-chain combination** saves 1.3–2.6k (Lidl+Spar, Auchan+Lidl or Aldi+Lidl). COMPUTED.
- The time-cost arithmetic is right. 25 min × 4.33 × (437,900 / 174 h = 2,517 Ft/h) = **4,540 Ft**. The median net wage of 437,900 Ft in July 2026 is VERIFIED in KSH ker2607.
- The conclusion rests on three assumptions:
  1. Time is valued at the **full net wage**. Valuing leisure at about half the wage, which is common in transport appraisal, halves the cost to about 2.3k. That is below the 2.6–3.8k cherry-pick gain.
  2. The cherry-pick gain is **not scaled** to the full basket, while the store-choice gain is. The stream's own logic (staples are 25–40% of food spend) would put it at about 4–10k.
  3. NIQ (VERIFIED) shows 85% visited supermarkets and 78% visited discounters in the past 4 weeks. Many shoppers already use 2 chains, so splitting a list between chains they already visit has close to zero extra time cost.
- **Corrected statement:** Spreading purchases across chains adds about 1.3–2.6k Ft/month (2 chains) or 1.7–3.8k (all 6) on staples. That beats one extra weekly store stop only if time is valued below about 2,500 Ft/h, or if the shopper already visits both chains. "Split the list across the 2 chains you already use" is a defensible feature. "Route me through 6 stores" is not.

### 3. Choosing a cheaper item within the chain beats switching chains (~10k) — PARTLY TRUE
- The average of median minus min is reproduced: **9,755 Ft** (Spar 16.0k, Auchan 11.7k, Tesco 10.7k, Aldi 8.6k, Lidl 6.9k, Penny 4.6k). COMPUTED.
- The figure is inflated by unlike items:
  - "Tengeri halfilé" mixes salmon (4,000–10,500 Ft/kg) with pollock or hake (about 2,630/kg). Without fish the average is **8.1k**.
  - The "typical item" is the median SKU, not a sales-weighted purchase. Measuring median minus the 25th-percentile item (a cheaper item, not the rock-bottom one) gives **6.5k** (5.3k without fish).
- NIQ figures are VERIFIED in the PDF:
  - "Olcsóbb termékre váltok" is the #1 saving strategy in Hungary at **58%** (n≈782, 2024). It is the most-cited strategy, not "58% say it is their top strategy".
  - Private label value share is **33.3%**.
- **Corrected statement:** The within-chain gap between the median SKU and the cheapest is about 8–10k Ft/month, and a realistic "trade down one notch" saving is about 5–6.5k. That is still roughly equal to or larger than the store-choice gain, so the direction holds. 58% already use this strategy, so the extra gain an app can add is smaller.

### 4. NomNom: Budget Meal Planner, a direct HU competitor — CONFIRMED (with additions)
VERIFIED through the iTunes lookup API (country=hu), the App Store HU page and nomnomplanner.com:
- Seller Z Gen Kibernetika Kft., brand Neo App Labs.
- Released **2026-07-23**, **703 ratings, 4.82★**, version 1.0.19 (2026-10-11), **#8 in the HU Food & Drink chart**.
- In-app purchases: **NomNom Plus 7,990 Ft**, NomNom Monthly **1,490 Ft**.
- The site says prices come "a Gazdasági Versenyhivatal hivatalos Árfigyelőjéből és bolti katalógusokból".

What the stream left out:
- iOS only ("Lesz Android? Egyelőre iOS").
- The App Store lists **EN** as the only language, while the site says the UI switches to Hungarian.
- Content is thin: **dinners only, 36 dinners in the planner, 1,000+ tracked products**.
- One store at a time ("válaszd a törzsboltod"), with no location or nearby-store comparison.
- It does have **macros, diet filters and "fehérjedús / alacsony kalóriás" modes**, so "minus a health focus" is too strong. It has health features but no nutrition-goal-driven planning.
- It aims at 27 EU countries. A US listing appeared on 2026-08-12 with 9 ratings.
- It runs paid ads (the site discloses ad-click attribution), so the 703 ratings are partly paid acquisition.

### 5. Árrésstop in force; phase-out would widen dispersion because capped staples have tiny gaps — PARTLY TRUE
- **Status confirmed** (VERIFIED, Index 2026-10-05):
  - 10% cap on 43 food categories (13 of the 14 announced December additions were kept), plus 30 drugstore categories at 15%.
  - Applies to retailers with 2023 net revenue above HUF 1 bn.
  - In force since 17 March 2025, with no end date (sunset removed April 2026; 84/2026 Korm. rendelet per a search summary).
  - On 2 October 2026 the PM said a phase-out "meg kell fontolni" (VG/444, VERIFIED), with no date. I found no decision between 5 and 12 October.
  - Detail: the stream's notes say "made statutory May 2025", while Index places the statutory step in 2026. Check this if it matters.
- **The causal inference is refuted.** The capped list includes Csirkemellfilé, Csirkecomb, Sertéscomb, Tojás, Vaj, Tehéntúró, Trappista and Késői burgonya (Pénzcentrum 2025-03-11, 30-item list), plus alma, fejes káposzta, paradicsom, vöröshagyma and zöldpaprika (VG, December 2025). On today's data these capped items show **large** chain spreads (COMPUTED, max/min of the chain-cheapest unit price):
  - tomato 2.05×, green pepper 2.07×, apple 1.67×, potato 1.61×, túró 1.55×, chicken leg 1.47×, butter 1.33×
  - Capped median 1.23× vs uncapped median 1.43×.
  - Tight spreads occur only on homogeneous commodities (oil 1.01, flour 1.03, sugar 1.09, milk 1.11), which are also cheapest-item commodities.
  - The cap limits each retailer's own margin. It does not set a common price.
- **Corrected statement:** The cap is in force and a phase-out is being discussed with no date. The cap does not explain the small cross-chain gaps: produce and meat are also capped and show 1.5–2× spreads. A phase-out would most likely cause a one-off price-level shift on capped items, a news event that helps engagement. Any lasting change in dispersion is speculative.

### 6. "Local" = which chains are near you; median 3 chains within 1 km — PARTLY TRUE
- On all 120 food categories (not the stream's 37-category sample), **priceSameEverywhere=false = 10.3%** of grocer entries, not 6.8%. **Tesco 38.8%**, Spar 4.1%, Auchan 1.5%, Lidl 1.3%, Aldi 0.0%, Penny 0.0%. COMPUTED.
- In 92% of these entries at least one price type has sameAmountEverywhere=false, meaning the amounts really do differ by store.
- The store-level endpoint works:
  - Tesco "FRISS CSIRKEMELL FILE PULTOS" returns 2,030 / 1,699 Ft at Hengermalom u. and Rákóczi F. út.
  - It returns "PRODUCT-SHOP-PRICES-NOT-FOUND" at the Teréz krt. and Máriaremetei út stores, because counter products are not sold in Expressz stores.
  - So "local" also means **which products a store format carries**, not only which chains are nearby.
- Chain density reproduces: 282 Budapest grocery stores; median 3 chains within 1 km and 5 within 2 km from store points. But on the uniform built-up grid the median is **1 within 1 km** and 4 within 2 km. Stores cluster, so the store-point proxy overstates what a typical resident sees.
- GVH also excludes CBA, Coop, Príma, Reál and other smaller chains, which make up much of Budapest's corner-shop network.
- **Corrected statement:** For Aldi, Lidl and Penny, local means "which chains are near me". Tesco (39% of entries) and to a small degree Spar differ by store and by format (Expressz vs hypermarket), and GVH's store endpoint exposes this. A typical resident has about 1–3 GVH chains within 1 km and 4–5 within 2 km. The population-weighted figure was not computed.

### 7. GVH misses most discounter promotions — CONFIRMED (numbers corrected)
- Full food pull: DISCOUNTED flags on **2.4%** of grocer entries, not 3.5%. Aldi 0.0%, Auchan 0.5%, Lidl 1.0%, Spar 3.9%, Tesco 4.0%, Penny 6.2%. LOYALTY: Lidl **0%** despite Lidl Plus; Auchan 6.5%; Tesco 3.8%. COMPUTED.
- Spot check (VERIFIED on aldi.hu): Aldi's offer pages from 2026-10-08 and 2026-10-12 list GVH-category items that are **absent from GVH**, for example "HALLOWEEN Virsli, 300 g 999 Ft" (category 23 virsli) and "LAVAZZA Szemes kávé 1 kg 8 999 Ft" (category 122). Most discounter leaflet items are temporary "amíg a készlet tart" SKUs, which GVH's ≥80%-of-stores staple scope does not cover.
- The leaflet survey is VERIFIED as reported by MediaFuture: 71% weekly, 85% monthly, 6% never; 25% + 55% say leaflets influence purchases. The source is Shopfully, a leaflet platform with a commercial interest, and no sample size or method is given.
- **Corrected statement:** GVH carries almost no discounter promotions (Aldi 0%, Lidl 1%, no Lidl Plus prices) and none of the temporary leaflet SKUs. A leaflet or promo source is required to capture deal-driven savings.

### 8. Market size (804k households, ~118k Ft/month, ~1,140 bn Ft) and the "tens of millions, not hundreds" revenue ceiling — PARTLY TRUE
- **VERIFIED:**
  - 804,044 Budapest households and 1,651,512 persons in 2024 (KSH jov0042).
  - Retail food sales of **5,925,957 m Ft** in 2025 (bel0005; soft drinks 609,224 m and coffee 207,833 m are listed separately).
  - Food prices −1.3% (−4.6% excluding catering) in September 2026 (far2609).
- **Cross-check (COMPUTED):** national retail food per person × 2.054 × the Budapest/national HBS ratio (384,772 / 357,493) gives **116k** (food only) to **132k** (with soft drinks and coffee). The 118k ESTIMATE is plausible, and 1,140 bn Ft follows from it.
- **The revenue ceiling is overstated in gross terms.** The stream's formula multiplies 1,490 Ft/month × 12 (17,880 Ft), but NomNom's default plan is **7,990 Ft/year** with a trial. App Store prices also include **27% Hungarian VAT** and Apple's 15% small-business commission. Net revenue per payer is about **5.3k (annual) to 12.0k (monthly × 12)** Ft/year.
  - Applied to the same adoption and conversion assumptions, net revenue is about **2–27m Ft/yr**, against the stream's 7–40m gross. COMPUTED on the stream's own assumptions.
  - The conclusion ("tens of millions at most; not hundreds") holds or is pessimistic in the right direction.
- The price-ceiling claim is weakly evidenced: it rests on two competitor list prices. Yazio HU charges up to **9,990 Ft per 12 months and 4,990 Ft per 3 months** (VERIFIED on the App Store HU page). A health-led product can price a little higher, but within the same order of magnitude.
- RevenueCat (VERIFIED): freemium D35 median 2.1%, hard paywall 10.7%, Health & Fitness 2.9%, Western Europe 2.0% (by developer HQ). No Eastern Europe figure.
- Kifli on VIVnetworks (VERIFIED): €5 per new customer, or per customer lapsed 60+ days; nothing for existing customers; 3-day cookie.

---

## Things the stream missed
1. **Salmon is in GVH** (category 93 "Tengeri halfilé" includes Aldi/Lidl lazacfilé). The brief's "not covered: salmon" is wrong. This mix of salmon and pollock in one category also distorts any "typical item" median.
2. The **store-level endpoint** `/api/product/{id}/shop/{shopUuid}` returns per-store prices and "not found" where the product is not sold. Real local pricing and availability are retrievable for the about 10% of non-uniform entries (Tesco 39%). The stream's local analysis used only the chain-level price.
3. **Format-dependent availability.** Expressz and City stores do not carry counter meat or many SKUs. A recipe priced with a hypermarket SKU may not be buyable at the nearest store of the same chain.
4. **The basket results depend on the cheapest SKU listed**: bread is 40% of the headline gap, and some items are unlike (400 g loaf vs 1 kg sliced; bulk tomato vs vine). The script also drops banana bunches priced per piece. Report ranges across item-selection rules (min, 2nd, p25, median), not one figure.
5. **Unit economics:** the 27% VAT and the Apple/Google commission were not netted out. The annual-plan price (7,990) was ignored in favour of monthly × 12.
6. **NomNom details** relevant to positioning:
   - iOS only, English-only App Store metadata.
   - Dinners only; 36 recipes; 1,000+ products.
   - One store at a time, no location.
   - Already has macros and diet filters, so "health-first" must mean more than macros, for example goal-based weekly nutrition, full-day plans, waste/leftover planning, and a Hungarian-language recipe base.
   - #8 in HU Food & Drink and paid acquisition. It is targeting 27 EU markets.
7. **Árrésstop scope vs GVH scope:** the cap applies to retailers above HUF 1 bn, while GVH reporting applies above HUF 100 bn. Smaller chains (CBA, Coop, Príma, Reál) are capped but invisible in GVH, which is a coverage gap for "local" in Budapest neighbourhoods.
8. **KSH quantities are from HBS 2020**, a COVID year with more eating at home. Per-household at-home quantities and the basket Ft values are probably somewhat overstated for 2026. ESTIMATE; not quantified.
9. **The Shopfully leaflet survey and the NIQ figures come from interested or commercial parties with thin method disclosure.** Treat them as indicative.
