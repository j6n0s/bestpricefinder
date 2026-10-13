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
# Budapest time whatever the machine's time zone: Debian/Ubuntu cron ignores CRON_TZ (only cronie honours it),
# and a CRON_TZ line would also shift the user's own entries that follow it. So the block sets no variables:
# every line fires hourly at the job's minute, and scheduler/at-budapest.sh lets it through only in the job's
# Budapest hour (and weekday). That needs a machine time zone whose UTC offset is a whole number of hours
# (the installer checks). Cron does not catch up runs missed while the machine was off.
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

# shellcheck source-path=SCRIPTDIR source=../_ops.sh
. "$(dirname "${BASH_SOURCE[0]}")/../_ops.sh"

BEGIN_MARK="# >>> bestpricefinder schedule (deploy/local/scheduler/install-linux.sh) >>>"
END_MARK="# <<< bestpricefinder schedule <<<"
CRONTAB=${BPF_CRONTAB:-crontab}

print_only=0
case $# in
    0) ;;
    1)
        if [ "$1" = "--print" ]; then print_only=1; else
            printf 'usage: %s [--print]\n' "$0" >&2
            exit 2
        fi
        ;;
    *)
        printf 'usage: %s [--print]\n' "$0" >&2
        exit 2
        ;;
esac

if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
    bpf_die "run this as your normal user (cron runs the jobs as the crontab's owner), not as root."
fi
if bpf_is_macos && [ "$print_only" -eq 0 ]; then
    bpf_die "on macOS use deploy/local/scheduler/install-macos.sh (launchd)."
fi

bpf_check_job_value "the repository path" "$BPF_REPO_ROOT"
bpf_resolve_paths # rejects unusable BPF_PGDATA / BPF_ENV_FILE / BPF_BACKUP_DIR values before anything is written
bpf_have_budapest_tz || bpf_die "the time zone database has no Europe/Budapest. Install tzdata (apt install tzdata)."
# at-budapest.sh gates by Budapest HOUR only: a line firing at local minute 30 must also be minute 30 in
# Budapest, which holds when the local UTC offset is a whole number of hours (Budapest's always is).
local_offset=$(date +%z)
case $local_offset in
    [+-][0-9][0-9]00) ;;
    *)
        bpf_die "this machine's UTC offset is $local_offset, not a whole number of hours: the jobs would run at" \
            "the wrong minute. Set the machine's time zone (e.g. sudo timedatectl set-timezone Europe/Budapest)."
        ;;
esac

job_path=$(bpf_job_path /usr/local/bin /usr/bin /bin)
settings=$(bpf_job_settings)

# ── the block ───────────────────────────────────────────────────────────────────────────────────────
env_prefix="PATH='$job_path'"
while IFS= read -r line; do
    [ -n "$line" ] || continue
    env_prefix="$env_prefix ${line%%=*}='${line#*=}'"
done <<EOF
$settings
EOF
# /bin/bash explicitly: the jobs work even if the scripts lost their executable bit.
at="/bin/bash '$BPF_SCHED_DIR/at-budapest.sh'"
ingest="/bin/bash '$BPF_OPS_DIR/run-ingest.sh' --scheduled"
block="$BEGIN_MARK
# Times are Europe/Budapest whatever this machine's time zone: each line fires hourly and at-budapest.sh lets
# it through only in the listed Budapest hour(s). Daily ingest 04:30 and 05:30 (the second run is a no-op
# after a good first one), availability Sundays 05:00, backup 03:15. Logs: .data/logs/. Edit the installer,
# not these lines.
30 * * * * $env_prefix $at any 4,5 $ingest daily
0 * * * * $env_prefix $at sun 5 $ingest availability
15 * * * * $env_prefix $at any 3 /bin/bash '$BPF_SCHED_DIR/backup-job.sh'
$END_MARK"
# Debian/Ubuntu cron refuses commands of about 1,000 characters ("command too long").
while IFS= read -r line; do
    if [ "${#line}" -gt 950 ]; then
        bpf_die "a crontab line would be ${#line} characters long, too long for cron (about 1,000 at most)." \
            "Use a shorter repository path, or unset the BPF_* settings the jobs do not need."
    fi
done <<EOF
$block
EOF

if [ "$print_only" -eq 1 ]; then
    printf '%s\n' "$block"
    exit 0
fi

# ── install ─────────────────────────────────────────────────────────────────────────────────────────
command -v "$CRONTAB" >/dev/null 2>&1 || bpf_die "$CRONTAB not found. Install cron (Debian/Ubuntu: apt install cron)."
work=$(mktemp -d "${TMPDIR:-/tmp}/bpf-cron.XXXXXX")
# shellcheck disable=SC2329 # invoked by the EXIT trap
cleanup() { rm -f "$work/current" "$work/err" "$work/new" "$work/check" && rmdir "$work"; }
trap cleanup EXIT

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
bpf_info "Logs: $DATA_ROOT/logs/. Show the block: crontab -l. Remove it: $BPF_SCHED_DIR/uninstall-linux.sh"
