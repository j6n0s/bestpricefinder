# GVH Árfigyelő: store level, location and basket economics (stream: gvh-location)

Data were pulled on 2026-10-12 between 19:00 and about 19:50 UTC (21:00–21:50 Budapest time).
Labels used throughout:
- **VERIFIED**: read directly from a primary source (URL given) or from the live API response.
- **COMPUTED**: calculated from data I pulled; the method is stated.
- **ESTIMATE**: my reasoning or extrapolation.

Folders under `research/gvh-location/`:
- `raw/`: untrusted downloads (API JSON, PDFs, the official XLSX).
- `scripts/`: my Python. Every script was run with `python3 -I`.
- `data/`: CSV and JSON outputs.

## 1. How the API works (from the site's JS bundle `/assets/index-5baaf084.js`, VERIFIED)

The axios client uses `baseURL:"/api"` with a 30 s timeout. The bundle declares these endpoint constants:
`/shops`, `/chain-stores`, `/products-by-category`, `/search`, `/product`, `/product/%productId%/shop/%storeId%`, `/categories`.
It has no other data endpoint: no history, no timestamp, no "last updated" call. The only other remote calls go to Google Maps.

| Call (as the bundle builds it) | Parameters | What comes back |
|---|---|---|
| `GET /api/products-by-category/{catId}` | `limit`, `offset`, `shopIds` (comma-joined store uuids; sent only when the user has turned on "only favourite stores") | `{products,count}`. **The server caps a page at 48 rows** (limit=200 and limit=1000 both returned 48). Works for leaf ids and level-2 ids (2xxx). Top-level ids (1xxx) return `count:0`. |
| `GET /api/search` | `q`, `limit`, `offset`, `shopIds` | Same shape. A 2-character q (`só`) returns HTTP 400 `SEARCH-INPUT-ERROR`. |
| `GET /api/product/{id}` | none | Detail. `chainStores[]` holds `prices` (min per price type), `pricesMax` (max), `priceSameEverywhere`, and **`availableInShops` (the full list of store uuids that carry the product)**. Returns **all** chains selling the product. |
| `GET /api/product/{id}/shop/{uuid1,uuid2,...}` | store ids comma-joined, URL-encoded | `{shops:[{shopUuid, prices:[{type,amount,unitAmount}]}]}`. **The actual per-store price.** 119 and 200 ids per call both worked. The longest URL I sent was 2.5 KB. |
| `GET /api/shops` | none | 1,829 stores: uuid, postalCode, city, address, chainStoreUuid, location{lat,lon}, openingTime |
| `GET /api/chain-stores` | none | 9 chains: uuid, name, imageUrl |
| `GET /api/categories` | none | Tree: 9 top, 42 level-2, 161 leaf categories (VERIFIED by count) |

Key behaviours (VERIFIED by experiment):
1. **`shopIds` filter = store-level view of a category.** Example: `products-by-category/18?shopIds=tesco-4030` returned 6 of the 37 csirkemell products. Those are only the ones that store carries, and each carries that store's own prices. Its DISCOUNTED price was absent, because that store had no discount. This is exactly the "near me" query the GVH site runs for favourite stores.
2. **The listing (`products-by-category`, `search`) shows at most 3 chains per product.** I compared it with the official daily XLSX (section 5). 1,570 products (2,530 product-chain pairs) appear in the XLSX with a chain the listing does not show. Every one of those products shows exactly 3 chains in the listing. The chains it drops are low-availability ones, and **in 57 cases the hidden chain was cheaper**. Example: Gillette Satin Care, EAN 3014260223007. The listing shows dm, Tesco and Rossmann. The detail endpoint also shows Spar at 6,450 Ft, below Tesco's 6,945, and Auchan. For food this affects about 116 products, because 84% of food SKUs are sold by only one chain. **Use the detail endpoint or the XLSX for chain completeness, not the listing.**
3. **`priceSameEverywhere`** is a chain-level flag. It is `false` when any store's price list differs, including when a DISCOUNTED price applies only in some stores. Example: the Tesco pultos csirkemell (2804780000000) had NORMAL 2,030 in all 119 stores and DISCOUNTED 1,699 in 118 of them, so the flag was false. In the listing, each price type also carries `sameAmountEverywhere`.
4. **The listing/detail "chain price" is the per-type MINIMUM across the chain's stores, even when only 1–2 stores charge it.** COMPUTED on 925 product-chain pairs: the listing NORMAL price equalled the cheapest store's NORMAL price in 920/925 (99.5%) and the most common store price in only 901/925.
   Examples:
   - Spar Don Francesco spagetti 500 g: the listing says 294 Ft. 296 stores charge 699 Ft; only 2 Budapest stores (Böszörményi u., Bessenyei u.) charge 294.
   - Spar "Étkezési paprika lédig": the listing says DISCOUNTED 399 Ft/kg. 312 stores charge 853; one store (Hódmezővásárhely, Kaszap u.) has the 399 discount.
   - The same single Spar store drives the listing's DISCOUNTED prices for paradicsom and alma, and with a Szombathely store for banán.

   The GVH FAQ (https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf) says the ranking uses "a kereskedő üzleteinek 80%-ában alkalmazott" price and that individual stores may be *cheaper*. The prices the API returns do not follow that rule; the 80% rule may apply only to sort order. **For a "near me" app, chain-level prices from the listing overstate what a typical Spar or Tesco shopper pays.**
