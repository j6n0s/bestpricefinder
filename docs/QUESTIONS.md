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
