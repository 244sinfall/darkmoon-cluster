# Sync-Safe Patterns

## Pattern 1: Redesign stale recovered refs

Recovered manifests are inputs, not truth.

Rewrite them to current cluster concepts:

- current namespace model
- current issuer names
- current registry names
- current domains

Recent repo examples:

- `apps/site/overlays/dev/ingress.yaml`
- `apps/site/secrets/site-config.dev.enc.yaml`

## Pattern 2: Keep overlays environment-specific

Put these in overlays, not base:

- namespace
- replicas
- ingress hostname
- environment-only secret generators

Recent example:

- `apps/site/overlays/dev/kustomization.yaml`

## Pattern 3: Targeted `ignoreDifferences` for API defaults

If Argo stays `OutOfSync` only because Kubernetes defaulted fields were added at runtime, add a narrow `ignoreDifferences` rule in the owning Application.

Recent examples:

- `clusters/darkmoon/root/applications/core/nfs-server-provisioner.yaml`
- `clusters/darkmoon/root/applications/dev/site.yaml`

Use this for fields such as:

- StatefulSet `persistentVolumeClaimRetentionPolicy`
- `podManagementPolicy`
- `revisionHistoryLimit`
- defaulted pod/container fields like `imagePullPolicy`, `resources`, `dnsPolicy`
- defaulted PVC template metadata and `volumeMode`

Do not use it to hide real drift like:

- wrong hostnames
- wrong namespaces
- wrong secret names
- wrong service DNS names
- wrong issuer references
