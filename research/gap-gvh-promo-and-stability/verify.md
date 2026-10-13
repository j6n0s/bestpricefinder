# Adversarial verification: promotions and stability (2026-10-13)

Two independent fact-checkers re-tested notes.md against live GVH data and the official XLSX of 2026-10-13. Where they conflict with notes.md, these findings take precedence.

---

# Adversarial re-check: promotion capture (notes §0–§1), run on 2026-10-13

Checked: `research/gap-gvh-promo-and-stability/notes.md`, §0 (bottom line) and §1 (promotion capture).
Run: Tue 2026-10-13, 10:06–10:21 CEST. GVH API calls 08:09–08:15 UTC.
Labels:
- **VERIFIED (url)**: read from the live page, API or file.
- **COMPUTED (method)**: calculated from data I pulled; the method is stated.
- **ESTIMATE**: my judgement.

Politeness: User-Agent `market-research-bot/0.1`, at least 1.15 s between requests to the same host, no logins and no forms. Downloads sit in their own `dl_*` folders, scripts in `scripts/`, and all Python ran with `-I`.

## 0. Verdict summary

| # | Claim (notes) | Verdict | Today's evidence |
|---|---|---|---|
| a1 | GVH shows in-scope promos at the promo price, chain-wide and in Budapest stores (26/26) | **confirmed** for the promo price | 26/26 again today: Penny 14/14, Lidl 4/4, Aldi 8/8. productMinAmount equals the promo price for all 36 GVH ids. Budapest: 96 of 96 store×id checks at the promo price, in 9 stores the notes did not use. |
| a2 | …"on the day the promotion starts" | **partly true** | Day one is observable only for the 13 Monday-start offers: 13/13 are absent on 11 Oct and present on 12 Oct. The 13 Thursday-start offers (from 10-08) were only ever observed on day 4–6. No 2026-10-08 XLSX exists, and Wayback has nothing after 2025-04. |
| a3 | …"every promoted product the law requires" | **unverifiable** | Two current promos look reportable but are not in GVH: Penny Zsúrkenyér 500 g and Lidl Omnia Silk 1 kg. "Required" depends on each product's selling period (§66(5)), which public data do not show. |
| b | Aldi promos only as NORMAL at the promo level, never DISCOUNTED | **confirmed** (food, today) | 0 DISCOUNTED and 0 LOYALTY among 420 Aldi food entries (120 leaves, 159 requests). The 8/8 Aldi promos are NORMAL at the promo price. |
| c | Lidl Plus prices not reported; LOYALTY absent for Lidl; excluded by law as coupon-type | **partly true** | 0 LOYALTY among 385 Lidl food entries, and 4/4 Lidl Plus items in GVH show only NORMAL = Lidl's deletedPrice. But Lidl's own page says weekly Lidl Plus offers activate automatically when the card is scanned and calls them distinct from coupons. The "coupon, so excluded" basis is therefore not supported. |
| d1 | §66(5): products sold ≤1 month are exempt | **confirmed** | Verbatim on njt (time state 2026.10.01). |
| d2 | §57(1)bc: coupon and quantity prices excluded from the loyalty price | **confirmed** | Verbatim on njt. Note that §55(5) and §55(10) as cited are numbered points of §55 ("55. § 5. pont"), not paragraphs. |
| e | Share of weekly offers that is in GVH: Penny 5–7%, Lidl 11%, Aldi 26% | **confirmed** | Full enumeration today: Penny 18–21/333 (5.4–6.3%), Lidl 8/70 (11.4%), Aldi 10/39 (25.6%). |

## 1. Sources fetched today (all VERIFIED)

**Penny**
- `https://www.penny.hu/sitemap.xml`.
- Weekly list `https://www.penny.hu/category/ajanlatok-10081014-koezoett?page=1..8`: **333 tiles**, the same 333 as the notes.
- `https://www.penny.hu/category/oesszes-ajanlat-99000000?page=1..16`: 695 tiles, which is the current week plus next week. All 333 weekly tiles are included; no further current offers.
- `…-penny-kartyaval-olcsobb-termekek`: 31 Penny-card tiles.
- `https://www.penny.hu/products/zsurkenyer-861573`, JSON-LD read.

**Lidl**
- `https://www.lidl.hu/c/akcioink-csutortoktol/a10104490`: 43 offers, 10-08..10-14.
- `https://www.lidl.hu/c/akcioink-hetfotol/a10104502`: 27 offers, 10-12..10-14.
- `/c/akcioink-szombattol/a10104796`: 23 offers, from 10-17, so not valid today.
- `/c/lidl-plus-ajanlataink/a10050097`: 44 Lidl Plus tiles. 17 are valid today, of which 15 duplicate the two pages above; the extras are Gránátalma and an air fryer.
- `/c/a-lidl-plus-rol/s10014705`.
- The product grids are complete as rendered. The page's only "Mutass többet" button belongs to the content masonry under the grid.

