#!/usr/bin/env bash
# Builds the web app (SvelteKit PWA) into web/build, which deploy/local/run-api.sh serves. Run it as your
# normal user, from any directory, after every `git pull` that changed web/:
#
#   deploy/local/build-web.sh
#
# Steps (stops at the first failure):
#   1. npm ci          install exactly the locked dependencies (web/package-lock.json; needs the network)
#   2. npm run check   generated API types up to date, svelte-check with no errors or warnings
#   3. npm run build   production build into web/build (index.html, service-worker.js, _app/immutable/...)
#
# Then restart deploy/local/run-api.sh: the API reads index.html (and its CSP) once at startup.
# Requires Node.js >= 22.12 and npm (macOS: brew install node@22). It does not touch the database.
set -euo pipefail
umask 022 # the build is public static content

# shellcheck source-path=SCRIPTDIR source=_ops.sh
. "$(dirname "${BASH_SOURCE[0]}")/_ops.sh"

[ $# -eq 0 ] || {
    printf 'usage: %s\n' "$0" >&2
    exit 2
}

[ -f "$BPF_WEB_DIR/package-lock.json" ] || bpf_die "no $BPF_WEB_DIR/package-lock.json; is this a complete checkout?"
rc=0
node_version=$(bpf_node_version) || rc=$?
case $rc in
    0) ;;
    1) bpf_die "node not found. Install Node.js 22 (macOS: brew install node@22)." ;;
    2) bpf_die "cannot parse the Node.js version: $node_version" ;;
    *) bpf_die "Node.js $node_version is too old; web/ needs >= $BPF_NODE_MIN (macOS: brew install node@22)." ;;
esac
command -v npm >/dev/null 2>&1 || bpf_die "npm not found. It comes with Node.js 22 (macOS: brew install node@22)."
bpf_info "Using Node.js $node_version, npm $(npm --version), in $BPF_WEB_DIR"

cd "$BPF_WEB_DIR"
bpf_info ""
bpf_info "== 1/3 npm ci =="
npm ci
bpf_info ""
bpf_info "== 2/3 npm run check =="
npm run check
bpf_info ""
bpf_info "== 3/3 npm run build =="
npm run build

[ -f "$BPF_WEB_DIR/build/index.html" ] || bpf_die "the build finished but $BPF_WEB_DIR/build/index.html is missing"
bpf_info ""
bpf_info "Built $BPF_WEB_DIR/build. Restart deploy/local/run-api.sh to serve it (it reads index.html at startup)."
