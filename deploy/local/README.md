# deploy/local: running bestpricefinder on one machine

Scripts for a production-like local installation: a dedicated, hardened PostgreSQL cluster for this app only
(docs/ARCHITECTURE.md, "Database security model"), the content load, the GVH ingest, the web build, the API,
a health check, a schedule (launchd or cron), HTTPS for phones (Caddy) and backups. The step-by-step guide is
[docs/RUNNING.md](../../docs/RUNNING.md). The cluster never touches another PostgreSQL you may already run.
Works on macOS (Homebrew `postgresql@18`, also 16/17; the scripts run on the system bash 3.2) and on Linux
(distro PostgreSQL 16+ or PGDG 18). Run every script as your normal user, never as root, from any directory.

## Database

```sh
deploy/local/db-init.sh          # once: create cluster, roles, database, credentials (leaves it RUNNING)
cd server && uv run bpf-migrate  # apply db/migrations (uv run bpf-migrate --check: exit 2 if pending)
deploy/local/db-stop.sh          # stop  (idempotent)
deploy/local/db-start.sh         # start (idempotent)
deploy/local/db-backup.sh        # pg_dump -Fc into .data/backups/ (mode 600)
```

## What you get

| Item | Where |
|---|---|
| Cluster data | `.data/pg/` (mode 700) |
| Server log | `.data/log/postgresql.log` |
| Unix socket | `.data/sock/` (mode 700); falls back to `$TMPDIR/bpf-sock-<uid>-<port>` if the path would exceed the 103-byte socket limit |
| TCP | `localhost:5544` only (127.0.0.1 and ::1) |
| App credentials | `.env.local` (mode 600): `BPF_DB_HOST/PORT/NAME`, `BPF_{MIGRATOR,INGEST,API}_PASSWORD` |
| Superuser credentials | `.data/pg-admin.env` (mode 600): `bpf_admin`, for maintenance only; the app never uses it |
| Backups | `.data/backups/bpf-<UTC timestamp>.dump[.age]` |

Everything above is git-ignored. Passwords are 32 random bytes (hex), passed to `psql` through the
environment (`\getenv`), never on a command line, and never written to the server log.

Roles: `bpf_owner` (NOLOGIN, owns every object), `bpf_migrator` (can `SET ROLE bpf_owner`, inherits nothing),
`bpf_ingest` (data writes, timeouts) and `bpf_api` (read-only transactions, 3 s statement timeout, 20 connections).
`pg_hba.conf` allows only SCRAM, only these roles, only on the `bpf` database; `bpf_admin` may reach any database;
everything else is rejected explicitly. `server/tests/test_db_roles.py` checks all of this automatically.

## Options (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `BPF_PG_BIN` | discovered | Directory with `initdb`, `pg_ctl`, `postgres` (>= 16). Discovery: `pg_config --bindir`, then the highest of `/opt/homebrew/opt/postgresql@*/bin`, `/usr/local/opt/postgresql@*/bin`, `/usr/lib/postgresql/*/bin`, `/usr/pgsql-*/bin` |
| `BPF_PGDATA` | `.data/pg` | Cluster directory. Log, socket, admin credentials and backups live next to it |
| `BPF_PG_PORT` | `5544` | Port (used by `db-init.sh`; later scripts read it from `<PGDATA>/bpf.conf`) |
| `BPF_SOCKET_DIR` | `<dirname PGDATA>/sock` | Socket directory (used by `db-init.sh`; later read from `bpf.conf`) |
| `BPF_ENV_FILE` | `.env.local` | Where `db-init.sh` writes the app credentials (the server reads the same variable) |
| `BPF_DB_NAME` | `bpf` | Application database name |
| `BPF_BACKUP_DIR` | `<dirname PGDATA>/backups` | Backup directory |
| `BPF_BACKUP_AGE_RECIPIENT` | unset | `age1…` public key or recipients file: the dump is piped into `age`, so only `*.dump.age` is written. If set and `age` is missing, no backup is made |

## Operation scripts

```sh
deploy/local/load-content.sh                      # bpf-migrate, validate data/ (no DB), load it as bpf_ingest
deploy/local/run-ingest.sh reference|daily|availability [bpf-ingest options]
deploy/local/build-web.sh                         # npm ci, npm run check, npm run build (web/build)
deploy/local/run-api.sh                           # python -m bpf.api on http://127.0.0.1:8000 (Ctrl-C stops)
deploy/local/doctor.sh                            # checks everything; exit 1 if anything FAILs
deploy/local/scheduler/install-macos.sh           # launchd agents   (uninstall-macos.sh removes them)
deploy/local/scheduler/install-linux.sh           # a crontab block  (uninstall-linux.sh removes it)
deploy/local/scheduler/backup-job.sh              # db-backup.sh + pruning, as the schedule runs it
```

