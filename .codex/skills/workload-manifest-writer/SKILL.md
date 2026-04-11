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

When adding a StatefulSet Application, start with explicit defaults in the
manifest where that is meaningful. If Argo still reports drift on Kubernetes
defaulted fields, add a targeted `ignoreDifferences` entry for that StatefulSet
in the owning Application.

Default-prone StatefulSet paths to consider:

```yaml
ignoreDifferences:
  - group: apps
    kind: StatefulSet
    name: <statefulset-name>
    namespace: <namespace>
    jsonPointers:
      - /metadata/labels/app.kubernetes.io~1instance
      - /spec/persistentVolumeClaimRetentionPolicy
      - /spec/podManagementPolicy
      - /spec/revisionHistoryLimit
      - /spec/template/metadata/creationTimestamp
      - /spec/template/spec/containers/0/imagePullPolicy
      - /spec/template/spec/containers/0/ports/0/protocol
      - /spec/template/spec/containers/0/resources
      - /spec/template/spec/containers/0/terminationMessagePath
      - /spec/template/spec/containers/0/terminationMessagePolicy
      - /spec/template/spec/dnsPolicy
      - /spec/template/spec/restartPolicy
      - /spec/template/spec/schedulerName
      - /spec/template/spec/terminationGracePeriodSeconds
      - /spec/updateStrategy
      - /spec/volumeClaimTemplates/0/apiVersion
      - /spec/volumeClaimTemplates/0/kind
      - /spec/volumeClaimTemplates/0/metadata/creationTimestamp
      - /spec/volumeClaimTemplates/0/spec/volumeMode
      - /spec/volumeClaimTemplates/0/status
```

Add only paths that apply to the resource. Common optional additions:

- `/spec/template/spec/securityContext` when the manifest intentionally leaves it empty and Kubernetes defaults it to `{}`
- `/spec/template/spec/volumes/<index>/configMap/defaultMode` for ConfigMap volumes
- `/spec/template/spec/volumes/<index>/secret/defaultMode` for Secret volumes
- more `/spec/template/spec/containers/<index>/...` entries for multi-container StatefulSets

Use the existing repo patterns:

- `clusters/darkmoon/root/applications/core/nfs-server-provisioner.yaml`
- `clusters/darkmoon/root/applications/dev/site.yaml`
- `clusters/darkmoon/root/applications/dev/game-server.yaml`

These show targeted `ignoreDifferences` for defaulted StatefulSet fields while keeping the actual workload spec under Git control.

## Verification

Before considering the change done, render the affected target locally:

```bash
source .venv/bin/activate && source .env && python scripts/render_cluster.py
source .venv/bin/activate && source .env && python scripts/render_apps.py
```

For more detail on current sync-safe patterns, read [references/sync-safe-patterns.md](references/sync-safe-patterns.md).
