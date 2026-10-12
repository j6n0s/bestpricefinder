# Adversarial fact-check: "Competitors & international analogs" stream

Checked on 2026-10-12. Every source was re-opened independently, and the numbers were re-computed with my own scripts.

Labels used throughout:
- **VERIFIED**: read today on the cited primary page or API.
- **COMPUTED**: derived from data I pulled today. The method is stated.
- **INFERENCE**: my reasoning, not a fact.

Where things are:
- Raw downloads (untrusted): `verify_dl/`
- Scripts: `verify_scripts/` (`xlsx_check.py`, `export_stats.py`, `food_split.py`, `pershop.py`, `pricetypes.py`)
- Derived data: `verify_data/gvh_export_2026-10-12_chain_stats.csv` and `verify_data/gvh_export_food_split_2026-10-12.csv`

Server load was kept low: I sent about 1 request per second with User-Agent `market-research-bot/0.1 (fact-check)`. I made about 25 GVH API calls in total.

Limitation: the shared WebSearch budget ran out partway through. Items that needed a web search, such as the reason Heisse Preise lost its feeds, are marked unverifiable. I did not work around the limit.

## Verdict summary

| # | Claim (short) | Verdict |
|---|---|---|
| 1 | NomNom core facts (publisher, release, 703 ratings, price, 5 stores, Android 1K+ / 4.7) | **partly-true**: the Play "4.7" rating is wrong, and there are several smaller inconsistencies |
| 2 | NomNom has no location, covers dinners only, and its reviews complain about recipe quality | **confirmed**, with caveats |
| 3 | NomNom blog: cross-chain recipe comparison saves only about 11% | **partly-true**: the blog itself calls the 11% an underestimate |
| 4 | GVH publishes an official daily Excel export (25,400 rows, 16,040 ids, 9 chains, 1,829 stores) | **confirmed**: the date is slightly off, and 78% of rows are non-food |
| 5 | Store-level price variation is rare (7.6%) and mostly at SPAR; availability is the real issue | **partly-true**: for food the figures differ materially, and Tesco, not SPAR, has the broad variation |
| 6 | Lefőzlek offers recipes, a weekly plan and price per portion | **partly-true**: the facts hold, but its Plusz price and multi-week planning were missed, and its prices are not store-specific |
| 7 | Cashmap's weak uptake shows that paywalled comparison is hard to sell | **partly-true**: the facts hold, but the inference is weak because the company is still maintained and may be pivoting to B2B |
| 8 | Heisse Preise lost most of its chain feeds in 2024–25 (scraping decays) | **partly-true**: 11 of 14 feeds stopped, but the cause is not stated |

---

## 1. NomNom core facts: PARTLY TRUE

### Confirmed (VERIFIED)

