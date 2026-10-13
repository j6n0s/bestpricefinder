#!/usr/bin/env bash
# Installs the bestpricefinder schedule into the current user's crontab (Linux), as one marked block:
#
#   daily 04:30 and 05:30 Europe/Budapest   run-ingest.sh --scheduled daily
#   Sundays 05:00 Europe/Budapest           run-ingest.sh --scheduled availability
#   daily 03:15 Europe/Budapest             scheduler/backup-job.sh
#
#   deploy/local/scheduler/install-linux.sh           # install, or replace the block from an earlier install
#   deploy/local/scheduler/install-linux.sh --print   # show the block; change nothing
#   deploy/local/scheduler/uninstall-linux.sh         # remove the block (the rest of the crontab stays)
#
# Budapest time on any machine time zone: Debian/Ubuntu cron ignores CRON_TZ (only cronie honours it), and a
# CRON_TZ line would also shift the user's own entries that follow it. So the block sets no variables: every
# line fires hourly at the job's minute, and scheduler/at-budapest.sh lets it through only in the job's
# Budapest hour (and weekday). Cron does not catch up runs missed while the machine was off.
#
# The jobs print nothing unless they fail (cron then mails that line, if mail is set up); their logs are in
# <data>/logs/ (.data/logs/ by default). These settings are copied into the block when they are set at install
# time (cron jobs do not see your shell's environment): BPF_PG_BIN, BPF_PGDATA, BPF_ENV_FILE, BPF_DB_NAME,
# BPF_BACKUP_DIR, BPF_BACKUP_AGE_RECIPIENT (a public key, not a secret), BPF_BACKUP_KEEP_DAYS,
# BPF_LOG_KEEP_DAYS, BPF_INGEST_LOCK_WAIT_S. Re-run the installer after changing them or moving the repository.
#
# Environment: BPF_CRONTAB, the crontab command (default: crontab; tests point it at a stub).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=../_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"

SCHED_DIR=$BPF_REPO_ROOT/deploy/local/scheduler
BEGIN_MARK="# >>> bestpricefinder schedule (deploy/local/scheduler/install-linux.sh) >>>"
END_MARK="# <<< bestpricefinder schedule <<<"
PASS_THROUGH="BPF_PG_BIN BPF_PGDATA BPF_ENV_FILE BPF_DB_NAME BPF_BACKUP_DIR BPF_BACKUP_AGE_RECIPIENT \
BPF_BACKUP_KEEP_DAYS BPF_LOG_KEEP_DAYS BPF_INGEST_LOCK_WAIT_S"
CRONTAB=${BPF_CRONTAB:-crontab}

print_only=0
case $# in
    0) ;;
    1) if [ "$1" = "--print" ]; then print_only=1; else
        printf 'usage: %s [--print]\n' "$0" >&2
        exit 2
    fi ;;
    *)
        printf 'usage: %s [--print]\n' "$0" >&2
        exit 2
        ;;
esac

if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
    bpf_die "run this as your normal user (cron runs the jobs as the crontab's owner), not as root."
fi
if bpf_is_macos && [ "$print_only" -eq 0 ]; then
    bpf_die "on macOS use deploy/local/scheduler/install-macos.sh (launchd); cron is deprecated there."
fi

# Values end up in crontab command lines inside single quotes: keep them boring. % is special to cron.
check_value() { # $1 = description, $2 = value
    case $2 in
        *"'"* | *'"'* | *\\* | *'$'* | *'`'* | *'&'* | *'<'* | *'>'* | *'%'*)
            bpf_die "$1 contains one of ' \" \\ \$ \` & < > %, which the scheduler does not support: $2"
            ;;
    esac
    if [ "$(printf '%s' "$2" | wc -l | tr -d ' ')" -ne 0 ]; then bpf_die "$1 contains a newline"; fi
}
check_value "the repository path" "$BPF_REPO_ROOT"

zone=$(TZ=Europe/Budapest date +%Z)
case $zone in
    CET | CEST) ;;
    *) bpf_die "the time zone database has no Europe/Budapest (got $zone). Install tzdata (apt install tzdata)." ;;
