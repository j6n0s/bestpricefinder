#!/bin/bash
# Creates vm-hetikosar: Standard_B1ms, Ubuntu 24.04 LTS, StandardSSD_LRS 32 GB, azureuser + SSH key only.
# No auto-shutdown is configured (the daily ingest runs at 04:30 Budapest time).
set -euo pipefail
export PYTHONWARNINGS=ignore
az vm create -g rg-hetikosar -n vm-hetikosar -l denmarkeast --size Standard_B1ms --image Ubuntu2404 \
  --admin-username azureuser --authentication-type ssh --ssh-key-values ~/.ssh/id_ed25519.pub \
  --nics nic-hetikosar --os-disk-name osdisk-hetikosar --os-disk-size-gb 32 --storage-sku StandardSSD_LRS \
  --tags project=hetikosar -o json --query "{state:provisioningState,ip:publicIpAddress,fqdn:fqdns,power:powerState}"
