# Gap-fill: formal permission route and residual legal risk for commercial reuse of GVH Árfigyelő data

Stream: `gap-gvh-reuse-legal-route` · Date: 2026-10-12 · This is research, not legal advice.
Labels: **VERIFIED** = read in the primary source (URL given) · **COMPUTED** = from data I pulled (method given) · **ESTIMATE** = my reasoning.

Method and housekeeping:
- I read njt.jog.gov.hu (Act CI 2023, Act L 2025, Infotv, Szjt, Tpvt, 250/2024 Korm. rendelet), kozadatportal.hu, magyarorszag.hu, gvh.hu, arfigyelo.gvh.hu, the competitor sites, Apple and Google Play policy pages, Telex and HVG. Downloads are in `dl/` (untrusted data). Scripts are in `scripts/` (Python run with `-I`, plus a compiled Swift PDFKit text extractor). User-Agent: `market-research-bot/0.1`, with pauses of 1 s or more between requests.
- **Disclosure:** the robots.txt of kozadatportal.hu disallows `/api/` and sets `Crawl-Delay: 10`. I sent 3 CKAN API GETs (`organization_list` and two `package_search` calls) before I read it. After reading it I stopped using `/api/` and used only HTML pages, 10 s apart. No login, no form submission, no accepted terms.
- **The web-search budget ran out** during this stream. Findings for items (2) and (6) come from direct site listings: the gvh.hu 2023/2026 press archives, the gvh.hu decision lists for 2023–2025, the Telex GVH tag page and the HVG GVH tag page. I ran no new search-engine queries.

---

## 0. Bottom line (for the decision)

1. **The formal route exists. It is cheap in law, but not fast or predictable in practice.**
   - The request is filed electronically: Nemzeti Közadatportál, then the SZÜF e-form at magyarorszag.hu with KAÜ login, sent to NAVÜ's office storage, then forwarded to GVH. Act CI 2023 §19(3), §56–57, §62. VERIFIED.
   - Statutory clock: 5 working days for the formal check, 20 WD to decide, extendable once by 20 WD, and court within 10 WD. Act CI §64(3), §65(1)-(2), §72(2). VERIFIED.
   - Fee: capped at marginal cost (§67(3)). VERIFIED.
   - Refusal grounds are exhaustive (§66(3)). VERIFIED.
   - **But** GVH has never published re-use terms for the Árfigyelő. Its own public-data page still cites the **repealed** Act LXIII 2012 and says it has no general re-use terms (VERIFIED). The Közadatkataszter was "temporarily unavailable" on 2026-10-12 (VERIFIED). GVH leadership is in turmoil (VERIFIED).
   - Realistic elapsed time: **~5–12 weeks if GVH engages, longer if it stalls**. ESTIMATE.
2. **Any agreement gives no moat.** Conditions must be non-discriminatory and non-exclusive (§6–7, §69(5)). The decision, conditions and fee are public-interest data (§66(5)). Árnéni, NomNom and Cashmap could get identical terms. VERIFIED.
3. **The 2023 precedent was about impersonation plus inaccuracy, not plain reuse.**
   - GVH's own release of 2023-08-05 says the app was "megtévesztésig hasonlító". GVH had not authorised use of "az Árfigyelő rendszer adatainak … és egyes arculati elemeinek", and the app gave "nem valós árinformációkat". VERIFIED.
   - I found no GVH decision, court ruling or follow-up release about it in the gvh.hu decision lists for 2023–2025 (COMPUTED). Whether the app was removed is not confirmed by any source I could reach.
   - In 2026 three or more commercial apps openly attribute GVH data with no reported action against them (VERIFIED for their pages; the "no action" part is ESTIMATE). None of them claims permission or an agreement.
4. **Recommendation (ESTIMATE): "launch on GVH data now, with guardrails, and file in parallel".** This is a conditional "go". It is not "wait for permission":
   - The data are public by statute (Act L 2025 §70, VERIFIED). Constitutional and Infotv dissemination rights sit outside Act CI (Act CI §1(3)(a), VERIFIED).
   - Competitors operate openly.
   - The live risks can be controlled: impersonation, product images and brand assets, inaccuracy, aggressive scraping, and app-store proof.
   - Guardrails: no GVH name or logo in the app name or icon; a clear "nem hivatalos, nem áll kapcsolatban a GVH-val" disclaimer; source attribution with "as of" timestamps; no retailer product images or logos; cached, low-rate pulls; an independent fallback data plan.
   - Escalate to "launch only after permission" if any of these happens: GVH sends an objection, Apple or Google ask for 5.2.2 authorization and reject the statutory argument, or the endpoints are locked.

---

## 1. Act CI of 2023 (Nahtv.) — VERIFIED from https://njt.jog.gov.hu/jogszabaly/2023-101-00-00 (njt time state 2026.01.01.)

