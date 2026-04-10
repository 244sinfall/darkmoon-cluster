---
name: darkmoon-verification
description: Use when changing Kubernetes manifests, Kustomizations, SOPS secrets, or Argo CD applications in this repository. Verify changes by rendering the affected target locally with standalone `kustomize` plus `ksops`, using the repo age key via an absolute `SOPS_AGE_KEY_FILE` path.
---

# Darkmoon Verification

Any manifest or secret change must be rendered locally before it is considered done.

## Rule

After changing any of these:

- `apps/**`
- `clusters/**`
- shared secret packages under `apps/_shared/**`
- encrypted secret files consumed by KSOPS

render the affected target with standalone `kustomize` and `ksops`.

Treat render failures as blocking.

## Commands

Use the repo age key with an absolute path:

```bash
export SOPS_AGE_KEY_FILE=/home/dmitry/Dev/Personal/darkmoon-cluster/.local/sops/age-key.txt
```

Render an app overlay:

```bash
~/.local/bin/kustomize build --enable-alpha-plugins --enable-exec apps/<app>/overlays/<env>
```

Render cluster config:

```bash
~/.local/bin/kustomize build --enable-alpha-plugins --enable-exec clusters/darkmoon/config
```

Render cluster root applications:

```bash
kubectl kustomize clusters/darkmoon/root
```

## Current baseline

Examples that should render locally:

```bash
export SOPS_AGE_KEY_FILE=/home/dmitry/Dev/Personal/darkmoon-cluster/.local/sops/age-key.txt

~/.local/bin/kustomize build --enable-alpha-plugins --enable-exec apps/site/overlays/dev
~/.local/bin/kustomize build --enable-alpha-plugins --enable-exec clusters/darkmoon/config
kubectl kustomize clusters/darkmoon/root
```
