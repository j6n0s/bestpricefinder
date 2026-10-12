# Legal & regulatory risk – meal-plan + local grocery price comparison app (Hungary)

Stream: `legal` · Research date: 2026-10-12 · Author: research subagent
**This is research, not legal advice. Before launch, have a Hungarian IT/IP lawyer review it.**

Labels: **VERIFIED** = read in a primary source (URL given) · **COMPUTED** = derived from data I pulled (method given) · **ESTIMATE/INFERENCE** = my reasoning.
Raw downloads are in `dl/` (untrusted data). Helper script: `scripts/html2txt.py`.

---

## 0. Bottom line (TL;DR)

1. **GVH Árfigyelő data is the legally strongest backbone.** Act L of 2025, §70 makes all non-archived Árfigyelő data **public** ("nyilvánosak"). Hungary's PSI/Open Data law (Act LXIII of 2012, as amended for Directive 2019/1024) gives a formal **right to request re-use**. GVH must answer within 20 working days, may charge at most marginal cost, may not discriminate or grant exclusivity, and **may not exercise the database-maker right**. Third-party IP (product photos, packaging, logos) is excluded. Risk: **LOW–MEDIUM**. The bigger risks are operational and political: the API is undocumented, and in 2023 GVH acted against an app that used Árfigyelő data "without permission".
2. **Scraping retailer sites is the risky part.** The terms of Kifli (clause 3(c), in force from 2026-09-26) and Aldi (clause 1.5) **expressly forbid** automated or commercial use. Tesco's terms forbid copying beyond own needs; Spar requires prior written consent. Tesco (Akamai) and Spar (Cloudflare) **block non-browser clients**, and getting around that raises Btk. 423 criminal exposure. Apple App Store guideline 5.2.2 demands "specific permission" under the third-party service's terms. Risk: **MEDIUM–HIGH**. Use partnerships or affiliate feeds instead.
3. **Location:** do the nearest-store calculation on the device, using the GVH store list (1,829 shops, 52 KB gzipped). Use foreground-only, approximate location after explicit consent. Hungarian Eht. 155(4) requires prior informed consent for any access to data on the device; its text has no "strictly necessary" carve-out. Offer manual postcode entry as a fallback. GVH's own map takes the same approach. Risk: **LOW** with this design.
4. **Claims and money:** a "cheapest at X" claim must be scoped and dated, for example "among the 9 chains reporting to GVH, daily price of [date], price used in ≥80% of the chain's stores". Affiliate commissions make the app **directly liable** under Fttv. 9(1) for misleading promotion. Paid placement must be labelled ("Reklám" / "Hirdetés" / "Szponzorált tartalom"). Ranking parameters must be disclosed (Fttv. 7(7)). "Healthy" recipe claims fall under Reg. 1924/2006; GVH published new guidance on this in June 2026.
5. **Politics:** the Árfigyelő now rests on an **ordinary statute** with **no sunset clause**. The 2022 war emergency ended on 2026-05-14. The new Tisza government has a two-thirds majority (sworn in 2026-05-09) and **has announced no change** as of 2026-10-08. GVH leadership is in open conflict with the new government. Repeal risk in the next 12 months: **LOW–MEDIUM** (estimate). Risk that the API changes or becomes unavailable: **MEDIUM–HIGH** (estimate).

---

## 1. GVH Árfigyelő – legal basis, publicity, re-use

### 1.1 Act L of 2025, Chapter V ("AZ ÁRFIGYELŐ RENDSZER MŰKÖDÉSE") – VERIFIED
Source: https://njt.jog.gov.hu/jogszabaly/2025-50-00-00 (time state 2026.10.01; local copy `dl/njt_2025_L.txt`)
- Full title: "az Ukrajna területén fennálló fegyveres konfliktusra tekintettel kihirdetett veszélyhelyzeti rendeletek törvényi szintre emeléséről". It lifts the emergency decrees, including 163/2023 Korm. rendelet, into a statute.
- Adopted by Parliament on 2025-06-11 and promulgated on 2025-06-19 (footnote 1). §124(1): in force on the 31st day after promulgation, which is **2025-07-20** (COMPUTED: 19 June + 31 days). This matches the effective date of the GVH visitor ÁFF.
- **Chapter V has no sunset clause.** Other chapters say "2026. december 31-ig" (e.g., §36, §73, §99, §108, §115, §119); Chapter V does not. No amendment footnotes appear in Ch. V as of the 2026-10-01 state. The 2026 amendments to Act L (2026. évi XXXV. tv. §23–24; 2026. évi XLIX. tv. §183) touch other chapters (X, 124/A, 86–87).
- §55: definitions. A "kereskedő" is a business with main activity TEÁOR'25 47.11 or 47.75. The "napi ár" is the lowest unit price and gross sale price publicly available to all consumers that day.
- §56: GVH runs a **public** price-monitoring system ("nyilvános árfigyelő rendszert") for competition-law enforcement and consumer protection.
- §57(1)–(2): records retailer name, every store's name and address, product identification data, price type, daily price, previous price and loyalty price, **per retailer and per store**.
- §57(3): prices cut because the product expires within 72 h are excluded.
- §57(4)–(6): changed data are **archived** the next day. **Archived data are accessible only** to named ministers, courts, NKFH/consumer authorities and KSH, and are deleted after 10 years.
- **§70 (key): "Az árfigyelő rendszer elektronikus nyilvántartás, az abban nyilvántartott, nem archivált adatok nyilvánosak. A Gazdasági Versenyhivatal biztosítja az árfigyelő rendszerhez való hozzáférést."**
- §59: mandatory reporting where consolidated net retail revenue > **HUF 100,000,000,000**. §61–65: voluntary joining is possible.
- §66(1): data must be sent daily, by the end of the day before the price applies. §66(5): **products sold for ≤1 month continuously need not be reported**, so short promotions and "special buys" are missing (coverage limit).
- §71(1)(c) + (4)(c): if the shelf price or loyalty price in a store is **higher** than the registered price, the consumer authority fines **HUF 50,000 per product**. Late or missing reporting costs HUF 3,000,000, or HUF 25,000 per product up to HUF 3 m. In effect, a registered GVH price is an enforceable ceiling. **This makes GVH-sourced prices legally robust to display.**
- §72: the minister sets categories by decree. §126(3): Ch. V serves compliance with the Services Directive 2006/123/EC.
- **Nothing in Ch. V regulates or limits third-party re-use, API access, or automated access.**