Scope and exclusions:
- §1(1)(a): the act covers services related to the use of national data assets held by public-task bodies, "ezen belül az adatok további felhasználására".
- **§1(3)(a):** the act does NOT apply to Infotv requests for access to public-interest or public-for-public-interest data "és azok terjesztése jogának gyakorlására" (and to exercising the right to disseminate them).
  - Consequence (ESTIMATE): disseminating the already-public Árfigyelő data rests on Alaptörvény VI. cikk (3), "közérdekű adatok megismeréséhez és terjesztéséhez" (VERIFIED in the legal stream's njt copy of the Alaptörvény), and on Infotv. It does not depend on an Act CI agreement.
  - Act CI governs *provision for re-use* by the body, for example a bulk feed or API under an agreement.
- §1(3)(b): the act also does not apply to data provision that public bodies carry out "alaptevékenységük keretében" (as part of their core activity). ESTIMATE: GVH's own public website and the API behind it are core activity under Act L §70, so their access terms come from Act L and the visitor ÁFF, not from Act CI.

Definitions (§2):
- 8 **dinamikus adat** = "gyorsan változó vagy gyorsan elavuló digitális formátumú közadat, amelyet jellemzően valós időben frissítenek, ilyenek különösen a szenzorok által generált adatok".
- 15 közadat = Infotv public-interest or public-for-public-interest data in digital form.
- 35 további felhasználás = commercial or non-commercial use outside the original public-task purpose.
- **36 védett adat** includes "a szerzői joggal védett adat" (copyright-protected data). So product images are not "nem személyes és nem védett adat" and fall outside the plain §35 route. ESTIMATE, based on the definition.

Non-discrimination and no exclusivity:
- §6(1): no "önkényes megkülönböztetés" (arbitrary discrimination) between requesters in conditions, provision or fees.
- §7(1): no exclusive rights.
- §7(5): a non-exclusive agreement that restricts third-party access must be **published on the portal 60 days before it enters into force**.
- §66(5): the decision, the conditions and the fee are **közérdekű adat** (public-interest data).

Transparency of fees:
- §5(2)-(3): the body must state the fee factors in advance and explain the fee on request.

Provision (§35–40):
- §35(1),(3): the public body must provide its re-usable data on a request filed via the portal.
- §36: data come in the format, mode and language requested. Fallbacks are an open machine-readable format, then the format available. Reasons include disproportionate effort and harm to the public task.
- §37(2): high-value datasets must be machine-readable, via API or bulk download.
- **§37(3): dynamic data must be provided "közvetlenül azok gyűjtése után, alkalmazásprogramozási interfészen keresztül"**, with bulk download where needed.
- §38: no duty to create new data, to transform data with disproportionate effort, to produce analyses, or to **store data beyond the original request for re-use (c)**. So no right to price history from GVH.
- §39: a fee may be charged for transformation.
- §40(1): information-security grounds alone cannot justify refusal.
- **§40(2):** if real-time provision of dynamic data is beyond the body's means, it may be provided "egy olyan időkereten belül vagy olyan ideiglenes technikai korlátozásokkal", provided this does not unnecessarily block their economic potential.
- ESTIMATE: daily prices that are public for one day only are "gyorsan elavuló" (quickly outdated) but not sensor-like. The dynamic-data argument is a negotiating point, not an entitlement.

Procedure (§56–66):
- §56(1): electronic filing via the portal.
- §58(2)-(3): if the request triggers a fee, the requester must authenticate it electronically with eAláírás, a qualified e-signature or a qualified e-seal.
- §59–61: simplified, automated and general procedures. Simplified and automated procedures need published general terms (§60(3), §61(2), §69(2)-(3)). **GVH has none for the Árfigyelő** (see §5 below), so only the **general procedure** is available.
- §62: the request is filed via the portal on an electronic form.
- **§64(1) mandatory content:**
  - a) an express statement that the data are requested "további felhasználás céljára";
  - b) name, home address or registered seat, phone and e-mail;
  - c) exact designation of the data;
  - d) format, including technical means and mode;
  - e) frequency for regular provision.
- §64(3): within **5 working days** the provider examines the request if it contains the (a) statement. Otherwise it rejects the request without examination.
- §64(5)-(6): a request to fill gaps gives **5–10 WD**. Missing that deadline means the request is treated as never filed, but it can be refiled.
- §64(7): the provider transfers the request to the right holder.
- **§65(1)-(2): decision on the merits within 20 WD of a complete request, extendable once by 20 WD.**
- §65(3): data that cannot be provided for re-use include:
  - (a) data outside the body's public tasks;
  - **(b) third-party IP-protected content;**
  - **(c) data whose access is excluded or limited by law.** This covers archived prices: Act L §57(5) gives authority-only access.
  - (f) logos and emblems only.
- **§65(4):** when providing data, the body "nem gyakorolhatja" (may not exercise) the database-maker's rights under Szjt.
- §66(1): the decision is an offer of a re-use agreement (on general terms or individual terms) or a rejection. §66(2): the data are handed over on the day both parties sign.
- **§66(3): rejection only if** (a) the data are not available for re-use or (b) the data are not held and cannot be transferred. §66(4): written reasons, naming the IP holder if known, plus remedies.

Fees (§67–68):
- **§67(3): the fee is capped at the marginal cost** of processing, provision and dissemination.
- §67(4): cost plus "észszerű megtérülés" (reasonable return) is allowed only if the body must fund a significant part of its tasks from its own revenue. §2(10): the return is at most the ECB rate plus 5 percentage points.
- §68: high-value datasets and research data are free. ESTIMATE: Árfigyelő prices do not fall into the HVD categories of Reg. (EU) 2023/138 (geospatial, earth observation, meteorological, statistics, companies, mobility).

