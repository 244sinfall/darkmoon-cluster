# KSOPS bootstrap

Argo CD does not decrypt `SOPS` files by itself. This bootstrap adds `KSOPS`
to `argocd-repo-server` and mounts the `age` private key so Argo can build
encrypted Kustomize trees.

## 1. Create the in-cluster `age` key secret

Use the local private key generated for this repo:

```bash
kubectl -n argocd create secret generic sops-age \
  --from-file=keys.txt=.local/sops/age-key.txt \
  --dry-run=client -o yaml | kubectl apply -f -
```

## 2. Enable Kustomize exec plugins

```bash
kubectl -n argocd patch configmap argocd-cm \
  --type merge \
  --patch-file bootstrap/argocd/ksops/argocd-cm-patch.yaml
```

## 3. Patch the repo-server

```bash
kubectl -n argocd patch deployment argocd-repo-server \
  --type strategic \
  --patch-file bootstrap/argocd/ksops/argocd-repo-server-patch.yaml
kubectl -n argocd rollout status deployment/argocd-repo-server
```

## 4. Verify repo-server environment

```bash
kubectl -n argocd exec deploy/argocd-repo-server -- sh -c \
  'command -v ksops && command -v kustomize && test -f /.config/sops/age/keys.txt'
```

After this, Argo CD can render `KSOPS` generators that reference encrypted
`*.enc.yaml` files in the repo.