### 1.2 11/2023. (VI. 22.) GFM rendelet – VERIFIED
https://njt.jog.gov.hu/jogszabaly/2023-11-20-8P (latest time state 2025.05.31). It defines the categories and products (Annex 1) and the price types. Product image and file extension / image link are "other identification data" (Annex 2 b), as cited in ÁFF XIV.2. It was originally issued under 163/2023 and remains the operative decree, cited by the GVH ÁFF and GYIK (2025).

### 1.3 GVH documents – VERIFIED
- Visitor ÁFF (effective 2025-07-20): https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_latogato.pdf (`dl/gvh/`)
  - V.4: "A Szolgáltatást bárki jogosult igénybe venni." VI.1: acceptance by use (browsewrap).
  - XII.4: non-archived data are public. XII.6–8: GVH disclaims liability for accuracy, including for "nem rendeltetésszerű használat".
  - **XIV.1**: the system and website (structure, look, software, documentation) are under copyright.
  - **XIV.2**: retailers supply the product images. Trademarked brand names and contents may be used **only in line with the site's purpose ("tájékozódás, tájékoztatás")**; other uses need the rightholder's prior consent.
  - Operator: IdomSoft Zrt.
- Merchant ÁFF: https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_kereskedo.pdf. **XIV.2**: retailers warrant that they hold the IP rights in the data they supply (images, trademarks) **only to the extent needed for the Árfigyelő Act**. The image licence therefore runs to GVH's statutory purpose, not to third parties (INFERENCE). Ingestion interface: `api.arfigyelo.gvh.hu`.
- GYIK: https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf. Daily prices are public **only on the day they apply** and are archived the next day. The ranking uses the price applied in **80% of the retailer's stores**, so individual stores may be cheaper. "Az Árfigyelő rendszer honlapja nem minősül gazdasági reklámnak vagy ajánlatnak", and the site carries no information on product availability.
- Privacy notice: https://arfigyelo.gvh.hu/docs/adatkezelesi_tajekoztato_arfigyelo.pdf §3.2. The GVH map store-finder processes the visitor's GPS position **on consent (GDPR 6(1)(a))**, only to pick the nearest store. The visitor can still pick a store manually on the map. This is a useful benchmark for our location design.
- No robots.txt on arfigyelo.gvh.hu (the SPA returns index.html). No public API documentation, developer terms or open-data licence was found on arfigyelo.gvh.hu or gvh.hu/arfigyelo (searched 2026-10-12).
- GVH press, 2026-03-10: 140 categories, >5,000 products, 1,817 stores, 6 grocery + 3 drugstore chains, "folyamatos fejlesztés és bővítés alatt áll" (https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2026-os-sajtokozlemenyek/gvh-az-arfigyelo-is-kordaban-tartja-az-elelmiszerarakat). GVH press, 2026-09-28: "Az online Árfigyelő továbbra is hatékonyan pörgeti a piaci versenyt" (https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2026-os-sajtokozlemenyek/milliardos-megterules-a-magyar-csaladoknak-hatekonyan-es-eredmenyesen-mukodik-a-gvh-2026-ban-is).
- **COMPUTED (2026-10-12):** one GET of `https://arfigyelo.gvh.hu/api/shops` returned **1,829 shops** in 415,968 bytes of JSON (52,191 bytes gzipped). The fields are address, chainStoreUuid, city, location, openingTime, postalCode and uuid; there are no personal data. The full list fits on the device. Product images are served from `cdnarfigyeloprodweu.azureedge.net` (checked on category 14).

### 1.4 Precedent – GVH v. the "pirate Árfigyelő app" (Aug 2023) – VERIFIED (secondary, quoting GVH)
https://telex.hu/belfold/2023/08/05/gvh-figyelmeztetes-kalozapplikacio-arfigyelo ; https://hvg.hu/itthon/20230805_Egy_kaloz_arfigyelo_beelozte_az_igazit_mobilon_a_versenyhivatal_eljarast_indit ; https://www.hwsw.hu/hirek/66470/online-arfigyelo-app-store-play-aruhaz-alkalmazas-gvh.html
- GVH: "nem adott engedélyt az illegális alkalmazás létrehozójának az árfigyelő rendszer adatainak felhasználására és egyes arculati elemeinek használatára". GVH took civil and criminal steps, got the app removed from Google and Apple, and opened an ex officio proceeding for consumer deception. The app showed non-real prices and imitated GVH branding.
- **INFERENCE:** GVH sees itself as able to "permit" data use, and will act when an app imitates the GVH brand and shows wrong prices. The case does **not** show GVH acting against a clearly distinct third-party app that accurately re-uses the data. Árnéni openly uses GVH data, and I found no GVH action against it. Mitigation: no GVH look-alike branding, accurate attributed data, and ideally a written GVH permission or re-use agreement.
- No official GVH mobile app launch was found for 2025–2026.

