# Gap fill: does GVH already capture weekly promotions, and how stable are prices, availability and chain rankings?

Stream key: `gap-gvh-promo-and-stability`. The work ran on 2026-10-12 from 22:00 CEST, and a background poller continued into 2026-10-13 (section 5).
Labels:
- **VERIFIED**: read from a primary source (URL given) or from a live API response or download.
- **COMPUTED**: calculated from data I pulled; the method is stated.
- **ESTIMATE**: my reasoning.

Folders under `research/gap-gvh-promo-and-stability/`:
- `dl_promo/`, `dl_gvh/`, `dl_xlsx/`, `dl_wayback/`: untrusted downloads, each in its own folder.
- `scripts/`: my code, all run with `python3 -I`.
- `data/`: CSV and JSON outputs.

Politeness: GVH calls at most about 1.6 per second (0.6 s gap), chain sites at 1 request per 1–1.5 s, Wayback at 1 per 3 s, and UA `market-research-bot/0.1`. No logins, forms or leaflet images. For Auchan I read one iPaper "enrichments" JSON, which holds hotspot links only, no images.

---

## 0. Bottom line

| Question | Answer | Basis |
|---|---|---|
| Does GVH capture weekly promotions? | **Yes, for every promoted product that the law requires to be reported. In my sample: 26/26 on the day the promotion starts, at the promo price, in every Budapest test store and chain-wide.** | VERIFIED via the API on 2026-10-12; COMPUTED |
| How does a promotion appear? | **Penny and Lidl:** `DISCOUNTED` = promo price, and `NORMAL` = the pre-promo price. NORMAL equals the chain's own published strike price in 17/17 cases. **Aldi:** only `NORMAL`, already at the promo level. 0/8 are flagged, so Aldi promotions look like ordinary price cuts. | VERIFIED |
| Loyalty prices | The Penny card price appears as `LOYALTY` (1/1 checked). **Lidl Plus app prices are missing (0/4).** The law excludes coupon-type and quantity-based prices from the loyalty field (§57(1)bc). | VERIFIED |
| What GVH misses | (a) Everything outside the decree's narrow product definitions: most of each leaflet, e.g. Jonagold apples, chicken drumsticks, 100 g salami, 2 l water, pipe rigate, 900 g coffee. (b) "Csak most!" temporary specials: the law exempts products sold for at most 1 month (§66(5)). (c) App and coupon prices. | VERIFIED legal text plus the sample |
| Share of each chain's weekly offers that is in GVH at all | Penny 5–7% (18–22/333; 18 confirmed), Lidl 11% (8/70), Aldi 26% (10/39 highlighted) | COMPUTED, matched by hand |
| Day-over-day change, food product×chain pairs (XLSX) | min/max changed: **1.8%** (11→12 Oct 2026) and 2.6% (8→9 Apr 2025). Store count changed: about 33%, but only **3.7%** changed by ≥5% of the chain's stores, and **1.4%** crossed the 80%-availability line. Pairs appearing or disappearing: 0.2–0.3%. | COMPUTED |
| Weekly change (6-day windows that span a Thursday) | **12.8–19.0%** of food pairs changed min or max | COMPUTED |
| Ranking stability (20-item core basket, chain-level XLSX min or max, 9 dates from 2024-09 to 2026-10) | **Lidl is cheapest on all 7 dates since 2025-03-07** (gap to #2: 0.2–10.5%). It is **not** cheapest on 2024-09-05 (Auchan or Penny, gap 0.1–0.4%) or on 2024-12-17 (Aldi, gap 0.6%). | COMPUTED |
| Item-level cheapest chain | Day to day: 17–19 of 20 items keep their cheapest chain. Week to week (6-day windows): only **9–11 of 20**. Across months: 5–7 of 20. | COMPUTED |
| Is leaflet data needed for the MVP? | **No**, for pricing the staple-ingredient basket inside GVH categories: promotions there are already in GVH on the day. **Yes**, for a broad "deals" feature, Lidl Plus prices, or ingredients outside GVH. The cheaper route for that is the chains' own structured web pages, not leaflet images. | ESTIMATE grounded in the above |

---

## 1. Promotion capture test (task 1)

### 1.1 Sources of the promotions (all VERIFIED, fetched 2026-10-12 about 22:10–22:20 CEST)
- **Penny**:
  - `https://www.penny.hu/sitemap.xml` (robots.txt only declares the sitemap). It lists weekly category pages such as `/category/ajanlatok-10081014-koezoett` (offers 10.08–10.14) and `/category/ajanlatok-10151021-koezoett` (next week).
  - Seven pages of `https://www.penny.hu/category/ajanlatok-10081014-koezoett?page=N` gave **333 offers**. 298 run "Cs 2026.10.08-tól Sze 2026.10.14-ig"; 35 are "H 2026.10.12-tól" (Monday–Wednesday).
  - Each tile carries the slug and SKU (`86-NNNNN`), price, struck "eredeti ár" (original price) and validity. Penny-card offers show two prices.
  - Product pages carry JSON-LD with `validFrom` and `validThrough`, e.g. `/products/milli-kremturo-8621737`.
  - The GVH id for own-brand items is `penny-` + SKU without the leading 86, e.g. `86-100453` → `penny-100453`. Branded items are keyed by EAN in GVH, so they cannot be id-matched from the Penny page.
- **Lidl**:
  - Robots.txt disallows only `/q/search?id=*`, `/1*`–`/9*` and a few assets.
  - Offer pages used: `https://www.lidl.hu/c/akcioink-csutortoktol/a10104490` (43 offers, 10.08–10.14) and `https://www.lidl.hu/c/akcioink-hetfotol/a10104502` (27 offers, 10.12–10.14).
  - Each tile's `data-grid-data` JSON has `ians` (Cikkszám, the article number), `price`, `oldPrice`, `discountText`, `storeStartDate` and `storeEndDate`, and "Lidl Plus" items that have no public price.
  - GVH id = `lidl-` + the IAN zero-padded to 7 digits. 8-digit IANs map via their first 5 digits (`82904001` → `lidl-0082904`) or their first 7 (`64172461` → `lidl-6417246`).
- **Aldi**:
  - `https://www.aldi.hu/szuper-akciok-mindennap`. Sections are named, e.g. "Akciók csütörtöktől szerdáig, 2026.10.08-tól 2026.10.14-ig", "…hétfőtől szerdáig, 2026.10.12-től 2026.10.14-ig" and "Frissesség minden nap hétfőtől szerdáig…".
  - Each teaser has the title, unit price and "Cikkszám: NNNNNN" (article number). GVH id = `aldi-NNNNNN`, sometimes with a `001`/`002` variant suffix.
  - The pack price is derived as unit price × pack, e.g. Milsani tejföl 886.67 Ft/kg × 0.45 kg = 399.
- **Auchan: not usable from public pages.**
  - `auchan.hu/ajanlatok` only links the iPaper catalogue `reklamujsag.auchan.hu/.../2026-10-08-10-14-heti-hipermarket-ajanlataink/`.
  - Its hotspot JSON links 142 products, all on pages 6 and 43–51. The ones I opened were electronics (an air fryer and an espresso maker).
  - The online shop's server-rendered category pages show 16 products each, cheapest first. Across 13 food categories (205 products) only 2 were `isDiscounted`, and neither is in GVH (sweet potato; basmati rice).
  - Where Auchan online prices could be compared with GVH by EAN (77 of 205), 63 equal GVH min=max. 13 differ, mostly weighed items priced per pack online.
  - **No Auchan capture rate could be computed without leaflet extraction.** That is itself a finding: Auchan's weekly deals are published mainly as a catalogue.
  - GVH's own listing does show Auchan with DISCOUNTED on 4.4% and LOYALTY on 14.8% of its product entries, computed from the gvh-location snapshot. So Auchan does report promotions.

### 1.2 Sample and method
- **Sample: 61 food promo items.** Penny 35, Lidl 14, Aldi 12. Built in `scripts/build_sample.py`; output in `data/promo_sample.json`.
- Items were picked as promotions valid on 2026-10-12 whose product type matches a GVH leaf-category name. Six "borderline" items were kept to test the edges.
- Matching to GVH:
  1. By chain-internal id (penny-/lidl-/aldi-).
  2. By EAN via name and pack, for branded items.
  3. A complete check of that chain's rows in the leaf category in the 2026-10-12 XLSX. This confirms absence, because the XLSX lists every product×chain.
- For the 30 items present in GVH, `scripts/promo_check.py` called:
  - `/api/product/{id}`: prices[] per type, pricesMax, priceSameEverywhere and availableInShops.
  - `/api/products-by-category/{leaf}?limit=48&offset=N`: the listing's prices[] and `productMinAmount`. Without `limit` the server returns only 12 per page.
  - `/api/product/{id}/shop/{4 Budapest stores}`:
    - Penny 265/234/87/64
    - Lidl 219/235/167/260
    - Aldi J120/J045/J053/J061
- Output: `data/promo_check_d12.json` and `data/promo_capture_sample_2026-10-12.csv`, one row per item with status and gap reason.

### 1.3 Results (VERIFIED from API responses on 2026-10-12, 22:30 CEST)

| Chain | Items | In GVH with promo price | Shown as | Budapest stores at promo price | Not in GVH: outside decree definition | Not in GVH: temporary "Csak most!" | App or coupon price missing | Unclear |
|---|---|---|---|---|---|---|---|---|
| Penny | 35 | **14** | 13 DISCOUNTED (NORMAL = strike price), 1 NORMAL at promo level | 56/56 | 9 | 10 | 0 | 2 |
| Lidl | 14 | **4** (all 4 priced promos that are in GVH) | 4 DISCOUNTED (NORMAL = Lidl `oldPrice`) | 16/16 | 3 | 0 | 5 (4 in GVH at NORMAL only, 1 under another id) | 2 |
| Aldi | 12 | **8** | 8 NORMAL at promo level, never DISCOUNTED | 32/32 | 4 | 0 | 0 | 0 |
| Auchan | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Every captured item had `priceSameEverywhere=true` and was listed in all of the chain's stores (Penny 248, Lidl 222, Aldi 188). The listing's `productMinAmount` equalled the promo price in every case.

**Capture rates (COMPUTED):**
- **Conditional on the product being reportable and in GVH: 26/26 = 100%** (Penny 14/14, Lidl 4/4, Aldi 8/8).
- Counting the 4 "unclear" items as misses: 26/30 = 87%. Adding the 5 Lidl Plus items as well: 26/35 = 74%.
- **Broad rate**, i.e. every sampled food promo whose product type matches a GVH category name, including temporary and out-of-definition items: Penny 14/35 = 40%, Lidl 4/14 = 29%, Aldi 8/12 = 67%. **Overall 26/61 = 43%.**
- **Whole weekly offer list, including non-food:** Penny 18–22/333 (5–7%; 18 confirmed, 4 more uncertain non-food EAN matches), Lidl 8/70 (11%), Aldi 10/39 highlighted items (26%).

**Timing (VERIFIED, XLSX diff):** promotions that started on Monday 2026-10-12 are absent from the 11 Oct file and present in the 12 Oct file. Examples:
- Penny császárszalonna 1169→899, citrom 699→449, almalé 399→299
- Lidl brokkoli 699→499, Pilos gouda 1095→759, zselici kefir 159→109
- Aldi karfiol 999→666, vajkrém 599→499, brie 699→545, almalé 399→305

The end of the Thursday–Sunday weekend deals shows up as rises on the same day, e.g. Penny karfiol 699→999 and Aldi sajtos virsli 929→1399. **All 11→12 Oct food price falls at Aldi, Lidl and Penny were the Monday promotions I sampled.**

### 1.4 Why the misses happen (VERIFIED legal text)
- Act L of 2025 (https://njt.jog.gov.hu/jogszabaly/2025-50-00-00; text saved by the legal stream at `research/legal/verify_dl/njt/2025-50-00-00.txt`):
  - §55(5): "napi ár" (daily price) = the lowest price available to all consumers that day. Promo prices must therefore be reported.
  - §55(10) and §57(1)bb: "korábbi ár" (earlier price) = the pre-reduction price. This is the `NORMAL` paired with `DISCOUNTED`.
  - §57(1)bc: the loyalty price must be reported only if it is lower than the daily price, **excluding coupon prices and quantity discounts** ("ide nem értve a kuponos, továbbá mennyiségi kedvezményhez kötött bruttó eladási árat").
  - §66(1): data must be uploaded by the end of the previous day.
  - **§66(5): products sold continuously for at most one month need not be reported** ("Nem kell adatot szolgáltatni … ha … megszakítás nélküli forgalmazási időszaka legfeljebb egy hónap").
- 11/2023 (VI.22.) GFM decree, Annex 1 (`research/legal/dl/njt_11_2023_GFM.txt`, https://njt.jog.gov.hu/jogszabaly/2023-11-20-8P), narrow definitions:
  - Alma: only loose Idared.
  - Csirkecomb: whole leg without back.
  - Téliszalámi: sticks from 350 g.
  - Rizs: 1,000 g white "B" grade.
  - Száraztészta: 400–1,000 g spaghetti, macaroni, penne or fusilli.
  - Ásványvíz: 1.5 l.
  - Őrölt kávé: 200–250 g. Szemes kávé: 900–1,000 g.
  - Tea: unflavoured green tea and earl grey only.
  - Szárazkolbász: parasztkolbász only.
  - Túródesszert: coated curd bars only.
- GVH FAQ (https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf): "Akciós ár esetén az árfigyelő rendszer megjelöli az akció mértékét is." (For a promotional price, the system also shows the size of the discount.)
- ESTIMATE: Aldi meets the "napi ár" duty by reporting the promo price as its NORMAL price and does not send a "korábbi ár". The data are legally fine for price comparison but not for labelling promotions. Telling an Aldi promotion apart needs your own history (yesterday's price) or Aldi's offer page.

---

## 2. Day-over-day stability from the official XLSX (task 2)

### 2.1 Files (VERIFIED)
- **2026-10-12 file:** downloaded with a cache-buster. Sheet "Napi feltöltések - 2026-10-12", Last-Modified Mon 12 Oct 2026 02:00:12 GMT, 2,087,294 bytes, SHA-256 59f7d04d…, identical to the gvh-location and competitors copies.
- **2026-10-11 file: none of the other streams had it.** All three earlier copies are the 12 Oct file (same hash). I recovered it from the CDN's stale cache.
  - A plain GET with `Accept-Encoding: gzip` (curl `--compressed`) returned sheet "Napi feltöltések - 2026-10-11", Last-Modified Sun 11 Oct 02:00:12 GMT, 2,089,159 bytes.
  - HEAD probes showed the Azure CDN keeps separate stale variants per Accept-Encoding: `identity` and `deflate` gave 11 Oct; `gzip, deflate` and `br` gave 12 Oct.
  - **A daily job must use a cache-buster and check the sheet-name date**, as the verifier said. Even a browser click can get yesterday's file.
- Wayback archive copies: section 3.

### 2.2 Results
Script `scripts/xlsx_diff.py`; full table in `data/xlsx_daily_diff.csv`. The key is product id × chain. "Food" = the 6 food top categories, 120 leaves.

| Window | Food pairs in common | min or max changed | min changed (up/down) | Store count changed | Changed by ≥5% of the chain's stores | Crossed the 80% line | Gone / new |
|---|---|---|---|---|---|---|---|
| 2026-10-11 (Sun) → 10-12 (Mon) | 5,554 | **1.76%** | 1.57% (34/53) | 33.9% | **3.7%** | **1.4%** | 12 / 7 |
| 2025-04-08 (Tue) → 04-09 (Wed) | 3,699 | **2.60%** | 2.54% (48/46) | 32.0% | 3.5% | 1.7% | 8 / 8 |
| 2025-04-09 → 04-15 (6 days, spans a Thursday) | 3,680 | **19.0%** | 18.2% (422/249) | 44.5% | 9.1% | 2.4% | 27 / 26 |
| 2025-03-07 → 03-13 (6 days) | 2,546 | **12.8%** | 12.6% (165/156) | 46.0% | 11.2% | 3.3% | 51 / 31 |
| 2025-03-13 → 04-08 (26 days, during the árrésstop margin-cap rollout) | 2,453 | 56.5% | 55.9% (318/1054) | 51.4% | 14.9% | 4.8% | 124 / 1,254 |

All products, 11→12 Oct 2026: 0.8% of 25,387 pairs changed min or max.

Per chain, food, 11→12 Oct, share of pairs with min or max changed:

| Penny | Lidl | Aldi | Rossmann | Spar | Tesco | Auchan |
|---|---|---|---|---|---|---|
| 5.2% | 3.9% | 4.0% | 8.3% | 2.4% | 0.3% | 0.1% |

Store-count changes are almost all Spar (76% of pairs), Tesco (54%), dm (69%) and Rossmann (49%). They are small daily wobbles in "Hány boltban elérhető" (number of stores carrying the product).

**Reading (ESTIMATE):** on a non-Thursday day about 2–3% of food prices change, and they cluster on promo start and end days (Monday and Thursday). Over a week 13–19% change. Availability is mostly stable at the chain level. A daily XLSX pull plus per-store detail only for pairs with min<max (about 11% of food pairs) is enough. A weekly full availability refresh would miss the 3–4% of pairs that move ≥5% of stores per day, so availability needs daily refresh too if shown per store.

### 2.3 The 19 "no-data" Budapest stores
- VERIFIED 2026-10-12 22:10 CEST: all 19 (17 Spar, 2 Tesco, listed in `data/nodata_stores_2026-10-12_from_gvh-location.txt`) still return count 0 in `products-by-category/{2034,2001,2050}?shopIds=…`. The control store spar-190 returns 36/24/43.
- Day-13 re-checks are in section 5.

---

## 3. History: Wayback CDX and ranking stability (task 3)

### 3.1 Wayback
- `http://web.archive.org/cdx/search/cdx?url=cdnarfigyeloprodweu.azureedge.net/excel/*&output=json` **worked** (HTTP 200).
- 14 captures. Downloaded with `id_` (raw), deduplicated by SHA-256. This gives **7 distinct daily files** with sheet dates:

| Sheet date | Rows | Distinct ids | Categories |
|---|---|---|---|
| 2024-09-05 | 2,510 | 1,982 | 78 |
| 2024-12-17 | 2,623 | 2,067 | 78 |
| 2025-03-07 | 2,597 | 2,056 | 78 |
| 2025-03-13 | 2,577 | 2,043 | 78 (the archived file GVH links) |
| 2025-04-08 | 3,707 | 2,897 | 104 |
| 2025-04-09 | 3,707 | 2,897 | 104 |
| 2025-04-15 | 3,706 | 2,899 | 104 |

  - Each old file covers 6 food chains, and the column layout is identical to today's.
  - The 2025-04-15 file was captured on 2025-04-16 01:10 UTC, so it is still the 15th's file.
- Nothing from mid-2025 to 2026-09 is archived. Together with today's 11 and 12 Oct files this gives **9 dates**.

### 3.2 Basket ranking by date
Script `scripts/basket_hist.py`; outputs `data/basket_ranking_by_date.csv` and `data/basket_items_by_date.csv`.
- The 25-item basket definition is copied from gvh-location `basket_def.py`.
- For each category × chain I take the cheapest product's XLSX "Minimum egységár" (variant `min`) or "Maximum egységár" (`max`, the dearest store). The `_w50` variants keep only products carried in ≥50% of the chain's stores.
- Missing items are filled at the cross-chain median.
- `core20` = the 20 categories present on every date. Five were added in 2025-04 or later: tengeri halfilé, rizs, lencse, brokkoli, olívaolaj.
- Check: on 2026-10-12, `min/full` reproduces gvh-location exactly (Lidl 13,530 … Tesco 16,845; cherry-pick 12,204).

Core20, variant `min` / `max` (COMPUTED):

| Date | Cheapest (min) | Gap to #2 | Cheapest (max) | Gap to #2 | Cherry-pick saving vs cheapest chain | Last |
|---|---|---|---|---|---|---|
| 2024-09-05 | Auchan | 0.4% | Penny | 0.1% | 7.5% / 5.3% | Spar / Tesco |
| 2024-12-17 | Aldi | 0.6% | Aldi | 0.6% | 9.5% / 8.4% | Penny / Auchan |
| 2025-03-07 | Lidl | 2.4% | Lidl | 2.4% | 3.6% / 2.9% | Auchan / Tesco |
| 2025-03-13 | Lidl | 0.2% (Spar) | Lidl | 0.9% | 7.8% | Tesco |
| 2025-04-08 | Lidl | 2.4% | Lidl | 2.4% | 5.0% | Tesco |
| 2025-04-09 | Lidl | 3.0% | Lidl | 3.0% | 4.9% / 4.4% | Tesco |
| 2025-04-15 | Lidl | 6.5% | Lidl | 6.5% | 4.0% / 3.9% | Tesco |
| 2026-10-11 | Lidl* | 5.7% | Lidl* | 10.5% | 8.3% / 6.0% | Tesco |
| 2026-10-12 | Lidl* | 5.8% | Lidl* | 7.2% | 7.8% / 5.3% | Tesco |

\* Lidl has 19/20 items in 2026 (no fokhagyma); the missing item is filled at the median.

Per-item cheapest chain (`scripts/item_stability.py`, `data/item_cheapest_stability.csv`), number of the 20 items that keep their cheapest chain:

| Window | Items keeping cheapest chain |
|---|---|
| 1 day | **19/20** (2025-04-08→09); **17–18/20** (2026-10-11→12) |
| 6 days | **9–11/20** |
| Months apart | 5–7/20 |

Across all 9 dates no chain dominates item wins. Aldi has the most item×date wins (54 of 180, variant min), then Auchan 38, Lidl 34, Tesco 22, Spar 17 and Penny 15.

**Reading (ESTIMATE):**
- "Which chain is cheapest for a whole basket" is stable over weeks and months: Lidl since March 2025, at chain level and national prices. Before that the lead changed, with near-ties.
- "Which chain is cheapest for each ingredient" changes for about half the items every week.
- So the cherry-pick or "best store for this week's recipes" feature has a weekly rationale. Its saving over the cheapest single chain is modest: 3–10% of the basket at chain level.
- The location value comes from chain mix. gvh-location found the nearest store is often a Spar costing 21–27% more. That is a stable effect, not one that changes weekly.

**Where the money is: chain choice versus item splitting** (COMPUTED, `scripts/pair_split.py`, `data/pair_split_min.csv` and `data/pair_split_max.csv`; core20, 9 dates)

| Measure | Variant min | Variant max |
|---|---|---|
| Dearest chain versus cheapest chain, whole basket | 7.5–29.5% | 9.7–42.6% |
| Best 2-chain split versus best single chain | 2.2–6.9% | 1.7–6.2% |
| 6-chain cherry-pick versus best single chain | 3.6–9.5% | 2.9–8.4% |

- The dearest chain is Tesco on 7 of 9 dates.
- The best second chain to pair with the cheapest one changes across dates: Aldi, Penny, Auchan, Spar or Tesco.
- ESTIMATE: the stable, large lever is which chain you shop at, worth 10–40% and recommending Lidl/Aldi since 2025. Weekly item routing between two nearby chains adds only about 2–7%, and its best partner rotates.

Caveats:
- National chain-level prices only. Spar and Tesco store prices vary.
- The 2024–25 files predate Act L/2025 and cover fewer categories.
- The basket uses the cheapest product per category, which mixes private labels.

---

## 4. Implications for the MVP

1. **No leaflet pipeline is needed to price a healthy staple basket.** For products inside the decree's definitions, GVH reflects promotions on the day they start, with the regular price kept (Penny, Lidl, Spar, Tesco and Auchan all use DISCOUNTED or LOYALTY types), uniformly across stores. A promo-aware weekly plan can be built from GVH alone (VERIFIED for Penny, Lidl and Aldi; ESTIMATE for the others).
2. **"This is a deal" labelling** works from the API for Penny and Lidl (and Spar, Tesco and Auchan, which use DISCOUNTED), but **not for Aldi**. Aldi needs either the app's own day-over-day history or Aldi's offer page. Not the XLSX: it has min/max only, no price types.
3. **A broad "deals of the week" feature does need a second source.** 74–95% of each chain's weekly offers are outside GVH. These are temporary specials, non-standard packs or varieties, non-regulated categories and app prices.
   - Penny, Lidl and Aldi publish their offers as **structured text on their own sites**:
     - Penny: tiles with SKU, price, strike price and validity, plus JSON-LD.
     - Lidl: grid JSON with IAN, price, oldPrice and start/end dates.
     - Aldi: text with Cikkszám and unit price.
   - That is a website pipeline, not leaflet-image extraction. It is also legally different from GVH reuse: the chains' terms of use apply, which this stream did not review.
   - Auchan has no such page; its weekly deals live in an iPaper catalogue.
4. **Lidl Plus prices are invisible in GVH** (coupon-type, excluded by law). VERIFIED on lidl.hu grid JSON, 2026-10-12:

   | Item | Lidl Plus price | Normal price | Discount |
   |---|---|---|---|
   | Freshona uborka | 429 | 515 | −16% |
   | Pikok kolbász | 369 | 499 | −26% |
   | Pilos mini mozzarella | 379 | 599 | −36% |
   | Pilos főzőtejszín | 219 ("2+1 ingyen", 2+1 free) | 329 | — |
   | Belbake búzaliszt | 259 | 399 | −35% |

   In all 4 GVH-listed cases, GVH shows only NORMAL, which equals Lidl's `deletedPrice`. For Lidl Plus users, GVH understates Lidl's deals by 16–36% on such items.
5. **Refresh cadence:**
   - Daily data are enough. The data change around midnight, and the XLSX appears by 04:00 CEST.
   - Promo turnovers cluster on Monday and Thursday.
   - Keep your own daily snapshots: archived prices are not public (§57(4)–(5)), and the Wayback history is sparse.

---

## 5. Midnight and next-morning polls (task 2, timing)

See section 5 results appended below. The poller is `scripts/midnight_poll.py`, with log `data/midnight_poll_log.jsonl`. It snapshots the listings of 8 level-2 food categories (2034, 2028, 2001, 2017, 2015, 2010, 2007, 2046; 1,933 product×chain entries) at 22:33, 23:50, 00:03, 00:20, 00:45, 01:30 and 04:10 CEST. At about 04:10 it downloads the XLSX with a cache-buster and re-checks the 19 no-data stores after midnight and after 04:10.

RESULTS_PLACEHOLDER

---

## 6. Files
- `data/promo_sample.json`, `data/promo_check_d12.json`, `data/promo_capture_sample_2026-10-12.csv`, `data/promo_capture_by_chain.csv`
- `data/penny_offers_1008_1014.json` (333 offers), `data/penny_card_items.json`, `data/lidl_offers_current.json` (70), `data/lidl_offers_next.json` (161), `data/aldi_offers.json` (137 teasers, kw41 and kw42), `data/auchan_cat_sample.json` (205)
- `data/x_2026-10-11.json`, `data/x_2026-10-12.json`, `data/wb_*.json` (parsed XLSX), `data/leaf_categories.csv`
- `data/xlsx_daily_diff.csv`, `data/basket_ranking_by_date.csv`, `data/basket_items_by_date.csv`, `data/item_cheapest_stability.csv`
- `data/nodata_store_checks.csv`, `data/midnight_poll_log.jsonl`
- Scripts: `xlsx_parse.py`, `xlsx_diff.py`, `basket_hist.py`, `item_stability.py`, `gvh.py`, `nodata_check.py`, `penny_tiles.py`, `lidl_grid.py`, `aldi_teasers.py`, `nuxt_payload.py`, `auchan_cats.py`, `fuzzy.py`, `build_sample.py`, `promo_check.py`, `midnight_poll.py`

## 7. Open questions
- Aldi's practice of reporting promotions as NORMAL with no "korábbi ár": is it compliant? Should GVH be asked? It matters for any "deal" badge.
- Whether "Csak most!" items really run at most 1 month. Inferred from the badge; not verified per item.
- Auchan promo capture is untested from structured sources.
- Spar and Tesco promo capture was not sampled (not in the task). The GVH listing shows them using DISCOUNTED (5.8% and 1.9% of entries) and LOYALTY (3.3% and 6.9%).
- Ranking history has gaps (2025-05 to 2026-09). Lidl's lead since 2025-03 rests on 7 snapshots, 5 of them within 6 weeks.
