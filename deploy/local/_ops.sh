# shellcheck shell=bash
# shellcheck disable=SC2034 # the globals set here are used by the scripts that source this file
# Shared helpers for the operation scripts (load-content, run-ingest, run-api, build-web, doctor) and for
# scheduler/. Source it, do not execute it. It sources _common.sh, the database helpers of the db-*.sh scripts.
#
# Portable to macOS (/bin/bash 3.2, BSD userland) and Linux, like _common.sh.
#
# BPF_ALLOW_ROOT=1 lets the operation scripts run as root. It exists for CI containers only: the PostgreSQL
# server itself must still run as an unprivileged user, and the db-*.sh scripts (and scheduler/backup-job.sh,
# which runs db-backup.sh) always refuse root.

# shellcheck source-path=SCRIPTDIR source=_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

BPF_OPS_DIR=$BPF_REPO_ROOT/deploy/local
BPF_SCHED_DIR=$BPF_OPS_DIR/scheduler
BPF_SERVER_DIR=$BPF_REPO_ROOT/server
BPF_WEB_DIR=$BPF_REPO_ROOT/web
BPF_NODE_MIN="22.12" # web/package.json "engines"

bpf_ops_refuse_root() {
    if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
        bpf_die "do not run this as root; run it as your normal user, who owns the database. PostgreSQL" \
            "refuses to run as root (BPF_ALLOW_ROOT=1 is for CI containers only)."
    fi
}

# Prints the path of uv: on PATH, else in the usual install locations (the scheduled jobs have a short PATH).
bpf_find_uv() {
    local candidate
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return 0
    fi
    for candidate in "${HOME:-/nonexistent}/.local/bin/uv" "${HOME:-/nonexistent}/.cargo/bin/uv" \
        /opt/homebrew/bin/uv /usr/local/bin/uv; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

# Sets UV or dies.
bpf_require_uv() {
    UV=$(bpf_find_uv) || bpf_die "uv not found. Install it (macOS: brew install uv; see docs/RUNNING.md)."
}

# Runs a command in server/'s environment: `uv run --locked` syncs server/.venv to server/uv.lock first if
# needed (and fails, changing nothing, if uv.lock does not match pyproject.toml). Needs UV.
bpf_server_run() { (cd "$BPF_SERVER_DIR" && "$UV" run --locked "$@"); }

# After bpf_resolve_paths: the env file must exist; exported so that bpf.config reads the same file.
bpf_require_env_file() {
    [ -f "$ENV_FILE" ] || bpf_die "no env file at $ENV_FILE. Create the database first: deploy/local/db-init.sh"
    export BPF_ENV_FILE=$ENV_FILE
}

# After bpf_resolve_paths: where the jobs write their logs and locks (next to the cluster, in .data/).
bpf_ops_paths() {
    JOB_LOG_DIR=$DATA_ROOT/logs
    LOCK_DIR=$DATA_ROOT/locks
}

# Today's date in Europe/Budapest (the data date of the ingest), YYYY-MM-DD.
bpf_budapest_date() { TZ=Europe/Budapest date +%Y-%m-%d; }

# 0 when the time zone database knows Europe/Budapest (without it, TZ=Europe/Budapest silently means UTC).
bpf_have_budapest_tz() {
    case $(TZ=Europe/Budapest date +%Z) in
        CET | CEST) return 0 ;;
    esac
    return 1
}

# 0 when the local cluster (bpf_resolve_paths' PGDATA_DIR) accepts connections. Changes no global.
bpf_db_accepting() {
    (
        bpf_find_pg_bin
        bpf_load_cluster_conf
        isready=$PG_BIN/pg_isready
        [ -x "$isready" ] || isready=$(command -v pg_isready) || exit 1
        "$isready" -q -h "$SOCKET_DIR" -p "$PG_PORT" -t 5
    ) >/dev/null 2>&1
}

