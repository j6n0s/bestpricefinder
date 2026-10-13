#!/usr/bin/env bash
# Installs the bestpricefinder schedule as launchd agents of the current user (macOS):
#
#   com.bestpricefinder.ingest-daily         daily 04:30 and 05:30   run-ingest.sh --scheduled daily
#   com.bestpricefinder.ingest-availability  Sundays 05:00           run-ingest.sh --scheduled availability
#   com.bestpricefinder.backup               daily 03:15             scheduler/backup-job.sh
#
#   deploy/local/scheduler/install-macos.sh                     # install (or reinstall) and load them
#   deploy/local/scheduler/install-macos.sh --any-timezone      # install although the Mac is not on Budapest time
#   deploy/local/scheduler/install-macos.sh --render-only DIR   # only write the filled-in plists to DIR
#   deploy/local/scheduler/uninstall-macos.sh                   # remove them
#
# launchd uses the Mac's local time, so the Mac must be set to Europe/Budapest (System Settings > General >
# Date & Time); the script refuses otherwise (--any-timezone overrides: then the times above are local
# times). A sleeping Mac runs missed jobs when it wakes (launchd merges the missed 04:30 and 05:30 runs into
# one). The jobs write their logs to <data>/logs/ (.data/logs/ by default).
#
# The plists are rendered from the templates next to this script: the repository path, a PATH that finds uv
# (and Homebrew's PostgreSQL and age), and these settings if they are set when you run the installer (the
# jobs do not see your shell's environment): BPF_PG_BIN, BPF_PGDATA, BPF_ENV_FILE, BPF_DB_NAME,
# BPF_BACKUP_DIR, BPF_BACKUP_AGE_RECIPIENT (a public key, not a secret), BPF_BACKUP_KEEP_DAYS,
# BPF_LOG_KEEP_DAYS, BPF_INGEST_LOCK_WAIT_S. Re-run the installer after changing any of them or moving
# the repository. Keep the repository outside ~/Documents, ~/Desktop, ~/Downloads and iCloud Drive: macOS
# privacy protection (TCC) blocks background jobs from reading those folders.
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=../_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"

SCHED_DIR=$BPF_REPO_ROOT/deploy/local/scheduler
LABELS="com.bestpricefinder.ingest-daily com.bestpricefinder.ingest-availability com.bestpricefinder.backup"
PASS_THROUGH="BPF_PG_BIN BPF_PGDATA BPF_ENV_FILE BPF_DB_NAME BPF_BACKUP_DIR BPF_BACKUP_AGE_RECIPIENT \
BPF_BACKUP_KEEP_DAYS BPF_LOG_KEEP_DAYS BPF_INGEST_LOCK_WAIT_S"

usage() {
    printf 'usage: %s [--any-timezone] | --render-only DIR\n' "$0" >&2
    exit 2
}

render_dir=
any_tz=0
while [ $# -gt 0 ]; do
    case $1 in
        --any-timezone) any_tz=1 ;;
        --render-only)
            [ $# -ge 2 ] || usage
            render_dir=$2
            shift
            ;;
        *) usage ;;
    esac
    shift
done

if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
    bpf_die "run this as your normal user (the agents run as the user who installs them), not as root."
fi
if [ -z "$render_dir" ] && ! bpf_is_macos; then
    bpf_die "this installs launchd agents (macOS). On Linux use deploy/local/scheduler/install-linux.sh."
fi

# Values end up inside XML and launchd's environment: keep them boring (no quoting or escaping needed).
check_value() { # $1 = description, $2 = value
    case $2 in
        *"'"* | *'"'* | *\\* | *'$'* | *'`'* | *'&'* | *'<'* | *'>'* | *'%'*)
            bpf_die "$1 contains one of ' \" \\ \$ \` & < > %, which the scheduler does not support: $2"
            ;;
    esac
    if [ "$(printf '%s' "$2" | wc -l | tr -d ' ')" -ne 0 ]; then bpf_die "$1 contains a newline"; fi
}
check_value "the repository path" "$BPF_REPO_ROOT"

# ── time zone ───────────────────────────────────────────────────────────────────────────────────────
if [ -z "$render_dir" ]; then
    tz_link=$(readlink /etc/localtime 2>/dev/null || true)
    case $tz_link in
        */zoneinfo/Europe/Budapest) bpf_info "Time zone: Europe/Budapest (launchd's local times are Budapest times)." ;;
        *)
            message="the Mac's time zone is not Europe/Budapest (/etc/localtime -> ${tz_link:-unknown}); launchd runs at local times."
            if [ "$any_tz" -eq 0 ]; then
                bpf_die "$message Set the time zone to Budapest (System Settings > General > Date & Time), or pass" \
                    "--any-timezone to accept local times (the ingest needs a run after about 04:00 Budapest time)."
            fi
            bpf_warn "$message Installing anyway (--any-timezone)."
            ;;
    esac
    case $BPF_REPO_ROOT in
        "${HOME:-/nonexistent}/Documents"* | "${HOME:-/nonexistent}/Desktop"* | "${HOME:-/nonexistent}/Downloads"* | \
            "${HOME:-/nonexistent}/Library/Mobile Documents"*)
            bpf_warn "the repository is in $BPF_REPO_ROOT: macOS privacy protection may block launchd jobs from" \
                "reading it ('Operation not permitted' in .data/logs/launchd-*.log). Move it, e.g. to ~/src/."
            ;;
    esac
