# Adversarial fact-check: stream "GVH Árfigyelő data: store level, location, basket economics"

Checked on 2026-10-12, 19:44–20:10 UTC (21:44–22:10 Budapest time). I re-queried the live API at 1 request per second or slower, with User-Agent `market-research-bot/0.1 (fact-check)`.

Labels used below:
- **VERIFIED**: read from a primary source or live response.
- **COMPUTED**: my own code over data I pulled, or over the stream's raw JSON files, which I treated as data.
- **ESTIMATE**: my inference.

Folders:
- `verify_raw/`: my downloads (untrusted).
- `verify_scripts/`: my code, all run with `python3 -I`.
- `verify_data/`: my outputs.

I did not re-download the XLSX or the PDFs. I checked the stream's copies against the live files' `content-length`, using a HEAD request with a cache-buster for the XLSX, and they match.

Web search was unavailable in this run: the shared per-turn search budget was used up. Points that would need a search are marked unverified. www.spar.hu returned HTTP 403, and I did not try to get around it.

---

## Biggest correction: `productMinAmount` is the 80%-of-stores price, and it is what GVH displays

The stream concluded that the listing's chain price is the per-type minimum across stores, "not the 80%-of-stores price the FAQ describes". That holds for the `prices[]` array: I reproduce 920 of 925 pairs equal to the cheapest store's NORMAL price.

But the same listing object also carries **`productMinAmount`**, which the stream never used.

- **VERIFIED (bundle `/assets/index-5baaf084.js`):** the GVH product card renders `formatPrice(c.productMinAmount)` per chain. It appends "-tól" only when `priceSameEverywhere` is false. The site therefore displays `productMinAmount`, not `prices[].amount`.
- **COMPUTED, using the stream's 925 product-chain pairs with per-store data:** `productMinAmount` follows one rule. It is the daily price (the lower of NORMAL and DISCOUNTED, excluding LOYALTY) charged by at least 80% of the chain's stores that carry the product. If no single price reaches 80%, it is the minimum. The rule matched **925 of 925** pairs, across every chain.
  - Script: `verify_scripts/pma_rule.py`.
  - In 96 of the 100 pairs whose price varies by store, `productMinAmount` equals the modal store price.
  - In the other 4, no price reaches 80% and it falls back to the minimum: the Lidl banana at 52% and three Spar pastas at 75–79%.
- **VERIFIED live, fresh sample:** the rule held on 8 of 8 pairs (`verify_scripts/live_pma.py`, `verify_raw/live/live_pma_rows.json`).
  - Don Francesco spagetti (5997490112823), Spar: `prices[]` NORMAL 294; `productMinAmount` 699; per-store prices are 296 stores at 699 and 2 stores at 294 (spar-120, spar-157). GVH displays **699**, not 294.
  - The other 7 pairs: Lidl banán kg, Tesco banán lédig, Auchan, and four more Tesco items.
- This matches the FAQ text: the system "a kereskedő üzleteinek 80%-ában alkalmazott termék árat veszi figyelembe", so individual stores "olcsóbbak is lehetnek" (https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf). **The FAQ is accurate for the displayed price.**

**Effect on the basket.** COMPUTED with `verify_scripts/basket_pma.py`, using the same 25 items, clean filter and median imputation as the stream:
- I first reproduced the stream's `prices[]` basket exactly: Lidl 13,530 / Spar 14,524 / Aldi 14,797 / Auchan 14,813 / Penny 15,446 / Tesco 16,845; cherry-pick 12,204, a saving of 9.8%.
- Using `productMinAmount` (the price GVH shows): **Lidl 13,530 < Aldi 14,797 < Auchan 14,813 < Spar 15,208 < Penny 15,446 < Tesco 16,855**.
  - Spread +24.6%.
  - Cherry-pick 12,395, a saving of **8.4%** against Lidl.
  - Spar moves from 2nd to 4th place. The difference comes from five single-store Spar minima: pasta, tomato, pepper, apple and banana.
  - Tesco is essentially unchanged.
  - Adding LOYALTY prices changes nothing.

**Implication.** An app gets a "typical chain price" directly from the listing, with no per-store calls. It needs per-store calls only for exact "this store" prices, mainly Tesco Expressz in Budapest and the rare Spar outlier store. Caveat: when no price reaches 80% (the Lidl banana: 379 Ft in 106 stores, 699 Ft in 116), `productMinAmount` is still the minimum, so it is not always "typical".

