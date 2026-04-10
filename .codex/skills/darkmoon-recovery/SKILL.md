---
name: darkmoon-recovery
description: Use when recovering workloads from `local-charts` into this repository's Argo CD layout. Classify recovered manifests into cluster-scoped platform components, environment-scoped applications, reusable Helm bases, and quarantine-only legacy inputs, then migrate them into `platform/`, `clusters/`, and `apps/` with `dev` as the first target environment.
---

# Darkmoon Recovery

Recover the old manually managed Helm/manifests into the repo's GitOps shape.

The final target is not a cleaner `local-charts` tree. The final target is:

- `platform/` for cluster-scoped shared components
- `clusters/darkmoon/` for cluster config and Argo CD application wiring
- `apps/` for environment-deployable workloads

Use `local-charts/` only as a recovery staging area while the migration is in progress.

## Current repo facts

- The repo already has Argo CD bootstrap and root applications.
- `clusters/darkmoon/root/` is the app-of-apps entrypoint.
- `platform/addons/` already holds cluster-scoped addons.
- `clusters/darkmoon/config/` already holds namespaces, issuers, and secrets.
- `apps/` already holds Argo-managed workloads using Kustomize overlays.

## Recovered input patterns

- Real Helm charts exist for `game-server`, `python_service`, `rust_service`, `dotnet_service`, and `dotnet_pgsql_service`.
- `local-charts/web/base-driven/` is mostly values-like or manifest-like workload input, not a coherent chart set.
- `site-template.yaml` is a monolithic recovered app bundle and should be decomposed, not copied as-is.
- `vpn-default`, `vpn-internal`, and `vpn-external` are cluster-scoped candidates because they differ mainly by networking and namespace-wide policy shape.
- `codex-context/dev-server/` contains workload-specific runtime context and values, not reusable chart primitives.
- `trinity-build-core` and `trinity-runtime` are image/build assets, not Kubernetes deployment definitions.
- Many recovered files contain inline secrets, hardcoded namespaces, and explicit environment names. Treat them as migration input only.

## Recovery classification rules

### 1. Cluster-scoped platform

Place here if the resource is one of:

- shared ingress or cert infrastructure
- VPN/WireGuard instances serving the cluster as shared infra
- shared network policy bundles
- shared storage or operators
- shared registry/auth plumbing

Target repo homes:

- `platform/addons/<name>/`
- `clusters/darkmoon/config/` when it is cluster-local config rather than a reusable addon
- `clusters/darkmoon/root/applications/core/<name>.yaml` for the Argo CD Application

### 2. Environment-scoped app

Place here if the resource is a deployable business workload:

- game server
- web site
- backend APIs
- workers and cronjobs
- internal app databases owned by one app stack

Target repo homes:

- `apps/<app>/base/`
- `apps/<app>/overlays/dev/`
- `clusters/darkmoon/root/applications/dev/<app>.yaml` or another environment-specific application set

### 3. Reusable chart/base primitive

Place here if the recovered content is a real reusable deployment pattern:

- generic Python service
- generic Rust service
- generic .NET service
- generic .NET plus PostgreSQL bundle
- game server base if it remains reusable after cleanup

These should become either:

- a cleaned local Helm chart under a clearly named recovery/base folder during migration, or
- a Kustomize base if the chart abstraction is not pulling its weight

### 4. Quarantine

Place here temporarily if the input is:

- prod-only and out of scope for `dev`
- secret-laden and not yet externalized
- duplicated or contradictory
- unclear whether it is still used
- obviously malformed or stale

Do not promote quarantined files into Argo applications until they are normalized.

## Target staging structure for `local-charts/`

During recovery, use this structure so input material is organized by migration role:

```text
local-charts/
  recovery/
    bases/
      python-service/
      rust-service/
      dotnet-service/
      dotnet-pgsql-service/
      game-server/
    envs/
      dev/
        dev-server/
        web/
        backend/
    cluster/
      vpn/
        default/
        internal/
        external/
    context/
      dev-server/
    build-assets/
      trinity-build-core/
      trinity-runtime/
    quarantine/
      prod/
      unknown/
      secret-heavy/
```

This is a migration taxonomy, not a final deployment taxonomy.

## Working strategy

1. Preserve recovered input, but reorganize it into the staging taxonomy above.
2. Strip inline secrets and move them to SOPS-managed secrets or external secret generation.
3. Normalize hardcoded namespaces so Argo destination plus overlay values define placement.
4. Extract monolithic YAML bundles into app-shaped bases.
5. Migrate one vertical slice at a time, starting with `dev`.
6. Keep cluster-scoped VPN/network components separate from app workloads from the start.
7. Prefer small Argo applications with clear ownership over one giant recovered mega-app.

## First implementation slice

Start with:

- `dev-server` game stack
- `site-template.yaml` decomposition for the `dev` web site
- shared VPN variants as cluster-scoped platform apps

Delay:

- prod recovery
- data migration
- uncertain services
- anything that cannot be secret-cleaned quickly

## Plan

Follow the phased plan in [PLAN.md](PLAN.md).
