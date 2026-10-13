#!/usr/bin/env bash
# Checks a local bestpricefinder installation and says how to fix what is wrong. Run it as your normal user,
# from any directory, whenever something looks off:
#
#   deploy/local/doctor.sh
#
# Checks: PostgreSQL >= 16 server binaries, uv, Python >= 3.14 (via uv), Node.js 22 and npm; the env file
# (exists, mode 600, BPF_CONTACT_EMAIL set); the cluster (created, socket directory mode 700, running);
# migrations applied; the data (latest data date and its staleness, the last ingest runs and their status,
# reference data, content: deploy/local/ops_status.py report); the web build (present, not older than the
# sources); whether the API answers on 127.0.0.1:8000; the scheduler (installed; on macOS also the time zone).
#
# Prints one line per check: [ ok ], [WARN] or [FAIL], with a "fix:" line where there is something to do.
# Exit status: 0 when nothing FAILed (warnings allowed), 1 otherwise. Read-only, except that `uv run` may
# create or update server/.venv to match uv.lock (as every script here does). Never prints a secret.
# Environment: BPF_ENV_FILE, BPF_PGDATA, BPF_PG_BIN (see _common.sh), BPF_API_PORT (default 8000),
# BPF_CRONTAB (the crontab command; tests); BPF_ALLOW_ROOT=1 lets it run as root (CI containers only).
set -euo pipefail
umask 077

# shellcheck source-path=SCRIPTDIR source=_ops.sh
. "$(dirname "${BASH_SOURCE[0]}")/_ops.sh"

DAILY_LABEL=com.bestpricefinder.ingest-daily
CRON_MARK="# >>> bestpricefinder schedule (deploy/local/scheduler/install-linux.sh) >>>"

[ $# -eq 0 ] || {
    printf 'usage: %s\n' "$0" >&2
    exit 2
}
bpf_ops_refuse_root

problems=0
warnings=0
ok() { printf '[ ok ] %s\n' "$1"; }
warn() {
    warnings=$((warnings + 1))
    printf '[WARN] %s\n' "$1"
    if [ $# -ge 2 ]; then printf '       fix: %s\n' "$2"; fi
}
fail() {
    problems=$((problems + 1))
    printf '[FAIL] %s\n' "$1"
    if [ $# -ge 2 ]; then printf '       fix: %s\n' "$2"; fi
}
section() { printf '\n== %s ==\n' "$1"; }
private_mode() { # 0 when $1 exists and has no group/other permission bits (mode 600 / 700 or stricter)
    [ -e "$1" ] || return 1
    [ -z "$(find "$1" -maxdepth 0 \( -perm -040 -o -perm -020 -o -perm -010 -o -perm -004 -o -perm -002 \
        -o -perm -001 \) 2>/dev/null)" ]
}

if bpf_is_macos; then os="macOS $(sw_vers -productVersion 2>/dev/null || uname -r)"; else os="$(uname -s) $(uname -r)"; fi
printf 'bestpricefinder doctor: %s, %s, user %s\n' "$BPF_REPO_ROOT" "$os" "$(id -un)"

# ── prerequisites ───────────────────────────────────────────────────────────────────────────────────
section "Prerequisites"
have_pg=0
if pg_out=$(bpf_find_pg_bin 2>&1 && printf '%s\n%s\n%s' "$PG_BIN" "$PG_MAJOR" "$PG_VERSION_STRING"); then
    PG_BIN=$(printf '%s\n' "$pg_out" | sed -n 1p)
    PG_MAJOR=$(printf '%s\n' "$pg_out" | sed -n 2p)
    ok "$(printf '%s\n' "$pg_out" | sed -n 3p) server binaries in $PG_BIN"
    have_pg=1
else
    fail "${pg_out#error: }" "macOS: brew install postgresql@18; Debian/Ubuntu: apt install postgresql; or set BPF_PG_BIN"
fi

have_python=0
if UV=$(bpf_find_uv); then
    ok "$("$UV" --version 2>/dev/null | head -n 1) ($UV)"
    # The interpreter of server/'s environment, as every script runs it (uv creates or syncs it if needed).
    if py_out=$(bpf_server_run python -c \
        'import sys; print("%d.%d.%d %s" % (*sys.version_info[:3], sys.prefix))' 2>/dev/null); then
        py_line=$(printf '%s\n' "$py_out" | tail -n 1)
        py_version=${py_line%% *}
        case $py_version in
            3.1[4-9].* | 3.[2-9][0-9].*)
                ok "Python $py_version in the server environment (${py_line#* })"
                have_python=1
                ;;
            *) fail "Python ${py_version:-unknown} in the server environment; server/ needs >= 3.14" "uv python install 3.14" ;;
        esac
    else
        fail "the server environment (Python >= 3.14 and server/uv.lock) cannot be set up or run" \
            "cd server && uv sync --locked (shows the error); uv python install 3.14"
    fi
else
    fail "uv not found" "macOS: brew install uv; Linux: see https://docs.astral.sh/uv/getting-started/installation/"
fi

