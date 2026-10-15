# Working agreement for agents in this repo

**Who writes the code:** the **local Claude Code session** on the founder's Mac, as decided by the user on 2026-10-15 ("I want to continue the development of the app in the claude session"). It owns `server/`, `web/`, `deploy/` and `data/`, may add new `db/migrations/` files, and deploys to the Azure VM ([deploy/azure/README.md](deploy/azure/README.md)). Its working checkout is `~/src/bestpricefinder`, branch `claude/practical-newton-fdz8jp`.
**Before that:** a cloud-based agent wrote the app from 2026-10-13 to 2026-10-15 (everything up to `b31d050`). **Restarted by the user on 2026-10-15** (QUESTIONS.md "map point, pantry amounts, cart categories"): it writes code again when the user asks and pushes to the branch above, so the local session **pulls before editing `web/` or deploying**. Both agents stage explicit paths and never rewrite the branch's history.
**Who wrote the foundation:** the local session "Meal planning app idea analysis", which produced the research, the spec, the architecture and migration 0001.

Start here: [docs/PROGRESS.md](docs/PROGRESS.md), then [BUILD-BRIEF.md](BUILD-BRIEF.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Working loop (local session)
- Develop on `claude/practical-newton-fdz8jp` (feature branches off it for larger work). Use Node 22 for `web/` (`/opt/homebrew/opt/node@22/bin`; Playwright hangs on Node 26); run the server tests with `LC_ALL=C` (some assert English psql messages).
- Before a commit: `cd server && uv run pytest -q -m "not db"` (plus the `db` tests when SQL changes), `cd web && npm run check && npx vitest run` (plus `npm run test:e2e` for UI changes).
- Deploy a verified commit with `deploy/azure/update-vm.sh`. Commit, push and deploy when the user asks.

## Communication (agents cannot message each other)
- Questions and decisions go in `docs/QUESTIONS.md`. Append, date and sign each entry.
- Progress goes in the checklist in `docs/PROGRESS.md`.
- The user relays anything urgent.

## Binding rules
- The legal guardrails in BUILD-BRIEF.md §8 apply to every component. In particular:
  - no GVH/"Árfigyelő" branding;
  - a source and date on every price;
  - no product images;
  - no scraping of Kifli, Tesco, Spar, Wolt, foodora or Auchan;
  - no copied recipes;
  - no health claims.
- The database schema changes only through new numbered files in `db/migrations/`. Never edit an applied migration.
- Never commit secrets: `.env*` files (except `.env.example`), keys, dumps or `pgdata/`.
- Never force-push to `main`. Use small commits with clear messages, and work on a branch with PRs when possible.
- If several agents share one working tree: don't switch branches, stash, `reset --hard` or `clean`, and stage explicit paths only.
