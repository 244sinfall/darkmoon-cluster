---
name: darkmoon-verification
description: Use when changing Kubernetes manifests, Kustomizations, SOPS secrets, Argo CD applications, or local observation scripts in this repository. Verify changes through the repo Python tooling after activating `.venv` and sourcing the repo-root `.env`.
---

# Darkmoon Verification

Any manifest, secret, or observation script change must be rendered locally before it is considered done.

## Rule

After changing any of these:

- `apps/**`
- `clusters/**`
- shared secret packages under `apps/_shared/**`
- encrypted secret files consumed by KSOPS
- observation tooling under `scripts/**`

render the local observation outputs through the repo Python scripts.

Treat render failures as blocking.

## Commands

Use the repo-root `.env` for local binary paths, KSOPS wiring, and the SOPS age key. Do not hardcode workstation home paths in verification commands.

Render the cluster observation tree:

```bash
source .venv/bin/activate && source .env && python scripts/render_cluster.py
```

Render the flattened secret observation tree:

```bash
source .venv/bin/activate && source .env && python scripts/flatten_secrets.py
```

Render the per-Application observation tree:

```bash
source .venv/bin/activate && source .env && python scripts/render_apps.py
```

If `.venv` does not exist or dependencies are missing, create/install them from the repo root:

```bash
python -m venv .venv
source .venv/bin/activate && python -m pip install -r requirements.txt
```

The scripts render the Argo CD root plus local Application sources and write output under:

- `.local/tmp/cluster`
- `.local/tmp/secrets`
- `.local/tmp/apps`

When checking the re-encryption path, use dry-run mode unless the user explicitly
wants encrypted secret files rewritten:

```bash
source .venv/bin/activate && source .env && python scripts/reencrypt_secrets.py --dry-run
```

## Current baseline

Examples that should render locally:

```bash
source .venv/bin/activate && source .env && python scripts/render_cluster.py
source .venv/bin/activate && source .env && python scripts/flatten_secrets.py
source .venv/bin/activate && source .env && python scripts/render_apps.py
```