**Aldi**
- `https://www.aldi.hu/szuper-akciok-mindennap`: 137 teasers. **39 are valid today**, from sections egeszhetikw41 (17), hetfoSzerdakw41 (17) and frissessegHetfotolkw41 (5).

**GVH**
- `/categories`, `/shops`, `/chain-stores`.
- `/products-by-category/{leaf}?limit=48&offset=N` for all **120 food leaves: 159 requests, 4,333 product rows, 0 errors**, at 08:09 UTC.
- `/product/{id}` and `/product/{id}/shop/{3 stores}` for 36 ids, plus penny-61364 and penny-347.

**XLSX**
- `https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx?v=vp20261013a`: sheet "Napi feltöltések - 2026-10-13", Last-Modified Tue 13 Oct 2026 02:00:12 GMT, 2,087,076 bytes, SHA-256 3f874738…, 25,392 data rows.

**Law**
- `https://njt.jog.gov.hu/jogszabaly/2025-50-00-00`: Act L of 2025, time state shown as 2026.10.01.
- `https://njt.jog.gov.hu/jogszabaly/2023-11-20-8P`: 11/2023 GFM decree, Annex.

**Wayback**
- CDX `…/excel/*&from=2025`: the newest daily-file capture is 2025-04-16. Later captures are only of the archived 2025-03-13 file. **No 2026-10-08 file exists.**

## 2. (a) Promotion capture with today's live data

### 2.1 Population, not a sample
- I matched **all** current offers to GVH ids:
  1. Chain-id rules (`penny-`, `lidl-`, `aldi-` with `001`–`005` variants) against the 13 Oct XLSX, all categories.
  2. Name and token fuzzy matching, plus price equality, against that chain's XLSX rows, reviewed by hand. EAN matches: Pöttyös Túró Rudi 6×51 g and 6×35 g 0%, Pick Pickolino (2 EANs), Magyar tejföl 330 g, Eduscho Family 250 g (2 EANs).
- **Result (COMPUTED): the in-GVH, priced food promos today are exactly the same 26 offers the notes sampled** (Penny 14, Lidl 4, Aldi 8; 36 GVH ids including variants and twin EANs), plus 4 Lidl Plus items.
- A "fresh" sample therefore cannot contain new captured items: the notes' 26 were the entire population at these three chains.

### 2.2 Live check
Script `scripts/promo_api_check.py`; output `data/promo_api_check_2026-10-13.json` and `data/promo_capture_2026-10-13.csv`. VERIFIED from the API at 08:13–08:15 UTC.

Fresh Budapest stores, not used in the notes:

| Chain | Stores |
|---|---|
| Penny | penny-233 (Király u. 82), penny-102 (Rétköz u. 1), penny-26 (Pesti út 16-18) |
| Lidl | lidl-356 (Rákóczi út 48-50), lidl-237 (Fehérvári út 211), lidl-129 (Pesti út 237/H) |
| Aldi | aldi-J062 (Rákóczi út 65), aldi-J047 (Rétköz u. 10/b), aldi-J059 (Pesti út 237/p) |

Capture per chain (offer level):

| Chain | Captured at promo price | Shown as | NORMAL = chain strike price | Budapest store×id at promo price | Detail priceSameEverywhere / availableInShops |
|---|---|---|---|---|---|
| Penny | **14/14** | 13 DISCOUNTED, 1 NORMAL (Milkeria magvas joghurt 199; no strike price on penny.hu; XLSX 213→199 on 10-12) | 13/13 | 48/48 | true / 248 |
| Lidl | **4/4** | 4 DISCOUNTED | 4/4 | 12/12 | true / 222 |
| Aldi | **8/8** | 8 NORMAL at the promo level | n/a | 36/36 | true / 188 |
| Lidl Plus | 0/4 at the app price | NORMAL only, equal to deletedPrice: uborka 515 (app 429), Pikok 499 (369), mini mozzarella 599 (379), főzőtejszín 329 (219, "2+1") | — | 12/12 at NORMAL | true / 222 |

- Listing `productMinAmount` equals the promo price for 36/36 ids (COMPUTED).
- The XLSX 13 Oct min = max = promo price for all 36 (COMPUTED).
- Non-food check: Penny-card Wippy papírtörlő 599/399 → `/product/penny-61364` shows NORMAL 599 + **LOYALTY 399** (VERIFIED). The XLSX shows 599 only, so **the XLSX omits LOYALTY prices**.

