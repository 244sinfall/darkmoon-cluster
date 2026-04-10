# darkmoon-cluster

Cluster-management repository for running the `darkmoon` cluster with Argo CD.

The bootstrap model is simple:

1. Install Argo CD into the cluster.
2. Bootstrap one root application from this repo.
3. Let Argo CD manage everything after that.

## Repository layout

- `bootstrap/argocd/`: first-run manifests and bootstrap notes
- `clusters/darkmoon/root/`: cluster-specific Argo CD root app, projects, and child applications
- `clusters/darkmoon/config/`: cluster-local config such as namespaces, issuers, and secrets
- `platform/addons/`: shared platform components managed from Git
- `apps/`: workload bases and overlays
- `docs/`: operational notes for secrets and bootstrap workflow

## Recommended bootstrap flow

1. Confirm the cluster is reachable:
   - `kubectl cluster-info`
   - `kubectl get nodes`
2. Install Argo CD from the official upstream manifest, pinned to a specific version you choose.
3. Bootstrap KSOPS if you want Argo CD to render SOPS-encrypted secrets from this repo.
4. Patch `repoURL` in `bootstrap/argocd/root-application.yaml` if needed.
5. Apply the root application:
   - `kubectl apply -f bootstrap/argocd/root-application.yaml`

## Notes

- Keep Argo CD installation bootstrap small and explicit.
- Do not put secrets in this repo unencrypted.
- Keep `apps/` mostly namespace-agnostic and let cluster-level Argo CD applications decide where each overlay is deployed.
