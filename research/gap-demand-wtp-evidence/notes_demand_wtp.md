# Gap stream: demand and willingness-to-pay evidence, and a fake-door test (Budapest)

Stream key: `gap-demand-wtp-evidence`. Date of all pulls: **2026-10-12**, 22:03–22:30 CEST.
Labels: **VERIFIED** (primary source, URL given), **COMPUTED** (from data pulled here; method given), **ESTIMATE** (my reasoning).
WebSearch budget ran out partway through (the harness limit). After that I used only direct fetches of known primary URLs. Anything that needed a search engine is listed under gaps.

## 0. Bottom line

1. **NomNom's traction is real, not overstated.** On 2026-10-12, NomNom is **#1 Top Grossing** and **#8 Top Free** in Food & Drink on the HU iPhone App Store (VERIFIED, Apple RSS genre 6023). The gap between its 9 written reviews and its 703 ratings is the normal pattern for apps that prompt users for star ratings; it does not show inflated traction (section 1.3).
   - **Correction:** the 9 written reviews average **3.0**, not 3.1 (COMPUTED: 5,5,5,5,3,1,1,1,1).
2. **The HU Food & Drink grossing chart is thin.** An app with **0** HU ratings (Mynu) ranks #8 and a UK-focused planner with 20 ratings (mise) ranks #4. Being #1 is therefore consistent with modest absolute revenue; its size is unknown (ESTIMATE).
3. **There is demand evidence for the health-first wedge, but it is indirect:**
   - Hungarians think in **five meal slots** (reggeli–tízórai–ebéd–uzsonna–vacsora): 12 of 500 Yazio HU written reviews ask for this (COMPUTED). NomNom is still **dinner-only, 36 dinners** (VERIFIED nomnomplanner.com/hu).
   - There is a strong **anti-AI-recipe sentiment**: NomNom 2/9, Eatr 2/22 and Yazio about 18/500 (COMPUTED).
   - **Repetition** churns paying users: NomNom, Eatr, Yazio.
   - Requests for **multi-week planning** exist but are few (Nosalty 2019; the Meal Plan & Weekly Menu app, twice).
   - HU users already pay for health-led planning: Eatr #9 grossing F&D; Myreset at 9,990 Ft/month is #57 grossing H&F; Yazio #1 grossing H&F (VERIFIED charts).
   - **However**, I found no review evidence that users want health-first planning *combined with local store prices*. That combination is still untested.
4. **WTP ceiling for price-only tools is low:** Cashmap's 1,290–1,690 Ft/month paywall drew about 20 of its 101 written reviews pushing back. Stated anchors were "300–400 Ft", "499 Ft", "a few hundred Ft" and one-time or lifetime fees (COMPUTED from reviews).
   - Free options are entrenched: Kalóriabázis is praised for being free and has 500K+ Android downloads, and Street Kitchen, Nosalty and Mindmegette all publish free "heti menü" pages (VERIFIED).
   - The 990 Ft arm sits near NomNom's annual-plan monthly equivalent of 666 Ft (COMPUTED).
5. **Non-subscription revenue is negligible at early scale.** The Kifli affiliate pays €5 per new or lapsed customer with a 3-day cookie (VERIFIED). Wolt/TradeDoubler rates are not public. No HU retailer shoppable-recipe programme was found. My estimate is under ~100k Ft/month below ~10k MAU, so it cannot rescue weak WTP.
6. **The cheapest decisive test is a fake door: about 1,800 Budapest landing-page visitors, costing about 110–360k Ft in Meta spend (ESTIMATE),** run before any engineering. The protocol and pre-set thresholds are in section 5.

---

## 1. App Store HU written reviews: what users ask for and complain about

### 1.1 Method (COMPUTED)
- App ids came from the iTunes Search API with `country=hu` (raw files: `raw_lookup/search_*.json`, `search2_*.json`).
- Reviews came from `https://itunes.apple.com/hu/rss/customerreviews/page=N/id=<id>/sortby=mostrecent/json`, pages 1–10, about 1 request per 1.2 s, with the UA `market-research-bot/0.1`. Fetching stopped when a page returned fewer than 50 entries. Script: `scripts/fetch_reviews.py`; log: `raw_reviews/_fetch_log.tsv`.
- **2,064 HU written reviews from 22 apps** are in `reviews_hu_appstore_2026-10-12.csv`. Keyword-tagged copy: `reviews_coded_2026-10-12.csv` (script `scripts/code_reviews.py`; Hungarian and English stems).
- The core planner apps were coded by hand in `manual_codes_core_apps.csv`. Keyword tags are approximate (false positives exist), so every count cited below was checked by reading the review.
- The feed returns at most 500 reviews (Yazio and Kifli are capped). Some feeds stop early (Tesco Online stopped at 100).

