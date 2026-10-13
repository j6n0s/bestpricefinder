# Questions & decisions log (asynchronous channel between agents and the user)

Append new entries at the bottom: `## YYYY-MM-DD — <author> — <topic>`, the question or decision, and the answer once known.

## 2026-10-13 — local research session — status of the promotions/stability research
- `research/gap-gvh-promo-and-stability/notes.md` is complete (sections 0–7). Unlike the main streams, it has **no adversarial `verify.md`**: the fact-check run hit a usage limit. Treat its numbers as single-source.
- What it established, and BUILD-BRIEF §3 already reflects:
  - GVH captured 26/26 sampled in-scope promotions on day one (Penny/Lidl as `DISCOUNTED`; Aldi as a lower `NORMAL`).
  - Lidl Plus app prices are absent, and "Csak most!" items are exempt.
  - About 1.8% of food prices change per day and 13–19% per week.
  - Lidl was cheapest for the core basket on all 7 sampled dates since 2025-03, but the history has gaps (2025-05 to 2026-09).
- Implication for the build: no leaflet pipeline in the MVP. A "deal" badge must not rely on `DISCOUNTED` alone, because Aldi never sets it. Compare against our own daily archive instead.
- Open question (unresolved): is Aldi's reporting compliant (no "korábbi ár")? It doesn't block the build.

## 2026-10-13 — local research session — promotions/stability research now fact-checked (supersedes the entry above)
- Added `research/gap-gvh-promo-and-stability/verify.md`: two independent checkers, using live data and the official XLSX of 2026-10-13. BUILD-BRIEF §3, §4.1 (traps 4, 10, 12, 13 are new or changed) and §11 were updated accordingly. **What changes for the build:**
  1. **Ingest timing:** the GVH API switches day at about 00:00 UTC (02:00 Budapest time in summer). Keep the 04:30 run, and check that the API and XLSX data dates agree.
  2. **XLSX:** it is always cache-busted and date-checked, because the plain URL served 6–30 hour old files. It contains no loyalty prices; `productMinAmount` doesn't either. Read card prices from listing `prices[]` LOYALTY.
  3. **"Deal" badge:** derive it from our own daily archive. `DISCOUNTED` also marks long-running reductions, and Aldi never sets it.
  4. **Ties:** 8–9 of 20 core items are exact cross-chain ties. Cheapest-chain logic must group ties and must never break them by chain name.
  5. Don't hard-code "Lidl is cheapest". Its basket lead was only 3.8% (391 Ft) today.
- Still open, and not blocking:
  - Thursday-start promos have only been seen from day 4, so add a Thursday snapshot test once the ingest runs daily.
  - Is Aldi's and Lidl Plus's reporting compliant?
