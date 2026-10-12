# Adversarial fact-check: "Alternative price sources (scrape / partner / buy)"

Checked on 2026-10-12 by the fact-check sub-agent. Primary sources were re-opened independently.

Labels:
- **VERIFIED**: read on the primary source today; URL given.
- **COMPUTED**: derived from data pulled today; method given.
- **ESTIMATE**: my reasoning.

Method and limits:
- Raw files are in `verify_dl/` (untrusted data) and scripts in `verify_scripts/`. Python ran with `-I`.
- All requests used the UA `market-research-bot/0.1 (fact-check)`, spaced at 1 request per second or slower. About 20 GVH API calls were made in total.
- **Limit:** the shared WebSearch budget ran out early in this check. Items that needed a fresh web search are marked unverifiable or left open. Everything else was checked by fetching primary pages directly.

---

## Verdicts (8 load-bearing items)

### 1. GVH acted against a third-party app using Árfigyelő data (Aug 2023): CONFIRMED, but the risk is framed too strongly

**VERIFIED** (Telex and Pénzcentrum, 2023-08-05):
- The app was described as "megtévesztésig hasonlító" (deceptively similar) to Árfigyelő.
- GVH said it gave no permission to use the system's data or "egyes arculati elemeinek" (some of its visual-identity elements).
- GVH took civil and criminal steps, asked for removal from the stores, and opened an ex officio consumer-deception case.
- GVH also said the app showed unreal prices and posed security risks.
- Neither article names the app or mentions money charges.
- No outcome of the case was found. My search budget ran out before I could look for later reports.

**Context the stream under-weights:**
- The 2023 case concerned **impersonation plus inaccurate data**, under the pre-2025 legal regime.
- Since 2025 the publicity of the data is **statutory**, not just in the ÁFF. Act L of 2025 **§70**: "az abban nyilvántartott, nem archivált adatok nyilvánosak. A Gazdasági Versenyhivatal biztosítja az árfigyelő rendszerhez való hozzáférést." VERIFIED at https://njt.hu/jogszabaly/2025-50-00-00.
- **Counter-evidence: Cashmap** has been live since **2023-09-10**, one month after the warning, and is still updated (2026-07-03). Its error-report form lists "Árfigyelő" as a data source. No GVH action against it was found, but I could not search for one. See Missed #3.

**Corrected statement:** GVH acted in 2023 against a look-alike app that copied Árfigyelő's design and showed inaccurate prices. The precedent shows that impersonation and misrepresentation are the red lines. Since 2025, non-archived Árfigyelő data are public by statute (Act L of 2025 §70). Third-party apps such as Cashmap and Árnéni have reused the data openly for years with no reported action. Written GVH confirmation is still advisable. The formal route is a re-use request under Act LXIII of 2012 (see item 2).

### 2. GVH Árfigyelő is the only viable MVP backbone: CONFIRMED, with important additions

Re-checked live today (COMPUTED from the GVH API):
- `/api/shops`: **1,829 stores**, all with latitude/longitude. **418 are in Budapest**: Spar 114, dm 75, Rossmann 55, Aldi 48, Lidl 46, Tesco 39, Penny 30, Müller 6, Auchan 5. That makes **282 food-chain stores** in Budapest. GVH press said 1,817 stores; today's count is higher.
- 9 chains appear in `/api/chain-stores`.
- `/product/{id}/shop/{storeId}` returns per-store prices (tested on 4 Auchan stores).
- In a sample of 10 staple categories (124 chain-price entries), **10 (8%) had priceSameEverywhere=false; 9 of those 10 were Tesco** (9 of 29 Tesco entries).
- `arfigyelo.gvh.hu/robots.txt` returns the SPA HTML page, so there is no robots file. The API answered 200 with no auth.

