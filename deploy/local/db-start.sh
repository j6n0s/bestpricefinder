#!/usr/bin/env bash
# Starts the bestpricefinder cluster created by db-init.sh. Idempotent: a running cluster is left alone.
# Port and socket directory come from <PGDATA>/bpf.conf; BPF_PGDATA/BPF_PG_BIN override (see _common.sh).
set -euo pipefail
umask 077

# shellcheck source=_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

bpf_refuse_root
bpf_find_pg_bin
bpf_resolve_paths
bpf_require_cluster
bpf_load_cluster_conf
bpf_print_pg_version
bpf_start_cluster