5. Price types are `NORMAL`, `DISCOUNTED` and `LOYALTY`. Under the law, the loyalty-card price is the lowest price reachable with a loyalty discount, excluding coupons and quantity deals. It is recorded only if it is below the daily price.
6. Product `bulk` differs between listing and detail for the same product (`false` vs `true` for 2804780000000), so don't rely on it.

## 2. Stores: `/api/shops` (question a)

File: `data/stores.csv`, one row per store with uuid, chain, postalCode, city, address, lat, lon, openingTime and a Budapest flag. Script: `scripts/shops_analysis.py`.

| Chain | Stores, Hungary | Budapest (postal code 1xxx) | Coordinates present and inside Hungary | openingTime filled in |
|---|---|---|---|---|
| Spar | 375 | 114 | 375 | 0 |
| Rossmann | 280 | 55 | 280 | 0 |
| dm | 259 | 76 | 259 | 0 |
| Penny | 248 | 30 | 248 | 0 |
| Lidl | 222 | 46 | 222 | **222** |
| Tesco | 197 | 39 | 197 | 0 |
| Aldi | 188 | 48 | 188 | 1 |
| Müller | 34 | 6 | 34 | 0 |
| Auchan | 26 | 5 | 26 | 1 |
| **Total** | **1,829** | **419** | 1,829 (100%) | 224 (12.2%) |

All counts are VERIFIED from the API on 2026-10-12. The "postal code 1xxx" and "city starts with Budapest" definitions give the same 419.
- The 6 food chains have **1,256 stores, 282 of them in Budapest**. The 3 drugstore chains have 573, of which 137 are in Budapest (COMPUTED).
- External totals differ by date: GVH press in 2026 said 1,817 stores; an economx article of 2025-11-13 citing GVH said 1,799.
- **Coordinates:** 100% present, and none fall outside Hungary. No duplicate coordinate pairs. Precision ranges from 3 to 15 decimals; 26 stores have only 3 decimals (about ±50–100 m). A sanity check against each city's median store position found **1 clear coordinate error**: Rossmann Zalaegerszeg, Platán sor 8, has latitude 47.84 instead of about 46.84, roughly 111 km off. It also found 1 postal-code error: Rossmann Komló has postal code 2900, which belongs to Komárom. Tesco "Pablo Neruda 1-2" has postal code 1036 but the street is in Békásmegyer. Everything else passes. **Coordinates are good enough for 1–2 km radius search as they are.** (COMPUTED, `scripts/shops_outliers.py`.)
- **Opening hours are effectively missing.** Only Lidl fills them in, as a string like `Nyitvatartás: 06:30-21:30#Nyitvatartás - Vasárnap: 07:00-19:00`, plus one Aldi and one Auchan. The app needs another source: chain store-finders, OpenStreetMap `opening_hours`, or Google Places. My one OSM Overpass attempt failed with a server timeout; not retried.
- **No store name or format field.** The site builds a label from postal code, city and address. Format can be inferred from the uuid scheme. Tesco `tesco-1xxx` (112 stores) are hypermarkets and large stores, for example Budapest Koppány u., Hengermalom u., Bécsi út 258. `tesco-4xxx` (67) are Expressz and small stores, for example Teréz krt. 55-57 and Kálvin tér 7. Assortment size per store confirms this (section 3).
- Store ids follow chain-specific patterns: `spar-110`, `penny-58`, `lidl-316`, `aldi-J179`, `auchan-007`, `tesco-4064`, `dm-345`, `rossmann-…`, `mueller-…`.
- Budapest food stores by district (COMPUTED): from 3 (I., XII. kerület) to 26 (XI.). Spar is everywhere (114). Auchan has only 5 Budapest stores, all on the outskirts (III, X, XI, XXI, XXIII).

## 3. Store-level price differences within the same chain (question b)

**Method (COMPUTED).** I took all 814 products in the 25 basket leaf categories, plus 321 products in 12 extra staple categories.
- For each product: `GET /api/product/{id}` (gives min/max and `availableInShops`).
- For every basket-category product, and every extra product with `priceSameEverywhere=false`: `GET /api/product/{id}/shop/{all carrying stores}`, in chunks of 200 ids.
- Totals: 1,135 detail calls (2.53 MB) and 1,176 per-store calls (13.47 MB). These returned **118,137 store-price observations**.
- Scripts: `scripts/storelevel.py` (collection), `scripts/variation.py`, `scripts/format_effect.py`, `scripts/decompose.py`.
- Outputs: `data/store_price_variation.csv` (one row per product × chain × scope), `data/staples_store_variation.csv`, `data/budapest_store_decomposition.csv`.