### 2.3 "On day one"
Script `scripts/dayone.py`, using the 11, 12 and 13 Oct XLSX (COMPUTED).
- **Monday-start offers (13): 13/13 change to the promo price exactly on 12 Oct** (11 Oct value → 12 Oct promo):

  | Chain | Item | 11 Oct | 12 Oct |
  |---|---|---|---|
  | Penny | császárszalonna | 1169 | 899 |
  | Penny | citrom | 699 | 449 |
  | Penny | gouda | 1269 | 1085 |
  | Penny | magvas joghurt | 213 | 199 |
  | Penny | almalé | 399 | 299 |
  | Lidl | brokkoli | 699 | 499 |
  | Lidl | gouda | 1095 | 759 |
  | Lidl | kefir | 159 | 109 |
  | Aldi | karfiol | 999 | 666 |
  | Aldi | vajkrém | 599 | 499 |
  | Aldi | brie | 699 | 545 |
  | Aldi | Bronze cut | 479 | 425 |
  | Aldi | almalé | 399 | 305 |

- **Thursday-start offers (13): already at the promo price on 11 Oct, which is day 4.** Day one (10-08) cannot be checked: no file exists for that date (Wayback CDX checked).
- So the notes' "26/26 on the day the promotion starts" is shown for **13/26** only.

### 2.4 "Every promoted product the law requires": possible misses
Population-wide keyword scan (`scripts/scope_scan.py`, `data/scope_scan.json`) followed by manual checks against the decree.

Decree text VERIFIED on njt 2023-11-20-8P:
- Alma: lédig Idared.
- Szemes kávé: 900–1000 g, not bio.
- Fehér kenyér: 500–1000 g fresh, not long-life, not toast.
- Száraztészta: 400–1000 g spagetti, makaróni, penne, fusilli, 2- or 4-egg, or durum.
- Téliszalámi: from 350 g, stick.
- Ásványvíz: 1.5 l.
- Túródesszert: coated curd bar.
- Csirkecomb: whole leg without back.
- Finomliszt: 1 kg BL-55.

Most non-GVH items are clearly outside these definitions (pack or variety) or carry Penny's "Csak most!" badge. Two remain plausible misses (**unclear**):

| Chain | Offer | Why it looks reportable | Status in GVH |
|---|---|---|---|
| Penny | ZSÚRKENYÉR 500 g, 499 (eredeti ár 699), Mon–Wed | SKU 86-1573, category Pékáru. A 4-digit SKU like Penny's regular breads, with a regular price. Fits "fehér kenyér 500–1000 g" unless it is long-life. | `penny-1573` is absent from the XLSX (all categories). VERIFIED (JSON-LD, XLSX). |
| Lidl | OMNIA Silk kávé 1 kg "Őrölt / szemes", 5799 SZUPER ÁR! | The bean variant is within "szemes kávé 900–1000 g". | Lidl reports only Omnia Silk 250 g (5997100004852 at 1839). The 1 kg beans (5997100070093) are in GVH for Auchan, Spar and Tesco but **not Lidl**. |

Similar within-definition items with "Csak most!" (temporary, §66(5) if sold ≤1 month; not verifiable):
- Penny Barilla spagetti, fusilli and penne 1 kg (899 each).
- Penny Segafredo Intermezzo szemes 1 kg (5999). Lidl does report this product, at 6999.
- Penny Gyermelyi finomliszt 1 kg.
- Penny Magyar trappista 1 kg, Ementaler 1 kg, Tarka natúr joghurt and kefír.

**Broad rate (ESTIMATE, population denominator):** captured priced offers ÷ current offers whose product type matches a GVH leaf.
- Penny ≈ 14/45–50 ≈ 28–31%. The notes' sample of 35 gave 40%.
- Lidl ≈ 4/14–16 ≈ 25–29%.
- Aldi ≈ 8/12–13 ≈ 62–67%.

### 2.5 Error in the notes' classification
- Notes L11 says "Belbake búzaliszt (Lidl Plus) … product itself is in GVH as lidl-0002118 at NORMAL 178", and the §1.3 table counts it as "1 under another id".
- Today's Lidl grid shows that the offer is **"Teljes kiőrlésű"** (wholemeal), 1 kg, Lidl Plus 259 against deletedPrice 399. lidl-0002118 is Belbake **BL-55 finomliszt** at 178.
- These are different products, and wholemeal flour is not a GVH leaf. The item is outside GVH, not "under another id". VERIFIED (lidl.hu grid JSON, XLSX).

## 3. (b) Aldi DISCOUNTED count in today's food listing
VERIFIED from 159 listing responses at 08:09 UTC; COMPUTED by `scripts/type_counts.py` (`data/type_counts_food_2026-10-13.csv`). Counts are product×chain entries in the 120 food leaves.

