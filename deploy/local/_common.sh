# shellcheck shell=bash
# shellcheck disable=SC2034 # the globals set here are used by the scripts that source this file
# Shared helpers for deploy/local/db-*.sh. Source it, do not execute it.
#
# Portable to macOS (/bin/bash 3.2, BSD userland, Homebrew postgresql@NN) and Linux (GNU userland,
# distro PostgreSQL 16+ or PGDG 18). Bash 3.2 means: no associative arrays, no mapfile, no ${x,,},
# and never expand a possibly-empty array under `set -u`.
#
# Environment overrides (all optional; the defaults are what a developer wants):
#   BPF_PG_BIN       directory holding initdb/pg_ctl/postgres (default: discovered, see bpf_find_pg_bin)
#   BPF_PGDATA       cluster data directory                     (default: <repo>/.data/pg)
#   BPF_PG_PORT      TCP port, also part of the socket name     (default: 5544)
#   BPF_SOCKET_DIR   unix socket directory, mode 0700           (default: <dirname PGDATA>/sock, or
#                    ${TMPDIR:-/tmp}/bpf-sock-<uid>-<port> when that socket path would be >= 103 bytes)
#   BPF_ENV_FILE     app credentials file written by db-init    (default: <repo>/.env.local)
#   BPF_DB_NAME      application database                       (default: bpf)
#   BPF_BACKUP_DIR   where db-backup.sh writes dumps            (default: <dirname PGDATA>/backups)
#
# Files derived from BPF_PGDATA (so a test can redirect everything with one variable):
#   <dirname PGDATA>/pg-admin.env       bpf_admin superuser password (chmod 600; never used by the app)
#   <dirname PGDATA>/log/postgresql.log server log written by pg_ctl -l
#
# For an initialised cluster, port and socket directory are read back from <PGDATA>/bpf.conf, which
# db-init.sh writes, so db-start/db-stop/db-backup always agree with the running configuration.

BPF_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
BPF_SOCKET_PATH_MAX=103   # sun_path is 104 bytes on macOS (108 on Linux) including the trailing NUL

# libpq/PostgreSQL environment that could silently redirect or alter our connections. Every
# connection below passes host, port, user and database explicitly; passwords travel in PGPASSWORD
# set for one command only.
unset PGHOST PGHOSTADDR PGPORT PGDATABASE PGUSER PGPASSWORD PGPASSFILE PGSERVICE PGSERVICEFILE \
    PGOPTIONS PGSSLMODE PGREQUIRESSL PGTARGETSESSIONATTRS PGAPPNAME PGDATA PGCLIENTENCODING
# Our pg_hba.conf allows scram-sha-256 only, so a server asking for anything else (a cleartext or md5
# password, trust) is an impostor on the port or in the socket directory: make psql, pg_dump and the app
# (bpf.db pins the same) refuse it instead of sending it a password. libpq >= 16; older ones ignore it.
export PGREQUIREAUTH=scram-sha-256

bpf_info() { printf '%s\n' "$*"; }
bpf_warn() { printf 'warning: %s\n' "$*" >&2; }
bpf_die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

bpf_refuse_root() {
    if [ "$(id -u)" -eq 0 ]; then
        bpf_die "do not run this as root. PostgreSQL refuses to run as root; run it as your normal user."
    fi
}

bpf_is_macos() { [ "$(uname -s)" = "Darwin" ]; }

# Byte length of a string (not characters: a socket path limit is in bytes).
bpf_byte_len() { printf '%s' "$1" | wc -c | tr -d ' '; }

# 32 random bytes from the kernel CSPRNG as 64 lowercase hex characters (no shell-special characters).
bpf_gen_password() {
    local pw
    pw=$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')
    [ "${#pw}" -eq 64 ] || bpf_die "could not read 32 random bytes from /dev/urandom"
    printf '%s' "$pw"
}

