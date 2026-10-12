# Competitors and international analogs: research notes

Stream: competitors. Research date: 2026-10-12.

Labels used throughout:
- **VERIFIED**: read on the cited primary page or API on 2026-10-12.
- **COMPUTED**: derived from data pulled today. The method is stated.
- **ESTIMATE / INFERENCE**: my reasoning, not a fact.
- **SECONDARY**: taken from a press article or search summary. The source is named and the claim was not checked against a primary source.

Data files in this folder:
- `app_store_metrics_2026-10-12.csv`: app ratings, review counts and download bands for about 40 apps, each with a source URL.
- `gvh_daily_export_price_variation_2026-10-12.csv`: per-chain price-variation and availability statistics computed from GVH's official daily Excel export.
- Raw downloads are in `dl/` (untrusted). Parsing scripts are in `scripts/`.

---

## 0. Headline findings (read this first)

1. **A Budapest team has already launched the founder's core idea: NomNom: Budget Meal Planner.**
   - Publisher: Z Gen Kibernetika Kft; developer name in the stores: Neo App Labs.
   - Released on iOS on 2026-07-23. It has 703 ratings on the HU App Store, averaging 4.82 (VERIFIED, iTunes Lookup API, `id=6788049718&country=hu`).
   - It is also on Google Play with 1K+ downloads and a 4.7 rating (VERIFIED, play.google.com `id=com.nomnomplanner`).
   - It plans a week of dinners around real Aldi, Lidl, Tesco, SPAR and Kifli prices "from the GVH Árfigyelő and store catalogues". It builds the shopping list with a running total and shows macros and diet filters.
   - Price: 7,990 Ft/year with a 7-day trial, or 1,490 Ft/month (VERIFIED, https://nomnomplanner.com/hu/ and https://nomnomplanner.com/terms/).
   - It does not use location: its privacy policy says "We do not collect … precise location" (VERIFIED, https://nomnomplanner.com/privacy/).
2. **GVH publishes an official daily bulk export, linked from the Árfigyelő footer as "Napi termékadatok letöltése".** This adds to and partly corrects the "undocumented API only" framing.
   - URL: https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx (VERIFIED, the link is present in the site JS bundle; HTTP 200; last-modified 2026-10-11 02:00 GMT; about 2.09 MB).
   - Contents (COMPUTED by parsing the file):
     - 25,400 product×chain rows, 16,040 product ids, 161 categories, 9 chains and 1,829 stores.
     - Each row has min and max price, min and max unit price, the number of chains carrying the product, the number of stores carrying it, and the chain's total store count.
     - It has no per-store prices and no split by price type (NORMAL, DISCOUNTED or LOYALTY).
3. **Store-level price differences are small and concentrated in two chains. Store-level availability differences are large.** COMPUTED from the export above:
   - Share of rows where the min price is below the max price: SPAR 27.6% (average spread 30% when it varies), Tesco 25.4% (average spread 9.3%), Auchan 1.4%, Lidl 0.9%, and 0% for Aldi, Penny, dm, Rossmann and Müller. That is 7.6% of all rows.
   - Share of a chain's products carried in at least 80% of its stores: Aldi 100%, Penny 94%, Lidl 87%, Auchan 28%, SPAR 14.5%, Tesco 11%.
   - So "best LOCAL prices" is mostly a chain choice plus a question of whether the nearby SPAR or Tesco format carries the item. Pricing by store matters only for SPAR (and a little for Tesco). INFERENCE.
4. **The crowded spaces in Hungary are:**
   - product-level price comparison: GVH (free), Árnéni, Cashmap, Mizu and many hobby projects;
   - leaflet and deal aggregation: Prospecto, Ajanlatok.hu, Kimbino, Akcióvadász, PromoAkcios and the retailer apps;
   - free recipe media: Nosalty, Mindmegette, Street Kitchen, Kifli Séf, Penny, Lidl Konyha.

   Since July 2026, priced budget meal plans are also contested, by NomNom and Lefőzlek.
5. **What remains open (INFERENCE):**
   - nutrition-first ("healthy") planning that covers breakfast, lunch and dinner, with human-tested Hungarian recipes;
   - multi-week or monthly planning;
   - optimising a two-store split basket for the stores near the user;
   - showing which items the specific nearby SPAR or Tesco format carries;
   - loyalty-price awareness.

   NomNom's text reviews complain about repetitive and AI-written recipes and the lack of breakfast (VERIFIED, App Store reviews RSS). That is a concrete opening, but it is narrow.

---

## 1. Árnéni (arneni.com): deep-dive

Sources: https://arneni.com/, https://arneni.com/terms, https://arneni.com/melyik-bolt, https://arneni.com/magic-kosar, https://arneni.com/legolcsobb-bevasarlas, https://arneni.com/kerdezd-arnenit (all VERIFIED 2026-10-12, fetched with curl, copies in `dl/arneni/`).

**What it is.** A web-only, independent price comparison and deal tracker. Its footer reads "© 2026 Árnéni.com (Arvago Systems)".
- Chains: 13 claimed (Aldi, Tesco, Lidl, Penny, Auchan, Spar, dm, Rossmann, Kifli, Müller, Metro, CBA, Coop). The site says "naponta több mint 17 000 akciót követ" (it tracks more than 17,000 deals a day). Both are VERIFIED as claims on /legolcsobb-bevasarlas.
- Data sources named in the terms (§3): the GVH Árfigyelő, retailer websites and promotional materials, and public online prices such as Kifli.hu. It also uses "AI-alapú szórólapfeldolgozás" (AI reading of leaflets).

**Features (VERIFIED from page text):**
- Akciók (deals).
- Magic kosár: an "AI" weekly deal basket built from a household profile, shopping frequency, a weekly budget in Ft and the stores the user visits. It has a "reliability level" filter for offers (GVH or store-confirmed versus unknown).
- Melyik bolt?: the cheapest store for a basket, a combined cheapest list across selected stores, a price grid, and unit-price versus pack-price views.
- Szórólapok (leaflets), Ártrendek (price trends) and Értesítő (alerts).
- Listám (list), with PDF export on Premium.
- Kérdezd Árnénit: an AI chat that is rate-limited for free users.
- Notes on loyalty prices (Lidl Plus, Penny Kártya, dm-active).

**Location:** none. No `navigator.geolocation` call appears in any downloaded page (COMPUTED by grep across 7 pages), and there is no near-me or store map. Store choice is by chain only.

**Recipes and meal plans:** none. Magic kosár is a weekly deal basket, not a meal plan.

**Apps:** no native app. Árnéni returns no results in the HU App Store search or on Google Play (VERIFIED, iTunes Search API "arneni" and "árnéni" give 0 results; the Play search shows no match). It is a website only.

**Pricing:** free tier of 15 searches, plus 50 with registration. Premium costs **1,475 Ft/month including VAT**, through Stripe, and can be cancelled at any time (VERIFIED, homepage and terms §5). Affiliate links are disclosed.

**Company and legal (VERIFIED, terms):**
- The terms are "Hatályos: 2025. január 1-jétől · Módosítva: 2026. március 27." (in force from 1 January 2025, amended 27 March 2026).
- The operator is "az Egyesült Királyságban bejegyzett vállalkozás" (a UK-registered business). UK law and the English courts govern.
- Processors: Stripe, Supabase, Cloudflare and GA4.
- The terms claim EU Database Directive protection over Árnéni's own database and ban scraping. This is ironic, since the data is largely GVH-derived.

**Company registry check:** UK Companies House search returns "No results found" for both "arvago" and "arneni" (VERIFIED, https://find-and-update.company-information.service.gov.uk/search/companies?q=arvago). "Arvago Systems" is probably a trading name, not the registered entity (INFERENCE). I did not use e-cegjegyzek or Opten, because their search is a form submission. The registry identity is therefore UNRESOLVED.

**Traction signals:**
- Domains: arneni.com was registered on 2026-03-13 (VERIFIED, whois) and arneni.hu on 2026-03-14 (VERIFIED, whois.nic.hu). The terms' "effective 2025-01-01" date predates the domain, which suggests an earlier brand or domain or a boilerplate date (INFERENCE).
- Web traffic: arneni.com is not in the Tranco top-1M list (VERIFIED, https://tranco-list.eu/api/ranks/domain/arneni.com returns empty ranks). For comparison, cashmap.hu ranks about 777k, gvh.hu about 271k, nosalty.hu about 20.5k, mindmegette.hu about 55.7k and streetkitchen.hu about 74.7k (VERIFIED, same API, 2026-10-11).
- Social: the Facebook page facebook.com/arneni.hu sits behind a login wall, so the follower count was not obtained.
- Press: none found through web search.
- Conclusion: there are no public traction numbers, and the signals point to a small, young operation (INFERENCE).

**Stack (VERIFIED from HTML):** static pages, Chart.js, jsPDF and html2canvas from cdnjs, Supabase for authentication, Stripe and a PWA manifest. This looks like a lean one-team build (INFERENCE).

---

## 2. Other Hungarian players

### 2.1 NomNom: Budget Meal Planner (direct competitor)

**Basic facts:**
- Publisher: Z Gen Kibernetika Kft (Hungary). Developer name in the stores: Neo App Labs. The site says "Budapesten készül" (made in Budapest). Domain registered 2026-07-08 (VERIFIED, whois).
- iOS release 2026-07-23, version 1.0.19 on 2026-10-11. HU App Store: 4.82 from 703 ratings. The US store has 9 ratings, and the app was not found in the GB, DE, AT, RO or SK storefronts via lookup (VERIFIED, iTunes Lookup). Hungary is effectively its only market.
- Google Play: 1K+ downloads, 4.7 rating, updated 2026-10-08 (VERIFIED). The terms say "On Google Play, NomNom Plus is currently sold in Hungary only."

**What it does (VERIFIED, https://nomnomplanner.com/hu/ and /en/):**
- A weekly dinner plan built from the user's store, budget, household size, diet and sensitivities, and kitchen appliances (airfryer, microwave, oven).
- Price per plate and macros for each dinner. Swapping a meal updates the total.
- A shopping list sorted by aisle with exact products (for example "Húsmester csirkemellfilé").
- Moods: high-protein, low-calorie, comfort and "trash".
- Gluten-free, lactose-free and vegetarian plans.
- Claims on the site: "1 000+ követett termék, 5 bolt, 36 vacsora a tervezőben, 27 EU-ország" (1,000+ tracked products, 5 stores, 36 dinners in the planner, 27 EU countries). Prices come from "a GVH hivatalos Árfigyelőjéből és bolti katalógusokból" (GVH's official Árfigyelő and store catalogues).

**Pricing (VERIFIED):** 7,990 Ft/year with a 7-day trial, or 1,490 Ft/month with no trial. Billing goes through Apple or Google.

**Privacy (VERIFIED, privacy page):** no accounts, plans stored on the device, PostHog analytics hosted in the EU, and no precise location collected.

**Marketing:** a paid creator (UGC) program run through "earnbycontent" (Brave New, Inc.): "Paid monthly, per video … first agreement starts at 10 videos per month" (VERIFIED, https://nomnomplanner.com/ambassador/). The privacy page mentions ad-click measurement. Both point to paid acquisition (INFERENCE).

**Rating velocity:** 703 ratings in 81 days, about 8.7 per day (COMPUTED). Only 9 written reviews appear in the public RSS (https://itunes.apple.com/hu/rss/customerreviews/id=6788049718/sortby=mostrecent/json). That ratio points to in-app rating prompts (INFERENCE).

**Written reviews (VERIFIED, RSS):** 4×5★, 1×3★, 4×1★. The 1★ themes:
- "Folyamatosan ugyan azt a 10 ételt pörgeti. Sok ételnél nincs recept." (It keeps cycling the same 10 dishes; many dishes have no recipe.)
- "AI slop ételek" (AI slop dishes).
- "A receptek nincsenek érthetően leírva, AI írta … elkészítési idők sem stimmelnek" (The recipes are not clearly written, AI wrote them; the cooking times are wrong too.)
- "Adjon már reggelit" (Give me breakfast already).

The 3★ review complained about the paywall.

**Its own data finding** (VERIFIED as NomNom's claim, https://nomnomplanner.com/hu/blog/heti-vacsora-ara/, 2026-07-09):
- The same 5 dinners for 3 people cost 18,893 Ft at Aldi, 19,750 at Lidl, 20,095 at SPAR, 20,987 at Tesco and 25,700 at Kifli. The spread across the four physical chains is 11%; Kifli is 36% above the cheapest.
- Own-label staples cost the same at every chain (carrots 489 Ft/kg and frozen peas 339 Ft at all four). The differences come from fresh and branded items.
- Implication: comparing prices per recipe saves roughly 10% a week, not 30–40% (INFERENCE from their data).

### 2.2 Lefőzlek (lefozlek.hu, Business Gravity Kft)

- iOS app launched 2026-10-01 (VERIFIED, iTunes Lookup `id=6763793215`). The domain dates from 2015 (whois.nic.hu). No Android app was found.
- Features: save recipes from TikTok, Instagram, Facebook, Pinterest or any URL; photo or scan import; a weekly plan; a one-tap shopping list grouped by store aisle; and "Adagonkénti ár és tápérték a legtöbb recepthez" (price per portion and nutrition for most recipes).
- Freemium: Plusz unlocks unlimited saves, planning any week, and so on. The price was not seen.
- The site has 259 tested recipes, with an "Olcsó receptek – kevesebb mint 1500 Ft-ból" (cheap recipes, under 1,500 Ft) collection of 136 recipes (VERIFIED, homepage).
- Price estimates are "bolti árak alapján, hozzávalónként … automatikus, tájékoztató jellegű" (based on store prices, per ingredient; automatic and indicative). The price source is not named (VERIFIED, /rolunk).

### 2.3 Cashmap (cashmap.hu, Cashmap Kft)

- Company: seat in Pap, cégjegyzékszám 15-09-088643 (VERIFIED, https://cashmap.hu/dokumentumok/impresszum). Domain registered 2021-05-10.
- Product: price comparison for Aldi, Lidl, Penny, Auchan, Ecofamily, Spar, Tesco, dm and Rossmann. The error-report form also lists CBA Príma, Coop, Reál, Metro, Kifli, "SPAR-WOLT" and "Aldi Árfigyelő".
- Features: alerts on favourites, a "Kalkulátor" that works out which store is cheapest for up to 100 items, a shopping list and a barcode scanner (VERIFIED, App Store description and site).
- Model: subscription. A 14-day trial, then Standard 1,290, Plus 1,999 or Premium 2,999 Ft/month, with a "42.000-es termék adatbázis" (42,000-product database) (VERIFIED, ÁSZF dated 2024-03-20).
- Traction: iOS 137 ratings (4.36) since 2023-09; Android 5K+ downloads, 278 reviews (VERIFIED).
- The site currently says "A lakossági regisztráció technikai okok miatt nem elérhető!" (consumer registration is unavailable for technical reasons) and invites business registrations by email (VERIFIED). This is a weak-traction signal for a paywalled consumer price comparison (INFERENCE).

### 2.4 Mizu – Árfigyelő (MizuAPP)

Community-based price comparison (Lidl, SPAR, Tesco, ALDI, Auchan, Penny, Príma, Reál and others) with a barcode scanner, gamified price submissions and a list. Android 100+ downloads, updated 2026-09-17 (VERIFIED, Play `hu.mizu.app`). Domain mizuapp.hu registered 2025-10-02.

### 2.5 Smartlyst

App Store id1435072793 returns 0 results from iTunes Lookup (hu and us), and the App Store page returns 404 (VERIFIED). smartlyst.com now serves an unrelated "Shopisquare" holding page (VERIFIED via WebFetch). A third-party tracker (appfollow) reports the last update as 2021-05-27 (SECONDARY). **Status: defunct.**

### 2.6 Recipe media and how they make money

**Nosalty**
- Publisher: Central Médiacsoport Zrt (VERIFIED, https://www.nosalty.hu/impresszum).
- App: "60.000 recept" (60,000 recipes), shopping list, "Kajacsúszka", cook mode.
- iOS: 510 ratings; last update 2023-01-12, so it is stale. Android: 100K+ downloads, 3.9 rating, updated 2026-08-11 (VERIFIED).
- The site has free editorial weekly menus ("Heti menü – olcsó receptek…", "7 nap 7 étel").
- Model: display advertising and sponsored content, plus newsletter consent for "üzleti partnerei … ajánlataival" (its business partners' offers) (VERIFIED, impresszum and newsletter text).

**Mindmegette**
- Publisher: MEDIAWORKS HUNGARY ZRT. The impresszum includes ad-sales contacts and the self-serve ad platform adsmart.hu (VERIFIED, https://www.mindmegette.hu/impresszum). It has a /heti-menu page.
- No standalone Mindmegette app was found in the HU App Store or Play searches (VERIFIED, absence in search results).

**Street Kitchen**
- Publisher: SK Sales House Kft. The site has "SK Shop", "SK Guide", "Heti menü" and a "Head of Sales" role (VERIFIED, https://streetkitchen.hu/impresszum/).
- New app on iOS since 2026-02-04 with 456 ratings; Android 10K+, 4.8 (VERIFIED). It offers recipes, cook mode, a shopping list from recipes, and a restaurant guide with a map (near me).
- Model: branded content and ads, merchandise and shop, print (INFERENCE from the imprint structure).

**Other recipe and diet apps:**
- Kisfazék: recipe community, Android 1K+ (VERIFIED).
- Myreset (iOS, 2026-05): women's healthy meal plans with calorie calculation (VERIFIED, 7 ratings).
- WFit: diet recipes (VERIFIED, 18 ratings).
- Kalóriabázis (CalorieBase): iOS app last updated 2020-11-22 (VERIFIED in iTunes search output).

### 2.7 Retailer apps and recipes

- **Kifli.hu: recipe-to-cart already exists.** The "Kifli Séf" pages are at https://www.kifli.hu/sef/receptek (VERIFIED).
  - The page data shows `recipesCount: 3651`, and the chef navigation shows `totalCount: 456`.
  - Each recipe shows "Adagonkénti ár" (price per portion, for example 1,796 Ft) and a "Kosárba tesz" (add to cart) button.
  - Three basket variants: "A séf választása" (chef's choice), "Legolcsóbb – Spórolj akár 16%-ot" (cheapest – save up to 16%) and "BIO/Organikus".
  - Per-ingredient substitutions, "Valószínűleg otthon van" (probably at home), and nutrition in kcal.
  - Creators include chefs and influencers.
  - Kifli apps: iOS 18,959 ratings, 4.96; Android 100K+, 4.9 (VERIFIED). Kifli has no meal-plan feature (no such strings in its pages; COMPUTED by search).
- **Penny HU:** 546 recipes, with a "Pénztárcabarát fogások" (budget-friendly dishes) category and "PENNY SÉF" (VERIFIED, https://www.penny.hu/receptek). Penny app: 1M+ Android downloads.
- **Lidl HU:** Lidl Konyha at https://konyha.lidl.hu/ has recipes with chef Mizsei Jani, desserts and an "online főzőiskola" (online cooking school). No prices or basket on the homepage (VERIFIED). A SECONDARY press report says the printed cookbook series reached about 4 million copies and that the 2025 Christmas volume was available only through Lidl Plus. Lidl Plus HU iOS: 6,206 ratings.
- **SPAR, MySPAR:** loyalty, coupons, leaflets and a store finder with location. 1M+ Android downloads, 103K reviews; iOS HU 75,320 ratings (VERIFIED). spar.hu returned 403 to curl, so its recipe pages were not checked (no bypass attempted). The 2017 "30 napos SPAR Életmód" health app (SECONDARY, ESM Magazine) no longer appears in store search (VERIFIED, absence).
- **Tesco:**
  - Clubcard HU: Android 1M+ and 84.8K reviews; iOS 11,870 ratings.
  - Tesco Online: Android 500K+.
  - tesco.hu and bevasarlas.tesco.hu returned 403 to curl, so the recipe features were not verified.
  - SECONDARY (Pénzcentrum 2026-08-04, citing Portfolio): Tesco is reportedly preparing to sell its Central European business, with Hungary as a separate package; 200 HU stores. This is a market-structure risk.
- **Aldi HU:** offers, shopping list, nearest-store finder; 500K+ downloads (VERIFIED). /hu/receptek.html redirects to the homepage.
- **Auchan:** OkAuchan iOS 27,299 ratings; Auchan Online Android 100K+. auchan.hu/receptek returns 404.
- **Coop Klub:** map search for the nearest store; 100K+ (VERIFIED).
- Retailer apps have mass reach (1M+ installs) but are loyalty and leaflet tools. None advertises meal planning (VERIFIED from store descriptions).

### 2.8 GVH Árfigyelő: is there a mobile app?

- No native app. iTunes search for "gvh" returns only German transport apps, and the Play searches for "GVH árfigyelő" return no GVH app (VERIFIED).
- The site is installable as a PWA: /site.webmanifest has `"display": "standalone"` (VERIFIED).

### 2.9 Projects built on the Árfigyelő data (GitHub and others)

GitHub repository search, VERIFIED via api.github.com/search/repositories:
- "arfigyelo" returns 19 repos. Many are unrelated price trackers (Steam, Notino, electricity).
- `landov/arfigyelo` (Kotlin Android app on the GVH API). The README says: "Due to legal concernes it will not be finished nor published."
- `ny3rs/arfigyelo-search-mcp` (2026-01): an MCP server indexing "the daily Árfigyelő Excel export". Its code points at the azureedge xlsx URL.
- `Mukedlii/arfigyelo-price-monitor` (2026-03): an Apify actor described as "~2,000 food products … no proxy needed".
- `BME-School/arfigyelo_web` and `arfigyelo_db` (2023): a student project scraping Tesco, Auchan and Aldi.
- `FasiSandor/multi-akciok` (2026-10): a deals search and price comparison PWA on Vercel.
- `botondboros/ecommerce_agent` (2026-03): an "AI-powered weekly grocery agent for Hungary" scraping Kifli, Auchan Online and Tesco with Playwright.
- `MarkAttila420/arfigyelo-scraper` (2025).

Apify store search: no public Árfigyelő actor is listed. Tesco-HU and Kifli-HU scrapers exist with 2 users each (VERIFIED, api.apify.com/v2/store).

Taken together, hobby and hackathon activity is high, few projects ship as consumer products, and at least one author stopped over legal concerns (INFERENCE).

### 2.10 Leaflet and deal aggregators (Hungary)

VERIFIED from store data:
- Prospecto.hu: Android 500K+, 2.26K reviews; last update 2025-12-09.
- Ajanlatok.hu (Kingbee B.V.): Android 10K+, 629 reviews; iOS 159 ratings.
- Kimbino: iOS HU 435 ratings.
- Promotheus: iOS HU 273 ratings.
- Akcióvadász (Loginet): Android 10K+, iOS 70 ratings.
- PromoAkcios: new in 2026-06; iOS 64 ratings.

These are crowded, ad and retailer funded, and have no meal-planning angle.

### 2.11 Substitutes: meal kits and prepared-meal delivery

- **Fit Food Way HU** (fitfoodway.hu): daily plans "napi 6.000 Ft-tól" to "napi 10.000 Ft-tól" (from 6,000 to from 10,000 Ft a day) depending on the program, with discounts for 5 or 20 days (VERIFIED, homepage).
- **Teletál** (teletal.hu/etlap): menu items 305–2,055 Ft; the median listed item is 880 Ft (COMPUTED from 45 price strings on the menu page; this mixes pastries, soups and mains). It has diet lines (IR, Zero, Vega, Alakreform).
- **Interfood** (traditional, fitness, slimming, zero and vegan menus) and **CityFood** (diet boxes): live (VERIFIED, homepages). Prices were not extracted.
- **Classic meal kits are thin or dead:**
  - hamm.hu now redirects to an unrelated "Mediacity" page (VERIFIED). HAMM recipe boxes were reviewed in 2022 (SECONDARY, welovebudapest).
  - gourmetbox.hu has no DNS A record (VERIFIED, dig).
  - hellofresh.hu does not resolve (VERIFIED). HelloFresh is not present in Hungary (INFERENCE).
  - chefmarket.hu is a HoReCa wholesaler, not a meal kit (VERIFIED).
  - The "Kifli Bisztró" meal-kit-style dishes launched in 2021 (SECONDARY, economx); current status not verified.
- **Third-party market size:** ecommercedb estimates the HU meal-kit e-commerce market at US$16.6M by 2028 (SECONDARY, paywalled estimate, low confidence).
- **Price anchor (COMPUTED from the figures above):**
  - NomNom's home-cooked dinner is about 1,260–1,400 Ft per person at physical chains.
  - Fit Food Way charges 6,000–10,000 Ft per day for all meals.

---

## 3. International analogs and lessons

### 3.1 Croatia: mandated machine-readable price lists (2025) and the apps on top

**The mandate:**
- Retailers must publish daily price lists on their websites "in digital formats suitable for automatic processing and comparison" from 15 May 2025. This covers food, beverages, cosmetics, cleaning and household goods (VERIFIED, https://www.croatiaweek.com/new-price-listing-obligations-for-croatian-retailers-introduced/, 2025-05-03).
- An expansion published in NN 101/2026 extends the rules to all traders and service providers with websites, in CSV or XML. Retailers must publish every working day by 08:00, keep files for 30 days and use a fixed file-naming scheme. Fines are €3,000–30,000 for companies. The start date moved from 1 Oct to **17 Nov 2026** (SECONDARY but detailed, https://www.digitalmomentum.hr/en/blog/anchor-price-digital-price-list-croatia).

**The apps (VERIFIED, Google Play HR):**

| App | Developer | Downloads | Reviews | Note |
|---|---|---|---|---|
| Usporedi cijene | NVTEH d.o.o. | 10K+ | 105 | |
| Moje Cijene | Artemis Alfa | 10K+ | 143 | compares "according to address and distance": the location angle |
| Košarica | (not recorded) | 1K+ | (not recorded) | |
| Usporedi Me | (not recorded) | 500+ | (not recorded) | lets users pick up to 10 nearby store locations |

**Infrastructure:** the open-source Cijene API (https://cijene.dev, GitHub senko/cijene-api, 120 stars, created 2025-05-20) offers free registration plus paid plans for current and historical prices (VERIFIED). The open-source front-end Disscount builds on it (SECONDARY).

**Lesson (INFERENCE):** mandated open data quickly produced an open-source data layer and many small look-alike apps, with no breakout consumer winner visible after 17 months (top apps at 10K+ downloads). Data access stops being a moat once it is open. Hungary's GVH data is in the same position.

### 3.2 Slovakia: cenyslovensko.sk (Ministry of Finance)

- Live as a pilot since July 2025. Six chains take part (Billa, Fresh Plus, Kaufland, Lidl, Terno, Tesco). Chains upload by 05:00 and the site publishes at 06:00. Coverage is about 300 products in 15 food types (SECONDARY, Slovak Spectator via search, and startitup.sk).
- Ministry figures from launch to Feb 2026: "viac ako 956-tisíc zobrazení" (more than 956,000 views), "vyše 41-tisíc aktívnych používateľov" (over 41,000 active users), and a cost of €126,000 excluding VAT. A consumer-association head said "nikto to nespomína" (nobody mentions it) (VERIFIED, https://www.noviny.sk/slovensko/1175178-pomaha-alebo-o-nom-nik-nevie-takto-sa-dari-porovnavacu-cien, 2026-02-26).
- An expansion by 23 basic foods (pulses, pasta, oils) was planned for 2026. Its status was not confirmed.
- I could not connect to cenyslovensko.sk from here (connection failure, not a block bypass attempt).
- **Lesson:** a state comparator with a thin assortment draws little habitual use.

### 3.3 Austria

- Statistik Austria **Preisradar** (statistik.at/preisradar) went live on 19 Jan 2026. It covers about 100 everyday products using weekly scanner data from the largest chains. It shows price development since Jan 2023, not shelf prices by store (SECONDARY, news.at, ORF and SN.at via search).
- The government's planned supply-chain price database for 2026 was called "sehr ambitioniert … Wir haben die Daten nicht" (very ambitious; we don't have the data) by Statistik Austria (SECONDARY, derStandard via search).
- The SPÖ proposed daily price reporting by supermarkets to the competition authority; adoption is not confirmed.
- **Heisse Preise** (heisse-preise.io), the open-source scraper of Austrian chains, is still online. Its banner says these stores are "nicht mehr aktualisiert" (no longer updated): Rewe DE (15.2.2024), Unimarkt (24.2.2024), Bipa (4.4.2024), MPreis (24.6.2024), Müller (3.3.2025), Lidl (27.3.2025), DM (29.7.2025), Penny (14.10.2025), Hofer (10.11.2025) (VERIFIED, https://heisse-preise.io/).
- **Lesson (load-bearing for data strategy):** a scraping-based grocery price dataset decays as retailers change or close their sites. Only government-mandated feeds are durable.

### 3.4 Greece

- e-katanalotis (2020, upgraded 2024) has been replaced by **PosoKanei** (June 2026): about 10,000 products and 10 chains, with personalised shopping lists and cheaper alternatives (VERIFIED, https://www.euronews.com/business/2026/06/18/greeces-posokanei-app-lets-shoppers-compare-supermarket-prices-in-real-time).
- PosoKanei GR App Store: 60 ratings, average 3.12 (VERIFIED, iTunes Search). The old e-katanalotis id1502408342 no longer resolves in the GR store (VERIFIED, lookup returns empty).
- **Lesson:** even government-backed apps get modest ratings and use.

### 3.5 Czech Republic: Kupi.cz (leaflets)

- Owned by Seznam.cz (51% acquired in 2014). About 2.5M monthly users and roughly 40% year-on-year growth (2025 interview). In 2025 it introduced **CPO (cost per open)** billing for retailers' digital leaflets (SECONDARY, MediaGuru: https://www.mediaguru.cz/clanky/2025/03/platba-jen-za-skutecne-procteni-kupi-cz-zavadi-metriku-cpo/).
- iOS CZ: 11,598 ratings, 4.71 (VERIFIED).
- **Lesson:** the money in deal discovery comes from retailers paying for reach, at multi-million-MAU scale, with a big portal owner behind it.

### 3.6 UK: trolley.co.uk (and mySupermarket)

- Trolley was founded by four former mySupermarket staff and launched in June 2021. By June 2022 it had been used "more than 11 million times" and compared about 7,000 products. It ran a crowdfund for £28,800 to pay "a licensing fee to use certain data" (VERIFIED, https://www.grocerygazette.co.uk/?p=33843 and https://bigissue.com/news/social-justice/food-comparison-site-close-cost-living-crisis, 2022-06). The co-founder said: "Trolley has never made any money."
- In 2026 it is alive, with "exclusive discount codes", deal lists across Sainsbury's, Morrisons, Iceland, Boots, Superdrug, Amazon and eBay, and Nectar prices (VERIFIED, homepage). That points to an affiliate and discount-code model (INFERENCE).
- mySupermarket closed in 2020 after 14 years. Its model was ads targeted on cart contents plus data services to retailers (SECONDARY, Grocery Gazette and Wikipedia via search).
- **Lessons:** consumer price comparison struggles to monetise; licensing of data and content (product images and descriptions) is a real cost; the survivor pivoted to affiliate.

### 3.7 Germany, Austria and Switzerland: Bring! and Marktguru

- **Bring!** (Bring! Labs AG; Swiss Post took a majority stake in Sept 2021):
  - The shopping list is free. Revenue comes from native ads and "commerce media" for brands and retailers (Danone, Dr. Oetker, Edeka, Lidl and others) and digital brochures (the Profital app). It claims 4.2M MAU in DACH (SECONDARY, getbring.com, markt-kom and the OMR exhibitor page; the MAU figure is undated).
  - iOS HU: 1,404 ratings (VERIFIED).
- **Marktguru** (AT 2011, DE 2016, part of ProSiebenSat.1 / SevenVentures):
  - A leaflet search app funded by brand and retailer ads, with ProSiebenSat.1 TV tie-ins.
  - Since Dec 2017 it has run **receipt-scan cashback** funded by manufacturers. It also has a recipe integration with happycart that links recipe ingredients to in-store offers (SECONDARY, Lebensmittel Zeitung, SevenOne press release and mydealz).
  - Reportedly part of ProSieben's digital portfolio up for sale (SECONDARY, forum relay of a Reuters report; unverified).
- **Lesson:** shopping lists and deals monetise through brands. Cashback per product is a proven brand-funded mechanic.

### 3.8 Meal planners that integrate grocery

- **Jow (France):**
  - The free app turns menus into a basket at the chosen retailer. Six large French grocers are partners (Carrefour, Auchan, Intermarché, E.Leclerc, Monoprix, Chronodrive). Jow puts "up to 70%" of basket items into the cart.
  - Funding: $1.5M (2018), $7M (2019) and a $20M Series A led by Eurazeo (VERIFIED, https://jow.fr/blog/frances-leading-e-recipe-and-grocery-app-jow-raises-20m-series-a-to-take-on-us-food-habits).
  - Users: "In France, Jow has 6 million users". US: Kroger and "a few hundred thousand users" (VERIFIED, https://grocerydive.com/news/kroger-jow-shoppable-recipes-grocery-ecommerce-profitability/706931, 2024-02-07).
  - Revenue: commissions or affiliate fees from grocers plus retail media and data (SECONDARY, TechCrunch 2019 and Northzone).
  - iOS FR: 47,518 ratings, 4.81 (VERIFIED).
  - It works because France has mature click-and-collect at every big chain and grocers willing to pay for basket size.
- **eMeals (US):**
  - Subscription; "as low as $4.99/month" on the 12-month plan; 14-day trial.
  - One-click list send to Walmart, Kroger, Instacart, Amazon and Shipt.
  - "More than 1 million families" (2018 press release) (SECONDARY / official press, emeals.com via search).
  - A long-lived subscription plus retailer-integration business (INFERENCE).
- **Mealime:** free, with Pro at $2.99/month (SECONDARY, App Store listing via search). A third-party estimate puts revenue at about $65k/month (low confidence).
- **Plan to Eat:** $5.95/month or $49/year, free trial, recipe clipper, planner, aisle-sorted list (VERIFIED, https://www.plantoeat.com/pricing/). A bootstrapped subscription niche.
- **Samsung Food (formerly Whisk):**
  - Whisk (Birmingham, UK) built shoppable recipes to retailer carts (clients included Tesco, Asda, Walmart and Amazon) and bought Avocando (DE). Samsung acquired it in 2019 and rebranded it Samsung Food in Aug 2023 (SECONDARY, 9to5Google and Global AgInvesting).
  - Samsung Food+ costs $6.99/month and offers personalised health-goal meal plans (VERIFIED, Samsung newsroom footnote via search).
  - It survived as a hardware ecosystem feature.
- **Yummly (Whirlpool):** the website and app shut down around 20 Dec 2024, after Whirlpool laid off the team (SECONDARY, Plan to Eat blog and The Spoon).
  - Lesson: a corporate-owned recipe app with no direct revenue is fragile.

**Survivors versus failures (INFERENCE):**

Survivors have one of these:
- (a) a retailer or brand paying for basket influence at scale: Jow, Kupi, Bring!, Marktguru;
- (b) a small loyal paying niche with low costs: Plan to Eat, eMeals, Mealime;
- (c) a strategic parent: Samsung Food, Bring! under Swiss Post.

Failures or decays came from:
- data dependency: Heisse Preise, and Trolley's licence crisis;
- a parent pulling the plug: Yummly, mySupermarket;
- thin consumer monetisation: Trolley "never made money", Cashmap's paywall.

---

## 4. Synthesis: crowded versus white space in Budapest (INFERENCE unless marked)

### Crowded or commoditised

1. **"Where is product X cheapest" across chains.** GVH does it for free with a map, list ranking and a PWA. Árnéni (13 chains, AI leaflets, 1,475 Ft/month), Cashmap (paid, 9+ chains) and Mizu (community) also compete, alongside hobby projects. The data is public and also available as an official daily Excel file.
2. **Leaflets and deals.** Prospecto 500K+, retailer apps at 1M+ each, Ajanlatok, Kimbino, Akcióvadász, PromoAkcios.
3. **Free recipes and editorial weekly menus.** Nosalty (60k recipes, "Heti menü – olcsó receptek"), Mindmegette, Street Kitchen, Kifli Séf (3,651 recipes with per-portion price and add-to-cart), Penny (546), Lidl Konyha.
4. **Since July 2026: budget weekly dinner plans priced at a chain.** NomNom (GVH plus catalogues; 5 stores; 7,990 Ft/year; 703 ratings in under 3 months; paid UGC acquisition). Lefőzlek (per-portion price and weekly plan; iOS since 2026-10-01).

### Remaining white space (narrow; validate before building)

1. **Health-first planning rather than budget-first.** Dietitian-grade nutritional balance (fibre, vegetables, protein targets) across breakfast, lunch and dinner, with human-tested Hungarian recipes. NomNom is dinners-only (36 dinners) and draws "AI slop" and repetition complaints; Lefőzlek is a recipe saver. Myreset and WFit are diet-content apps without prices.
2. **Planning for the month.** The founder's "coming weeks of the month" angle: batch cooking and leftovers across weeks, buying monthly bulk staples when they are discounted. No HU player plans more than one week ahead (NomNom generates weekly).
3. **Location as availability, not just price.** COMPUTED data shows SPAR and Tesco carry only 11–15% of their GVH-listed products in at least 80% of stores, while Aldi, Lidl and Penny carry 87–100%. A planner that knows which nearby store format actually stocks the ingredients, and splits the list between the two nearest chains, is not offered by NomNom (single store) or Árnéni (chain-level). The GVH site has a map, but not for recipe-derived lists. The per-store price gain is small: only SPAR shows meaningful store-level spread.
4. **Ingredient gaps that matter for healthy cooking.** Oats, legumes other than lentils, spinach, salmon and spices are not in GVH (established). NomNom fills such gaps with "bolti katalógusok" (store catalogues). A healthy-recipe product needs a stated estimation policy for uncovered items.
5. **Loyalty-price awareness** (Lidl Plus, Penny Kártya, Clubcard): GVH carries LOYALTY price types per chain (established). This is partly exploited by Árnéni.

### Monetisation reality check (INFERENCE)

- The HU consumer price anchor is about 1,475–1,490 Ft/month (Árnéni, NomNom) and 7,990 Ft/year (NomNom). Cashmap's 1,290–2,999 Ft/month paywall coincides with weak uptake.
- International money comes from retailers and brands (Jow, Kupi, Bring!, Marktguru). That needs either scale (millions of MAU, in a country of about 9.6M people) or retailer partnerships.
- In Hungary, Kifli already does recipe-to-cart itself, and Tesco's ownership may change.
- An affiliate or partnership with Kifli, Wolt (SPAR), Auchan Online or Tesco Online is the most plausible B2B hook.

### Data and legal implications (load-bearing)

- **Use the official daily Excel export for chain-level coverage, plus the store-level API for local detail.** The export is officially linked by GVH, which makes it the lowest-risk and most robust source.
- **Avoid building on retailer-site scraping.** Heisse Preise lost 11 store feeds in 2024–25. Trolley had to pay for data licences. tesco.hu and spar.hu already block plain curl (403).
- **At least two commercial HU products openly state that they reuse GVH data**: Árnéni (terms §3) and NomNom (homepage). Cashmap probably does too: its error form lists a store option called "Aldi Árfigyelő" (INFERENCE). None shows signs of being challenged. This is tolerance, not legal clearance. One developer abandoned a GVH-based app over legal concerns. GVH ÁFF XIV.2 (brand names and content) still needs a legal read, or a direct inquiry to or partnership with GVH.

---

## 5. Open questions

- NomNom's real installs, conversion and churn. Its plans for breakfast and lunch, health and multi-chain lists (it says Android is now available in HU).
- The legal entity behind Árnéni / "Arvago Systems". There is no UK Companies House match under either name, and an HU registry check needs a form search.
- Lefőzlek's price source (GVH or not) and its Plusz price.
- Whether GVH would grant written permission for or partner on commercial reuse, including images and brand names (ÁFF XIV.2).
- The current ToS of Kifli, Tesco, SPAR and Auchan on catalogue and price reuse (not checked here).
- Adoption of GVH Árfigyelő itself: no visitor statistics found.
- Status of Slovakia's 2026 expansion and Austria's mandatory price-platform proposal.
- Whether Hungarians pay for meal planning at all. Validate with a landing-page or pre-sale test before building.