| Chain | Entries | DISCOUNTED | LOYALTY |
|---|---|---|---|
| **Aldi** | 420 | **0** | **0** |
| **Lidl** | 385 | 4 (the 4 promos above) | **0** |
| Penny | 338 | 19 | 2 |
| Spar | 1,077 | 40 (3.7%) | 2 (0.2%) |
| Tesco | 1,123 | 45 (4.0%) | 43 (3.8%) |
| Auchan | 1,579 | 8 (0.5%) | 100 (6.3%) |
| Rossmann | 158 | 15 | 8 |
| Müller | 229 | 0 | 0 |
| dm | 60 | 0 | 0 |

Caveat: the notes' Auchan (4.4% / 14.8%), Spar (5.8% / 3.3%) and Tesco (1.9% / 6.9%) DISCOUNTED/LOYALTY shares are **not reproduced** on today's food listing. They came from another snapshot, and their scope is not stated.

## 4. (c) Lidl Plus
- Lidl LOYALTY entries in today's food listing: **0 of 385** (COMPUTED).
- Today 15 Lidl Plus offers are valid on the two weekly pages, plus 2 more on the Lidl Plus page. Four are in GVH and all four show NORMAL = deletedPrice (VERIFIED).
- Three checked in detail, each in 3 Budapest stores:

  | Item | Lidl Plus price | GVH NORMAL | Gap |
  |---|---|---|---|
  | Pikok szeletelt paprikás kolbász | 369 | 499 | −26% |
  | Pilos mini mozzarella | 379 | 599 | −36% |
  | Freshona uborka | 429 | 515 | −16% |

- **Legal basis contested.** Lidl's page (`https://www.lidl.hu/c/a-lidl-plus-rol/s10014705`, VERIFIED) describes "Heti Lidl Plus ajánlatok és egyedi kuponok" (weekly Lidl Plus offers and individual coupons). The weekly offers "automatikusan aktiválódnak a Lidl Plus kártya beolvasásakor" (activate automatically when the Lidl Plus card is scanned), and the individual coupons are listed separately.
  - ESTIMATE: single-unit weekly Lidl Plus prices look like a "törzsvásárlói ár" (loyalty price) rather than a "kuponos" (coupon) price. §57(1)bc would then require them whenever lower than the daily price.
  - Only the főzőtejszín "2+1" is clearly a quantity discount and thus excluded.
  - So the absence is a fact, but "excluded by law" is not established. It may be a reporting gap. This is a question for GVH or counsel, not a settled exclusion.

## 5. (d) Law (VERIFIED, njt.jog.gov.hu/jogszabaly/2025-50-00-00, fetched 08:08 UTC)
- **§66(5)**, verbatim: "Nem kell adatot szolgáltatni a termékről az árfigyelő rendszerbe, ha a kereskedelmi tevékenységgel érintett termék megszakítás nélküli forgalmazási időszaka legfeljebb egy hónap." (No data need be sent about a product whose uninterrupted selling period is at most one month.)
- **§57(1)bc**: the loyalty price is recorded "ha a törzsvásárlói ár – ide nem értve a kuponos, továbbá mennyiségi kedvezményhez kötött bruttó eladási árat – alacsonyabb mint a napi ár" (if the loyalty price, excluding coupon and quantity-discount prices, is lower than the daily price).
- **§55 point 5** defines napi ár (daily price) and **§55 point 10** defines korábbi ár (earlier price). §66(1) sets upload by the end of the previous day. §71(1)c makes it a violation when the in-store price or loyalty price is higher than the price recorded in GVH.
- The "Csak most!" = ≤1 month link remains an inference. Not verified per item.

## 6. (e) Share of each chain's weekly offers that is in GVH at all (COMPUTED, full enumeration)

| Chain | Valid today | Total in GVH | Food | Non-food | Share |
|---|---|---|---|---|---|
| Penny | 333 | 18 sure (21 incl. likely variant matches) | 14 | 4 sure (Flóraszept ×2, Wippy ×2); 3 likely (Amodent 100 ml ×2, Gliss sampon 250 ml) | **5.4–6.3%** |
| Lidl | 70 (72 incl. the Lidl Plus-page extras) | 8 | 8 (4 priced + 4 Lidl Plus) | 0 | **11.4%** (11.1%) |
| Aldi | 39 | 10 | 8 | 2 (Kokett papírtörlő, mosószer 4.2 l) | **25.6%** |

- Lidl's branded detergents (Formil, Igel, Baba) are in GVH only in other pack sizes.
- Caveat: Aldi's denominator is the 39 highlighted teasers, not Aldi's whole leaflet.