**Share of product-chain pairs whose NORMAL price differs between stores (basket and extra categories):**

| Chain | Pairs (national) | Pairs with any NORMAL difference, national | Same, Budapest only | Median max/min spread where it varies | Median share of chain stores carrying the product |
|---|---|---|---|---|---|
| Aldi | 84 | 0% | 0% | – | 100% |
| Penny | 69 | 0% | 0% | – | 100% |
| Lidl | 84 | 1.2% (one banana SKU: 379 Ft in 106 stores, 699 Ft in 116; Budapest mostly 379) | 1.2% | 84% | 100% |
| Auchan | 282 | 1.1% (4.6% counting loyalty prices) | 0.8% | 5% | 73% (Budapest 60%) |
| Spar | 197 | 9.6% (12.7% counting all types) | 7.1% | 61% (outlier single-store prices) | 63% |
| Tesco | 172 | **37.8%** | **38.1%** | 6.3% (p90 13%) | 72% (Budapest 38%) |
| dm / Rossmann / Müller | 39 | 0% | 0% | – | – |

**Whole-catalogue cross-check from the official XLSX** (all 5,561 food product-chain pairs; COMPUTED in `data/xlsx_chain_price_uniformity.csv`). Share of pairs where min < max across stores:
- Tesco 39.9% (median spread 8.2%)
- Spar 11.1%
- Auchan 2.0%
- Lidl 1.5%
- Aldi, Penny and the drugstores 0%

Across all 25,400 pairs the figure is 7.6%. The XLSX flag and the API's `priceSameEverywhere` matched the observed store data in **100%** of the 927 pairs I checked. The only exceptions were 12 pairs that varied only in a loyalty price, mostly Auchan's −30% loyalty deals in a few stores.

**About 40 staples:** these are the 146 product-chain pairs picked as cheapest per basket item per chain (`data/staples_store_variation.csv`).
- Nationally, 19 of 146 show any store-to-store difference: Tesco 10, Spar 6, Auchan 2, Lidl 1, Aldi 0, Penny 0.
- In Budapest, 14 of 144 do.
- Tesco differences are small, mostly +2–10% at some stores. Examples: banán 699/729/739; zöldborsó 753→842; brokkoli 1,438→1,518; TS spagetti 650→890.
- Spar differences are single-store anomalies that drag the chain-level price down (section 1, point 4).

**Where the differences come from (COMPUTED, `format_effect.py`).** Store NORMAL price as a mean ratio to the cheapest store, by store-id group:
- Tesco `1xxx` (hypermarkets) 1.0006
- Tesco `4xxx` (Expressz) 1.0156 nationally and **1.035 in Budapest**
- Tesco `5xxx` 1.026
- Spar 1.047–1.072, because the chain minimum is often a 1–2-store price
- Lidl 1.006, Auchan 1.007

Assortment differs much more than price. Products carried from the fetched categories, as a median per store:
- Tesco hypermarket 184 vs Expressz 99
- Spar 144–214
- Aldi 114 in every store, Lidl 106–113, Penny 91–94

**Budapest single-store basket** (25-item basket below; best price incl. discounts; missing items imputed at the Budapest median; 257 stores with at least 20 of 25 items):

| Chain | Stores | p10 | Median | p90 | Max |
|---|---|---|---|---|---|
| Lidl | 46 | 13,529 | 13,529 | 13,849 | 13,849 |
| Aldi | 48 | 14,797 | 14,797 | 14,797 | 14,797 |
| Penny | 30 | 15,446 | 15,446 | 15,518 | 15,518 |
| Spar | 95 | 15,661 | 16,386 | 17,210 | 17,769 |
| Auchan | 4 | 15,697 | 16,137 | 16,138 | 16,581 |
| Tesco | 34 | 16,536 | 16,855 | 17,077 | 19,117 |

COMPUTED, `data/budapest_store_basket.csv` and `data/budapest_store_decomposition.csv`:
- **Between chains:** the median store ranges from 13,529 (Lidl) to 16,855 (Tesco), **+24.6%**.
- **Within a chain (p10→p90):** Spar 9.9%, Tesco 3.3%, Lidl 2.4%, Aldi and Penny 0%. Full range: Spar 15.6%, Tesco 20.4% (one outlier, Tesco Ady Endre u. 99, XXII).
- Spar's within-chain gap splits roughly into assortment (median +1,178 Ft against a "chain-best" basket) and store price (median +801 Ft).

**Conclusion (question b).** Location changes the best price **mainly through which chains are near you**: about 25% between chains against 0–10% within a chain.
- Store-level price differences matter only for **Tesco** (Expressz/small formats, about +3.5% in Budapest) and **Spar** (assortment plus a few odd store prices).
- Aldi, Penny and practically Lidl charge one national price.
- Within-chain, **assortment** matters as much as price: whether the small store carries the cheap private-label pack.
- The app needs per-store *availability* more than per-store *prices*.

