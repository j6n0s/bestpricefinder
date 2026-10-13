#!/usr/bin/env bash
# Removes the bestpricefinder block written by install-linux.sh from the current user's crontab. The rest of
# the crontab is kept as it is. Logs, backups and the database are left alone. Idempotent.
#
#   deploy/local/scheduler/uninstall-linux.sh
#
# Environment: BPF_CRONTAB, the crontab command (default: crontab; tests point it at a stub).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=../_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"

BEGIN_MARK="# >>> bestpricefinder schedule (deploy/local/scheduler/install-linux.sh) >>>"
END_MARK="# <<< bestpricefinder schedule <<<"
CRONTAB=${BPF_CRONTAB:-crontab}

[ $# -eq 0 ] || {
    printf 'usage: %s\n' "$0" >&2
    exit 2
}
if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
    bpf_die "run this as the user who installed the schedule, not as root."
fi
command -v "$CRONTAB" >/dev/null 2>&1 || bpf_die "$CRONTAB not found"

work=$(mktemp -d "${TMPDIR:-/tmp}/bpf-cron.XXXXXX")
trap 'rm -rf "$work"' EXIT
if ! "$CRONTAB" -l >"$work/current" 2>"$work/err"; then
    if grep -qi 'no crontab' "$work/err"; then
        bpf_info "No crontab: the bestpricefinder schedule is not installed."
        exit 0
    fi
    cat "$work/err" >&2
    bpf_die "could not read the current crontab with '$CRONTAB -l'"
fi
begins=$(grep -cxF "$BEGIN_MARK" "$work/current" || true)
ends=$(grep -cxF "$END_MARK" "$work/current" || true)
if [ "$begins" -eq 0 ] && [ "$ends" -eq 0 ]; then
    bpf_info "The bestpricefinder schedule is not in the crontab; nothing to do."
    exit 0
fi
if [ "$begins" != "$ends" ]; then
    bpf_die "the crontab holds a damaged bestpricefinder block ($begins start / $ends end markers). Remove it" \
        "with 'crontab -e'."
fi
awk -v b="$BEGIN_MARK" -v e="$END_MARK" '$0 == b { skip = 1; next } $0 == e { skip = 0; next } !skip' \
    "$work/current" >"$work/new"
"$CRONTAB" "$work/new" || bpf_die "'$CRONTAB' rejected the new crontab; nothing was changed"
"$CRONTAB" -l >"$work/check" 2>/dev/null || true
if grep -qxF "$BEGIN_MARK" "$work/check"; then bpf_die "the block is still in the crontab"; fi
bpf_info "Removed the bestpricefinder schedule from the crontab (the rest is unchanged)."
