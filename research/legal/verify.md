# Fact-check of the "Legal & regulatory risk" stream

Checker: adversarial verification subagent · Date: 2026-10-12
Input checked: `legal_notes.md` and the stream summary, findings and key numbers.
Method: I re-opened the primary sources myself instead of reading the stream's `dl/` copies. These were njt.jog.gov.hu, net.jogtar.hu, arfigyelo.gvh.hu PDFs, the Kifli PDF, the aldi.hu page, Apple's guidelines page and the GVH `/api/shops` endpoint. I also ran a quick curl test against the bot protection. My own downloads are in `verify_dl/` (untrusted data) and my scripts are in `verify_scripts/`. I used one request per resource with User-Agent `market-research-bot/0.1 (fact-check)` and pauses of 1 s or more between requests.
Labels: **VERIFIED** = I read it in the primary source (URL given) · **COMPUTED** = from data I pulled (method given) · **ESTIMATE** = my reasoning.
This is research, not legal advice.

---

## Headline result

**One load-bearing error.** The stream builds its "formal re-use request" route on **Act LXIII of 2012, but that act has been repealed.** The njt footnote reads: *"A törvényt a 2023. évi CI. törvény 104. § a) pontja hatályon kívül helyezte 2024. április 1. napjával."* (https://njt.jog.gov.hu/jogszabaly/2012-63-00-00; njt shows its last time state as 2022.12.20.) The rules now sit in **2023. évi CI. törvény a nemzeti adatvagyon hasznosításának rendszeréről és az egyes szolgáltatásokról**. That act is in force from 2024-04-01 per §101(4), and §105(1) states that it serves Directive (EU) 2019/1024 (https://njt.jog.gov.hu/jogszabaly/2023-101-00-00, time state 2026.01.01). Most of the substance survives, but the section numbers and the **procedure have changed**. A request must now be filed **on an electronic form via the Nemzeti Közadatportál (kozadatportal.hu, run by NAVÜ)**, not by email to arfigyelo@gvh.hu. The stream's step 1 in its next-steps list must be rewritten accordingly. Everything else I checked holds, apart from nuances and a few gaps listed below.

---

## 1. Act L of 2025, Chapter V: publicity, no sunset, ordinary law, unamended → **CONFIRMED**

VERIFIED from a fresh njt fetch (time state **2026.10.01.**, https://njt.jog.gov.hu/jogszabaly/2025-50-00-00):
- §70 is verbatim: "Az árfigyelő rendszer elektronikus nyilvántartás, az abban nyilvántartott, nem archivált adatok nyilvánosak. A Gazdasági Versenyhivatal biztosítja az árfigyelő rendszerhez való hozzáférést."
- No paragraph in Chapter V (§55–§72) has an amendment footnote. The 2026 amendments touch §86–87 (2026. évi XLIX.), Chapter X (2026. évi XXXV. §24) and §124/A.
- §125 lists the cardinal provisions: §1–5, §12, §14(1)(a)-(b), §15(1), §192–194 and subtitle 56. None of them is in Chapter V, so Chapter V is ordinary law.
- Footnote 1: adopted 2025-06-11, promulgated 2025-06-19. §124(1): in force on the 31st day after promulgation, which is 2025-07-20 (COMPUTED).
- Key numbers re-read in the text: §59 sets the threshold at HUF 100,000,000,000. §71(4) sets fines of a) HUF 3,000,000; b) HUF 25,000 per product, max HUF 3,000,000, if more than 10 products; c) HUF 50,000 per product. §57(5)-(6): authority-only access to the archive, deletion after 10 years. §66(5): products sold for ≤1 month need not be reported.
- The footnote to §124(4) says: "A 22/2026. (V. 15.) ME határozat a) pontja alapján a hatálybalépés időpontja 2026. május 14." This confirms the end of the emergency.

**Nuance the stream should add:**
- §57(2) makes the system register prices **per retailer and per store**. The §71(1)(c) fine compares the shelf price with the price registered *for that store*.
- The GVH headline "cheapest" price is the price applied in 80% of the chain's stores, and individual stores may be cheaper. VERIFIED in the GYIK: "a kereskedő üzleteinek 80%-ában alkalmazott termék árat veszi figyelembe ... az árak a kereskedő egyes üzleteiben ennél olcsóbbak is lehetnek" (https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf).
- The visitor ÁFF VIII.1 confirms that the site shows separate prices where regions or cities differ.
- Also from the GYIK: daily prices are public only on the day they apply.

