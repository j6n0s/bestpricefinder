# Stream: Recipe content and nutrition data sources (recipes-nutrition)

Research date: 2026-10-12. Researcher: subagent (recipes-nutrition stream).
Labels: **VERIFIED** = read in a primary or named source this session (URL given). **COMPUTED** = derived from data pulled this session (method given). **ESTIMATE** = my reasoning, not verified.
Note: nothing here is legal advice. The legal conclusions are a researcher's reading and should be checked by a Hungarian IP/food-law lawyer before launch.

Data files in this folder:
- `data/off_sample_results.csv` / `.json`: 60 GVH barcodes checked against Open Food Facts (OFF)
- `data/gvh_ean_share_by_chain.txt`: share of GVH product ids that are valid EAN-13 codes, by chain and top category
- `data/gvh_leaf_categories.tsv`: 161 GVH leaf categories with their top category
- `dl_*`: raw downloads (untrusted data); `scripts/`: the scripts used

---

## 0. Corrections to the brief

1. **OKOSTÁNYÉR® is made by MDOSZ, not NNGYK.** It is published by the Magyar Dietetikusok Országos Szövetsége (Hungarian Dietetic Association). The 2021 renewal "az MTA Élelmiszertudományi Tudományos Bizottság, a Magyar Táplálkozástudományi Társaság és az Országos Gyógyszerészeti és Élelmezés-egészségügyi Intézet ajánlásával jelent meg". OGYÉI is the predecessor of NNGYK, so NNGYK's role is endorsement only. VERIFIED: https://www.okostanyer.hu/2023/09/18/megujult-a-felnotteknek-szolo-okostanyer/ and https://okostanyer.hu/ ("A Magyar Dietetikusok Országos Szövetsége (MDOSZ) elkészítette a legújabb magyar táplálkozási ajánlást…"). The English PDF says "Made by the Hungarian Dietetic Association (MDOSZ)…".
2. **"Index Konyha" does not exist as a separate brand** (index.hu/konyha and index.hu/gasztro return 404). Index's homepage links its recipe content to **Sobors**, which belongs to the same group (Indamedia, IndaWorld Publishing Kft.). VERIFIED by curl, 2026-10-12.
3. **The OFF rate limit is stricter than our ≤1 req/s rule.** OFF's own API documentation says "15 req/min/IP address for all read product queries" and asks anyone fetching "more than a few hundred products" to use the CSV/JSONL dump. VERIFIED: https://openfoodfacts.github.io/openfoodfacts-server/api/. My 60-call sample ran at about 1 call per 1.2 s, roughly 50 per minute. No 429 errors came back, but future sampling should stay at 15 per minute or less, or use the dump.

---

## 1. Hungarian recipe sites: owner, size, API, reuse terms

