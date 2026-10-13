#!/usr/bin/env bash
# Stops the bestpricefinder cluster (fast shutdown: open transactions are rolled back). Idempotent: a
# stopped or never-created cluster is not an error. BPF_PGDATA/BPF_PG_BIN override (see _common.sh).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

bpf_refuse_root
bpf_find_pg_bin
bpf_resolve_paths
if ! bpf_cluster_exists; then
    bpf_info "No cluster at $PGDATA_DIR; nothing to stop."
    exit 0
fi
bpf_stop_cluster
