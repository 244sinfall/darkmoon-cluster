# Argo CD bootstrap

This directory is only for the first bootstrap operations that happen before Argo CD manages itself.

## Install Argo CD

Use an official upstream install manifest pinned to an explicit version. Example shape:

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/<ARGOCD_VERSION>/manifests/install.yaml
```

Replace `<ARGOCD_VERSION>` with the version you want to run.

## Bootstrap the repo

After Argo CD is installed and the API server is reachable:

1. If the repository is private, create the Argo CD repository credential secret first.
2. Apply the root application:

```bash
kubectl apply -f bootstrap/argocd/root-application.yaml
```

## Why keep install outside Argo

The cluster needs Argo CD before Argo CD can sync anything from Git. After that, Argo takes over the objects under `clusters/` and `platform/`.
