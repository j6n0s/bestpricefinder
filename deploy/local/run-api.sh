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
#
# Environment: BPF_API_PORT (default 8000), BPF_API_LOG_LEVEL (critical|error|warning|info|debug, default
# info), BPF_ENV_FILE (default .env.local); BPF_ALLOW_ROOT=1 lets it run as root (CI containers only).
# Everything else (BPF_HSTS, BPF_TRUST_PROXY_HEADERS, BPF_WEB_BUILD_DIR...) is read by the server from the
# env file or the environment (.env.example).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

[ $# -eq 0 ] || {
    printf 'usage: %s   (settings via BPF_API_PORT, BPF_API_LOG_LEVEL and the env file)\n' "$0" >&2
    exit 2
}

if [ "$(id -u)" -eq 0 ] && [ "${BPF_ALLOW_ROOT:-}" != "1" ]; then
    bpf_die "do not run this as root; run it as the user who owns the database (BPF_ALLOW_ROOT=1 is for CI only)."
fi

port=${BPF_API_PORT:-8000}
case $port in '' | *[!0-9]*) bpf_die "BPF_API_PORT must be a number: $port" ;; esac
if [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then bpf_die "BPF_API_PORT must be between 1024 and 65535: $port"; fi
log_level=${BPF_API_LOG_LEVEL:-info}
case $log_level in
    critical | error | warning | info | debug) ;;
    *) bpf_die "BPF_API_LOG_LEVEL must be one of critical, error, warning, info, debug: $log_level" ;;
esac

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
SERVER_DIR=$BPF_REPO_ROOT/server

# ── the web build ───────────────────────────────────────────────────────────────────────────────────
# Same precedence as bpf.config: the environment, then the env file, then <repo>/web/build. A relative
# path is relative to server/, where the API runs.
web_build=${BPF_WEB_BUILD_DIR:-}
if [ -z "$web_build" ]; then web_build=$(bpf_env_get "$ENV_FILE" BPF_WEB_BUILD_DIR || true); fi
case $web_build in \"*\") web_build=${web_build#\"} && web_build=${web_build%\"} ;; esac
if [ -z "$web_build" ]; then web_build=$BPF_REPO_ROOT/web/build; fi
case $web_build in /*) ;; *) web_build=$SERVER_DIR/$web_build ;; esac
if [ ! -f "$web_build/index.html" ]; then
    bpf_die "no web build at $web_build (index.html is missing). Build it first: deploy/local/build-web.sh"
fi
if [ "$web_build" = "$BPF_REPO_ROOT/web/build" ]; then
    web=$BPF_REPO_ROOT/web
    newer=$(find "$web/src" "$web/static" "$web/package.json" "$web/package-lock.json" "$web/svelte.config.js" \
        "$web/vite.config.ts" "$web/tsconfig.json" -type f -newer "$web_build/index.html" 2>/dev/null |
        head -n 3 || true)
    if [ -n "$newer" ]; then
        bpf_warn "web/build is older than the web sources (e.g. ${newer%%$'\n'*}); the app may be out of date." \
            "Rebuild with deploy/local/build-web.sh, then restart this script."
    fi
fi

# ── migrations ──────────────────────────────────────────────────────────────────────────────────────
rc=0
check=$(cd "$SERVER_DIR" && "$UV" run --locked bpf-migrate --check 2>&1) || rc=$?
case $rc in
    0) ;;
    2)
        printf '%s\n' "$check" >&2
        bpf_die "database migrations are pending; apply them with deploy/local/load-content.sh"
        ;;
    *)
        printf '%s\n' "$check" >&2
        bpf_die "cannot check the database migrations (exit $rc). Is PostgreSQL running? deploy/local/db-start.sh"
        ;;
esac

bpf_info "Serving http://127.0.0.1:$port (API + $web_build); Ctrl-C stops it."
cd "$SERVER_DIR"
exec "$UV" run --locked python -m bpf.api --host 127.0.0.1 --port "$port" --log-level "$log_level"
