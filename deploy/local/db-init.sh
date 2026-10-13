#!/usr/bin/env bash
# Creates the dedicated, hardened PostgreSQL cluster for bestpricefinder (docs/ARCHITECTURE.md,
# "Database security model"). Run once, as your normal user:
#
#   deploy/local/db-init.sh            # then: cd server && uv run bpf-migrate
#
# What it does:
#   - initdb with SCRAM auth for local and host connections and a superuser `bpf_admin` (random password);
#   - postgresql.conf include file `bpf.conf`: localhost only, port 5544, private unix socket dir (0700),
#     scram-sha-256, connection/DDL/slow-statement logging, conservative limits;
#   - a strict pg_hba.conf: scram-sha-256 only, the app roles on the app database only, everything else rejected;
#   - roles bpf_owner (NOLOGIN, owns everything), bpf_migrator (may SET ROLE bpf_owner, inherits nothing),
#     bpf_ingest and bpf_api (read-only transactions, timeouts, connection limit), with random passwords;
#   - database `bpf` owned by bpf_owner, with no privileges for PUBLIC;
#   - writes the app credentials to .env.local (chmod 600) and the superuser password to
#     .data/pg-admin.env (chmod 600). Passwords never appear on a command line or in the server log.
#
# It never overwrites anything: if the cluster or either credentials file exists, it stops and says how to
# reset. The cluster is LEFT RUNNING at the end; stop it with db-stop.sh. Overrides: see _common.sh.
set -euo pipefail
umask 077

# shellcheck source=_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

bpf_refuse_root
bpf_find_pg_bin
bpf_resolve_paths
bpf_print_pg_version

reset_hint="To start over: deploy/local/db-stop.sh; rm -rf '$PGDATA_DIR' '$ADMIN_ENV_FILE' '$ENV_FILE'"
if bpf_cluster_exists; then
    bpf_die "a cluster already exists at $PGDATA_DIR; refusing to touch it. $reset_hint"
fi
if [ -e "$PGDATA_DIR" ] && [ -n "$(ls -A "$PGDATA_DIR" 2>/dev/null)" ]; then
    bpf_die "$PGDATA_DIR exists and is not empty; refusing to touch it. $reset_hint"
fi
for f in "$ENV_FILE" "$ADMIN_ENV_FILE"; do
    if [ -e "$f" ]; then bpf_die "$f already exists; refusing to overwrite credentials. $reset_hint"; fi
done
[ -d "$(dirname "$ENV_FILE")" ] || bpf_die "directory of BPF_ENV_FILE does not exist: $(dirname "$ENV_FILE")"

bpf_ensure_dir "$DATA_ROOT"
bpf_ensure_private_dir "$SOCKET_DIR"
bpf_ensure_private_dir "$LOG_DIR"

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/bpf-init.XXXXXX")
initdb_done=0
started=0
on_exit() {
    local rc=$?
    if [ -n "${work_dir:-}" ] && [ -d "$work_dir" ]; then rm -rf "$work_dir"; fi
    if [ "$rc" -ne 0 ]; then
        if [ "$started" -eq 1 ]; then
            "$PG_BIN/pg_ctl" -D "$PGDATA_DIR" -w -m fast stop >/dev/null 2>&1 || true
        fi
        if [ "$initdb_done" -eq 1 ]; then
            printf 'error: db-init failed; the half-initialised cluster was stopped and left for inspection.\n' >&2
            printf '       %s\n' "$reset_hint" >&2
        fi
    fi
    return "$rc"
}
trap on_exit EXIT

admin_pw=$(bpf_gen_password)
migrator_pw=$(bpf_gen_password)
ingest_pw=$(bpf_gen_password)
api_pw=$(bpf_gen_password)

# ── initdb ────────────────────────────────────────────────────────────────────────────────────────
pwfile=$work_dir/admin.pw
printf '%s\n' "$admin_pw" >"$pwfile" # printf is a builtin: the password is not on any argv

initdb_args=(
    -D "$PGDATA_DIR"
    --username=bpf_admin
    --pwfile="$pwfile"
    --auth-local=scram-sha-256
    --auth-host=scram-sha-256
    --encoding=UTF8
    --data-checksums
)
if [ "$PG_MAJOR" -ge 17 ]; then
    # Builtin provider: code-point collation with Unicode semantics, independent of the OS's libc locales.
    # The libc categories are pinned to C so the user's shell locale (e.g. hu_HU) cannot leak in.
    initdb_args+=(--locale-provider=builtin --builtin-locale=C.UTF-8 --locale=C)
