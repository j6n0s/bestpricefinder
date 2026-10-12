# Stream "market-user": market size and user evidence (research date 2026-10-12)

Labels: **VERIFIED** = read on the cited primary/secondary page today; **COMPUTED** = derived by me from data I pulled (method stated); **ESTIMATE** = my reasoning/assumption. "Secondary" = a news/trade summary of someone else's study (the primary was not readable).

Folder layout (all under this stream folder):
- `scripts/` my code (fetch_basket.py, analyze_basket.py, store_density.py, local_gap.py, ksh_table.py, es_print.py, pdftext.py)
- `dl_gvh/` raw GVH Árfigyelő API downloads (untrusted data): `basket_2026-10-12/cat_*.json` (37 categories, all products), `shops.json`, `chains.json`, `categories.json`
- `dl_web/` raw KSH/Eurostat/iTunes/PDF downloads (untrusted data)
- `data/` outputs: `chain_category_prices.csv`, `basket_by_chain.csv`, `same_product_spreads.csv`, `summary.json`, `budapest_store_density.json`, `key_numbers.csv`

Correction to the "already established" brief: `/api/products-by-category/{id}?offset=N` returns **12 products per page by default**, not 48. Adding `&limit=48` returns up to 48 (tested: category 18 has count 37; `offset=0` gives 12, `offset=0&limit=48` gives 37). `pageSize=` is ignored.

---

## 1. Size of the market