## 7. What the notes missed
1. **GVH carries promos that the chain's website does not list.**
   - Penny karfiol (`penny-347`): XLSX 699 → 999 → **699** on 11, 12 and 13 Oct. Today the API shows DISCOUNTED 699 / NORMAL 999 chain-wide (248 stores, 3/3 Budapest stores).
   - Karfiol appears on none of Penny's 695 current and next-week tiles.
   - The notes read the 12 Oct rise as "end of weekend deal"; the price is back at 699 today.
2. **DISCOUNTED is not the same as a leaflet promo.** These Penny DISCOUNTED entries are stable on 11–13 Oct and absent from Penny's current offers:

   | Item | DISCOUNTED | NORMAL |
   |---|---|---|
   | Penny hasábburgonya | 599 | 649 |
   | Penny sütőben süthető burgonya | 649 | 849 |
   | Casablanca crema szemes | 4599 | 4799 |

   A deal badge driven by DISCOUNTED will include such long-running reductions. 19 Penny DISCOUNTED entries against 15 leaflet ids.
3. **productMinAmount ignores LOYALTY.** Penny sörfelvágott shows LOYALTY 349 but productMinAmount 399; Penny spagetti shows LOYALTY 339 but productMinAmount 399. The XLSX also omits LOYALTY (Wippy 599, while LOYALTY is 399).
4. **The Thursday day one was not observed**, and no archive can fill it. A daily snapshot on Thursdays is needed to prove day-one capture for 298 of Penny's 333 offers.
5. **Belbake búzaliszt misclassification** (§2.5).
6. **The 26 was the population, not a sample.**
   - The conditional 100% is partly tautological: an item is "in scope" because GVH lists it.
   - The informative test is whether any product that GVH does list for the chain is on promo at a non-promo GVH price.
   - That count is **0** today across 32 sure offer matches (35 including likely ones), excluding Lidl Plus: Penny 18 (+3), Lidl 4, Aldi 10.
   - Food items were checked through the API and the XLSX; non-food items through the XLSX min = offer price (pack price for Aldi).
7. **Two plausible reportable-but-missing promos** remain open (§2.4): Penny Zsúrkenyér 500 g and Lidl Omnia Silk szemes 1 kg.

## 8. Files (this folder)
- Scripts:
  - `scripts/fetch.py`, `gvh_crawl.py`, `type_counts.py`, `match_offers.py`, `price_eq_scan.py`, `aldi_scan.py`, `build_items.py`, `promo_api_check.py`, `dayone.py`, `scope_scan.py`, `summarize.py`.
  - Parsers copied from the original stream: `penny_tiles.py`, `lidl_grid.py`, `aldi_teasers.py`, `xlsx_parse.py`.
- Data:
  - `data/gvh_food_listing_2026-10-13.json`, `data/type_counts_food_2026-10-13.csv`, `data/x_2026-10-13.json`.
  - `data/offers_matched.json`, `data/items_in_gvh.json`, `data/promo_api_check_2026-10-13.json`, `data/promo_capture_2026-10-13.csv`, `data/scope_scan.json`.
  - Offer parses: `data/penny_*.json`, `data/lidl_*.json`, `data/aldi_offers.json`.
- Raw downloads (untrusted): `dl_penny/`, `dl_lidl/`, `dl_aldi/`, `dl_gvh/`, `dl_xlsx/`, `dl_njt/`, `dl_wayback/`.

---

# Verify: gap-gvh-promo-and-stability, lens = stability, ranking, data operations

Checked on 2026-10-13, 10:05–10:20 CEST (08:05–08:20 UTC). Adversarial pass over notes §0, §2, §3, §4 and §5, using today's data.

Labels:
- **VERIFIED (url)**: read from a live response.
- **COMPUTED (method)**: calculated from data I pulled or from the stream's parsed files.
- **ESTIMATE**: my reasoning.

Folder `verify_stability/`:
- `dl_xlsx/`, `dl_api/`: untrusted downloads.
- `scripts/`: my code, all run with `python3 -I`. `xlsx_parse.py`, `xlsx_diff.py`, `basket_hist.py`, `item_stability.py` and `gvh.py` are copies of the stream's scripts, read in full before running. In `gvh.py` the UA is set to `market-research-bot/0.1` and the gap to 1.1 s.
- `out/`: parsed files and results.

Politeness: no more than 1 request per second per host. About 100 API calls and 7 CDN calls in total. No logins and no forms.

---

## Verdict summary

