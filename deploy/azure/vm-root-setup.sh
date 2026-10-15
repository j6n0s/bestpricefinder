#!/bin/bash
# Run on the VM as: sudo bash vm-root-setup.sh (deploy/azure/README.md). Packages, Caddy repo, swap, sshd and upgrade checks.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get -y -q upgrade
apt-get -y -q install postgresql git curl cron tzdata age unattended-upgrades \
  debian-keyring debian-archive-keyring apt-transport-https gnupg
# The app runs its own cluster on 5544; the distro service must not run.
systemctl disable --now postgresql
systemctl stop 'postgresql@*' 2>/dev/null || true
systemctl enable --now cron
# Caddy from its official apt repository (caddyserver.com/docs/install#debian-ubuntu-raspbian).
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
apt-get update -q
apt-get -y -q install caddy
# Until our Caddyfile is in place, Caddy must not serve its default page on :80.
systemctl stop caddy
# Security updates: unattended-upgrades on.
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'X'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
X
systemctl enable --now unattended-upgrades
# PostgreSQL runs as azureuser (bpf-db.service): logind's default RemoveIPC=yes would delete its shared memory
# whenever azureuser's last login session ends ("could not open shared memory segment").
install -d -m 0755 /etc/systemd/logind.conf.d
printf '[Login]\nRemoveIPC=no\n' > /etc/systemd/logind.conf.d/90-hetikosar-keep-ipc.conf
systemctl restart systemd-logind
# 2 GB swap file.
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/90-swappiness.conf && sysctl -q -p /etc/sysctl.d/90-swappiness.conf
# sshd: key only, no root login (pin the Azure defaults explicitly).
cat > /etc/ssh/sshd_config.d/90-hetikosar.conf <<'X'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
X
install -d -m 0755 /run/sshd  # Ubuntu 24.04: socket-activated sshd; sshd -t needs this directory
sshd -t && systemctl reload ssh
echo "== checks"; sshd -T | grep -E '^(passwordauthentication|kbdinteractiveauthentication|permitrootlogin|pubkeyauthentication) '
swapon --show; caddy version; /usr/lib/postgresql/*/bin/postgres --version
systemctl is-enabled postgresql || true; systemctl is-active postgresql || true
