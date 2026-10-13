# Running bestpricefinder on your own machine

This is the founder's guide to running the app day to day, for your own use. It covers macOS first, with
notes for Linux. Every command is run from the repository root as your normal user, never with `sudo`.

What runs where:

```
 your phone ── HTTPS ──► Caddy (optional; deploy/local/caddy/)        your Mac's browser
                              │                                              │
                              ▼                                              ▼
                 deploy/local/run-api.sh: API + web app on http://127.0.0.1:8000 (localhost only)
                              │
                              ▼
          PostgreSQL cluster in .data/pg (port 5544, private socket in .data/sock)
                              ▲
   scheduled jobs (launchd on macOS, cron on Linux): GVH ingest at 04:30/05:30, weekly availability,
   daily backup ─── at most 1 request/s to arfigyelo.gvh.hu, with your e-mail in the User-Agent
```

Quick reference (all in `deploy/local/`):

| Script | What it does |
|---|---|
| `db-init.sh` | Creates the dedicated database cluster and `.env.local` (once). |
| `db-start.sh` / `db-stop.sh` | Starts or stops the cluster. |
| `load-content.sh` | Applies migrations, then validates `data/` and loads ingredients, recipes and KSH prices. |
| `run-ingest.sh reference\|daily\|availability` | Fetches GVH data, with a lock and a log in `.data/logs/`. |
| `build-web.sh` | `npm ci`, `npm run check` and `npm run build` in `web/`. |
| `run-api.sh` | Serves the app on http://127.0.0.1:8000. |
| `doctor.sh` | Checks everything and prints the fix for each problem. |
| `db-backup.sh` | Backs up the database to `.data/backups/` (optionally encrypted with age). |
| `scheduler/install-macos.sh`, `scheduler/install-linux.sh` | Installs the schedule (`uninstall-*.sh` removes it). |

## 1. Install the prerequisites

### macOS