| # | Claim (notes) | Verdict | Today's evidence |
|---|---|---|---|
| 1 | 1.8% of food product×chain pairs change min or max per day (§0, §2.2); "about 2–3% on a non-Thursday day" | **partly true** | 12→13 Oct: **1.15%** (64/5,545). The 1.76% for 11→12 Oct and the 2.60% for 8→9 Apr 2025 reproduce exactly. The figure is one day's value; three daily observations span **1.15–2.60%**. |
| 2 | 3.7% of pairs change store count by ≥5% of the chain's stores; about 33% change store count at all; 1.4% cross the 80% line | **confirmed** | 12→13: **3.46%**, 34.1% and 1.24% |
| 3 | 0.2–0.3% of pairs appear or disappear | **partly true** | Each direction alone fits: gone 0.29%, new 0.27% today. Combined churn (gone+new over common pairs) is **0.56%** today and 0.34% for 11→12, above the stated range. |
| 4 | Lidl is cheapest on the core-20 basket on all 7 dates since 2025-03-07 | **confirmed, and holds for an 8th date** | 13 Oct: Lidl 10,414 < Spar 10,805 (min variant, gap **3.8%**). Max variant: Lidl 10,414 < Auchan 11,295 (gap **8.5%**). Lidl is #1 in all 4 variants. The result holds with no median imputation and with LOYALTY prices included. |
| 5 | 17–19 of 20 items keep their cheapest chain day to day | **confirmed** | 12→13: **19/20** (min, max and min_w50). Counting ties properly (same set of cheapest chains): 18/20. |
| 6 | "Aldi has the most item×date wins (54 of 180)" (§3.2) | **refuted** (a tie-break artifact) | 67 of 180 cells are exact ties, and the script breaks them alphabetically, so Aldi wins every tie it is in. Unique wins: Auchan 26, Lidl 22, Tesco 22, Aldi 16. Splitting ties fractionally: Lidl 39.9, Auchan 33.6, Tesco 29.7, Aldi 28.0. |
| 7 | XLSX regenerates at about 02:00 UTC; "the data change around midnight"; "XLSX appears by 04:00 CEST" (§4.5, §5) | **partly true** | XLSX Last-Modified is 02:00:12 GMT on 11, 12 and 13 Oct (04:00:12 CEST). **The API switches between 23:50 and 00:05 UTC (01:50–02:05 CEST), not at Budapest midnight.** The stream's own poller logged only `t0`, and §5 is still `RESULTS_PLACEHOLDER`. |
| 8 | The 19 Budapest "no-data" stores return 0 | **confirmed (5/5 re-checked)** | spar-191, tesco-1046, spar-193, tesco-1008 and spar-60 all return count 0 for leaves 2, 14, 31 and L2 2034. They are still listed in `/shops`. The controls spar-190 and tesco-1025 return data. |

---

## (a) Today's XLSX and the day-over-day diff

**File (VERIFIED, https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx?v=v13-…-vs, fetched 08:06:06 UTC):**
- Sheet "Napi feltöltések - **2026-10-13**"
- Last-Modified **Tue, 13 Oct 2026 02:00:12 GMT**; ETag 0x8DF28CDB7AA9117
- 2,087,076 bytes; SHA-256 3f874738…54edbf3b8
- 25,392 rows; no duplicate (id, chain) keys; every category id is in `leaf_categories.csv`

Headers are in `dl_xlsx/h_cb.txt`.

**Diff.** The stream's `xlsx_diff.py` and my independent `indep_diff.py` (which compares the raw text) agree to the decimal. Food = the 6 food top categories.

| Window | Food pairs in common | min or max changed | Store count changed | Changed by ≥5% of chain's stores | Crossed 80% | Gone / new | (gone+new)/common | Food pairs with min<max |
|---|---|---|---|---|---|---|---|---|
| 2025-04-08 → 04-09 (repro) | 3,699 | 2.60% | 32.0% | 3.46% | — | 8 / 8 | 0.43% | 10.1% |
| 2026-10-11 → 10-12 (repro) | 5,554 | **1.76%** | 33.9% | 3.69% | 1.39% | 12 / 7 (0.22% / 0.13%) | 0.34% | 11.2% |
| **2026-10-12 → 10-13 (new)** | **5,545** | **1.15%** | **34.1%** | **3.46%** | **1.24%** | **16 / 15 (0.29% / 0.27%)** | **0.56%** | **11.3%** |

All COMPUTED with `scripts/xlsx_diff.py` and `scripts/indep_diff.py`; output in `out/xlsx_daily_diff_verify.csv`.

Per chain, food, 12→13 Oct, share of pairs with min or max changed (COMPUTED):

| Penny | Lidl | Aldi | Rossmann | Spar | Tesco | Auchan |
|---|---|---|---|---|---|---|
| 1.44% | 0.98% | 0.24% | 0% | 1.92% | **1.81%** | 0.74% |

Tesco changed more on Tuesday than on Monday (0.34%).

**Tuesday turnovers (COMPUTED, XLSX 12→13):**
- Penny's short promotions reverted:
  - csomós sárgarépa 299→399
  - csomós petrezselyemgyökér 549→689
  - petrezselyemgyökér girbe-gurba 349→449
