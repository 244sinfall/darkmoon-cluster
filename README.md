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

## Local Verification

Install standalone `kustomize` and `ksops` locally. The repo uses `ksops` exec
plugins, so `kubectl kustomize` is not enough for secret-backed overlays.

```bash
mkdir -p ~/.local/bin /tmp/codex-install
cd /tmp/codex-install

curl -fL -o kustomize_v5.8.1_linux_amd64.tar.gz \
  https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/v5.8.1/kustomize_v5.8.1_linux_amd64.tar.gz
curl -fL -o kustomize-checksums.txt \
  https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/v5.8.1/checksums.txt
sha256sum -c <(grep 'kustomize_v5.8.1_linux_amd64.tar.gz' kustomize-checksums.txt)
tar -xzf kustomize_v5.8.1_linux_amd64.tar.gz
install -m 0755 kustomize ~/.local/bin/kustomize

curl -fL -o ksops_4.4.0_Linux_x86_64.tar.gz \
  https://github.com/viaduct-ai/kustomize-sops/releases/download/v4.4.0/ksops_4.4.0_Linux_x86_64.tar.gz
curl -fL -o ksops-checksums.txt \
  https://github.com/viaduct-ai/kustomize-sops/releases/download/v4.4.0/checksums.txt
sha256sum -c <(grep 'ksops_4.4.0_Linux_x86_64.tar.gz' ksops-checksums.txt)
tar -xzf ksops_4.4.0_Linux_x86_64.tar.gz
install -m 0755 ksops ~/.local/bin/ksops
```

Create `.env` from the repo example and set local paths there:

```bash
cp .env.example .env
```

Any change to app manifests, cluster config, Argo applications, or KSOPS-backed
secrets should be rendered locally before it is considered done.

```bash
source .venv/bin/activate && source .env && python scripts/render_cluster.py
source .venv/bin/activate && source .env && python scripts/flatten_secrets.py
source .venv/bin/activate && source .env && python scripts/render_apps.py
```
