#!/usr/bin/env bash
# Runs one GVH Árfigyelő ingest (python -m bpf.ingest) against the local database, as bpf_ingest, under a
# lock, with a log file. Run it as your normal user, from any directory:
#
#   deploy/local/run-ingest.sh reference              # chains, categories, stores (3 requests)
#   deploy/local/run-ingest.sh daily [--max-requests N] [-v] ...   # any bpf-ingest option after the kind
#   deploy/local/run-ingest.sh availability           # weekly: which stores carry which product (slow)
#   deploy/local/run-ingest.sh --scheduled daily      # what launchd/cron run (see scheduler/)
#
# Requirements: the env file (BPF_ENV_FILE, default .env.local; written by db-init.sh) and BPF_CONTACT_EMAIL,
# either in that file or in the environment: GVH gets it in the User-Agent (BUILD-BRIEF §4.1 trap 11).
#
# Lock: only one ingest of any kind runs at a time (they all talk to GVH, at most 1 request/s in total):
# flock(1) on <data>/locks/ingest.lock where it exists (Linux), else a mkdir lock with the owner's pid
# (macOS). A manual run fails at once (exit 75) when another ingest holds the lock; a scheduled run waits
# for it (BPF_INGEST_LOCK_WAIT_S, default 10800 s).
#
# Log: everything (ours, uv's and bpf-ingest's) is appended to <data>/logs/ingest-YYYY-MM-DD.log (mode 600;
# <data> is .data/ by default, the directory above BPF_PGDATA). Logs older than BPF_LOG_KEEP_DAYS (default 30)
# are deleted. A manual run also shows the output; --scheduled prints nothing unless the run did not end ok.
# Nothing here prints a secret: the env file is never echoed, and bpf-ingest never logs credentials.
#
# --scheduled (no further options allowed):
#   - starts the local cluster first if it exists but is not running (a laptop after a reboot);
#   - daily: does nothing when today's (Budapest) daily run already finished ok. The scheduler starts the
#     daily ingest at 04:30 and again at 05:30 Europe/Budapest, so a stale XLSX at 04:30 (bpf-ingest exit 1,
#     error "StaleXlsxError": the CDN still served yesterday's file, BUILD-BRIEF §4.1 trap 4) or a partial
#     run is retried once, and the 05:30 run is a no-op after a good 04:30 run. Nothing is retried within
#     one invocation.
#
# Exit codes: those of bpf-ingest (0 ok, 1 failed, 2 usage error, 3 partial: data written, something
# missing), plus 75 when another ingest holds the lock. A skipped scheduled daily run exits 0.
#
# Environment: BPF_ENV_FILE, BPF_PGDATA, BPF_PG_BIN (see _common.sh); BPF_INGEST_LOCK_WAIT_S;
# BPF_LOG_KEEP_DAYS; BPF_LOCK_IMPL=mkdir forces the macOS lock (tests); BPF_ALLOW_ROOT=1 lets it run as
# root (CI containers only: the PostgreSQL server itself still runs as an unprivileged user).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

SCRIPT_DIR=$BPF_REPO_ROOT/deploy/local
EX_LOCKED=75

usage() {
    printf 'usage: %s [--scheduled] {reference|daily|availability} [bpf-ingest options]\n' "$0" >&2
    exit 2
}

scheduled=0
if [ "${1:-}" = "--scheduled" ]; then
    scheduled=1
    shift
fi
[ $# -ge 1 ] || usage
kind=$1
shift
case $kind in
    reference | daily | availability) ;;
    *) usage ;;
esac
if [ "$scheduled" -eq 1 ] && [ $# -gt 0 ]; then
    bpf_die "--scheduled takes no bpf-ingest options (got: $*)"
fi

if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
    bpf_die "do not run this as root; run it as the user who owns the database (BPF_ALLOW_ROOT=1 is for CI only)."
fi

bpf_resolve_paths
JOB_LOG_DIR=$DATA_ROOT/logs
LOCK_DIR=$DATA_ROOT/locks

keep_days=${BPF_LOG_KEEP_DAYS:-30}
case $keep_days in '' | *[!0-9]*) bpf_die "BPF_LOG_KEEP_DAYS must be a whole number of days: $keep_days" ;; esac
[ "$keep_days" -ge 1 ] || bpf_die "BPF_LOG_KEEP_DAYS must be at least 1"
if [ "$scheduled" -eq 1 ]; then lock_wait=${BPF_INGEST_LOCK_WAIT_S:-10800}; else lock_wait=${BPF_INGEST_LOCK_WAIT_S:-0}; fi
case $lock_wait in '' | *[!0-9]*) bpf_die "BPF_INGEST_LOCK_WAIT_S must be a whole number of seconds: $lock_wait" ;; esac