- Penny karfiol went 999→699 (DISCOUNTED in the API).
- Tesco zöldpaprika 500 g went 1079→499.

ESTIMATE: "turnovers cluster on Monday and Thursday" holds for Lidl and Aldi. Penny and Tesco also move on other weekdays.

**Sampled promotions on day 2 (COMPUTED):** all 26 captured promos from `promo_capture_sample_2026-10-12.csv` still have XLSX min = max = promo price on 13 Oct.

## (b) Basket ranking today

I ran `basket_hist.py` unchanged on 11, 12 and 13 Oct. Its 11 and 12 Oct output is byte-identical to the stream's `basket_ranking_by_date.csv` (16 rows) and `basket_items_by_date.csv` (2,090 rows). This confirms that the basket definition and method were reproduced.

Core20, 2026-10-13 (COMPUTED):

| Variant | Ranking (Ft) | Gap to #2 |
|---|---|---|
| min | Lidl 10,414 (19/20 items) < Spar 10,805 < Auchan 11,286 < Aldi 11,424 < Penny 11,899 < Tesco 13,206 | **3.8%** |
| max | Lidl 10,414 < Auchan 11,295 < Aldi 11,424 < Spar 11,501 < Penny 11,899 < Tesco 14,553 | **8.5%** |
| min_w50 | Lidl 10,414 < Spar 11,175 < Aldi 11,424 < … | 7.3% |
| max_w50 | Lidl 10,414 < Aldi 11,424 < Penny 11,899 < … | 9.7% |

Cherry-pick saving versus Lidl: 9.4% (min) and 5.4% (max).

**Robustness (COMPUTED):**
- **No median imputation.** Using only the 17 items that all 6 chains carry, Lidl stays #1: 9,416 vs Spar 9,800 (gap 4.1%, min) and 9,416 vs Aldi 10,270 (gap 9.1%, max).
- **With LOYALTY prices.** I rebuilt the basket from today's API listings of the 20 leaves (`scripts/basket_api_loyalty.py`).
  - The non-LOYALTY minimum unit price equals the XLSX `min` variant on all 120 item×chain cells (0 mismatches).
  - Including LOYALTY changes nothing: no core-20 item has LOYALTY as its cheapest type today.
- **One item moved the lead.** Lidl's min-variant lead fell from 5.8% to 3.8% in one day because of one item. Lidl banana (lidl-0080000, 1 kg in the basket) went from XLSX min 379 / max 699 on 12 Oct to 579/579 on 13 Oct, adding 200 Ft. ESTIMATE: Lidl's lead over Spar in the min variant (391 Ft) is about two single-item moves wide.

## (c) Item-level stability, 12 → 13 Oct

From `item_stability.py` on the verify items (COMPUTED): **19/20** for min, max and min_w50. The changes were:
- min: Banán, Lidl → Spar
- max: Banán, Aldi → Lidl (the 12 Oct "Aldi" was a 4-way tie at 699)

**Tie problem (COMPUTED, `scripts/tie_aware_stability.py`, `scripts/tie_bias.py`):**
- `item_stability.py` sorts by (cost, chain), so an exact tie goes to whichever chain comes first alphabetically: Aldi, then Auchan, then Lidl.
- 8–9 of 20 items are exact ties on each 2026 date. Over all 9 dates, 67/180 cells are ties (min variant) and 74/180 (max variant).

Tie-aware stability, as alphabetical / identical cheapest set / overlapping set (min variant):

