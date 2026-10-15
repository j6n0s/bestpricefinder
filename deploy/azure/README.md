# Azure VM: vm-hetikosar

The app runs on one Azure VM, deployed on 2026-10-15 by the local Claude Code session from
[docs/DEPLOY_HANDOFF.md](../../docs/DEPLOY_HANDOFF.md). This folder holds what runs there, so it can be
rebuilt or updated. Day-to-day operation uses the same scripts as a local install ([deploy/local/](../local/README.md)).

## What exists

| Item | Value |
|---|---|
| Subscription / region | "Azure for Students", `denmarkeast` (B1ms is not offered to this subscription in `austriaeast`) |
| Resource group | `rg-hetikosar`: VM, NIC, NSG, VNet `10.42.0.0/24`, static public IP, 32 GB StandardSSD disk (all tagged `project=hetikosar`) |
| VM | `vm-hetikosar`, Standard_B1ms (1 vCPU, 2 GB) + 2 GB swap, Ubuntu 24.04 LTS, user `azureuser`, SSH key only |
| Address | `https://hetikosar-burk.denmarkeast.cloudapp.azure.com`, static IP `9.205.31.89` |
| NSG inbound | 22 from `146.110.152.0/24` (the university NAT pool) and the owner's home IP (not in git: `BPF_ADMIN_CIDRS`); 443 from `146.110.0.0/16`; 80 from the Internet (Let's Encrypt HTTP-01 and the redirect only) |
| Access | Private (BUILD-BRIEF §8): only `146.110.0.0/16`, enforced by the NSG and again by Caddy (`remote_ip`). No login. |
| Code | `/home/azureuser/bestpricefinder`; the deployed commit is in `DEPLOYED_COMMIT`. The VM has no git checkout and no GitHub credentials. |
| Services | `bpf-db.service` (the cluster, `deploy/local/db-start.sh`), `bpf-api.service` (`run-api.sh`, 127.0.0.1:8000), Caddy (the package's unit, `/etc/caddy/Caddyfile` = [Caddyfile](Caddyfile)), cron (the block from `scheduler/install-linux.sh`), unattended-upgrades |
| Python | uv 0.13.1 in `~/.local/bin`; Python 3.14 (`server/.python-version`) |
| Backups | `.data/backups/` on the VM only, not encrypted (public prices and our own content; no personal data). Encrypting them and copying them off the VM is open (RUNNING.md §11). |

## Update the VM to the current commit

From the Mac, in the repository root, with a clean working tree:

```bash
deploy/azure/update-vm.sh
```

It builds the web app locally (Node 22), uploads the code and the build, keeps `.data/`, `.env.local` and the
virtual environment, applies migrations and content, reinstalls the cron block, restarts `bpf-api` and checks
`/api/health`. SSH must come from an address the NSG admits.

## Operate

```bash
ssh -i ~/.ssh/id_ed25519 azureuser@hetikosar-burk.denmarkeast.cloudapp.azure.com
cd ~/bestpricefinder && deploy/local/doctor.sh   # "node/npm not found" is expected: the build happens on the Mac
systemctl status bpf-db bpf-api caddy
tail -n 50 .data/logs/ingest-$(TZ=Europe/Budapest date +%F).log
```

Pause, resume or remove (from the Mac):

```bash
az vm deallocate -g rg-hetikosar -n vm-hetikosar   # stops compute billing; disk and IP still cost a little
az vm start -g rg-hetikosar -n vm-hetikosar
az group delete -n rg-hetikosar                    # deletes everything, permanently
```

## Rebuild from scratch

1. `BPF_ADMIN_CIDRS="<admin CIDRs>" az-01-network.sh`, then `az-02-vm.sh` (Azure CLI, logged in to the subscription).
2. Copy `vm-root-setup.sh`, the two units and the Caddyfile to the VM; `sudo bash vm-root-setup.sh`; reboot.
3. Install uv 0.13.1 (the release tarball, checksum-verified) into `~/.local/bin`; unpack the code and a web build
   into `~/bestpricefinder` (or run `update-vm.sh` once the directory exists).
4. Follow DEPLOY_HANDOFF.md §5 steps 3–6: `db-init.sh`; add `BPF_CONTACT_EMAIL`, `BPF_TRUST_PROXY_HEADERS=true`
   and `BPF_HSTS=true` to `.env.local`; `load-content.sh`; `run-ingest.sh reference`, `daily`, `load-content.sh`
   again, `availability` (about 50 minutes); `scheduler/install-linux.sh`.
5. `db-stop.sh`, then install the units and `sudo systemctl enable --now bpf-db bpf-api`.
6. Audits (`pip-audit` on `server/.venv`, `npm audit --omit=dev` on the Mac), then `az-03-open-firewall.sh`,
   install the Caddyfile and `sudo systemctl enable --now caddy` (it obtains the certificate).

Ubuntu 24.04 note: sshd is socket-activated, so `/run/sshd` exists only while it runs; `vm-root-setup.sh`
creates it before `sshd -t`.

PostgreSQL runs as `azureuser`, so logind must keep that user's shared memory after logout: `RemoveIPC=no` in
`/etc/systemd/logind.conf.d/90-hetikosar-keep-ipc.conf` (set by `vm-root-setup.sh`). Without it the database breaks
when the last SSH session closes.