# ── log file ────────────────────────────────────────────────────────────────────────────────────────
bpf_ensure_dir "$DATA_ROOT"
bpf_ensure_private_dir "$JOB_LOG_DIR"
JOB_LOG=$JOB_LOG_DIR/ingest-$(date +%Y-%m-%d).log
touch "$JOB_LOG"
chmod 600 "$JOB_LOG"
if [ "$scheduled" -eq 1 ]; then
    # Keep the caller's stdout (launchd's log file, or cron's mail) on fd 3 for the one-line failure notice;
    # everything else goes to the job log.
    exec 3>&1 >>"$JOB_LOG" 2>&1
fi

log_line() { printf '%s run-ingest[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$$" "$*" >>"$JOB_LOG"; }

say() { # a line in the job log; a manual run also shows it
    log_line "$*"
    if [ "$scheduled" -eq 0 ]; then printf '%s\n' "$*"; fi
}

notify() { # scheduled runs: one line for launchd's log / cron's mail
    if [ "$scheduled" -eq 1 ]; then printf 'bestpricefinder %s ingest: %s (log: %s)\n' "$kind" "$*" "$JOB_LOG" >&3; fi
}

die() {
    log_line "error: $*"
    if [ "$scheduled" -eq 1 ]; then notify "failed: $*"; else printf 'error: %s\n' "$*" >&2; fi
    exit 1
}

# Logs of the last $keep_days days are kept (find -mtime +N: N full days older than now).
find "$JOB_LOG_DIR" -maxdepth 1 -type f \( -name 'ingest-*.log' -o -name 'backup-*.log' \) \
    -mtime +"$((keep_days - 1))" -exec rm -f {} + 2>/dev/null || true

if [ "$scheduled" -eq 1 ]; then mode="scheduled"; else mode="manual"; fi
say "=== $kind ingest ($mode) starting; Budapest time $(TZ=Europe/Budapest date '+%Y-%m-%d %H:%M %Z') ==="

# ── prerequisites ───────────────────────────────────────────────────────────────────────────────────
[ -f "$ENV_FILE" ] || die "no env file at $ENV_FILE. Create the database first: deploy/local/db-init.sh"
export BPF_ENV_FILE=$ENV_FILE
if [ -z "${BPF_CONTACT_EMAIL:-}" ] && ! bpf_env_get "$ENV_FILE" BPF_CONTACT_EMAIL >/dev/null; then
    die "BPF_CONTACT_EMAIL is not set. Add the line BPF_CONTACT_EMAIL=you@example.org to $ENV_FILE:" \
        "GVH receives it in the User-Agent so that they can reach the operator (BUILD-BRIEF §4.1 trap 11)."
fi

find_uv() {
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
UV=$(find_uv) || die "uv not found. Install it (macOS: brew install uv; see docs/RUNNING.md)."

server_python() { # python in the server project's environment (uv syncs it to uv.lock first if needed)
    (cd "$BPF_REPO_ROOT/server" && PYTHONUNBUFFERED=1 "$UV" run --locked python "$@")
}

db_accepting() { # 0 when the local cluster accepts connections
    (
        bpf_find_pg_bin >/dev/null
        bpf_load_cluster_conf
        isready=$PG_BIN/pg_isready
        [ -x "$isready" ] || isready=$(command -v pg_isready)
        "$isready" -q -h "$SOCKET_DIR" -p "$PG_PORT" -t 5
    ) 2>/dev/null
}

if [ "$scheduled" -eq 1 ] && bpf_cluster_exists && ! db_accepting; then
    say "PostgreSQL is not running; starting it with deploy/local/db-start.sh"
    # 3>&-: the postmaster must not inherit cron's mail pipe or launchd's log descriptor.
    "$SCRIPT_DIR/db-start.sh" 3>&- || die "PostgreSQL could not be started (see above)"
fi

# ── lock ────────────────────────────────────────────────────────────────────────────────────────────
LOCK_HELD_DIR=
# shellcheck disable=SC2329 # invoked by the EXIT trap below
release_lock() {
    if [ -n "$LOCK_HELD_DIR" ] && [ "$(cat "$LOCK_HELD_DIR/pid" 2>/dev/null || true)" = "$$" ]; then
        rm -rf "$LOCK_HELD_DIR"
    fi
    LOCK_HELD_DIR=
}
trap release_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir_lock_stale() { # $1 = lock dir; 0 when it belongs to no live run-ingest.sh
    local pid command
    pid=$(cat "$1/pid" 2>/dev/null || true)
    case $pid in
        '' | *[!0-9]*)
            # No pid yet: the owner may be between mkdir and writing it. Stale only after a minute.
            [ -n "$(find "$1" -maxdepth 0 -mmin +1 2>/dev/null)" ]
            return
            ;;
    esac
    command=$(ps -ww -p "$pid" -o command= 2>/dev/null || true)
    case $command in
        *run-ingest.sh*) return 1 ;; # alive (ps works whatever the owner, unlike kill -0)
    esac
    return 0 # dead, or the pid was reused by another program after a crash or reboot
}

