# Alternative grocery price sources for Budapest (scrape / partner / buy)

Stream: `alt-price-sources` · Research date: 2026-10-12 · Author: research sub-agent

Labels used: **VERIFIED** (read on the source on 2026-10-12, URL given) · **COMPUTED** (derived from data I pulled; method given) · **ESTIMATE** (my reasoning) · **SNIPPET** (seen only via a search-engine summary; the page itself could not be read).

Quotes of terms are kept short (key phrase only) and paraphrased otherwise; section numbers are given so the founder or a lawyer can read the full clause.

Data files in this folder:
- `data/sources_matrix_2026-10-12.csv`: one row per source with coverage, freshness, terms, access, risk, partnership chance and rank.
- `data/auchan_online_vs_gvh_2026-10-12.csv`: EAN-matched comparison of Auchan webshop prices against GVH Árfigyelő Auchan prices.
- `data/ksh_ara0044_latest_avg_prices.csv`: KSH monthly national average prices (175 items, latest month 2026-09).
- Raw downloads are in `downloads/` (untrusted data). Scripts are in `scripts/`.

---

## 0. Bottom line

1. No alternative source beats the **GVH Árfigyelő** for an MVP. It is the only source that is store-level, multi-chain, daily, geolocated and not blocked by contract or technology. Every alternative is one of these:
   - contractually off-limits: Kifli ÁSZF 3(c), Wolt 12.7–12.8, foodora 12.1, the Auchan site terms, Árnéni 8;
   - technically protected: Tesco is behind Akamai, spar.hu behind a Cloudflare challenge, metro.hu returns 403;
   - promo-only: leaflets and the discounters' own sites;
   - too coarse: KSH national averages, NIQ/YouGov panels;
   - not yet usable: NAV e-nyugta, Open Prices.
2. **New load-bearing risk: GVH has acted before against an app that used Árfigyelő data.** In August 2023 GVH said it had not permitted a look-alike app to use Árfigyelő data or design elements. It took civil and criminal steps and asked Google and Apple to remove the app (VERIFIED in the Telex and Pénzcentrum reports of 2023-08-05). The 2025 ÁFF says non-archived data are public (XII.4), and in 2026 Árnéni and an Apify actor openly reuse the data. Still, **get written confirmation from GVH before launch**, and never imitate GVH branding.
3. **Fill gaps with official, low-risk data** before any scraping:
   - KSH monthly national average prices (STADAT 1.2.1.8, `ara0044`), for items GVH lacks such as mushrooms, dry beans and walnuts. Label these clearly as national averages.
   - Deep links to each chain's official weekly leaflet, for promotions and for chains GVH does not cover (CBA, Príma, Coop).
4. **Partnerships worth pursuing later**:
   - Kifli/Rohlik: tech-forward. It runs a public MCP server and its own recipes and meal planning, and is a natural "send this week's basket to Kifli" partner.
   - Roksh: runs Aldi's online shop (shop.aldi.hu, about 3,300 products) and has a B2B backend.
   - Groby: a small Budapest online grocer; no anti-scraping clause found in its ÁSZF.
   - Wolt affiliate programme via TradeDoubler (VERIFIED). It allows link-outs only, never data.
5. **Do not buy scraped data** from Apify actors or Actowiz-type vendors. The Tesco HU actor explicitly needs a Bright Data "Web Unlocker" to get past Akamai. That is circumvention of a technical measure, and it inherits each site's ToS breach.
6. **Crowdsourcing is a later-stage moat, not an MVP source.** NAV e-nyugta is real infrastructure: the customer app can export and import receipts on the user's instruction, and receipts are itemised. But as of 2026-09-04 only NAV's own customer app and four e-cash-register models are licensed. Online cash registers remain allowed until 2028-07-01, so grocery-chain coverage is negligible before then (ESTIMATE).

---

## 1. Corrections and additions to the "already established" facts

| Established claim | Finding today | Label |
|---|---|---|
| "robots.txt of bevasarlas.tesco.hu doesn't block product pages" | With an honest bot User-Agent, **every Tesco host returns HTTP 403 "Access Denied" (Akamai edge)**. That includes `bevasarlas.tesco.hu/robots.txt`, `tesco.hu/`, the help/ÁSZF pages and the `digitalcontent.api.tesco.com` T&C PDF. WebFetch also gets 403. robots.txt is moot: the CDN blocks bots. A third-party Apify actor confirms Tesco HU sits behind Akamai Bot Manager and needs an "unlocker" for category crawls. | VERIFIED (curl 2026-10-12) + vendor page https://apify.com/studio-amba/tesco-hu-scraper |
| "robots.txt of spar.hu doesn't block" | True: robots.txt is permissive (it disallows only cart, checkout and account pages). But the spar.hu homepage returns a **Cloudflare "Just a moment…" challenge (403)** to a bot UA. More importantly, **the SPAR online shop no longer exists**: `https://www.spar.hu/onlineshop` redirects to `/wolt`, and SPAR moved its entire online shop to Wolt on 2025-03-21. | VERIFIED (curl) + https://xpatloop.com/channels/2025/03/spar-to-use-wolt-and-cut-staff-in-hungary-after-online-shop-restructuring.html |
| "robots.txt of kifli.hu doesn't block product pages" | True (only `/regal/*` is disallowed for `*`, and ClaudeBot/GPTBot are explicitly allowed). But **Kifli's ÁSZF 3(c) prohibits automated or manual copying or tracking of shop content without prior written permission** (see §2.1). robots.txt is not a licence. | VERIFIED https://www.kifli.hu/robots.txt and the ÁSZF PDF |
| "robots.txt of lidl.hu doesn't block" | True. But lidl.hu does not show regular prices anyway (see §4). | VERIFIED |
| Online FMCG ranking: #3 Wolt "sells SPAR" | Correct, and wider: **Auchan (all stores since 2025-04-01) and Tesco are also on Wolt**. Tesco moved all home delivery to Dodo and Wolt. | VERIFIED https://telex.hu/gazdasag/2025/04/01/tesco-auchan-spar-wolt-dodo-kiszallitas-kiszervezes |
| GVH data are "public" (ÁFF XII.4) | Correct for the 2025 ÁFF, but see the 2023 precedent: GVH took legal action against an unauthorised look-alike app that used Árfigyelő data. | VERIFIED https://telex.hu/belfold/2023/08/05/gvh-figyelmeztetes-kalozapplikacio-arfigyelo |

