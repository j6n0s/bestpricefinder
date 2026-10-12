# Working agreement for agents in this repo

**Who writes the code:** a **cloud-based agent**, as decided by the user on 2026-10-13. It owns `server/`, `web/`, `deploy/` and `data/`. It may also add new `db/migrations/` files.
**Who wrote the foundation:** the local session "Meal planning app idea analysis", which produced the research, the spec, the architecture and migration 0001. It is now advisory only.

Start here: [docs/PROGRESS.md](docs/PROGRESS.md), then [BUILD-BRIEF.md](BUILD-BRIEF.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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
