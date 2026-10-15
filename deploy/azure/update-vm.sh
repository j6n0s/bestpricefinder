#!/usr/bin/env bash
# Deploys the current commit to vm-hetikosar (deploy/azure/README.md). Run on the Mac from the repository root,
# with a clean working tree:
#
#   deploy/azure/update-vm.sh
#
# 1. builds the web app locally (deploy/local/build-web.sh; the VM has no Node.js);
# 2. uploads `git archive HEAD` and web/build to ~/deploy-in on the VM;
# 3. on the VM: replaces the code in ~/bestpricefinder (keeping .data/, .env.local and server/.venv), applies
#    migrations and content (deploy/local/load-content.sh), reinstalls the cron block, restarts bpf-api and
#    checks /api/health.
#
# Environment: BPF_VM_HOST (default hetikosar-burk.denmarkeast.cloudapp.azure.com), BPF_SSH_KEY (default
# ~/.ssh/id_ed25519), BPF_NODE_BIN (default /opt/homebrew/opt/node@22/bin, Node 22 for the build).
set -euo pipefail
umask 077

host=${BPF_VM_HOST:-hetikosar-burk.denmarkeast.cloudapp.azure.com}
key=${BPF_SSH_KEY:-$HOME/.ssh/id_ed25519}
node_bin=${BPF_NODE_BIN:-/opt/homebrew/opt/node@22/bin}
ssh_opts=(-o StrictHostKeyChecking=accept-new -i "$key")

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

repo=$(git rev-parse --show-toplevel) || die "not inside the repository"
cd "$repo"
[ -z "$(git status --porcelain)" ] || die "the working tree is not clean; commit or stash first"
commit=$(git rev-parse HEAD)
short=${commit:0:7}

printf '== 1/3 Build the web app (%s)\n' "$short"
[ -x "$node_bin/node" ] || die "Node 22 not found at $node_bin (brew install node@22, or set BPF_NODE_BIN)"
PATH="$node_bin:$PATH" deploy/local/build-web.sh

printf '== 2/3 Upload %s to %s\n' "$short" "$host"
work=$(mktemp -d "${TMPDIR:-/tmp}/bpf-update.XXXXXX")
trap 'rm -rf "$work"' EXIT
git archive --format=tar.gz --prefix=bestpricefinder/ -o "$work/code-$commit.tar.gz" HEAD
tar -czf "$work/web-build-$commit.tar.gz" web/build
ssh "${ssh_opts[@]}" "azureuser@$host" 'mkdir -p -m 700 ~/deploy-in'
scp "${ssh_opts[@]}" "$work/code-$commit.tar.gz" "$work/web-build-$commit.tar.gz" "azureuser@$host:deploy-in/"

printf '== 3/3 Install on the VM\n'
# shellcheck disable=SC2087 # $commit is expanded here on purpose; everything else runs on the VM
ssh "${ssh_opts[@]}" "azureuser@$host" "bash -s -- $commit" <<'REMOTE'
set -euo pipefail
umask 022
commit=$1
export PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
stage=$(mktemp -d "$HOME/deploy-in/stage.XXXXXX")
trap 'rm -rf "$stage"' EXIT
tar -xzf "$HOME/deploy-in/code-$commit.tar.gz" -C "$stage"
tar -xzf "$HOME/deploy-in/web-build-$commit.tar.gz" -C "$stage/bestpricefinder"
rsync -a --delete \
    --exclude=/.data/ --exclude=/.env.local --exclude=/server/.venv/ --exclude=/DEPLOYED_COMMIT \
    "$stage/bestpricefinder/" "$HOME/bestpricefinder/"
echo "$commit" >"$HOME/bestpricefinder/DEPLOYED_COMMIT"
rm -f "$HOME/deploy-in/code-$commit.tar.gz" "$HOME/deploy-in/web-build-$commit.tar.gz"
cd "$HOME/bestpricefinder"
deploy/local/load-content.sh | tail -n 3
deploy/local/scheduler/install-linux.sh >/dev/null
sudo systemctl restart bpf-api
for _ in $(seq 1 30); do
    if curl -fsS -o /dev/null http://127.0.0.1:8000/api/health 2>/dev/null; then break; fi
    sleep 1
done
printf 'health: %s\n' "$(curl -s http://127.0.0.1:8000/api/health)"
printf 'deployed: %s\n' "$(cat DEPLOYED_COMMIT)"
REMOTE