**Related correction on `priceSameEverywhere`.** COMPUTED (`verify_scripts/flag_check.py`, `flag_check2.py`):
- The **listing** flag is `true` in 17 pairs where store prices do differ. In all 17, between 82% and 99.7% of stores share one price, so the listing flag follows the 80% notion.
- The **detail** endpoint's flag reflects real variation in 924 of 925 pairs.
- So the stream's listing-based shares (Tesco 24.6%, Spar 8.0% false) understate literal store variation. Use detail or the XLSX min<max for literal variation.

---

## Verdicts on the load-bearing items

### 1. Per-store prices are public: `/product/{id}/shop/{ids}` and `shopIds=`. CONFIRMED
VERIFIED live:
- `/api/product/2804780000000/shop/<119 ids>` returned 119 stores: 118 with NORMAL 2,030 + DISCOUNTED 1,699, and 1 with NORMAL only. Exactly as the stream said.
- A 200-id chunk worked; the URL was about 1.3–2.5 KB.
- `products-by-category/31?shopIds=tesco-4062,lidl-274,spar-8251` returned only those stores' products at store prices. The Tesco Teréz krt. banana is 739 Ft against the chain's `productMinAmount` of 699.

Minor note: `pricesMax` in the detail response held only NORMAL for that product.

### 2. Official daily XLSX. CONFIRMED, with operational corrections
VERIFIED:
- Footer link in the bundle.
- Origin `last-modified` Mon, 12 Oct 2026 02:00:12 GMT, 2,087,294 bytes, the same as the stream's copy.
- Sheet `Napi feltöltések - 2026-10-12`; 14 columns as listed.

COMPUTED with my own parser (`verify_scripts/xlsx_verify.py`):
- 25,400 rows, 16,040 products, 161 categories.
- Food: 5,561 pairs and 4,332 products.
- Share of food pairs with min<max: Tesco 39.9%, Spar 11.1%, Auchan 2.0%, Lidl 1.5%, all others 0%; all food 11.2%; all pairs 7.6%.
- Maximum availability per chain: Spar 317/375, Tesco 193/197, Rossmann 268/280, dm 253/259.

All of these match the stream.

Corrections:
- (a) **The CDN serves a stale file by default.** Three plain HEAD requests at 19:47 UTC each returned the 11 Oct file (`x-cache: TCP_HIT`, 2,089,159 bytes), about 41 h old despite `max-age=3600`. Only a cache-busting query (`?nocache=…`) returned the 12 Oct file. This is the normal behaviour, not one stale edge. A daily job must add a cache-buster and check the sheet-name date.
- (b) Prices and counts are stored as **text with a decimal comma** ("1699,0000"); a naive float parse fails.
- (c) The file has only min and max per chain, **no 80% price and no LOYALTY**. Spaghetti shows min 294 / max 699, so it carries the same single-store-minimum bias the stream criticises. The listing's `productMinAmount` does not have this bias. "Lowest-risk backbone" is fair; "sufficient chain price" is not.