else
    c_utf8=$(locale -a 2>/dev/null | grep -Eic '^c\.utf-?8$' || true)
    if [ "${c_utf8:-0}" -gt 0 ]; then
        initdb_args+=(--locale=C.UTF-8)
    else
        bpf_warn "the C.UTF-8 locale is not installed; using --no-locale (C collation)"
        initdb_args+=(--no-locale)
    fi
fi

bpf_info "Initialising cluster in $PGDATA_DIR ..."
initdb_done=1
if ! "$PG_BIN/initdb" "${initdb_args[@]}" >"$work_dir/initdb.log" 2>&1; then
    cat "$work_dir/initdb.log" >&2
    bpf_die "initdb failed"
fi
rm -f "$pwfile"

# ── server configuration ──────────────────────────────────────────────────────────────────────────
# bpf_load_cluster_conf in _common.sh parses `port` and `unix_socket_directories` back from this file:
# keep their format.
cat >"$PGDATA_DIR/bpf.conf" <<EOF
# bestpricefinder settings, written by deploy/local/db-init.sh. Included at the end of postgresql.conf.
listen_addresses = 'localhost'
port = $PG_PORT
unix_socket_directories = '$SOCKET_DIR'
unix_socket_permissions = 0700
password_encryption = 'scram-sha-256'
ssl = off
max_connections = 50
idle_in_transaction_session_timeout = '60s'
log_connections = on
log_disconnections = on
log_min_duration_statement = 500
log_line_prefix = '%m [%p] %u@%d/%a '
log_statement = 'ddl'
EOF
printf "\n# bestpricefinder (deploy/local/db-init.sh)\ninclude_if_exists = 'bpf.conf'\n" >>"$PGDATA_DIR/postgresql.conf"

cat >"$PGDATA_DIR/pg_hba.conf" <<EOF
# bestpricefinder pg_hba.conf, written by deploy/local/db-init.sh. First match wins.
# scram-sha-256 only. No trust, peer, ident, md5 or password lines, ever.
# TYPE  DATABASE     USER                                ADDRESS        METHOD
local   $DB_NAME     bpf_migrator,bpf_ingest,bpf_api                    scram-sha-256
host    $DB_NAME     bpf_migrator,bpf_ingest,bpf_api     127.0.0.1/32   scram-sha-256
host    $DB_NAME     bpf_migrator,bpf_ingest,bpf_api     ::1/128        scram-sha-256
local   all          bpf_admin                                          scram-sha-256
host    all          bpf_admin                           127.0.0.1/32   scram-sha-256
host    all          bpf_admin                           ::1/128        scram-sha-256
# Everything else is refused explicitly. The replication lines exist because 'all' does not match them.
local   all          all                                                reject
local   replication  all                                                reject
host    all          all                                 0.0.0.0/0      reject
host    all          all                                 ::/0           reject
host    replication  all                                 0.0.0.0/0      reject
host    replication  all                                 ::/0           reject
EOF

# ── start, then roles and database ────────────────────────────────────────────────────────────────
started=1
bpf_start_cluster

admin_psql() { # $1 = database; SQL on stdin. The admin password is in the environment of psql only.
    PGPASSWORD=$admin_pw "$PSQL" -X -q -w -v ON_ERROR_STOP=1 -h "$SOCKET_DIR" -p "$PG_PORT" -U bpf_admin \
        -d "$1" -v dbname="$DB_NAME" -f -
}

bpf_info "Creating roles and database $DB_NAME ..."
BPF_MIGRATOR_PASSWORD=$migrator_pw BPF_INGEST_PASSWORD=$ingest_pw BPF_API_PASSWORD=$api_pw \
    admin_psql postgres <<'SQL'
-- Keep the cleartext passwords below out of the server log, also if a statement fails.
SET log_statement = 'none';
SET log_min_duration_statement = -1;
SET log_min_error_statement = 'panic';
SET password_encryption = 'scram-sha-256';
\getenv migrator_pw BPF_MIGRATOR_PASSWORD
\getenv ingest_pw BPF_INGEST_PASSWORD
\getenv api_pw BPF_API_PASSWORD

CREATE ROLE bpf_owner NOLOGIN;
CREATE ROLE bpf_migrator LOGIN PASSWORD :'migrator_pw';
CREATE ROLE bpf_ingest LOGIN PASSWORD :'ingest_pw';
CREATE ROLE bpf_api LOGIN CONNECTION LIMIT 20 PASSWORD :'api_pw';
-- The migrator may switch to the owner (SET ROLE bpf_owner) but has none of its rights implicitly.
GRANT bpf_owner TO bpf_migrator WITH INHERIT FALSE, SET TRUE;
\unset migrator_pw
\unset ingest_pw
\unset api_pw