| Metric | Value | Label / source |
|---|---|---|
| Budapest households (HBS weighted, 2024) | **804,044** households, 1,651,512 persons, 2.1 persons/household | VERIFIED, KSH STADAT 14.1.2.1 https://www.ksh.hu/stadat_files/jov/hu/jov0042.html |
| Hungary households (HBS weighted, 2024) | 4,044,811; 9,381,986 persons; 2.3/household | VERIFIED, same table |
| Budapest population, census 2022 | ~1.68 million (1 million 682 thousand) | VERIFIED (search snippet of KSH census page + https://nepszamlalas2022.ksh.hu/en/news/turned-out-where-in-what-numbers-and-under-what-conditions-we-live says ~1.7 m) |
| Budapest households with a child under 15 (census 2022) | **17%** (national 21%, Pest county 28%) | VERIFIED https://nepszamlalas2022.ksh.hu/en/results/final-data/publication/ |
| One-person households, Hungary 2022 | about one in three households | VERIFIED, same page |
| Budapest census household count | not retrieved (census results pages return 403 to my client; did not try to get around it) | gap |
| Per-capita food & non-alcoholic beverage spend (HBS, COICOP 01), 2020 | Hungary **357,493 Ft/yr**; Budapest **384,772 Ft/yr** | VERIFIED, KSH STADAT 14.8.2.4 https://www.ksh.hu/stadat_files/jov/hu/jov0050.html (detailed COICOP tables stop at 2020; last updated 2022-11-04) |
| Food share of consumption expenditure, HBS 2020 | Hungary **26.1%**, Budapest **21.6%**; food / net income Hungary 2020 = 20.5% | COMPUTED from jov0050 and jov0001 |
| "Basic" spending share (food + housing/energy + transport), 2024 | 56.5% (2023: 56.9%) | VERIFIED, KSH STADAT 14.1.1.1 https://www.ksh.hu/stadat_files/jov/hu/jov0001.html |
| Per-capita consumption expenditure 2024 | 2,014,329 Ft/yr (2023: 1,888,298) | VERIFIED, jov0001 |
| HICP weight of food & non-alc beverages, Hungary | 2025: 201.64 per mille (20.2%); 2021 peak 23.6% | VERIFIED, Eurostat prc_hicp_inw API (dl_web/eurostat_hicp_inw_hu.json) |
| **Typical Budapest household food spend at home, 2026** | **~118,000 Ft/month** (range 105–135k) | ESTIMATE: 384,772 × food CPI 2021–25 (×1.7876) × 2026 price (×0.98) × per-capita food volume 2021–25 from national accounts (×1.023) × 2.05 persons / 12. Flat-volume variant 115k |
| Cross-check: KSH retail food sales per Hungarian household, 2025 | 122,090 Ft/month (139k incl. soft drinks + coffee) | COMPUTED: KSH STADAT 2.1.1.5 food sales 5,925,957 m Ft (https://www.ksh.hu/stadat_files/bel/hu/bel0005.html) / 4,044,811 households / 12. Includes tourist and business purchases, so it is an upper bound |
| Cross-check: survey | 143.5k Ft/month household food + soft drinks (March 2024); 45% of households spend ≤100k | VERIFIED (secondary): Nézőpont Intézet "Fogyasztói Barométer", via https://www.economx.hu/belfold/2024/05/05/nezopont-elelmiszer-barometer-talaber-krisztian-inflacio-789330/ |
| Total Budapest at-home food spend | ~1,140 bn Ft/yr | COMPUTED: 804,044 × 118k × 12 (on the ESTIMATE above) |
| Hungary retail food sales 2025 | 5,926 bn Ft (food only); food-type mixed stores total turnover 9,996 bn Ft | VERIFIED, KSH STADAT 2.1.1.5 and 2.1.1.6 (bel0005, bel0006) |

### Food inflation 2022–2026 (KSH)
- Annual food CPI (KSH category "Élelmiszerek"): 2021 +4.1%, **2022 +26.0%, 2023 +25.9%**, 2024 +2.8%, 2025 +5.3%. VERIFIED, KSH STADAT 1.1.1.2 https://www.ksh.hu/stadat_files/ara/hu/ara0002.html
- Cumulative 2025 food price level vs 2021: **+71.7%**. COMPUTED (1.260 × 1.259 × 1.028 × 1.053).
- Peak monthly food inflation 44.8% (Dec 2022). VERIFIED (GVH quoting KSH) https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2024-es-sajtokozlemenyek/hetfon-lesz-egy-eves-az-online-arfigyelo
- 2026: food prices **−1.3% YoY in Sept 2026** (−4.6% without catering; KSH's food group now includes catering services); Aug 2026 −1.4% / −4.8%; Feb 2026 +0.2% / −3.2%. VERIFIED https://www.ksh.hu/gyorstajekoztatok/far/far2609.html , .../far2608.html , GVH 2026-03-10 release https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2026-os-sajtokozlemenyek/gvh-az-arfigyelo-is-kordaban-tartja-az-elelmiszerarakat
- Per-capita household food consumption volume (national accounts): 2022 92.1, 2023 92.3, 2024 110.1, 2025 104.9 (previous year = 100). VERIFIED KSH STADAT 21.1.1.38 https://www.ksh.hu/stadat_files/gdp/hu/gdp0038.html — households cut food volume ~15% during the inflation shock, then recovered.
- NIQ: Hungarian FMCG prices +50% 2024 vs 2021; 90% of shoppers still said food prices are rising (2024, n=782). VERIFIED (NIQ slides, Holczinger-Zay, 2025-04-03) https://trade-marketing.hu/wp-content/uploads/2025/04/holczinger-zay-krisztina-niq-tmk-online-konferencia-publikus.pdf

### Policy context that changes price dispersion (load-bearing)
- **Árrésstop** (margin cap): 10% cap on gross margin for food categories (30 at start, **43 since 1 Dec 2025**), 15% for 30 drugstore categories; applies to retailers with 2023 net revenue > HUF 1 bn; fine HUF 5 m per category. In force since 17 March 2025, made statutory May 2025, sunset removed April 2026. On 2 Oct 2026 the new Prime Minister (Magyar Péter) said a phase-out is being considered, no date. VERIFIED, Index 2026-10-05 https://index.hu/gazdasag/2026/10/05/arresstop-elelmiszerarak-inflacio-kiskereskedelem-kisboltok-magyar-peter-hatosagi-ar-elelmiszerinflacio-dragulas-boltok/
- My GVH check is consistent with the cap compressing spreads on capped staples: flour, oil, sugar, milk and rice show max/min chain spreads of 1.01–1.13, while produce, bread and meat show 1.3–2.1 (see §4). COMPUTED. INFERENCE: if the cap is phased out, chain price dispersion on staples (and the value of comparison) would probably widen.

### Digital reach
- Individuals 16–74 using internet on a mobile phone: **88.7% (2025)**; by age 16–24 97.2%, 25–34 95.5%, 35–44 94.5%, 45–54 93.8%, 55–64 85.9%, **65–74 64.7%**. VERIFIED, Eurostat isoc_ci_dev_i API.
- Households with a smartphone: **82% (2025)**; mobile phone 96%; small-screen mobile internet 79%; streaming subscription 30% of households; 16% of population does not use the internet (mostly 70+). VERIFIED, NMHH household survey 2025 (n=3,020) https://nmhh.hu/dokumentum/259193/nmhh_haztartasi_kutatas_2025_riport.pdf
- Budapest smartphone households: ~680–700k. ESTIMATE (804k × 85–87%; Budapest is younger/more urban than the national 82%).

### Online grocery
- Online FMCG 2024: gross **245.3 bn Ft** (+24%); food 165.2 bn Ft (+28.8%); 34% of internet users (~1.7 m people) buy FMCG online; purchases per shopper per year: Kifli.hu 14, Tesco 9.3, Auchan 4.7. VERIFIED (secondary: Trade Magazin on PwC E-toplista, 2025-10-07) https://trademagazin.hu/en/polarizalodo-piac-folyamatos-fejlesztesek-valtozo-vasarloi-igenyek-megjelent-a-pwc-magyarorszag-legnagyobb-forgalmu-online-fmcg-szereploket-is-felsorakoztato-toplistaja/ (the PwC PDF returned 403).
- Online share of food retail ≈ **3.0% (2024)**. COMPUTED: 165.2 / 5,524.16 bn Ft (KSH retail food sales 2024). Definitions are not identical.
- Top-10 online FMCG retailers 2025: 192 bn Ft, 8.1 m orders. Secondary (search-result summary of PwC E-toplista 2025), not opened.
- Individuals who bought food/beverages online from stores or meal-kit providers in the last 3 months: **13.4% (2024)**, EU 11.0%; by age 25–34 20.1%, 35–44 19.2%, 16–24 11.6%, 65–74 4.8%. Restaurant delivery 27.1%. VERIFIED, Eurostat isoc_ec_ibgs API.
- NIQ food channel value shares (MAT Feb 2025): discounters **36.0%** (from 34.7%), traditional trade 26.5%, supermarkets incl. drug 15.9%, hypermarkets 15.8%. VERIFIED (NIQ slides above; e-commerce share not legible in the text extraction).

---

## 2. Behaviour evidence

### Shopping and deal hunting
- NIQ Shopper Trends 2024 (n≈807): store types visited in the past 4 weeks: supermarkets 85%, discounters 78%, hypermarkets 64%. Main store for most grocery spend: **discounters 40%** (2022: 34%), hypermarkets 24%, supermarkets 21%. VERIFIED (NIQ slides).
- Top 3 saving strategies in Hungary (NIQ Shopper Trends 2024): **switch to a cheaper product 58%**, buy only essentials 44%, watch the basket total 36%. VERIFIED (NIQ slides).
- Private label value share of FMCG in Hungary **33.3%** (global 23.3%). VERIFIED (NIQ slides).
- Leaflets (Shopfully, adults): **71% browse deal leaflets weekly**, 85% at least monthly, 6% never; 30–33% digital-only, 43% both, ~21% print-only; 80% say leaflets influence purchases. Budapest has more digital-only readers. VERIFIED (secondary: MediaFuture 2025-03-18 https://mediafuture.hu/content/2025/03/18/akcios-ujsag-shopfully/ ; fielded by Ipsos in Aug 2024 per another summary).
- Shopfully/Flipp "State of Shopping 2026" (8 countries, 6,600–7,000+ respondents): Hungary 26% buy only on promotion or postpone (EU 15%); 36% actively seek promotional/best-value products (EU 52%); 45% name price/value as the key factor; 63% buy regularly from the same retailer; **62% mainly choose stores with a loyalty programme** (EU 51%); 49% would switch store for a better offer (EU 56%); 80% search online before buying (EU 91%); 29% would share personal data for better offers (EU 38%). VERIFIED (secondary: Prím 2026-09-24 https://hirek.prim.hu/cikk/2026/09/24/a_magyar_vasarlo_nem_mond_le_csak_kivar).
- Discounter household penetration 96% in 2020 (GfK). Search-snippet only; the source page now 404s. Treat as unverified.
- Stores per week / trips per week: no public 2025–26 figure found (NIQ Shopper Trends and YouGov/GfK ConsumerScan are paid). Gap.

### GVH Árfigyelő usage
- Launch weekend (1–2 July 2023): ~200k unique visitors, 12.5 m downloads, 51k product searches. VERIFIED (secondary: mfor 2023-07-04 https://mfor.hu/cikkek/makro/gvh-nagyon-nepszeru-az-online-arfigyelo-20230704.html)
- ~650k unique visitors in month 1; **~1.4 m unique visitors in the first 5 months**; ~900k free-text searches; most searched: milk, cheese, chicken breast, sugar, eggs. VERIFIED (secondary: HVG 2023-12-01 https://hvg.hu/gazdasag/20231201_A_GVH_elarulta_mit_keresnek_a_magyarok_az_Arfigyelon)
- An independent (non-audited) traffic measure in July 2023 suggested daily uniques rarely above 40k and falling (media1.hu; page returned 403, so only the search summary was seen). Unverified.
- No 2024–2026 usage figures were found in GVH releases (the 2024 anniversary release and the 2026-03-10 release give coverage but no visitor numbers). Gap: ask GVH.
- GVH-quoted Makronóm Intézet estimate: the Árfigyelő saved households **~20 bn Ft in 3 months** (winter 2023–24). VERIFIED that GVH quotes it (2026-03-10 release). COMPUTED: ≈ **1,650 Ft per household per month** averaged over all 4.04 m households. Method unknown; the source is a think tank.
- Coverage today: 140 categories, 5,000+ products, 1,817 stores, 6 grocery and 3 drugstore chains (GVH 2026-03-10). VERIFIED. My /api/shops pull on 2026-10-12 returned **1,829** stores. COMPUTED.

### Food waste (NÉBIH / Maradék nélkül, 2025 survey: 153 households, Q4 2025, 1-week diary)
- **60.68 kg/person/year** household food waste; **20.80 kg avoidable** (34.3%), 34.3 kg unavoidable, 5.6 kg potentially avoidable. Avoidable waste is down by a third since 2016 (33.14 kg). Nationally ~197k t/yr avoidable. VERIFIED https://portal.nebih.gov.hu/documents/10182/2075745350/Kutatasi+osszefoglalo_Haztartasi+elelmiszerhulladek+felmeres+2025.pdf
- Most avoidable waste is cooked/ready meals, fresh fruit and vegetables, and bakery (75.76%). Most common causes: **forgot it / it expired, bought too much, cooked too much**. VERIFIED (same).
- Households estimated their own waste at 22.71 kg vs 60.68 measured (63% underestimate); 86.9% think they could reduce waste (13.7% "significantly"). VERIFIED (same).
- Series 2016–2025 (total kg/person): 68.04, 65.49, 61.51, 59.86, 61.96, 59.72, 60.68. VERIFIED (same).
- Value of avoidable waste per 2.05-person household: **~3,600–7,100 Ft/month** at 1,000–2,000 Ft/kg. ESTIMATE (the Ft/kg value is my assumption).

### Diet-related health (OECD/European Observatory, State of Health in the EU, Hungary Country Health Profile 2025)
- Self-reported adult obesity **22% (2022)** vs EU 15%; **measured obesity 33% (2019)**, up from 29% in 2009; men 26% → 36%. Adolescent overweight/obesity 15% (2010) → 25% (2022), one of the highest in the EU. Daily fruit 41% and vegetables 33% among adults. Behavioural and environmental risks caused 35% of deaths in 2021 (EU 29%). VERIFIED https://www.oecd.org/content/dam/oecd/en/publications/reports/2025/12/country-health-profile-2025-country-notes_7e72146d/hungary_3e575303/ddb34486-en.pdf
- (Older) 2019 profile: ~28% of deaths in 2017 were attributable to dietary risks. Secondary (search summary of the OECD 2019 profile).

### Interest in healthy eating / food content (proxies)
- Recipe sites: Nosalty.hu and Mindmegette.hu would be in the top 10 Hungarian sites by monthly reach; the 10th site had 1.40 m monthly real users, so each has **>1.4 m monthly real users** (16–75, July 2026, Gemius-EDME). VERIFIED (NMHH report) https://nmhh.hu/dokumentum/260952/online_kozonsegmeres_julius.pdf ; the ">1.4 m" is my inference from the chart.
- App Store HU rating counts on 2026-10-12, a proxy for installed base (COMPUTED from the iTunes Search API, country=hu): Yazio **68,170**; MySPAR 75,320; Mein dm 50,346; OkAuchan 27,299; Kifli.hu 18,959; Tesco Clubcard 11,870; Lidl Plus 6,206; Foodvisor 5,552; Listonic 3,954; MyFitnessPal 3,411; ALDI HU 3,367; Bring! 1,404; Diverzum (student discounts) 782; **NomNom: Budget Meal Planner 703 (launched 2026-07-23)**; Nosalty 510; Street Kitchen 456; Cashmap 137. Nutrition tracking (Yazio) has a much bigger HU iOS base than recipe or shopping-list apps.

---

## 3. Willingness to pay and monetisation

- **Direct HU benchmark (new, load-bearing): NomNom: Budget Meal Planner** (seller Z Gen Kibernetika Kft., brand Neo App Labs, "made in Budapest"). iOS. HU App Store: 4.8★ from **703 ratings**, launched 2026-07-23. It plans a week of dinners to a budget and household size, builds a shopping list with real shelf prices (Aldi, Lidl, Tesco, Spar; the website adds Kifli), shows price per serving and macros, and has diet filters. **Price: NomNom Plus 7,990 Ft/year (7-day trial) or 1,490 Ft/month.** Its website says Hungarian prices come "from the GVH official Árfigyelő and store catalogues". VERIFIED https://apps.apple.com/hu/app/nomnom-budget-meal-planner/id6788049718 and https://nomnomplanner.com/
- Árnéni Premium 1,475 Ft/month (from the brief, not re-checked).
- Cashmap (HU): compares 9 chains, deal alerts, a calculator for where to buy a list of up to 100 products, shopping list; 137 HU App Store ratings. Pricing not stated. VERIFIED https://apps.apple.com/hu/app/cashmap/id6463898604 , https://cashmap.hu/
- Kifli.hu affiliate (VIVnetworks catalogue): **€5 per new customer's first order, or per customer lapsed 60+ days; nothing for existing customers; 3-day cookie.** VERIFIED https://www.vivnetworks.com/hu/affiliate-katalog/kifli-hu/ (listing date not shown). Dognet (HU affiliate network) pays per % of order or a fixed fee per advertiser; payout threshold €100. Secondary.
- Global subscription benchmarks (RevenueCat State of Subscription Apps 2026, 115k+ apps, CY2025): download-to-paid by day 35: **freemium median 2.1%**, hard paywall median 10.7%; Health & Fitness 2.9% (top quartile 6.2%); trial-to-paid H&F 37.7%; Western Europe median D35 2.0%. Eastern Europe is not reported. Food & Drink is not broken out. VERIFIED https://www.revenuecat.com/state-of-subscription-apps/
- Hungarian purchasing power per capita €12,323, 60% of the European average (GfK 2025). Secondary (Trade Magazin summary).
- Streaming subscriptions in 30% of households (NMHH 2025). This is evidence that a sizeable minority pays for digital subscriptions. VERIFIED.
- No Hungary-specific public survey on the share of people paying for apps was found. Gap.

---

## 4. My GVH API check: what store choice is worth (COMPUTED, 2026-10-12)

**Method.** I pulled every product in 37 GVH leaf categories (1,271 chain-price entries for the 6 grocers plus a few drugstore entries) at ≤1.5 requests/second. For each category and chain I took the cheapest unit price (Ft/kg, l or piece) at regular (NORMAL) price, the cheapest at min(NORMAL, DISCOUNTED), the cheapest also allowing LOYALTY, and the **median** regular unit price across that chain's products in the category (the "typical item" a non-optimising shopper might pick). I priced a **monthly basket of 27 staples for a 2.05-person Budapest household** using KSH at-home consumption quantities for Budapest (KSH STADAT 14.8.2.5, 2020, Budapest column: e.g. milk 52.9 l, poultry 23.7 kg, pork 12.4 kg, potatoes 25.6 kg, bread 25.5 kg, eggs 139 per person per year; splits inside a KSH line such as poultry = 50% breast / 50% leg are my ESTIMATE). Two missing chain-category cells (Aldi rice, Auchan cabbage) were filled with the cross-chain median. Script: `scripts/analyze_basket.py`.

**Monthly 27-staple basket (Ft):**

| Chain | cheapest item, regular price | cheapest item incl. promo | typical (median) item |
|---|---|---|---|
| Lidl | 29,008 | 29,008 | **36,067** |
| Aldi | 30,387 | 30,387 | 39,199 |
| Auchan | 31,197 | 31,165 | 43,118 |
| Spar | 32,459 | 29,966 | **46,322** |
| Penny | 33,982 | 33,982 | 38,694 |
| Tesco | 34,061 | 32,954 | 43,903 |
| Cherry-pick across all 6 | 27,085 | 26,103 | 34,295 |

- Cheapest vs priciest chain: **~5,000 Ft/month (14.6–14.8%)** when buying the cheapest item; **~10,250 Ft/month (22%)** when buying the typical item (Lidl vs Spar). Cheapest chain vs the average chain: 2.2–2.8k (cheapest item) or 5.2k (typical item).
- Cherry-picking across all 6 chains saves only **1.8–2.9k Ft/month** more than the best single chain, and would mean visiting up to 6 stores.
- **Product choice inside a chain matters more than chain choice.** Typical item minus cheapest equivalent item within the same chain: Spar 16.4k, Auchan 12.0k, Tesco 10.9k, Aldi 8.8k, Lidl 7.1k, Penny 4.7k per month (average ~10k). Caveat: the median item can be a premium or organic variant.
- Loyalty prices barely change the result (Auchan −184 Ft; others 0). DISCOUNTED flags are rare in GVH (3.5% of entries; Aldi 0%, Lidl 1%). INFERENCE: GVH probably does not carry most leaflet promotions for discounters. This matters because 71% of adults browse leaflets weekly.
- Identical products (same id) sold by ≥2 grocers: n=105; median max-vs-min spread **7.2%** (regular price 6.8%); 11% identical everywhere. Some extreme spreads (e.g. 50%+) may be data or unit errors. See `data/same_product_spreads.csv`.
- No single chain wins everywhere. On cheapest-item-incl.-promo: Lidl wins potatoes, onion, tomato, banana, bread, eggs, fish, flour; Aldi wins dairy, minced pork, lentils, sugar; Spar wins milk, chicken, pepper, apple, pasta (via promos); Tesco wins carrot and rice; Auchan wins pork leg and oil. Margin-capped staples have tiny spreads (flour 1.03×, oil 1.01×, sugar 1.09×, milk 1.11×); produce and bread have big ones (tomato 2.05×, bread 2.14×, carrot 2.04×, banana 1.98×).
- **Price uniformity**: priceSameEverywhere=false for 6.8% of entries in this sample, almost all Tesco (32% of Tesco entries; Spar 4%; Aldi, Lidl and Penny ~0%). INFERENCE: for discounters, "local prices" means "which chains are near me"; store-level price differences mainly matter for Tesco.

**Local reach in Budapest** (GVH /shops, `scripts/store_density.py`): 282 Budapest stores of the 6 grocers (Spar 114, Aldi 48, Lidl 46, Tesco 39, Penny 30, Auchan 5) plus 137 drugstores. GVH lists only stores where reporting applies, so small formats and CBA/Coop/Reál are missing. Using store locations as a proxy for where people live: median **3** distinct grocery chains within 1 km (64% have ≥3) and **5** within 2 km. On a uniform ~500 m grid over built-up Budapest: median 1 within 1 km and 4 within 2 km. COMPUTED.

**Saving from picking the cheapest chain among those within 1 km** (`scripts/local_gap.py`), staples basket per month: versus the average nearby chain, median **1.8k** (cheapest item) to **4.0k** (typical item); versus the priciest nearby chain, 4.0k to 7.8k. Within 2 km: 2.3–4.8k vs average and 5.0–10.3k vs priciest. COMPUTED.

**Scaling to the whole food budget (ESTIMATE).** The staples basket is roughly 25–40% of the ~118k Ft monthly food spend. Assume similar percentage gaps on the rest of the chain-bought basket (smaller for identical branded goods at a median ~7%), and that most Budapest households already use a discounter.
- Realistic store-choice saving for a typical household that follows advice: **~2,000–6,000 Ft/month (≈2–5% of food spend)**.
- Upper bound for a household that moves from typical items at Spar/Tesco/Auchan to a discounter: ~10–12k Ft/month.
- Product-swap advice (cheaper equivalent item) could add as much again, but 58% of shoppers say they already do this.
- Planning-driven waste reduction: cutting avoidable waste by 25–40% ≈ 0.9–2.8k Ft/month.
- Combined realistic headline: **~3–8k Ft/month (≈36–96k Ft/year)**. That is 2–5× the 1,490 Ft/month price point.

**Time and travel cost of visiting more stores (ESTIMATE).** Median net wage July 2026 was 437,900 Ft/month (≈2,517 Ft/hour); the average was 523,300 (≈3,007 Ft/hour). VERIFIED https://www.ksh.hu/gyorstajekoztatok/ker/ker2607.html. One extra 25-minute store stop per week ≈ 1.8 h/month ≈ **4,500 Ft/month of time** at the median wage. That is more than the 1.8–2.9k extra from multi-store cherry-picking on staples. For transit-pass holders (Budapest monthly pass 8,950 Ft, secondary) the extra trip costs no money. A 5 km car detour costs roughly 200–250 Ft in fuel (ESTIMATE). Conclusion: **choosing the best single nearby store pays; cherry-picking across stores mostly does not**, except for big-ticket items (meat, cheese, coffee, olive oil) and weekly promotions on the shopper's route.

---

## 5. Segments (evidence-weighted)

| Segment | Evidence | Fit |
|---|---|---|
| Couples / young professionals 25–44 | Highest online food purchase (20.1% / 19.2%), mobile internet 94–95% (Eurostat); Budapest households average 2.05 persons | **Core early adopters**: cook at home, time-poor, app-native, some WTP |
| Families with children | Only 17% of Budapest households have a child under 15 (census 2022); highest absolute food spend (2-adult + 2-child household 2020: 259,734 Ft per person per year × 4 ≈ 1.04 m Ft per year, roughly 150k Ft/month in 2026 prices, ESTIMATE); NIQ: discounters are the main store for 40% | High pain and spend, but a smaller share in Budapest than in the agglomeration (Pest county 28%). Strong for planning and waste |
| Single-person households | ~1/3 of households nationally; highest per-person food spend (528k Ft vs 357k average, 2020, jov0035); package-size waste ("pack too big" is a named NÉBIH cause) | Good fit for portioning and waste features; low basket value, so absolute savings are small |
| Students | Mobile internet 97%; tight budgets; student-discount app Diverzum has 782 HU ratings | Price-sensitive and easy to reach, very low WTP. Ad- or affiliate-funded |
| Seniors / pensioners | 65–74 mobile internet use only 64.7%; 16% of population offline, mostly 70+ (NMHH); prefer print leaflets (Shopfully) | Strongest price pain, weakest app fit |
| Health / fitness-motivated | Yazio 68k HU ratings; obesity 22% self-reported, 33% measured; low fruit and vegetable intake | Large and willing to pay for nutrition. The differentiator vs pure price apps (NomNom is budget-first; Árnéni and Cashmap are price-first) |

---

## 6. Open items and caveats
- KSH detailed COICOP household budget tables stop at 2020; the 2026 food spend is an ESTIMATE (cross-checked against KSH retail sales and a Nézőpont survey; all three land at 115–145k Ft/month per household).
- No public data on trips or stores per week, GVH Árfigyelő usage after 2023, or the share of Hungarians paying for apps.
- The GVH basket uses today's snapshot (one day). Promotions for discounters seem largely missing, so time-series savings from timing deals are not captured.
- Some "same product" spreads look like data errors; the median is robust, the tails are not.
- NomNom traction (703 ratings in ~11 weeks) is from iOS only. Android presence is unknown.