### 3. No public price history. CONFIRMED
VERIFIED, njt (https://njt.jog.gov.hu/jogszabaly/2025-50-00-00, consolidated text dated 2026.10.01):
- §57(4): price data are archived after they change.
- §57(5): access to archived data only for the listed ministers, courts, NKFH and KSH.
- §57(6): deletion after 10 years.
- §70: "nem archivált adatok nyilvánosak".
- §66(1): upload by the end of the previous day.
- Chapter V has no sunset clause. Several other chapters of the same act end on 2026-12-31.

FAQ: "csak azon a napon érhetők el nyilvánosan … a következő napon … archiválásra kerülnek".

VERIFIED: dated XLSX URLs for 2026-10-11, 2026-10-12, 2026-10-01, 2025-03-12 and 2025-03-14 return 404. Only the 2025-03-13 file exists, and the directory listing is 404.

Nuance: §70 does not literally say "only". The restriction comes from reading it together with §57(5). Third parties such as Árnéni, and Lidl for its advertising, keep their own daily history.

### 4. Listing chain price = per-type minimum, not the FAQ's 80% price; chain prices overstate savings. PARTLY TRUE
- True for `prices[]`: 920 of 925.
- False as a statement about "the chain price the listing returns": the listing also returns `productMinAmount`, the 80% price GVH displays (925 of 925, see above).
- The FAQ is not contradicted.
- The spaghetti is not "listed at 294 Ft" on the site; it is displayed at 699 Ft. 294 Ft appears only in `prices[]` and in the XLSX minimum.
- Overstatement occurs only if you use `prices[]` or the XLSX minimum. With `productMinAmount`, Spar's basket rises by 684 Ft (4.7%), Tesco's by 10 Ft, and the cherry-pick saving falls from 9.8% to 8.4%.

### 5. Listing shows at most 3 chains; 48-row page cap; top-level ids return count 0. CONFIRMED
- COMPUTED over the stream's 422 listing pages: chains per product is 1 for 11,823 products, 2 for 1,604 and 3 for 2,613; never more than 3.
- VERIFIED live for Gillette 3014260223007 in `products-by-category/157` and `/search`: dm 1,255, Tesco 1,389 and Rossmann 1,413 are shown. Detail adds **Spar 1,290 (43 stores)**, cheaper than Tesco and Rossmann, and Auchan 1,449 (2 stores).
- The three chains shown are the ones with the most carrying stores (92, 184 and 179 against 43 and 2), consistent with "drops low-availability chains".
- `limit=200` on category 50 returned 48 of 162. Category 1001 returned count 0.

### 6. 84% of food SKUs are sold by only one chain. PARTLY TRUE (number right, explanation wrong)
- COMPUTED: 3,632 of 4,332 = 83.8%. The distribution (1: 3,632; 2: 362; 3: 222; 4: 69; 5: 27; 6: 15; 7: 2; 8: 3) matches exactly.
- But the explanation "private label or in-store variable-weight codes" is inaccurate. Of the 3,632 single-chain products:
  - **2,337 have ordinary GTIN barcodes** (many are brands that only one reporting chain lists; Auchan alone has 1,023 single-chain food SKUs),
  - 955 are chain-internal ids such as `lidl-…`, `aldi-…` or `penny-…`,
  - 327 are in-store codes starting with 2.
- Chain-internal ids also prevent barcode matching for branded goods that Lidl, Aldi or Penny list under their own codes.
- The design conclusion stands: match at leaf-category level plus name and unit, not by barcode.

### 7. Store data: 1,829 stores; opening hours only for Lidl; about 7% of Budapest food stores without data. CONFIRMED, minor corrections
- VERIFIED from `/api/shops`, refetched:
  - 1,829 stores; 419 in Budapest, by postal code and by city name alike.
  - Food chains: 1,256 stores, 282 in Budapest. Per-chain counts are identical to the stream's.
  - `openingTime` filled in for 224 stores: Lidl 222, Aldi 1 (J233), Auchan 1 (auchan-220).
  - Fields are only uuid, postalCode, city, address, chainStoreUuid, location and openingTime. There is no name or format field.
  - Rossmann Zalaegerszeg Platán sor 8 is about 111 km off; it is the only store more than 20 km from its city's median position.
- Correction: the endpoint is `/api/shops`, not `/api/stores`.
- Correction: **19, not 20,** Budapest food stores have no data: **17 Spar + 2 Tesco (6.7%)**. Both my recount from the stream's 1,135 detail files and the stream's own `data/budapest_store_basket.csv` (19 rows with 0 items) give 19.
- VERIFIED live: `shopIds=spar-171`, `spar-193` and `tesco-1008` each return count 0 in categories 2034, 2001 and 2050, while `spar-190` returns 36, 24 and 43.
- The national "12 Rossmann / 6 dm" figures come from the XLSX maximum per product, which is a lower bound. From food-only detail files I get Rossmann 104, but that sample is food-biased, so the national drugstore figure is not well established.

### 8. Location: the best price changes mainly through which chains are near; the nearest store is a Spar costing 21–27% more at 4 of 5 points. PARTLY TRUE
- COMPUTED (`verify_scripts/nearest.py`): the nearest-store identities and radius chain sets reproduce exactly.
- COMPUTED (`verify_scripts/tesco_fmt.py`): Tesco 4xxx stores in Budapest average 1.0352× the chain minimum and 1xxx stores 1.0006×, matching the stream.
- The between-chain versus within-chain logic holds: Aldi and Penny have 0% variation in the XLSX; Lidl 1.5%.

Caveats the stream understated:
- (a) "Nearest food store" means the nearest of the **6 reporting chains**. /shops lists only obligated retailers' own stores. CBA, Coop, Príma, Reál, SPAR partner (franchise) stores and others are absent, and in Budapest they are common. This is an ESTIMATE; I could not verify counts because search was unavailable.
- (b) The "premium" is often a choice between almost equally near stores:

  | Point | Nearest store | Cheaper alternative |
  |---|---|---|
  | Nyugati | Spar 52 m | Lidl 146 m |
  | Határ út | Spar 216 m | Aldi 525 m, Lidl 632 m |
  | Újpest | Spar 139 m | Lidl 694 m |
  | Örs | Spar 17 m | Aldi 1,084 m, Lidl 1,654 m |

  Express the saving per extra metre walked, not as "nearest versus best".
- (c) The Tesco 4xxx premium is **Budapest-specific**: 1.0069 outside Budapest, and 52% of Budapest 4xxx price observations are above the chain minimum against 12% elsewhere. It is better described as a Budapest small-store pricing zone than as a format effect.

---

## Other checks (confirmed)
- 1-month reporting exemption: the retailer ÁFF says no reporting is needed "ha … termék megszakítás nélküli forgalmazási időszaka legfeljebb egy (1) hónap" (https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_kereskedo.pdf; same size as the live file, last modified 2025-10-06). Nuance: enforcement works through GVH forwarding complaints and notifying the government office (fogyasztóvédelmi hatóság) under XIII. It is not automatic. The 4-hour clause is a duty to report IT outages; nothing explicitly says it excuses missed uploads.
- Lidl/GVH case (economx, 2025-11-13): closed with commitments and **no infringement found**. The commitments are: always cite Árfigyelő; a ≥2.5% gap for monthly claims; at least one more cheapest day for whole-month claims. **It was a misleading-advertising case, not a ruling on data re-use rights**, so it is weak evidence about API or commercial re-use. Lidl's method used monthly averages of daily basket prices over 62 categories, so Lidl itself keeps daily history.
- API operations: no `content-encoding` with `Accept-Encoding: gzip, br`; `x-cache: TCP_MISS` on an identical repeat. Search: `zabpehely` gives 4 hits (oat flour ×3, soap); `passata` 0; `só` HTTP 400. All confirmed.
- No 2026 Árfigyelő press release on gvh.hu/sajtoszoba/sajtokozlemenyek (no open-data or API announcement found).

## Things the stream missed
1. `productMinAmount` = the 80%-of-stores daily price, displayed by GVH. It gives a "typical chain price" directly from the listing, removes most of the need for per-store calls in a chain-level MVP, and reconciles the FAQ with the API.
2. The listing `priceSameEverywhere` follows the 80% rule; the detail flag is literal.
3. The XLSX CDN serves a 1–2-day-old file by default; a cache-buster is needed, plus a date check on the sheet name.
4. XLSX numbers are text with a decimal comma.
5. /shops excludes non-obligated retailers and franchise stores. "Nearest store" analyses must say "nearest reporting store".
6. Most single-chain food SKUs are GTIN-coded brands, not private label. Chain-internal ids block barcode matching.
7. The Tesco Expressz premium is Budapest-specific.
8. The 19 no-data Budapest stores include large sites (e.g. Tesco Koppány u., Spar Árkád Örs). Whether they are closed, INTERSPAR formats or failing to report is unknown; checking over several days, or asking GVH, is needed. Unverified.
9. A possible public history proxy, KSH monthly average consumer prices, was not checked (search unavailable). Unverified.

## Files
- Scripts: `verify_scripts/shops_check.py`, `pma_check.py`, `pma_rule.py`, `flag_check.py`, `flag_check2.py`, `live_pma.py`, `xlsx_verify.py`, `basket_pma.py`, `nearest.py`, `tesco_fmt.py`
- Data: `verify_data/basket_pma.csv`, `verify_data/xlsx_rows_verify.json`, `verify_raw/live/live_pma_rows.json`