Install [Homebrew](https://brew.sh/) first, then:

```sh
xcode-select --install                       # git and the command line tools, if not installed yet
brew install postgresql@18 uv node@22 age
brew install caddy                           # only for phone access (step 9)
echo 'export PATH="$(brew --prefix node@22)/bin:$PATH"' >> ~/.zprofile   # node@22 is keg-only
exec zsh -l                                  # reload the shell, then check:
node --version                               # v22.12 or newer
```

- You do **not** need `brew services start postgresql@18`. The app runs its own, separate cluster, which
  `db-init.sh` creates. A Homebrew PostgreSQL you already use is left alone.
- uv installs Python 3.14 by itself the first time a script needs it.
- Keep the Mac's time zone on Budapest (System Settings → General → Date & Time), because the schedule uses
  local time.

### Linux (Debian/Ubuntu)

```sh
sudo apt install postgresql git age tzdata cron curl   # PostgreSQL 16 or newer (Ubuntu 24.04: 16)
curl -LsSf https://astral.sh/uv/install.sh | sh        # uv, into ~/.local/bin
# Node.js 22: from https://nodejs.org/ (or NodeSource / nvm); check with: node --version
```

The distribution's own PostgreSQL service is not used and may stay stopped. The scripts find the server
binaries in `/usr/lib/postgresql/<version>/bin` (or set `BPF_PG_BIN`). Debian 12 ships PostgreSQL 15, which is
too old: install 16 or newer from the PostgreSQL project's apt repository (apt.postgresql.org).

## 2. Get the code

```sh
mkdir -p ~/src && cd ~/src
git clone <repository URL> bestpricefinder
cd bestpricefinder
```

On macOS, keep the repository **outside** `~/Documents`, `~/Desktop`, `~/Downloads` and iCloud Drive. macOS
privacy protection stops background jobs (the schedule) from reading those folders.

## 3. Create the database (once)

```sh
deploy/local/db-init.sh
```

This creates a hardened PostgreSQL cluster in `.data/pg`. It listens on localhost:5544 and a private socket
directory only. It also writes random passwords to `.env.local` (mode 600) and leaves the cluster running.
Everything in `.data/` and `.env.local` is git-ignored: never commit or share it. After a reboot, start the
cluster with `deploy/local/db-start.sh`; the scheduled jobs also start it when they find it stopped.

## 4. Load the schema and the content

```sh
deploy/local/load-content.sh
```

This applies the database migrations, then validates `data/` (ingredients, recipes, KSH prices) and loads it in
one transaction: if anything is invalid, nothing is written. Run it again after every `git pull`. It is
idempotent. Once the first ingest has run (step 6), it also checks the ingredients' GVH categories and the
recipes' price coverage against the real GVH data, so run it once more after step 6.

## 5. Set your contact e-mail

GVH receives your e-mail address in the User-Agent of every request, so that they can reach the operator
(BUILD-BRIEF §4.1 trap 11). The ingest refuses to run without it:

```sh
printf 'BPF_CONTACT_EMAIL=%s\n' 'you@example.org' >> .env.local   # your real address
```

## 6. The first ingest

```sh
deploy/local/run-ingest.sh reference      # chains, categories, 1,829 stores: 3 requests, seconds
deploy/local/run-ingest.sh daily          # today's prices: about 1,000-1,700 requests, 20-30 minutes
deploy/local/run-ingest.sh availability   # which store carries what: thousands of requests, about an hour
```

- `daily` fetches the prices of today's date (Budapest). Between midnight and about 04:30 Budapest time it fails
  with "stale XLSX": GVH regenerates its daily XLSX at about 02:00 UTC (04:00 in summer, 03:00 in winter), and
  until then its CDN serves yesterday's file. Nothing is wrong then, and nothing was written: run it again later.
- Run `availability` **after** a successful `daily`: it refreshes the products of the latest daily run. Run before
  any, it refreshes nothing, and the app then treats most stores as having no data until it runs again
  (`doctor.sh` warns about this). Until the first real availability run, every store counts as having data.
- At most one ingest runs at a time. A second one exits with code 75 and says so.
- Output goes to the terminal and to `.data/logs/ingest-YYYY-MM-DD.log`.
- Exit codes: 0 ok, 1 failed, 3 partial (data were written but something is missing; `doctor.sh` shows what).

## 7. Build the web app

```sh
deploy/local/build-web.sh
```

This runs `npm ci` (it needs the network), then `npm run check` (types and accessibility rules) and `npm run
build`, which writes `web/build/`. `npm ci` prints an `npm audit` summary: only 3 low advisories remain,
all for `cookie` in SvelteKit's server runtime, which this static app does not ship (`npm audit --omit=dev`
reports 0). See "Known issues" in [`web/README.md`](../web/README.md).

## 8. Start the app

```sh
deploy/local/run-api.sh
```

Open <http://127.0.0.1:8000>. Keep the terminal tab open; Ctrl-C stops the app. The script refuses to start
when `web/build` is missing or migrations are pending, and it warns when `web/build` is older than the web
sources. It binds to 127.0.0.1 only, so other devices cannot reach it without Caddy. Nothing starts the app
by itself: after a reboot, run `deploy/local/db-start.sh` and then `deploy/local/run-api.sh` again.

Then check the whole installation:

```sh
deploy/local/doctor.sh
```

Every line is `[ ok ]`, `[WARN]` or `[FAIL]`, with a `fix:` line under each problem.

## 9. Use it on your phone (HTTPS)

Phones allow location only on HTTPS pages. Put Caddy in front of the app, following
[`deploy/local/caddy/README.md`](../deploy/local/caddy/README.md). In short, for your home network:

1. Add `BPF_TRUST_PROXY_HEADERS=true` to `.env.local` and restart `run-api.sh`.
2. Run `BPF_LAN_ADDRESS=<the Mac's LAN IP> caddy run --config deploy/local/caddy/Caddyfile.example --adapter caddyfile`.
3. Install Caddy's root certificate on the phone once, then open `https://<the Mac's LAN IP>:8443`.

A public domain with Let's Encrypt is option (b) in the same README. It makes the app public, so read the legal
notes there first.

## 10. Install the schedule

| Job | When (Europe/Budapest) | What |
|---|---|---|
| Daily ingest | 04:30, and again at 05:30 | `run-ingest.sh --scheduled daily`. The 05:30 run does nothing if 04:30 finished ok; otherwise it is the retry (e.g. after a stale XLSX). |
| Availability | Sundays 05:00 | `run-ingest.sh --scheduled availability`. It waits for a daily run that is still going. |
| Backup | 03:15 | `scheduler/backup-job.sh`: `db-backup.sh`, then deletes dumps older than 30 days (the newest 7 are always kept). |

**macOS** (launchd agents of your user):

```sh
deploy/local/scheduler/install-macos.sh
```

- launchd uses the Mac's local time, so the installer refuses unless the Mac is on Europe/Budapest time
  (`--any-timezone` overrides that).
- If the Mac sleeps at 04:30, the job runs when it wakes up; missed runs are merged into one. A Mac that is
  switched off runs nothing.
- Check the agents: `launchctl print gui/$(id -u)/com.bestpricefinder.ingest-daily`. Start one now:
  `launchctl kickstart gui/$(id -u)/com.bestpricefinder.ingest-daily`.
- Remove them: `deploy/local/scheduler/uninstall-macos.sh`.

**Linux** (a block in your user crontab):

```sh
deploy/local/scheduler/install-linux.sh          # --print shows the block without installing it
deploy/local/scheduler/uninstall-linux.sh
```

Debian/Ubuntu cron ignores `CRON_TZ`, and a `CRON_TZ` line would also shift the schedule of your other entries.
So every line of the block fires hourly, and `scheduler/at-budapest.sh` lets it through only in the Budapest hour
of the job. The times are right whatever the machine's time zone (as long as its UTC offset is a whole number of
hours, which the installer checks), including across daylight saving changes. Cron does not catch up on runs
missed while the machine was off. A cron daemon must be running (`sudo systemctl enable --now cron`).

Both installers copy these settings into the jobs if they are set when you run the installer (the jobs do not
see your shell's environment): `BPF_PG_BIN`, `BPF_PGDATA`, `BPF_ENV_FILE`, `BPF_DB_NAME`, `BPF_BACKUP_DIR`,
`BPF_BACKUP_AGE_RECIPIENT`, `BPF_BACKUP_KEEP_DAYS`, `BPF_LOG_KEEP_DAYS` and `BPF_INGEST_LOCK_WAIT_S`. Re-run the
installer after changing any of them or after moving the repository.

Logs are in `.data/logs/`. `ingest-YYYY-MM-DD.log` and `backup-YYYY-MM-DD.log` are kept for 30 days. On macOS,
`launchd-*.log` receive one line per failed run. On Linux, cron mails that line to you if local mail is set up.

## 11. Backups

```sh
deploy/local/db-backup.sh        # by hand: .data/backups/bpf-<UTC timestamp>.dump (mode 600)
```

The schedule makes one every night. The database holds only public price data, our own recipes and run
records, and no personal data. Still, **encrypt anything that leaves the Mac**, using [age](https://age-encryption.org/):

```sh
mkdir -p ~/.config/bestpricefinder
age-keygen -o ~/.config/bestpricefinder/backup-key.txt     # prints "Public key: age1..."
# Store a copy of backup-key.txt in your password manager. Without it the backups cannot be read.
export BPF_BACKUP_AGE_RECIPIENT=age1...                      # the public key
deploy/local/db-backup.sh                                    # writes only bpf-<timestamp>.dump.age
deploy/local/scheduler/install-macos.sh                      # re-run (Linux: install-linux.sh), so the nightly job encrypts too
```

Copy `.data/backups/*.dump.age` to an external disk or a cloud drive now and then. To restore, see
[`deploy/local/README.md`](../deploy/local/README.md#restoring-a-backup). Set `BPF_BACKUP_KEEP_DAYS` (default 30;
0 = keep everything) before installing the schedule to change how long the nightly job keeps old dumps.

## 12. Updating

```sh
git pull
deploy/local/load-content.sh     # new migrations and content
deploy/local/build-web.sh        # when web/ changed (run-api.sh warns when the build is older than the sources)
# restart the app: Ctrl-C in its terminal, then
deploy/local/run-api.sh
deploy/local/doctor.sh
```

- Python dependencies update by themselves: every script runs `uv run --locked`, which syncs `server/.venv` to
  `server/uv.lock`.
- The app reads `web/build/index.html` once at startup, so always restart it after `build-web.sh`.
- Re-run the scheduler installer if the update says the schedule changed.

## 13. Troubleshooting

Start with `deploy/local/doctor.sh`. Then look at the newest log in `.data/logs/`.

| Symptom | Cause and fix |
|---|---|
| `failed: stale XLSX` (`StaleXlsxError: ... sheet date X != expected Y`) | GVH's CDN still served yesterday's file (BUILD-BRIEF §4.1 trap 4). It is regenerated at about 02:00 UTC. No prices were written. The 05:30 run retries; by hand, run `run-ingest.sh daily` later. If it persists all day, check <https://arfigyelo.gvh.hu> in a browser. |
| `partial` with `api_xlsx_date_mismatch` | The GVH API switches days at about 00:00 UTC, and its listing still disagreed with the dated XLSX (trap 10). The data were written and are served. The 05:30 run retries automatically (only an `ok` run makes it a no-op); by hand, run `run-ingest.sh daily` again later in the morning. |
| `GvhHttpError`, `ConnectError`, timeouts | GVH or your network is unreachable. Check the connection, then run the ingest again. The client already retries 5xx and connection errors 3 times. |
| `GvhSchemaError` | GVH changed its undocumented API or XLSX. The ingest refuses to guess (it fails loudly). See `server/bpf/gvh/ASSUMPTIONS.md`; the code needs an update. |
| `GvhConfigError` / "BPF_CONTACT_EMAIL is not set" | Step 5. |
| `another ingest is running`, exit 75 | Wait for it to finish (`ps aux \| grep bpf.ingest`). Each run takes the lock in `.data/locks/`. |
| `PostgreSQL is not running` / `cannot query the database` | `deploy/local/db-start.sh`. Its log is `.data/log/postgresql.log`. |
| `run-api.sh`: "no web build" / "migrations are pending" | `deploy/local/build-web.sh` / `deploy/local/load-content.sh`. |
| `address already in use` | Something else uses port 8000: stop it, or start with `BPF_API_PORT=8001 deploy/local/run-api.sh`. |
| The app says the prices are stale | The latest data are older than yesterday: the schedule did not run or keeps failing. Check `doctor.sh` and `.data/logs/`. |
| macOS: `Operation not permitted` in `.data/logs/launchd-*.log` | The repository is in a protected folder (step 2). Move it and re-run `install-macos.sh`. |
| doctor: "the last availability run ... refreshed nothing" | `availability` ran before any daily run had succeeded, so the app treats most stores as having no data. Run `run-ingest.sh availability` again now (step 6). |
| A run stays `running` in doctor | Its process was killed (e.g. power loss). It is harmless, because the next run is not blocked. |
| Linux: jobs never run | No cron daemon (`sudo systemctl enable --now cron`), or the machine was off at those hours. |

## 14. Legal reminders while operating it

From BUILD-BRIEF §8 (research, not legal advice):

- **Attribution and dates.** Every price must show "Forrás: GVH Árfigyelő (arfigyelo.gvh.hu), [adat dátuma]",
  and KSH estimates must show "Forrás: KSH" with a link. "Legolcsóbb" claims stay scoped to the selected stores
  and the data date. Keep the schedule running so the data date stays current.
- **No GVH branding.** No "Árfigyelő" or "GVH" name or logo in the app's name or icon. Keep the disclaimer: "Nem
  hivatalos alkalmazás, nem áll kapcsolatban a Gazdasági Versenyhivatallal." No product images or retailer logos.
- **Only GVH and KSH data.** Never point the ingest, a script or a scheduled job at Kifli, Tesco, Spar, Wolt,
  foodora or Auchan, and never work around bot protection. Do not raise the request rate (at most 1 request/s,
  enforced), run ingests in parallel or schedule them more often. Keep your real e-mail in the User-Agent.
- **Founder-only:** file the GVH re-use request (draft: `research/gap-gvh-reuse-legal-route/request_draft_hu.txt`)
  before the app is used by anyone else. Until then, and until the impresszum and privacy policy exist, keep it
  private: localhost, or Caddy option (a) on your home network.
- **Personal data stays on the phone.** The server stores none and Caddy keeps no access log. Keep it that way.
- **No health claims**, and the recipes are our own (`tested=false` until cooked).
- The fake GVH in `server/tests/` is **synthetic** test data. Never load it into your real database (the tests
  use throwaway clusters).