Additions (VERIFIED, Act L of 2025, Chapter V, njt.hu):
- §66(1): retailers must upload daily prices by the end of the day **before** the price applies. "Daily" is statutory.
- **§57(4)–(5): archived data (price history) are NOT public.** Only ministers, courts, the NKFH and consumer authorities, and **KSH** get access. The app must build its own history from daily snapshots. No back-fill from GVH is possible.
- §55(5) and §57(3): the "napi ár" is the lowest price publicly available to every consumer. Markdowns because of expiry within 72 hours are excluded, so clearance prices never appear.
- §57(1)(bc): the loyalty price is recorded only if it is lower than the daily price, and coupon or multi-buy prices are excluded.
- §59: only retailers with consolidated net revenue above HUF 100 bn are obliged. §61: others may join voluntarily, which is a lever for CBA or Coop.
- **Act LXIII of 2012 on the re-use of public data** (VERIFIED https://njt.hu/jogszabaly/2012-63-00-00) gives a formal, enforceable route that the stream missed:
  - §10: a written re-use request must contain an explicit re-use declaration, the data, the format and the frequency.
  - §13: decision within 20 working days, extendable once by 20.
  - §14(3): refusal only on listed grounds, and it must be reasoned.
  - §15(2): fee at most marginal cost.
  - **§3/A: the public body may not exercise database-maker rights.**
  - Caveats: §3(b) excludes content protected by third-party copyright, which likely covers **retailer-supplied product images**, and §3(f) excludes logos.

**Corrected statement:** GVH is the only open, store-level, daily and geolocated multi-chain source. Its current data are public by statute. History is not public, so the app must snapshot daily. Use a formal re-use request under Act LXIII of 2012 rather than an informal "permission" e-mail. Do not reuse the product images.

### 3. Kifli ÁSZF bans copying and tracking; its MCP server needs a customer login: CONFIRMED

- PDF re-downloaded; header "Hatályos: 2026. szeptember 26. napjától".
- §3 (c) is verbatim as quoted: "nem szerzi meg, követi nyomon vagy másolja az Online Shop tartalmait vagy információit sem automatizált eszközökkel, sem manuálisan, a Kifli.hu előzetes írásos engedélye nélkül".
- §3 (d) covers circumvention and undue load.
- §11 includes "az azon található adatbázisokkal".
- §3 also says prices and availability vary by delivery address and serving warehouse.
- `https://www.kifli.hu/mcp-docs` lists `https://mcp.kifli.hu/mcp`, OAuth, and "Aktív Kifli fiókra van szükséged".
- A plain GET to the endpoint returned **HTTP 401** with `WWW-Authenticate: Bearer error="invalid_token"` (VERIFIED). It is a per-customer agent integration, not a feed.
- Nuance, as the stream already noted: §3 binds the "Vásárló" (customer).

### 4. Wolt terms forbid bots and systematic copying; SPAR's own shop moved to Wolt: CONFIRMED (Tesco-on-Wolt not verified)

Wolt ÁSZF (https://explore.wolt.com/hu/hun/terms; the page ends "Hatályos 2026. július 31-től") was re-read:
- 12.7 (vi), (vii) "nem használhat botokat és egyéb automatizált módszereket", and (ix) are verbatim.
- 12.8 "kereskedelmi célú felhasználására" is not allowed, and systematic mapping or copying by web robot is "kifejezetten tilos".
- 11.1 covers IP.

Other checks:
- The affiliates page (https://explore.wolt.com/en/hun/affiliates) says Wolt "partnered with the affiliate network TradeDoubler". VERIFIED.
- `https://www.spar.hu/onlineshop` returns **301 to `https://www.spar.hu/wolt`** today. The spar.hu homepage returns a Cloudflare "Just a moment..." 403. VERIFIED.
- Telex 2025-04-01, re-read:
  - Auchan launched on Wolt from April 1 in all its hyper- and supermarkets, with 3,200 items (4,500 in Budakalász). Auchan's own site remains.
  - SPAR's online shop moved to Wolt; 133 staff were affected.
  - **For Tesco, the article only says that Dodo and Wolt now do all Tesco *deliveries*** ("mostantól mindent a Dodo és a Wolt végez"). It does not say there is a Tesco storefront on Wolt, and I did not verify one. I did not browse wolt.com because of ÁSZF 12.7 (vii).

**Correction:** for Tesco, write "Tesco home deliveries are handled by Dodo and Wolt", not "Tesco on Wolt".

### 5. Tesco sites block bots (Akamai), so website data would require circumvention: PARTLY TRUE

- Re-tested with the honest UA:
  - `bevasarlas.tesco.hu/robots.txt` and `/groceries/hu-HU/` return **403** (server AkamaiGHost).
  - `www.tesco.hu/` and `/help/` return **403** (edgesuite "Access Denied").
  - The default curl UA also gets 403 on robots.txt.
  - So this is bot management or IP reputation, not a UA-string rule. CONFIRMED.
- However, the Apify actor page (https://apify.com/studio-amba/tesco-hu-scraper, VERIFIED) says "Category scraping requires a Bright Data Web Unlocker key; **keyword search does not**".
- It also confirms "Akamai Bot Manager with hard IP-reputation blocking". It shows $2.00 per 1,000 results, 2 total users and 1 monthly active user.

**Corrected statement:** Tesco's web hosts block automated clients at the edge, so a polite, honest crawler cannot read even robots.txt. Full-catalogue scraping by the known vendor depends on an unblocking service, which is circumvention. A keyword-search path reportedly works without one, but it still conflicts with Tesco's own-use terms (seen only in a snippet) and should not be used. Tesco prices are in GVH anyway.

### 6. Discounters do not publish full regular price lists on their own sites: CONFIRMED (Aldi count slightly off)

**Lidl:**
- The `p10024531` (Pilos tejföl) JSON-LD offer has no price: `{"priceCurrency":"HUF",…,"availability":"InStoreOnly"}`.
- The Nuxt payload has `"price":null`. VERIFIED.

**Penny:** 695 `/products/` URLs in `penny.hu/sitemap.xml`. COMPUTED; this matches the stream.

**Aldi:**
- 853 `/termek/` URLs in `aldi.hu/sitemap_products.xml`. COMPUTED; matches.
- My re-match of GVH Aldi items in 10 staple categories against the sitemap article numbers found **2 of 21**: Húsmester csirkemellfilé, 1,979 Ft, and Húsmester csirkecomb egész, **848 Ft**. **Both prices equal GVH.** The stream reported 1 of 22.
- Keyword search of the slugs found no spaghetti, penne, étolaj (cooking oil) or plain tejföl (sour cream) pages, only snack variants.
- 19 of 21 Aldi GVH entries use `aldi-<id>` ids and 2 use EANs.

**Corrected statement:** aldi.hu lists about 850 products and covered about 2 of 21 GVH Aldi staples in my sample. Where items overlap, the prices matched GVH.

### 7. NAV e-receipts: export and import on instruction; only NAV apps and 4 e-cash-register licences; online cash registers until 2028-07-01: CONFIRMED (with precision)

**Licence list** (VERIFIED https://nav.gov.hu/ado/enyugta/forgalmazasi-engedelyek/forgalmazasi-engedelyek, page dated "2026.09.04."):
- E-cash registers: C001 and C002 NAV ePénztárgép (Android, iOS; cloud), **B001 Fiscat Super eFP** (hardware; special purpose "éttermi, egészségkártyás", i.e. restaurant and health-card; 2026-08-06), and C003 Számlázz.hu ePénztárgép (Android; 2026-08-31).
- That is **4 licences for 3 products, and the only hardware model is a special-purpose one**.
- Customer apps: only P001 and P002 NAV eNyugta.

**Decree 8/2025 (III. 31.) NGM** (VERIFIED https://njt.hu/jogszabaly/2025-8-20-2X, amended by 39/2025 (XII. 19.) NGM):
- **§57(3): "Az 59. § és a 7. melléklet 2028. július 1-jén lép hatályba."** So a 2028-07-01 milestone exists in the primary source.
- The not-yet-effective §59 text is not displayed, so the exact wording "online cash registers usable until 2028-07-01" still rests on secondary sources (hellobiznisz: "A kötelező átállás végső határideje 2028. július 1.").
- Annex 5, point 6: the customer app "exportálja a tárolt bizonylatokat a vevő kifejezett utasítására… minden egyes exportálási műveletet egyedi utasítás alapján végez el", and may not contain a function that performs several exports on one instruction. **Bulk or automatic export is banned.**
- Annex 6: the customer-app distribution licence fee is **500,000 Ft** (amendment 250,000 Ft).

The NAV Q&A (VERIFIED) confirms the app does not identify the user, export needs an explicit instruction, and there is no automatic forwarding.

### 8. KSH STADAT ara0044 is a free official fallback (175 items, about 86 food, latest 2026-09; reuse "no resale"): PARTLY TRUE. The numbers are confirmed but the licence is misstated.

COMPUTED (HTML re-downloaded and decoded as ISO-8859-2):
- **175 item rows; 86 with food codes 1xxxx.** The other code groups are 3xxxx: 13, 4xxxx: 15, 5xxxx: 35 and 6xxxx: 26.
- The last non-empty month is **2026-09 for 172 of the 175 items**. The page shows "Utolsó frissítés: 2026. október 7."
- Values match the stream: Gomba 1,900; Szárazbab 1,540; Tisztított dió 6,180; Fűszerpaprika 8,840; Csirkemellfilé 2,460 Ft/kg. There are no rows for spenót (spinach), cukkini (zucchini), lazac (salmon), csicseri (chickpeas), zab (oats) or brokkoli (broccoli).
- Rice (676 Ft/kg) is also present.

**Licence, corrected** (VERIFIED https://www.ksh.hu/copyright):
- KSH uses **CC BY 4.0**. All content on the site, "beleértve a táblázatokat" (including tables), may be freely copied and distributed, **commercial use included**.
- Attribution "Forrás: KSH" or www.ksh.hu is mandatory, with an active link when online (3.2).
- Only data sets extracted on individual request from KSH's internal databases are CC BY-NC 4.0 (3.3).
- The KSH logo is excluded (3.4).

The stream's "no resale" (from a snippet) is wrong for STADAT tables.

---

## Important things the stream missed

1. **Statutory publicity and no history.** Act L of 2025 §70 makes the non-archived data public by law, which is stronger than ÁFF XII.4. §57(4)–(5) means price history is not public (only ministries, courts, authorities and KSH). The app must snapshot daily from day one.
2. **Formal re-use route.** Act LXIII of 2012 provides:
   - a written re-use request (§10);
   - a 20+20 working-day decision (§13);
   - limited refusal grounds (§14);
   - a marginal-cost fee (§15);
   - no database-right enforcement by the public body (§3/A).
   
   Third-party-copyright content (retailer product images) and logos are excluded (§3 b, f). Use this instead of an informal "written confirmation".
3. **Missed competitor: Cashmap** (Cashmap Kft., HQ in Pap). VERIFIED via the iTunes Search API and cashmap.hu.
   - **iOS app since 2023-09-10, current version 2026-07-03, 137 ratings, average 4.36**, genres Food & Drink and Shopping.
   - It compares 9 stores: Aldi, Lidl, Penny, Auchan, Ecofamily, Spar, Tesco, dm, Rossmann.
   - Features: deal alerts, a "Kalkulátor" that finds where to buy up to 100 products, shopping lists, a barcode scanner, and a paid subscription (OTP Mobil payments in its ÁSZF).
   - Its error-report form lists its sources: **"Árfigyelő", "Auchan Online", "Kifli.hu", "SPAR-WOLT-ÚJ 2026 áprilistól", Metro, "Coop Online akciók", "coopshop-online", Príma/CBA stores**, among others.
   - So a 3-year-old competitor openly reuses GVH data and apparently the sources the stream marks as contractually off-limits. That is evidence of market practice, not of legality.
   - It also hints that something changed with SPAR on Wolt in April 2026 (not verified).
   - It belongs in the competitor list next to Árnéni.
4. **Auchan online vs store is understated.** For Kalifa lencse, GVH flags priceSameEverywhere=false, yet all 4 Auchan stores checked (Budakalász, Soroksár, Szentendrei út, Hunyadi János u.) list **599 NORMAL and 499 DISCOUNTED**. auchan.hu shows **609** (JSON-LD, re-fetched today) with no discount. The online price is +10 Ft against the store's normal price and **+110 Ft (+22%) against the in-store promo price** in force. COMPUTED. Online prices can therefore miss in-store promotions entirely.
5. **Tesco keyword-search loophole.** Per its own page, the Apify Tesco actor's keyword path needs no unblocker. Tesco also blocks the default curl UA (IP or bot management), so "honest UA" is not the deciding factor.
6. **e-receipt crowdsourcing UX constraint.** The decree bans bulk or multi-export on one instruction, so each user must export receipt by receipt. Becoming a licensed customer app costs a 500,000 Ft licence fee plus certification. The only hardware e-cash register licensed so far is a restaurant and health-card model.
7. **Store-level variation is concentrated in Tesco.** COMPUTED: 9 of 29 Tesco chain entries in the sample vary by store, against 0 for Lidl, Aldi, Penny and Spar and 1 of 21 for Auchan. Only for Tesco (and rarely Auchan) does a "local price" feature need per-shop calls.
8. **Budapest coverage figure for the pitch.** 282 GVH food-chain stores in Budapest, all geocoded (COMPUTED).

## Not re-checked (low decision weight or blocked)

- The foodora ÁSZF, Groby, CBA and Coop pages, Kimbino and akcios-ujsag.
- The Kifli 19,000-product claim.
- ESM and Pénzcentrum figures (SPAR 10,000 items on Wolt, 73 stores in 40 towns; Aldi/Roksh 3,300 products).
- Any later outcome of the 2023 GVH case.

Reason: the WebSearch budget was exhausted. The Open Prices figure was re-checked: `currency=HUF` gives total **37**, latest 2026-09-29 Spar Budapest. CONFIRMED.
