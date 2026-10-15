#!/bin/bash
# Creates the network for vm-hetikosar in rg-hetikosar (denmarkeast). The NSG gets ONLY the SSH rule here;
# 443 and 80 are added by 05-open-firewall.sh after the audits pass (DEPLOY_HANDOFF: audit before opening).
set -euo pipefail
export PYTHONWARNINGS=ignore
RG=rg-hetikosar; LOC=denmarkeast; T="project=hetikosar"
# SSH sources (CIDRs, space-separated): the admin's addresses. Required; never commit them.
: "${BPF_ADMIN_CIDRS:?set BPF_ADMIN_CIDRS, e.g. '146.110.152.0/24 203.0.113.7/32'}"
LABEL=hetikosar-burk
az network nsg create -g $RG -n nsg-hetikosar -l $LOC --tags $T -o none
az network nsg rule create -g $RG --nsg-name nsg-hetikosar -n Allow-SSH-Admin --priority 100 \
  --direction Inbound --access Allow --protocol Tcp --source-address-prefixes $BPF_ADMIN_CIDRS \
  --source-port-ranges '*' --destination-address-prefixes '*' --destination-port-ranges 22 \
  --description "SSH from the owner's university NAT pool and home IP (key auth only)" -o none
az network vnet create -g $RG -n vnet-hetikosar -l $LOC --address-prefixes 10.42.0.0/24 \
  --subnet-name snet-app --subnet-prefixes 10.42.0.0/27 --tags $T -o none
az network public-ip create -g $RG -n pip-hetikosar -l $LOC --sku Standard --allocation-method Static \
  --version IPv4 --dns-name "$LABEL" --tags $T -o none
az network nic create -g $RG -n nic-hetikosar -l $LOC --vnet-name vnet-hetikosar --subnet snet-app \
  --public-ip-address pip-hetikosar --network-security-group nsg-hetikosar --tags $T -o none
az network public-ip show -g $RG -n pip-hetikosar --query "[ipAddress,dnsSettings.fqdn]" -o tsv
