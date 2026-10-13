#!/usr/bin/env bash
# The scheduled daily backup: deploy/local/db-backup.sh (pg_dump -Fc; only an age-encrypted file when
# BPF_BACKUP_AGE_RECIPIENT is set), then pruning of old dumps and job logs. launchd/cron run it (see
# scheduler/install-*.sh); you can also run it by hand.
#
#   deploy/local/scheduler/backup-job.sh
#
# Output goes to <data>/logs/backup-YYYY-MM-DD.log (mode 600); the job prints one line only when it fails
# (launchd's log file, cron's mail). It starts the local cluster first if it is not running.
#
# Pruning: dumps named <db>-<UTC timestamp>.dump[.age] in the backup directory that are older than
# BPF_BACKUP_KEEP_DAYS days (default 30; 0 = never delete) are deleted, but the newest 7 are always kept.
# Job logs older than BPF_LOG_KEEP_DAYS (default 30) are deleted. Nothing else is touched.
# Environment: as db-backup.sh (BPF_PGDATA, BPF_PG_BIN, BPF_BACKUP_DIR, BPF_BACKUP_AGE_RECIPIENT...).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=../_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"

SCRIPT_DIR=$BPF_REPO_ROOT/deploy/local
MIN_KEEP=7

[ $# -eq 0 ] || {
    printf 'usage: %s\n' "$0" >&2
    exit 2
}
bpf_refuse_root # db-backup.sh refuses root as well

keep_days=${BPF_BACKUP_KEEP_DAYS:-30}
case $keep_days in '' | *[!0-9]*) bpf_die "BPF_BACKUP_KEEP_DAYS must be a whole number of days: $keep_days" ;; esac
log_keep_days=${BPF_LOG_KEEP_DAYS:-30}
case $log_keep_days in '' | *[!0-9]*) bpf_die "BPF_LOG_KEEP_DAYS must be a whole number of days: $log_keep_days" ;; esac
[ "$log_keep_days" -ge 1 ] || bpf_die "BPF_LOG_KEEP_DAYS must be at least 1"

bpf_resolve_paths
bpf_ensure_dir "$DATA_ROOT"
JOB_LOG_DIR=$DATA_ROOT/logs
bpf_ensure_private_dir "$JOB_LOG_DIR"
JOB_LOG=$JOB_LOG_DIR/backup-$(date +%Y-%m-%d).log
touch "$JOB_LOG"
chmod 600 "$JOB_LOG"
exec 3>&1 >>"$JOB_LOG" 2>&1

say() { printf '%s backup-job[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$$" "$*"; }
fail() {
    say "error: $*"
    printf 'bestpricefinder backup: failed: %s (log: %s)\n' "$*" "$JOB_LOG" >&3
    exit 1
}

say "=== backup starting ==="
find "$JOB_LOG_DIR" -maxdepth 1 -type f \( -name 'ingest-*.log' -o -name 'backup-*.log' \) \
    -mtime +"$((log_keep_days - 1))" -exec rm -f {} + 2>/dev/null || true

bpf_cluster_exists || fail "no cluster at $PGDATA_DIR (deploy/local/db-init.sh)"
accepting=0
if (
    bpf_find_pg_bin >/dev/null
    bpf_load_cluster_conf
    isready=$PG_BIN/pg_isready
    [ -x "$isready" ] || isready=$(command -v pg_isready)
    "$isready" -q -h "$SOCKET_DIR" -p "$PG_PORT" -t 5
) 2>/dev/null; then accepting=1; fi
if [ "$accepting" -eq 0 ]; then
    say "PostgreSQL is not running; starting it with deploy/local/db-start.sh"
    # 3>&-: the postmaster must not inherit cron's mail pipe or launchd's log descriptor.
    "$SCRIPT_DIR/db-start.sh" 3>&- || fail "PostgreSQL could not be started (see the log)"
fi

"$SCRIPT_DIR/db-backup.sh" 3>&- || fail "db-backup.sh failed (see the log)"

# ── pruning ─────────────────────────────────────────────────────────────────────────────────────────
if [ "$keep_days" -eq 0 ]; then
    say "pruning disabled (BPF_BACKUP_KEEP_DAYS=0)"
elif [ -d "$BACKUP_DIR" ]; then
    kept=0
    deleted=0
    # Only names db-backup.sh writes (<db>-YYYYMMDDTHHMMSSZ.dump[.age]; no spaces), newest first by the
    # timestamp in the name.
    names=$(for path in "$BACKUP_DIR"/*.dump "$BACKUP_DIR"/*.dump.age; do
        [ -f "$path" ] || continue # an unmatched glob stays literal
        name=${path##*/}
        printf '%s\n' "$name" | grep -qE '^[a-z_][a-z0-9_]*-[0-9]{8}T[0-9]{6}Z\.dump(\.age)?$' || continue
        stamp=${name##*-}
        printf '%s %s\n' "${stamp%%Z*}" "$name"
    done | sort -r | cut -d' ' -f2)
    for name in $names; do
        kept=$((kept + 1))
        [ "$kept" -gt "$MIN_KEEP" ] || continue
        if [ -n "$(find "$BACKUP_DIR/$name" -maxdepth 0 -type f -mtime +"$((keep_days - 1))" 2>/dev/null)" ]; then
            rm -f "$BACKUP_DIR/$name"
            deleted=$((deleted + 1))
            say "deleted old backup $name"
        fi
    done
    say "pruning: $deleted old backup(s) deleted (older than $keep_days days; the newest $MIN_KEEP are always kept)"
fi
say "=== backup done ==="