acquire_mkdir_lock() { # $1 = seconds to wait
    local dir=$LOCK_DIR/ingest.lock.d deadline now announced=0
    deadline=$(($(date +%s) + $1))
    while :; do
        if mkdir "$dir" 2>/dev/null; then
            printf '%s\n' "$$" >"$dir/pid"
            LOCK_HELD_DIR=$dir
            return 0
        fi
        if mkdir_lock_stale "$dir"; then
            # Break a stale lock under a second lock, so that two waiters never both remove it (the second
            # would remove the first one's fresh lock). A break lock left by a killed process expires.
            if mkdir "$dir.break" 2>/dev/null; then
                if mkdir_lock_stale "$dir"; then
                    say "removing a stale lock (pid $(cat "$dir/pid" 2>/dev/null || printf 'unknown') is no running run-ingest.sh)"
                    rm -rf "$dir"
                fi
                rmdir "$dir.break"
                continue
            elif [ -n "$(find "$dir.break" -maxdepth 0 -mmin +1 2>/dev/null)" ]; then
                rmdir "$dir.break" 2>/dev/null || true
                continue
            fi
        fi
        now=$(date +%s)
        [ "$now" -lt "$deadline" ] || return 1
        if [ "$announced" -eq 0 ]; then
            say "another ingest holds the lock (pid $(cat "$dir/pid" 2>/dev/null || printf 'unknown')); waiting up to $1 s"
            announced=1
        fi
        if [ $((deadline - now)) -gt 5 ]; then sleep 5; else sleep $((deadline - now)); fi
    done
}

acquire_lock() { # $1 = seconds to wait
    bpf_ensure_private_dir "$LOCK_DIR"
    if [ "${BPF_LOCK_IMPL:-}" != "mkdir" ] && command -v flock >/dev/null 2>&1; then
        # fd 9 stays open in bpf-ingest too, so the lock is held for exactly as long as the run lives.
        exec 9>>"$LOCK_DIR/ingest.lock"
        if flock -n 9; then return 0; fi
        [ "$1" -gt 0 ] || return 1
        say "another ingest holds the lock; waiting up to $1 s"
        flock -w "$1" 9
        return
    fi
    acquire_mkdir_lock "$1"
}

if ! acquire_lock "$lock_wait"; then
    if [ "$lock_wait" -gt 0 ]; then
        say "gave up after waiting $lock_wait s for the lock"
    else
        say "another ingest is running (lock in $LOCK_DIR); try again when it has finished"
    fi
    notify "skipped: another ingest held the lock"
    exit "$EX_LOCKED"
fi

# ── a scheduled daily run after a good one is a no-op ───────────────────────────────────────────────
if [ "$scheduled" -eq 1 ] && [ "$kind" = "daily" ]; then
    check_rc=0
    check=$(server_python "$SCRIPT_DIR/ops_status.py" daily-ok 2>&1) || check_rc=$?
    say "$check"
    if [ "$check_rc" -eq 0 ]; then
        say "=== nothing to do ==="
        exit 0
    fi
fi

# ── run ─────────────────────────────────────────────────────────────────────────────────────────────
offset=$(wc -c <"$JOB_LOG" | tr -d ' ')
say "running: python -m bpf.ingest $kind${*:+ $*}"
rc=0
if [ "$scheduled" -eq 1 ]; then
    server_python -m bpf.ingest "$kind" "$@" 3>&- || rc=$?
else
    set +e
    # tee ignores Ctrl-C, so the interrupted run can still record itself and print its last lines.
    server_python -m bpf.ingest "$kind" "$@" 2>&1 | (trap '' INT && exec tee -a "$JOB_LOG")
    rc=${PIPESTATUS[0]}
    set -e
fi

# bpf-ingest's one-line summary: "<kind> <date>: <status> (run N, ...)[ error: <Type>: <message>]"
summary=$(tail -c +"$((offset + 1))" "$JOB_LOG" |
    grep -E "^$kind [0-9]{4}-[0-9]{2}-[0-9]{2}: (ok|partial|failed) " | tail -n 1 || true)
case $rc in
    0) say "=== ok: ${summary:-done} ===" ;;
    3)
        say "=== partial: data were written but something is missing; deploy/local/doctor.sh shows the warnings ==="
        notify "partial (data written, something missing)"
        ;;
    1)
        case $summary in
            *"error: StaleXlsxError"*)
                say "=== failed: stale XLSX (the GVH CDN still serves an older file; BUILD-BRIEF §4.1 trap 4). No prices"
                say "    were written. The scheduler runs the daily ingest at 04:30 and 05:30 Budapest time; otherwise run it"
                say "    again later. ==="
                notify "failed: stale XLSX (the scheduler runs it at 04:30 and 05:30 Budapest time)"
                ;;
            *)
                say "=== failed: ${summary:-bpf-ingest could not start (see above)} ==="
                notify "failed"
                ;;
        esac
        ;;
    2) say "=== usage error (see above) ===" ;;
    *)
        say "=== stopped with exit code $rc ==="
        notify "stopped with exit code $rc"
        ;;
esac
exit "$rc"