# Prints the major version of the server binaries in directory $1; fails if they are not there.
bpf_pg_major() {
    local dir=$1 out major
    [ -x "$dir/initdb" ] && [ -x "$dir/pg_ctl" ] && [ -x "$dir/postgres" ] || return 1
    out=$("$dir/postgres" --version 2>/dev/null) || return 1
    # "postgres (PostgreSQL) 18.6 (Debian 18.6-1.pgdg13+2)" -> 18
    major=$(printf '%s\n' "$out" | sed -n 's/^[^0-9]*\([0-9][0-9]*\).*$/\1/p' | head -n 1)
    [ -n "$major" ] || return 1
    printf '%s' "$major"
}

# Sets PG_BIN, PG_MAJOR, PG_VERSION_STRING, PSQL and PG_DUMP. Order: $BPF_PG_BIN, then
# `pg_config --bindir` (if it holds server binaries >= 16), then the highest version among the usual
# Homebrew (Apple silicon and Intel), Debian/Ubuntu and RHEL install locations.
bpf_find_pg_bin() {
    local dir major best="" best_major=0
    if [ -n "${BPF_PG_BIN:-}" ]; then
        major=$(bpf_pg_major "$BPF_PG_BIN") ||
            bpf_die "BPF_PG_BIN=$BPF_PG_BIN does not contain PostgreSQL server binaries (initdb, pg_ctl, postgres)"
        [ "$major" -ge 16 ] || bpf_die "BPF_PG_BIN=$BPF_PG_BIN is PostgreSQL $major; version 16 or newer is required"
        best=$BPF_PG_BIN
        best_major=$major
    else
        if command -v pg_config >/dev/null 2>&1; then
            dir=$(pg_config --bindir 2>/dev/null || true)
            if [ -n "$dir" ] && major=$(bpf_pg_major "$dir") && [ "$major" -ge 16 ]; then
                best=$dir
                best_major=$major
            fi
        fi
        if [ -z "$best" ]; then
            for dir in /opt/homebrew/opt/postgresql@*/bin /usr/local/opt/postgresql@*/bin \
                /usr/lib/postgresql/*/bin /usr/pgsql-*/bin; do
                [ -d "$dir" ] || continue # an unmatched glob stays literal
                major=$(bpf_pg_major "$dir") || continue
                if [ "$major" -gt "$best_major" ]; then
                    best=$dir
                    best_major=$major
                fi
            done
        fi
        if [ -z "$best" ] || [ "$best_major" -lt 16 ]; then
            bpf_die "no PostgreSQL >= 16 server binaries found. Install one (macOS: brew install postgresql@18;" \
                "Debian/Ubuntu: apt install postgresql) or set BPF_PG_BIN to the directory containing initdb."
        fi
    fi
    PG_BIN=$best
    PG_MAJOR=$best_major
    PG_VERSION_STRING=$("$PG_BIN/postgres" --version)
    if [ -x "$PG_BIN/psql" ]; then PSQL=$PG_BIN/psql; else PSQL=$(command -v psql || true); fi
    [ -n "$PSQL" ] || bpf_die "psql not found next to $PG_BIN/postgres or on PATH"
    PG_DUMP=$PG_BIN/pg_dump
}

bpf_print_pg_version() { bpf_info "Using $PG_VERSION_STRING from $PG_BIN"; }

