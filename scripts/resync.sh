kubectl -n argocd patch application cluster-root \
  --type merge \
  -p '{"operation":{"sync":{"prune":true}}}'
