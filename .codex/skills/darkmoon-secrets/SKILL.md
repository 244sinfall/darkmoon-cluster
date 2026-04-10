---
name: darkmoon-secrets
description: Use when creating, moving, or reusing SOPS and KSOPS-managed secrets in this repository. Choose between cluster-scoped secrets under `clusters/<cluster>/config/secrets`, app-scoped secrets under `apps/<app>/secrets`, and shared namespace-agnostic secrets under `apps/_shared/secrets`, then wire them into Kustomize with KSOPS generators.
---

# Darkmoon Secrets

Use this skill when a task touches encrypted Kubernetes secrets in this repo.

The target pattern is:

- plaintext stays local only
- Git stores only `*.enc.yaml`
- Argo renders secrets through KSOPS
- shared namespaced secrets reuse one encrypted source and let overlays apply namespace

## Pick the right scope

### Cluster secret

Use when the cluster or shared infrastructure owns the secret.

Place in:

- `clusters/darkmoon/config/secrets/*.enc.yaml`

Wire through:

- `clusters/darkmoon/config/secrets/secret-generator.yaml`

Examples:

- `cloudflare-api-key.enc.yaml`
- `registry-basic-auth.enc.yaml`

### App secret

Use when one app owns the secret and it should travel with the app.

Place in:

- `apps/<app>/secrets/*.enc.yaml`

Wire through:

- the app overlay `kustomization.yaml` with a local KSOPS generator file

Examples:

- `apps/site/secrets/site-config.dev.enc.yaml`
- `apps/site/secrets/site-mysql.dev.enc.yaml`

### Shared namespaced secret

Use when the same secret value must exist in multiple namespaces.

Pattern:

- keep one encrypted Secret manifest under `apps/_shared/secrets/`
- omit `metadata.namespace`
- expose it through a reusable Kustomize package under `apps/_shared/<component>/`
- let the consuming overlay apply its namespace during render

Example:

- `apps/_shared/secrets/registry-pull-secret.enc.yaml`
- `apps/_shared/image-pull-secret/`

This is the preferred pattern for reusable `regcred`.

## Rules

- Never commit plaintext credentials or decrypted manifests.
- Do not duplicate ciphertext per namespace unless values differ.
- Keep secrets namespace-agnostic if they are meant to be reused across namespaces.
- Keep cluster singletons in `clusters/darkmoon/config/secrets/`.
- Keep app-owned secrets with the app even if only `dev` exists today.
- Prefer stable secret names to avoid churn in mounts and references.

## Workflow

1. Decide whether the secret is `cluster`, `app`, or `shared`.
2. Create a plain Secret manifest locally outside Git tracking.
3. Encrypt it with `sops` using `--filename-override` for the final repo path.
4. Add or update the KSOPS generator in the consuming Kustomization.
5. Render with standalone `kustomize build --enable-alpha-plugins --enable-exec`.
6. Only then wire the secret into workloads.

## Commands

Use the repo age key.

For plain `sops` commands, relative paths may work.
For local `kustomize` plus `ksops` rendering in this repo, use an absolute path:

```bash
SOPS_AGE_KEY_FILE=/home/dmitry/Dev/Personal/darkmoon-cluster/.local/sops/age-key.txt
```

Encrypt an app secret:

```bash
SOPS_AGE_KEY_FILE=.local/sops/age-key.txt sops -e \
  --filename-override /home/dmitry/Dev/Personal/darkmoon-cluster/apps/<app>/secrets/<name>.enc.yaml \
  --output apps/<app>/secrets/<name>.enc.yaml \
  .local/secrets/<name>.yaml
```

Encrypt a cluster secret:

```bash
SOPS_AGE_KEY_FILE=.local/sops/age-key.txt sops -e \
  --filename-override /home/dmitry/Dev/Personal/darkmoon-cluster/clusters/darkmoon/config/secrets/<name>.enc.yaml \
  --output clusters/darkmoon/config/secrets/<name>.enc.yaml \
  .local/secrets/<name>.yaml
```

Render locally:

```bash
SOPS_AGE_KEY_FILE=.local/sops/age-key.txt \
  kustomize build --enable-alpha-plugins --enable-exec apps/<app>/overlays/<env>
```

## Repo patterns

Read [references/repo-patterns.md](references/repo-patterns.md) for the exact repo examples and the `_shared` reuse pattern.
