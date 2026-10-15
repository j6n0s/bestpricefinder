# Deployment hand-off: current state and the Azure VM plan (for the local agent)

Written 2026-10-15 by the cloud agent, at the user's request, for the **local agent**, who will deploy the app
to an **Azure virtual machine**. The cloud agent cannot reach Azure or the user's machine; everything it knows is
in the repository. Read this file first, then [docs/RUNNING.md](RUNNING.md) (the step-by-step installation
guide this plan follows) and [deploy/local/README.md](../deploy/local/README.md) (every script and variable).
The working agreement is [AGENTS.md](../AGENTS.md): questions and decisions go to [docs/QUESTIONS.md](QUESTIONS.md),
progress to [docs/PROGRESS.md](PROGRESS.md).

## 1. Where the code is

| Item | Value |
|---|---|
| Repository | `j6n0s/bestpricefinder` on GitHub |
| Branch to deploy | `claude/practical-newton-fdz8jp` at commit `52c0656` (2026-10-15). `design/pixel-kitchen` points to the same commit. |
| `main` | `8be5b9d`: the foundation only (research, brief, architecture, migration 0001). Everything below is 56 commits ahead of it on the branch above. Deploy the branch, or merge it into `main` first (a PR; never force-push `main`). |
| Working tree | Clean. Nothing uncommitted anywhere. |

## 2. What the app is (as built)

One machine runs everything; nothing else is needed.

