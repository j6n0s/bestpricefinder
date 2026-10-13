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
deploy/local/db-harden.sh        # re-apply sql/harden-functions.sql (no large objects, advisory locks only where used, temp_file_limit for bpf_api); db-init.sh already does this for new clusters
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

With the default paths everything above is git-ignored (`.data/` and `.env.local`). If you change
`BPF_PGDATA`, `BPF_BACKUP_DIR` or `BPF_ENV_FILE`, keep them under `.data/` or outside the repository. The parent
directory of `BPF_PGDATA` receives `pg-admin.env` (the superuser password), the backups (unless `BPF_BACKUP_DIR`
is set), the server log and the jobs' logs and locks, and outside `.data/` git may not ignore them:
`BPF_PGDATA=$PWD/pgdata`, for example, would write the superuser password to `./pg-admin.env`.
`git check-ignore -v <file>` shows whether git ignores a file. Passwords are 32 random bytes (hex), passed to
`psql` through the environment (`\getenv`), never on a command line, and never written to the server log.

Roles: `bpf_owner` (NOLOGIN, owns every object), `bpf_migrator` (can `SET ROLE bpf_owner`, inherits nothing),
`bpf_ingest` (data writes, timeouts) and `bpf_api` (SELECT on the `api` views only, 20 connections; read-only
transactions and a 3 s statement timeout by default). The read-only mode and the timeouts of both roles are
per-role session defaults (`ALTER ROLE … SET`). They catch mistakes in our code, but any session can `SET` them
differently, so they are not a security boundary. What keeps `bpf_api` from changing a table is that it has no
write privilege on any table.
`pg_hba.conf` allows only SCRAM, only these roles, only on the `bpf` database; `bpf_admin` may reach any database;
everything else is rejected explicitly. `server/tests/test_db_roles.py` checks all of this automatically.

## Options (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `BPF_PG_BIN` | discovered | Directory with `initdb`, `pg_ctl`, `postgres` (>= 16). Discovery: `pg_config --bindir`, then the highest of `/opt/homebrew/opt/postgresql@*/bin`, `/usr/local/opt/postgresql@*/bin`, `/usr/lib/postgresql/*/bin`, `/usr/pgsql-*/bin` |
| `BPF_PGDATA` | `.data/pg` | Cluster directory. Log, socket, admin credentials (`pg-admin.env`), backups and the jobs' logs and locks live next to it, in its parent directory: keep it under `.data/` or outside the repository (see above) |
| `BPF_PG_PORT` | `5544` | Port (used by `db-init.sh`; later scripts read it from `<PGDATA>/bpf.conf`) |
| `BPF_SOCKET_DIR` | `<dirname PGDATA>/sock` | Socket directory (used by `db-init.sh`; later read from `bpf.conf`) |
| `BPF_ENV_FILE` | `.env.local` | Where `db-init.sh` writes the app credentials (the server reads the same variable) |
| `BPF_DB_NAME` | `bpf` | Application database name |
| `BPF_BACKUP_DIR` | `<dirname PGDATA>/backups` | Backup directory |
| `BPF_BACKUP_AGE_RECIPIENT` | unset | `age1…` public key or recipients file: the dump is piped into `age`, so only `*.dump.age` is written. If set and `age` is missing, no backup is made |

## Operation scripts

