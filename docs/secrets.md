# Secrets With SOPS And age

This repo uses `SOPS` for file encryption and `age` for key management.

## Mental model

- Secret manifests stay in Git, but encrypted.
- The `age` public key is safe to keep in the repo.
- The `age` private key must never be committed.
- `.sops.yaml` tells `sops` which key should encrypt matching files.

## Local key

The local private key for this workstation is expected at:

`./.local/sops/age-key.txt`

That file is ignored by Git.

The public key currently configured in [/.sops.yaml](/home/dmitry/Dev/Personal/darkmoon-cluster/.sops.yaml) is:

`age1rnfzyrzrlykyx2ak7jymfd6f4293e65kfchtgmrvuty6wl8dydeqqcnkg3`

## File locations

Use encrypted secret files in one of these patterns:

- `clusters/<cluster>/config/secrets/*.enc.yaml`
- `apps/<app>/secrets/*.enc.yaml`

Keep plain manifests out of Git once they contain real secret values.

## Typical workflow

1. Create a plain secret manifest locally.
2. Encrypt it with `sops`.
3. Commit only the `*.enc.yaml` file.
4. Decrypt only when you need to inspect or edit values locally.

## Commands

Encrypt an already named file in place:

```bash
SOPS_AGE_KEY_FILE=.local/sops/age-key.txt sops -e -i clusters/darkmoon/config/secrets/cloudflare-api-key.enc.yaml
```

Create a new encrypted file from a temporary plain manifest:

```bash
SOPS_AGE_KEY_FILE=.local/sops/age-key.txt sops -e \
  --filename-override /home/dmitry/Dev/Personal/darkmoon-cluster/clusters/darkmoon/config/secrets/cloudflare-api-key.enc.yaml \
  --output clusters/darkmoon/config/secrets/cloudflare-api-key.enc.yaml \
  .local/secrets/cloudflare-api-key.yaml
```

`--filename-override` matters when the input file is outside the final repo path. That is how `sops` knows which `.sops.yaml` creation rule to use.

Edit an encrypted file:

```bash
SOPS_AGE_KEY_FILE=.local/sops/age-key.txt sops clusters/darkmoon/config/secrets/cloudflare-api-key.enc.yaml
```

View decrypted content without modifying:

```bash
SOPS_AGE_KEY_FILE=.local/sops/age-key.txt sops -d clusters/darkmoon/config/secrets/cloudflare-api-key.enc.yaml
```

Rotate encryption to the current `.sops.yaml` recipients:

```bash
SOPS_AGE_KEY_FILE=.local/sops/age-key.txt sops updatekeys -y clusters/darkmoon/config/secrets/cloudflare-api-key.enc.yaml
```

## Backup rule

Back up all of these together:

- Git repository
- `age` private key
- cluster bootstrap notes

If you lose the private key, you lose the ability to decrypt and update encrypted secrets.

## Argo CD integration

This repo uses `KSOPS` for Argo CD integration.

`KSOPS` is a Kustomize plugin that calls `sops` during manifest generation. The
flow is:

1. Argo CD runs `kustomize build`.
2. Kustomize sees a `ksops` generator.
3. `KSOPS` decrypts the referenced `*.enc.yaml` file with `sops`.
4. `sops` reads the mounted `age` private key and emits a normal Secret
   manifest to Argo CD.

Bootstrap files for Argo live under:

- `bootstrap/argocd/ksops/argocd-cm-patch.yaml`
- `bootstrap/argocd/ksops/argocd-repo-server-patch.yaml`
- `bootstrap/argocd/ksops/README.md`

The `age` private key must exist in-cluster as the `argocd/sops-age` secret.

## Current repo secret

The cluster currently includes:

`clusters/darkmoon/config/secrets/cloudflare-api-key.enc.yaml`

It is referenced by `clusters/darkmoon/config/secrets/secret-generator.yaml`
and is consumed by the Let's Encrypt DNS solver through the
`cloudflare-api-token` Secret.