## 4. Basket economics (question c)

**Basket:** a healthy week for 2 adults, 25 items, each mapped to one GVH leaf category (`scripts/basket_def.py`). Quantities are an ESTIMATE of a realistic week:
- 0.8 kg csirkemellfilé, 0.5 kg pulykamellfilé, 0.4 kg tengeri halfilé
- 10 db tojás, 1 kg natúr joghurt, 0.5 kg tehéntúró, 2 l ESL tej 1,5%, 0.2 kg trappista
- 1.5 kg teljes kiőrlésű kenyér, 0.5 kg rizs, 0.5 kg száraztészta, 0.5 kg lencse, 0.25 l extra szűz olívaolaj
- 1 kg paradicsom, 0.6 kg zöldpaprika, 2 db kígyóuborka, 1 kg sárgarépa, 1 kg vöröshagyma, 0.1 kg fokhagyma, 0.5 kg brokkoli, 1.5 kg burgonya, 1 kg fejes káposzta
- 1.5 kg alma, 1 kg banán, 0.45 kg fagyasztott zöldborsó

Rule: per chain, take the cheapest unit price in the leaf category among products whose unit matches, × quantity. A "clean" filter drops obvious misfits. Examples: refined or flavoured "olive oil" in the extra-virgin category; a trappista mislisted under natúr joghurt (Spar "Tejmalom érlelt trappista" sits in category 7); breaded fish in halfilé.

**A. Chain-level listing prices** (what the GVH site and most competitors show). COMPUTED, `data/basket_per_chain.csv` and `data/basket_items_national.csv`. Values in Ft; missing items imputed at the cross-chain median.

| Chain | Items found | All price types | NORMAL only | Common 21 items, all types |
|---|---|---|---|---|
| Lidl | 24 (no kg-priced garlic) | **13,530** | 13,730 | 12,258 |
| Spar | 25 | 14,525 | 15,525 | 13,245 |
| Aldi | 24 (no rice) | 14,797 | 14,797 | 13,369 |
| Auchan | 23 (no cucumber, no cabbage) | 14,813 | 15,072 | 13,531 |
| Penny | 25 | 15,446 | 15,766 | 14,369 |
| Tesco | 25 | 16,845 | 17,746 | 15,770 |
| **Cherry-pick across 6 chains** | 25 | **12,204** | **12,908** | 11,146 |

- **Spread:** most expensive vs cheapest chain is +24.5% (all types) and +29.2% (NORMAL only); on the 21 common items, +28.7%.
- **Cherry-picking saves 9.8%** against the best single chain (Lidl) with all price types, and **6.0%** with NORMAL only. On the common items, 9.1%.
- **LOYALTY prices never changed any cheapest pick in this basket.** "All" and "no-loyalty" are identical. DISCOUNTED prices are worth 0–1,000 Ft per chain, the most at Spar and Tesco.
- **Sensitivity:** drop the one sparse item (wholemeal bread: Tesco lists only one 1,778 Ft/kg multigrain loaf) and the spread falls from 24.5% to **13.1%**. Tesco moves from last to fifth; cherry-pick saving becomes 10.3%. One thinly covered category can flip a ranking.

**B. "Typical store" prices.** Only products carried by at least 50% of the chain's stores (stores with data), priced at their most common store price. COMPUTED, `data/basket_per_chain_typical_store.csv`.
- All price types: Lidl 13,850; Aldi 14,797; Penny 15,446; Spar 16,008; Auchan 16,822; Tesco 16,855. Cherry-pick 13,140.
- Spread +21.7%. **Cherry-pick saving vs Lidl only 5.1%** (NORMAL only: 2.6%).
- **Spar loses 1,483 Ft (10%) going from A to B.** Its listing prices are single-store minima, and its cheap wholemeal bread is in 1% of stores.

**Comparability caveats (all observed in the data):**
1. **Private label vs brand.** 84% of food SKUs (3,632 of 4,332) are sold by only one chain (XLSX). Cross-chain comparison is necessarily *category-level*, matching e.g. "cheapest 1.5% ESL milk", not identical products. The cheapest picks are almost all private labels or loose (lédig) produce.
2. **Pack size.** Unit prices assume you buy exactly the quantity needed. With whole packs ("checkout cost", pack-rounded) the picture changes. Over the items each chain has, Aldi goes from 14,522 to 17,214 and Lidl from 13,380 to 17,803, because 1 l olive oil, 30-egg trays or 2 kg bags are the cheapest per kg. Auchan, with many small packs, becomes the cheapest at checkout among items found: 14,812, though it is missing 2 items. Cherry-pick at checkout is 13,017. Leftovers carry over to later weeks, so checkout cost overstates the weekly cost; it is still what a shopper sees at the till.
3. **Missing items.** Aldi has no rice in the "Rizs" category. Lidl has no kg-priced garlic (only per-piece). Auchan has no cucumber or white cabbage. Some categories mix `db` and `kg` units (paprika, répa, hagyma, fokhagyma, alma, banán, uborka), so per-piece products can't be compared with per-kg ones without a weight assumption.
4. **Category misfits and label errors** are rare but real. 26 of 5,662 food price rows (0.5%) have `unitAmount ≠ amount/packaging`, e.g. "Koronás kristálycukor 1 kg" with packaging 0.5. Misfiled products exist (trappista in joghurt). "Olívaolaj" without "extra szűz" is listed in the extra-virgin category.
5. **Quality differences** within a category: ketreces S eggs vs free-range L, fürtös vs loose tomato, MSC vs non-MSC fish. A "cheapest in category" basket is a floor price, not like-for-like.
6. **The chain-min effect** (section 1, point 4) biases Spar and Tesco listing baskets downward.