rc=0
node_version=$(bpf_node_version) || rc=$?
case $rc in
    0)
        case $node_version in
            v22.*) ok "Node.js $node_version" ;;
            *) warn "Node.js $node_version: web/ is built and tested with Node.js 22" "install Node.js 22 (macOS: brew install node@22)" ;;
        esac
        ;;
    1) fail "node not found (needed to build web/)" "install Node.js 22 (macOS: brew install node@22)" ;;
    2) fail "cannot read the Node.js version ($node_version)" "install Node.js 22 (macOS: brew install node@22)" ;;
    *) fail "Node.js $node_version is too old for web/ (>= $BPF_NODE_MIN)" "install Node.js 22 (macOS: brew install node@22)" ;;
esac
if command -v npm >/dev/null 2>&1; then ok "npm $(npm --version 2>/dev/null)"; else
    fail "npm not found" "it comes with Node.js 22 (macOS: brew install node@22)"
fi

# ── configuration ───────────────────────────────────────────────────────────────────────────────────
section "Configuration"
bpf_resolve_paths
have_env=0
if [ -f "$ENV_FILE" ]; then
    have_env=1
    export BPF_ENV_FILE=$ENV_FILE
    if [ ! -O "$ENV_FILE" ]; then
        fail "the env file $ENV_FILE is not owned by $(id -un)" "chown $(id -un) '$ENV_FILE'"
    elif private_mode "$ENV_FILE"; then
        ok "env file $ENV_FILE (mode 600)"
    else
        fail "the env file $ENV_FILE is readable by other users (it holds passwords)" "chmod 600 '$ENV_FILE'"
    fi
    if [ -n "${BPF_CONTACT_EMAIL:-}" ] || bpf_env_get "$ENV_FILE" BPF_CONTACT_EMAIL >/dev/null; then
        ok "BPF_CONTACT_EMAIL is set (GVH User-Agent contact)"
    else
        fail "BPF_CONTACT_EMAIL is not set: the ingest refuses to run" "add BPF_CONTACT_EMAIL=you@example.org to $ENV_FILE"
    fi
    hsts=${BPF_HSTS:-$(bpf_env_get "$ENV_FILE" BPF_HSTS || true)}
    case $hsts in
        [Tt]rue | 1 | [Yy]es | [Oo]n)
            warn "BPF_HSTS is on: browsers will refuse plain HTTP to this host name for a year" \
                "only with a real domain behind Caddy (deploy/local/caddy/README.md); otherwise remove the line"
            ;;
    esac
else
    fail "no env file at $ENV_FILE" "deploy/local/db-init.sh (creates the cluster and the env file)"
fi

# ── database ────────────────────────────────────────────────────────────────────────────────────────
section "Database"
db_up=0
if ! bpf_cluster_exists; then
    fail "no cluster at $PGDATA_DIR" "deploy/local/db-init.sh"
elif [ ! -f "$PGDATA_DIR/bpf.conf" ]; then
    fail "$PGDATA_DIR was not created by deploy/local/db-init.sh (bpf.conf is missing)"
else
    conf_out=$(bpf_load_cluster_conf 2>/dev/null && printf '%s\n%s' "$PG_PORT" "$SOCKET_DIR") || conf_out=
    if [ -z "$conf_out" ]; then
        fail "cannot read port and socket directory from $PGDATA_DIR/bpf.conf"
    else
        PG_PORT=$(printf '%s\n' "$conf_out" | sed -n 1p)
        SOCKET_DIR=$(printf '%s\n' "$conf_out" | sed -n 2p)
        data_major=$(cat "$PGDATA_DIR/PG_VERSION")
        if [ "$have_pg" -eq 1 ] && [ "$data_major" != "$PG_MAJOR" ]; then
            fail "the cluster is PostgreSQL $data_major but the binaries in $PG_BIN are $PG_MAJOR" \
                "set BPF_PG_BIN to the PostgreSQL $data_major bin directory"
        else
            ok "cluster $PGDATA_DIR (PostgreSQL $data_major, port $PG_PORT)"
        fi
        if [ ! -d "$SOCKET_DIR" ]; then
            warn "socket directory $SOCKET_DIR does not exist (it is created when the cluster starts)" \
                "deploy/local/db-start.sh"
        elif private_mode "$SOCKET_DIR"; then
            ok "socket directory $SOCKET_DIR (mode 700)"
        else
            fail "socket directory $SOCKET_DIR is accessible to other users" "chmod 700 '$SOCKET_DIR'"
        fi
        if [ "$have_pg" -eq 1 ]; then
            if bpf_db_accepting; then
                ok "PostgreSQL accepts connections (socket $SOCKET_DIR, port $PG_PORT)"
                db_up=1
            else
                fail "PostgreSQL is not running (or not accepting connections)" "deploy/local/db-start.sh"
            fi
        fi
    fi
fi

