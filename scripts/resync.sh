#!/usr/bin/env bash
set -euo pipefail

app="${1:-cluster-root}"

kubectl -n argocd patch application "$app" \
  --type merge \
  -p '{"operation":{"sync":{"prune":true}}}'
