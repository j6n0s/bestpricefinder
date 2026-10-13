#!/usr/bin/env bash
# Removes the launchd agents installed by install-macos.sh (stops them and deletes their plists from
# ~/Library/LaunchAgents/). Logs, backups and the database are left alone. Idempotent.
#
#   deploy/local/scheduler/uninstall-macos.sh
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=../_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/../_common.sh"

LABELS="com.bestpricefinder.ingest-daily com.bestpricefinder.ingest-availability com.bestpricefinder.backup"

[ $# -eq 0 ] || {
    printf 'usage: %s\n' "$0" >&2
    exit 2
}
if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
    bpf_die "run this as the user who installed the agents, not as root."
fi
bpf_is_macos || bpf_die "this removes launchd agents (macOS). On Linux use deploy/local/scheduler/uninstall-linux.sh."
command -v launchctl >/dev/null 2>&1 || bpf_die "launchctl not found"

agents_dir=${HOME:?HOME is not set}/Library/LaunchAgents
uid=$(id -u)
for label in $LABELS; do
    if launchctl print "gui/$uid/$label" >/dev/null 2>&1; then
        launchctl bootout "gui/$uid/$label" || bpf_die "launchctl bootout failed for $label"
        bpf_info "stopped $label"
    fi
    if [ -e "$agents_dir/$label.plist" ]; then
        rm -f "$agents_dir/$label.plist"
        bpf_info "removed $agents_dir/$label.plist"
    fi
done
bpf_info "The bestpricefinder schedule is not installed (any more)."