From iTunes Lookup (https://itunes.apple.com/lookup?id=6788049718&country=hu):
- trackName "NomNom: Budget Meal Planner"; sellerName "Z Gen Kibernetika Korlatolt Felelossegu Tarsasag"; artistName "Neo App Labs".
- releaseDate 2026-07-23; version 1.0.19, released 2026-10-11.
- userRatingCount 703, averageUserRating 4.81649.

From https://nomnomplanner.com/hu/:
- The weekly dinner plan uses "valódi Aldi, Lidl, Tesco, SPAR és Kifli árakból" (real Aldi, Lidl, Tesco, SPAR and Kifli prices).
- The prices come "a Gazdasági Versenyhivatal hivatalos Árfigyelőjéből és bolti katalógusokból" (from the Competition Authority's official Árfigyelő and store catalogues).
- "1 000+ követett termék, 5 bolt összevetve, 36 vacsora a tervezőben, 27 EU-ország" (1,000+ tracked products, 5 stores compared, 36 dinners in the planner, 27 EU countries).
- Pricing: 7,990 Ft/year with a 7-day trial, or 1,490 Ft/month with no trial.

From https://nomnomplanner.com/terms/ (effective 16 Aug 2026): 7,990 HUF/year with a 7-day trial, or 1,490 HUF/month. "On Google Play, NomNom Plus is currently sold in Hungary only."

Google Play (https://play.google.com/store/apps/details?id=com.nomnomplanner): the listing exists as "NomNom Meal Planner" by Neo App Labs, with "1 E+ letöltés" (1K+ downloads) and an update date of 2026-10-08.

Rating velocity: 703 ratings over 81 days (2026-07-23 to 2026-10-12) is 8.7 per day (COMPUTED).

### Refuted

**"Google Play 4.7".** The NomNom Play page shows no star rating for the app.
- Neither the HU nor the EN version of the page has an `aggregateRating`.
- The header block shows only "PEGI 3 · 1 E+ letöltés".
- The "4,7" strings on the page belong to the "similar apps" carousel (for example "KitchenPal … 4,7"). This is also true of the stream's own saved copy, `dl/gplay/d_com.nomnomplanner.html`.
- Correct statement: NomNom on Google Play has 1K+ downloads and too few ratings for Play to show an average.

### Inconsistencies the stream did not flag (VERIFIED)

- **Store count:** the App Store description (HU and US) says "Real shelf prices from Aldi, Lidl, Tesco and Spar in Hungary". That is four chains; Kifli appears only on the website.
- **Android:** the website FAQ still says "Lesz Android? Egyelőre iOS. Az Android a kívánságlistán van" (Android? iOS for now; Android is on the wishlist). The EN page says the same. This contradicts the live Play listing, so the website is stale.
- **Location of the company:** Google Play's developer block gives the publisher's address in Szeged (6720). The site says "Budapesten készül" (made in Budapest). The team may sit in Budapest, but the company address is in Szeged.
- **EU availability:** the site claims the app "works in all 27 EU countries" on iOS. iTunes Lookup for id 6788049718 returns 0 results in the DE, AT, SK, RO, FR and GB storefronts.
  - A US listing exists as "NomNom: Meal Planner & Recipes", released 2026-08-12, with 9 ratings.
  - The ambassador page invites "Creators from Europe and the United States".
  - The ambition is international, but in practice the app is live only in HU and the US.
- **Acquisition:** the privacy policy (effective 28 Sep 2026) lists the Meta Conversions API, the TikTok Events API, Google Ads conversion import and in-app Meta, TikTok and Firebase SDKs. Together with the paid creator program, this confirms funded paid acquisition (INFERENCE).

## 2. NomNom's gaps (no location, dinners only, recipe-quality complaints): CONFIRMED, with caveats

- **Location (VERIFIED):** the privacy policy says "We do not collect your name, email, contacts, or precise location." It adds that the "IP address is used … to derive a rough location (country/city)" for analytics only. Store choice is a manual "melyik boltba jársz" (which store do you shop at).
- **Dinners only (VERIFIED):** the App Store text says "Dinner for the week". The site says "36 vacsora" (36 dinners).
- **Reviews (VERIFIED):** the HU reviews RSS (https://itunes.apple.com/hu/rss/customerreviews/id=6788049718/sortby=mostrecent/json) has exactly 9 entries: four 5★, one 3★ and four 1★. The quotes in the stream are accurate:
  - "Folyamatosan ugyan azt a 10 ételt pörgeti" (it keeps cycling the same 10 dishes)
  - "AI slop ételek" (AI slop dishes)
  - "A receptek nincsenek érthetően leírva, AI írta" (the recipes are unclear, written by AI)
  - "Adjon mar reggelit" (give me breakfast already)
- **Caveat 1 (VERIFIED):** all four 1★ reviews are on versions 1.0.6 to 1.0.14 (11 Aug to 16 Sep). The four most recent reviews, on versions 1.0.17 and 1.0.18 (24 Sep to 1 Oct), are all 5★. Nine reviews are anecdotal, and the problems may be partly fixed.
- **Caveat 2 (VERIFIED, App Store Search):** a new international app, "Misu – Budget Meal Planner" (iOS 2026-09-29, 0 ratings), describes itself with "184 supermarkets across 22 countries". Its Premium "unlocks your full weekly plan — breakfast, lunch and dinner — the aisle-sorted shopping list priced at your supermarket". Its Hungarian coverage is unverified. The "dinners only" gap is being targeted by others.

## 3. NomNom blog: comparison saves "only about 11%": PARTLY TRUE

Source: https://nomnomplanner.com/hu/blog/heti-vacsora-ara/ (2026-07-09).

**The figures are reproduced correctly (VERIFIED).**
- Aldi 18,893, Lidl 19,750, SPAR 20,095, Tesco 20,987 and Kifli 25,700 Ft.
- The gap between the four physical chains is 2,094 Ft, or 11.08% (COMPUTED: (20,987 − 18,893) / 18,893).
- Carrots cost 489 Ft/kg and 450 g frozen peas 339 Ft at all four chains.

**The pattern still holds today (COMPUTED from the 2026-10-12 export):**
- 1 kg own-label carrots: Aldi 489, Lidl 489, SPAR S-Budget 489, Tesco "TS" 489–519 depending on the store.
- 450 g own-label frozen peas: Aldi, Lidl, Penny and SPAR 339; Tesco 339–379 depending on the store.

**What the stream left out (VERIFIED, same blog post):**
- **The blog calls its own number an underestimate.** "A huszonkilenc hozzávalóból … az Aldinak tizenhatot, a Lidlnek és a SPAR-nak tizenötöt, a Tescónak tizennégyet [árazza a nyilvános adat]. A többinél a Kifli katalógusából vesszük az árat, mindegyik boltnál ugyanazt … a boltok közti valódi különbség nagyobb." In English: the public data priced only 14 to 16 of the 29 ingredients per chain. The rest were priced from Kifli's catalogue at the same price for every chain, so the real difference between stores is larger.
- **The comparison leaves things out.** Promotions, loyalty prices and local store differences are excluded: "Akciók, törzsvásárlói kedvezmények és a boltok közti helyi eltérések nincsenek benne."
- **The cleanly comparable items show a bigger gap.** On the 8 ingredients that all four chains price, the spread is 1,905 Ft (Lidl) to 2,329 Ft (SPAR), or 22% (COMPUTED from the blog's table). Single items differ by up to 2.4 times; cucumber, for example, costs 214 Ft at Lidl and 513 Ft at SPAR.

**Correct statement:** NomNom reports a list-price gap of at least about 11% between the cheapest and most expensive of four chains for one 5-dinner basket on one day. By its own account the true gap is larger. The figure does not support the reading that comparing prices saves only about 11%.

**Bigger implication for the founder (VERIFIED from the blog):** for 5 ordinary dinners, GVH data covered only about half of the ingredients per chain. A second price source is needed from day one.

## 4. GVH official daily Excel export: CONFIRMED, with corrections

**The link is official (VERIFIED).** The current bundle `/assets/index-5baaf084.js` contains the footer link `{url:"https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx",text:"Napi termékadatok letöltése"}` (download daily product data). It also links the archived file `arfigyelo_20250313_napi_termekadatok.xlsx`.

**The download (VERIFIED):**
- HTTP 200, 2,087,294 bytes.
- `last-modified: Mon, 12 Oct 2026 02:00:12 GMT`.
- Sheet name "Napi feltöltések - 2026-10-12" (daily uploads, 2026-10-12).
- The stream's copy has the same SHA-256 hash as mine. Its stated last-modified date of 2026-10-11 is therefore a small error: the file is the 2026-10-12 one.

**Contents (COMPUTED, independent parser):**
- 14 columns: Termék azonosító, Termék név, Kategória azonosító/név, Üzletlánc név, Egység, Kiszerelés, Minimum/Maximum ár, Minimum/Maximum egységár, Hány üzletláncban elérhető, Hány boltban elérhető, Üzletlánc összes boltja (product id, name, category id and name, chain, unit, pack size, min and max price, min and max unit price, number of chains carrying the product, number of stores carrying it, chain's total store count).
- 25,400 rows, 16,040 distinct ids, 161 leaf categories, 9 chains.
- The chains' store totals add up to 1,829, which equals the 1,829 shops returned by `/api/shops`.
- No product×chain row appears twice.

**Correction: the file is mostly non-food (COMPUTED).** I mapped the leaf categories to top-level categories using `/api/categories`.
- Food rows: only 5,561 of 25,400 (22%), covering 4,332 distinct products and 120 leaf categories.
- "Szépség és higiénia" (beauty and hygiene) alone accounts for 12,955 rows (51%).

**It agrees with the API (COMPUTED).** I paged two categories fully, using `limit=48`:
- Tojás (eggs): 96 of 96 product×chain entries are identical.
- Túródesszert (curd dessert): 210 of the export's 227 entries are in the API.

**What min/max mean (VERIFIED with the per-store API, see item 5):** the minimum and maximum are the range of each store's effective price, including promotions that run in only some stores. They are not a regular-price range, and the file does not split prices by type.

## 5. Store-level price variation and availability: PARTLY TRUE

**The all-row numbers reproduce exactly (COMPUTED).**
- Share of rows where the minimum price is below the maximum: SPAR 27.6%, Tesco 25.4%, Auchan 1.4%, Lidl 0.9%, and 0% for the others. That is 7.6% overall.
- Share of rows carried in at least 80% of the chain's stores: Aldi 100%, Penny 94.4%, Müller 87.6%, Lidl 87.4%, dm 79.7%, Rossmann 53.0%, Auchan 27.9%, SPAR 14.5%, Tesco 11.0%.

**But a food app should use food rows (COMPUTED, `verify_data/gvh_export_food_split_2026-10-12.csv`):**

| Chain | Food rows | Share of food rows with min < max | Mean (median) spread when varying | Food rows in ≥80% of stores |
|---|---|---|---|---|
| Tesco | 1,161 | **39.9%** | 9.1% (8.2%) | **24.9%** |
| SPAR | 1,104 | **11.1%** | 58% (56%) | **28.9%** |
| Auchan | 1,620 | 2.0% | 26% (13%) | 43.5% |
| Lidl | 410 | 1.5% | 39% (34%) | 86.6% |
| Penny | 349 | 0% | – | 90.5% |
| Aldi | 425 | 0% | – | 100% |
| **6 grocery chains** | **5,069** | **12.3%** | | |

What this changes:
- SPAR's high all-row variation comes mostly from non-food: 37.0% of its non-food rows vary, for example Gillette products.
- For food, the broad store-level price variation is at **Tesco** (40% of food items, around 9%). SPAR has fewer varying food items (11%), but with large gaps (around 55%), which look like promotions running in only some stores.
- The stream's line in its notes, "pricing by store matters only for SPAR (and a little for Tesco)", is therefore backwards for food.

**Per-store API spot checks (VERIFIED, `/api/product/{id}/shop/{store}`):**
- **Lidl, Banán kg (lidl-0080000):**
  - lidl-316: NORMAL 379 Ft.
  - lidl-166: NORMAL 379 Ft.
  - lidl-182: NORMAL 699 Ft.
  - The export shows 379/699. Real store differences exist even at Lidl.
- **SPAR, Banán lédig (8591189960848):**
  - Chain level: `priceSameEverywhere: true`, with NORMAL 699 and DISCOUNTED 399 (both `sameAmountEverywhere: true`).
  - Stores spar-110, -197, -275, -8264, -13 and -916 all show only NORMAL 699.
  - The export shows 399/699, so the discount runs in only a subset of stores.
  - **The chain-level "same everywhere" flag misses differences in promotion coverage.**
- **Tesco, Kígyóuborka (0000000023214):**
  - The 4 stores sampled all show DISCOUNTED 219 Ft, with NORMAL prices of 399, 429, 399 and 435 Ft.
  - The export shows 219/415. The export's max is lower than the live API's normal prices, which suggests the normal price changed during the day (INFERENCE).
- **Penny, Kígyóuborka:** NORMAL 379 and DISCOUNTED 219 at chain level; the export shows 219/219. The effective price is the same in every store, so the row does not count as varying, even though a NORMAL price exists.

**Further caveats (INFERENCE):**
- Store-level variation in the export is a single-day snapshot of effective prices, so it moves with promotion calendars.
- When a chain-wide discount masks the regular price, regional differences in that regular price are hidden. Example: SPAR Mizo tejföl 20% has NORMAL `sameAmountEverywhere:false`, yet the export shows 399/399.
- "Hány boltban elérhető" (number of stores carrying the product) counts the stores for which the retailer uploads a price. It is not verified shelf stock: Aldi reports all 729 rows in all 188 stores.

**About the "80%" text on the GVH homepage (VERIFIED, bundle):** the exact text is "A termékek az üzletek legalább 80 %-ában az itt feltüntetett áraktól elérhetők, de egyes üzletekben ennél olcsóbbak is lehetnek." In English: products are available at the prices shown, or cheaper, in at least 80% of stores; some stores may be cheaper still. It describes how the price on the default product card is chosen. It does not promise that every listed product is stocked in 80% of a chain's stores, so it does not contradict the low availability shares at SPAR and Tesco.

**Corrected statement:**
- On 2026-10-12, 12.3% of food product×chain rows in the six grocery chains had different effective prices across a chain's stores.
- Tesco: 40% of rows, with spreads of around 9%. SPAR: 11%, with spreads of around 55%. Auchan 2%, Lidl 1.5%, Aldi and Penny 0%.
- Food items reported in at least 80% of a chain's stores: Aldi 100%, Penny 91%, Lidl 87%, Auchan 43%, SPAR 29%, Tesco 25%.
- Location therefore matters for both price (mainly at Tesco and SPAR) and availability (SPAR, Tesco, Auchan).

## 6. Lefőzlek: PARTLY TRUE

**Confirmed (VERIFIED, iTunes Lookup id 6763793215):**
- Seller: Business Gravity Kft.
- Released 2026-10-01; version 1.1.5 on 2026-10-09.
- Features: imports from TikTok, Instagram, Facebook, Pinterest and URLs; a weekly plan; a one-tap shopping list sorted by aisle; "Adagonkénti ár és tápérték a legtöbb recepthez" (price per portion and nutrition for most recipes).

Also confirmed:
- lefozlek.hu: "259 kipróbált recept" (259 tested recipes) and "hozzávalónkénti árbecsléssel (bolti árak alapján)" (price estimates per ingredient, based on store prices). Neither the homepage nor /rolunk names a price source.
- Google Play search for "lefőzlek" finds no app.

**Missed or corrected (VERIFIED, App Store description):**
- **Plusz price:** "A Plusz ára 999 Ft / hó vagy 9 990 Ft / év" (999 Ft/month or 9,990 Ft/year). The stream said the price was not seen.
- **What the free tier covers:** the current week's plan.
- **What Plusz adds:** "bármelyik hét tervezése" (planning any week) and "a nap és a hét tápértéke és ára, becsült kosárérték" (the day's and week's nutrition and price, and an estimated basket value). Multi-week planning with cost and nutrition already exists, though the user plans by hand.
- **Traction:** 1 rating (VERIFIED).
- **Prices are not store-specific:** I found no store selection or comparison. The prices are generic estimates, so Lefőzlek is a recipe-keeper and planner, not a store price comparator.

## 7. Cashmap: PARTLY TRUE

**Confirmed (VERIFIED):**
- https://cashmap.hu/dokumentumok/aszf is dated "2024-03-20". It gives the seat as 4631 Pap, Cg. 15-09-088643; a 14-day trial; tiers of Standard 1,290, Plus 1,999 and Premium 2,999 Ft/month; and a "42.000-es termék adatbázis" (42,000-product database).
- The site HTML contains "A lakossági regisztráció technikai okok miatt nem elérhető! Céges regisztráció miatt kérjük írjon…" (consumer registration is unavailable for technical reasons; for business registration, please write to…).
- iTunes Lookup: released 2023-09-10, updated 2026-07-03, 137 ratings, average 4.36.
- I did not re-check the Play figures (5K+, 278 reviews).

**Why the inference is weak (INFERENCE):**
- The product is still maintained. The iOS app was updated in July 2026, and the store list in the error-report form includes "SPAR-WOLT-ÚJ 2026 áprilistól" (SPAR-Wolt, new from April 2026).
- Closing consumer sign-ups while inviting business sign-ups points at least as much to a B2B pivot as to consumer failure.
- One small company is weak evidence that a paywall cannot work in Hungary.

**Correct statement:** Cashmap's paid consumer app has modest public traction (137 iOS ratings in 3 years). Consumer registration is currently closed and business access is offered instead. This is consistent with, but does not prove, weak consumer willingness to pay.

## 8. Heisse Preise feed decay: PARTLY TRUE

**What the site says (VERIFIED, https://heisse-preise.io/ banner).** These stores are "nicht mehr aktualisiert" (no longer updated):
- Rewe Deutschland (15.2.2024)
- Unimarkt (24.2.2024)
- Bipa (4.4.2024)
- MPreis (24.6.2024)
- Müller (3.3.2025)
- **Müller Deutschland** (3.3.2025)
- Lidl (27.3.2025)
- DM (29.7.2025)
- **DM Deutschland** (29.7.2025)
- Penny (14.10.2025)
- Hofer (10.11.2025)

That makes 11. The stream's notes list only 9 names, but its count of 11 is right.

**How many remain (COMPUTED from the site's `index.js`):** the script configures 14 stores (billa, bipa, dm, dmDe, hofer, lidl, mpreis, mueller, muellerDe, penny, reweDe, spar, sparSi, unimarkt). Only Billa, Spar and Spar SI are still live, so "most" is correct.

**What is not established:** the cause. The banner gives no reason; it says only "Die historischen Daten sind weiterhin verfügbar" (the historical data is still available). The idea that the feeds stopped because retailers changed or blocked their sites is an INFERENCE. Maintainer capacity is an equally plausible explanation. I could not search for press coverage because the search budget was exhausted. Treat "scraping decays" as plausible, but not proven by this example.

---

## Additional spot-check, not one of the 8: Árnéni

The stream's claims hold (VERIFIED, 2026-10-12):
- Premium costs "1 475 Ft / hó (ÁFA-val)" (1,475 Ft/month including VAT), on the homepage and in terms §5.
- 13 chains and "több mint 17 000 akciót" (more than 17,000 deals), on /legolcsobb-bevasarlas, "Frissítve: 2026. április" (updated April 2026). The same page also says "10 szupermarket" in one place, which is internally inconsistent.
- No `geolocation`, recipe or app-store link appears in any page or in the four first-party scripts (arneni-bell, -consent, -gate, -watchlist).
- iTunes Search for "arneni" and "árnéni" returns 0 results.
- robots.txt disallows `/scripts/`, so I did not fetch anything there.

## Things the stream missed

1. **NomNom's own blog shows that GVH data priced only 14–16 of 29 ingredients** for five ordinary dinners; NomNom filled the rest from Kifli's catalogue. This is direct evidence that a recipe-pricing app needs a second data source for about half of its ingredients.
2. **In the export, min/max are store-level effective prices,** including promotions that run in only part of a chain. In the API, `priceSameEverywhere` and `sameAmountEverywhere` are set per price type and can read `true` while stores really differ (SPAR banana). Telling a user the "local price" needs the per-store endpoint.
3. **The export is 78% non-food.** The food universe is 5,561 rows, 4,332 products and 120 leaf categories. Food-only statistics change the conclusions: Tesco, not SPAR, has the broad store-level price variation.
4. **GVH API pagination:** with no `limit`, `/products-by-category` returns 12 items per page; `limit=48` works. A crawler that steps the offset by 48 without `limit` silently skips three-quarters of the items.
5. **GVH UI wording:** "A törzsvásárlói árak tájékoztató jellegűek, üzletenként eltérhetnek" (loyalty prices are indicative and can differ by store). The "80%" text describes how the displayed price is chosen, not product availability.
6. **New entrants the stream did not list (VERIFIED, HU App Store search, 2026-10-12):**
   - Misu – Budget Meal Planner (2026-09-29): budget planner across 22 countries; Premium includes breakfast, lunch and dinner and a list priced at the user's supermarket; 0 ratings.
   - Ma Sem Halunk Éhen (2026-09-24): app of a popular HU food blog, with a weekly menu planner, an automatic shopping list and suggestions based on what is in the pantry; no prices; 3 ratings.
   - Meal Planning Routine (2026-04-08): HU-language UI, breakfast, lunch and dinner, "Plan continuously across upcoming weeks"; 0 ratings.
   - I-Foodie Étrendtervező (2023): about 130 recipes, macros, a diet scheduler; 10 ratings.
7. **The stream's claim that "no HU player plans more than one week ahead" is wrong.** Lefőzlek Plusz ("bármelyik hét tervezése", planning any week) and Meal Planning Routine both plan beyond one week. What nobody offers is multi-week planning priced at nearby stores.
8. **Inconsistencies in NomNom's own materials:** the App Store lists 4 stores while the site lists 5; the site says iOS only while the Play listing exists; the address is in Szeged although the site says it is made in Budapest; the "27 EU countries" claim is not backed by any storefront except HU and the US.
9. **NomNom funds acquisition and aims beyond Hungary:** it uses Meta, TikTok and Google conversion APIs and in-app SDKs, and its creator program recruits creators from Europe and the US. Expect it to keep growing and adding features.