## 2. The PSI / open-data re-use route → **PARTLY TRUE: the cited act is repealed, but the substance survives in Act CI of 2023**

| Stream's claim (Act LXIII 2012) | Status on 2026-10-12 | Current provision (Act CI 2023), VERIFIED |
|---|---|---|
| Formal written request (§10) | Route changed | §62(1)-(2): the request is lodged **via the Nemzeti Közadatportál on an electronic form**. §64(1): it must contain an express re-use statement, name and address, phone and e-mail, the exact data, format and technical means, and the frequency |
| Examined within 5 working days (§11(2)) | Same | §64(3) |
| Decision in 20 working days, extendable once by 20 (§13) | Same | §65(1)-(2) |
| DB-maker right not exercisable (§3/A) | Same, **but narrower wording** | §65(4): the public body (and the service provider) "nem gyakorolhatja ... az adatbázis előállítóját megillető jogokat" **when deciding on and making the data available** |
| Third-party IP excluded (§3 b)) | Same | §65(3)(b) |
| Legally restricted data excluded (§3 c)), so archived prices are out | Same | §65(3)(c) |
| No discrimination (§8) / no exclusivity (§9) | Same | §6 / §7 |
| Fee ≤ marginal cost (§15(2)) | Same, with an exception | §67(3). The §67(4) exception (cost plus reasonable return) is open only to bodies that must fund a significant part of their tasks from their own revenue |
| Re-use agreement whose conditions must be objective and non-restrictive (§17) | Same | §69(1), (4)-(5). §69(6)-(7): general terms may be published on the portal. The simplified and automated procedures (§69(2)-(3)) then apply |
| Court review within "10 days" (§18) | **10 working days** | §72(2). §72(1): the burden of proof is on the public body |
| Refusal grounds | Exhaustive list | §66(3): only "not available for re-use" or "data not held" |

- The portal is live: https://kozadatportal.hu/ returned HTTP 200 on 2026-10-12, with the title "Nemzeti Közadatportál".
- The ministerial approval mechanism (§8(2)(b), §25–27) applies to NAVÜ's own analysis services, not to a plain re-use request (VERIFIED by reading §25–27 and §62–72).
- **Practical consequence (ESTIMATE):** the formal re-use agreement is still the right de-risking step. But it should be filed through the portal and should cite Act CI 2023. Do not send an email citing Act LXIII 2012, because GVH could treat such an email as an Infotv. request for public-interest information instead (§64(3); compare §1(3)(a)).

## 3. "Daily prices are dynamic data, so GVH must offer an API" → **PARTLY TRUE, and weaker than stated**

- VERIFIED: Act CI 2023 §2(8) defines "dinamikus adat" as "gyorsan változó vagy gyorsan elavuló digitális formátumú közadat, **amelyet jellemzően valós időben frissítenek, ilyenek különösen a szenzorok által generált adatok**".
- §37(3): the provider must supply dynamic data by API immediately after collection.
- §40(2): a proportionality fallback allows a time lag or temporary technical limits.
- ESTIMATE: prices that change daily and expire daily fit "gyorsan elavuló". They do not fit the "typically real-time, sensor" archetype, so the argument is plausible but contestable. It is a negotiating argument, not an entitlement. The duty is also triggered only inside the re-use service (§35), so you first need a request.

## 4. Third-party IP is excluded, so no product images or brand content → **CONFIRMED**

- VERIFIED in the visitor ÁFF (effective 2025-07-20; https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_latogato.pdf, fresh copy) at XIV.2. The product image and image link count as "other identification data" under GFM rendelet Annex 2 b). The retailer warrants only the rights "melyek az árfigyelő rendszerről szóló törvényben meghatározottak teljesítéséhez szükségesek". Protected brand names and content "kizárólag a Honlap céljával összhangban (tájékozódás, tájékoztatás) használhatók fel. Az ettől eltérő célra való használathoz a jogtulajdonos előzetes hozzájárulása szükséges."
- The warranty sentence appears **in the visitor ÁFF itself**, not only in the merchant ÁFF.
- XIV.1: the system and website, including their structure, look, software and documentation, are under copyright.
- Act CI 2023 §65(3)(b) excludes third-party IP from re-use (replacing the old §3 b)).

## 5. The 2023 copycat-app precedent and Apple 5.2.2 → **CONFIRMED**