---

## 2. Online shops with priced catalogues serving Budapest

### 2.1 Kifli.hu (Rohlik Group)
- **Catalogue size: "Összesen több mint 19 000 termék"** (VERIFIED, kifli.hu homepage copy, 2026-10-12). Online-only, with several warehouses ("Budapest Kelet" shown).
- **Prices vs in-store:** not applicable (online-only). Prices **vary by delivery address and warehouse** (ÁSZF 3: availability and displayed prices may differ depending on the address and the serving warehouse). VERIFIED.
- **API:** no public data API. **Kifli runs a public MCP server** (`https://mcp.kifli.hu/mcp`, docs at https://www.kifli.hu/mcp-docs). It supports product search, price comparison, cart, recipes and shopping lists, but it is **consumer OAuth: an active Kifli account is required** ("Aktív Kifli fiókra van szükséged"). It is a personal-assistant integration, not a B2B data feed. VERIFIED.
- **Affiliate:** only a customer referral programme (https://www.kifli.hu/oldal/kifli-ajanloprogram). No publisher affiliate programme was found. Rohlik sells retail media to brands (https://ads.rohlik.group/). VERIFIED / not found.
- **ToS** (ÁSZF effective **2026-09-26**, PDF https://cdn-kifli.s3.eu-central-1.amazonaws.com/files/terms/260926_A%CC%81ltala%CC%81nos+Szerzo%CC%8Bde%CC%81si+Felte%CC%81telek_final_HU.pdf):
  - **§3 (c):** the buyer undertakes not to obtain, track or copy shop content or information "sem automatizált eszközökkel, sem manuálisan" (neither by automated means nor manually) without Kifli's prior written permission.
  - **§3 (d):** no circumventing access-restriction measures, and nothing that causes undue load.
  - **§11 Szellemi tulajdonjogok:** Kifli claims all rights in the website and its content, explicitly including "az azon található adatbázisokkal" (the databases on it), and reserves full damages.
  - Note: §3 is phrased as an obligation of the "Vásárló" (customer). Whether it binds a non-customer crawler is a legal question. §11's database claim applies regardless. VERIFIED.
- **Partnership chance: medium** (ESTIMATE). Rohlik is unusually open to AI and agent integrations (MCP, ChatGPT app, "Maia" assistant). It also already has recipes and meal planning in-app, so it is partly a competitor. The best pitch is a basket hand-off ("order this week's plan at Kifli") with a referral or affiliate fee, not a price feed.
- Árnéni states it uses "publicly available price info from online grocers such as Kifli.hu" (https://arneni.com/terms.html §3). That shows a competitor is taking the risk; it does not make it allowed.

### 2.2 Tesco online (bevasarlas.tesco.hu, "Tesco Otthonról")
- **Access:** HTTP 403 (Akamai) for all hosts with a bot UA, so the terms could not be read directly (VERIFIED).
- **Terms (SNIPPET):** a "Tesco Otthonról ÁSZF" on tesco.hu/help, reportedly published 2025-10-16. It uses the concept of a **"kiszolgáló áruház"** (serving store, assigned by delivery address or pickup point), so online prices are tied to that store. That Tesco online prices equal the serving store's shelf prices is an **ESTIMATE**, not verified.
  - The older Tesco web-shop ÁSZF PDF (2017 and 2022 versions on tesco.hu/img/…) has a section "Szellemi tulajdonjogok védelme, a weboldal használata". It restricts users to own use, and copying, downloading or distributing beyond own needs is prohibited (SNIPPET; section number not readable).
- **Catalogue:** about 14,000 products in 2020 (SNIPPET, https://www.penzcentrum.hu/vasarlas/20200507/itt-a-tesco-bejelentese-3-uj-magyar-telepulesen-indul-el-az-online-bevasarlas-1094876). Since 2024–25, delivery is outsourced to Dodo and Wolt (VERIFIED, Telex 2025-04-01).
- **API, feed or affiliate:** none found.
- **Verdict:** not an option. Tesco prices are already in GVH.

### 2.3 Auchan online (auchan.hu/shop)
- **Operator** named in the site terms: "MH Magyarország Kft. ("Auchan")". Warehouses: Budakalász, Central, Soroksár (VERIFIED from the site payload).
- **Catalogue: 53,034 product URLs** in 3 product sitemaps, including non-food (COMPUTED: `auchan.hu/sitemap_index.xml`, then `product-sitemap-0..2.xml`).
- **Prices vs in-store:**
  - The site UI string reads **"A feltüntetett ár Online rendelés esetén érvényes! Egyes termékek ára eltérhet az áruházi áraktól!"** (VERIFIED in the page source).
  - The ÁSZF also says online discounts may differ from the traditional store prices and discounts.
  - **My EAN-matched check of 5 packaged items against GVH Auchan prices: 4 identical, 1 higher online** (Kalifa lencse 500 g: online 609 Ft vs GVH NORMAL 599 Ft, DISCOUNTED 499 Ft). For a fresh chicken-breast-fillet SKU, the online unit price was 2,197 Ft/kg vs 1,967–1,973 Ft/kg for comparable (different-SKU) in-store items in GVH, about 11% higher (COMPUTED; `data/auchan_online_vs_gvh_2026-10-12.csv`). Small sample, so treat it as indicative.
- **Technical:** product pages carry schema.org JSON-LD (`offers.price`) and a Nuxt payload with `eanCode`, gross price and price per kg. They are easy to parse, but each page is about 2 MB (VERIFIED), so a full crawl would be heavy (ESTIMATE: tens of GB).
- **ToS:** "Felhasználási feltételek" (https://auchan.hu/felhasznalasi-feltetelek, no section numbers):
  - it permits only **"személyes, nem kereskedelmi célú"** (personal, non-commercial) study and download of site materials;
  - and prohibits copying or republishing the site in whole or part without prior written permission ("Az Auchan előzetes írásbeli engedélye nélkül tilos a weboldal egészét, vagy részeit… sokszorosítani, másolni, újraközölni").
  - VERIFIED.
- **Also on Wolt:** all Auchan stores since 2025-04-01, about 3,200 items via Wolt (4,500 from Budakalász). Auchan's own webshop remains (VERIFIED, Telex 2025-04-01).
- **API, feed or affiliate:** none found. **Verdict:** Auchan in-store prices are already in GVH. Scraping the webshop would add online-only prices against the site terms. Not for the MVP.

### 2.4 SPAR online shop and SPAR on Wolt
- **The SPAR own online shop is closed.** It moved to Wolt on 2025-03-21; `spar.hu/onlineshop` now redirects to `spar.hu/wolt` (VERIFIED by curl redirect; xpatloop 2025-03).
- **Coverage on Wolt:** 73 SPAR/INTERSPAR stores in 40 towns. Wolt's Hungary CEO said orders are fulfilled "a boltokban megszokott árakon" (at the usual store prices) (VERIFIED, quote in https://www.penzcentrum.hu/vasarlas/20250115/ezek-azok-a-termekek-amiert-mar-nem-mozdulunk-meg-ebbol-rendelunk-a-legtobbet-hazhoz-1173096). About 10,000 SPAR items on Wolt (VERIFIED, https://www.esmmagazine.com/retail/in-conversation-wolt-and-spar-hungary-executives-talk-about-their-strategic-partnership-286776, 2025-04-16).
- **Wolt ÁSZF (Hungary)** (https://explore.wolt.com/hu/hun/terms; VERIFIED):
  - **12.7 (vi):** no collecting, using, copying or passing on any information learned via the service without Wolt's consent.
  - **12.7 (vii):** "nem használhat botokat és egyéb automatizált módszereket" (may not use bots or other automated methods).
  - **12.7 (ix):** access only via interfaces Wolt explicitly provides.
  - **12.8:** commercial use of the service, including its content, is not allowed, and systematic mapping or copying by web robot or extraction software is "kifejezetten tilos" (expressly prohibited).
  - **11.1** claims database and catalogue rights.
  - **3.2:** retail product pricing is set at the order date. **5.6:** weight-based prices are estimates.
- **Affiliate:** **Wolt Hungary runs an affiliate programme via TradeDoubler** (VERIFIED https://explore.wolt.com/en/hun/affiliates). It pays for traffic and orders only; it gives no data rights.
- **Wolt developer APIs** (developer.wolt.com, restaurant-api.wolt.com) are merchant-side integrations, not consumer catalogue data (VERIFIED links on the Wolt page; scope ESTIMATE).
- **Verdict:** no data source. SPAR in-store prices are already in GVH. Wolt can be an affiliate link-out.

### 2.5 Wolt Market (own dark stores)
- Budapest dark stores (e.g. "Wolt Market Lehel" listed on the Wolt Budapest page; VERIFIED). Launch range was "more than 2,500 products" in 2021 (SNIPPET). It added 600 products and rebranded in March 2026 (VERIFIED, https://xpatloop.com/channels/2026/03/grocery-delivery-selection-widens-in-hungary-as-wolt-market-rebrands-and-expands.html). It operates 24/7 with 30–40 minute delivery.
- Same Wolt ÁSZF applies, so no scraping. **Verdict:** out.

### 2.6 foodora (still in Hungary in 2026)
- **Active:** current ÁSZF "Hatályos: 2026.02.03." (VERIFIED https://www.foodora.hu/contents/terms-and-conditions.htm, which links to a Google Drive PDF, "DHH FOGYASZTÓI ÁSZF v2.7"). It runs its own "foodora market" (Delivery Hero Dmart).
- **Penny on foodora:** nationwide since November 2024, in 43 towns; "az árak változatlanul a boltokban megszokott szinten maradnak" (prices stay at store level) (VERIFIED, https://www.penzcentrum.hu/vasarlas/20241119/orszagosan-is-elerhetove-valt-az-online-bevasarlas-a-penny-nel-1159497).
- **ÁSZF 1.8:** the partner's range and **prices on the platform may differ from the partner's store or own online channels**, and may differ between the partner's units.
- **ÁSZF 12.1:** any use of platform content requires the provider's "előzetes írásbeli engedélyével" (prior written permission). **12.2** threatens criminal sanctions as well. VERIFIED.
- robots.txt allows most paths for `*`; `GPTBot` is disallowed.
- **API or affiliate:** none found. **Verdict:** out.

### 2.7 CBA / Príma / Coop
- **CBA (cba.hu) and Príma (prima.hu):** WordPress sites. The CBA product sitemap has only **17 URLs** (a handful of loyalty or non-food items with prices) (COMPUTED). Weekly leaflet as a 3D flipbook: `https://www.cba.hu/3d-flip-book/<oktober-8-14>/` (VERIFIED). **No full online catalogue.** The old CBA web shop (Csepel) and the "Príma Express" on Wolt (2020) are historical (SNIPPET). Not in GVH: franchise members are below the HUF 100 bn threshold (ESTIMATE, consistent with the ÁFF threshold).
- **Coop:**
  - `https://www.coop.hu/akcios-termekek/` lists the national promo items in HTML with regular and promo price and unit price. Example (VERIFIED 2026-10-12): "Coop „B" minőségű rizs 1 kg 629 → 499 Ft", valid 2026-10-08 to 10-14.
  - `cooponline.hu` is a **Jászberény-based long-life-goods parcel shop** ("Tartós élelmiszerek házhozszállítása", nationwide). It is not a Budapest fresh-grocery catalogue (VERIFIED). Its ÁSZF page has no scraping clause (VERIFIED by grep).
- **Verdict:** only promo pages and leaflets exist. Use deep links in the MVP; possibly user-reported prices later.

### 2.8 Groby (GRoby Online Szupermarket, G'Roby Netshop Kft., 1186 Budapest)
- **Active:** it delivers to Budapest and the surrounding area; free delivery from 29,999 Ft (VERIFIED homepage meta).
- **Catalogue:** about **7,883 product URLs** in the sitemap (COMPUTED: `https://www.groby.hu/sitemap.xml`, URLs matching `/termekek/<id>-…`).
- **ÁSZF** (https://www.groby.hu/cikk/aszf): **no anti-scraping or IP clause found** (VERIFIED by full-text grep). robots.txt is permissive.
- **API or affiliate:** none found.
- **Verdict:** lowest-friction e-grocer for a later **partnership** (small, independent, Budapest-only) (ESTIMATE). It is low priority, because its prices are online-grocer prices and not chain store prices.

### 2.9 Metro
- metro.hu returns **403** to a bot UA, so the terms could not be read (VERIFIED). Metro is B2B cash & carry and needs a card; consumer relevance is low (SNIPPET, older press). **Out.**

### 2.10 Roksh / Aldi online (shop.aldi.hu)
- `shop.aldi.hu` is a **ROKSH white-label shop** (page title "ROKSH élelmiszer házhozszállítás"; VERIFIED). It has **about 3,300 products** and reaches 3.2 million customers in 107 towns (VERIFIED, https://www.esmmagazine.com/retail/aldi-boosts-online-grocery-in-hungary-expands-european-reach-for-golden-power-298299, 2025-10-27).
- The Roksh JS bundle references `roksh-backend-b2b.roksh.com`. Roksh also runs Hofer in Austria and Switzerland (VERIFIED host strings). It is an Angular SPA, so its terms are not readable without JS (not checked). robots.txt lists only Googlebot.
- **Partnership chance: medium** (ESTIMATE). Roksh is a Hungarian B2B-minded company already handling Aldi catalogue data. Whether Aldi would allow onward use of prices is unknown.

### 2.11 Drugstores (dm, Rossmann, Müller)
- Full online shops exist (Árnéni links to `dm.hu/search` and `shop.rossmann.hu`). They are already in GVH and largely non-food, so they are not assessed further.

---

## 3. Weekly leaflets (akciós újság)

### 3.1 Where each chain publishes (VERIFIED 2026-10-12 unless marked)

| Chain | Landing page | Format and URL pattern |
|---|---|---|
| Aldi | https://www.aldi.hu/online-akcios-ujsag | **Publitas** viewer on `szorolap.aldi.hu/aldi_online_akcios_ujsag_<YYYY>_kw<WW>`, plus `aldi_kozepso_sor_<YYYY>_kw<WW>` (non-food). Publitas offers "PDF letöltése" and product hotspots. Offers are also HTML at `aldi.hu/ajanlatok/<YYYY-MM-DD>` with schema.org prices on `/termek/…` pages. |
| Lidl | https://www.lidl.hu/c/szorolap/s10013623 | Schwarz viewer `lidl.hu/l/hu/ujsag/akcios-ujsag-<WW>-het-<YYYY>/ar/0`, plus a non-food variant and **store-specific regional leaflets** (e.g. `regionalis-akciok-debrecen-monostorpalyi-ut-42het`). This is evidence of local price differences. |
| Penny | https://www.penny.hu/reklamujsag | `files.rewe.co.at/PennyIntLeaflet/HU/<YYYYWW>/`. Promo items are also HTML on `penny.hu/products/<slug>-<id>` (about **695** product URLs in the sitemap, COMPUTED; each shows validity dates and promo and regular price). |
| Auchan | auchan.hu footer | `reklamujsag.auchan.hu/online-katalogusok/<YYYY>/tr<WW>/<YYYY-MM-DD-DD>-<slug>/`. The root of `reklamujsag.auchan.hu/` returns 404. |
| SPAR | spar.hu (Cloudflare-challenged for bots) | Historical PDF pattern `spar.hu/content/dam/sparhuwebsite/_flyers/<YYYY>/<MMDD>/<name>.pdf` (SNIPPET from search; the 2025 example now returns 404). |
| Tesco | tesco.hu (Akamai 403) | Not readable for bots. |
| CBA / Príma | https://www.cba.hu/3d-flip-book/ | WordPress "3D FlipBook" plugin, `cba.hu/3d-flip-book/<oktober-8-14>/`. |
| Coop | https://www.coop.hu/akcios-termekek/ | HTML list of promo items with prices and validity (see §2.7). |

### 3.2 Aggregators
- **Kimbino** (https://www.kimbino.hu). Operator **Kimbino Green s.r.o., Žilina, Slovakia** (VERIFIED contact page).
  - robots.txt **disallows `/api/`, `/_api/v2/leaflet/deals-brochures/*` and `/offers/*`**.
  - Terms (PDF linked as "A weboldal használati feltételei"), **section II.7**: content may be copyright-protected, platform databases are protected by "a special right of the database procurer", and use is only "in compliance with their purpose".
  - "B2B zóna" (`b2b.kimbino.net`) is a login app for retailers' campaigns and coupons, i.e. advertising, not data licensing.
  - **No public API or data licensing found.**
- **Akciós-Újság.hu** (https://akcios-ujsag.hu). Operator **Central Médiacsoport Zrt.**
  - Felhasználási feltételek: the operator holds copyright and **database-maker rights**; beyond reading and personal, non-commercial saving or printing, nothing may be used without prior written permission. Content takeover is limited to title plus lead with a link.
  - VERIFIED https://akcios-ujsag.hu/felhasznalasi-feltetelek/
- **Others seen** (not assessed in depth): Tiendeo (tiendeo.hu), Ajanlatok.hu, GeoBuyer.hu, Akciókereső.hu (launched 2024, more than 150 stores per its own claim), Sokakció.hu (claims product search across leaflets), Akció Központ, akcios-ujsag.net (SNIPPET). Kimbino and Sokakció also extract products from leaflets.
- **Licensing reality** (ESTIMATE): aggregators earn from retailer ad placements and none sells data. A data deal would be bespoke. Since prices are facts but leaflet images and layouts are copyright works, the cleaner route is first-party: link to the chain's own viewer, or extract only facts (product, price, validity) from the chain's own leaflet under legal advice.

### 3.3 How Árnéni processes leaflets
- Árnéni's "Szórólapok" page states: "Az adatokat az **Arvago saját AI vision technológiája** nyerte ki a szórólapokból. Az árak és terméknevek pontatlanok lehetnek." (VERIFIED, https://arneni.com/szorolapok.html). In English: the data were extracted from the leaflets by Arvago's own AI vision technology, and prices and product names may be inaccurate.
  - Chains covered: Müller, dm, Aldi, Lidl, Penny, Tesco, Spar, Rossmann, Auchan.
  - Deals are served from `scripts/flyer_deals.json`. I did not fetch it, because robots.txt disallows `*.json`.
- **Terms §3 data sources:** GVH Árfigyelő; "Kiskereskedelmi weboldalak és promóciós anyagok"; and online grocers "mint például a Kifli.hu". **§6:** some links are affiliate links. **§8:** users may not scrape or redistribute substantial parts of the database, under 96/9/EC. The operator serves the EU from the UK (privacy section). VERIFIED https://arneni.com/terms.html
- Árnéni deep-links product names into each chain's search: `auchan.hu/shop/search?q[]=…`, `bevasarlas.tesco.hu/groceries/hu-HU/search?query=…`, `shop.aldi.hu/kinalat/kereses/…`, `penny.hu/kereso/…`, `dm.hu/search?query=…`, `shop.rossmann.hu/talalatok?q=…`, and still `spar.hu/onlineshop/search?q=…`, which now redirects to Wolt (VERIFIED in page source).
- "Ártrendek" page: "A történelmi áradatok még gyűlnek" (historical price data still being collected), so the product is young (BETA). No B2B or data offering by Arvago was found.

---

## 4. Do the discounters publish full regular price lists outside GVH?

**Short answer: no.** All three publish promo prices; none publishes its full regular-price range on its own website (VERIFIED for the samples below). The partial exception is Aldi's Roksh-run online shop (about 3,300 products), whose regular-price parity with stores is not verified.

- **Aldi** (aldi.hu):
  - The product sitemap holds **853 product URLs**, with schema.org `offers.price` (COMPUTED).
  - **Only 1 of 22 GVH Aldi staples** (Húsmester csirkemellfilé, id 320859, **1,979 Ft on both aldi.hu and GVH**) appears in that sitemap (COMPUTED by matching GVH `aldi-<id>` to the trailing article number in aldi.hu URLs).
  - The category page "Olaj és ecet" lists **1 product** (a vinegar), so the site is not a full price list (VERIFIED).
  - The "Hatósági árréscsökkentés" information page holds only a link to kormany.hu, with no product list (VERIFIED).
  - Felhasználási feltételek (effective 2022-04-20) forbid "szoftverek vagy egyéb szkriptek" (software or other scripts) that harm or may harm the site (VERIFIED).
  - The Aldi online shop is shop.aldi.hu, run by Roksh (see §2.10).
- **Lidl** (lidl.hu):
  - The product sitemap holds **1,962 product URLs** (COMPUTED).
  - The page for a regular item (Pilos tejföl, p10024531) has **no price value**: the Nuxt `price` object has currency fields only, `eans` is empty, `regionsPrices` is empty, and the JSON-LD offer is `availability: InStoreOnly` with no price (VERIFIED).
  - Prices appear only for weekly offers and leaflets. Lidl Plus app coupons and loyalty prices are app-only.
- **Penny** (penny.hu):
  - Category and product pages show **only items with validity dates** ("Cs 2026.10.08-tól Sze 2026.10.14-ig"), giving promo and regular price. Example: Magyar tejföl 330 g, 399 Ft (regular 449 Ft) (VERIFIED).
  - The sitemap holds about 695 product URLs (COMPUTED).
  - Jogi nyilatkozat: no scraping clause found; it notes that the store and webshop offers are separate offers (VERIFIED).
  - Penny's full range is orderable via foodora at "store-level" prices (VERIFIED claim, 2024), but foodora ÁSZF 12.1 forbids reuse.

---

## 5. Commercial data vendors

| Vendor | What they sell for Hungary | Fit for this app | Pricing visibility |
|---|---|---|---|
| **NielsenIQ (incl. former GfK retail)** | Retail measurement (sell-out, average prices) for manufacturers and retailers. GfK Hungária ran a "**Leaflet Monitor**" (it was reported in 2013: leaflet counts falling, especially at discounters; SNIPPET https://www.penzcentrum.hu/vasarlas/20130216/tovabb-csokken-az-akcios-ujsagok-szama-1035511). No current HU leaflet-monitor product page was found. | Poor. Category-level averages, not store-level shelf prices; restrictive licences. | Not public. ESTIMATE: tens of thousands of EUR per year. |
| **YouGov (bought GfK Consumer Panel Services, €315m, 2024)** | HU shopper panel of 4,000 households. In 2024 it partnered with **RetailZoom** for a "Retail Audit Total Market Read" (store-level, basket and loyalty data). Panels exclude some non-cooperating chains, e.g. some discounters (SNIPPET via https://business.yougov.com/content/50810-yougov-partners-with-retailzoom). | Poor (B2B FMCG analytics). | Not public. |
| **Actowiz Solutions** | Template pages for "Hungarian … grocery data scraping" and a Coop Hungary tracker. The same boilerplate is reused with different names. | Avoid: scraping-as-a-service inherits ToS and circumvention risk. | "From $500/mo" on one template (SNIPPET; vendor claim). |
| **Apify community actors** | `studio-amba/kifli-hu-scraper` (uses Kifli's internal API; $2 per 1,000 results); `studio-amba/tesco-hu-scraper` ($2 per 1,000 results; **category and full-catalogue runs need a Bright Data Web Unlocker key because Tesco HU is behind Akamai Bot Manager**); `blackfalcondata/tesco-scraper`; `mukedlii/arfigyelo-price-monitor` (wraps GVH Árfigyelő; about 2,000 food products; 2 users). | Avoid. The Tesco route is circumvention of a technical measure; the Kifli route breaches ÁSZF 3(c). | VERIFIED listing pages https://apify.com/studio-amba/tesco-hu-scraper and https://apify.com/mukedlii/arfigyelo-price-monitor |
| **Árnéni / Arvago** | No B2B data offer found. Its own terms forbid scraping its database (§8). | — | — |
| **Leaflet aggregators** (Kimbino, akcios-ujsag.hu) | Advertising for retailers only. | — | — |

---

## 6. Crowdsourced options

### 6.1 NAV e-nyugta (digital receipt), the most interesting medium-term channel
- **Legal basis:** 8/2025. (III. 31.) NGM rendelet on e-cash registers and e-receipts (listed on https://nav.gov.hu/ado/enyugta/forgalmazoknak). VERIFIED.
- **How it works:**
  - The customer shows a QR code from a "vevői alkalmazás" (customer app). The e-cash register issues the e-receipt into NAV's "nyugtatár".
  - The app downloads it using a search key, **with no user identification**.
  - **Mandatory app functions include "E-nyugta és más bizonylatok (bizonylatadatok) exportálása és importálása a vevő utasítására"** (export and import of receipts on the customer's instruction). Automatic forwarding to other apps is **not** allowed.
  - Multiple customer apps can be used in parallel. NAV publishes the list of licensed customer apps.
  - VERIFIED https://nav.gov.hu/ado/enyugta/kerdesek-es-valaszok/vevoi-alkalmazas
- **Licences as of 2026-09-04** (VERIFIED https://nav.gov.hu/ado/enyugta/forgalmazasi-engedelyek/forgalmazasi-engedelyek):
  - E-cash registers: C001 and C002 NAV ePénztárgép (cloud, Android and iOS, Pillér Nonprofit Kft.); B001 Fiscat Super eFP (the **only hardware** model, licensed 2026-08-06); C003 Számlázz.hu ePénztárgép (cloud, 2026-08-31).
  - Customer apps: **only P001 and P002, "NAV eNyugta" for Android and iOS.**
- **Timeline:**
  - Voluntary phase since 2025-07-01.
  - From 2026-09-01, businesses that issue paper or computer receipts must report receipt data. There is a sanction-free period until 2026-12-31 (SNIPPET: Billingo, RSM).
  - **Online cash registers remain usable until 2028-07-01**; after that, hardware e-cash registers are needed for register-obliged activities (SNIPPET: NAV via hellobiznisz.telekom.hu, accace, billingo).
- **Implication** (ESTIMATE): big grocery chains run online cash registers and have no reason to switch before 2028. Itemised e-receipts from Tesco, Lidl and others are therefore unlikely at scale in 2026–2027.
- **Later options:** (a) apply for a **customer-app distribution licence** (the procedure page exists under "Forgalmazóknak"), or (b) let users import receipts exported from the NAV eNyugta app, on their instruction. Both are privacy-friendly (no identity) and lawful by design. Each receipt carries **real paid prices per store**.
- **NAV online cash register data** (OPG): flows to NAV as tax data. There is no public or third-party access (ESTIMATE; tax secrecy under Art. 2017. évi CL. tv.). **Not accessible.**

### 6.2 Paper-receipt OCR
- Feasible today with no licence. Receipts carry abbreviated names (e.g. "MIZO TR CITROM-ÁFONYA ÉT 5X45G" style) and **no EAN**, so matching to products is noisy (ESTIMATE).
- Paper online-cash-register receipts have no consumer QR that resolves to an itemised receipt. None was found (searches returned nothing), unlike Serbia's fiscal QR.
- The KSH household budget survey app uses receipt photos, so the UX pattern exists in Hungary (SNIPPET: KSH HBS guide).

### 6.3 Open Prices (Open Food Facts)
- Global open price DB under **ODbL** (proof images CC-BY-SA 4.0), with API and daily dumps (SNIPPET: data.gouv.fr and openfoodfacts.github.io guides).
- **Hungary: only 37 HUF price records in total** (COMPUTED: `GET https://prices.openfoodfacts.org/api/v1/prices?currency=HUF&size=5` returned `total: 37`; the latest is 2026-09-29, Spar Budapest).
- It also accepts **GDPR-request data**: users export their loyalty-card purchase history from retailers (GDPR Art. 15/20). The same approach could work with Lidl Plus, Tesco Clubcard or SPAR card histories, user-initiated (ESTIMATE; not tested for Hungarian chains).
- **Caveat:** ODbL share-alike means mixing it into a proprietary DB has obligations.

### 6.4 User-reported prices
- Necessary for chains outside GVH (CBA, Príma, Coop, markets such as Fény utcai or Lehel piac) and for items GVH does not cover.
- Needs moderation, decay rules and photo proof (ESTIMATE).
- The cold-start problem is severe, so it only works after there is a user base (ESTIMATE).

---

## 7. Official statistics as a gap filler: KSH

- **STADAT 1.2.1.8 "Egyes termékek és szolgáltatások fogyasztói átlagára (nyers adatok), havonta"** (https://www.ksh.hu/stadat_files/ara/hu/ara0044.html). It covers **175 items, about 86 of them food**, monthly from 2017. The **latest month is 2026-09**, last updated 2026-10-07 (VERIFIED / COMPUTED, `data/ksh_ara0044_latest_avg_prices.csv`).
- **Covers some GVH gaps:**
  - Gomba: 1,900 Ft/kg
  - Szárazbab: 1,540 Ft/kg
  - Tisztított dió: 6,180 Ft/kg
  - Fűszerpaprika: 8,840 Ft/kg-equivalent
  - All figures are September 2026 national averages (COMPUTED).
- **Does not cover** zucchini, spinach, oats, chickpeas or salmon (COMPUTED by keyword search).
- **Reuse:** KSH terms reportedly grant free, non-exclusive use with attribution ("Forrás: Központi Statisztikai Hivatal"). Resale of the content itself is not allowed, but an independent work built on it may be used commercially (SNIPPET from KSH terms PDFs; **confirm with KSH**).
- **Use:** recipe-cost estimates labelled "országos átlagár (KSH)", never as a store price.

---

## 8. Ranking

### MVP (launch in Budapest, 2026–27)
1. **GVH Árfigyelő API.** The backbone: store-level, geolocated, daily, 6 food chains. Action: written reuse confirmation from GVH, no GVH look-alike branding, and attribution.
2. **KSH ara0044 national averages.** Fallback for items missing from GVH, clearly labelled. Monthly.
3. **Official chain leaflets and promo pages as deep links, not extraction.** Covers promotions plus CBA, Príma and Coop. Zero data-rights risk.
4. **Affiliate or hand-off link-outs** (Wolt via TradeDoubler; Kifli if a deal is reached). For revenue, not price data.

### Later stage (after traction)
5. **Kifli/Rohlik partnership.** Basket hand-off with referral fee; possibly a sanctioned price or product feed for recipe ingredients that GVH lacks (Kifli's range is above 19,000 products).
6. **Roksh (Aldi online) and Groby partnerships.** Small partners, easier to sign.
7. **Leaflet fact extraction** (AI vision, like Árnéni) from the chains' own leaflets, after legal advice on copyright in the layout and images versus facts. Freshness is weekly.
8. **Crowdsourcing:** NAV e-nyugta import (and possibly a customer-app licence), paper-receipt OCR, user price reports, and contribution to and use of Open Prices. Coverage of chain receipts should become meaningful only around the 2028-07-01 online-cash-register phase-out (ESTIMATE).
9. **Not recommended at any stage:** scraping Tesco (Akamai), Wolt or foodora (explicit bans), or Kifli or Auchan without permission; buying scraped datasets; NIQ or YouGov panels for consumer features.

### Concrete data strategy
- **Ingest:** a nightly GVH snapshot (all food leaf categories, all stores, at polite rates), plus history accumulated by the app itself (GVH shows current data only).
- **Normalise:** EAN, chain-internal ids and variable-weight codes, mapped to a canonical ingredient (e.g. "csirkemellfilé, kg") with unit prices.
- **Fallback:** KSH average with a "becsült" (estimated) badge. Then "nincs adat", with a suggestion of a substitute ingredient that GVH covers.
- **Local:** filter stores by geolocation; flag `priceSameEverywhere=false` entries as "árak üzletenként eltérhetnek" (prices may vary by store).
- **Promotions:** show GVH DISCOUNTED and LOYALTY types, and link to the official leaflet for the week.
- **Legal hygiene:** written GVH confirmation; no retailer images or logos without consent (ÁFF XIV.2); attribution "Forrás: GVH Online Árfigyelő"; keep a terms-review log per source.

---

## 9. Open questions
- Will GVH confirm in writing that a commercial app may reuse Árfigyelő data via the API? Under what conditions (attribution, rate limits, images, branding)?
- The exact current Tesco Otthonról ÁSZF clauses (unreadable due to Akamai). A human with a browser should read it.
- Roksh's and Aldi's position on reuse of shop.aldi.hu prices; whether shop.aldi.hu regular prices equal store prices.
- Whether Kifli/Rohlik would offer a partner feed or affiliate deal for a meal-planning app (contact: pr@kifli.hu or the "Együttműködés" page).
- Confirmation of the KSH reuse terms from the current ksh.hu terms page.
- Whether any HU grocery chain plans hardware e-cash registers before 2028; whether NAV allows third-party customer apps to bulk-read user-exported receipts (requires reading the 8/2025 NGM rendelet in full on njt.hu).
- The size of price gaps between online and store for Auchan (only 5 EAN pairs checked) and for SPAR on Wolt (not checked, because Wolt ÁSZF 12.8 forbids automated checks).

---

## Sources (primary first)
- Kifli ÁSZF 2026-09-26: https://cdn-kifli.s3.eu-central-1.amazonaws.com/files/terms/260926_A%CC%81ltala%CC%81nos+Szerzo%CC%8Bde%CC%81si+Felte%CC%81telek_final_HU.pdf ; terms index https://www.kifli.hu/oldal/felhasznaloi-feltetelek ; MCP https://www.kifli.hu/mcp-docs ; robots https://www.kifli.hu/robots.txt
- Auchan: https://auchan.hu/felhasznalasi-feltetelek ; https://auchan.hu/altalanos-szerzodesi-feltetelek ; https://auchan.hu/sitemap_index.xml
- Wolt HU terms: https://explore.wolt.com/hu/hun/terms ; affiliates: https://explore.wolt.com/en/hun/affiliates
- foodora: https://www.foodora.hu/contents/terms-and-conditions.htm (current ÁSZF Google Drive PDF id 1Zu78O10Bpi49mB5wr7lHLgbI_SORn_GY)
- Groby ÁSZF: https://www.groby.hu/cikk/aszf ; sitemap https://www.groby.hu/sitemap.xml
- Coop: https://www.coop.hu/akcios-termekek/ ; https://cooponline.hu/aszf/
- CBA: https://www.cba.hu/product-sitemap.xml ; https://www.cba.hu/3d-flip-book/oktober-8-14/
- Aldi: https://www.aldi.hu/sitemap_products.xml ; https://www.aldi.hu/customer-services/felhasznalasi-feltetelek ; https://www.aldi.hu/online-akcios-ujsag ; https://shop.aldi.hu/
- Lidl: https://www.lidl.hu/static/sitemap.xml ; https://www.lidl.hu/p/pilos-tejfol/p10024531 ; https://www.lidl.hu/c/szorolap/s10013623
- Penny: https://www.penny.hu/reklamujsag ; https://www.penny.hu/products/magyar-tejfoel-8620962 ; https://www.penny.hu/joginyilatkozat
- Árnéni: https://arneni.com/terms.html ; https://arneni.com/szorolapok.html ; https://arneni.com/araink.html
- Kimbino: https://www.kimbino.hu/kapcsolat/ ; terms PDF https://d34seexzbffcio.cloudfront.net/d1b5145766b899b9019ccdf005d1391167bc930a7ec03.pdf
- Akciós-Újság.hu: https://akcios-ujsag.hu/felhasznalasi-feltetelek/
- NAV e-nyugta: https://nav.gov.hu/ado/enyugta/kerdesek-es-valaszok/vevoi-alkalmazas ; https://nav.gov.hu/ado/enyugta/forgalmazasi-engedelyek/forgalmazasi-engedelyek ; https://nav.gov.hu/ado/enyugta/forgalmazoknak
- KSH: https://www.ksh.hu/stadat_files/ara/hu/ara0044.html
- Open Prices: https://prices.openfoodfacts.org/api/v1/prices?currency=HUF ; https://openfoodfacts.github.io/open-prices/guides/data/
- GVH 2023 action against the look-alike app: https://telex.hu/belfold/2023/08/05/gvh-figyelmeztetes-kalozapplikacio-arfigyelo ; https://www.penzcentrum.hu/vasarlas/20230805/fortelmes-csalasra-figyelmeztet-a-gvh-eszrevetlen-bukhatsz-csomo-penzt-ezen-az-appon-1139815/amp
- Press: Telex 2025-04-01 (Tesco/Auchan/SPAR on Wolt); xpatloop 2025-03 (SPAR to Wolt); Pénzcentrum 2025-01-15 (Wolt SPAR at store prices); Pénzcentrum 2024-11-19 (Penny on foodora); ESM 2025-04-16 (SPAR on Wolt, about 10k items); ESM 2025-10-27 (Aldi via Roksh, 3,300 items); xpatloop 2026-03 (Wolt Market rebrand).
- Vendors: https://apify.com/studio-amba/tesco-hu-scraper ; https://apify.com/studio-amba/kifli-hu-scraper ; https://apify.com/mukedlii/arfigyelo-price-monitor ; https://www.actowizsolutions.com/hungarian-market-grocery-data-scraping-services.php ; https://business.yougov.com/content/50810-yougov-partners-with-retailzoom