### 1.5 Open Data / PSI law – 2012. évi LXIII. törvény a közadatok újrahasznosításáról – VERIFIED
https://njt.jog.gov.hu/jogszabaly/2012-63-00-00 (time state 2022.12.20). The closing provisions state that it serves compliance with **Directive (EU) 2019/1024**. It was amended by 2022. évi LXII. tv. (https://njt.jog.gov.hu/jogszabaly/2022-62-00-00).
- §4.4: "közadat" = public-interest data ("közérdekű adat") and data public on public-interest grounds ("közérdekből nyilvános adat") as defined in Infotv. Infotv. §3.6: "közérdekből nyilvános adat" is any data whose publicity a law orders (https://njt.jog.gov.hu/jogszabaly/2011-112-00-00). **Árfigyelő data made public by Act L §70 qualify (INFERENCE, strong).**
- §4.8: "újrahasznosítás" = use for commercial or non-commercial purposes outside the original public task.
- §3 b): content protected by **third parties' copyright or IP** cannot be made available for re-use, so product images and packaging are out. §3 c): data whose access is excluded or limited by law cannot be made available, so **archived** Árfigyelő data (Act L §57(5)) are out.
- **§3/A: a public body "nem gyakorolhatja ... az adatbázis előállítóját megillető jogokat"** when providing data for re-use. This transposes ODD Art. 1(6).
- §8: no arbitrary discrimination between re-users. §9: no exclusive arrangements.
- §10(3): a written request must contain an express re-use statement, the requester's identity and contact details, the exact data, the format and technical method, and the frequency for regular supply. §11(2): examined within 5 working days. §13: decision within **20 working days**, extendable once by 20. Outcomes are grant, partial grant, refusal with written reasons, or grant on further conditions, with a re-use agreement offered.
- §15(2): fee ≤ **marginal cost** of processing, provision and dissemination.
- §16(4b): APIs are mandatory only for high-value datasets. §9/A lists their categories (geospatial, earth observation, meteorological, statistics, companies, mobility); retail price data are not among them (INFERENCE).
- **§16/A(1): "dinamikus adatok" must be made available immediately after collection via APIs** (bulk download where relevant). §16/A(2) allows a proportionality fallback. §4.10 defines "dinamikus adat" as rapidly changing or quickly obsolete digital public data. **INFERENCE:** daily prices that expire every day plausibly qualify, which is a legal argument for asking GVH for a supported API.
- §17: a re-use agreement is required. Any conditions must serve the public interest, be objective, proportionate and non-discriminatory, and not restrict competition (§17(3)). If GVH published open general terms, no request would be needed (§17(6)); GVH has not.
- §18: court review within 10 days; the burden of proof is on the public body.
- §1(4)(b): the Act does not cover "a közérdekű és közérdekből nyilvános adatok terjesztése jogának gyakorlására". The right to **disseminate** public-interest data also follows from the **Fundamental Law, Art. VI(3)**: "Mindenkinek joga van ... a közérdekű adatok megismeréséhez és terjesztéséhez" (https://njt.jog.gov.hu/jogszabaly/2011-4301-02-00). INFERENCE: displaying already-public GVH prices is strongly defensible even without a formal agreement. The agreement mainly buys stability, Apple 5.2.2 evidence and API terms.

### 1.6 Political and regulatory status after the April 2026 election
- Act L 2025, Ch. V is an ordinary statute (not cardinal), so a simple majority can amend it. VERIFIED (no cardinality reference to Ch. V; §125 lists cardinal parts).
- **The war emergency ended on 2026-05-14.** VERIFIED: njt footnote 18 to Act L §124(4) says "A 22/2026. (V. 15.) ME határozat a) pontja alapján a hatálybalépés időpontja 2026. május 14." Confirmed by https://444.hu/2026/05/14/nyugi-van-megszunt-a-haborus-veszelyhelyzet and https://www.economx.hu/belfold/2026/05/14/hivatalos-megszunt-az-orosz-ukran-haboru-miatt-elrendelt-veszelyhelyzet/. Parliament then passed 2026. évi XIV. tv. (https://njt.jog.gov.hu/jogszabaly/2026-14-00-00), which I did not find touching the Árfigyelő. **The Árfigyelő was already in statute, so the end of the emergency did not affect it.**
- Election: Tisza won a two-thirds majority, **141 of 199 seats** per AP. Péter Magyar was sworn in as PM on **2026-05-09** (https://www.bostonglobe.com/2026/05/09/world/hungarys-peter-magyar-set-to-be-sworn-in-as-prime-minister/ , https://www.news4jax.com/news/2026/05/09/...). VERIFIED (secondary).
- Telex, **2026-10-08** (Brückner Gergely): the Tisza government has not rushed to scrap the margin cap ("árrésstop"), and it is unclear whether there is any intention to change the 27% VAT **or the GVH Árfigyelő site**. The PM said the margin-cap phase-out "should be considered". Industry figures credit the Árfigyelő and the margin cap with making prices transparent. https://telex.hu/gazdasag/2026/10/08/elelmiszer-aldi-lidl-tesco-spar-auchan-penny-market-kisbolt-zoldseg-gyumolcs — VERIFIED.
- GVH governance conflict: President Rigó Csaba Balázs was reappointed for **6 years from 2026-04-15**. Péter Magyar demanded the GVH leaders resign by end of May; they refused (https://www.economx.hu/gazdasag/2026/06/17/lemondas-helyett-turk-tanacs-gvh-elnoke-nav/). On 2026-09-24 GVH announced legal steps against a Telex article and stressed its independence (Tpvt. 33 §(2)). On 2026-09-29 the GVH president ordered an independent organisational audit. VERIFIED: gvh.hu 2026 press releases.
- **ESTIMATE:** outright abolition in the next 12 months is unlikely (~10–20%). Reasons: the tool is popular and politically cross-cutting ("transparency"), it is cheap to run, and the government focuses on phasing out the margin cap, where the price monitor is a natural companion. More plausible scenarios are a GVH leadership change or restructuring, a rebrand or ministry shift, a scope change (more chains, lower threshold, or fewer categories), and **technical change to the undocumented API** (moderate-to-high probability over 1–3 years). No change has been announced as of 2026-10-08.

---

## 2. Scraping retailer websites (HU/EU)

### 2.1 Sui generis database right – Szjt. 84/A–84/F – VERIFIED
https://njt.jog.gov.hu/jogszabaly/1999-76-00-00 (`dl/njt_szjt.txt`)
- §60/A: definition of database. §84/A(1): the maker's consent is needed to extract (kimásolás) or re-utilise (újrahasznosítás) the whole or a **substantial part**. §84/A(3): consent is needed even for **repeated and systematic** extraction of insubstantial parts that conflicts with normal exploitation or unreasonably prejudices the maker. **§84/A(5): the right exists only if obtaining, verifying or presenting the contents required substantial investment.** §84/A(4): use is remunerated.
- §84/B(1): a lawful user may extract or re-use **insubstantial** parts, even repeatedly; contractual terms to the contrary are **void** (84/B(5)).
- §84/C(1): private copying, but not of electronic databases. **§84/D(2): free use for text and data mining (copying only), if Szjt. 35/A(1) is met**: lawful access, **no machine-readable opt-out**, and copies kept only as long as the TDM needs. TDM covers extraction for analysis, **not** displaying the data to the public.
- §84/F: protection lasts 15 years from publication.
- **INFERENCE on retailer price databases:** under CJEU *BHB v William Hill* (C-203/02) and *Fixtures Marketing* (C-46/02 etc.), money spent **creating** data (setting your own prices) does not count; only spending on obtaining, verifying or presenting does. A retailer's own price list is weak database-right material, but money spent on a website or app presentation may count.

### 2.2 CJEU case law
- **C-762/19 CV-Online Latvia v Melons (3 June 2021, ECLI:EU:C:2021:434).** A specialised search engine that copies and indexes a freely accessible database is extracting and re-utilising it. The maker can prohibit this **only if it adversely affects the maker's investment, i.e. risks the possibility of redeeming it through normal operation of the database**. Access-to-information and competition interests enter the balance. Sources (secondary, quoting the ruling): https://www.ippt.eu/sites/ippt/files/2021/IPPT20210603_CJEU_CV-Online_Latvia_v_Melons.pdf ; https://legalblogs.wolterskluwer.com/copyright-blog/access-to-information-and-competition-concerns-enter-the-sui-generis-rights-infringement-test-the-cjeu-redefines-the-database-right/ ; https://www.twobirds.com/en/insights/2021/uk/cv-online-latvia-cjeu-complicates-the-enforcement-of-database-rights. (EUR-Lex returned HTTP 202 with an empty body to automated fetches, so I relied on these copies.)
- **C-202/12 Innoweb v Wegener (19 Dec 2013).** A dedicated meta-search engine that re-runs the user's query on the source site's search form in real time and presents all results re-utilises the whole or a substantial part. https://www.ippt.eu/items/ippt20131219-cjeu-innoweb-v-wegener ; https://www.scl.org/2984-database-right-innoweb-v-wegener-cjeu-judgment/
- **C-30/14 Ryanair v PR Aviation (15 Jan 2015).** If a database has neither copyright nor sui generis protection, the Database Directive does not stop its author from imposing **contractual limits** on third-party use, subject to national contract law. Scraping ToS can therefore bite where no IP right exists, **but only if a contract was formed**. https://www.scl.org/3280-the-cjeu-takes-flight-databases-and-air-fares/ ; https://portolano.it/news/ecj-clarifies-database-directive-scope-in-screen-scraping-case
- **Comparative pricing (see §3):** C-562/15 Carrefour v ITM (8 Feb 2017) and C-159/09 Lidl v Vierzon (18 Nov 2010).

### 2.3 Hungarian court practice – VERIFIED
- **Kúria Pfv.IV.21.503/2021/6** (ad aggregator copied almost all of the plaintiff's ads). The first instance found substantial investment and infringement. The second instance found the investment **not proven** (the experts could not quantify it) and dismissed the claim. The Kúria upheld the dismissal on other grounds (infringer dissolved), without ruling on 84/A. https://kuria-birosag.hu/hu/kuriai-dontesek/324-szerzoi-jogrol-szolo-torvenyben-meghatarozott-jogkovetkezmenyek-jogsertes
  → INFERENCE: in Hungarian practice the claimant must evidence the investment. Database-right claims are not automatic wins.
- **Fővárosi Ítélőtábla 9.Pf.20.353/2024/6-II (2024-12-03)** (press publisher v. search engine). Crawling and indexing were held to be **free use under the TDM exception, Szjt. 35/A(1)**. Conditions: lawful access, **no circumvention of technical access measures**, and **robots.txt is the machine-readable opt-out**. The stored index facts were held to be unprotected data. Short snippets fell within Szjt. 82/C b). Local copy: `dl/court/FIT_9Pf20353_2024.pdf`. Source: eakta.birosag.hu (anonymised judgment).
  → INFERENCE: in Hungary, robots.txt and other TDM opt-outs are **legally relevant**. Honour them. Never get around access controls.

### 2.4 Retailer terms of use (checked 2026-10-12)
| Retailer | Key clause | Source | Status |
|---|---|---|---|
| **Kifli.hu** (ÁSZF in force from **2026-09-26**) | 3(c): the buyer undertakes "nem szerzi meg, követi nyomon vagy másolja az Online Shop tartalmait vagy információit sem automatizált eszközökkel, sem manuálisan, a Kifli.hu előzetes írásos engedélye nélkül". 3(d): no circumvention or undue load. §11: Kifli holds the rights, incl. databases. §3: **prices depend on the delivery address / warehouse** | https://cdn-kifli.s3.eu-central-1.amazonaws.com/files/terms/260926_...HU.pdf (linked from https://www.kifli.hu/oldal/felhasznaloi-feltetelek) | VERIFIED (binds registered "Vásárló") |
| **ALDI** (Felhasználási feltételek, in force from 2022-04-20) | 1.5: "Az ALDI szolgáltatásokat a felhasználók kizárólag magáncélra használhatják. A felhasználók nem használhatják az ALDI szolgáltatásokat és az azok révén hozzáférhető adatokat kereskedelmi vagy üzleti célokra." Acceptance "bármely ALDI szolgáltatás használatával" | https://www.aldi.hu/customer-services/felhasznalasi-feltetelek | VERIFIED |
| **Tesco** | ÁSZF (per search snippets): no use beyond own needs, no copying, downloading or distributing; no electronic copies without consent; Tesco holds the rights in databases | https://tesco.hu/bevasarlas/altalanos-szerzodesi-feltetelek.html (HTTP 403 to curl and WebFetch: Akamai "Access Denied"; also bevasarlas.tesco.hu) | Secondary only; **site blocks automated clients** |
| **SPAR** | Legal notice (mediatar.spar.hu, 2016): all image and text content and its arrangement are copyright/trademark protected; any use needs SPAR's prior written consent, except Szjt. free uses | https://mediatar.spar.hu/felhasznalasi-feltetelek ; www.spar.hu returns 403 with a Cloudflare "Just a moment..." challenge | Secondary; **site blocks automated clients** |
| **Penny** | Legal notice: prices and availability vary by store; no scraping clause found | https://www.penny.hu/joginyilatkozat | VERIFIED |
| **Lidl** | Imprint: lidl.hu is operated by Lidl Stiftung & Co. KG; no ToS clause on automated use found in the static HTML | https://www.lidl.hu/c/impresszum/s10014076 | Partially checked |
| **Auchan** | Terms page is a JS shell; operator footer "MH Magyarország Kft." | https://www.auchan.hu/felhasznalasi-feltetelek | Not readable statically |

**Enforceability (INFERENCE):** clickwrap terms (Kifli on registration or order) bind clearly. Browsewrap terms (Aldi: "by using any service") against an anonymous scraper are uncertain under Ptk. 6:77–6:78 incorporation rules. Ryanair makes contract the main weapon where no IP right exists. Tpvt. §2, the general unfair-competition clause (https://njt.jog.gov.hu/jogszabaly/1996-57-00-00), is another possible claim.

### 2.5 Criminal-law edge: getting around bot protection – VERIFIED text
Btk. (2012. évi C.) 423. § (1): "Aki információs rendszerbe az információs rendszer védelmét biztosító technikai intézkedés megsértésével vagy kijátszásával jogosulatlanul belép ... vétség miatt két évig terjedő szabadságvesztéssel büntetendő." 423. § (2) a): "... az információs rendszer működését jogosulatlanul ... akadályozza" is a felony (bűntett) punishable by up to 3 years. Source: https://net.jogtar.hu/jogszabaly?docid=a1200100.tv (njt's static page is truncated).
→ INFERENCE: whether a Cloudflare/Akamai challenge is a "technical measure protecting an information system" is untested. **Do not get around it.** Aggressive crawling that degrades a site could fall under 423(2)(a).

### 2.6 Copyright in product photos, descriptions and recipes
- Szjt. 1(3): protection requires individual, original character; "fotóművészeti alkotás" is a protected work. A packshot also reproduces **packaging artwork and trademarks**, owned by brand owners. Marketing descriptions can be original; bare facts (name, size, price) are not.
- GVH images: PSI Act §3 b) excludes third-party IP. ÁFF XIV.2 restricts brand content to informational use. The merchant ÁFF XIV.2 licences go to GVH's statutory purpose only. → **MEDIUM risk** to copy or hotlink at scale. INFERENCE: embedding freely accessible files under CJEU *BestWater* (C-348/13) is arguable, but it is not a safe harbour for a commercial product.
- Open Food Facts: database under ODbL, contents under DbCL, **images CC BY-SA**. OFF warns that packaging may carry third-party copyright or trademarks and that re-users are responsible (https://world.openfoodfacts.org/terms-of-use). ODbL share-alike may apply to a derived public database.
- Recipes from third-party sites (Nosalty, Mindmegette, etc.): original method text and photos are protected, the site may hold database rights, and ToS apply. An ingredient list is factual. **Write your own or license recipes**; linking out is fine (CJEU *Svensson* C-466/12, linking to freely available content).

### 2.7 Trademarks and chain names – VERIFIED
Vt. (1997. évi XI.) 15. § (1) c): the owner cannot prevent use of the mark "a védjegyjogosult áruinak vagy szolgáltatásainak ekként történő azonosítása vagy azokra való hivatkozás céljából", provided it accords with honest practice. 12. § (3) g): comparative advertising contrary to Tpvt. can be prohibited. https://njt.jog.gov.hu/jogszabaly/1997-11-00-00
→ Plain-text chain and brand names used to identify them: LOW risk. Logos, look-alike app names, or anything implying affiliation (e.g., "Árfigyelő", the GVH crest): MEDIUM–HIGH, also under Apple 5.2.1 and Tpvt. 6.

---

## 3. "Cheapest at X", comparative advertising, wrong prices

- **Fttv.** (2008. évi XLVII.) https://njt.jog.gov.hu/jogszabaly/2008-47-00-00. §2.8 defines "kereskedelmi gyakorlat" as conduct of a business **or of a person acting in its interest or on its behalf** directly connected with promoting sales to consumers.
  - §7(7): when consumers can search products offered by **different traders**, the **main ranking parameters** and their relative weight are "material information". They must be shown in a separate, easily reachable section of the results page. Online search-engine providers under P2B Art. 2(6) are exempt.
  - Annex 1 (blacklist), point 11: paid editorial content not clearly identified (disguised advertising). Point 32: search results that do not clearly disclose paid ads or payment for higher ranking. Points 34–35: unverified or fake reviews.
  - §9(1): the business with a **direct interest** in the sale is liable. §10–11: the GVH is the competent authority where competition is substantially affected; otherwise the consumer authority.
- **Tpvt.** 6/A (comparative advertising definition and bans) and **10. §**: compare only products meeting the same needs; compare material, verifiable features; be objective when price is compared. A neutral aggregator that is not itself a retailer is arguably **not** the "advertiser" comparing with its own competitors. That changes if it acts on behalf of a paying retailer (INFERENCE). Tpvt. 3. §: harming a competitor's reputation by false facts. Ptk. 2:43 / 2:45: reputation of legal persons. A wrong "X is more expensive" claim invites a retailer complaint.
- **CJEU C-562/15 Carrefour v ITM (2017).** A price comparison between stores of **different size or format** can be misleading unless the difference is disclosed in the ad itself. https://curia.europa.eu/jcms/upload/docs/application/pdf/2017-02/cp170012en.pdf
- **CJEU C-159/09 Lidl v Vierzon (2010).** Basket comparisons of food are allowed if the products are sufficiently interchangeable and **identifiable or verifiable** from the comparison itself. https://www.ippt.eu/sites/default/files/2010/IPPT20101118_ECJ_Lidl_v_Vierzon_Distribution.pdf
- **Liability for wrong prices (INFERENCE + VERIFIED law):** GVH disclaims accuracy (ÁFF XII.6–7). Retailers must not charge above the registered GVH price (Act L §71(1)(c)), which helps the app if it shows the GVH price with its date. Exposure: (a) Fttv. misleading price information, higher if monetised; (b) contract or tort claims by users; (c) reputation claims by chains. **Ptk. 6:152 (VERIFIED, current text via net.jogtar):** "A szándékos, továbbá emberi életet, testi épséget vagy egészséget megkárosító szerződésszegésért való felelősséget korlátozó vagy kizáró szerződési kikötés semmis." Beyond that, ordinary liability limits in the app terms are possible, subject to B2C unfair-terms review.
- **Mitigation wording (suggested):** "A legolcsóbb ár a GVH Árfigyelőbe adatot szolgáltató 9 lánc [dátum]-i napi árai alapján (a lánc üzleteinek legalább 80%-ában alkalmazott ár). Egyes üzletekben az ár eltérhet; a készletről nincs információ. Forrás: GVH Árfigyelő." Show unit prices. Label substitutions (e.g., private label instead of a brand). Show store-level prices where `priceSameEverywhere=false`. Add a report-error button and a correction log.

---

## 4. Location data – GDPR, ePrivacy, app stores

- **Eht. 155. § (4)** (2003. évi C., in force; VERIFIED text at https://net.jogtar.hu/jogszabaly?docid=a0300100.tv; njt footnote confirms (4) was set by 2011:CVII): "Egy előfizetőnek vagy felhasználónak elektronikus hírközlő végberendezésén csak az érintett felhasználó vagy előfizető világos és teljes körű – az adatkezelés céljára is kiterjedő – tájékoztatását követő hozzájárulása alapján lehet adatot tárolni, vagy az ott tárolt adathoz hozzáférni."
  - **The Hungarian text contains no explicit "strictly necessary" exemption** (I searched the whole act). ePrivacy Directive Art. 5(3) has one. INFERENCE: treat reading device location as needing prior, informed, purpose-specific consent. Use an in-app explainer screen followed by the OS permission prompt.
  - EDPB Guidelines 2/2023 on the technical scope of Art. 5(3), v2.0 of 2024-10-16, treat access to information on or generated by the terminal broadly (https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-22023-technical-scope-art-53-eprivacy-directive_en).
- **GDPR:** location is personal data. Lawful basis is consent (Art. 6(1)(a)), which is GVH's own choice for its store-finder, or arguably contract necessity (6(1)(b)) for a user-requested "near me" feature. Apply data minimisation (Art. 5(1)(c)) and privacy by design (Art. 25). WP29 Opinion 13/2011 (WP185) on geolocation on smart mobile devices: opt-in consent, a persistent indicator, short retention. https://www.statewatch.org/news/2011/august/eu-article-29-data-protection-working-party-opinion-13-2011-on-geolocation-services-on-smart-mobile-devices
- **NAIH:** I found no NAIH recommendation or decision specific to app geolocation (searched naih.hu and the web on 2026-10-12). The closest item is the Warsaw Declaration on "appification" (https://www.naih.hu/files/35th-adatv-konf-2013_09_24-Varsoi-Nyilatkozat_appification_HU.pdf).
- **Design that minimises risk (INFERENCE):** ship the GVH store list (1,829 shops, ~52 KB gzipped; COMPUTED) inside the app or as a daily download. Compute distances **on the device**. Never send coordinates to the backend or to third-party SDKs (ads/analytics). Request **foreground ("while using")** permission only. Approximate (coarse) location is enough. Offer manual postcode or city entry. Keep no history. Personalised ads using location would need separate explicit consent; avoid them.
- **Apple App Store Review Guidelines** (https://developer.apple.com/app-store/review/guidelines/): 5.1.1(i) requires a privacy policy. 5.1.1(iii) data minimisation. **5.1.5: "Ensure that you notify and obtain consent before collecting, transmitting, or using location data."** Explain the purpose in the app. 5.2.1: no unauthorised trademarks or copycat names. **5.2.2: "If your app uses, accesses, monetizes access to, or displays content from a third-party service, ensure that you are specifically permitted to do so under the service's terms of use. Authorization must be provided upon request."** → This is a reason to obtain written GVH permission or a PSI re-use agreement, and not to scrape retailers whose terms forbid it.
- **Google Play location policy** (https://support.google.com/googleplay/android-developer/answer/9799150): foreground access preferred. A prominent in-app disclosure must come before the runtime prompt. Background location needs a declaration form and review, and is refused if the purpose is only ads or analytics. Use coarse location where possible. Fill in the Data safety section.

---

## 5. Affiliate and sponsored content disclosure (HU)

- **GVH "Tájékoztató az influenszer marketingről" (2022-11-10)**: https://www.gvh.hu/pfile/file?path=/szakmai_felhasznaloknak/tajekoztatok/Tajekoztato_az_influenszer_marketingrol.pdf1&inline=true — VERIFIED.
  - "Ellenszolgáltatás" covers any incentive: money, discount, free product, barter, future partnership.
  - Disclosure must be prominent, simple, clear and **in Hungarian**: "Reklám", "Hirdetés", "… támogatta", "Szponzorált tartalom". Foreign-language tags are not acceptable unless the content itself is in that language. Place it before any "more" click or scroll.
  - **Para 32: a direct interest exists if the publisher receives a sales-linked incentive, "például jutalékban részesül".** The publisher is then jointly liable under Fttv. 9(1).
  - Para 27: food content must comply with Reg. 1924/2006.
- **GVH food-claims guidance (June 2026)**: https://www.gvh.hu/pfile/file?path=/szakmai_felhasznaloknak/tajekoztatok/Tajekoztato_elelmiszer_reklamozasrol_kieg_2026_06.pdf1&inline=true — VERIFIED.
  - Commercial practice expressly includes "webáruházban, **mobilalkalmazásban** megjelenített tájékoztatás".
  - Only authorised health claims may be used (269 on the EU register per the guidance). **General claims ("egészséges") must be accompanied by an authorised specific claim** (para 42).
  - **Medicinal claims are banned outright** (Reg. 1169/2011 Art. 7(3)). Nutrition claims follow the 1924/2006 Annex conditions (e.g., "zsírszegény" ≤3 g/100 g).
  - Liability (para 56–57): everyone earning revenue from sales of the promoted products, **including affiliates paid by commission**.
- **GVH enforcement trend 2026:** influencer cases (e.g., Whisper Ton, Sept 2026), a health-claims proceeding, and sustainability (EmpCo, applicable from 2026-09-27). Source: gvh.hu 2026 press list.
- **P2B Regulation (EU) 2019/1150 (INFERENCE):** applies only if the app becomes an "online intermediation service" with contracts with retailers (e.g., affiliate or partner listings). Ranking transparency and T&C duties toward business users would then follow.

---

## 6. Risk matrix (data source × legal risk × mitigation)
Also in `risk_matrix.csv`.

| # | Data source / feature | Legal risk | Main legal hooks | Mitigation |
|---|---|---|---|---|
| 1 | GVH Árfigyelő prices, product names and IDs, categories (current day) via public JSON | **LOW** (legal) / **MED–HIGH** (operational/political) | Act L §70 publicity; PSI Act §3/A, §8–9, §16/A; ÁFF XII; 2023 pirate-app precedent; Apple 5.2.2 | File a PSI re-use request (§10) and seek a written agreement or API terms. Attribute "Forrás: GVH Árfigyelő" with date. No GVH branding. Polite caching (one pull per day, low request rate). Monitor the API |
| 2 | GVH store list and coordinates | **LOW** | Same as #1; no personal data | Same as #1; bundle on the device for the local nearest-store calculation |
| 3 | GVH product images (Azure CDN) and brand content | **MEDIUM** | ÁFF XIV.2 (visitor + merchant); PSI §3 b); Szjt.; Vt. | MVP without images or with generic icons; license from brand owners or GS1 later; no logos |
| 4 | Own historical price series built from daily GVH snapshots | **LOW–MED** | Act L §57(4)–(5) restricts GVH's archive, not third-party copies; misleading if labelled "GVH" | Label as "saját gyűjtés a GVH napi adataiból"; show dates; no claim of official history |
| 5 | Scraping retailer websites (Aldi, Lidl, Penny, Auchan) | **MEDIUM–HIGH** | Szjt. 84/A (CV-Online harm test); Aldi 1.5 commercial-use ban; Tpvt. §2; Apple 5.2.2; robots/TDM opt-out (35/A) | Prefer GVH data. If ever needed: written permission, facts only (price, name, unit), honour robots.txt and TDM opt-outs, low rate, no login, no images or text, legal opinion first |
| 6 | Scraping Tesco / Spar (bot-protected) | **HIGH** | Same as #5 + Btk. 423(1)/(2)(a) if protection is circumvented or the site is overloaded; TDM "lawful access" fails | **Do not.** Use GVH data (both chains report) or a partnership |
| 7 | Online grocers (Kifli, Tesco online, Wolt/Foodora) prices | **HIGH** (scrape) / **LOW** (partner feed) | Kifli ÁSZF 3(c),(d), §11; address-dependent prices | Affiliate or partner API only; disclose commissions |
| 8 | Retailer leaflets via AI/OCR | **MEDIUM** | Copyright in layout and photos; TDM 35/A only for analysis; ToS | Extract facts only; never republish leaflet images; honour opt-outs; prefer licensed feeds |
| 9 | Open Food Facts (nutrition, barcodes) | **LOW–MED** | ODbL share-alike; CC BY-SA images; third-party packaging IP | Attribution; keep the OFF-derived DB ODbL-compliant; use nutrients, not images |
| 10 | Recipes and meal plans from third-party sites | **HIGH** (copy) / **LOW** (own or licensed, link-out) | Szjt. (text, photos); database right; ToS | Write or commission your own; use CC-licensed sources with attribution; link out |
| 11 | "Healthy" labels and nutrition claims | **MEDIUM** | Reg. 1924/2006; 1169/2011 Art. 7(3); Fttv.; GVH June 2026 guidance | Factual nutrient values; no disease or medicinal claims; "egészséges" only with an authorised claim or avoid it; dietitian review |
| 12 | User location (nearest stores) | **LOW** (on-device) / **MED–HIGH** (server or SDK sharing, ads) | GDPR 6, 5(1)(c), 25; Eht. 155(4) consent; Apple 5.1.5; Play location policy | On-device calculation; foreground and coarse only; Hungarian consent explainer; postcode fallback; no third-party sharing |
| 13 | "Cheapest at X" and basket comparisons | **MEDIUM** | Fttv. misleading price info; Tpvt. 6/A, 10, 3; CJEU Carrefour, Lidl v Vierzon | Scope and date the claim; unit prices; label substitutes; store-level where available; correction workflow |
| 14 | Affiliate links and sponsored placements | **MEDIUM** | Fttv. Annex 1 pts 11 and 32, §7(7), §9(1); GVH influencer guidance; P2B if contracted | Hungarian "Reklám/Hirdetés" labels; payment never changes the price ranking; publish ranking parameters |
| 15 | Chain names, logos, app name | **LOW** (word marks) / **MED–HIGH** (logos, GVH look-alike) | Vt. 15(1)(c), 12(3)(g); Tpvt. 6; Apple 5.2.1 | Plain-text names; no logos without a licence; distinct brand, not "Árfigyelő"/GVH |
| 16 | Dependence on the Árfigyelő regime | **MEDIUM** (business) | Ordinary statute, no sunset; 2/3 government can amend; GVH leadership conflict | Multi-source roadmap; monitor Magyar Közlöny and parliament.hu; build partnerships |

---

## 7. Open questions / next steps
1. Send GVH (arfigyelo@gvh.hu) a **PSI re-use request** under Act LXIII 2012 §10. Ask for: format (JSON API), daily regularity, the scope (non-archived prices, products, categories, stores), the licence terms, and confirmation that commercial use is allowed. The deadline clock is 5 + 20 (+20) working days.
2. Confirm with counsel whether Árfigyelő daily prices are "dinamikus adat" (§16/A API duty), and how Act L §57(4) archiving interacts with third-party historical snapshots.
3. Check that retailer robots.txt files and TDM opt-outs (TDMRep, ai.txt, etc.) are consistent with any leaflet or AI extraction.
4. Check whether Hungarian courts or NAIH apply an implied "strictly necessary" exemption to Eht. 155(4). Until then, use consent.
5. Monitor the Tisza government's plans (margin-cap phase-out, GVH reform) and any amendment bills touching Act L Ch. V.
6. Contact retailers and online grocers (Kifli, Tesco, SPAR via Wolt, Auchan) about affiliate programmes or data partnerships.
7. Decide whether the app makes health or nutrition claims at all. If it does, set up a claims register based on the EU register.
