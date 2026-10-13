#!/usr/bin/env bash
# Serves the app: python -m bpf.api (the API at /api and the SPA in web/build at /) on http://127.0.0.1:8000.
# Run it as your normal user, from any directory; Ctrl-C stops it. It builds nothing:
#
#   deploy/local/run-api.sh
#
# Before starting it refuses when the env file is missing, when the web build (web/build/index.html) is
# missing (run deploy/local/build-web.sh) or when database migrations are pending (run
# deploy/local/load-content.sh), and it warns when web/build is older than the web sources.
# It binds 127.0.0.1 only: phones reach it through Caddy over HTTPS (deploy/local/caddy/README.md).
# The server reads web/build/index.html (and the CSP in it) once at startup: restart it after build-web.sh.
#
# Environment: BPF_API_PORT (default 8000), BPF_API_LOG_LEVEL (critical|error|warning|info|debug, default
# info), BPF_ENV_FILE (default .env.local); BPF_ALLOW_ROOT=1 lets it run as root (CI containers only).
# The server reads everything else (BPF_HSTS, BPF_TRUST_PROXY_HEADERS, BPF_WEB_BUILD_DIR...) from the env
# file or the environment (.env.example).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=_ops.sh
. "$(dirname "${BASH_SOURCE[0]}")/_ops.sh"

[ $# -eq 0 ] || {
    printf 'usage: %s   (settings: BPF_API_PORT, BPF_API_LOG_LEVEL and the env file)\n' "$0" >&2
    exit 2
}

bpf_ops_refuse_root

port=${BPF_API_PORT:-8000}
case $port in '' | *[!0-9]*) bpf_die "BPF_API_PORT must be a number: $port" ;; esac
if [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then bpf_die "BPF_API_PORT must be between 1024 and 65535: $port"; fi
log_level=${BPF_API_LOG_LEVEL:-info}
case $log_level in
    critical | error | warning | info | debug) ;;
    *) bpf_die "BPF_API_LOG_LEVEL must be one of critical, error, warning, info, debug: $log_level" ;;
esac

bpf_resolve_paths
bpf_require_env_file
bpf_require_uv

# ── the web build ───────────────────────────────────────────────────────────────────────────────────
web_build=$(bpf_web_build_dir)
if [ ! -f "$web_build/index.html" ]; then
    bpf_die "no web build at $web_build (index.html is missing). Build it first: deploy/local/build-web.sh"
fi
newer=$(bpf_web_sources_newer "$web_build")
if [ -n "$newer" ]; then
    bpf_warn "web/build is older than the web sources (e.g. ${newer%%$'\n'*}); the app may be out of date." \
        "Rebuild with deploy/local/build-web.sh, then restart this script."
fi

# ── migrations ──────────────────────────────────────────────────────────────────────────────────────
rc=0
check=$(bpf_server_run bpf-migrate --check 2>&1) || rc=$?
case $rc in
    0) ;;
    2)
        printf '%s\n' "$check" >&2
        bpf_die "database migrations are pending; apply them with deploy/local/load-content.sh"
        ;;
    *)
        printf '%s\n' "$check" | tail -n 5 >&2
        bpf_die "cannot check the database migrations (exit $rc). Is PostgreSQL running? deploy/local/db-start.sh"
        ;;
esac

bpf_info "Serving http://127.0.0.1:$port (API + $web_build); Ctrl-C stops it."
cd "$BPF_SERVER_DIR"
exec "$UV" run --locked python -m bpf.api --host 127.0.0.1 --port "$port" --log-level "$log_level"