- VERIFIED from Telex (2023-08-05): GVH "nem adott engedélyt az illegális alkalmazás létrehozójának" to use the system's data and visual elements. GVH took civil and criminal steps, sought the app's removal, and opened an ex officio proceeding for consumer deception. The app was "megtévesztésig hasonlító" and showed "nem valós árinformációkat" (https://telex.hu/belfold/2023/08/05/gvh-figyelmeztetes-kalozapplikacio-arfigyelo).
- I found no GVH statement inviting third-party API use and no action against a distinct, accurate re-user (searches on 2026-10-12).
- VERIFIED, Apple App Review Guidelines (page "Last Updated: June 8, 2026"). 5.2.2: "If your app uses, accesses, monetizes access to, or displays content from a third-party service, ensure that you are specifically permitted to do so under the service's terms of use. Authorization must be provided upon request." 5.1.5: "notify and obtain consent before collecting, transmitting, or using location data" (https://developer.apple.com/app-store/review/guidelines/).
- ESTIMATE: the visitor ÁFF V.4 says "A Szolgáltatást bárki jogosult igénybe venni", but it says nothing about apps or automated reuse. A re-use agreement under Act CI is therefore the cleanest "authorization" to show Apple.

## 6. Political and institutional status → **CONFIRMED, but incomplete. The risk is higher than the stream implies.**

VERIFIED:
- Péter Magyar was sworn in on 2026-05-09 (AP, via WSLS/news4jax/Boston Globe). Tisza holds 141 of 199 seats, Fidesz-KDNP 52 and Mi Hazánk 6.
- GVH president Rigó Csaba Balázs was reappointed from 2026-04-15 for his **second** six-year term, on the proposal of the then (outgoing) PM, three days after the election. The stream omits that detail. Economx 2026-06-17 confirms the refusal to resign (https://www.economx.hu/gazdasag/2026/06/17/lemondas-helyett-turk-tanacs-gvh-elnoke-nav/).
- Telex 2026-10-08 (Brückner Gergely) says it is unclear whether there is any intention to change the GVH Árfigyelő site. The same article also argues that the Árfigyelő together with the margin cap has made the big chains' prices transparent and "nivellálódtak", and calls the arrangement a state-built legal "kartell" in the sense of an information exchange (https://telex.hu/gazdasag/2026/10/08/elelmiszer-aldi-lidl-tesco-spar-auchan-penny-market-kisbolt-zoldseg-gyumolcs).

**Missed by the stream (VERIFIED):**
- On 2026-09-28, **7 members of the Competition Council and 11 professional middle managers** signed a letter calling on the GVH president and deputy presidents to resign. Deputy president Bak László reportedly signalled that he would resign (https://index.hu/belfold/2026/09/28/gazdasagi-versenyhivatal-lemondas-vezetoseg/).
- G7/Telex on 2026-10-05 (Jandó Zoltán) reported that the government is weighing a GVH restructuring. The option most often mentioned is a **merger with the Közbeszerzési Hatóság**, which would allow new leadership. The government has also asked for ideas on rewriting the competition act. No bill or timeline exists, and the Árfigyelő is not mentioned (https://telex.hu/g7/kozelet/2026/10/05/gvh-atalakitas-kormany-tervek-atvilagitas).

**ESTIMATE (revised):**
- Outright repeal of Chapter V within 12 months: I keep the stream's ~10–20%.
- An institutional change of the operator, such as a merger, new leadership or a transfer to a ministry, within 12–24 months: **~35–55%**. This has a knock-on effect on any agreement or API.
- The "transparency facilitates tacit collusion" framing in Telex is a policy argument that could justify reduced publicity, such as delayed or aggregated publication. It deserves monitoring.
- Mitigation: draft any re-use agreement to bind "the operator of the árfigyelő rendszer and its legal successor". Keep a fallback data roadmap.

## 7. Retailer terms, bot protection and Btk. 423 → **CONFIRMED, with scope nuances**

- **Kifli** ÁSZF "Hatályos: 2026. szeptember 26. napjától" (PDF re-downloaded and read). Clause 3(c) is verbatim: "nem szerzi meg, követi nyomon vagy másolja az Online Shop tartalmait vagy információit sem automatizált eszközökkel, sem manuálisan, a Kifli.hu előzetes írásos engedélye nélkül". Clause 3(d) adds no circumvention and no undue load. §11 claims rights in the databases. §3 says prices depend on the delivery address and warehouse.
- **Nuance:** these duties bind the **"Vásárló"**, meaning registered buyers who accept the ÁSZF when ordering (§1). An anonymous non-buyer is not clearly bound by contract (Ryanair logic). Database-right and unfair-competition claims remain.
- Kifli also states (§4.10) that sponsored products are labelled.
- **Aldi** (aldi.hu, "Hatályos: 2022. április 20-tól"). Clause 1.5 is verbatim as quoted. **Nuance:** §1.1 scopes the terms to the account and account features, and states that reading content "regisztráció nélkül is lehetséges". Acceptance runs "bármely ALDI szolgáltatás használatával". It is therefore uncertain that clause 1.5 binds an anonymous reader of product pages, but it clearly binds account users.
- **Tesco / Spar bot protection** (COMPUTED: one request each on 2026-10-12 with a self-identifying bot User-Agent):
  - bevasarlas.tesco.hu returned **403** "Access Denied" with `server: AkamaiGHost`.
  - tesco.hu/bevasarlas/…feltetelek.html returned **403** "Access Denied".
  - www.spar.hu returned **403** "Just a moment..." with `server: cloudflare`.
  - I did not test with a browser User-Agent, on purpose, so as not to approach circumvention.
- **Btk.** (net.jogtar, Hatály 2026.X.1.–). 423(1) is a misdemeanour with up to 2 years. 423(2) is a felony with up to 3 years. The stream omitted two further rules:
  - **423(3):** 1–5 years if the (2) offence affects a significant number of systems or causes significant harm.
  - **424(1):** up to 2 years for making, obtaining or distributing a password or **program** for committing 423, which is relevant to any bypass tooling.
- Whether a bot challenge counts as a "technical measure" has not been tested in court. This is an ESTIMATE, as the stream also says.

## 8. Location: Eht. 155(4) has no "strictly necessary" exemption, and the store list is small → **CONFIRMED**

- VERIFIED from the full Eht text (net.jogtar, Hatály 2026.X.1.–). 155(4) is a single sentence with no carve-out. 155(5) is about investigative authorities and was rewritten in 2026 (XLVI). A search of the whole act for "feltétlenül szükséges" / "kifejezetten igényel" found no terminal-equipment exemption.
- **Nuance:** Ekertv. 13/A(3) allows processing of personal data "amelyek a szolgáltatás nyújtásához technikailag elengedhetetlenül szükségesek" (https://njt.jog.gov.hu/jogszabaly/2001-108-00-00). This is a data-processing basis, not an Art. 5(3)-style exemption. Practical conclusion: ask for consent anyway (the OS prompt plus an explainer). This does not change the design.
- **COMPUTED:** one GET of https://arfigyelo.gvh.hu/api/shops on 2026-10-12 returned HTTP 200.
  - 415,968 bytes and **1,829 shops**, matching the stream.
  - 9 distinct chainStoreUuid values, 0 entries missing a location.
  - **419** entries whose city starts with "Budapest".
  - Python gzip at level 9 gives **47,751 bytes**. The stream's 52,191 B is plausible for default or HTTP compression; either way the size is about 50 KB.
  - Fields: uuid, postalCode, city, address, chainStoreUuid, location, openingTime. No personal data.

---

## Other spot checks (confirmed, not counted among the 8)

- **Fttv.** (njt time state 2026.10.01.):
  - §7(7) on ranking parameters is verbatim as summarised.
  - Annex 1 point 32 bans undisclosed paid ranking.
  - §9(1): liable is the business "amelynek a kereskedelmi gyakorlattal érintett termék értékesítése, eladásának ösztönzése közvetlenül érdekében áll".
  - **New since the EmpCo transposition, §7(9):** if a service compares products' **environmental or social** characteristics, its method, scope and update measures are material information. This is relevant if the app ever shows "eco/bio/sustainable" comparisons.
- **GVH GYIK:** the 9 obligated chains have been listed since 2025-06-01.

---

## Important things the stream missed

1. **Statute swap (high impact):** Act LXIII 2012 has been repealed (from 2024-04-01) and replaced by Act CI of 2023. Requests go through the Nemzeti Közadatportál; see item 2.
2. **The narrower database-right waiver (ESTIMATE, from the text):** Act CI §65(4) bars GVH from using its database-maker right *when making data available on a request*. Outside the re-use procedure, for example when bulk-pulling the undocumented API without an agreement, GVH's sui generis right in the Árfigyelő database (if it qualifies under Szjt. 84/A) is arguably still enforceable against systematic extraction. Act CI §1(3)(a) leaves the dissemination right of public data (Infotv. / Alaptörvény VI(3)) outside the act. This strengthens the case for getting the agreement before launch, not after.
3. **GVH institutional turmoil:** the internal revolt of 2026-09-28 and the merger option reported on 2026-10-05. Any agreement should cover legal successors; see item 6.
4. **Health data under GDPR Art. 9:** a meal planner that records allergies, intolerances (gluten-free or lactose-free), diabetes, pregnancy or weight-loss goals processes *data concerning health* (GDPR Art. 4(15)). Religious diets such as halal or kosher can reveal religious belief. Either needs **explicit consent** (Art. 9(2)(a)), probably a **DPIA** (Art. 35), minimisation and on-device storage where possible. The stream covers only location data.
5. **Medical-device boundary:** disease-specific diet plans (for diabetes, kidney disease or IBS, for example) can turn software into a medical device under Regulation (EU) 2017/745 (MDCG 2019-11 qualification guidance). Stick to general healthy eating. (Legal pointer; not re-verified today.)
6. **AI Act Art. 50:** if the app uses an AI chatbot or AI-generated recipes or plans, the transparency duties apply from 2026-08-02. Secondary sources say the Digital Omnibus on AI (Reg. (EU) 2026/1744) did not delay Art. 50, except for a grace period to 2026-12-02 on Art. 50(2) marking for systems already on the market. **Unverified against the OJ text.**
7. **Ekertv. information duties:** an app operator is an information-society service provider and must publish its identification data (Ekertv. §4(1)). Aldi's terms cite exactly this provision.
8. **Btk. 423(3) and 424** (tools for circumvention); see item 7.
9. **Contract scope of retailer ToS:** Kifli's ban binds registered buyers, and Aldi's terms are scoped to account services. That lowers *contract* risk for anonymous reading, but not the database-right, unfair-competition, Apple 5.2.2 or reputational risks. The recommendation (partnerships, no scraping) stands.
10. **Competitive note found in the Kifli ÁSZF §2.5:** Kifli's AI assistant "Maia" already "segíthet az étkezések megtervezésében" and can fill the basket. A large online grocer already offers meal-planning help, which matters for the founder's positioning.
11. **Fttv. §7(9) (EmpCo)** applies if sustainability comparisons are added.

## Sources (opened by me on 2026-10-12)
- https://njt.jog.gov.hu/jogszabaly/2025-50-00-00 (time state 2026.10.01.)
- https://njt.jog.gov.hu/jogszabaly/2012-63-00-00 (repeal footnote; last time state 2022.12.20.)
- https://njt.jog.gov.hu/jogszabaly/2023-101-00-00 (Act CI 2023, time state 2026.01.01.)
- https://kozadatportal.hu/
- https://njt.jog.gov.hu/jogszabaly/2008-47-00-00 (Fttv., time state 2026.10.01.)
- https://njt.jog.gov.hu/jogszabaly/2001-108-00-00 (Ekertv.)
- https://net.jogtar.hu/jogszabaly?docid=a0300100.tv (Eht., Hatály 2026.X.1.–)
- https://net.jogtar.hu/jogszabaly?docid=a1200100.tv (Btk., Hatály 2026.X.1.–)
- https://arfigyelo.gvh.hu/docs/arfigyelo_rendszer_AFF_latogato.pdf ; https://arfigyelo.gvh.hu/docs/arfigyelo_GYIK.pdf
- https://arfigyelo.gvh.hu/api/shops
- https://cdn-kifli.s3.eu-central-1.amazonaws.com/files/terms/260926_A%CC%81ltala%CC%81nos+Szerzo%CC%8Bde%CC%81si+Felte%CC%81telek_final_HU.pdf
- https://www.aldi.hu/customer-services/felhasznalasi-feltetelek
- https://developer.apple.com/app-store/review/guidelines/
- https://telex.hu/belfold/2023/08/05/gvh-figyelmeztetes-kalozapplikacio-arfigyelo
- https://telex.hu/gazdasag/2026/10/08/elelmiszer-aldi-lidl-tesco-spar-auchan-penny-market-kisbolt-zoldseg-gyumolcs
- https://telex.hu/g7/kozelet/2026/10/05/gvh-atalakitas-kormany-tervek-atvilagitas
- https://index.hu/belfold/2026/09/28/gazdasagi-versenyhivatal-lemondas-vezetoseg/
- https://www.economx.hu/gazdasag/2026/06/17/lemondas-helyett-turk-tanacs-gvh-elnoke-nav/
- https://www.wsls.com/news/2026/05/09/hungarys-peter-magyar-is-set-to-be-sworn-in-as-prime-minister-ending-viktor-orbans-16-year-rule/
