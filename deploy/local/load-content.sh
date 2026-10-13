#!/usr/bin/env bash
# Brings the database schema and our own content up to date. Run it as your normal user, from any directory,
# after deploy/local/db-init.sh and after every `git pull`:
#
#   deploy/local/load-content.sh                        # migrate, then validate and load data/
#   deploy/local/load-content.sh --allow-low-coverage   # load even if recipes fail the 90 % cost rule
#
# Steps (it stops at the first failure):
#   1. uv run bpf-migrate     apply pending db/migrations as bpf_migrator (one transaction per migration)
#   2. python -m bpf.content  validate data/ (ingredients, recipes, KSH prices; the ingredients' GVH leaves
#                             against the database's categories once a reference ingest has run), check the
#                             recipes' cost coverage (with the latest GVH prices once a daily ingest has run),
#                             then load everything as bpf_ingest in ONE transaction. Invalid content writes
#                             nothing, and the content loaded before stays as it was.
#
# Needs the env file (BPF_ENV_FILE, default .env.local) and a running cluster (deploy/local/db-start.sh).
# BPF_ALLOW_ROOT=1 lets it run as root (CI containers only).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=_ops.sh
. "$(dirname "${BASH_SOURCE[0]}")/_ops.sh"

content_args=()
for arg in "$@"; do
    case $arg in
        --allow-low-coverage) content_args=(--allow-low-coverage) ;;
        *)
            printf 'usage: %s [--allow-low-coverage]\n' "$0" >&2
            exit 2
            ;;
    esac
done

bpf_ops_refuse_root
bpf_resolve_paths
bpf_require_env_file
bpf_require_uv

bpf_info "== 1/2 Database migrations (bpf-migrate, as bpf_migrator) =="
if ! bpf_server_run bpf-migrate; then
    bpf_die "migrations failed (see above); nothing further was done. Is PostgreSQL running? deploy/local/db-start.sh"
fi

bpf_info ""
bpf_info "== 2/2 Content: validate data/, check recipe coverage, load (as bpf_ingest, one transaction) =="
# "${arr[@]+"${arr[@]}"}" expands an empty array safely under set -u on bash 3.2 (macOS).
if ! bpf_server_run python -m bpf.content ${content_args[@]+"${content_args[@]}"}; then
    bpf_die "the content was not loaded; nothing was written (see the problems above, and docs/DATA.md)."
fi

bpf_info ""
bpf_info "Done: schema up to date and content loaded."
bpf_info "First time? Next: set BPF_CONTACT_EMAIL, then deploy/local/run-ingest.sh reference, daily and" \
    "availability (docs/RUNNING.md, steps 5 and 6)."