## 5. Official daily bulk file: "Napi termékadatok letöltése" (new finding, VERIFIED)

- The site footer links to `https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx`, labelled "Napi termékadatok letöltése" in the JS bundle. A second link, "2025. március 13-i adatok letöltése", points to `arfigyelo_20250313_napi_termekadatok.xlsx`.
- The GET on 2026-10-12 returned 2,087,294 bytes, `last-modified: Mon, 12 Oct 2026 02:00:12 GMT`, `cache-control: public,max-age=3600`. A HEAD a minute earlier hit a stale CDN edge and showed `Sun, 11 Oct 2026 02:00:12 GMT`. **The file is regenerated every day at about 02:00 UTC (04:00 Budapest time).** Its only sheet is named `Napi feltöltések - 2026-10-12`.
- Contents (COMPUTED by parsing it with the standard library): 25,400 rows, one per product-chain pair, covering all 16,040 products and all 161 categories. Columns: Termék azonosító, Termék név, Kategória azonosító, Kategória név, Üzletlánc név, Egység, Kiszerelés, Minimum ár, Maximum ár, Minimum egységár, Maximum egységár, Hány üzletláncban elérhető, Hány boltban elérhető, Üzletlánc összes boltja.
- Price semantics (COMPUTED by matching against the API listing on 22,870 pairs): min/max are the **daily price, including DISCOUNTED and excluding LOYALTY**. In 352 + 102 + 30 pairs with a discount, the min equalled the discounted price. In 900 + 87 pairs with a loyalty price, the min equalled NORMAL. Only 23 of 22,870 pairs disagreed with the API (0.1%), probably because of intraday changes.
- What it is good for: a cheap, sanctioned, complete chain-level daily snapshot in one request of about 2 MB. It also shows **which product-chain pairs vary across stores (min < max)** and availability counts.
- What it lacks: per-store prices, *which* stores carry the product, and LOYALTY prices. Location features still need the API (section 3).

## 6. Data operations (question e)