App ids (VERIFIED iTunes Search/Lookup, hu):

| App | id |
|---|---|
| NomNom | 6788049718 |
| Lefőzlek | 6763793215 |
| Cashmap | 6463898604 |
| Yazio | 946099227 |
| Nosalty | 1397911524 |
| Kifli | 1521445846 |
| Listonic | 331302745 |
| Bring! | 580669177 |
| Mealime | 1079999103 |
| Samsung Food | 1133637674 |

Extra apps pulled:

| App | id |
|---|---|
| Eatr | 6479693198 |
| Street Kitchen | 6751809018 |
| Kalóriabázis | 1498199527 |
| Tesco Online HU | 844568009 |
| MyFitnessPal | 341232718 |
| Munch | 1528038390 |
| WFit | 1531084417 |
| Myreset | 6759920267 |
| EcoFeast | 6759725198 |
| mise | 6777471316 |
| Meal Plan & Weekly Menu | 6460821436 |
| Akcióvadász | 1668798567 |
| Ajanlatok.hu | 6469340340 |
| Kimbino | 6444317791 |

### 1.2 Written vs aggregate rating (COMPUTED; `written_vs_aggregate_2026-10-12.csv`)
Aggregate figures are from iTunes Lookup, hu, 22:06 CEST (`raw_lookup/lookup_all_20261012T2206.json`).

| App | written n | written avg | aggregate avg (n) | gap | written/total | 1★ share of written |
|---|---|---|---|---|---|---|
| **NomNom** | 9 | **3.00** | 4.82 (703) | 1.82 | 1.3% | 44% |
| Lefőzlek | 0 | – | 5.0 (1) | – | – | – |
| Eatr (health AI meal plan) | 22 | **1.27** | 4.66 (1,728) | 3.39 | 1.3% | 86% |
| Yazio | 500 (cap) | 2.56 | 4.82 (68,170) | 2.25 | ≤0.7% | 37% |
| Street Kitchen | 34 | 2.00 | 4.75 (456) | 2.75 | 7.5% | 50% |
| Tesco Online HU | 100 | 2.87 | 4.51 (2,072) | 1.64 | 4.8% | 40% |
| Munch | 162 | 2.98 | 4.13 (686) | 1.16 | 23.6% | 28% |
| Nosalty | 89 | 3.91 | 4.69 (510) | 0.78 | 17.5% | 11% |
| Kalóriabázis | 113 | 3.58 | 4.33 (486) | 0.76 | 23.3% | 12% |
| MyFitnessPal | 192 | 4.09 | 4.72 (3,411) | 0.63 | 5.6% | 11% |
| Listonic | 172 | 4.35 | 4.80 (3,954) | 0.45 | 4.4% | 8% |
| Bring! | 43 | 4.63 | 4.85 (1,404) | 0.22 | 3.1% | 2% |
| Cashmap | 101 | 4.41 | 4.36 (137) | −0.05 | **73.7%** | 10% |
| Kifli | 500 (cap) | 4.96 | 4.96 (18,959) | 0.00 | ≤2.6% | 0.2% |
| Mealime | 3 | 3.67 | 4.60 (25) | 0.93 | 12% | 0% |
| Samsung Food | 1 | 5.0 | 4.92 (13) | – | – | – |

### 1.3 How to read the gap (ESTIMATE/INFERENCE)
- Large gaps of 1.6–3.4 together with a written share of about 1–8% are typical of subscription apps that prompt for stars in-app (Yazio, Eatr, NomNom, Street Kitchen). Prompted users leave stars; motivated users, often angry about billing, ads or bugs, write text.
- NomNom's written share (1.3%) is the same as Eatr's (1.3%). Its gap is **smaller** than Yazio's or Eatr's. So the gap does not single NomNom out as inflated.
- Cashmap is the opposite anomaly: 74% of raters wrote text, and **82 of its 101 written reviews fall after 2024-10-01 at an average of 4.78**, clustered on single days. There were 13 five-star reviews on 2024-10-23, 12 on 2024-11-25 and 8 on 2024-11-26 (COMPUTED). The 12 reviews from 2024-03-20 to 2024-09-30, right after the paywall, average 1.83.
  - INFERENCE: this pattern is consistent with a solicited-review campaign. Discount Cashmap's positive reviews.