# Values that end up inside postgresql.conf, pg_hba.conf, SQL and the env file must stay boring.
bpf_check_path() { # $1 = description, $2 = path
    case $2 in
        /*) ;;
        *) bpf_die "$1 must be an absolute path: $2" ;;
    esac
    case $2 in
        *"'"* | *'"'* | *\\* | *'$'* | *'`'* | *'#'*)
            bpf_die "$1 contains a quote, backslash, \$, backtick or #, which is not supported: $2"
            ;;
    esac
    if [ "$(printf '%s' "$2" | wc -l | tr -d ' ')" -ne 0 ]; then bpf_die "$1 contains a newline"; fi
}

bpf_abspath() { # prints $1 made absolute against $PWD (does not resolve symlinks; the path may not exist)
    case $1 in
        /*) printf '%s' "$1" ;;
        *) printf '%s/%s' "$(pwd -P)" "$1" ;;
    esac
}

# Sets PGDATA_DIR, DATA_ROOT, PG_PORT, DB_NAME, ENV_FILE, ADMIN_ENV_FILE, LOG_DIR, LOG_FILE, BACKUP_DIR
# and SOCKET_DIR from the environment (see the header). For an existing cluster call bpf_load_cluster_conf
# afterwards: the port and socket directory it was initialised with win over the environment.
bpf_resolve_paths() {
    PGDATA_DIR=$(bpf_abspath "${BPF_PGDATA:-$BPF_REPO_ROOT/.data/pg}")
    PGDATA_DIR=${PGDATA_DIR%/}
    bpf_check_path "BPF_PGDATA" "$PGDATA_DIR"
    DATA_ROOT=$(dirname "$PGDATA_DIR")
    ADMIN_ENV_FILE=$DATA_ROOT/pg-admin.env
    LOG_DIR=$DATA_ROOT/log
    LOG_FILE=$LOG_DIR/postgresql.log
    BACKUP_DIR=$(bpf_abspath "${BPF_BACKUP_DIR:-$DATA_ROOT/backups}")
    bpf_check_path "BPF_BACKUP_DIR" "$BACKUP_DIR"

    PG_PORT=${BPF_PG_PORT:-5544}
    case $PG_PORT in
        '' | *[!0-9]*) bpf_die "BPF_PG_PORT must be a number: $PG_PORT" ;;
    esac
    if [ "$PG_PORT" -lt 1024 ] || [ "$PG_PORT" -gt 65535 ]; then
        bpf_die "BPF_PG_PORT must be between 1024 and 65535: $PG_PORT"
    fi

    DB_NAME=${BPF_DB_NAME:-bpf}
    if ! printf '%s' "$DB_NAME" | grep -Eq '^[a-z_][a-z0-9_]{0,62}$'; then
        bpf_die "BPF_DB_NAME must match ^[a-z_][a-z0-9_]{0,62}\$: $DB_NAME"
    fi

    ENV_FILE=$(bpf_abspath "${BPF_ENV_FILE:-$BPF_REPO_ROOT/.env.local}")
    bpf_check_path "BPF_ENV_FILE" "$ENV_FILE"

    local sock
    if [ -n "${BPF_SOCKET_DIR:-}" ]; then
        sock=$(bpf_abspath "$BPF_SOCKET_DIR")
        sock=${sock%/}
        if [ "$(bpf_byte_len "$sock/.s.PGSQL.$PG_PORT")" -ge "$BPF_SOCKET_PATH_MAX" ]; then
            bpf_die "BPF_SOCKET_DIR is too long: the socket path $sock/.s.PGSQL.$PG_PORT must be under" \
                "$BPF_SOCKET_PATH_MAX bytes"
        fi
    else
        sock=$DATA_ROOT/sock
        if [ "$(bpf_byte_len "$sock/.s.PGSQL.$PG_PORT")" -ge "$BPF_SOCKET_PATH_MAX" ]; then
            sock=${TMPDIR:-/tmp}
            sock="${sock%/}/bpf-sock-$(id -u)-$PG_PORT"
        fi
    fi
    bpf_check_path "socket directory" "$sock"
    SOCKET_DIR=$sock
}

bpf_cluster_exists() { [ -f "$PGDATA_DIR/PG_VERSION" ]; }

bpf_require_cluster() {
    bpf_cluster_exists || bpf_die "no cluster at $PGDATA_DIR. Create it with deploy/local/db-init.sh"
    [ -f "$PGDATA_DIR/bpf.conf" ] ||
        bpf_die "$PGDATA_DIR was not created by deploy/local/db-init.sh (bpf.conf is missing)"
    local data_major
    data_major=$(cat "$PGDATA_DIR/PG_VERSION")
    if [ "$data_major" != "$PG_MAJOR" ]; then
        bpf_die "the cluster at $PGDATA_DIR is PostgreSQL $data_major but the binaries in $PG_BIN are" \
            "$PG_MAJOR. Point BPF_PG_BIN at PostgreSQL $data_major."
    fi
}

# Reads port and socket directory back from <PGDATA>/bpf.conf (written by db-init.sh in a fixed format).
bpf_load_cluster_conf() {
    local conf=$PGDATA_DIR/bpf.conf port sock
    port=$(sed -n 's/^port = \([0-9][0-9]*\)$/\1/p' "$conf" | tail -n 1)
    sock=$(sed -n "s/^unix_socket_directories = '\(.*\)'\$/\1/p" "$conf" | tail -n 1)
    [ -n "$port" ] && [ -n "$sock" ] || bpf_die "could not read port and unix_socket_directories from $conf"
    if [ -n "${BPF_PG_PORT:-}" ] && [ "$BPF_PG_PORT" != "$port" ]; then
        bpf_warn "BPF_PG_PORT=$BPF_PG_PORT ignored: the cluster at $PGDATA_DIR uses port $port"
    fi
    PG_PORT=$port
    SOCKET_DIR=$sock
}

# Creates directory $1 (and parents, mode 0700) if missing. Does not touch an existing directory.
bpf_ensure_dir() {
    [ -d "$1" ] || (umask 077 && mkdir -p "$1") || bpf_die "cannot create directory $1"
}

# Creates directory $1 (and parents) and makes sure it is ours, not a symlink, and mode 0700.
bpf_ensure_private_dir() {
    local dir=$1
    if [ ! -d "$dir" ]; then
        (umask 077 && mkdir -p "$dir") || bpf_die "cannot create directory $dir"
    fi
    [ ! -L "$dir" ] || bpf_die "$dir is a symlink; refusing to use it"
    [ -O "$dir" ] || bpf_die "$dir exists but is not owned by $(id -un); refusing to use it"
    chmod 700 "$dir"
}

# 0 = running, 3 = not running (pg_ctl status semantics); anything else is an error.
bpf_cluster_status() {
    local rc=0
    "$PG_BIN/pg_ctl" -D "$PGDATA_DIR" status >/dev/null 2>&1 || rc=$?
    return "$rc"
}

bpf_start_cluster() {
    local rc=0
    bpf_cluster_status || rc=$?
    if [ "$rc" -eq 0 ]; then
        bpf_info "PostgreSQL is already running (data: $PGDATA_DIR, port $PG_PORT)."
        return 0
    fi
    [ "$rc" -eq 3 ] || bpf_die "pg_ctl status failed for $PGDATA_DIR (exit $rc)"
    bpf_ensure_private_dir "$SOCKET_DIR"
    bpf_ensure_private_dir "$LOG_DIR"
    if bpf_is_macos; then
        # Without a UTF-8 LC_ALL the postmaster aborts with "became multithreaded during startup".
        export LC_ALL=en_US.UTF-8
    fi
    if ! "$PG_BIN/pg_ctl" -D "$PGDATA_DIR" -l "$LOG_FILE" -w -t 60 start >/dev/null; then
        printf 'error: PostgreSQL did not start. Last lines of %s:\n' "$LOG_FILE" >&2
        tail -n 20 "$LOG_FILE" >&2 || true
        exit 1
    fi
    bpf_info "PostgreSQL started (data: $PGDATA_DIR, port $PG_PORT, socket dir $SOCKET_DIR, log $LOG_FILE)."
}

bpf_stop_cluster() {
    local rc=0
    bpf_cluster_status || rc=$?
    if [ "$rc" -eq 3 ]; then
        bpf_info "PostgreSQL is not running (data: $PGDATA_DIR)."
        return 0
    fi
    [ "$rc" -eq 0 ] || bpf_die "pg_ctl status failed for $PGDATA_DIR (exit $rc)"
    "$PG_BIN/pg_ctl" -D "$PGDATA_DIR" -w -t 60 -m fast stop >/dev/null || bpf_die "pg_ctl stop failed"
    bpf_info "PostgreSQL stopped (data: $PGDATA_DIR)."
}

# Prints the value of KEY from an env file written by db-init.sh (KEY='value' or KEY=value lines).
# The file is parsed, never sourced.
bpf_env_get() { # $1 = file, $2 = key
    local line value
    [ -r "$1" ] || return 1
    line=$(grep -E "^$2=" "$1" | tail -n 1) || return 1
    value=${line#*=}
    case $value in
        \'*\') value=${value#\'} && value=${value%\'} ;;
    esac
    [ -n "$value" ] || return 1
    printf '%s' "$value"
}
