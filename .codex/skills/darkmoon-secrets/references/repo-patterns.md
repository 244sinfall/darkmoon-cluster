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

Shape:

- one encrypted Secret manifest
- no namespace in the encrypted source
- one reusable Kustomize package exposes it
- each consuming overlay includes that package and gets the secret in its own namespace

This is the pattern to use for `regcred`.

## Consumer pattern

App overlay:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: dev
resources:
  - ../../base
  - ../../../_shared/image-pull-secret
generators:
  - secret-generator.yaml
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