# Prints the Node.js version (v22.22.0). Returns 1 when node is missing, 2 when the version cannot be read,
# 3 when it is older than BPF_NODE_MIN.
bpf_node_version() {
    local version major minor want_major want_minor
    command -v node >/dev/null 2>&1 || return 1
    version=$(node --version 2>/dev/null || true)
    printf '%s' "$version"
    major=$(printf '%s' "$version" | sed -n 's/^v\([0-9][0-9]*\)\..*$/\1/p')
    minor=$(printf '%s' "$version" | sed -n 's/^v[0-9][0-9]*\.\([0-9][0-9]*\)\..*$/\1/p')
    [ -n "$major" ] && [ -n "$minor" ] || return 2
    want_major=${BPF_NODE_MIN%%.*}
    want_minor=${BPF_NODE_MIN#*.}
    if [ "$major" -lt "$want_major" ] || { [ "$major" -eq "$want_major" ] && [ "$minor" -lt "$want_minor" ]; }; then
        return 3
    fi
    return 0
}

# After bpf_require_env_file: prints the directory the API serves the SPA from, with bpf.config's
# precedence: the environment, then the env file, then <repo>/web/build. A relative path is relative to
# server/, where the API runs.
bpf_web_build_dir() {
    local dir=${BPF_WEB_BUILD_DIR:-}
    if [ -z "$dir" ]; then dir=$(bpf_env_get "$ENV_FILE" BPF_WEB_BUILD_DIR || true); fi
    case $dir in \"*\") dir=${dir#\"} && dir=${dir%\"} ;; esac
    if [ -z "$dir" ]; then dir=$BPF_WEB_DIR/build; fi
    case $dir in /*) ;; *) dir=$BPF_SERVER_DIR/$dir ;; esac
    printf '%s' "${dir%/}"
}

# Prints up to 3 web source files that are newer than the build in $1 (nothing when it is current). Only
# meaningful for <repo>/web/build; prints nothing for another directory.
bpf_web_sources_newer() {
    local build=$1
    [ "$build" = "$BPF_WEB_DIR/build" ] && [ -f "$build/index.html" ] || return 0
    find "$BPF_WEB_DIR/src" "$BPF_WEB_DIR/static" "$BPF_WEB_DIR/package.json" "$BPF_WEB_DIR/package-lock.json" \
        "$BPF_WEB_DIR/svelte.config.js" "$BPF_WEB_DIR/vite.config.ts" "$BPF_WEB_DIR/tsconfig.json" \
        -type f -newer "$build/index.html" 2>/dev/null | head -n 3 || true
}

# Values that the schedulers write into crontab lines (inside single quotes) or launchd plists (XML text)
# must need no quoting or escaping: no quotes, backslash, $, backtick, &, <, >, % (special to cron), newline.
bpf_check_job_value() { # $1 = description, $2 = value
    case $2 in
        *"'"* | *'"'* | *\\* | *'$'* | *'`'* | *'&'* | *'<'* | *'>'* | *'%'*)
            bpf_die "$1 contains one of ' \" \\ \$ \` & < > %, which the scheduler does not support: $2"
            ;;
    esac
    if [ "$(printf '%s' "$2" | wc -l | tr -d ' ')" -ne 0 ]; then bpf_die "$1 contains a newline"; fi
}

# The settings the installers copy into the scheduled jobs (the jobs do not see your shell's environment).
BPF_JOB_PASS_THROUGH="BPF_PG_BIN BPF_PGDATA BPF_ENV_FILE BPF_DB_NAME BPF_BACKUP_DIR BPF_BACKUP_AGE_RECIPIENT \
BPF_BACKUP_KEEP_DAYS BPF_LOG_KEEP_DAYS BPF_INGEST_LOCK_WAIT_S"

# Prints "NAME=value" lines for the BPF_JOB_PASS_THROUGH variables that are set, paths made absolute, each
# checked with bpf_check_job_value (dies on a bad one).
bpf_job_settings() {
    local var value
    for var in $BPF_JOB_PASS_THROUGH; do
        value=${!var:-}
        [ -n "$value" ] || continue
        case $var in
            BPF_PG_BIN | BPF_PGDATA | BPF_ENV_FILE | BPF_BACKUP_DIR) value=$(bpf_abspath "$value") ;;
            BPF_BACKUP_AGE_RECIPIENT) case $value in age1*) ;; *) value=$(bpf_abspath "$value") ;; esac ;;
            BPF_BACKUP_KEEP_DAYS | BPF_LOG_KEEP_DAYS | BPF_INGEST_LOCK_WAIT_S)
                case $value in *[!0-9]*) bpf_die "$var must be a whole number: $value" ;; esac
                ;;
        esac
        bpf_check_job_value "$var" "$value"
        printf '%s=%s\n' "$var" "$value"
    done
}

# Prints a PATH for the scheduled jobs: uv's directory first, then the usual system directories ($@).
bpf_job_path() {
    local uv_path uv_dir dir path=
    uv_path=$(bpf_find_uv) || bpf_die "uv not found. Install it first (docs/RUNNING.md)."
    uv_dir=$(cd "$(dirname "$uv_path")" && pwd -P)
    for dir in "$uv_dir" "$@"; do
        case ":$path:" in *":$dir:"*) continue ;; esac
        path=${path:+$path:}$dir
    done
    bpf_check_job_value "PATH for the jobs" "$path"
    printf '%s' "$path"
}
