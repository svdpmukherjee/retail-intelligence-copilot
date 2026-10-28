#!/usr/bin/env bash
# DESTRUCTIVE: deletes an entire Azure resource group and everything in it.
# Not run in M1 (nothing is provisioned). Usage: ./teardown.sh <resource-group>
set -euo pipefail

rg="${1:?usage: teardown.sh <resource-group>}"

read -r -p "Delete resource group '$rg' and ALL its resources? Type the name to confirm: " answer
if [[ "$answer" != "$rg" ]]; then
  echo "Confirmation did not match; aborting." >&2
  exit 1
fi

az group delete --name "$rg" --yes --no-wait
echo "Deletion of '$rg' requested."