Agreement (§69):
- §69(1): an agreement is concluded.
- §69(4): minimum content is the parties, the data, timing, mode and format of transfer, the fee, payment terms, and "f) a … felhasználásának részletes feltételeit".
- **§69(5): the conditions** a) may be set only for a public-interest purpose; b) must be objective, proportionate and non-discriminatory; c) must not unnecessarily restrict re-use, must not serve to restrict competition, and must not conflict with the act.
- §69(6)-(7): general terms are possible and must be published on the portal.

Personal data and remedies (§70–72):
- §70: requester personal data are deleted after fulfilment.
- §71(1): court action is possible against a rejection, an expired deadline, or the amount of the fee.
- §72(1): the **burden of proof is on the provider**.
- §72(2): action within **10 WD**.
- §72(3): a national body is sued at the törvényszék (regional court) where the defendant has its seat. Budapest, so the Fővárosi Törvényszék (ESTIMATE as to the court name).
- §72(4)-(6): the court can order provision and change the fee.

Open data publication:
- §21(1): public bodies publish their "nyílt hozzáférésű közadataikat" on the portal as well. ESTIMATE: the statutorily public Árfigyelő data arguably qualify, and GVH has not published them there (see §2). This is a soft lever for the request.

Timing provisions:
- §101(4): the core provisions apply from 2024-04-01.
- §102: the act applies to requests filed after 2024-03-31.
- §105(1): the act serves Directive (EU) 2019/1024.

