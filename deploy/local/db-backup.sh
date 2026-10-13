#!/usr/bin/env bash
# Dumps the app database with `pg_dump -Fc` as bpf_admin into <dirname PGDATA>/backups (mode 0700),
# named <db>-<UTC timestamp>.dump and created with mode 0600.
#
# Encryption: if BPF_BACKUP_AGE_RECIPIENT is set (an age public key "age1...", or the path of an age
# recipients file), the dump is piped straight into `age` and only <db>-<timestamp>.dump.age is written;
# the plaintext never touches the disk. If the recipient is set but `age` is not installed, nothing is
# dumped. Encrypt anything that leaves this machine.
#
# Restore (into an empty database owned by bpf_owner):  pg_restore -d bpf --no-owner --role=bpf_owner FILE
set -euo pipefail
umask 077

# shellcheck source=_common.sh
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

recipient=${BPF_BACKUP_AGE_RECIPIENT:-}
age_args=()
if [ -n "$recipient" ]; then
    command -v age >/dev/null 2>&1 ||
        bpf_die "BPF_BACKUP_AGE_RECIPIENT is set but 'age' is not installed; refusing to write an unencrypted dump"
    if [ -f "$recipient" ]; then age_args=(-R "$recipient"); else age_args=(-r "$recipient"); fi
fi

bpf_ensure_private_dir "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out=$BACKUP_DIR/$DB_NAME-$stamp.dump
if [ -n "$recipient" ]; then out=$out.age; fi
[ ! -e "$out" ] || bpf_die "$out already exists"

# The admin password is in the environment of pg_dump only; -w: never prompt.
if [ -n "$recipient" ]; then
    if ! PGPASSWORD=$admin_pw "$PG_DUMP" -w -Fc -h "$SOCKET_DIR" -p "$PG_PORT" -U bpf_admin -d "$DB_NAME" |
        age "${age_args[@]}" -o "$out"; then
        rm -f "$out"
        bpf_die "backup failed"
    fi
else
    if ! PGPASSWORD=$admin_pw "$PG_DUMP" -w -Fc -h "$SOCKET_DIR" -p "$PG_PORT" -U bpf_admin -d "$DB_NAME" \
        -f "$out"; then
        rm -f "$out"
        bpf_die "backup failed"
    fi
fi
chmod 600 "$out"
bpf_info "Backup written: $out"