**Timestamps and refresh**
- The API sends no last-updated field. No endpoint, header (`Last-Modified` or `ETag` on `/api/*`) or JSON field carries a data date (VERIFIED: response headers and bundle).
- The only machine-readable date is the XLSX `Last-Modified` header (02:00 UTC daily) and its sheet name (`Napi feltöltések - YYYY-MM-DD`).
- The legal timing is VERIFIED from Act L of 2025 §66(1) (https://njt.jog.gov.hu/jogszabaly/2025-50-00-00) and the retailer ÁFF (https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_kereskedo.pdf). Retailers must upload "naponta … legkésőbb a napi ár … alkalmazását megelőző nap végéig", that is, by the end of the day *before* the price applies.
- The GVH FAQ (https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf, text extracted locally): each day's prices are public only on that day; the next day they are archived.
- The bundle has a modal "Az aktuális termék érvénytelenné vált a napi adatok frissítése miatt", so the site expects one daily switch.
- ESTIMATE: the API switches to day D's prices around midnight, and at the latest by the time the XLSX is built at 04:00. A poll right after midnight and again at about 04:30 would confirm this. I did not observe a switch, because the session ran at 21:00–22:00.

**History**
- The API has no history or trend endpoint (VERIFIED: bundle endpoint list).
- The law says price fields are archived the day after they change (§57(4)). Archived data are open only to listed state bodies: ministers, courts, the consumer protection authority and KSH (§57(5)). Only "nem archivált adatok nyilvánosak" (§70). **A price history therefore exists only if you snapshot it yourself every day.** The 2025-03-13 XLSX is the only historical file offered.

**Rate limiting and caching (VERIFIED by observation)**
- About 2,800 requests ran at 1–1.8 req/s: no HTTP 429, no throttling, no rate-limit headers.
- API responses carry `cache-control: public, max-age=299`, but Azure Front Door returned `x-cache: TCP_MISS` even for an identical repeated request, so treat every call as hitting origin.
- **No gzip.** The API sent the same bytes with and without `Accept-Encoding: gzip`, while the XLSX is served zipped.
- `robots.txt` does not exist; the SPA returns `index.html`.

**Request and MB cost of a full daily snapshot (COMPUTED from this run; extrapolations marked ESTIMATE)**

| Snapshot | Requests | Uncompressed MB | Note |
|---|---|---|---|
| Official XLSX (all 9 chains, chain-level min/max) | 1 | 2.1 (12.6 MB unzipped XML) | COMPUTED |
| API listing, all 161 leaf categories | 422 | 10.70 | COMPUTED; took 6.6 min at about 1.1 req/s |
| API listing, 120 food leaf categories (6 food top categories) | 159 | 2.73 | COMPUTED; 4,332 SKUs |
| Store-level for 1,135 products (25 basket + 12 extra categories): 1,135 detail + 1,176 per-store calls | 2,311 | 16.0 (detail 2.53 + per-store 13.47) | COMPUTED. Averages: detail 2.2 KB; per-store call 11.5 KB; 114 bytes per store-price entry; 1.42 per-store calls per product |
| Naive store-level for ALL 4,332 food SKUs (listing + detail + per-store for every product) | about 10,600 (159 + 4,332 + about 6,150) | about 82 (2.7 + 9.7 + about 70) | ESTIMATE: per-product averages above × 4,332. About 2 h at 1.5 req/s |
| Smart daily food snapshot: XLSX + listing (for LOYALTY) + per-store only for the about 623 food pairs where XLSX min < max (11.2% of 5,561) | about 1,000–1,700 | about 12–17 | ESTIMATE. Plus a weekly `availableInShops` refresh (4,332 detail calls, about 10 MB), assuming availability changes slowly. Not verified; diff two days to confirm |

The API runs at about 0.4 s per call. The listing snapshot of 422 calls took 6.6 min (COMPUTED).

## 7. Location scenarios (question d)

Points (VERIFIED via OpenStreetMap Nominatim): Móricz Zsigmond körtér 47.4774, 19.0470; Nyugati tér 47.5103, 19.0558; Örs vezér tere 47.5030, 19.1365; Újpest-Központ 47.5603, 19.0906; Határ út (M3) 47.4658, 19.1262. Distances are straight-line (haversine), not walking. Store-level prices, all price types.
- "Best single store" = cheapest basket at one store with at least 20 of 25 items; missing items topped up at the cheapest store in the same radius.
- "City best" = Lidl, 13,529 Ft.
- Outputs: `data/location_scenarios.csv`, `data/location_stores_in_radius.csv`.

| Point | Stores ≤1 km (by chain) | Stores ≤2 km (by chain) | Nearest food store, basket (vs city best) | Best single store ≤1 km | Best ≤2 km | Cherry-pick ≤1 km / ≤2 km |
|---|---|---|---|---|---|---|
| Móricz Zs. krt. (XI) | Lidl 1, Spar 3, Tesco 1, Rossmann 1, dm 1 | Aldi 6, Lidl 2, Spar 10, Tesco 4, dm 6, Rossmann 5, Müller 1 | Lidl Bartók B. út 47, 13,529 (0%) | Lidl, 13,529 (0%) | Lidl, 13,526 | 12,970 / 12,774 |
| Nyugati tér (VI/XIII) | Aldi 2, Lidl 3, Penny 1, Spar 6, Tesco 1, dm 6, Rossmann 5 | Aldi 4, Lidl 7, Penny 3, Spar 17, Tesco 3, dm 15, Rossmann 10, Müller 2 | Spar Nyugati tér 1-2, 16,585 (**+22.6%**) | Lidl Arany J. u., 13,526 (0%) | Lidl, 13,526 | 12,810 / 12,790 |
| Örs vezér tere (X/XIV) | **Spar 5 only** (1 is the Árkád store with no data), dm 2, Rossmann 1, Müller 1 | Aldi 1, Lidl 1, Penny 2, Spar 8, Tesco 2, dm 4, Rossmann 2, Müller 1 | Spar Kerepesi út 61, 16,386 (**+21.1%**) | Spar, 16,386 (**+21.1%**) | Lidl Mogyoródi út, 13,846 (+2.3%) | 16,386 / 13,094 |
| Újpest-Központ (IV) | Lidl 2, Penny 1, Spar 5, dm 2, Rossmann 1 | Lidl 2, Penny 2, Spar 8, Tesco 1, dm 5, Rossmann 4 | Spar István u. 10, 17,170 (**+26.9%**) | Lidl Görgey A. u., 13,529 (0%) | same | 13,010 / 13,010 |
| Határ út (XIX/IX/X) | Aldi 1, Lidl 2, Penny 1, Spar 2, dm 2, Rossmann 1 | Aldi 1, Lidl 4, Penny 2, Spar 6, Tesco 1, dm 3, Rossmann 3 | Spar Üllői út 201, 16,386 (**+21.1%**) | Lidl Lobogó u., 13,526 (0%) | same | 12,864 / 12,774 |

With NORMAL prices only: same pattern; nearest-store premium +21.8% to +27.5%.

**Price of convenience (COMPUTED):**
- Shopping at the *nearest* food store instead of the best one within 1 km costs **+21–27%** at 4 of 5 points. The nearest store is a Spar in 4 of 5; Móricz has a Lidl 160 m away.
- At Örs vezér tere, 1 km is not enough: only Spar is within reach. 2 km brings in a Lidl and cuts the basket from 16,386 to 13,846 Ft.
- Within 1–2 km the best single store usually matches the city best, because Lidl's prices are national.
- Multi-store cherry-picking within 2 km saves a further **3.8–5.4%**. Visiting every Budapest store would save 8.6% (12,365 vs 13,529), which is not realistic.
- **Data gap:** 20 of the 282 Budapest food stores listed in `/shops` (7%; 18 Spar, 2 Tesco) have **no products at all** in today's data, e.g. Spar Örs vezér tere 25 (Árkád) and Tesco Koppány u. Nationally, the XLSX shows Spar 317/375, Tesco 193/197, Rossmann 268/280 and dm 253/259 stores carrying at least one product. `products-by-category/2034?shopIds=spar-171` returned 0 products; the neighbouring `spar-190` returned 36. **The app must hide such stores or label them "no price data".**

## 8. Free-text search for recipe ingredients (question f)

COMPUTED, `data/search_results.csv`; raw responses in `raw/search/`. `/api/search` matches fuzzily, ignoring accents, as substrings. It has no synonyms or ingredient semantics, and ranks results poorly.

| Query | Hits | What came back |
|---|---|---|
| csirkemellfilé | 23 | all correct |
| csirkemell | 36 | 30 correct; also cheese spread, baby food, ham |
| zabpehely | 4 | **no oats**: gluten-free oat flour and a soap. Oats are not covered. |
| spenót | 10 | 9 baby foods, 1 pasta. **No spinach.** |
| lazac | 54 | 35 fish fillets (some salmon), 13 baby foods |
| paradicsom | 32 | 14 fresh, 14 baby food. "passata" and "sűrített paradicsom": 0 hits |
| csicseriborsó | 8 | chickpea pasta and baby food; **no chickpeas** |
| bab | 629 | nappies (substring of "baba") |
| túró | 157 | Túró Rudi desserts ranked first; plain túró only 6 in the first 48 |
| citrom | 179 | dishwasher tablets and detergents first |
| dió | 95 | fuzzy junk (mineral water "dioxiddal", "Di Cuori" tissues) |
| olívaolaj | 72 | refined oil ranked first |
| bulgur, tonhal, fűszerpaprika, vörösbab | 0 | not covered |
| só | – | HTTP 400 (queries must be at least 3 characters) |

**Conclusion:** search is not usable for automatic ingredient-to-product matching. The app needs a curated **ingredient → GVH leaf category (+ unit and name filter)** table. 161 leaves make this feasible by hand. It also needs a fallback price source for the many recipe ingredients GVH does not cover.

## 9. Legal and terms notes found in this stream (VERIFIED unless marked otherwise)

- **Act L of 2025, Chapter V** (§§55–72, https://njt.jog.gov.hu/jogszabaly/2025-50-00-00) replaced Govt. Decree 163/2023. The njt version of 163/2023 notes it was repealed with effect from 2025-07-20.
  - §57(2): prices are recorded "kereskedőnként és üzletenként" (per retailer and per store).
  - §57(3): reductions caused by a best-before date within 72 hours are excluded.
  - §57(1) bc: the loyalty price is the lowest loyalty price, excluding coupons and quantity deals, and is recorded only if lower than the daily price.
  - §66(1): upload by the end of the previous day.
  - §70: non-archived data are public, and GVH provides access.
  - §57(5)–(6): archived data are open only to listed authorities and deleted after 10 years.
  - **No provision on third-party re-use, API use or licensing.**
- **Retailer ÁFF** (https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_kereskedo.pdf):
  - Products sold continuously for **at most 1 month need not be reported**. Short leaflet-only promotional SKUs are therefore not in the data. Price cuts on regularly sold SKUs do appear as DISCOUNTED.
  - The consumer protection authority acts if the shelf price is **higher** than the price registered in Árfigyelő. The registered price is effectively a binding ceiling for that day and store, a strong incentive for accuracy.
  - IT outages over 4 hours excuse missed uploads, so occasional gaps are possible.
- **GVH FAQ** (https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf):
  - Daily prices are public only on the day they apply.
  - The site "does not contain information on in-store availability". `availableInShops` means the store has a reported price, not that the product is on the shelf.
- **The official XLSX download** is offered openly by GVH in the site footer, with no terms attached to it specifically. Using the bulk file GVH publishes is lower-risk than hitting the undocumented API (ESTIMATE, not legal advice). The visitor ÁFF XIV.2 limits on brand and image use still apply.
- Precedent, not legal advice: Lidl used Árfigyelő data in "cheapest chain" advertising. GVH closed its case on 2025-11-13 with commitments: cite Árfigyelő as source; claim "cheapest" only with a gap of at least 2.5%; claim a whole month only with one more cheapest day. Reported at https://www.economx.hu/magyar-gazdasag/2025/11/13/gvh-versenyhivatal-eljaras-lidl-arak-819279/. Commercial communication built on Árfigyelő data is tolerated when sourced and fair.
- Telex (2023-09-01, https://telex.hu/g7/penz/2023/09/01/nem-biztos-hogy-a-kormanyzati-arfigyeloben-kozzetett-aron-meg-is-tudod-venni-a-termekeket) already reported the effect I measured: the cheapest chain-level price can apply in only a handful of stores (5 stores nationwide in their example).

## 10. Implications for the product (my inferences)

1. **GVH data are enough for a credible Budapest MVP price layer** for the covered staples, across 6 chains and 263 Budapest food stores with data. They do *not* cover CBA, Coop, Reál, Kifli or Wolt, nor many recipe ingredients: oats, legumes other than lentils, spinach, zucchini, mushrooms, salmon as its own category, spices, canned tomato.
2. **Location value = chain proximity + small-format assortment, not store price micro-differences.**
   - Aldi, Penny and Lidl have one national price, so a Lidl is a Lidl.
   - The app's "best local price" is mostly "which discounter is within X km, and is the cheap SKU stocked in this Spar or Tesco Expressz".
   - Store-level price calls matter only for about 40% of Tesco and about 11% of Spar food SKUs.
3. **Don't use chain-level listing prices as "the price at your store" for Spar and Tesco.** They are per-type minima across all stores and can be single-store outliers. Use per-store prices from `/product/{id}/shop/{ids}` or `products-by-category?shopIds=`, or at least the modal price.
4. **Build your own history.** The law archives prices away from the public, so daily snapshotting from day one is a moat and a prerequisite for "price trend" and "is this a real deal" features. The XLSX is a cheap daily backbone: 1 request, and it carries a date.
5. **Recipe mapping must be curated:** about 161 leaf categories, unit handling (db vs kg), name filters. Free-text search is unusable for this.
6. **Cherry-picking saves only 4–10%.** Choosing a nearby discounter instead of the nearest supermarket saves about 20–27%. The strongest user message is "go to this store this week for your plan", not "split your basket across 4 stores".
7. Operational risk: the API is undocumented, uncompressed and shows no throttling today. A polite daily job of about 1–2k calls is light. Hide stores with no price data; source opening hours elsewhere.

## 11. Open questions

- Exact time the API switches to the new day's prices. Expected: around midnight, by 04:00 at the latest given the XLSX at 02:00 UTC. Poll around 00:05 and 04:30 to confirm.
- Does `availableInShops` change daily or slowly? Diff two consecutive days before deciding the refresh cadence.
- Why do 58 Spar stores, including Árkád Örs vezér tere, and 4 Tesco stores have no data? Closed stores, INTERSPAR formats, or non-reporting? Ask GVH (arfigyelo@gvh.hu), or check against spar.hu and tesco.hu store lists.
- Does GVH object to commercial API use? Neither ÁFF addresses it. Consider asking GVH for written confirmation, or a data partnership, before launch.
- Reconcile the FAQ's "80% of stores" rule with the observed min-price behaviour, possibly by asking GVH.
- Opening hours source (OSM, chain store finders, Google Places): coverage and licence.


## 12. File index (all under this stream folder)
- `data/stores.csv`: all 1,829 stores with coordinates, opening times and a Budapest flag
- `data/basket_per_chain.csv`, `data/basket_items_national.csv`: chain-level listing basket, every mode × clean variant, with item-level product picks
- `data/basket_per_chain_typical_store.csv`, `data/basket_items_typical_store.csv`: typical-store (modal price, ≥50% availability) basket
- `data/budapest_store_basket.csv`: basket cost at each of the 282 Budapest food stores (3 modes, items found)
- `data/budapest_store_decomposition.csv`: actual vs assortment-only vs chain-best per Budapest store
- `data/location_scenarios.csv`: 5 points × 1/2 km × 2 price modes
- `data/location_stores_in_radius.csv`: every store within 1 and 2 km of each point, with distance
- `data/store_price_variation.csv`, `data/staples_store_variation.csv`: per product × chain store-price dispersion, national and Budapest
- `data/xlsx_chain_price_uniformity.csv`: share of pairs with store-level differences, from the official XLSX
- `data/search_results.csv`: free-text search tests
- `data/snapshot_log.json`, `data/storelevel_log*.json`: request logs (sizes, timings)
- `raw/`: API responses (`snapshot/`, `storelevel/`, `probe/`, `search/`), `xlsx/napi.xlsx` (official daily file of 2026-10-12), `docs/` (GYIK and retailer ÁFF PDFs), `index-5baaf084.js` (site bundle)
- `scripts/`: all code (`snapshot.py`, `storelevel.py`, `basket_def.py`, `basket_national.py`, `basket_typical.py`, `variation.py`, `format_effect.py`, `decompose.py`, `location.py`, `xlsx_read.py`, `xlsx_stats.py`, `shops_analysis.py`, `shops_outliers.py`, `search_test.py`, `pdftext.py`)
