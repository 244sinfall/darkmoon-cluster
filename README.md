# darkmoon-cluster

Fresh cluster-management repository for rebuilding the cluster around GitOps.

The initial goal is simple:

1. Install Argo CD into the cluster.
2. Bootstrap one root application from this repo.
3. Let Argo CD manage everything after that.

## Current state

Your local `kubectl` context is set to `kubernetes-admin@kubernetes`, but the API server hostname currently does not resolve from this machine:

- `k8s-shared-new.rp-wow.ru`

Until that DNS or kubeconfig endpoint issue is fixed, any bootstrap apply will fail.

## Repository layout

- `bootstrap/argocd/`: first-run manifests and bootstrap notes
- `clusters/prod/shared-new/root/`: cluster-specific GitOps entrypoint
- `clusters/prod/shared-new/config/`: cluster-local config such as issuers and test routing
- `apps/`: workload manifests and overlays

## Recommended bootstrap flow

1. Fix API connectivity first:
   - `kubectl cluster-info`
   - `kubectl get nodes`
2. Install Argo CD from the official upstream manifest, pinned to a specific version you choose.
3. Patch `repoURL` in `bootstrap/argocd/root-application.yaml` if needed.
4. Apply the root application:
   - `kubectl apply -f bootstrap/argocd/root-application.yaml`

## Notes

- Keep Argo CD installation bootstrap small and explicit.
- Do not put secrets in this repo unencrypted.
- Once this is working, the next good step is adding ingress, cert-manager, and sealed-secrets or SOPS.