| Window | Alphabetical (notes' method) | Identical cheapest set | Overlapping set |
|---|---|---|---|
| 1 day (3 windows) | 18–19 | 18–19 | 18–19 |
| 6 days (2 windows) | 9–11 | 9–10 | 12–15 |
| Months | 5–7 | 2–5 | 9–11 |

- The "17–19 day to day" claim survives every definition.
- The weekly "only 9–11/20" becomes 12–16/20 once a tied chain that stays cheapest counts as keeping the item.
- The "Aldi has the most item×date wins" claim is an artifact of the tie-break; see verdict 6.

## (d) Timing

- **XLSX.** Last-Modified is 02:00:12 GMT for the 11, 12 and 13 Oct files (VERIFIED: `dl_xlsx/h_cb.txt` today; the stream's `dl_xlsx/h_*.txt` for 11 and 12 Oct). That is 04:00:12 CEST, so "by 04:00 CEST" is literally 12 s late. A job should fetch from about 04:05 CEST.
- **CDN staleness is far beyond max-age=3600** (VERIFIED: HEAD at 08:14 UTC on 13 Oct, plain URL, `dl_xlsx/head_plain_encodings.txt`):
  - `identity`, `gzip`, `gzip, deflate` and `br` still served the **12 Oct** file.
  - `deflate` served the **11 Oct** file.
  - That is more than 6 h and more than 30 h stale. A cache-buster plus a sheet-date check is mandatory.
- **API versus XLSX (COMPUTED, `scripts/api_vs_xlsx.py`).** The comparison covers the same 8 L2 food listings as the stream's poller.
  - The stream's `snap_t0` was taken at 12 Oct 22:33 CEST. Its non-LOYALTY minimum price equals the **12 Oct** XLSX min on 1,924/1,924 pairs.
  - On the 25 pairs whose XLSX min changed 12→13, the snapshot matches XLSX-12 25/25 and XLSX-13 0/25.
  - My snapshot at 13 Oct 10:08 CEST matches XLSX-13 on 1,925/1,925 pairs, and on 25/25 of the discriminating pairs.
- **When the API switched.** The stream's own poller cannot say: its log has only `start` and `t0`, `dl_gvh/midnight/` holds only `snap_t0.json`, and notes §5 is still `RESULTS_PLACEHOLDER`.
  - I used the gvh-location verifier's raw poll files (`research/gvh-location/verify2_raw/poll/*_cat31.json`, timed by file mtime), which are untrusted data.
  - Lidl banana was still **379** at 01:34, 01:35 and 01:50 CEST, and **579** from 02:05:45 CEST onward.
  - **So the switch is between 23:50 and 00:05 UTC, i.e. at about 00:00 UTC = 02:00 CEST, not Budapest midnight.** COMPUTED; the mtimes are a weaker timestamp than a log.
  - Implication: between 00:00 and 02:00 Budapest time (summer time) the API still serves yesterday's prices.
- **XLSX minimum excludes LOYALTY.** The XLSX "Minimum ár" equals the minimum over non-LOYALTY price types on 100% of pairs (COMPUTED). In the 8 categories, 21 pairs have a LOYALTY price below the XLSX min: Auchan 15, Tesco 5, Spar 1. Example: Tesco 5998200462924 has XLSX 2,990 and LOYALTY 1,999.

## (e) No-data stores, re-checked 08:10–08:11 UTC

VERIFIED via https://arfigyelo.gvh.hu/api/products-by-category/{2,14,31,2034}?shopIds=…&limit=48 and /api/shops. Output in `out/nodata_recheck_2026-10-13.csv`.

| Store | In /shops | Leaf 2 (ESL tej 1.5%) | Leaf 14 (tojás) | Leaf 31 (banán) | L2 2034 (zöldség) |
|---|---|---|---|---|---|
| spar-191 | yes | 0 | 0 | 0 | 0 |
| tesco-1046 | yes | 0 | 0 | 0 | 0 |
| spar-193 | yes | 0 | 0 | 0 | 0 |
| tesco-1008 | yes | 0 | 0 | 0 | 0 |
| spar-60 | yes | 0 | 0 | 0 | 0 |
| spar-190 (control) | yes | 4 | 18 | 1 | 35 |
| tesco-1025 (control) | yes | 5 | 17 | 1 | 27 |

As a cross-check, `/api/product/5999139403316` (S-Budget ESL milk) is available in 317 Spar shops, including spar-190 but none of the 5. Likewise `/api/product/5051007146265` (Tesco ESL milk, 193 shops) includes tesco-1025 but none of the 5.

## (f) §4 "Implications for the MVP": where today's data disagree

1. **§4.5 "The data change around midnight"** is wrong. The API switches at about 00:00 UTC (02:00 CEST, and an estimated 01:00 CET in winter). A job at Budapest midnight would label yesterday's prices as today's. The XLSX follows at 02:00 UTC, and a fetch without a cache-buster can return a file hours or days old.
2. **§4.5 "Promo turnovers cluster on Monday and Thursday"** holds for Lidl and Aldi only. On Tuesday, Penny reverted three short promotions and started one, and Tesco had its busiest food day of the three observed.
3. **§2.2 reading "on a non-Thursday day about 2–3% of food prices change"** is too high for Tuesday (1.15%). A better statement: 1–3% per day, in the 2026 data.
4. **§4.1 "uniformly across stores"** holds for promotions (26/26 still at promo price on day 2). It does not hold for every Lidl item: on 12 Oct Lidl banana had XLSX min 379 and max 699.
5. **§4.2 "Not the XLSX: it has min/max only, no price types"** is true, and the XLSX min also silently drops LOYALTY prices. Any XLSX-based price is a non-loyalty price, which matters for Auchan, Tesco and Spar.
6. Not contradicted: §4.1 (promotions on day 2), the 11% min<max share for selective per-store pulls, and Lidl as the stable basket leader.