migrations_ok=0
if [ "$db_up" -eq 1 ] && [ "$have_env" -eq 1 ] && [ "$have_python" -eq 1 ]; then
    rc=0
    migrate_out=$(bpf_server_run bpf-migrate --check 2>&1) || rc=$?
    case $rc in
        0)
            ok "database migrations are all applied"
            migrations_ok=1
            ;;
        2) fail "database migrations are pending" "deploy/local/load-content.sh" ;;
        *)
            printf '%s\n' "$migrate_out" | tail -n 5 | sed 's/^/       /'
            fail "cannot check the migrations (bpf-migrate --check exit $rc)" "see the lines above; deploy/local/db-start.sh"
            ;;
    esac
fi

if [ "$migrations_ok" -eq 1 ]; then
    section "Data"
    rc=0
    report=$(bpf_server_run python "$BPF_OPS_DIR/ops_status.py" report 2>&1) || rc=$?
    # Only the report's own lines (uv may print notices first).
    printf '%s\n' "$report" | grep -E '^(\[ ok \]|\[WARN\]|\[FAIL\]|       fix: )' || true
    report_warnings=$(printf '%s\n' "$report" | grep -c '^\[WARN\]' || true)
    report_fails=$(printf '%s\n' "$report" | grep -c '^\[FAIL\]' || true)
    warnings=$((warnings + report_warnings))
    problems=$((problems + report_fails))
    if [ "$rc" -ne 0 ] && [ "$report_fails" -eq 0 ]; then
        printf '%s\n' "$report" | tail -n 5 | sed 's/^/       /'
        fail "the data checks failed to run (exit $rc)"
    fi
else
    printf '\n(data not checked: that needs the env file, uv, Python, a running database and applied migrations)\n'
fi

# ── web build and API ───────────────────────────────────────────────────────────────────────────────
section "Web and API"
if [ "$have_env" -eq 1 ]; then web_build=$(bpf_web_build_dir); else web_build=$BPF_WEB_DIR/build; fi
if [ -f "$web_build/index.html" ]; then
    newer=$(bpf_web_sources_newer "$web_build")
    if [ -n "$newer" ]; then
        warn "the web build is older than the web sources (e.g. ${newer%%$'\n'*})" \
            "deploy/local/build-web.sh, then restart deploy/local/run-api.sh"
    else
        ok "web build present ($web_build)"
    fi
else
    fail "no web build ($web_build/index.html): run-api.sh refuses to start" "deploy/local/build-web.sh"
fi
api_port=${BPF_API_PORT:-8000}
if command -v curl >/dev/null 2>&1; then
    # --noproxy: never send this to an HTTP proxy configured in the environment.
    if health=$(curl --noproxy '*' -fsS --max-time 3 "http://127.0.0.1:$api_port/api/health" 2>/dev/null); then
        case $health in
            *'"status":"ok"'*) ok "the API answers on http://127.0.0.1:$api_port: $health" ;;
            *) warn "the API answers on http://127.0.0.1:$api_port but is not ok: $health" \
                "see the Data checks above (stale or missing prices)" ;;
        esac
    else
        warn "the API is not running on http://127.0.0.1:$api_port (or its database is down)" \
            "deploy/local/run-api.sh"
    fi
fi

# ── scheduler ───────────────────────────────────────────────────────────────────────────────────────
section "Scheduler"
if bpf_is_macos; then
    if launchctl print "gui/$(id -u)/$DAILY_LABEL" >/dev/null 2>&1; then
        ok "launchd agents installed ($DAILY_LABEL ...)"
        tz_link=$(readlink /etc/localtime 2>/dev/null || true)
        case $tz_link in
            */zoneinfo/Europe/Budapest) ok "the Mac is on Europe/Budapest time (launchd uses local time)" ;;
            *) warn "the Mac's time zone is not Europe/Budapest (${tz_link:-unknown}): the jobs run at local times" \
                "System Settings > General > Date & Time: Budapest" ;;
        esac
    else
        warn "the schedule (daily ingest, weekly availability, daily backup) is not installed" \
            "deploy/local/scheduler/install-macos.sh"
    fi
else
    crontab_cmd=${BPF_CRONTAB:-crontab}
    if command -v "$crontab_cmd" >/dev/null 2>&1 && "$crontab_cmd" -l 2>/dev/null | grep -qxF "$CRON_MARK"; then
        ok "crontab block installed"
        if pgrep -x cron >/dev/null 2>&1 || pgrep -x crond >/dev/null 2>&1; then ok "a cron daemon is running"; else
            warn "no cron daemon (cron/crond) seems to be running" "sudo systemctl enable --now cron"
        fi
        if ! bpf_have_budapest_tz; then
            fail "the time zone database has no Europe/Budapest: the scheduled jobs refuse to run" "sudo apt install tzdata"
        fi
    else
        warn "the schedule (daily ingest, weekly availability, daily backup) is not installed" \
            "deploy/local/scheduler/install-linux.sh"
    fi
fi

printf '\n'
if [ "$problems" -eq 0 ]; then
    printf 'No problems found (%d warning(s)).\n' "$warnings"
    exit 0
fi
printf '%d problem(s) and %d warning(s) found; see the fix: lines above.\n' "$problems" "$warnings"
exit 1
