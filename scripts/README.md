# Cluster Observation Scripts

These scripts render the Argo CD-managed cluster locally into `./.local/tmp`.
They are intended for quick inspection by humans and AI agents after local
SOPS/KSOPS settings are available.

## Setup

Create a local env file from the root example:

```bash
cp .env.example .env
```

Then edit the paths in `.env`.

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

## `render_cluster.py`

Renders the configured Argo CD root, follows every rendered `Application`
`spec.source.path` that belongs to this repository, then writes resources under:

```text
./.local/tmp/cluster/<namespace>/<resource-kind>/<resource-name>.yaml
```

Cluster-scoped resources are written under `./.local/tmp/cluster/_cluster`.
Rendered `Secret` manifests are written with `decodedData` instead of base64
`data`, so the output is meant for inspection, not re-apply.

External Helm/chart Applications are kept as Argo CD `Application` manifests in
the root output, but their external chart contents are not rendered by this
tool. Override `DARKMOON_LOCAL_REPO_URLS` if this repository is referenced by a
different URL in your local branch.

Run it with:

```bash
python scripts/render_cluster.py
```

## `flatten_secrets.py`

Renders the same Argo CD graph and writes only decoded secrets under:

```text
./.local/tmp/secrets/<namespace>/<secret-name>/
```

Each secret folder contains `metadata.yaml` plus one file per secret key. Secret
`data` and `stringData` values are written as decoded bytes. The metadata keeps
the KSOPS source path, generator path, preferred `data`/`stringData` field, and
a `keys` map from safe local filenames back to Kubernetes Secret keys.

Run it with:

```bash
python scripts/flatten_secrets.py
```

## `render_apps.py`

Renders each local Argo CD `Application` separately and writes resources under:

```text
./.local/tmp/apps/<app-name>/<namespace>/<resource-kind>/<resource-name>.yaml
```

This is useful when you want the app boundary to be visible in the rendered
tree. Resources that set their own namespace use that namespace; namespaced
resources without `metadata.namespace` use the Application destination
namespace. Cluster-scoped resources use `_cluster`. Secret manifests are decoded
the same way as `render_cluster.py`.

Run it with:

```bash
python scripts/render_apps.py
```

## `reencrypt_secrets.py`

Reads edited flattened secrets from:

```text
./.local/tmp/secrets/<namespace>/<secret-name>/
```

Then maps each secret back to its original KSOPS-managed `*.enc.yaml` source,
replaces only the Secret values, and re-encrypts that source with `sops`.
The script decrypts the current encrypted file as a template first, so shared
namespace-agnostic secrets stay namespace-agnostic even when their flattened
render lives under a concrete namespace.

If a flattened `metadata.yaml` points `source.encryptedPath` at a new
`*.enc.yaml`, the script creates that encrypted file and appends it to
`source.generatorPath`. This lets you add a secret by copying a nearby flattened
folder, changing `metadata.name` and `source.encryptedPath`, editing the key
files, and running `reencrypt_secrets.py`.

Unchanged flattened values are skipped, so a fresh flatten followed by a dry
run should not rewrite every encrypted file.

Check the mapping without writing encrypted files:

```bash
python scripts/reencrypt_secrets.py --dry-run
```

Re-encrypt after editing flattened files:

```bash
python scripts/reencrypt_secrets.py
```

## Notes

- `DARKMOON_OUTPUT_ROOT` defaults to `./.local/tmp`.
- `DARKMOON_CLUSTER_ROOT_PATH` defaults to `clusters/darkmoon/root`.
- `DARKMOON_LOCAL_REPO_URLS` controls which Argo CD source URLs are treated as
  local paths.
- `DARKMOON_CLEAN_OUTPUT=true` removes the output root before each run.
- `SOPS_BIN` defaults to `sops`.
- `KSOPS_BIN` is used by prepending its directory to `PATH`, because the repo's
  KSOPS generator invokes `ksops` by name.
- The output contains decrypted secret material. Keep it under `.local/`, which
  is already ignored by Git.
