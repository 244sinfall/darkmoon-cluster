# Darkmoon Recovery Plan

This plan assumes the end state is full Argo CD ownership and that `dev` is the only recovery target for now.

## Objectives

- Reclassify recovered material from `local-charts/` into reusable bases, environment inputs, cluster-scoped components, and quarantine.
- Migrate recovered workloads into the repo's existing GitOps layout.
- Recover `dev` first with no data migration requirement.
- Leave a repeatable pattern so `stage` or `prod` can be cloned later with controlled differences.

## Proposed repo end state

The steady-state shape should look like:

```text
platform/
  addons/
    ingress-nginx/
    vpn-default/
    vpn-internal/
    vpn-external/

clusters/
  darkmoon/
    config/
      namespaces/
      issuers/
      secrets/
    root/
      applications/
        core/
        dev/

apps/
  dev-server/
    base/
    overlays/
      dev/
  site/
    base/
    overlays/
      dev/
  auth-service/
    base/
    overlays/
      dev/
  vpn-service/
    base/
    overlays/
      dev/
  ...
```

`local-charts/` remains only a migration workbench until the inputs have been promoted.

## Proposed `local-charts/` recovery structure

Before promoting anything, reorganize the recovered mess into:

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
        site/
        backend/
        integrations/
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
      duplicate/
      secret-heavy/
```

## Why this structure

- `bases/` isolates actual reusable deployment primitives from one-off recovered values.
- `envs/dev/` captures the first recovery target without pretending the inputs are reusable.
- `cluster/` keeps VPN and network-policy-heavy components out of app namespaces.
- `context/` keeps server configs and helper scripts close to the app they inform without mixing them into chart primitives.
- `build-assets/` separates Docker build context from deployment manifests.
- `quarantine/` prevents low-confidence files from contaminating the migration path.

## Workstream breakdown

## 1. Inventory and classify

Actions:

- List every recovered workload and mark it `cluster`, `env-app`, `base`, or `quarantine`.
- Identify duplicates, malformed files, and suspicious leftovers like typoed filenames.
- Identify all inline secrets and hardcoded namespaces.

Expected findings from current input:

- `game-server` is a real app chart.
- `codex-context/dev-server/` belongs to `dev-server` env context.
- `web/base/*_service` are base primitives.
- `web/base-driven/*` are mostly per-app env input files and should not be treated as a clean shared base.
- `web/vpn-*` are cluster-scoped platform candidates.
- `site-template.yaml` is a recovered monolith for the `site` app and must be decomposed.

## 2. Normalize secrets and config boundaries

Actions:

- Remove inline credentials from recovered values and manifests.
- Move secrets into SOPS-encrypted manifests under `clusters/darkmoon/config/secrets/` or app-specific secret manifests rendered by Argo.
- Move non-secret config into ConfigMaps or app values files.

Rules:

- No plain secrets in promoted `apps/`, `platform/`, or committed values.
- `local-charts/` may temporarily contain sensitive recovery input, but promoted targets may not.

## 3. Promote cluster-scoped infrastructure first

Candidates:

- `vpn-default`
- `vpn-internal`
- `vpn-external`

Target:

- One addon directory per variant under `platform/addons/`
- One Argo Application per addon under `clusters/darkmoon/root/applications/core/`

Why first:

- It establishes the cluster-wide network primitives early.
- It keeps app migrations from embedding infra concerns.

## 4. Recover reusable workload bases

Candidates:

- `python_service`
- `rust_service`
- `dotnet_service`
- `dotnet_pgsql_service`
- possibly `game-server` if kept as Helm rather than rewritten as plain manifests

Decision rule:

- Keep Helm only where the templating is already useful and understandable.
- Rewrite to Kustomize bases where the chart is mostly boilerplate or where raw manifests are simpler.

Expected direction:

- Generic service templates may migrate to `apps/<service>/base/` Kustomize or stay as local charts referenced by Argo.
- `dotnet_pgsql_service` should be challenged hard before reuse because app-plus-database coupling often becomes awkward in GitOps.

## 5. Recover the `dev-server` vertical slice

Scope:

- game server chart/base
- `codex-context/dev-server/` values and configs
- namespace, storage, service exposure, TLS, and image pull secrets

Target:

- `apps/dev-server/base/`
- `apps/dev-server/overlays/dev/`
- `clusters/darkmoon/root/applications/dev/dev-server.yaml`

Notes:

- Keep this app environment-scoped.
- No production data migration is needed.
- Preserve operational files like server configs, but move them under the app rather than leaving them in generic chart staging.

## 6. Decompose `site-template.yaml` into a real `site` app

Split into:

- database/stateful components
- PVCs
- config maps
- deployment(s)
- service(s)
- ingress
- related secrets

Target:

- `apps/site/base/`
- `apps/site/overlays/dev/`
- `clusters/darkmoon/root/applications/dev/site.yaml`

Rules:

- Eliminate hardcoded namespace `dev-site`.
- Externalize inline secrets.
- Separate shared infra assumptions from site-specific config.
- If the site owns MySQL for `dev`, keep it with the app overlay for now rather than prematurely generalizing it.
- Replace recovered `registry.rp-wow.ru/*` image references with `registryv2.rp-wow.ru/*` where the registry has already been migrated.
- Use a shared namespace-agnostic SOPS-encrypted `regcred` secret as a single source of truth, then render it through one shared-secret Argo CD Application per namespace so workload Applications only reference it by name.

## 7. Recover backend services incrementally

Prioritize services by dependency value to the site and game flows:

1. `auth-service`
2. `api-gateway`
3. `vpn-service`
4. other backend APIs and workers

Per service target:

- `apps/<service>/base/`
- `apps/<service>/overlays/dev/`
- `clusters/darkmoon/root/applications/dev/<service>.yaml`

Rules:

- Do not batch all services into one Argo application.
- Promote only after the service's secret/config boundary is clean.
- Keep workers and cronjobs near the owning service unless there is a strong reason to split them.

## 8. Add a `dev` application group in Argo CD

Target additions:

- `clusters/darkmoon/root/applications/dev/kustomization.yaml`
- one Application per recovered dev workload
- update `clusters/darkmoon/root/applications/kustomization.yaml` to include the new group

Why:

- The repo currently has `core/` and `playground/`; recovered workloads need a dedicated `dev/` group.
- This gives a clean clone point for future environments.

## 9. Verification gates

Each promoted workload should pass:

- renders cleanly with the chosen toolchain
- no inline secrets remain
- namespace is overlay- or Argo-defined
- storage objects are explicit
- ingress/TLS ownership is explicit
- Argo sync succeeds without manual patching

## Implementation order

1. Restructure `local-charts/` into the recovery taxonomy.
2. Create the `clusters/darkmoon/root/applications/dev/` group.
3. Promote VPN variants into `platform/addons/`.
4. Promote `dev-server`.
5. Decompose and promote `site`.
6. Promote the minimum backend set required by `site` and `dev-server`.
7. Quarantine or delete dead recovery inputs after confidence is high.

## Open questions to resolve during implementation

- Which recovered backend services are truly needed for `dev` day one?
- Is `dotnet_pgsql_service` still worth keeping as a reusable primitive?
- Which VPN variant is externally exposed versus internal-only in the new cluster?
- Should `game-server` stay Helm-based or be flattened into Kustomize-managed manifests?
- Which parts of `site-template.yaml` are still operationally required versus historical baggage?

## Non-goals for the first pass

- prod migration
- stage migration
- live data import
- preserving every historical manifest exactly
- keeping all recovered abstractions if they slow down GitOps normalization
