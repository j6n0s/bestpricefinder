#!/usr/bin/env bash
# Re-apply the function-level hardening (sql/harden-functions.sql) to an existing cluster: no large objects
# for the app roles, advisory locks only where the code uses them, and a temp_file_limit for bpf_api.
# db-init.sh applies the same file to new clusters; running this again is harmless (idempotent).
#
# Usage: deploy/local/db-harden.sh        (honours BPF_PGDATA, BPF_ENV_FILE, BPF_DB_NAME like the others)
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

bpf_refuse_root
bpf_find_pg_bin
bpf_resolve_paths
bpf_require_cluster
bpf_load_cluster_conf

rc=0
bpf_cluster_status || rc=$?
[ "$rc" -eq 0 ] || bpf_die "PostgreSQL is not running (data: $PGDATA_DIR). Start it with deploy/local/db-start.sh"

admin_pw=$(bpf_env_get "$ADMIN_ENV_FILE" BPF_ADMIN_PASSWORD) ||
    bpf_die "cannot read BPF_ADMIN_PASSWORD from $ADMIN_ENV_FILE"
if [ -z "${BPF_DB_NAME:-}" ]; then
    DB_NAME=$(bpf_env_get "$ADMIN_ENV_FILE" BPF_DB_NAME || printf '%s' "$DB_NAME")
fi

PGPASSWORD=$admin_pw "$PSQL" -X -q -w -v ON_ERROR_STOP=1 -h "$SOCKET_DIR" -p "$PG_PORT" -U bpf_admin \
    -d "$DB_NAME" -v dbname="$DB_NAME" -f "$(dirname "${BASH_SOURCE[0]}")/sql/harden-functions.sql" ||
    bpf_die "hardening failed"
bpf_info "Function-level hardening applied to database $DB_NAME."