```sh
deploy/local/load-content.sh                      # bpf-migrate, then validate data/ and load it as bpf_ingest
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
| `load-content.sh` | `bpf-migrate`, then `python -m bpf.content`, which validates `data/` (against the database's GVH categories once a reference ingest has run), checks recipe coverage (with the latest GVH prices once a daily ingest has run) and loads everything in one transaction; invalid content writes nothing. `--allow-low-coverage` is passed on. Run it after every `git pull`. |
| `run-ingest.sh` | Needs `BPF_CONTACT_EMAIL` (env file or environment). One ingest of any kind at a time: `flock` on `.data/locks/ingest.lock` on Linux, a `mkdir` lock (`.data/locks/ingest.lock.d` with the owner's pid) on macOS; a lock whose owner is no longer a running `run-ingest.sh` is broken safely. A manual run exits 75 if another holds the lock; `--scheduled` waits up to `BPF_INGEST_LOCK_WAIT_S` (10800 s). Output is appended to `.data/logs/ingest-YYYY-MM-DD.log` (Budapest date, mode 600); a manual run also prints it. Exit codes: bpf-ingest's (0 ok, 1 failed, 2 usage, 3 partial) or 75. |
| `run-ingest.sh --scheduled` | For launchd/cron: no options after the kind; quiet unless the run did not end ok (then one line for launchd's log or cron's mail); starts the cluster if it exists but is stopped. `daily` is a no-op when today's (Budapest) daily run already finished `ok` (`ops_status.py daily-ok`). The schedule starts it at 04:30 and 05:30, so a stale XLSX (exit 1, `StaleXlsxError`) or a partial run at 04:30 is retried once at 05:30. Nothing is retried inside one invocation. |
| `build-web.sh` | Needs Node.js >= 22.12 and the network (`npm ci`). Restart `run-api.sh` afterwards: the API reads `index.html` and its CSP at startup. |
| `run-api.sh` | Binds 127.0.0.1 only. Refuses to start without `web/build/index.html` or with pending migrations (`bpf-migrate --check`); warns when `web/build` is older than `web/src`, `web/static` or the web configuration. Builds nothing. |
| `doctor.sh` | `[ ok ]` / `[WARN]` / `[FAIL]` lines with a `fix:` each: PostgreSQL >= 16, uv, Python >= 3.14, Node.js 22, npm; env file mode 600 and `BPF_CONTACT_EMAIL`; cluster, socket directory mode 700, running; migrations; latest data date and staleness, the last run of each ingest kind, reference data, content (`ops_status.py report`); web build; API health; schedule (and the Mac's time zone). |
| `ops_status.py` | Small helper the scripts run with uv: `daily-ok` (exit 0 if today's daily run finished ok) and `report` (doctor's data checks). Connects as `bpf_ingest`, reads only. |
| `_ops.sh` | Shell helpers shared by the operation scripts (it sources `_common.sh`, the helpers of the `db-*.sh` scripts). |
| `scheduler/` | launchd plist templates (placeholders filled in by `install-macos.sh`), the cron installer, `at-budapest.sh` (lets an hourly cron line through only in its Budapest hour: Debian/Ubuntu cron ignores `CRON_TZ`) and `backup-job.sh`. Schedule (Europe/Budapest): daily ingest 04:30 and 05:30, availability Sundays 05:00, backup 03:15. |
| `caddy/` | `Caddyfile.example` and its [README](caddy/README.md): HTTPS for phones, (a) LAN with Caddy's internal CA or (b) a real domain with Let's Encrypt. |

Files they write (under `.data/` by default, i.e. next to `BPF_PGDATA`, and git-ignored there):

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

Stop `run-api.sh` and make sure no ingest is running, then, from the repository root:

```sh
deploy/local/db-start.sh
# Encrypted dumps only: decrypt into the private backup directory (mode 700).
age --decrypt -i ~/.config/bestpricefinder/backup-key.txt -o .data/backups/restore.dump .data/backups/bpf-<timestamp>.dump.age
# pg_restore asks for the bpf_admin password: BPF_ADMIN_PASSWORD in .data/pg-admin.env. The socket directory
# must be an absolute path (BPF_DB_HOST in .env.local); a relative one would be taken for a host name.
pg_restore -h "$PWD/.data/sock" -p 5544 -U bpf_admin -d bpf --clean --if-exists --single-transaction \
    .data/backups/restore.dump        # or the unencrypted .data/backups/bpf-<timestamp>.dump
rm .data/backups/restore.dump
deploy/local/run-api.sh
```

`--single-transaction`: if anything fails, the database stays as it was.

## Notes

- macOS: `db-start.sh` exports `LC_ALL=en_US.UTF-8` before `pg_ctl start`; without it the postmaster aborts with
  "became multithreaded during startup".
- PostgreSQL 17+ uses the builtin `C.UTF-8` collation provider (independent of OS locales); PostgreSQL 16 uses the
  libc `C.UTF-8` locale, or `C` if that locale is not installed.
- The server log records connections, disconnections, DDL and statements slower than 500 ms.
