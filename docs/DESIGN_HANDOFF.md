# Design hand-off: "Heti kosár" UI redesign (from the local session to the cloud agent)

**Branch:** `design/pixel-kitchen`, based on `claude/practical-newton-fdz8jp` at 5bfc911. **Saved:** 2026-10-14 by the local session "Meal planning app idea analysis".
**Owner from now on:** the cloud agent. The user wants the design development to continue in the cloud.

## 1. What the user asked for (in order; the latest wins)
1. More intuitive and more "human-made"; a pixel-art reference image; a vegetable and cooking vibe.
2. "It feels cold, I want it warm like cooking." **Titles in Courier New**; paragraphs and other text keep the normal (system) font.
3. **Never use "≈".** "Too much, AI-like web design": **a more standard look**. Their reference was a plain shop product card: white card, product name, unit-price chip, chain and price, a soft "add to list" button. ⚠️ That reference is a **GVH Árfigyelő** card. Take only the generic pattern; never imitate GVH's own UI or colours (BUILD-BRIEF §8, legal guardrail).
4. **"Too much information."** Less displayed text and a self-explanatory UI. Pages and menu items must not "talk about themselves".
5. **Never use "kb." either; use "-tól".** For example "600 Ft-tól", "from 600 Ft".

## 2. Done on this branch
- **Standard look.** All pixel-art experiments were reverted (no pixel font, pixel icons, hard shadows or gingham). The original components are back, with:
  - a **warm palette** in `web/src/app.css`. Light: cream `#fdf0dc`, paprika red `#a8321a`, espresso text `#3a1f12`. Dark: espresso `#1f120c` with amber `#f6ad3a`. `src/lib/contrast.test.ts` passes for both themes;
  - **Courier New** (`--font-title`) for h1/h2 and the header brand; body text uses the system font;
  - softer radii (6/10/14 px) and a light card shadow;
  - app icons regenerated with `scripts/gen-icons.mjs` (the original basket, paprika and cream); theme colours updated in `src/app.html` and `static/manifest.webmanifest`.
- **"≈" removed** from all UI texts and the tests. Recipe prices read "313 Ft/adag-tól (Aldi, Lidl)" and "from 313 Ft/serving".
- **Declutter (step 4), mostly done** by an agent that was **stopped mid-run**:
  - page intros, the home "Így működik" card, privacy reminders, the "kipróbálatlan" banner and price-method notes removed;
  - the location explainer shortened (new `LocationPrivacy.svelte`);
  - "how we calculate" moved into a collapsed `HowCalculated.svelte`;
  - i18n keys and tests updated.
- `tests/e2e/smoke.spec.ts`: the nav-clearance check now **polls**. The single read raced BottomNav's ResizeObserver: −54.8 px immediately, +0.2 px two frames later. The original design has the same race. The dark-background expectation is now `rgb(31, 18, 12)`.

**Verified at save time:** `npm run check` gives 0 errors and 0 warnings (476 files); `npx vitest run` passes 619/619.
**NOT verified after the declutter:** `npm run test:e2e` and `npm run test:fullstack`. That is your first task.

## 3. To do (in order)
1. **Run and fix** `npm run test:e2e` and `npm run test:fullstack`; read the git diff first. Use Node 22 (`brew install node@22`). Playwright's browser install hangs on Node 26.
2. **Finish the declutter.** Goal: each page explains itself through its title, labels, buttons and numbers. Rules:
   - **remove:** page intros, permanent method notes, self-descriptions;
   - **keep, small and muted:** the GVH attribution with its date and the disclaimer on **every** price view; the KSH labels ("becsült országos átlagár (KSH)", "nincs benne a fizetendő összegben", "Forrás: KSH"); error, offline and edge-case messages (they are conditional); the full `/forrasok` page;
   - **location consent:** one short sentence plus a privacy link **before** any geolocation request, and nothing fetched before the click.
   Check every page (/, /terv, /receptek, /receptek/[id], /lista, /kosar, /beallitasok) for any remaining permanent paragraph of more than about 15 words.
3. **Remove every "kb."** (step 5). These remain (hu; check the en twins too):
   - `cart.hu.ts` `pieces: 'kb. {count} db'` → `'{count} db'`;
   - `list.hu.ts` `leftover: 'Marad kb. {qty}'` → `'Marad {qty}'`;
   - `list.hu.ts` `ksh_value: 'kb. {price}, nincs benne a fizetendő összegben'` → `'{price}-tól, nincs benne a fizetendő összegben'` (en: `'from {price}, not included in the amount to pay'`). The "becsült országos átlagár (KSH)" label must stay next to it;
   - `journey.hu.ts` `walk_round`, `walk_journey_longer`, `walk_journey_shorter`: drop "kb." ("Séta: {distance} légvonalban …").
   Update the e2e and fullstack expectations that contain these strings.
4. **Screenshot pass:** 320, 390 and 1280 px, light and dark, on every page. Show the user screenshots early; they judge by feel.

## 4. Constraints
- BUILD-BRIEF §8 legal guardrails: no GVH branding or lookalike, source and date on every price, no product images, no health claims.
- CSP: no inline styles or scripts, no external requests (fonts must be system fonts or self-hosted).
- Keep the a11y and contrast tests passing, and never weaken the privacy, CSP or legal checks.
- Known flaky test (it also fails on the original code): `plan.spec.ts` "the picker works with the keyboard alone" fails rarely under load and passed 30/30 when run alone.
