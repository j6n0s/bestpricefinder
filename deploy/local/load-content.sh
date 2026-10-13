#!/usr/bin/env bash
# Brings the database schema and our own content up to date. Run it as your normal user, from any directory,
# after deploy/local/db-init.sh and after every `git pull`:
#
#   deploy/local/load-content.sh                        # migrate, validate, load
#   deploy/local/load-content.sh --allow-low-coverage   # load even if recipes fail the 90 % cost rule
#
# Steps (it stops at the first failure; nothing half-written: each step is transactional):
#   1. uv run bpf-migrate                 apply pending db/migrations as bpf_migrator
#   2. python -m bpf.content --dry-run    validate data/ (ingredients, recipes, KSH prices) without a database
#   3. python -m bpf.content              validate again against the database's GVH categories, check recipe
#                                         coverage, and load everything as bpf_ingest in one transaction
#
# Needs the env file (BPF_ENV_FILE, default .env.local) and a running cluster (deploy/local/db-start.sh).
# BPF_ALLOW_ROOT=1 lets it run as root (CI containers only).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

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

if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
    bpf_die "do not run this as root; run it as the user who owns the database (BPF_ALLOW_ROOT=1 is for CI only)."
fi

bpf_resolve_paths
[ -f "$ENV_FILE" ] || bpf_die "no env file at $ENV_FILE. Create the database first: deploy/local/db-init.sh"
export BPF_ENV_FILE=$ENV_FILE

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
UV=$(find_uv) || bpf_die "uv not found. Install it (macOS: brew install uv; see docs/RUNNING.md)."

in_server() { (cd "$BPF_REPO_ROOT/server" && "$UV" run --locked "$@"); }

bpf_info "== 1/3 Database migrations (bpf-migrate, as bpf_migrator) =="
if ! in_server bpf-migrate; then
    bpf_die "migrations failed (see above). Is PostgreSQL running? deploy/local/db-start.sh"
fi

bpf_info ""
bpf_info "== 2/3 Validating data/ (no database) =="
# "${arr[@]+"${arr[@]}"}" expands an empty array safely under set -u on bash 3.2 (macOS).
if ! in_server python -m bpf.content --dry-run ${content_args[@]+"${content_args[@]}"}; then
    bpf_die "the content in data/ is invalid; nothing was written. Fix the problems listed above (docs/DATA.md)."
fi

bpf_info ""
bpf_info "== 3/3 Loading content (as bpf_ingest, one transaction) =="
if ! in_server python -m bpf.content ${content_args[@]+"${content_args[@]}"}; then
    bpf_die "loading failed; nothing was written (see above)."
fi

bpf_info ""
bpf_info "Done: schema up to date and content loaded."
bpf_info "Next (first time): deploy/local/run-ingest.sh reference, then daily, then availability (docs/RUNNING.md)."
