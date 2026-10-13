# Local PostgreSQL for bestpricefinder

A dedicated, hardened PostgreSQL cluster for this app only (docs/ARCHITECTURE.md, "Database security model").
It never touches another PostgreSQL you may already run. Works on macOS (Homebrew `postgresql@18`, also 16/17)
and on Linux (distro PostgreSQL 16+ or PGDG 18). Run every script as your normal user, never as root.

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