| Script | Notes |
|---|---|
| `load-content.sh` | Stops at the first failing step; every step is transactional. `--allow-low-coverage` is passed to `python -m bpf.content`. Run it after every `git pull`. |
| `run-ingest.sh` | Needs `BPF_CONTACT_EMAIL` (env file or environment). One ingest at a time: `flock` on `.data/locks/ingest.lock` (Linux), a `mkdir` lock with the owner's pid on macOS (a lock left by a dead process is broken safely). A manual run exits 75 if another holds the lock; `--scheduled` waits up to `BPF_INGEST_LOCK_WAIT_S` (10800 s). Output is appended to `.data/logs/ingest-YYYY-MM-DD.log` (mode 600); a manual run also prints it. Exit codes: bpf-ingest's (0 ok, 1 failed, 2 usage, 3 partial) or 75. |
| `run-ingest.sh --scheduled` | For launchd/cron: no options after the kind; quiet unless the run did not end ok (then one line for launchd's log or cron's mail); starts the cluster if it exists but is stopped. `daily` is a no-op when today's (Budapest) daily run already finished `ok` (`ops_status.py daily-ok`). The schedule starts it at 04:30 and 05:30, so a stale XLSX (exit 1, `StaleXlsxError`) or a partial run at 04:30 is retried once at 05:30. Nothing is retried inside one invocation. |
| `build-web.sh` | Needs Node.js >= 22.12 and the network (`npm ci`). Restart `run-api.sh` afterwards: the API reads `index.html` and its CSP at startup. |
| `run-api.sh` | Binds 127.0.0.1 only. Refuses to start without `web/build/index.html` or with pending migrations (`bpf-migrate --check`); warns when `web/build` is older than `web/src`, `web/static` or the web configuration. Builds nothing. |
| `doctor.sh` | `[ ok ]` / `[WARN]` / `[FAIL]` lines with a `fix:` each: PostgreSQL >= 16, uv, Python >= 3.14, Node.js 22, npm; env file mode 600 and `BPF_CONTACT_EMAIL`; cluster, socket directory mode 700, running; migrations; latest data date and staleness, the last run of each ingest kind, reference data, content (`ops_status.py report`); web build; API health; schedule (and the Mac's time zone). |
| `ops_status.py` | Small helper the scripts run with uv: `daily-ok` (exit 0 if today's daily run finished ok) and `report` (doctor's data checks). Connects as `bpf_ingest`, reads only. |
| `scheduler/` | launchd plist templates (placeholders filled in by `install-macos.sh`), the cron installer, `at-budapest.sh` (lets an hourly cron line through only in its Budapest hour: Debian/Ubuntu cron ignores `CRON_TZ`) and `backup-job.sh`. Schedule (Europe/Budapest): daily ingest 04:30 and 05:30, availability Sundays 05:00, backup 03:15. |
| `caddy/` | `Caddyfile.example` and its [README](caddy/README.md): HTTPS for phones, (a) LAN with Caddy's internal CA or (b) a real domain with Let's Encrypt. |

Files they write (all git-ignored, under `.data/`, i.e. next to `BPF_PGDATA`):

| Item | Where |
|---|---|
| Ingest and backup job logs | `.data/logs/ingest-YYYY-MM-DD.log`, `.data/logs/backup-YYYY-MM-DD.log` (mode 600, kept `BPF_LOG_KEEP_DAYS` = 30 days) |
| launchd's own output (failures only) | `.data/logs/launchd-*.log` |
| Ingest lock | `.data/locks/` |

Environment of the operation scripts (besides the database variables above):

| Variable | Default | Meaning |
|---|---|---|
| `BPF_API_PORT` | `8000` | Port of `run-api.sh` and of doctor's health check |
| `BPF_API_LOG_LEVEL` | `info` | uvicorn log level for `run-api.sh` |
| `BPF_INGEST_LOCK_WAIT_S` | `0` manual, `10800` scheduled | How long `run-ingest.sh` waits for another ingest to finish |
| `BPF_LOG_KEEP_DAYS` | `30` | Days of job logs to keep |
| `BPF_BACKUP_KEEP_DAYS` | `30` | `backup-job.sh` deletes older dumps (the newest 7 are always kept); `0` = keep all |
| `BPF_CRONTAB` | `crontab` | Crontab command of the Linux installers (tests use a stub) |
| `BPF_LOCK_IMPL` | | `mkdir` forces the macOS lock on Linux (tests) |
| `BPF_ALLOW_ROOT` | | `1` lets `load-content.sh`, `run-ingest.sh`, `run-api.sh`, `doctor.sh` and the scheduler (un)installers run as root. CI containers only: the PostgreSQL server must still run as an unprivileged user, and the `db-*.sh` scripts and `backup-job.sh` always refuse root |

The scheduled jobs do not see your shell's environment. The installers copy `BPF_PG_BIN`, `BPF_PGDATA`,
`BPF_ENV_FILE`, `BPF_DB_NAME`, `BPF_BACKUP_DIR`, `BPF_BACKUP_AGE_RECIPIENT`, `BPF_BACKUP_KEEP_DAYS`,
`BPF_LOG_KEEP_DAYS` and `BPF_INGEST_LOCK_WAIT_S` into the jobs when they are set at install time, together with a
`PATH` that finds uv.

## Resetting (destroys the local database)

```sh
deploy/local/db-stop.sh && rm -rf .data/pg .data/pg-admin.env .env.local && deploy/local/db-init.sh
```

`db-init.sh` refuses to run while any of those exist, so it never overwrites data or credentials.

## Restoring a backup

```sh
age --decrypt -i key.txt .data/backups/bpf-….dump.age > /tmp/bpf.dump   # only for encrypted dumps
pg_restore -h .data/sock -p 5544 -U bpf_admin -d bpf --clean --if-exists /tmp/bpf.dump
```

## Notes

- macOS: `db-start.sh` exports `LC_ALL=en_US.UTF-8` before `pg_ctl start`; without it the postmaster aborts with
  "became multithreaded during startup".
- PostgreSQL 17+ uses the builtin `C.UTF-8` collation provider (independent of OS locales); PostgreSQL 16 uses the
  libc `C.UTF-8` locale, or `C` if that locale is not installed.
- The server log records connections, disconnections, DDL and statements slower than 500 ms.
