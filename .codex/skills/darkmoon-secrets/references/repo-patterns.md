# Repo Patterns

## Cluster secret pattern

Use when one secret is owned by cluster configuration.

Files:

- `clusters/darkmoon/config/secrets/registry-basic-auth.enc.yaml`
- `clusters/darkmoon/config/secrets/cloudflare-api-key.enc.yaml`
- `clusters/darkmoon/config/secrets/secret-generator.yaml`

Shape:

- encrypted Secret manifest stored once
- explicit namespace only if the runtime object truly belongs to one fixed namespace
- rendered by cluster config

## App secret pattern

Use when the secret belongs to one workload.

Files:

- `apps/site/secrets/site-config.dev.enc.yaml`
- `apps/site/secrets/site-mysql.dev.enc.yaml`
- `apps/site/overlays/dev/secret-generator.yaml`

Shape:

- encrypted Secret manifests stored next to the app
- overlay-local KSOPS generator references them
- overlay namespace applies at render time if the manifest omits `metadata.namespace`

## Shared namespaced secret pattern

Use when the same secret value must exist in multiple namespaces.

Files:

- `apps/_shared/secrets/registry-pull-secret.enc.yaml`
- `apps/_shared/image-pull-secret/kustomization.yaml`
- `apps/_shared/image-pull-secret/secret-generator.yaml`
- `apps/_shared/overlays/dev/kustomization.yaml`
- `clusters/darkmoon/root/applications/dev/shared-secrets.yaml`

Shape:

- one encrypted Secret manifest
- no namespace in the encrypted source
- one reusable Kustomize package exposes it
- one shared overlay per environment applies the namespace
- one Argo CD Application owns the rendered Secret for that namespace
- workload Applications only reference the Secret by name

This is the pattern to use for `regcred`.

Do not include the shared package directly from multiple workload overlays. Argo
CD will add different tracking labels for each Application and the Applications
will compete over the same live Secret.

## Shared app pattern

Shared overlay:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: dev
resources:
  - ../../image-pull-secret
```

Argo CD Application:

```yaml
metadata:
  name: shared-secrets-dev
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  source:
    path: apps/_shared/overlays/dev
  destination:
    namespace: dev
```

Workload usage:

```yaml
spec:
  imagePullSecrets:
    - name: regcred
```

## Decision rule

Use the smallest scope that still avoids duplication:

- cluster secret if the cluster owns it
- app secret if one app owns it
- shared namespaced secret if many namespaces need the same value