| Site | Owner / operator | Size | Public API | Reuse terms (summary) | robots.txt / TDM signal |
|---|---|---|---|---|---|
| **Nosalty** (nosalty.hu) | **Central Médiacsoport Zrt.**, 1037 Bp. Montevideo u. 9., Cg. 01-10-048280 (VERIFIED: https://www.nosalty.hu/impresszum) | Claims "több mint 63 000 ellenőrzött … recept" (VERIFIED, self-reported: https://sales.centralmediacsoport.hu/termekportfolio/online/noi-eletmod/nosalty/). The sitemap lists **~72,300 recipe URLs** (COMPUTED: recipes-1…8 sitemaps, files 1–7 hold 10,000 each and file 8 holds 2,276). Media kit counters show 20.7M page views per month. The unique-user counter reads "23M", but the page text says it reaches more than 2.5 million people a month, so the counter is almost certainly 2.3M (Gemius 2025 Q1, self-reported). NMHH/Gemius Oct 2025 says Nosalty and Mindmegette would make the top 10 by monthly reach (VERIFIED: https://nmhh.hu/dokumentum/255735/az_online_mediater_kozonsege_2025_oktober.pdf). | None found. Recipe pages carry schema.org `Recipe` JSON-LD **including `nutrition`** (VERIFIED on one page; the units in it are buggy, e.g. calories given in "g"). | Terms VI: "A Szolgáltatás, valamint a Weboldalon elérhető tartalom szerzői jogi védelem alatt áll. A szerzői jogok összessége és az adatbázis előállítójának védelmét szolgáló jogok a Szolgáltatót illetik meg", and anything beyond reading, screen display, temporary copies and personal non-commercial saving or printing needs prior written permission. VI also bans any "rendszer vagy megoldás" (system or solution) used in a way the contract does not expressly allow (VERIFIED: https://www.nosalty.hu/felhasznalasi-feltetelek). Users grant Central and its group a free, irrevocable, **sublicensable** licence over the recipes they upload (IV), so Central can license its UGC to a partner. | robots allows /recept/ and disallows /kereses/, /receptkonyv/, /preview/ (VERIFIED). |
| **Mindmegette** (mindmegette.hu) | **Mediaworks Hungary Zrt.**, 1082 Bp. Üllői út 48., Cg. 01-10-047955 (VERIFIED: impresszum and terms PDF) | Recipe count not determined (the sitemaps are monthly and mixed with articles). Top-10 by monthly reach (NMHH Oct 2025, see above). | robots disallows `/publicapi` apart from the RSS feed. No public API. | Terms effective 2025-12-02 (https://mediaworks.hu/wp-content/uploads/2025/12/4682367Mindmegettefelhasznalasifeltetelek20251202.pdf), chapter VII. VII.3: users must use the content for private, non-commercial purposes only. VII.6: private copies only, and no reproduction, storing in a database, adaptation or commercial distribution. VII.8: another website may take a recipe only "a Szolgáltató előzetes írásbeli engedélyét követően", showing only the exact recipe name, no image, and a hyperlink. VII.9: such taking may never be "üzletszerűen". VII.11: Mediaworks claims the **press-publisher right**. VII.12: uploaded user content carries an **exclusive**, transferable, sublicensable licence to Mediaworks. (VERIFIED; I extracted the PDF text with my own parser, so spacing is degraded.) | — |
| **Street Kitchen** (streetkitchen.hu, plus a mobile app) | Operator: **Lunchbox Produkciós Kft.**, 1116 Bp. Fehérvári út 108–112. Publisher per impresszum: **SK Sales House Kft.** (VERIFIED: https://streetkitchen.hu/felhasznalasi-feltetelek-sk, https://streetkitchen.hu/impresszum) | **~9,700 recipe URLs** (COMPUTED: 10 recipe sitemaps, file 1 = 1,000 and file 10 = 728, assuming files 2–9 hold 1,000 each). | None found. | Terms effective 2026-04-30, §5: "A tartalmak kizárólag személyes célra használhatók fel. Kereskedelmi felhasználás csak a Szolgáltató előzetes írásbeli engedélyével lehetséges." §6 forbids "automatizált adatgyűjtésre (pl. scraping, botok)". (VERIFIED) | robots: Allow / (VERIFIED). |
| **Sobors** (sobors.hu) | **IndaWorld Publishing Kft.**, member of Indamedia Network Zrt., Cg. 01-09-429075 (VERIFIED: https://sobors.hu/impresszum/) | Not counted. | None found. | https://sobors.hu/info/szerzoi-jogok: all content is IndaWorld's intellectual property, and any use without prior written permission is forbidden, "beleértve a tartalom szöveg- és adatbányászat céljára való felhasználását is". This is an **explicit TDM reservation** under Szjt. 35/A. A "nagyon rövid részlet" (very short extract) may be taken freely, which they define as the title plus at most 10 tags. (VERIFIED) | robots blocks AI-training crawlers with a dedicated section (VERIFIED). |
| **Receptneked** (receptneked.hu) | **Receptneked Kft.**, 6763 Szatymaz, Cg. 06-09-026585 (VERIFIED: https://receptneked.hu/impresszum/) | **~28,400 recipe URLs** (COMPUTED: 29 recipe sitemaps, file 1 = 1,000 and file 29 = 390, assuming files 2–28 are full). | None found. | Terms (https://receptneked.hu/felhasznalasi-feltetelek/) ban circumventing technical protections and "automatizált támadás vagy túlzott terhelést okozó kérés". The user-content licence is non-exclusive and covers partners. (VERIFIED) | robots: `Content-Signal: search=yes,ai-train=no,use=reference`, and GPTBot, ClaudeBot, CCBot, Google-Extended and others are disallowed (VERIFIED). |
| **Kifőztük** (kifoztuk.hu) | **Szépségtár Kft.** (VERIFIED: https://kifoztuk.hu/copyright/) | "Már 7,064 recept" (VERIFIED, self-reported) | None | "A szerzők engedélye nélkül történő másolásuk, felhasználásuk … jogkövetkezményeket von maga után." (VERIFIED) | robots allows all. |

**Takeaways.** Every major Hungarian recipe publisher reserves reuse, and the two biggest (Nosalty, Mindmegette) hold sublicensable or exclusive rights over their large UGC recipe pools. None offers a public API or a syndication programme on its site; I found only ad/media-sales pages. Sobors, Receptneked and Index also signal a TDM/AI opt-out. **Scraping recipe texts or photos from these sites for a commercial app is ruled out on contract, copyright (photos and text), sui generis database and TDM-reservation grounds.** The only legitimate routes are a content licence or partnership, which is commercially plausible because all of them sell sponsored content (Nosalty's media kit sells "egyedi hirdetői megoldások"), or a title-plus-link "discovery" model. Even that needs written permission at Mindmegette; Sobors allows title plus up to 10 tags freely.

Partnership value (ESTIMATE): Nosalty has a dietitian-built ingredient database with per-recipe calories and nutrients. Its sales page says it is "Magyarország első nyilvános alapanyag-adatbázisa" and that "minden recepthez biztosítunk pontos kalória és tápanyag összetételt" (VERIFIED, self-claim). Licensing a curated subset of a few hundred recipes plus nutrition from Central would replace most in-house content work. The price is unknown; publishers usually want brand attribution, links back and revenue share.

---

## 2. Open recipe datasets and licences

| Dataset | Size | Licence | Usable commercially? |
|---|---|---|---|
| **Hungarian Wikibooks "Szakácskönyv"** | **9,092 pages** under the `Szakácskönyv/` prefix (VERIFIED via MediaWiki search API totalhits, 2026-10-12). This count includes non-recipe pages (Tudnivalók, Diéta, etc.). | **CC BY-SA 4.0**. Footer: "Creative Commons Nevezd meg! – Így add tovább! 4.0 licenc" (VERIFIED: https://hu.wikibooks.org/wiki/Szakácskönyv) | Yes, with **attribution and share-alike**. Any adapted recipe text we publish must also be CC BY-SA, so competitors could copy it. Facts (ingredient combinations, methods) are free anyway. Quality, units and provenance vary; there is no nutrition and no photos (ESTIMATE from browsing titles). Best used as an idea source, not as published text. |
| **English Wikibooks Cookbook** | Category:Recipes = 3,829 pages (VERIFIED via API) | CC BY-SA 4.0 | Same as above. English, so it needs translation and localisation. |
| **RecipeNLG** | 2,231,142 recipes (VERIFIED: https://github.com/Glorf/recipenlg) | The PUT download agreement limits use to non-commercial research and educational purposes (per HF dataset card; https://huggingface.co/datasets/mbien/recipe_nlg) | **No.** It is also scraped from US sites. |
| **TheMealDB** | Not stated | The test key "1" is for development or educational use, and "you must become a supporter if releasing publicly on an appstore" (VERIFIED: https://www.themealdb.com/api.php) | Only as a paying supporter. English, international dishes, poor fit for HU. |
| Recipe1M+, Food.com (Kaggle) | — | Research-only or unclear provenance (not re-verified this session) | Treat as no. |
| Spoonacular / Edamam APIs | — | Commercial paid APIs (terms not re-verified this session) | Possible but English/US-centric. No HU prices, poor HU food fit. |
| **MDOSZ / okostanyer.hu recipes** ("Receptek" section; "30 év 30 recept" PDF https://www.okostanyer.hu/wp-content/uploads/2022/09/30ev30recept.pdf) | Small | No open licence seen, so all rights reserved by default | Only via partnership. MDOSZ is the natural "healthy" partner (see §5). |

Conclusion: **no open, commercially usable, Hungarian-language recipe dataset of decent quality exists.** HU Wikibooks is the only open HU source, and share-alike makes it unattractive as published text. That points to an in-house library (§4), a licence (§1), or both.

---

## 3. Legal status of recipes (EU / HU)

The statute text below was VERIFIED in the consolidated Szjt. (1999. évi LXXVI. törvény) at https://njt.jog.gov.hu/jogszabaly/1999-76-00-00.

- **The method and the ingredient list (facts, idea, procedure) are not protected.** Szjt. 1. § (6): "Valamely ötlet, elv, elgondolás, eljárás, működési módszer vagy matematikai művelet nem lehet tárgya a szerzői jogi védelemnek." Protection needs "egyéni, eredeti jelleg" (1. § (3)). The Hungarian Copyright Expert Board opinion **SZJSZT 21/2004** ("Szakácskönyv, illetve receptek szerzői jogi védelme") applied this to recipes. As reported in search snippets of the opinion (the PDF itself now returns 404), copyright covers the *expressed form* of a recipe (copying or communicating the text), while cooking by the recipe needs no permission. CJEU **C-310/17 Levola Hengelo** (2018) held that the taste of a food is not a "work". The inference from 1. § (6) is that a dish, its ingredient set and its general method are free to reuse.
- **The instruction text can be protected** when its wording is original. The EU threshold is the author's own intellectual creation (Infopaq), and the bar is low. Practical rule (ESTIMATE): write all instructions ourselves and never paste or lightly paraphrase another site's text, especially distinctive prose, tips or stories.
- **Food photos are protected.** Szjt. 1. § (2) i) lists "fotóművészeti alkotás", and the EU originality test for photos is low (Painer C-145/10). Never reuse photos.
- **The collection is protected as a database.** Szjt. 84/A: the maker's consent is needed to extract or re-use "az adatbázis tartalmának egészét vagy jelentős részét", or even insubstantial parts repeatedly and systematically (84/A (3)), when "jelentős ráfordítás" (substantial investment) went into it (84/A (5)). CJEU C-762/19 CV-Online (from the brief) adds a harm-to-investment test. Systematic harvesting of ingredient lists from Nosalty or Mindmegette could infringe the database right even though each list is unprotected (ESTIMATE). The same right will protect **our own** curated library.
- **Contract (website terms).** Under CJEU C-30/14 Ryanair v PR Aviation (2015), where a database is not protected by copyright or the sui generis right, the maker may still restrict use by contract. The HU sites' terms (§1) are therefore relevant on their own (legal reading; not re-fetched this session).
- **TDM / AI.** Szjt. 35/A (1) allows commercial text and data mining only if the rightholder "nem tiltakozott … géppel olvasható formában" (has not objected in machine-readable form). Sobors (terms), Receptneked (robots Content-Signal ai-train=no) and Index/Sobors (robots blocks AI crawlers) have objected. Training or fine-tuning an LLM on their recipes, or RAG over them, is therefore not covered by the exception (ESTIMATE, legal reading).
- **Press-publisher right** (Szjt. 82/A–): Mediaworks asserts it for Mindmegette (VII.11). It mainly matters for article snippets.

**Implications.** (a) Recipes for common dishes (paprikás csirke, lencsefőzelék) can be written from scratch without anyone's permission. (b) Do not copy text, photos or systematic extracts. (c) LLM drafting must not use these sites as retrieval sources. (d) Purely AI-generated text likely lacks copyright protection under the EU "own intellectual creation" test (ESTIMATE). Human editing and the database right still protect our library.

---

## 4. In-house recipe library for the MVP

### 4.1 How many recipes (ESTIMATE, reasoning shown)
- Planning model: 4 weeks ahead, 7 days. The Hungarian main meal is lunch (often soup plus main), with a lighter dinner.
- **No repeat within 4 weeks** means 28 main-dish slots per user (56 if lunch and dinner are both "main").
- **Filters shrink the pool.** Vegetarian is about 25–35% of a typical library, quick (≤30 min) about 40%, budget about 50%. For the narrowest common filter (vegetarian) to still give at least 28 mains, the library needs about 30–40 vegetarian mains, i.e. **about 100–120 mains in total**.
- **Seasonality.** Suppose about 40% of recipes are tied to a season (spring/summer/autumn/winter, roughly 10% each). Then about 70% of the library is usable in any given month, and 110 mains leave about 75 in-season.
- **OKOSTÁNYÉR weekly rules** (§5) need minimum category depth over 4 weeks: ≥1 fish meal per week (needs ≥6–8 fish mains), ≥1 legume meal per week (≥6–8), ≥1 meat-free day per week, red meat capped at 350–500 g cooked per week, potatoes at most every other day, sweets at most twice a week.
- **Recommended MVP: about 150 recipes** = 100–110 mains (of which about 35 vegetarian, about 10 fish and about 10 legume-based), 20–25 soups (a Hungarian staple), 15–20 breakfasts or light dinners, and about 10 sides or salads. **Absolute minimum to launch: about 100.** **Target after 6–12 months: 250–300.**
- **Design constraint from GVH coverage:** price comparison only works for ingredients GVH covers. Write recipes so that **≥70–80% of ingredient cost falls in GVH categories** (ESTIMATE target). The rest (spices, herbs, chickpeas/beans, oats, zucchini, mushrooms per the brief) gets marked "price not available". Of the legumes, only lentils (and frozen peas) are priced in GVH, so legume meals will lean on lentils (lencsefőzelék, lencseleves, lencsesaláta) until another price source exists.

### 4.2 Dietitian validation cost
- Consumer reference prices (VERIFIED): SYNLAB charges 30,000 Ft for a 60-min in-person dietetic consultation and 20,000 Ft for 45 min online (price list valid from 2024-07-01, https://synlab.hu/content/pricelist/SYNLAB-arlista_Konzultacio_20240701.pdf). Wáberer Medical Center charges 24,000 Ft for a dietitian consultation (https://wmc.hu/en/?p=8669, date not shown). MDOSZ has about 2,500 members (secondary, search snippet of an MDOSZ document).
- Effort (ESTIMATE): 20–40 min per recipe (check portions, the nutrient calculation, allergens, the tag/claim wording), plus 15–25 h to set up the framework (planner rules from OKOSTÁNYÉR, tag taxonomy, claims policy). For 150 recipes that is about **75–100 h**.
- Cost (ESTIMATE): about **1.0–2.0M Ft** at a B2B freelance rate of 12,000–20,000 Ft/h, or **2.3–3.0M Ft** at consumer-level rates of 24,000–30,000 Ft/h. After that, a retainer of about 150–300k Ft per month for new recipes and claim review.
- Other content costs (ESTIMATE, not verified): one test-cook per recipe, about 1,500–3,500 Ft of ingredients per 4-portion test (this can be computed from GVH prices), so about 0.3–0.5M Ft for 150. Photos: either own photos (phone plus light box) or a freelance food photographer, an unverified market rate of perhaps 8–25k Ft per final image.

### 4.3 LLM-assisted drafting with human review (ESTIMATE)
- **Pipeline:** (1) the LLM drafts into a strict schema (ingredients in grams with a composition-table code and the GVH category; steps; times; servings; the 14 EU allergens), constrained to GVH-priced ingredients and OKOSTÁNYÉR rules, with no web or recipe-site retrieval (see §3 TDM). (2) Automated checks: nutrient calculation (§6), allergen detection, salt per portion, cost per portion from GVH, and unit sanity. (3) A human cook-test, at least for every recipe before it goes live. (4) Dietitian sign-off on nutrition text and tags.
- **Savings:** drafting falls from about 1–2 h to about 15–30 min of editing per recipe. LLM API cost is negligible (a few USD for 150 recipes). The binding costs are cook-testing and dietitian review.
- **Risks:** hallucinated quantities or times, food-safety errors (poultry doneness, raw egg), Hungarian culinary authenticity, near-duplicate text of a famous recipe (spot-check), and copyright thinness of purely AI text. AI-generated dish images can mislead, so prefer real photos or clearly labelled illustrations.

---

## 5. "Healthy" standards to anchor on

### 5.1 OKOSTÁNYÉR® (MDOSZ), the best HU anchor
- Owner/author: MDOSZ. The renewal was done in 2021 (adult) and announced 2023-09-18, endorsed by MTA ÉTB, MTT and OGYÉI. There are separate versions for adults and for 4–17-year-olds. VERIFIED: https://www.okostanyer.hu/2023/09/18/megujult-a-felnotteknek-szolo-okostanyer/
- **Machine-encodable rules** (VERIFIED from the English adult leaflet https://www.okostanyer.hu/wp-content/uploads/2021/11/2021_OKOSTANYER_ANGOL_felnott_A4.pdf and the HU renewal article):
  - ≥5 portions of vegetables and fruit a day (3–4 veg plus 1–2 fruit, at least 1 raw). The HU article puts it at **500 g/day**. Potatoes do not count; eat potatoes at most every other day.
  - Legumes at least once a week. Nuts and seeds 2–3 times a week.
  - 3 portions of grains a day, at least 1 wholegrain.
  - Milk and dairy daily, preferring lower fat.
  - **At least one meat-free day a week.** Red meat no more than 350–500 g cooked (500–700 g raw) a week. Processed meat only occasionally. Fish at least once a week.
  - Sweets at most twice a week. Limit high-fat foods. Breaded or deep-fried only occasionally. Use oils and fat-sparing techniques.
- **Licence / usability:** the guideline *content* (rules and facts) can be implemented freely as planner logic; ideas and recommendations are not protected under Szjt. 1. § (6), though the leaflets' text and graphics are. "OKOSTÁNYÉR®" carries ® on every page, so the **name and logo are a registered trademark** (holder presumably MDOSZ; not checked in the SZTNH register this session). Using the name or logo to badge recipes or the app ("OKOSTÁNYÉR-kompatibilis") needs **MDOSZ permission**. Saying "based on the Hungarian dietary guideline (MDOSZ OKOSTÁNYÉR)" as a factual reference is lower risk, but should also be cleared (ESTIMATE). NutriComp software already evaluates diets "Okostányér® ajánlás szerint" (VERIFIED: Táplálkozástudományi és Dietetikai Szemle 2022/1 article by NutriComp Bt.), which shows a commercial tool aligning with it.

### 5.2 WHO and EFSA
- WHO "Healthy diet" fact sheet (dated 26 Jan 2026; VERIFIED: https://www.who.int/news-room/fact-sheets/detail/healthy-diet): ≥400 g fruit and vegetables a day; free sugars <10% of energy (<5% for further benefit); total fat ≤30%; saturated fat ≤10%; trans fat ≤1%; salt <5 g/day (2 g sodium).
- EFSA: DRVs (AR/PRI/AI/RI) via the DRV Finder. EFSA only advises on food-based dietary guidelines; member states set them (VERIFIED: https://www.efsa.europa.eu/en/topics/topic/dietary-reference-values). Use EFSA reference intakes for per-portion "% of daily need" displays. Regulation 1169/2011 Annex XIII reference intakes, the ones used on labels (8400 kJ/2000 kcal, 70 g fat, 20 g saturates, 260 g carbohydrate, 90 g sugars, 50 g protein, 6 g salt), are the safer choice for consumer-facing % figures (from regulation knowledge; not re-fetched).

### 5.3 Nutri-Score in Hungary
- Not adopted or recommended by Hungary. Santé publique France lists the countries that recommend it as France (2017), Belgium, Switzerland, Germany, Spain, the Netherlands and Luxembourg (VERIFIED: http://www.santepubliquefrance.fr/nutri-score).
- Hungary co-sponsored the **September 2020 AGRIFISH non-paper** (with IT, CZ, CY, GR, LV, RO) opposing Nutri-Score-type colour coding and backing a voluntary approach and NutrInform (secondary: Olive Oil Times, CEP; https://oliveoiltimes.com/business/countries-protest-nutri-score-labels/85966).
- An EU harmonised front-of-pack scheme was never proposed. 2025 reports say it was shelved (secondary: ANSA 2025-03-25, ESM).
- Nutri-Score appears voluntarily on some HU packs (e.g. Danone from July 2021; Trademagazin 2021-08-26 and 2023-10-16).
- Logo use is free but requires registration as a company or brand. The guidance addresses food operators, not apps (VERIFIED: Santé publique France page).
- **Implication:** showing Nutri-Score in a HU app is not a national standard, could read as "foreign" or contested, and raises logo-use questions. OFF computes it (9 of 24 OFF hits had a grade). Prefer OKOSTÁNYÉR-based tags plus plain nutrient values.

### 5.4 Public-catering decree 37/2014. (IV. 30.) EMMI as a benchmark
VERIFIED, consolidated text: https://njt.jog.gov.hu/jogszabaly/2014-37-20-5H. Annexes 5 and 6 were last replaced by 53/2024. (XI. 11.) BM rendelet.
- §7: for all-day catering, at least 4 portions a day of vegetables (not potato) or fruit, at least 1 raw, plus 3 portions of grain-based food, at least 1 wholegrain. Dairy daily.
- §11: over 10 consecutive catering days, at most 30% of energy from fat (35% for ages 1–3) and at most 20% from sugars (15% for single-meal catering).
- §12 and Annex 5: daily salt limits per age group. For all-day catering, 19–69 years: 5 g target, at most 12 g during the transition period, which §18 allows only until 2028-08-31. Iodised salt only.
- §14 bans, among others, salty seasoning powders and soup cubes (except for texture), meat with >30% fat, sugary soft drinks and syrups, energy drinks, palm or coconut fat for cooking, and since the 2025-02-09 amendment peanuts, tree nuts and sesame. Sweets cannot be served as a stand-alone lunch.
- Annex 6, frequencies per 10 catering days for all-day catering: meat 6–14 times; **fish ≥1**; deep-fried food ≤1; **wholegrain ≥10**; dry pasta ≤3; **dry legumes ≥3**; sweets/fine pastry ≤6.
- **Use:** a defensible, official Hungarian benchmark to calibrate the planner (frequency caps and minima per 10 days, fat/sugar energy shares, salt per day). It legally binds only public caterers, not an app.

---

## 6. Nutrition data

### 6.1 Open Food Facts: licence and share-alike implications
- Licences (VERIFIED: https://world.openfoodfacts.org/terms-of-use): the database is under **ODbL**, individual contents under **DbCL**, and images under **CC BY-SA** ("may contain graphical elements subject to copyright"). Commercial use is allowed. Attribution must link to openfoodfacts.org. Derivative works must be shared under the same terms.
- ODbL mechanics (VERIFIED: https://opendatacommons.org/licenses/odbl/1-0/):
  - §4.4: a **Derivative Database** that is "Publicly Used" must be ODbL. Extracting a substantial part into a new database counts as a Derivative Database (4.4b), and it is Publicly Used if a **Produced Work** made from it is publicly used (4.4c).
  - §4.6: if you publicly use a Derivative Database, or a Produced Work from one, you must offer the derivative database, or a file of all alterations, in machine-readable form, free over the internet.
  - §4.5a: a **Collective Database** (OFF *unmodified*, alongside independent databases) does **not** need to be ODbL.
  - §4.5c: internal use is not public use.
- **Practical implication (ESTIMATE, legal reading):**
  - If we merge OFF nutrition into our product table (e.g. a GVH product × OFF nutriments join) and show it in the app, we probably create a Derivative Database used publicly through a Produced Work. We would then have to **publish that merged database (or the alteration file) under ODbL**, which could expose our GVH-price-to-barcode mapping and curation.
  - Safer pattern: keep OFF in a **separate, unmodified store** (a Collective Database), join at query time, keep our price data and recipe library in independent databases, and attribute OFF in the UI. Contribute corrections back to OFF.
  - Images are CC BY-SA and may include packaging trademarks. Avoid them or attribute them.
  - Rate limit: 15 product reads per minute per IP (per user when calls come from the mobile app). For bulk use, run a **daily JSONL/CSV dump** into our own backend (VERIFIED: API docs).
- Size: OFF search API count for `countries_tags_en=hungary` = **11,743 products** (VERIFIED by API call, 2026-10-12, https://world.openfoodfacts.org/api/v2/search?countries_tags_en=hungary).

### 6.2 OFF coverage of real GVH barcodes (COMPUTED)
Method: GVH API `/products-by-category/{leaf}?offset=0` for all 120 food leaf categories (first page, max 48 products each) gave 1,316 products. Of these, 605 have a valid EAN-13 (13 digits, not starting with 2, correct check digit). I drew a stratified random sample (seed 20261012) of 60 barcodes, at most 1 per leaf category, and queried `https://world.openfoodfacts.org/api/v2/product/{code}.json` about once per 1.2 s.

| Metric | Result |
|---|---|
| Product found in OFF | **24/60 = 40%** (95% Wilson CI 29–53%) |
| Found with energy per 100 g | 19/60 = 32% (21–44%) |
| Found with full mandatory 7 per 100 g (energy, fat, saturates, carbs, sugars, protein, salt) | **16/60 = 27%** (17–39%) |
| Nutri-Score grade present | 9/60 |
| Hungarian ingredient text | 2/60 (any-language ingredients 7/60) |
| Tagged country Hungary | 14/24 hits |
| Found, packaged items only (excluding Zöldség-gyümölcs) | 23/45 = 51% (37–65%) |
| Fresh produce (Zöldség-gyümölcs) | 1/15 found |
| By prefix: 599 (HU) | 13/42 = 31%; 505 (UK GS1, mostly Tesco own label) 4/5; other 7/13 |

**Key structural limit (COMPUTED from the same 1,316 GVH products):** valid EAN-13 by chain is Spar 88%, Tesco 78%, Auchan 72%, drugstores 100%, but **Lidl 12%, Penny 12%, Aldi 6%**. GVH lists discounters' private labels under internal ids ("lidl-…", "aldi-…", "penny-…"). By category: Hús 27%, Zöldség 39%, Pékáru 38%, Tejtermék 45%, Tartós 63%, Speciális 68%. All food page-1 products: 605/1,316 = 46%.
**Effective OFF nutrition coverage of GVH food SKUs: about 46% × about 27–32% ≈ 12–15%** (COMPUTED extrapolation; page-1 products only, so it may over-represent popular items).
Data quality: names are often non-Hungarian (e.g. a Tesco camembert carries a Czech name), and some HU-relevant fields are missing.
**Conclusion: OFF cannot be the nutrition backbone. It is an optional enrichment for branded packaged products.** Recipe nutrition must come from generic composition tables.

### 6.3 Generic composition tables usable commercially

| Table | Version / size | Licence | Fit for HU recipes |
|---|---|---|---|
| **CIQUAL (ANSES, France)** | **Ciqual 2025, published 2025-11-19, 3,484 foods, 74 constituents** (VERIFIED: https://www.anses.fr/en/content/new-enhanced-and-more-representative-version-ciqual-table; dataset doi:10.57745/RDMHWY) | **Etalab Open Licence 2.0** (VERIFIED via the Dataverse API, licence field "etalab 2.0"). Commercial reuse is allowed with attribution (producer plus date of last update). It is CC-BY-compatible. | **Best primary source**: European foods, recent, permissive, XML/XLSX files. |
| **Frida (DTU, Denmark)** | **Frida 5.5** (Nov 2025, made available 2026-01-19) (VERIFIED: figshare API https://api.figshare.com/v2/articles/29500682, DOI 10.11583/DTU.29500682) | **Dataset files CC BY 4.0** (the PDF documentation is © DTU) (VERIFIED). The DTU Orbit page footer "All rights reserved incl. TDM" is the portal's generic footer, not the dataset licence. | Good second source with rich analytical data. Nordic foods. |
| **USDA FoodData Central** | SR Legacy / Foundation / FNDDS | **CC0 / public domain**: "USDA FoodData Central data are in the public domain and they are not copyrighted." API: 1,000 requests/hour per IP with a data.gov key (VERIFIED: https://fdc.nal.usda.gov/api-guide/) | Use for gaps. **Caution:** US flour and rice are often *enriched*, so pick unenriched codes. US cuts differ from HU cuts. USDA Nutrient Retention Factors Release 6 (2007) is also public (https://www.ars.usda.gov/Services/docs.htm?docid=9448). |
| **McCance & Widdowson CoFID (UK)** | 2021 update (VERIFIED: https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid) | **Open Government Licence v3.0** ("All content is available under the OGL v3.0, except where otherwise stated") (VERIFIED). The Quadram FN-NBRI API version is **CC BY-NC-SA**, so don't use that route (secondary). | Usable with attribution. Last full validation of older foods is dated. |
| **Fineli (THL, Finland)** | >5,000 foodstuffs, 55 nutrients (VERIFIED: suomi.fi listing) | CC BY 4.0 per a University of Helsinki page (secondary). Fineli is a THL trademark and must not imply THL endorsement (secondary). fineli.fi sits behind a Cloudflare challenge, which I did not bypass, so the licence is NOT VERIFIED from the primary page. | Optional. |
| **Hungarian tables** | **Rodler I.: Új tápanyagtáblázat, Medicina, 2005**, print (VERIFIED as cited in a 2022 HU journal reference list). **NutriComp** (NutriComp Bt., Budapest) is a commercial dietitian software (Étrend, Sport, DietCAD) whose Hungarian food-composition database is "évente … több alkalommal online frissítésre kerül" (VERIFIED: Táplálkozástudományi és Dietetikai Szemle 2022/1, https://real-j.mtak.hu/30587/1/TaplalkozastudomanyiDietetikaiSzemle_2evf1szam.pdf). A 2011 parliamentary question asked when the national nutrient table would be online (VERIFIED: https://www.parlament.hu/irom39/03937/03937.pdf). tapanyagtablazat.med.unideb.hu **no longer resolves** (DNS check 2026-10-12). | **No open Hungarian table found**: Rodler is copyrighted print; NutriComp is a commercial licence. | For HU-specific foods (túró, tejföl 12/20%, trappista, parasztkolbász, lecsókolbász), use CIQUAL/Frida analogues or the producer's label values from OFF or packaging. A NutriComp data licence or a Nosalty partnership are the paid HU-native options. |

### 6.4 How to compute recipe nutrition (method)
1. Store each ingredient as **edible raw weight in grams**. Convert units such as "1 db tojás" (≈50 g edible, ESTIMATE) or "1 fej hagyma" with a conversion table, and apply edible-portion factors for peel and bones.
2. Map each ingredient to **one composition code** (CIQUAL primary, Frida/USDA fallback) and record the source and version (for attribution under Etalab and CC BY).
3. Sum the nutrients of the raw ingredients. For cooked dishes, either (a) apply **yield factors** (weight change from water loss or uptake) and **retention factors** for vitamins (USDA Release 6, EuroFIR recipe-calculation guidance), or (b) for energy and macronutrients, ignore retention (macros are stable) and correct only for fat absorbed in frying. A footnote in the annexes of 37/2014 EMMI counts at most 30% of the frying fat into the nutrient content, which is a usable HU convention (VERIFIED in the decree).
4. Salt: "ízlés szerint" needs a default (e.g. 1 g per portion, ESTIMATE) or exclusion, with a note.
5. Divide by servings and show per portion: energy (kJ/kcal), fat, saturates, carbohydrate, sugars, fibre, protein, salt. Optionally show % of the 1169/2011 reference intakes.
6. Have the dietitian spot-check about 10% of recipes against NutriComp or another reference.

---

## 7. What the app can say about "healthy" (regulation)

- **Regulation (EC) 1924/2006** (VERIFIED: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02006R1924-20141213):
  - Art. 1(2): applies to nutrition and health claims "made in commercial communications", whether in labelling, presentation or advertising of foods.
  - Art. 2(2)(1): "claim" = "any message or representation, which is not mandatory…".
  - Art. 10(3): "general, non-specific benefits … for overall good health" (e.g. "healthy", "egészséges") are allowed only when accompanied by an authorised specific health claim.
  - Annex conditions (examples): LOW FAT ≤3 g/100 g; HIGH PROTEIN ≥20% of energy from protein; SOURCE OF FIBRE ≥3 g/100 g or ≥1.5 g/100 kcal; LOW SODIUM/SALT ≤0.12 g sodium per 100 g.
- **CJEU C-19/15 Innova Vital (2016)** (VERIFIED: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62015CJ0019): claims in a commercial communication fall under 1924/2006 even when addressed only to professionals. "Commercial communication" takes the Directive 2000/31 Art. 2(f) definition: any communication designed to promote, **directly or indirectly**, goods, services or image. So once the app promotes specific products, retailers or affiliate links, its statements about those foods can be commercial communications.
- **Recipe content vs food labels (ESTIMATE, legal reading):**
  - A self-written recipe is not a "food placed on the market". Editorial descriptions of our *own* recipes ("zöldségben gazdag", "húsmentes") are lower risk.
  - Risk rises when (a) claims sit next to specific branded products or price, affiliate or retailer-sponsored placements, (b) we use regulated claim words ("alacsony zsírtartalmú", "magas fehérjetartalmú", "rostforrás") without meeting Annex thresholds, or (c) we use disease or health-function claims ("csökkenti a koleszterint", "erősíti az immunrendszert"), which are only allowed if authorised and product-specific.
  - Safe pattern: show factual per-portion nutrients; use descriptive OKOSTÁNYÉR-based tags (e.g. "1 adag hüvelyes", "teljes kiőrlésű gabona"); if using claim words, apply Annex thresholds per 100 g of dish as a self-imposed rule; avoid "egészséges" as a product label; never make health or disease claims; add a disclaimer that the app is not medical advice.
  - In Hungary, NÉBIH supervises food information and GVH supervises unfair commercial practices (secondary knowledge, not verified this session).
- **Value of a dietitian partner (ESTIMATE):**
  - credibility, since "dietetikus" is a regulated health profession in HU (not re-verified this session);
  - validation of nutrient calculations and portion sizes;
  - claim-wording review against 1924/2006;
  - designing the planner rules (OKOSTÁNYÉR, 37/2014);
  - allergen correctness;
  - a route to an MDOSZ or OKOSTÁNYÉR® trademark permission;
  - optionally a paid "személyre szabott" tier later.
  - Cost per §4.2.

---

## 8. Recommended data strategy (ESTIMATE)
1. **Recipes:** a self-written library of about 150 recipes for the MVP (LLM-drafted, cook-tested, dietitian-validated), designed around GVH-priced ingredients. In parallel, pursue a **licence with Central (Nosalty)** or Mediaworks (Mindmegette) for scale. Do not scrape recipe sites.
2. **Healthy logic:** encode the OKOSTÁNYÉR weekly rules, calibrated with the 37/2014 EMMI 10-day frequencies and WHO limits. Seek MDOSZ permission before using the OKOSTÁNYÉR® name. Skip Nutri-Score.
3. **Nutrition:** CIQUAL 2025 (Etalab 2.0) as primary, with Frida 5.5 (CC BY 4.0) and USDA (CC0) as fallbacks, plus manual HU-specific entries from labels. OFF only as a separate, unmodified enrichment store (ODbL collective-database pattern) for packaged branded items. Expect about 12–15% of GVH food SKUs to have OFF nutrition.
4. **Claims:** factual nutrients plus descriptive tags. Keep commercial or affiliate content visibly separate from nutrition statements.

## Open questions
- Will Central (Nosalty) or Mediaworks license recipes and nutrition data to a startup, and on what terms?
- Who exactly holds the OKOSTÁNYÉR® trademark (SZTNH register), and what are MDOSZ's terms for app use?
- Can NutriComp's HU food database be licensed for app use, and at what price?
- Exact Mindmegette recipe count.
- Fineli licence on the primary page.
- B2B dietitian rates in Budapest (I have only consumer consultation prices).
- Whether NÉBIH has guidance on recipe or app nutrition statements.