| Part | What | Where it listens |
|---|---|---|
| PostgreSQL 16+ | A dedicated, hardened cluster created by `deploy/local/db-init.sh` (roles `bpf_owner`, `bpf_migrator`, `bpf_ingest`, `bpf_api`; SCRAM only; the API role can only read the `api.*` views). Schema: `db/migrations/0001..0003`, applied by `uv run bpf-migrate`. | `localhost:5544` and a Unix socket under `.data/sock` |
| Content | Our own ingredients, recipes and the KSH price seed in `data/` (364 KB, in git). Loaded by `deploy/local/load-content.sh` (validates, then one transaction). | |
| Ingest | `python -m bpf.ingest` fetches **GVH Árfigyelő** data (`https://arfigyelo.gvh.hu/api` and the daily XLSX on `cdnarfigyeloprodweu.azureedge.net`), at most 1 request/s, with a descriptive User-Agent that carries `BPF_CONTACT_EMAIL`. Kinds: `reference` (chains, categories, stores; 3 requests), `daily` (prices), `availability` (which store carries what; weekly, slow). Run by `deploy/local/run-ingest.sh`, one at a time, under a lock, logged under `.data/logs/`. | outbound HTTPS only |
| API + web | `python -m bpf.api` (FastAPI, uvicorn): the JSON API at `/api/*` and the built SvelteKit PWA from `web/build` at `/`. Strict CSP by hash, rate limit 120 requests/min/IP, 64 KiB body limit, no cookies, no accounts, **no personal data on the server** (plans, preferences, location live in the phone's localStorage). Started by `deploy/local/run-api.sh`. | `127.0.0.1:8000` only |
| HTTPS | Caddy in front (`deploy/local/caddy/Caddyfile.example`): TLS, compression, proxy to 8000. Phones need HTTPS for geolocation. | `:443` (+ `:80` redirect) with a real domain, or `:8443` with Caddy's internal CA |
| Schedule | `deploy/local/scheduler/install-linux.sh` installs a crontab block: daily ingest 04:30 and 05:30 Budapest time (the second is a retry), availability Sundays 05:00, backup 03:15. `at-budapest.sh` makes the hours Budapest-local on a UTC machine. | |
| Backups | `deploy/local/db-backup.sh` (`pg_dump -Fc` into `.data/backups`, optionally encrypted with `age`). | |

Runtime requirements: **Python ≥ 3.14** (uv downloads it when missing: `uv run` does), **uv**, **Node.js ≥ 22.12**
and npm (build only), **PostgreSQL ≥ 16** server binaries (Ubuntu 24.04 ships 16), `age` (optional, backups),
`cron`, `curl`, `tzdata`, Caddy. All scripts run as a normal user and refuse root (`BPF_ALLOW_ROOT=1` exists for
CI containers only; do not use it on the VM; the PostgreSQL server must not run as root anyway).

Configuration: `.env.local` (mode 600, git-ignored, written by `db-init.sh`; every variable is listed with
placeholders in [`.env.example`](../.env.example)). The three settings a public VM needs beyond the defaults:

- `BPF_CONTACT_EMAIL=<the operator's real e-mail>` (the ingest refuses to run without it);
- `BPF_TRUST_PROXY_HEADERS=true` (behind Caddy on the same machine, so the rate limiter sees the client's IP);
- `BPF_HSTS=true` (only with a real domain and Let's Encrypt).

## 3. State of the work (what is done and verified)

Everything in `docs/PROGRESS.md` "Next steps" 1–8 is done and ticked, by the cloud agent, on 2026-10-13/15:
content package, planner, API (contract v1.2, `docs/API.md`, `docs/openapi.json`), web app (Hungarian PWA with an
English toggle), full-stack e2e, ops scripts, scheduler, Caddy example, `docs/RUNNING.md`. Since then:

- the GVH parsers were matched to the real API shapes captured on 2026-10-14 (`server/tests/fixtures`), and the KSH
  seed was converted from the original `ara0044` file;
- the cart ("Kosár") and the "Hol vásárolj?" one-store-or-route feature with a schematic map (computed on the
  device; no map tiles, no external request);
- the design rounds the user asked for (white/black page, soft green controls, less text, plain-word price
  notes, a closed "Források" disclosure per price view, a first-visit "Mit nem eszel?" question);
- the weekly **sweets rule was removed** on 2026-10-15 at the user's request (planner, API, UI; `docs/QUESTIONS.md`);
- a device sweep in Chromium at 14 phone/tablet/desktop profiles plus touch/iOS hardening (`docs/E2E.md`
  "Devices and browsers").

Verified green at `52c0656`: server `uv run pytest` 2534 tests (incl. role-privilege, fuzz, security and
scheduler tests), web `vitest` 629, Playwright e2e 110 (production build, mocked API), full-stack e2e 4 (real
PostgreSQL, fake GVH server, real ingest, real API), device sweep 126, `ruff`, `svelte-check`.

**Not done / caveats the deployer must know:**

1. **Nothing runs as a service yet.** `run-api.sh` runs in the foreground, the cluster is started by
   `db-start.sh`, Caddy by hand. On the VM these need systemd units (section 5, step 9). The repo has none;
   write them on the VM (or add them under `deploy/azure/` if you want them versioned; `deploy/` belongs to
   the cloud agent, but the user may reassign it).
2. **Safari and Firefox were never run** (only Chromium exists in the cloud environment). The support floor is
   iOS 16+, Chrome/Edge 107+, Firefox 104+. After deployment, open the app on a real iPhone (Safari, and "Add to
   Home Screen"), an Android phone and desktop Firefox once, and note anything odd in `docs/QUESTIONS.md`.
3. **Legal gates before the app is public** (BUILD-BRIEF §8, `docs/RUNNING.md` §14, founder-only):
   - the GVH re-use request has to be filed (draft: `research/gap-gvh-reuse-legal-route/request_draft_hu.txt`);
   - an impresszum / contact address and a privacy policy are still missing: `web/src/routes/forrasok/+page.svelte`
     carries the `TODO(founder)` marker;
   - until both exist, keep the VM **private**: restrict the Azure NSG's 443 rule to the user's own IP (or use
     Caddy option (a), `tls internal`, and install its root certificate on the phone).
4. `data/CONTENT_REPORT.md` is a dated feasibility report from before the sweets rule was removed; `BUILD-BRIEF.md`
   still lists "sweets ≤ 2". Both are left as written; `docs/QUESTIONS.md` 2026-10-15 overrides them.
5. `docs/PROGRESS.md` step 9 (security review: `pip-audit`, `npm audit`, secrets scan before every push) is the
   one open step. Run `pip-audit` and `npm audit` on the VM before opening the firewall.
6. The ingest depends on GVH staying as captured on 2026-10-14. If a run ends with a parse error, that is the
   first thing to check (`.data/logs/ingest-YYYY-MM-DD.log`); `server/tools/capture_gvh_samples.py` captures fresh
   samples for comparison (how it was used: `docs/QUESTIONS.md`, 2026-10-14).

## 4. Azure choices (recommendation; the user decides)

- **Image:** Ubuntu Server 24.04 LTS (PostgreSQL 16 in apt, cron, systemd). Not Debian 12 (PostgreSQL 15 is too old).
- **Size:** B2s or B2as_v2 (2 vCPU, 4 GB) is plenty: the API is light, the ingest is a few thousand requests at
  1/s, the database is small (plan a few GB of disk for years of daily prices). 30 GB OS disk.
- **Network:** one static public IP, a DNS `A` record for the domain (Caddy gets the Let's Encrypt certificate
  itself; ports 80 and 443 must be reachable from the internet for that). NSG inbound: 22 (restricted to the
  user's IP), 80, 443, nothing else. Outbound: default allow (GVH, the Azure CDN, Let's Encrypt, apt, npm, uv).
- **Login:** SSH keys only, a normal user (e.g. `bpf`) with sudo for the installation; the app itself never runs
  as root. Enable unattended-upgrades. The VM's clock can stay UTC (the schedule converts to Budapest time).

## 5. Deployment steps on the VM (follow `docs/RUNNING.md`; the Azure-specific points are here)

Run everything as the normal user from the repository root unless a line says `sudo`.

1. **Prerequisites** (RUNNING.md §1, Linux):
   `sudo apt install postgresql git age tzdata cron curl`; uv from `https://astral.sh/uv/install.sh` (into
   `~/.local/bin`; make sure it is on `PATH` for cron and systemd too); Node.js 22 (NodeSource or nvm);
   Caddy from its apt repository (`https://caddyserver.com/docs/install#debian-ubuntu-raspbian`). Stop and
   disable the distro's own PostgreSQL service (`sudo systemctl disable --now postgresql`): the app uses its own
   cluster on port 5544.
2. **Code:** `git clone` the repository into e.g. `/opt/bestpricefinder` (owned by the normal user) and check out
   `claude/practical-newton-fdz8jp` (or `main` after the merge).
3. **Database (once):** `deploy/local/db-init.sh` → creates the cluster under `.data/pg`, the roles, `.env.local`
   and `.data/pg-admin.env`. Keep both files mode 600; never commit them.
4. **Schema and content:** `deploy/local/load-content.sh`.
5. **Settings:** add `BPF_CONTACT_EMAIL`, `BPF_TRUST_PROXY_HEADERS=true` and (with a real domain) `BPF_HSTS=true`
   to `.env.local`.
6. **First ingest:** `deploy/local/run-ingest.sh reference`, then `deploy/local/run-ingest.sh daily`, then
   `deploy/local/load-content.sh` again (coverage is checked against real prices now), then
   `deploy/local/run-ingest.sh availability` (slow; can run later via the schedule).
7. **Web build:** `deploy/local/build-web.sh` (npm ci, check, build → `web/build`).
8. **Try it:** `deploy/local/run-api.sh` in the foreground, `curl -s http://127.0.0.1:8000/api/health`, then
   Ctrl-C. `deploy/local/doctor.sh` must show no `[FAIL]`.
9. **Services (write these; they are not in the repo):**
   - a systemd unit for the API, run as the normal user, `WorkingDirectory=` the repository root,
     `ExecStartPre=<repo>/deploy/local/db-start.sh`, `ExecStart=<repo>/deploy/local/run-api.sh`,
     `Restart=on-failure`, and a `PATH` that contains `~/.local/bin` (uv) and the Node directory; `WantedBy=multi-user.target`;
   - Caddy's own service from the package (`/etc/caddy/Caddyfile`): copy `deploy/local/caddy/Caddyfile.example`,
     keep the `bpf_app` block, delete the (a) site, uncomment the (b) site with the domain and the e-mail, drop
     `skip_install_trust` and `auto_https disable_redirects` from the global options (they are for option (a)).
     `caddy validate --config /etc/caddy/Caddyfile`, then `sudo systemctl enable --now caddy`;
   - the cluster starts with the API unit's `ExecStartPre` (idempotent); no separate unit needed.
   Restart the API unit after every `build-web.sh` (it reads `index.html` and the CSP at startup).
10. **Schedule:** `deploy/local/scheduler/install-linux.sh` (installs the crontab block for the normal user; it
    copies the `BPF_*` overrides it sees at install time). Check with `crontab -l` and `doctor.sh`.
11. **Backups:** generate an `age` key, put its public key in `BPF_BACKUP_AGE_RECIPIENT` for the schedule (so only
    encrypted dumps are written), store the private key in the user's password manager, and copy the dumps off the
    VM (an Azure storage account works; RUNNING.md §11).
12. **Firewall:** open 80/443 in the NSG; until the legal gates in section 3 are passed, restrict 443 to the user's
    IP.
13. **Check from a phone:** `https://<domain>/` loads, "Heti terv" → "Terv készítése" works, "Lista" → the location
    explanation → nearby stores and prices appear with "Források: GVH Árfigyelő, <date>" at the bottom, and
    "Add to Home Screen" installs it. Then `deploy/local/doctor.sh` once more.
14. **Updating later** (RUNNING.md §12): `git pull`, `deploy/local/load-content.sh`, `deploy/local/build-web.sh`,
    restart the API unit.

## 6. Checks the deployer can run on the VM

- `deploy/local/doctor.sh` — the whole installation, with a `fix:` line for every problem.
- `cd server && uv run pytest -q -m "not db"` — the unit tests (the `db` tests need the throwaway cluster the test
  harness creates; they also run on Linux, about 7 minutes in all).
- `cd web && npm run check && npm test` — types and unit tests; `npm run test:e2e` needs Playwright's Chromium.
- `curl -sI https://<domain>/ | grep -i -E "strict-transport|content-security|cache-control"` — the headers Caddy
  passes through from the app.

## 7. Questions for the user (the local agent should ask before deploying)

1. Domain name for the VM, and the operator e-mail for `BPF_CONTACT_EMAIL` and Let's Encrypt.
2. Merge the branch into `main` before deploying, or deploy the branch as is?
3. Keep the app private (NSG restricted to the user's IP) until the GVH request and the impresszum exist? The
   cloud agent recommends yes.
4. Where the encrypted backups should go (Azure storage account, or none for now).