fi

# ── what goes into the plists ───────────────────────────────────────────────────────────────────────
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
uv_path=$(find_uv) || bpf_die "uv not found. Install it first (brew install uv; docs/RUNNING.md)."
uv_dir=$(cd "$(dirname "$uv_path")" && pwd -P)

job_path=
for dir in "$uv_dir" /opt/homebrew/bin /usr/local/bin /usr/bin /bin /usr/sbin /sbin; do
    case ":$job_path:" in *":$dir:"*) continue ;; esac
    job_path=${job_path:+$job_path:}$dir
done
check_value "PATH for the jobs" "$job_path"

bpf_resolve_paths
JOB_LOG_DIR=$DATA_ROOT/logs
check_value "the log directory" "$JOB_LOG_DIR"

extra_env=
for var in $PASS_THROUGH; do
    value=${!var:-}
    [ -n "$value" ] || continue
    case $var in
        BPF_PG_BIN | BPF_PGDATA | BPF_ENV_FILE | BPF_BACKUP_DIR) value=$(bpf_abspath "$value") ;;
        BPF_BACKUP_AGE_RECIPIENT) case $value in age1*) ;; *) value=$(bpf_abspath "$value") ;; esac ;;
    esac
    check_value "$var" "$value"
    extra_env="$extra_env		<key>$var</key>
		<string>$value</string>
"
done

render() { # $1 = template, $2 = output file
    local line in_note=0 template_name
    template_name=$(basename "$1")
    {
        while IFS= read -r line || [ -n "$line" ]; do
            if [ "$in_note" -eq 1 ]; then
                case $line in *'-->'*) in_note=0 ;; esac
                continue
            fi
            case $line in
                '<!-- TEMPLATE:'*)
                    case $line in *'-->'*) ;; *) in_note=1 ;; esac
                    continue
                    ;;
                *'<!-- __BPF_EXTRA_ENV__ -->'*)
                    printf '%s' "$extra_env"
                    continue
                    ;;
                '<!DOCTYPE '*)
                    printf '%s\n' "$line"
                    printf '<!-- Written by deploy/local/scheduler/install-macos.sh from %s. -->\n' "$template_name"
                    continue
                    ;;
            esac
            line=${line//__BPF_REPO__/$BPF_REPO_ROOT}
            line=${line//__BPF_PATH__/$job_path}
            line=${line//__BPF_LOG_DIR__/$JOB_LOG_DIR}
            printf '%s\n' "$line"
        done <"$1"
    } >"$2.tmp"
    if grep -q '__BPF_[A-Z_]*__' "$2.tmp"; then
        rm -f "$2.tmp"
        bpf_die "internal error: a placeholder was left in $2"
    fi
    if command -v plutil >/dev/null 2>&1 && ! plutil -lint -s "$2.tmp"; then
        rm -f "$2.tmp"
        bpf_die "the rendered $2 is not a valid property list"
    fi
    chmod 644 "$2.tmp"
    mv -f "$2.tmp" "$2"
}

if [ -n "$render_dir" ]; then
    [ -d "$render_dir" ] || bpf_die "--render-only: $render_dir is not a directory"
    for label in $LABELS; do
        render "$SCHED_DIR/$label.plist" "$render_dir/$label.plist"
        bpf_info "wrote $render_dir/$label.plist"
    done
    exit 0
fi

# ── install and load ────────────────────────────────────────────────────────────────────────────────
command -v launchctl >/dev/null 2>&1 || bpf_die "launchctl not found"
bpf_ensure_dir "$DATA_ROOT"
bpf_ensure_private_dir "$JOB_LOG_DIR" # launchd does not create the directory of StandardOutPath
agents_dir=${HOME:?HOME is not set}/Library/LaunchAgents
[ -d "$agents_dir" ] || (umask 022 && mkdir -p "$agents_dir")
uid=$(id -u)
for label in $LABELS; do
    plist=$agents_dir/$label.plist
    launchctl bootout "gui/$uid/$label" >/dev/null 2>&1 || true # not loaded yet: fine
    render "$SCHED_DIR/$label.plist" "$plist"
    launchctl enable "gui/$uid/$label"
    tries=0
    # bootout can take a moment to finish; bootstrap fails with "Input/output error" until it has.
    until launchctl bootstrap "gui/$uid" "$plist"; do
        tries=$((tries + 1))
        [ "$tries" -lt 5 ] || bpf_die "launchctl bootstrap failed for $plist"
        sleep 1
    done
    launchctl print "gui/$uid/$label" >/dev/null || bpf_die "$label is not loaded after bootstrap"
    bpf_info "loaded $label ($plist)"
done
bpf_info ""
bpf_info "Installed. Logs: $JOB_LOG_DIR/ (ingest-*.log, backup-*.log; launchd-*.log hold only failures)."
bpf_info "Check: launchctl print gui/$uid/com.bestpricefinder.ingest-daily | grep -E 'state|last exit'"
bpf_info "Run now: launchctl kickstart gui/$uid/com.bestpricefinder.ingest-daily     Remove: $SCHED_DIR/uninstall-macos.sh"