CREATE DATABASE :"dbname" OWNER bpf_owner TEMPLATE template0 ENCODING 'UTF8';
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dbname" TO bpf_migrator, bpf_ingest, bpf_api;
-- Nobody but the superuser needs the maintenance databases.
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;

ALTER ROLE bpf_api IN DATABASE :"dbname" SET default_transaction_read_only = on;
ALTER ROLE bpf_api IN DATABASE :"dbname" SET statement_timeout = '3s';
ALTER ROLE bpf_api IN DATABASE :"dbname" SET lock_timeout = '1s';
ALTER ROLE bpf_api IN DATABASE :"dbname" SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE bpf_api IN DATABASE :"dbname" SET search_path = api;
ALTER ROLE bpf_ingest IN DATABASE :"dbname" SET statement_timeout = '10min';
ALTER ROLE bpf_ingest IN DATABASE :"dbname" SET lock_timeout = '10s';
ALTER ROLE bpf_ingest IN DATABASE :"dbname" SET search_path = core, app, ops, api;
ALTER ROLE bpf_migrator IN DATABASE :"dbname" SET lock_timeout = '10s';
ALTER ROLE bpf_migrator IN DATABASE :"dbname" SET search_path = public;
SQL

admin_psql "$DB_NAME" <<'SQL'
-- The owner role creates in public (schema_migrations lives there); nobody else may even look in it.
ALTER SCHEMA public OWNER TO bpf_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

DO $$
DECLARE
    r text;
BEGIN
    IF NOT has_schema_privilege('bpf_owner', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'bpf_owner cannot create in schema public';
    END IF;
    FOREACH r IN ARRAY ARRAY['public', 'bpf_migrator', 'bpf_ingest', 'bpf_api'] LOOP
        IF has_schema_privilege(r, 'public', 'CREATE') OR has_schema_privilege(r, 'public', 'USAGE') THEN
            RAISE EXCEPTION '% has privileges on schema public', r;
        END IF;
        IF has_database_privilege(r, current_database(), 'CREATE')
           OR has_database_privilege(r, current_database(), 'TEMPORARY') THEN
            RAISE EXCEPTION '% may create schemas or temporary tables in %', r, current_database();
        END IF;
    END LOOP;
    IF has_database_privilege('public', current_database(), 'CONNECT') THEN
        RAISE EXCEPTION 'PUBLIC may connect to %', current_database();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_auth_members
                   WHERE roleid = 'bpf_owner'::regrole AND member = 'bpf_migrator'::regrole
                     AND set_option AND NOT inherit_option AND NOT admin_option) THEN
        RAISE EXCEPTION 'bpf_migrator must be a member of bpf_owner WITH SET TRUE, INHERIT FALSE';
    END IF;
END $$;
SQL

# ── credentials files (created with noclobber, mode 600) ──────────────────────────────────────────
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
(
    set -o noclobber
    cat >"$ADMIN_ENV_FILE" <<EOF
# bestpricefinder local cluster superuser, written by deploy/local/db-init.sh at $created_at.
# For maintenance scripts (db-backup.sh) only. The app never uses it. Never commit or share it.
BPF_ADMIN_USER='bpf_admin'
BPF_ADMIN_PASSWORD='$admin_pw'
BPF_DB_NAME='$DB_NAME'
EOF
) || bpf_die "could not create $ADMIN_ENV_FILE"
chmod 600 "$ADMIN_ENV_FILE"

(
    set -o noclobber
    cat >"$ENV_FILE" <<EOF
# bestpricefinder app credentials, written by deploy/local/db-init.sh at $created_at.
# chmod 600 and git-ignored: never commit it. To rotate, reset the cluster (deploy/local/README.md).
BPF_DB_HOST='$SOCKET_DIR'
BPF_DB_PORT='$PG_PORT'
BPF_DB_NAME='$DB_NAME'
BPF_MIGRATOR_PASSWORD='$migrator_pw'
BPF_INGEST_PASSWORD='$ingest_pw'
BPF_API_PASSWORD='$api_pw'
EOF
) || bpf_die "could not create $ENV_FILE"
chmod 600 "$ENV_FILE"

bpf_info ""
bpf_info "Done. PostgreSQL $PG_MAJOR cluster '$DB_NAME' is RUNNING on localhost:$PG_PORT and socket dir $SOCKET_DIR."
bpf_info "  app credentials:   $ENV_FILE (chmod 600)"
bpf_info "  superuser (admin): $ADMIN_ENV_FILE (chmod 600)"
bpf_info "  server log:        $LOG_FILE"
bpf_info "Next: cd server && uv run bpf-migrate     Stop: deploy/local/db-stop.sh     Start: deploy/local/db-start.sh"