**250/2024. (VIII. 15.) Korm. rendelet** (https://njt.jog.gov.hu/jogszabaly/2024-250-20-22, time state 2025.06.11.), VERIFIED:
- §5(2): NAVÜ handles requests for non-personal, non-protected data **only by agreement with the body concerned**. §5(3) is the exception: data available via automatic information transfer.
- §5(5)-(6): if routing to a provider is not possible, NAVÜ either forwards the request to the competent body or rejects it.
- No separate deadline is set for NAVÜ's forwarding. **ESTIMATE:** add a few days to a couple of weeks before the 5-WD clock starts at GVH.

## 2. kozadatportal.hu (read without login) — VERIFIED 2026-10-12

- Home page: CKAN-based. It states that the portal is regulated by Act CI 2023 and points to 249/2024 and 250/2024 Korm. rendelet.
- **Közadatkataszter** (https://kozadatportal.hu/publicdata), the register of re-usable public data: the results area says "A Közadatkataszter szolgáltatás átmenetileg nem elérhető, a szolgáltatás helyreállítása folyamatban van." A search for "Gazdasági Versenyhivatal" returned the same message. **It cannot be verified whether GVH or the Árfigyelő is registered there.**
- Open datasets (https://kozadatportal.hu/dataset/?q=árfigyelő): "Nincs adatkészlet a "árfigyelő" lekérdezéshez". VERIFIED.
- COMPUTED: the CKAN organisation list, fetched before I read robots.txt, has **21 publishing organisations**, for example KSH with 1,269 datasets, Oktatási Hivatal 597, NAV 209 and MEKH 48. **GVH is not among them.** A `package_search` for "árfigyelő" and for "Versenyhivatal" returned **0 results** each.
- News page: the latest item is dated 2026-03-31. ESTIMATE: the portal is semi-dormant.
- "Adathasznosítás" page (https://kozadatportal.hu/dataut): requests are filed electronically via the portal. The button leads to the SZÜF procedure "A Nemzeti Adatvagyon Ügynökség, valamint a központi vagy regisztrációköteles adathasznosítás-támogatási szolgáltatás nyújtója által nyújtott szolgáltatások igénybevételére irányuló igény benyújtása" (https://magyarorszag.hu/szuf_ugyleiras?id=0b70cf76-26f7-4313-831a-07b2fc1c71ec).
- **Guide for filing** (https://kozadatportal.hu/pdf/utmutato_adathasznositas.pdf?ver=2, 8 pages, NAVÜ Kft.):
  1. Kozadatportal → Adathasznosítás → "Adathasznosítás-támogatási szolgáltatások igénylése" → SZÜF.
  2. "Ügyintézés indítása". After KAÜ identification, choose to file as **Természetes személy, Hivatali tárhely or Cégkapu**.
  3. "Fontos: Az igénybenyújtási űrlap kizárólag a NAVÜ Kft. hivatali tárhelyére küldhető be. Az egyéb módon (személyesen, postán vagy e-mailben) benyújtott igényt a NAVÜ Kft. nem fogadja be."
  4. Form sections:
     - 3.1 **Igénylő beazonosítása**: name, address, e-mail, phone. For an organisation, the name as in its founding document plus an official e-mail and phone.
     - 3.2 **Igény leírása**: a free-text "Igény szöveges indoklása" (why the service is needed, the exact need, and the format, mode and language, e.g. xlsx/csv/pdf/json), plus a **"Szolgáltatás típusa"** dropdown.
     - 3.3 **Csatolmány**: pdf, docx or xlsx only. If a fee arises, the e-signed request is attached here (§58(2)).
  5. "Ellenőrzések futtatása" → "Kitöltés befejezése" → "Beküldés folytatása".
  6. Confirmation and a PDF/KR copy in SZÜF. Questions go to **igenykezeles@navu.hu**.
- I did **not** open the form itself, because that requires login.

## 3. GVH's own re-use disclosures — VERIFIED https://www.gvh.hu/kozerdeku_adatok/tevekenysegre-mukodesre-vonatkozo-adatok/kozerdeku_adatok_igenylese (fetched 2026-10-12)

- "A Gazdasági Versenyhivatalnál nincsenek a közérdekű adatok felhasználására, hasznosítására vonatkozó általános szerződési feltételek." (updated 2024-01-11)
- "A Gazdasági Versenyhivatalnál jelenleg nincsenek közérdekű adatok hasznosítására irányuló szerződések." (updated 2024-01-11)
- In the same table, a row titled "**Újrahasznosítási megállapodás a 2012. évi LXIII. törvény rendelkezéseinek megfelelően**" links to "Adatszolgáltatás xlsx/csv formátumban_2026.10.09" (`GVH_eljarasok_20261009.xlsx1/.csv1`). A hidden link `MIGAL_25_október.xlsx` is a list of GVH **proceedings**: vjszam, ugynev, ugytip, cegnev and so on (COMPUTED from the sheet header).
  - So GVH does run a re-use arrangement and refreshes it (2026-10-09), but for **case data, not Árfigyelő data**.
  - The page still cites the **repealed** Act LXIII 2012. ESTIMATE: GVH's internal re-use processes have not been updated to Act CI, so expect a slow, case-by-case handling.
- GVH's register-disclosure page (https://www.gvh.hu/kozerdeku_adatok/tevekenysegre-mukodesre-vonatkozo-adatok/a_gvh_nyilvantartasai) says for every item: "A közzétételi egység a Gazdasági Versenyhivatal esetében nem értelmezhető". **The Árfigyelő is not listed as a GVH register.** VERIFIED.
- GVH received **14** public-data requests in 2025, covering 24 data types (same page). VERIFIED.
- Árfigyelő robots.txt: https://arfigyelo.gvh.hu/robots.txt returns the SPA HTML shell, so there is no robots file and no machine-readable opt-out. VERIFIED (HTTP 200, HTML body).
- Visitor ÁFF, fresh copy (https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_latogato.pdf, "hatályos 2025. július 20-tól"), VERIFIED:
  - V.2: the site's purpose is consumer information and strengthening competition.
  - V.4: "A Szolgáltatást bárki jogosult igénybe venni."
  - VI.1: the ÁFF is accepted by conduct.
  - XII.4: non-archived data are public.
  - XII.6-8: no liability for accuracy, and "nem rendeltetésszerű használat" (improper use) is excluded from liability.
  - XIV.1: copyright in the system and the site.
  - XIV.2: images are retailer-supplied "egyéb azonosító adat". The retailer warrants rights only for the statute's purposes. Protected brand names and content may be used "kizárólag a Honlap céljával összhangban (tájékozódás, tájékoztatás)".
  - XV.1: bug reports go to arfigyelo@gvh.hu.
  - **Nothing on API, automated access or commercial reuse.**

## 4. The 2023 copycat app — VERIFIED from GVH primary source

GVH release "Csalókra figyelmeztet a GVH", Budapest, 2023-08-05 (https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2023-as-sajtokozlemenyek/csalokra-figyelmeztet-a-gvh):
- The app was "Az online Árfigyelőre megtévesztésig hasonlító mobilapplikáció", available on Google and Apple.
- **What GVH objected to (verbatim):** "ez a kalózapplikáció az online Árfigyelő rendszer illetéktelen, engedély nélküli felhasználása! A GVH nem adott engedélyt az illegális alkalmazás létrehozójának az Árfigyelő rendszer adatainak felhasználására és egyes arculati elemeinek használatára." So the objection covered **data use AND branding/visual identity**, together with **impersonation** ("megtévesztésig hasonlító"), **inaccuracy** ("félrevezető, nem valós árinformációkat közöl") and **security risk**.
- **Actions:** civil and criminal steps against the makers, a request to Google and Apple to remove the app, an ex officio proceeding for consumer deception, a public call on the makers to remove the app, and advice to consumers to delete it. The official GVH app was "in development".
- The listing order on the 2023 press pages was COMPUTED by parsing pages 1–7.
- Telex 2023-08-05 (https://telex.hu/belfold/2023/08/05/gvh-figyelmeztetes-kalozapplikacio-arfigyelo) repeats the release. **No app name or developer** is given, and the article does **not confirm removal**. Telex said it had e-mailed the developers.
- **Follow-up:** I parsed all pages of the GVH decision lists for 2023, 2024 and 2025 (https://www.gvh.hu/dontesek/versenyhivatali_dontesek/dontesek-2023 and the -2024 and -2025 lists) and found **no decision mentioning an Árfigyelő app or a mobile application** (COMPUTED by grep). I found no court ruling. Removal is **unconfirmed**.
  - ESTIMATE: the case most likely ended with store takedowns and a quiet closure. A HU App Store lookup by another stream for "arfigyelo" shows no GVH or copycat app today.
  - **Limitation:** the web-search budget was exhausted, so I could not check Index or HVG coverage from 2023.
- **Legal context then vs now (ESTIMATE):** in 2023 the Árfigyelő ran under emergency government decrees. Since 2025-07-20 Act L 2025 §70 declares the non-archived data public by statute. That weakens a pure "unauthorised data use" objection against an accurate, clearly independent app. It does not weaken objections to impersonation, branding or inaccuracy.

## 5. Act L of 2025, Chapter V — VERIFIED https://njt.jog.gov.hu/jogszabaly/2025-50-00-00 (time state 2026.10.01.)

- §55 1-2: "archiválás" means placing data in a dataset kept separate from the system that gives public access. "Archivált adat" is data held in that archive. §55 5 "napi ár", 7 "termék azonosításához szükséges adat" (category, brand, barcode, packaging and other data set by ministerial decree), 10 "korábbi ár".
- §56: purpose. The system is run to support competition (Tpvt §11 and §21, TFEU 101–102) and consumer protection.
- §57(1)-(2): registers retailer, store name and address, product ID data, daily price, previous price and loyalty price, **per retailer and per store**. §57(4): archiving on the day after a change. **§57(5): GVH gives access to archived data only to** listed ministers, courts, consumer authorities and KSH. §57(6): deletion after 10 years.
- §59: obligated retailers are those with consolidated net revenue above **HUF 100,000,000,000** from retail trade in the previous closed business year.
- §66(1): daily upload by the end of the day before the price applies. §66(5): products on sale for one month or less are exempt.
- **§70:** "Az árfigyelő rendszer elektronikus nyilvántartás, az abban nyilvántartott, nem archivált adatok nyilvánosak. A Gazdasági Versenyhivatal biztosítja az árfigyelő rendszerhez való hozzáférést."
- §71: fines on retailers. §72: ministerial decree power.
- COMPUTED: 0 amendment footnote markers in §55–§72.

**Question 3: may a third party store and publish its own price history from daily snapshots?**
- **Act L 2025 contains no rule on third-party reuse, attribution, storage or republication.** Its archive and access limits (§57(4)-(6)) bind the operator of the system. They do not bind a member of the public who kept a copy of data that was public on the day. VERIFIED absence, after reading §55–72.
- **No attribution or form requirement** for republication exists in Act L. VERIFIED absence. Attribution duties could arise only from:
  - an Act CI agreement (§69(4)(f), which must meet the §69(5) tests);
  - the ÁFF XIV.2 limit on brand content;
  - general consumer law (Fttv) on not misleading.
- ESTIMATE on residual risks for a self-built history:
  - (i) **Database right.** Under Szjt. 84/A(1), (3) and (5) (VERIFIED, https://njt.jog.gov.hu/jogszabaly/1999-76-00-00, time state 2026.01.01), systematic daily extraction of the whole catalogue is extraction and re-utilisation of a substantial part, if GVH is a "maker" with substantial investment. Act CI §65(4) bars GVH from exercising that right only **when providing data under a request**. Directive 2019/1024 Art 1(6) is broader, and Hungarian courts should read national law in conformity with it. **Moderate-to-low risk; an agreement removes it.**
  - (ii) **TDM exception.** Szjt 84/D(2) with 35/A(1) (VERIFIED) frees *extraction* for text and data mining if access is lawful and there is no machine-readable opt-out. The Árfigyelő has none. Copies may be kept only as long as TDM needs them. This covers analytics such as cheapest-store calculations. It does **not** cover republishing raw prices or keeping a long history.
  - (iii) **Fttv.** Showing an old price as current, or "was/now" claims built on the app's own history, could mislead. Label dates and keep history out of discount claims.
  - (iv) **Policy risk.** The legislature chose authority-only access to the archive (§57(5)). A public third-party archive is lawful under current law, but it could attract a legislative fix if prices are re-politicised. Telex 2026-10-08 already floated a "transparency helps collusion" argument.

## 6. Competitors: attribution and permission claims — VERIFIED (pages fetched 2026-10-12)

| App | Where | What it says about GVH data | Claims permission or agreement? |
|---|---|---|---|
| **NomNom** (Z Gen Kibernetika Kft.) | https://nomnomplanner.com/hu/ (FAQ section) | "A NomNom magyar árai a Gazdasági Versenyhivatal hivatalos Árfigyelőjéből és bolti katalógusokból jönnek." The feature tile reads "Hivatalos áradat – GVH Árfigyelő, Magyarország nyilvános ármonitora". FAQ answer: "A GVH hivatalos Árfigyelő programjából és bolti katalógusadatokból." | **No.** The Terms of Use (https://nomnomplanner.com/terms/, effective 16 August 2026) and the privacy page do not mention GVH. They say prices "are estimates based on periodically collected data". The app is live on iOS (App Store HU, launched 2026-07-23 per the market-user stream) and its terms mention Android. ESTIMATE: it passed Apple review with openly attributed GVH data. |
| **Árnéni** | https://arneni.com/terms ("Hatályos: 2025. január 1-jétől · Módosítva: 2026. március 27.") | §3 Adatforrások: "A Gazdasági Versenyhivatal (GVH) Árfigyelő rendszere (arfigyelo.gvh.hu)", alongside retailer sites and Kifli. Footer: "Az áradatok nyilvános forrásokból származnak, beleértve a GVH Árfigyelő rendszert…" | **Expressly no:** "Az Árnéni nem áll hivatalos kapcsolatban ezen adatforrásokkal, és nem állítja, hogy általuk jóváhagyott vagy támogatott szolgáltatás lenne." Ironically, §8 bans users from scraping Árnéni's own database and invokes Directive 96/9/EC. Árnéni is UK-based: UK law governs and the operator is "Egyesült Királyságban bejegyzett vállalkozás". |
| **Cashmap** (Cashmap Kft.) | ÁSZF https://cashmap.hu/dokumentumok/aszf, GYIK, adatvédelmi | ÁSZF §6: ranking by "a Szolgáltató rendszerébe kerülő ár, melyeket a Szolgáltató szerez be és dolgoz fel különféle adatforrásokból". "Árfigyelő" appears only as an option in the price-error report dropdown, next to the store names. **No GVH attribution** in the ÁSZF, GYIK or privacy notice. | **No.** |
| **Lefőzlek** | https://www.lefozlek.hu/ (home, /aszf, /adatkezeles, /segitseg, /rolunk, a recipe page and the public JS bundle) | Recipes with "árbecslés (bolti árak alapján)", a weekly meal plan ("Heti étrend") and a shopping list with "Becsült kosárérték · bolti árak alapján". **No mention of GVH or Árfigyelő anywhere checked.** Its price source is undisclosed. | **No.** |

Takeaways (ESTIMATE):
- Nobody in the market claims a GVH agreement. The norm is attribution plus a disclaimer of affiliation (Árnéni's wording is the best model).
- NomNom's "Hivatalos áradat" label leans on GVH's authority. It is accurate (the data are official) but close to the line under Google Play's affiliation rule. Avoid "hivatalos" near your own brand.
- Lefőzlek is a **direct concept competitor**: recipes, weekly plan, shopping list and per-ingredient price estimate.

## 7. App stores — VERIFIED quotes

Apple App Review Guidelines (https://developer.apple.com/app-store/review/guidelines/, "Last Updated: June 8, 2026"):
- **5.2.2:** "If your app uses, accesses, monetizes access to, or displays content from a third-party service, ensure that you are specifically permitted to do so under the service's terms of use. Authorization must be provided upon request."
- **5.2.1:** "Don't use protected third-party material such as trademarks, copyrighted works, or patented ideas in your app without permission, and don't include misleading, false, or copycat representations, names, or metadata in your app bundle or developer name."
- **4.1(b):** "Submitting apps which impersonate other apps or services is considered a violation of the Developer Code of Conduct and may result in removal from the Apple Developer Program."

Google Play Policy Center (fetched 2026-10-12):
- Intellectual Property (https://support.google.com/googleplay/android-developer/answer/9888072): "You must ensure that all content in your app and store listing is either your own original work or that you have the necessary licenses and/or permissions to use it." Also: "If you have written documentation proving that you have permission to use a third party's intellectual property … contact the Google Play team in advance of your submission".
- Deceptive Behavior / Misleading Claims (https://support.google.com/googleplay/android-developer/answer/9888077): disallows "Apps that falsely claim affiliation with a government entity or to provide or facilitate government services for which they are not properly authorized." Do: "Get all necessary permissions and rights before claiming to be an "official" app."
- Impersonation (https://support.google.com/googleplay/android-developer/answer/9888374): "Don't imply that your app is related to or authorized by someone that it isn't." One example given is "The app is using a national emblem and misleading users into believing it is affiliated with government."
- There is no Google rule that specifically requires a licence to display public government data. The tests are IP, affiliation and impersonation.

**What proof of permission a public-data app needs (ESTIMATE):**
- Apple 5.2.2 is triggered by "content from a third-party service". GVH's "terms of use" are the visitor ÁFF. It grants use to "bárki" (anyone, V.4) and limits brand content to informational use (XIV.2). The data are public by statute (§70). It says nothing on apps or APIs.
- If asked, a defensible authorization pack would be:
  - (1) an English translation of Act L 2025 §70 with the njt link;
  - (2) ÁFF V.2, V.4, XII.4 and XIV.2 excerpts;
  - (3) a statement that the app shows no GVH branding and no retailer images or logos, and is "independent, not affiliated";
  - (4) ideally a **GVH letter or an Act CI re-use agreement**, which is the only document that fully answers "specifically permitted";
  - (5) for Google, the same pack, sent proactively per the IP policy if any retailer names or logos are shown.
- Evidence that review does not block in practice: NomNom (iOS) and Cashmap (iOS and Android) are live with GVH-derived data.
- The real exposure is a **GVH or retailer complaint** that triggers an authorization request after launch, which is how the 2023 case went. Without a GVH document, the outcome would depend on Apple accepting the statutory argument.

## 8. GVH institutional situation after 2026-09-28 — VERIFIED unless marked

- 2026-09-28: Telex G7 "gvh-elnok-elnokhelyettes-lemondas-level" exists on the Telex GVH tag page (https://telex.hu/cimke/gvh). Content per the legal stream: 7 Competition Council members and 11 managers called on the leaders to resign.
- **2026-09-29 GVH statement** (https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2026-os-sajtokozlemenyek/a-gazdasagi-versenyhivatal-kozlemenye): the president ordered an independent organisational audit by external experts into "belső munkahelyi konfliktusok", and says GVH "további információt az ügyben nem közöl" until the audit ends.
- **2026-10-05 Telex/G7** (Jandó Zoltán, https://telex.hu/g7/kozelet/2026/10/05/gvh-atalakitas-kormany-tervek-atvilagitas):
  - Main option: "a GVH más szervezetekkel történő összevonása". Most sources name the **Közbeszerzési Hatóság**, a merger the president himself had floated earlier.
  - An alternative is a legislated removal of leaders, on the media-authority model.
  - The sources are **anonymous**. There is **no bill** and the timeline is "hosszú folyamat" (a long process). The government has consulted sector players since summer about amending the competition act.
  - **The Árfigyelő and consumer protection are not mentioned.**
- 2026-10-05 HVG (https://hvg.hu/kkv/20261005_gvh-belso-feszultseg): internal tension. No resignations, no merger plan, no bill, no Árfigyelő mention.
- 2026-10-10 Telex/G7 op-ed (Csorba Gergely): no restructuring facts.
- GVH keeps operating normally. Press releases on 2026-10-07 and 2026-10-12 (proceeding on the Déli Körvasút) are in the GVH 2026 list (COMPUTED from the listing page).
- **Statutes:**
  - Tpvt on njt (time state **2026.09.27.**) shows 2026 amendments only by 2026. évi XVIII (§95/O asset declarations of GVH leaders) and XXXIV (wording). No merger provision (COMPUTED by grepping the footnotes).
  - Act L 2025 Chapter V is unchanged at time state 2026.10.01. VERIFIED.
- **Conclusion (ESTIMATE):** nothing since 2026-09-28 has changed the Árfigyelő's operator. A merger would most plausibly transfer the Árfigyelő to the successor body by statute.
  - Practical effects: a pending re-use request may stall during the transition; the endpoints or domain may change; an agreement must name "the operator of the árfigyelő rendszer and its legal successor".
  - My probability of an operator or leadership change within 12–24 months stays at roughly **35–55%**, the legal stream's estimate, which I do not revise.

---

## 9. Risk matrix

See `risk_matrix.csv` (same rows).

| # | Risk | Likelihood | Impact | Basis | Label | Mitigation |
|---|---|---|---|---|---|---|
| 1 | Republishing current Árfigyelő prices is itself unlawful | Low | High | Act L §70 public; Act CI §1(3)(a) dissemination outside Act CI; Alaptörvény VI(3) | VERIFIED law / ESTIMATE conclusion | Attribute the source; show only non-archived data as current |
| 2 | GVH objects to an *accurate, clearly independent* app | Low–Medium | High | No GVH action found against Árnéni, NomNom or Cashmap; 2023 case involved impersonation and false prices | ESTIMATE | Árnéni-style non-affiliation text; no GVH marks; file the Act CI request |
| 3 | Impersonation or branding triggers takedown (2023 pattern) | High if done / Low if avoided | Critical | GVH 2023-08-05 release; Apple 4.1(b), 5.2.1; Google Impersonation | VERIFIED | Never use "Árfigyelő", the GVH logo or a lookalike UI in the name or icon |
| 4 | Product images or retailer brand assets infringe | Medium–High | Medium | ÁFF XIV.2; Act CI §2(36), §65(3)(b) | VERIFIED | No GVH-hosted images; own icons; text brand names only, descriptively |
| 5 | Database-right claim over systematic API extraction without agreement | Low–Medium | Medium | Szjt 84/A(1),(3),(5); Act CI §65(4) only in the request context; Dir. 2019/1024 Art 1(6) | VERIFIED law / ESTIMATE risk | Get an agreement; cache; low request rate; never resell raw data |
| 6 | Formal request refused | Low | Medium | §66(3) exhaustive grounds; §72(1) burden on GVH | VERIFIED | Ask only for non-archived, non-image data |
| 7 | Formal request stalls or is slow | Medium–High | Medium | Kataszter down; GVH page still cites repealed act; leadership turmoil; NAVÜ forwarding time not fixed | VERIFIED facts / ESTIMATE likelihood | File now; calendar the 5/20/20/10 WD deadlines; parallel informal letter to GVH |
| 8 | Agreement imposes attribution, rate limits, no images or no-endorsement terms | High (expected) | Low | §69(4)(f), §69(5): conditions must be public-interest, objective and proportionate | VERIFIED law / ESTIMATE content | Accept; build attribution in from day one |
| 9 | Agreement gives no exclusivity; competitors get the same terms | Certain | Low–Medium | §6, §7, §66(5), §7(5) | VERIFIED | Compete on health and planning features, not on data access |
| 10 | Fee is significant | Low | Low | §67(3) marginal-cost cap; §67(4) unlikely for GVH | VERIFIED cap / ESTIMATE | Ask for the fee factors (§5(2)) |
| 11 | Self-built price history challenged | Low–Medium | Medium | No ban in Act L; §57(5) binds the operator; DB right; Fttv | VERIFIED absence / ESTIMATE | Date-stamp; no "was/now" discount claims; keep history internal at first |
| 12 | GVH will not supply history or archive | Certain | Medium | §57(5); Act CI §38(c), §65(3)(c) | VERIFIED | Start snapshotting on day 1 (risk 11 applies) |
| 13 | Apple or Google ask for 5.2.2 authorization and reject the statutory argument | Low–Medium | High | 5.2.2 "Authorization must be provided upon request"; NomNom and Cashmap live | VERIFIED rule / ESTIMATE | Prepare the authorization pack; a GVH letter or agreement is best |
| 14 | Operator change (merger or successor) disrupts endpoints or agreement | Medium (35–55% in 12–24 months) | Medium | G7 2026-10-05 (anonymous, no bill); GVH audit 2026-09-29 | VERIFIED news / ESTIMATE probability | Successor clause; endpoint abstraction; fallback sources |
| 15 | Publicity reduced (delay or aggregation) for policy reasons | Low–Medium | High | Telex 2026-10-08 collusion argument; Chapter V is ordinary law | ESTIMATE | Fallback data plan (retailer feeds, leaflets, partnerships) |
| 16 | Undocumented API changes or gets blocked | Medium–High | High | No published API or terms; robots absent | ESTIMATE | Request a documented API (§37(3)); monitor; degrade gracefully |
| 17 | Misleading price display (Fttv) | Medium | Medium | GVH 80%-of-stores rule; regional prices exist; ÁFF XII.7 | VERIFIED facts / ESTIMATE | Label "GVH-adat, [dátum]"; note "üzletenként eltérhet" |

## 10. Draft request text (for the founder to file HIMSELF; I did NOT submit anything)

See `request_draft_hu.txt`. It covers every Act CI §64(1) element. Placeholders are in [brackets]. A suggested informal companion letter to GVH is included.

## Open questions
- Is the Árfigyelő (or anything from GVH) registered in the Nemzeti Adatvagyon Leltár or Közadatkataszter? The Kataszter was offline on 2026-10-12. Recheck later, or ask igenykezeles@navu.hu.
- Which values does the SZÜF "Szolgáltatás típusa" dropdown offer? It is visible only after login.
- Was the 2023 copycat app removed, and did the criminal complaint go anywhere? This needs a news search (budget exhausted) or an Infotv request to GVH.
- Will GVH treat its existing public endpoints as covered by Act L §70 (no agreement needed) or require an Act CI agreement for bulk use? Only GVH can answer, which is a reason to file.
- How long does NAVÜ take to forward a request to GVH? Not regulated; ask NAVÜ.
- Does any bill on restructuring the GVH appear on parlament.hu after 2026-10-12? Not checked (search budget).

## Sources (opened 2026-10-12)
- https://njt.jog.gov.hu/jogszabaly/2023-101-00-00 (Act CI 2023, time state 2026.01.01.)
- https://njt.jog.gov.hu/jogszabaly/2024-250-20-22 (250/2024 Korm. r., time state 2025.06.11.)
- https://njt.jog.gov.hu/jogszabaly/2025-50-00-00 (Act L 2025, time state 2026.10.01.)
- https://njt.jog.gov.hu/jogszabaly/2011-112-00-00 (Infotv, time state 2026.10.01.)
- https://njt.jog.gov.hu/jogszabaly/1999-76-00-00 (Szjt, time state 2026.01.01.)
- https://njt.jog.gov.hu/jogszabaly/1996-57-00-00 (Tpvt, time state 2026.09.27.)
- https://kozadatportal.hu/ , /publicdata , /dataset/?q=árfigyelő , /dataut , /news , /robots.txt
- https://kozadatportal.hu/pdf/utmutato_adathasznositas.pdf?ver=2
- https://magyarorszag.hu/szuf_ugyleiras?id=0b70cf76-26f7-4313-831a-07b2fc1c71ec
- https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2023-as-sajtokozlemenyek/csalokra-figyelmeztet-a-gvh
- https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2023-as-sajtokozlemenyek (pages 1–7)
- https://www.gvh.hu/dontesek/versenyhivatali_dontesek/dontesek-2023 , -2024 , -2025 (all pages)
- https://www.gvh.hu/kozerdeku_adatok/tevekenysegre-mukodesre-vonatkozo-adatok/kozerdeku_adatok_igenylese
- https://www.gvh.hu/kozerdeku_adatok/tevekenysegre-mukodesre-vonatkozo-adatok/a_gvh_nyilvantartasai
- https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2026-os-sajtokozlemenyek ; https://www.gvh.hu/sajtoszoba/sajtokozlemenyek/2026-os-sajtokozlemenyek/a-gazdasagi-versenyhivatal-kozlemenye
- https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_latogato.pdf ; https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf ; https://arfigyelo.gvh.hu/robots.txt
- https://telex.hu/belfold/2023/08/05/gvh-figyelmeztetes-kalozapplikacio-arfigyelo
- https://telex.hu/g7/kozelet/2026/10/05/gvh-atalakitas-kormany-tervek-atvilagitas ; https://telex.hu/g7/kozelet/2026/10/10/hallgato-szakemberek-felelossege-verseny-csokkenese-gvh-versenytanacs ; https://telex.hu/cimke/gvh
- https://hvg.hu/kkv/20261005_gvh-belso-feszultseg
- https://nomnomplanner.com/hu/ ; https://nomnomplanner.com/terms/ ; https://nomnomplanner.com/privacy/
- https://arneni.com/terms
- https://cashmap.hu/dokumentumok/aszf ; https://cashmap.hu/GYIK ; https://cashmap.hu/dokumentumok/adatvedelmi
- https://www.lefozlek.hu/ ; /aszf ; /adatkezeles ; /segitseg ; /rolunk
- https://developer.apple.com/app-store/review/guidelines/
- https://support.google.com/googleplay/android-developer/answer/9888072 ; /9888077 ; /9888374
