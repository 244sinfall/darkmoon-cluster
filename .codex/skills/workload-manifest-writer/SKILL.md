---
name: workload-manifest-writer
description: Use when creating or migrating Kubernetes workload manifests in this repository. Write workloads into `apps/<app>/base` and `apps/<app>/overlays/<env>`, redesign stale recovered references to match the current cluster, and keep Argo CD synced by either making defaulted fields explicit or adding targeted `ignoreDifferences` in the owning Application.
---

# Workload Manifest Writer

Use this skill when building or migrating app manifests in this repo.

The goal is not a format-only migration from recovered YAML. The goal is a clean Argo CD workload that matches the current cluster design and stays synced.

## Placement

Write workloads into:

- `apps/<app>/base/` for reusable manifests
- `apps/<app>/overlays/<env>/` for environment-specific changes
- `clusters/darkmoon/root/applications/<env>/<app>.yaml` for the Argo CD Application

Keep bases namespace-agnostic. Put namespace, replica count, ingress hostnames, and environment-specific secret wiring in overlays.

## Migration rule

Do not blindly preserve recovered references.

When migrating old manifests, actively replace dead or obsolete references such as:

- old namespaces
- old registry hostnames
- old ClusterIssuer names
- old domain names
- old service DNS names that no longer match the namespace model

Example:

- recovered `letsencrypt-rp-wow` became `letsencrypt-prod`
- recovered `dev.rp-wow.ru` became `devv2.rp-wow.ru`
- recovered `dev-site` namespace was collapsed into `dev`

## Secrets

Use the `darkmoon-secrets` skill patterns:

- cluster secrets in `clusters/darkmoon/config/secrets/`
- app secrets in `apps/<app>/secrets/`
- reusable namespaced secrets in `apps/_shared/secrets/`

## Sync-safe writing

Prefer this order:

1. Write the manifest cleanly and explicitly where it makes sense.
2. Render locally with the `darkmoon-verification` commands.
3. If Kubernetes defaulting still causes persistent Argo `OutOfSync`, add a targeted `ignoreDifferences` rule in the owning Argo Application.

Do not:

- ignore the whole resource
- ignore broad chunks of spec unless necessary
- use `ignoreDifferences` as a substitute for fixing a real design mismatch

## Common drift pattern

StatefulSets often drift on API-defaulted fields.

Use the existing repo pattern:

- `clusters/darkmoon/root/applications/core/nfs-server-provisioner.yaml`
- `clusters/darkmoon/root/applications/dev/site.yaml`

These show targeted `ignoreDifferences` for defaulted StatefulSet fields while keeping the actual workload spec under Git control.

## Verification

Before considering the change done, render the affected target locally:

```bash
export SOPS_AGE_KEY_FILE=/home/dmitry/Dev/Personal/darkmoon-cluster/.local/sops/age-key.txt

~/.local/bin/kustomize build --enable-alpha-plugins --enable-exec apps/<app>/overlays/<env>
kubectl kustomize clusters/darkmoon/root
```

For more detail on current sync-safe patterns, read [references/sync-safe-patterns.md](references/sync-safe-patterns.md).