### 1.4 Jobs and pains: counts verified by reading

| Tag | NomNom (9) | Eatr (22) | Yazio (500) | Others |
|---|---|---|---|---|
| Breakfast/lunch, meal slots | **1** ("give me breakfast") | **1** (roast pork planned for breakfast) | **12** ask for tízórai/uzsonna or 5+ meal slots | Mealime 1/3 (wants a breakfast/lunch/snack/dinner generator with a calorie target); Meal Plan & Weekly Menu 1/3 |
| Health goals | 0 | 4 (macro or calorie targets not met; disliked foods ignored) | dominant topic (weight-loss stories) | Kalóriabázis and MFP: weight-loss stories |
| AI-written recipes (negative) | **2** ("AI slop"; recipes written by AI and unclear) | **2** | **~18** (forced or inaccurate AI) | – |
| Repetition | **1** (same ~10 dishes) | **1** (same 15) | **3** paid users (same recipes for years) | – |
| Price accuracy | 0 | 0 | 0 | Cashmap 1–2 (stale promo prices: user went to the store for nothing); Tesco Online stock-outs |
| Store choice | 0 | 0 | 0 | Cashmap many (compare chains, calculator); Akcióvadász asks for more stores; Bring! 2017 asks for per-store lists |
| Family / household | 0 | 0 | 2 (recipe sharing with spouse) | Listonic and Bring!: shared family lists are the main praise; Kalóriabázis (Play) asks for household sharing |
| Multi-week planning | 0 | 0 | 1 (copy meals a week ahead) | Nosalty 2019 asks for a weekly/monthly menu planner; Meal Plan & Weekly Menu 2/3 (multi-week should be free; plan next week) |
| Meal prep | 0 | 1 | 2 | – |
| Paywall / billing | **1** ("pity it's paid") | **10** (trial or charge anger) | many (aggressive Pro upsell) | Cashmap ~20; Listonic (would rather keep ads than pay monthly); Street Kitchen 2/34 would pay to remove ads |
| Waste | 0 | 0 | 0 | EcoFeast 1 (throws away less); Munch is a waste app (#6 Top Free F&D) |

**What this supports (INFERENCE):**
- A Hungarian planner that covers **breakfast, tízórai, ebéd, uzsonna and vacsora** with **human-tested recipes**, plus **variety guarantees** and **meal prep**, addresses the observed pains in NomNom, Eatr and Yazio.
- The evidence base is small: about 20 relevant reviews across apps. It shows *pain*, not *willingness to pay* for the fix.
- I found no review asking for health planning plus local or nearby store prices together.

## 2. Charts and rating counts (VERIFIED feeds, 2026-10-12)
- Source feeds: `https://itunes.apple.com/hu/rss/{topfreeapplications|toppaidapplications|topgrossingapplications}/limit=200/genre={6023 Food & Drink|6013 Health & Fitness}/json`, updated 2026-10-12T13:10 PT. Each returns 100 entries.
- Also used: `https://rss.marketingtools.apple.com/api/v2/hu/apps/top-free/100/apps.json` (the old applemarketingtools domain 301-redirects here).
- The **top-paid overall feed returned 502/504** twice and could not be read.
- CSV: `appstore_hu_charts_2026-10-12.csv`; script `scripts/charts_csv.py`.

**Food & Drink, HU iPhone (VERIFIED):**
- **Top Grossing:**

  | Rank | App |
  |---|---|
  | **#1** | **NomNom** |
  | #2 | Gronda |
  | #3 | Cookpad |
  | #4 | mise (UK, 20 HU ratings) |
  | #5 | Herbi (1 rating) |
  | #6 | Pam |
  | #7 | ReciMe |
  | #8 | Mynu (0 ratings) |
  | **#9** | **Eatr** |
  | #20 | Cashmap |
  | #22 | Disha: Budget Meal Planner (0 HU ratings) |
  | #45 | Samsung Food |
  | #51 | Meal Plan & Weekly Menu |
  | #81 | Mealime |

  Lefőzlek is not in the top 100.
- **Top Free:**

  | Rank | App |
  |---|---|
  | 1 | foodora |
  | 2 | McDonald's |
  | 3 | Wolt |
  | 4 | Burger King |
  | 5 | KFC |
  | **6** | **Munch** |
  | **7** | **Kifli** |
  | **8** | **NomNom** |
  | 11 | Street Kitchen |
  | 15 | Tesco Online |
  | 27 | Disha |
  | 28 | Cookpad |
  | 39 | mise |
  | 48 | Eatr |
  | 50 | Nosalty |
  | 74 | Meal Plan & Weekly Menu |

- Top Paid F&D: none of the watched apps.

**Health & Fitness, HU iPhone (VERIFIED):**
- **Top Grossing:** #1 **Yazio**, #3 Foodvisor, #22 MyFitnessPal, **#57 Myreset** (HU, 9,990 Ft/month).
- **Top Free:** #3 Yazio, #7 Foodvisor, **#13 Kalóriabázis**, #65 MFP, #78 Myreset.

**Overall Top Free (all categories) HU:** Munch #72, Kifli #80, Yazio #94. NomNom is not in the overall top 100.

**Rating counts, iTunes Lookup hu, 2026-10-12 22:06 (VERIFIED):**

| App | Ratings |
|---|---|
| Yazio | 68,170 |
| Kifli | 18,959 |
| Cookpad | 5,837 |
| Foodvisor | 5,552 |
| Auchan Online | 4,476 |
| Listonic | 3,954 |
| MFP | 3,411 |
| Tesco Online | 2,072 |
| **Eatr** | **1,728** |
| Bring! | 1,404 |
| **NomNom** | **703** |
| Munch | 686 |
| Nosalty | 510 |
| Kalóriabázis | 486 |
| Street Kitchen | 456 |
| Cashmap | 137 |
| Meal Plan & Weekly Menu | 61 |
| Mealime | 25 |
| mise | 20 |
| WFit | 18 |
| Samsung Food | 13 |
| EcoFeast | 8 |
| Myreset | 7 |
| Lefőzlek | 1 |

**NomNom velocity:**
- ratingCount is still **703** at 22:06 on 2026-10-12. The App Store web page JSON-LD also shows 703 (VERIFIED).
- No time has passed since the brief's figure, so velocity cannot be updated today. There are no Wayback snapshots (CDX returned empty).
- Average since release: 703 ratings / 81 days (2026-07-23 → 2026-10-12) = **8.7 ratings/day** (COMPUTED).
- Re-run `curl "https://itunes.apple.com/lookup?id=6788049718&country=hu"` in 7 days to measure current velocity.

**What the charts mean (ESTIMATE):**
- #1 grossing in HU F&D shows that NomNom has the most paying iOS users in this niche category.
- Because zero-rating apps rank in the top 10, the absolute revenue behind #1 could be small, plausibly tens of paying conversions per week rather than thousands. This is a guess, with no verified revenue source.
- **HU iOS users do pay for meal planners**, health-led (Eatr) and budget-led (NomNom, Disha) alike. Health tracking (Yazio, Kalóriabázis) is a far larger base than recipes or planning.

## 3. Google Play listings, HU (VERIFIED; `raw_play/_play_summary.json`)
Fetched with `hl=hu&gl=HU`. Download bands are global, and the review counts shown are Play's totals.

| App | Downloads | Rating (reviews) | Notes |
|---|---|---|---|
| NomNom (com.nomnomplanner) | **1 E+** | no rating shown | iOS-led; Android came later |
| Lefőzlek | not found on Play | – | – |
| Cashmap (hu.kiwisoft.cashmap) | 5 E+ | 4.5 (278) | Visible snippets: "would pay but not 1,300 Ft/month — almost half a Netflix"; "price a bit high" |
| Yazio | 50 M+ | 4.6 (870 E) | Snippets: recipe creation broken even for Pro |
| Kalóriabázis (hu.kaloriabazis.kaloriabazis) | **500 E+** | 4.8 (6.06 E) | HU-only nutrition app. A snippet from a subscriber of 2+ years; household-sharing request |
| Nosalty | 100 E+ | 3.9 (2.18 E) | Recipe saving broken; one user says fix it "or make the app paid" |
| Kifli | 100 E+ | 4.9 (18.2 E) | Delivery praise |
| Listonic (com.l) | 10 M+ | 4.8 (318 E) | Family shared list |
| Bring! | 10 M+ | 4.6 (144 E) | – |
| Mealime | 1 M+ | 4.7 (26.8 E) | Global |
| Samsung Food (com.foodient.whisk) | 1 M+ | 4.6 (23 E) | – |
| Eatr (com.eatr.eatr) | 1 M+ | 4.4 (57 E) | HU snippets: weekly-plan quantities and shopping list are "chaos"; trial billing complaint |
| Street Kitchen (hu.streetkitchen.app) | 10 E+ | 4.8 (356) | Ads complaints |
| Disha (com.dishaapp.app) | 10 E+ | – | German-market budget planner |

## 4. Prices observed (WTP anchors) and non-subscription revenue

### 4.1 HU App Store in-app purchase prices (VERIFIED, apps.apple.com/hu/app/id…; `raw_web/_appstore_pages_summary.json`)

| App | Prices |
|---|---|
| **NomNom** | Plus **7,990 Ft**/yr; Monthly **1,490 Ft** (listed first: Plus) |
| **Lefőzlek Plusz** | **9,990 Ft/yr; 999 Ft/month** |
| **Cashmap** | Prémium 1 hónap **1,690 Ft** (the ÁSZF of 2024-03-20 listed 1,290/1,999/2,999 per competitors stream) |
| Yazio PRO | 3,390–21,990 Ft (12 months at 8,500 / 15,000 / 21,990; several promotional SKUs) |
| Eatr | yearly 6,990–34,999 Ft; quarterly 9,990 |
| mise | monthly 4,490; yearly 8,990–22,990 |
| Samsung Food | 2,990/month; 24,990/yr |
| Meal Plan & Weekly Menu | "Advanced Meal Planning" 4,490 |
| **Myreset** (HU) | **9,990/month; 99,000/yr** |
| Listonic | 399–999/month; 2,690–4,990/yr; lifetime 3,990–5,990 |
| Bring! | 699/month; 3,990/yr |
| MyFitnessPal | 2,690–7,790/month; 13,790–30,990/yr |

- Kalóriabázis premium is a donation-style membership: one-off ("Alkalmi") 2,999 / 5,999 / 14,999 Ft or recurring 2,999 / 9,999 / 19,999 Ft. It states that ad revenue does not cover costs and that the full feature set stays free (VERIFIED https://kaloriabazis.hu/premium_info). Its diary UI also shows a Ft cost per food and a store list (Coop, Aldi, Spar, Interspar, Lidl, Tesco, Metro, CBA Prima) (VERIFIED homepage HTML). It is a nutrition-plus-cost precedent, but user-maintained.
- **Net revenue per payer:** after 27% VAT and Apple's 15% small-business rate (COMPUTED):

  | Price | Net to developer |
  |---|---|
  | 990 Ft | **663 Ft/month** |
  | 1,490 Ft | **997 Ft/month** |
  | 1,990 Ft | **1,332 Ft/month** |
  | NomNom annual 7,990 Ft | **5,348 Ft/yr** (≈446/month) |

### 4.2 Non-subscription revenue lines
- **Kifli via VIVnetworks** (VERIFIED https://www.vivnetworks.com/hu/affiliate-katalog/kifli-hu/):
  - **€5** per new customer's first order, or per customer lapsed more than 60 days; **nothing for existing customers**; **3-day cookie**.
  - Brand-keyword SEM and SEO are not allowed. Coupon and cashback sites are allowed. Apps are not mentioned. No date is shown (© 2026).
  - Sizing (ESTIMATE): at 5,000 Budapest MAU, 4% tap a "rendeld meg a Kiflin" hand-off per month (200 taps), and 5–10% of those are new or lapsed customers who order within 3 days. That gives 10–20 commissions = **€50–100 ≈ 18–37k Ft/month**. At 50k MAU, ≈180–370k Ft/month.
  - Kifli's large existing base (18,959 iOS ratings; 100 E+ Android) means many affluent Budapest users are already customers and do not count.
- **Wolt via TradeDoubler** (VERIFIED https://explore.wolt.com/en/hun/affiliates): the programme exists. **Commission, cookie window and SPAR eligibility are not public** (they sit in the TradeDoubler portal). Not sizable from public pages.
- **Retail media / shoppable recipes:**
  - **Rohlik Ads** exists (https://ads.rohlik.group/ — title only: "Connect Your Brand with Affluent Urban Audiences"; no formats or prices public) (VERIFIED existence).
  - **Unlimitail**'s homepage does not mention Hungary or Auchan HU (VERIFIED absence).
  - The Tesco (tesco.hu/receptek) and SPAR (spar.hu/receptek) recipe URLs returned **403** to my bot; I did not try to get around this. Lidl /receptek and Auchan /receptek returned 404.
  - **Penny** has 546 recipes with **no product, price or list links and no visible sponsors** (VERIFIED https://www.penny.hu/receptek).
  - Kifli Séf has a "Chef inspiráció erre a hétre" block and healthy and reflux-friendly categories (VERIFIED https://www.kifli.hu/sef). The recipes-nutrition stream already verified per-portion price and add-all-to-cart there.
  - **Street Kitchen** monetises with display ads and brand sponsorship: a sponsor block with a Fanta logo file (INFERENCE from the filename), a "Coke & meals" section, and Kenwood/Braun partner articles (VERIFIED https://streetkitchen.hu/).
  - App reviewers report in-app **foodora** shopping pop-ups on Street Kitchen recipes (VERIFIED as user reports, App Store 2026-05-14 and 2026-08-26).
  - I found no public rate card for HU shoppable recipes. dunnhumby / Tesco Media HU could not be checked because the search budget ran out.
- **Verdict (ESTIMATE):** below about 50k MAU, affiliate plus sponsorship is likely to be **under ~100–400k Ft/month**. It is a supplement, not a business model, so the consumer subscription WTP remains the riskiest assumption.

## 5. Fake-door protocol, Budapest (cheapest real test; run before engineering)

### 5.1 Hypotheses (pre-registered)
- **H1 (demand):** at least 5% of Budapest landing-page visitors give an email for a health-first, multi-week planner when the price is shown.
- **H2 (wedge):** the health-first multi-week proposition converts no worse than the "cheapest nearby store" proposition (at most 1 pp lower).
- **H3 (price):** sign-up at 1,490 Ft is at least 66% of sign-up at 990 Ft (the revenue break-even ratio 990/1,490 = 0.664; COMPUTED). For 1,990 vs 990 the ratio is 0.497.
- **H4 (scope):** at least 40% of sign-ups want breakfast and/or lunch planned, and at least 25% want two or more weeks planned ahead (ESTIMATE thresholds).

### 5.2 Design
- **Three value propositions**, each an ad set with 2–3 creatives that link to a matching landing-page variant:
  - **A. Health-first, multi-week:** "Kiegyensúlyozott heti menü az egész hónapra – reggeli, ebéd, vacsora, kipróbált magyar receptekkel, bevásárlólistával."
  - **B. Cheapest nearby store:** "A heti menüd hozzávalói a hozzád közeli boltok közül ott, ahol a legolcsóbb (GVH Árfigyelő-adatok alapján)."
  - **C. Less waste:** "Kevesebb kidobott étel: a menü beosztja a maradékokat és a félbehagyott csomagokat."
- **Three price arms** (990 / 1,490 / 1,990 Ft per month): randomised per visitor (first-party random assignment stored in the page), shown above the fold and on the CTA ("Kipróbálom – 1 490 Ft/hó, 7 nap ingyen").
  - Cells: 3 × 3 = 9.
  - Show the annual equivalent in small print for all arms (for example "vagy 7 990 Ft/év"), to mirror NomNom.
- **Funnel:** ad → LP view → CTA click → email form (consent checkbox) → thank-you page that says plainly the app is in development ("Fejlesztés alatt – elsőként szólunk") → one optional 3-question survey (which meals; how many weeks ahead; current tool: NomNom / Yazio / receptoldal / none) → an optional "Lefoglalom az indulási árat" button (intent click; **no payment taken**).
- **Targeting:** Meta (Facebook and Instagram), Budapest plus about 15 km, age 25–49, Hungarian language, broad interests (cooking, healthy eating). Placement: Advantage+. Optimisation: landing-page views.
  - An optional Google Search ad group (about 30–50k Ft) on "heti menü", "egészséges heti menü", "olcsó heti menü", "menütervező" checks search intent.
- **Measurement:** use cookieless analytics (for example Plausible) or server logs for LP views and sign-ups. If a Meta pixel is used, it needs prior consent under Eht. 155(4) (see legal stream). The primary denominator is unique LP views, not ad clicks.
- **Compliance (from legal and recipes-nutrition streams):**
  - No "legolcsóbb" claim without scope and date.
  - No nutrition or health claims ("egészséges" needs care under Reg. 1924/2006; prefer "kiegyensúlyozott, zöldségben gazdag").
  - GDPR-compliant consent and privacy notice.
  - Delete emails if the project stops.
  - No payment collection in this stage.
- **I did not post, register, submit forms or run ads.** The founder runs them.

### 5.3 Sample sizes (COMPUTED; `scripts/gap_and_power.py`)
- **Precision, 95% CI ±m:**

  | Rate | Margin | n |
  |---|---|---|
  | p = 2% | ±1 pp | **753** |
  | p = 3% | ±1 pp | **1,118** |
  | p = 5% | ±1.5 pp | **811** |
  | p = 5% | ±1 pp | 1,825 |

- **One arm against a 2% floor** (one-sided α = 0.05, power 0.8): to detect 5% needs **191** visitors; 4% needs 391.
- **Two arms** (α = 0.05 two-sided, power 0.8):

  | Comparison | Visitors per arm |
  |---|---|
  | 2% vs 5% | **588** |
  | 3% vs 6% | 749 |
  | 3% vs 5% | 1,506 |
  | 2% vs 4% | 1,141 |
  | 20% vs 30% (intent click among sign-ups) | 294 |

- **Plan:** **600 LP visitors per value proposition (1,800 total)**, which gives 600 per price arm and about 200 per cell.
  - This detects VP gaps of about 2 vs 5% or 3 vs 6%.
  - It tells "≥5%" apart from "≤2%" for each VP. Example Wilson 95% CIs: 30/600 = [3.5%, 7.0%]; 12/600 = [1.1%, 3.5%].
  - It cannot resolve 3 vs 5% between price arms; that would need about 1,500 per arm. If H3 is borderline, run a Stage 1b of +1,800 visitors on the winning VP only.

### 5.4 Budget (ESTIMATE, anchored on VERIFIED benchmarks)
- **Meta HU benchmarks** (VERIFIED, Superads, median of campaign medians, all industries, nationwide, roughly USD; months available Nov 2025 – May 2026; sparse; March 2026 is an outlier; sample size not disclosed):
  - CPM **$1.62 ≈ 529 Ft**; CPC **$0.138 ≈ 45 Ft**; CTR **1.6%**; cost per app install $0.94 (one month only); cost per lead $58 (noisy).
  - Sources: https://www.superads.ai/facebook-ads-costs/cpm/hungary , /cpc/hungary , /ctr/hungary , /cost-per-lead/hungary , /cost-per-app-install/hungary.
  - Neighbours: Czechia CPM $7.10 / CPC $0.16; Poland CPM $9.24 / CPC $0.64.
  - FX: ECB 2026-10-12 cross rate, 326.56 Ft/USD (EUR 365.13 Ft; USD 1.1181).
- **Assumption (ESTIMATE):** Budapest-only targeting, a new ad account, a small budget and a cold audience cost 1.5–4× the national median, and 70–90% of link clicks become LP views. That gives **60–200 Ft per LP visitor**.
- **Stage 1 (1,800 visitors):** **108k–360k Ft** of media (COMPUTED from the range).
  - Plus Google intent test ~30–50k Ft (ESTIMATE; **no verified HU Google Ads CPC found**, and Keyword Planner needs a login).
  - Plus tooling ~10–20k Ft (ESTIMATE).
  - **Total about 150–430k Ft (≈ €410–1,180), about 2 weeks** (3 days to build, 10–14 days of ads at roughly 10–30k Ft/day).
- **Stage 1b, if needed:** +108–360k Ft.

### 5.5 Pre-set go/no-go thresholds (decide before launch; do not move them)
The primary metric is email sign-ups / unique LP views, per VP (pooled over price) and per cell.
- **GO to Stage 2 (concierge MVP, not an app):** all of the following must hold.
  - VP A sign-up ≥ 5% pooled, with Wilson lower bound ≥ 3%.
  - VP A at 1,490 Ft ≥ 4%.
  - VP A is at most 1 pp below VP B.
  - H4 holds.
  - At least 25% of sign-ups click "Lefoglalom".
- **ITERATE (one copy/creative re-test, ≤ 150k Ft):** the best VP is between 2% and 5%, or VP A trails VP B by 1–2.5 pp.
- **NO-GO for a consumer subscription app:** any one of the following.
  - Every VP is under 2% at 990 Ft.
  - VP A is under half of VP B. The wedge fails: demand is price-led, which is NomNom, Árnéni and Cashmap territory. Consider B2B or data/affiliate instead.
  - The 1,490 arm is under 50% of the 990 arm. WTP is below NomNom's price.
- **Price choice:** pick the arm with the highest price × sign-up rate, provided its lower bound stays ≥ 2%.
- **Stage 2 (only after GO):**
  - 2–3 weeks of concierge plans (PDF/email, hand-built from GVH prices) for 30–50 sign-ups.
  - Then a **real pre-sale** to the waitlist: first month at the chosen price through a payment link, refundable, run by the founder.
  - **Build only if** at least 8–10% of the waitlist pays within 14 days and at least 60% of concierge users open plans in week 2.
  - Basis (VERIFIED via market-user stream, RevenueCat SOSA 2026): freemium D35 median 2.1%; hard paywall 10.7%; H&F 2.9%.

## 6. Corrections to the brief
- NomNom written-review average: **3.0, not 3.1** (9 reviews: four 5★, one 3★, four 1★) (COMPUTED).
- "NomNom's traction may be overstated" is **not supported**:
  - The written-vs-aggregate gap is structural across prompted-rating apps.
  - NomNom is #1 Top Grossing and #8 Top Free in HU F&D (VERIFIED).
  - What *is* uncertain is the absolute revenue behind those ranks (ESTIMATE: possibly small).
- NomNom is still dinner-only with 36 dinners, one week per plan, macros and "fehérjedús" / "alacsony kalóriás" filters, and no location features (VERIFIED nomnomplanner.com/hu, 2026-10-12). Health filters already exist, so "health-first" must mean full-day nutrition and variety, not macro display.

## 7. Gaps and open items
- WebSearch quota was exhausted. I did not find:
  - HU Google Ads CPC benchmarks;
  - dunnhumby / Tesco Media HU, SPAR or Auchan retail-media programmes;
  - Wolt/TradeDoubler commission terms;
  - any HU survey on app subscription willingness to pay.
- NomNom's revenue, installs, trial conversion and churn are unknown. Re-check its ratingCount in 7 days, and track the HU F&D grossing rank daily for 2 weeks (`scripts/charts_csv.py`).
- The review evidence is small-n and self-selected. Treat it as hypothesis-generating; the fake door is the actual test.

## 8. Files
- `reviews_hu_appstore_2026-10-12.csv` (raw written reviews, 2,064 rows); `reviews_coded_2026-10-12.csv` (keyword tags); `manual_codes_core_apps.csv` (hand codes with paraphrases)
- `written_vs_aggregate_2026-10-12.csv`; `review_tag_summary_raw.json`
- `appstore_hu_charts_2026-10-12.csv`
- `raw_reviews/`, `raw_lookup/`, `raw_charts/`, `raw_play/`, `raw_web/` (untrusted downloads); `scripts/` (fetch_reviews.py, parse_reviews.py, code_reviews.py, appstore_pages.py, charts.py, charts_csv.py, play_pages.py, gap_and_power.py)

## Sources
- Apple review RSS: https://itunes.apple.com/hu/rss/customerreviews/page=1/id=6788049718/sortby=mostrecent/json (and the ids listed in 1.1)
- iTunes Lookup: https://itunes.apple.com/lookup?id=6788049718&country=hu
- Charts: https://itunes.apple.com/hu/rss/topgrossingapplications/limit=200/genre=6023/json ; …/topfreeapplications/…/genre=6023 ; …/genre=6013 ; https://rss.marketingtools.apple.com/api/v2/hu/apps/top-free/100/apps.json
- App Store pages: https://apps.apple.com/hu/app/id6788049718 , id6763793215, id6463898604, id946099227, id6479693198, id6759920267, id331302745, id580669177, id1133637674, id6777471316, id6460821436, id341232718, id1064020872
- Google Play: https://play.google.com/store/apps/details?id=com.nomnomplanner&hl=hu&gl=HU (and the packages in section 3)
- NomNom site: https://nomnomplanner.com/hu/
- Kifli affiliate: https://www.vivnetworks.com/hu/affiliate-katalog/kifli-hu/
- Wolt affiliate: https://explore.wolt.com/en/hun/affiliates
- Rohlik Ads: https://ads.rohlik.group/ ; Unlimitail: https://www.unlimitail.com/
- Penny receptek: https://www.penny.hu/receptek ; Kifli Séf: https://www.kifli.hu/sef ; Street Kitchen: https://streetkitchen.hu/ (heti menü: /kategoriak/heti-menu) ; Nosalty /cikkek/heti-menu ; Mindmegette /heti-menu
- Kalóriabázis: https://kaloriabazis.hu/premium_info
- Meta benchmarks: https://www.superads.ai/facebook-ads-costs/cpm/hungary (and cpc, ctr, cost-per-lead, cost-per-app-install; czech-republic and poland for comparison)
- FX: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml
