# Adversarial fact-check: "Recipe content and nutrition data sources" stream

Date: 2026-10-12. Checker: adversarial verification subagent.
Labels: **VERIFIED** = re-read in a primary source this session (URL given). **COMPUTED** = derived from data I pulled this session (method given). **ESTIMATE** = reasoning. Nothing here is legal advice.

Files I created (all under this folder):
- `verify_dl/` raw downloads (untrusted data): full GVH food catalogue (`gvh/all_food_products.json`), robots.txt files, OFF re-sample, terms pages, CIQUAL XML, Kifli pages, 2016 ministry PDF
- `verify_scripts/` my scripts (`fetch_all.py`, `ean_full.py`, `off_resample.py`, `off_resample_summary.py`, `wb_allpages.py`, a copy of `pdftext.py`)
- `verify_data/gvh_ean_share_full_catalogue.txt`, `verify_data/off_resample_results.csv`, `verify_data/off_resample_summary.txt`

Politeness: GVH about 1 request per 0.8 s (159 requests in total). OFF product reads 1 per 4.2 s (about 14 per minute, within OFF's documented 15 per minute), plus 2 search calls 7 s apart. Wikimedia sent 429 after 9 calls, so I stopped there. No logins, forms or protections bypassed.

---

## Headline: one load-bearing number is wrong, and the error reaches beyond this stream

**The GVH API's default page is 12 products, not 48, and products come back roughly in ascending unit-price order.** COMPUTED/VERIFIED by calling `GET /api/products-by-category/7?offset=0`. Without a limit parameter it returns 12 of 52 products. With `&limit=48` it returns 48. `offset=12` returns the next 12. The first 12 are the cheapest: aldi-…, lidl-…, penny-… ids first. Across all 120 food leaf categories, 92 are strictly ascending by `minUnitPrice`.

The stream's "first page" was therefore the **12 cheapest products per category** (1,316 of 4,332 SKUs). Those over-represent discounter private labels that GVH lists under internal ids. Any other stream that sampled "page 1" has the same bias. The brief's line "(max 48 per page)" should read "default 12 per page; `limit` up to at least 48".

Re-run on the **full** food catalogue: 120 leaf categories, 4,332 products, all fetched with `limit=48` (COMPUTED, `verify_data/gvh_ean_share_full_catalogue.txt`):

| Metric | Stream (page 1 only) | Full catalogue (this check) |
|---|---|---|
| Valid EAN-13 (13 digits, check digit OK, not starting with 2) | 605/1,316 = 46% | **3,012/4,332 = 69.5%** |
| Products ranked 13th and later in their category | n/a | 2,407/3,016 = 79.8% |
| Spar / Tesco / Auchan | 88% / 78% / 72% | **92% / 90% / 87%** |
| Lidl / Aldi / Penny | 12% / 6% / 12% | **19% / 20% / 22%** |
| Hús-hal / Zöldség-gyümölcs / Tejtermék / Tartós / Speciális / Pékáru | 27/39/45/63/68/38% | 45/45/71/86/84/58% |

Non-EAN ids in the full catalogue: 327 in-store codes starting with 2, aldi- 322, lidl- 301, penny- 256, **spar- 76**, plus a few 8–12-digit codes. 990 of the 4,332 products are listed only at Lidl, Aldi or Penny.

**OFF re-sample** (COMPUTED, `verify_data/off_resample_summary.txt`): a simple random sample of 60 valid EAN-13s from the full catalogue (seed 1012), checked against OFF API v2:
- found 30/60 = **50%** (95% Wilson CI 38–62%)
- energy per 100 g present: 21/60 = **35%** (24–48%)
- all 7 mandatory nutrients per 100 g: 17/60 = **28%** (19–41%)
- tagged Hungary: 13/60 = 22%

I re-checked 10 of the stream's own barcodes (5 hits, 5 misses), and all 10 reproduced. So the stream's OFF lookups were sound; the population it sampled was not.

**Corrected effective OFF nutrition coverage of GVH food SKUs:** 69.5% × 28–35% ≈ **19–24%**. Applying the CI bounds gives roughly 13–33% (COMPUTED extrapolation). The stream said 12–15%. The conclusion "OFF cannot be the nutrition backbone" still stands.

Side checks (VERIFIED by API, 2026-10-12): OFF products tagged Hungary: 11,743, matching the stream. Of those, 9,792 carry the state `en:nutrition-facts-completed`. OFF API docs confirm "15 req/min/IP" for product reads and 10 per minute for search, and point bulk users to the CSV/JSONL dumps (https://openfoodfacts.github.io/openfoodfacts-server/api/). OFF terms confirm ODbL for the database, DbCL for contents, CC BY-SA for images, commercial use allowed, attribution required, and derivatives under the same conditions (https://world.openfoodfacts.org/terms-of-use).

---

## Verdicts on the load-bearing items (8)

### 1. HU recipe sites reserve commercial reuse; there is no public API or syndication; scraping is ruled out. **CONFIRMED** (with one gap)
- Nosalty terms re-fetched (VERIFIED: https://www.nosalty.hu/felhasznalasi-feltetelek). The copyright and database-maker rights belong to the Szolgáltató (Central Médiacsoport Zrt.). Nothing beyond reading, display, temporary copies and personal non-commercial saving or printing is allowed "a Szolgáltató előzetes írásbeli engedélyének hiányában". Links must use the form "Forrás: Nosalty www.nosalty.hu …". The UGC licence is free, irrevocable, transferable and covers "harmadik személy részére alfelhasználási jog engedésének jogát" (the right to sublicense), granted to Central and its group.
- Street Kitchen (VERIFIED: https://streetkitchen.hu/felhasznalasi-feltetelek-sk, effective 2026-04-30). §5: "Kereskedelmi felhasználás csak a Szolgáltató előzetes írásbeli engedélyével lehetséges." §6 bans "automatizált adatgyűjtésre (pl. scraping, botok)".
- Sobors (VERIFIED: https://sobors.hu/info/szerzoi-jogok). Written permission is needed for any use, "beleértve a tartalom szöveg- és adatbányászat céljára való felhasználását is". The free "very short extract" is the title plus at most 10 tags.
- Mindmegette (VERIFIED: the PDF is live, Last-Modified 2025-12-02). A recipe may be taken only after prior written permission, with name only, no image and a link, and never "üzletszerűen". UGC carries an exclusive, transferable, sublicensable licence. robots.txt disallows `/publicapi` except `/publicapi/hu/rss/`: an internal API path exists, but it is not offered to third parties.
- **Gap the stream missed:** **Kifli.hu "Kifli Séf"** is a sizeable recipe publisher that was not assessed. COMPUTED: 3,373 `/sef/{id}` URLs in https://www.kifli.hu/sitemap_base.xml. See Missed.

### 2. TDM opt-outs: Sobors, Receptneked and Index object in machine-readable form, so training on them or retrieving from them is off the table. **PARTLY TRUE**
- Szjt. 35/A (1) b) re-read on njt (VERIFIED: https://njt.jog.gov.hu/jogszabaly/1999-76-00-00). Free TDM reproduction applies only if the rightholder "… géppel olvasható formában – nem tiltakozott". 84/D (2) extends this to database extraction.
- Robots.txt files re-fetched 2026-10-12 (VERIFIED):
  - **Index** blocks GPTBot, Google-Extended, CCBot, anthropic-ai, Applebot-Extended, Bytespider **and also the retrieval agents ChatGPT-User and PerplexityBot**.
  - **Sobors** blocks training crawlers (GPTBot, Google-Extended, ClaudeBot, Claude-Web, anthropic-ai, Applebot-Extended, CCBot, Bytespider, TikTokSpider, Amazonbot). It **explicitly allows** answer and retrieval agents (ChatGPT-User, OAI-SearchBot, Claude-User, Claude-SearchBot, Perplexity-User, PerplexityBot, …). The comment block (in Hungarian) says to block AI training and allow retrieval and citation bots.
  - **Receptneked** sets `Content-Signal: search=yes,ai-train=no,use=reference` and states that restrictions are express reservations under DSM Art. 4. `ai-input` (RAG and grounding) is **not set**, and its own legend says an unset signal "neither grants nor restricts".
  - **Nosalty, Mindmegette, Street Kitchen and Kifőztük have no AI or TDM signals** in robots.txt. Street Kitchen's ToS bans scraping in plain text; whether ToS text counts as "machine-readable" is legally unsettled (ESTIMATE).
- Corrected statement: the **training** opt-out is solid for Index, Sobors and Receptneked. A **retrieval** opt-out via robots exists only for Index. Sobors' robots signal invites retrieval bots, but its ToS reserves all TDM, and Receptneked leaves retrieval unspecified. This does not change the practical outcome. The TDM exception only ever covers copies *made for mining*; it never allows republishing recipe text or photos in an app. "Do not scrape or republish" stands on copyright, the database right and contract regardless of the opt-outs.

### 3. Ingredient lists and methods are free; text, photos and systematic extraction are protected. **CONFIRMED** (one sub-source unverifiable)
- Szjt. 1. § (6) "Valamely ötlet, elv, elgondolás, eljárás, működési módszer … nem lehet tárgya a szerzői jogi védelemnek" and 84/A (database maker's consent for the whole or a substantial part) were re-read on njt (VERIFIED).
- SZJSZT 21/2004: the old sztnh.gov.hu URL redirects to a "torol" page, and the Internet Archive was offline today. The opinion exists (search index shows the title and the opening reasoning about the expressed form), but I could not read its operative conclusion, so that part is **UNVERIFIABLE today**. The statutory basis alone supports the stream's reading.

### 4. No open, commercially usable Hungarian recipe dataset. **CONFIRMED**
- RecipeNLG: the HF card says "Researcher shall use the Dataset only for non-commercial research and educational purposes" (VERIFIED: https://huggingface.co/datasets/mbien/recipe_nlg).
- TheMealDB: "you must become a supporter if releasing publicly on an appstore" (VERIFIED: https://www.themealdb.com/api.php).
- HU Wikibooks: search totalhits for `prefix:Szakácskönyv/` is 9,092 (VERIFIED by API). A partial allpages crawl (A–I, 2,732 non-redirect pages before a 429 stopped me) includes many non-recipe pages, e.g. Italok/Borok/…. Usable recipe pages are well below 9,092 (ESTIMATE).

### 5. OKOSTÁNYÉR® is MDOSZ's; its rules can be coded; the name and logo need permission. **CONFIRMED** (trademark holder still unverifiable)
- okostanyer.hu homepage: "A Magyar Dietetikusok Országos Szövetsége (MDOSZ) elkészítette a legújabb magyar táplálkozási ajánlást, amely az OKOSTÁNYÉR® elnevezést viseli" (VERIFIED). The English adult PDF re-downloaded is byte-identical to the stream's copy (md5 b73ffa27…). It contains: legumes at least once a week; potatoes at most every other day; "Insert at least one meat-free day a week"; "not more than 350-500g a week of cooked … (500-700 g raw) red meat"; sweets at most twice a week; at least 5 portions of fruit and vegetables; 3 grain portions, at least 1 wholegrain (VERIFIED).
- Trademark holder: the TMview API was unreachable and web search found no register entry, so **UNVERIFIABLE**.
- New fact: MDOSZ publishes a running **monthly "OKOSTÁNYÉR receptek"** series on okostanyer.hu. The latest is 2026-09-18 ("szeptemberi-okostanyer-receptek-3") (VERIFIED from homepage links). This is a stronger partnership hook than the stream's "small" MDOSZ recipe set.

### 6. OFF coverage of GVH barcodes and the "46% valid EAN, 12–15% effective coverage" figures. **PARTLY TRUE: the EAN share and the effective coverage are REFUTED**
- The per-barcode OFF rates hold (stream 40% found and 27% full nutrition; mine 50% and 28%, CIs overlap).
- **46% valid EAN** is a sampling artefact. The full catalogue gives **69.5%**. Discounters are **19–22%**, not 6–12%.
- **Effective coverage is about 19–24%** (range 13–33%), not 12–15%. Details above.

### 7. Recipe nutrition from open tables (CIQUAL 2025 primary; Frida, USDA, CoFID fallbacks); no open Hungarian table. **CONFIRMED**
- CIQUAL 2025: Dataverse API (VERIFIED: https://entrepot.recherche.data.gouv.fr/api/datasets/:persistentId/?persistentId=doi:10.57745/RDMHWY). Licence "etalab 2.0"; released 2025-11-19; the description says 3,484 foods and 74 constituents. COMPUTED: the downloaded `alim_2025_11_03.xml` holds **3,484 `<ALIM>` records with `alim_nom_eng` English names**, so the French-only XLS is not a blocker.
- Frida: figshare API (VERIFIED: https://api.figshare.com/v2/articles/29500682). "Frida version 5.5", published 2026-01-19, licence **CC BY 4.0**; files are the xlsx/ods dataset plus DA/EN PDFs.
- No open HU table: `tapanyagtablazat.med.unideb.hu` returns **NXDOMAIN** (re-checked). A 2016 ministry summary on nutrition labelling (VERIFIED: elelmiszerlanc.kormany.hu, "Összefoglaló az élelmiszerek tápértékjelöléséről 2016 12 15.pdf") lists as Hungarian sources only:
  - that now-dead Debrecen site
  - **Rodler: Kalória- és tápanyagtáblázat (Medicina, 2008)**, an edition the stream missed
  - Rodler 2005 and Bíró–Lindner 1988, both print
  - a third-party PDF
  - FAO/INFOODS
  - a **sector database for frozen and canned products** compiled by the FM, NÉBIH, OGYÉI, NAK, Campden BRI Magyarország and MHKSZ. It is not open, but it is a partnership lead for frozen vegetables, which GVH prices.
- The claim stands.

### 8. MVP library of about 150 recipes; dietitian validation about 1–3M Ft (anchored on SYNLAB 30,000 Ft/60 min and WMC 24,000 Ft). **PARTLY TRUE**
- SYNLAB price list URL now returns **404**, so that anchor cannot be re-verified.
- WMC dietetics page (VERIFIED: https://wmc.hu/en/szakteruletek/dietetics/, redirected from ?p=8669) now says "Consultation with dietician **30 000 Ft-tól**" (from 30,000 Ft) and follow-up 25,000 Ft-tól. **The stream's 24,000 Ft is outdated.**
- The consumer anchor is therefore about 30,000 Ft per session, which puts the "consumer-rate" scenario at the top of the stream's range. The 75–100 h effort and the B2B rate are unverified ESTIMATEs.
- Library size: the arithmetic is internally consistent (28 vegetarian mains at a 30% vegetarian share ≈ 93 mains), but the result swings with the assumptions:
  - Hungarian "két napra főzés" (cooking soup or főzelék for two days) roughly halves the distinct slots.
  - Planning both lunch and dinner as mains doubles them.
  - Treat 100–150 as a planning ESTIMATE, not a finding.

---

## Other spot checks (not in the 8)
- CJEU C-19/15 Innova Vital: EUR-Lex returned an empty page to curl, so this is secondary only (ippt.eu, eulawradar). The ruling is that 1924/2006 covers claims in commercial communications even when addressed only to professionals. Its reasoning is about food business operators circumventing the rules. Nuance: whether an independent app's editorial recipe text is a "commercial communication" about a *food* is open. Risk concentrates where specific products, retailers or affiliate links are promoted, as the stream says.
- Nosalty media kit (VERIFIED): "több mint 63 000 ellenőrzött … recept"; "Magyarország első nyilvános alapanyag-adatbázisát", built under dietitian Bodon Judit; reach "több mint 2 és fél millió" people a month.

## Missed by the stream
1. **GVH API pagination and sort artefact** (default 12 per page, cheapest first). It invalidates "page-1" statistics here and possibly in other streams.
2. **Kifli.hu "Kifli Séf"** (COMPUTED: about 3,373 recipe URLs; VERIFIED on https://www.kifli.hu/sef/12444). Recipe pages carry schema.org Recipe JSON-LD, an "Adagonkénti ár" (price per portion, e.g. 1 343,61 Ft), "Kosárba tesz" (add all ingredients to cart), ingredient-set variants ("A séf választása", "Legolcsóbb – Spórolj akár 43%-ot", "BIO/Organikus") and a "Tápértékek" (nutrition) tab. This is a direct single-retailer competitor to features (2)+(3), and a potential content or affiliate partner. Kifli's robots.txt allows GPTBot and ClaudeBot and blocks CCBot (VERIFIED), but its content is still copyrighted.
3. **Retailer e-shops as a branded-product nutrition source.** Reg. 1169/2011 Art. 14 requires mandatory food information, including the nutrition declaration, before purchase in distance selling (legal reading, not re-fetched). Tesco, Auchan and Kifli product pages should therefore carry nutrition for the roughly 70% of GVH SKUs with EANs. Their ToS still apply, and a partnership is the clean route.
4. **MDOSZ's monthly OKOSTÁNYÉR recipe series**: a "healthy" content partner that also controls the ® name.
5. **The FM/NÉBIH/OGYÉI/Campden BRI/MHKSZ frozen and canned composition database** and the Rodler 2008 edition.
6. **GS1 Hungary product master data** is a likely licensed source of EAN-keyed nutrition. NOT checked; the web-search budget was exhausted.
7. Robots nuance: Sobors *invites* AI retrieval bots, and Index blocks them. This matters if the app ever uses LLM web retrieval at runtime.