esac

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
uv_path=$(find_uv) || bpf_die "uv not found. Install it first (docs/RUNNING.md)."
uv_dir=$(cd "$(dirname "$uv_path")" && pwd -P)
job_path=
for dir in "$uv_dir" /usr/local/bin /usr/bin /bin; do
    case ":$job_path:" in *":$dir:"*) continue ;; esac
    job_path=${job_path:+$job_path:}$dir
done
check_value "PATH for the jobs" "$job_path"

# ── the block ───────────────────────────────────────────────────────────────────────────────────────
env_prefix="PATH='$job_path'"
for var in $PASS_THROUGH; do
    value=${!var:-}
    [ -n "$value" ] || continue
    case $var in
        BPF_PG_BIN | BPF_PGDATA | BPF_ENV_FILE | BPF_BACKUP_DIR) value=$(bpf_abspath "$value") ;;
        BPF_BACKUP_AGE_RECIPIENT) case $value in age1*) ;; *) value=$(bpf_abspath "$value") ;; esac ;;
    esac
    check_value "$var" "$value"
    env_prefix="$env_prefix $var='$value'"
done
at="'$SCHED_DIR/at-budapest.sh'"
ingest="'$BPF_REPO_ROOT/deploy/local/run-ingest.sh' --scheduled"
block="$BEGIN_MARK
# Times are Europe/Budapest whatever this machine's time zone: each line fires hourly and at-budapest.sh lets
# it through only in the listed Budapest hour(s). Daily ingest 04:30 and 05:30 (the second run is a no-op
# after a good first one), availability Sundays 05:00, backup 03:15. Logs: .data/logs/. Edit the installer,
# not these lines.
30 * * * * $env_prefix $at any 4,5 $ingest daily
0 * * * * $env_prefix $at sun 5 $ingest availability
15 * * * * $env_prefix $at any 3 '$SCHED_DIR/backup-job.sh'
$END_MARK"

if [ "$print_only" -eq 1 ]; then
    printf '%s\n' "$block"
    exit 0
fi

# ── install ─────────────────────────────────────────────────────────────────────────────────────────
command -v "$CRONTAB" >/dev/null 2>&1 || bpf_die "$CRONTAB not found. Install cron (Debian/Ubuntu: apt install cron)."
work=$(mktemp -d "${TMPDIR:-/tmp}/bpf-cron.XXXXXX")
trap 'rm -rf "$work"' EXIT

if ! "$CRONTAB" -l >"$work/current" 2>"$work/err"; then
    if grep -qi 'no crontab' "$work/err"; then
        : >"$work/current"
    else
        cat "$work/err" >&2
        bpf_die "could not read the current crontab with '$CRONTAB -l'"
    fi
fi
begins=$(grep -cxF "$BEGIN_MARK" "$work/current" || true)
ends=$(grep -cxF "$END_MARK" "$work/current" || true)
if [ "$begins" != "$ends" ] || [ "$begins" -gt 1 ]; then
    bpf_die "the crontab holds a damaged bestpricefinder block ($begins start / $ends end markers). Fix it with" \
        "'crontab -e' (delete the block), then run this again."
fi
# Everything except an earlier block; the new block goes at the end.
awk -v b="$BEGIN_MARK" -v e="$END_MARK" '$0 == b { skip = 1; next } $0 == e { skip = 0; next } !skip' \
    "$work/current" >"$work/new"
printf '%s\n' "$block" >>"$work/new"
"$CRONTAB" "$work/new" || bpf_die "'$CRONTAB' rejected the new crontab; nothing was changed"

"$CRONTAB" -l >"$work/check" 2>/dev/null || bpf_die "could not read the crontab back"
grep -qxF "$BEGIN_MARK" "$work/check" || bpf_die "the block is missing from the installed crontab"
if [ "$begins" -eq 1 ]; then bpf_info "Replaced the bestpricefinder block in the crontab."; else
    bpf_info "Added the bestpricefinder block to the crontab."
fi

if ! pgrep -x cron >/dev/null 2>&1 && ! pgrep -x crond >/dev/null 2>&1; then
    bpf_warn "no cron daemon (cron/crond) seems to be running: the jobs will not run until one is" \
        "(Debian/Ubuntu: sudo systemctl enable --now cron)."
fi
bpf_resolve_paths
bpf_info "Logs: $DATA_ROOT/logs/. Remove the schedule: $SCHED_DIR/uninstall-linux.sh"
