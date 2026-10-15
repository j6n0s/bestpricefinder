#!/bin/bash
# Opens 443 (owner's user network only) and 80 (Internet, for Let's Encrypt HTTP-01 only). Run after the audits.
set -euo pipefail
export PYTHONWARNINGS=ignore
RG=rg-hetikosar
az network nsg rule create -g $RG --nsg-name nsg-hetikosar -n Allow-HTTPS-UserNet --priority 110 \
  --direction Inbound --access Allow --protocol Tcp --source-address-prefixes 146.110.0.0/16 \
  --source-port-ranges '*' --destination-address-prefixes '*' --destination-port-ranges 443 \
  --description "HTTPS from the owner's chosen user network only" -o none
az network nsg rule create -g $RG --nsg-name nsg-hetikosar -n Allow-HTTP-ACME --priority 120 \
  --direction Inbound --access Allow --protocol Tcp --source-address-prefixes Internet \
  --source-port-ranges '*' --destination-address-prefixes '*' --destination-port-ranges 80 \
  --description "Let's Encrypt HTTP-01 only; Caddy serves only the ACME challenge and a redirect on :80" -o none
az network nsg rule list -g $RG --nsg-name nsg-hetikosar -o table
