from __future__ import annotations

import base64
import binascii
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

DEFAULT_OUTPUT_ROOT = REPO_ROOT / ".local" / "tmp"
DEFAULT_CLUSTER_ROOT_PATH = "clusters/darkmoon/root"
DEFAULT_LOCAL_REPO_URLS = (
    "git@github.com:244sinfall/darkmoon-cluster.git",
    "https://github.com/244sinfall/darkmoon-cluster.git",
)
CLUSTER_NAMESPACE = "_cluster"

CLUSTER_SCOPED_KINDS = {
    "APIService",
    "AppProject",
    "CertificateSigningRequest",
    "ClusterIssuer",
    "ClusterRole",
    "ClusterRoleBinding",
    "ComponentStatus",
    "CustomResourceDefinition",
    "IngressClass",
    "MutatingWebhookConfiguration",
    "Namespace",
    "Node",
    "PersistentVolume",
    "PriorityClass",
    "RuntimeClass",
    "StorageClass",
    "ValidatingAdmissionPolicy",
    "ValidatingAdmissionPolicyBinding",
    "ValidatingWebhookConfiguration",
    "VolumeAttachment",
}


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    output_root: Path
    cluster_root_path: str
    kustomize_bin: str
    ksops_bin: str | None
    sops_bin: str
    sops_age_key_file: str | None
    local_repo_urls: tuple[str, ...]
    clean_output: bool


@dataclass(frozen=True)
class RenderedDocument:
    doc: dict[str, Any]
    source_name: str
    source_path: str
    destination_namespace: str | None


@dataclass(frozen=True)
class LocalApplication:
    name: str
    source_path: str
    destination_namespace: str | None


def load_dotenv() -> None:
    """Load simple KEY=VALUE files without adding a runtime dependency."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_settings() -> Settings:
    load_dotenv()

    repo_root = Path(os.environ.get("DARKMOON_REPO_ROOT", REPO_ROOT)).expanduser().resolve()
    output_root = Path(os.environ.get("DARKMOON_OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT)).expanduser()
    if not output_root.is_absolute():
        output_root = repo_root / output_root

    sops_age_key_file = os.environ.get("SOPS_AGE_KEY_FILE")
    if sops_age_key_file:
        sops_age_key_file = str(Path(sops_age_key_file).expanduser().resolve())

    return Settings(
        repo_root=repo_root,
        output_root=output_root.resolve(),
        cluster_root_path=os.environ.get("DARKMOON_CLUSTER_ROOT_PATH", DEFAULT_CLUSTER_ROOT_PATH),
        kustomize_bin=os.environ.get("KUSTOMIZE_BIN", "kustomize"),
        ksops_bin=os.environ.get("KSOPS_BIN"),
        sops_bin=os.environ.get("SOPS_BIN", "sops"),
        sops_age_key_file=sops_age_key_file,
        local_repo_urls=_env_list("DARKMOON_LOCAL_REPO_URLS", DEFAULT_LOCAL_REPO_URLS),
        clean_output=_env_bool("DARKMOON_CLEAN_OUTPUT", default=True),
    )


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.environ.get(name)
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def prepare_output_root(path: Path, *, clean: bool) -> None:
    if clean and path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def command_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    if settings.sops_age_key_file:
        env["SOPS_AGE_KEY_FILE"] = settings.sops_age_key_file
    if settings.ksops_bin:
        ksops_path = _resolve_executable(settings.ksops_bin)
        if ksops_path:
            env["PATH"] = f"{ksops_path.parent}{os.pathsep}{env.get('PATH', '')}"
    return env


def render_cluster(settings: Settings) -> list[RenderedDocument]:
    root_docs = build_kustomize(settings, settings.cluster_root_path)
    rendered: list[RenderedDocument] = [
        RenderedDocument(
            doc=doc,
            source_name="argocd-root",
            source_path=settings.cluster_root_path,
            destination_namespace="argocd",
        )
        for doc in root_docs
        if is_kubernetes_object(doc)
    ]

    for app in local_applications(settings, root_docs):
        for doc in build_kustomize(settings, app.source_path):
            if is_kubernetes_object(doc):
                rendered.append(
                    RenderedDocument(
                        doc=doc,
                        source_name=app.name,
                        source_path=app.source_path,
                        destination_namespace=app.destination_namespace,
                    )
                )

    return rendered


def local_applications(settings: Settings, root_docs: Iterable[dict[str, Any]] | None = None) -> list[LocalApplication]:
    if root_docs is None:
        root_docs = build_kustomize(settings, settings.cluster_root_path)

    apps: list[LocalApplication] = []
    for app in sorted(_applications(root_docs), key=lambda item: item.get("metadata", {}).get("name", "")):
        source = app.get("spec", {}).get("source", {})
        path = source.get("path")
        if not path:
            continue
        app_name = app.get("metadata", {}).get("name", path)
        if not _is_local_source(settings, source):
            repo_url = source.get("repoURL", "<missing repoURL>")
            print(f"Skipping external Application {app_name}: {repo_url}", file=sys.stderr)
            continue
        if not (settings.repo_root / path).exists():
            print(f"Skipping Application {app_name}: local path does not exist: {path}", file=sys.stderr)
            continue
        apps.append(
            LocalApplication(
                name=str(app_name),
                source_path=str(path),
                destination_namespace=app.get("spec", {}).get("destination", {}).get("namespace"),
            )
        )
    return apps


def build_kustomize(settings: Settings, path: str) -> list[dict[str, Any]]:
    cmd = [
        settings.kustomize_bin,
        "build",
        "--enable-alpha-plugins",
        "--enable-exec",
        path,
    ]
    result = subprocess.run(
        cmd,
        cwd=settings.repo_root,
        env=command_env(settings),
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"kustomize build failed for {path}\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    return [doc for doc in yaml.safe_load_all(result.stdout) if isinstance(doc, dict)]


def is_kubernetes_object(doc: dict[str, Any]) -> bool:
    return bool(doc.get("apiVersion") and doc.get("kind") and doc.get("metadata", {}).get("name"))


def object_namespace(doc: dict[str, Any], destination_namespace: str | None = None) -> str:
    kind = str(doc.get("kind", ""))
    namespace = doc.get("metadata", {}).get("namespace")
    if namespace:
        return str(namespace)
    if kind in CLUSTER_SCOPED_KINDS:
        return CLUSTER_NAMESPACE
    return destination_namespace or CLUSTER_NAMESPACE


def object_kind_path(doc: dict[str, Any]) -> str:
    return safe_path_part(str(doc.get("kind", "unknown")).lower())


def object_name_path(doc: dict[str, Any]) -> str:
    return safe_path_part(str(doc.get("metadata", {}).get("name", "unnamed")))


def safe_path_part(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return value.strip(".-") or "unnamed"


def unique_yaml_path(directory: Path, name: str, source_name: str) -> Path:
    candidate = directory / f"{name}.yaml"
    if not candidate.exists():
        return candidate
    return directory / f"{name}--{safe_path_part(source_name)}.yaml"


def write_yaml(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def decode_secret_for_yaml(secret: dict[str, Any]) -> dict[str, Any]:
    secret = dict(secret)
    decoded = decode_secret_data(secret)
    if decoded:
        secret.pop("data", None)
        secret["decodedData"] = decoded
    return secret


def decode_secret_data(secret: dict[str, Any]) -> dict[str, str]:
    decoded: dict[str, str] = {}
    data = secret.get("data") or {}
    if not isinstance(data, dict):
        return decoded

    for key, value in data.items():
        if not isinstance(value, str):
            continue
        try:
            raw_value = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            decoded[key] = value
            continue
        try:
            decoded[key] = raw_value.decode("utf-8")
        except UnicodeDecodeError:
            decoded[key] = value
    return decoded


def decode_secret_data_bytes(secret: dict[str, Any]) -> dict[str, bytes]:
    decoded: dict[str, bytes] = {}
    data = secret.get("data") or {}
    if not isinstance(data, dict):
        return decoded
    for key, value in data.items():
        if not isinstance(value, str):
            continue
        try:
            decoded[key] = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            decoded[key] = value.encode("utf-8")
    return decoded


def secret_string_data(secret: dict[str, Any]) -> dict[str, str]:
    string_data = secret.get("stringData") or {}
    if not isinstance(string_data, dict):
        return {}
    return {str(key): str(value) for key, value in string_data.items()}


def _applications(docs: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for doc in docs:
        if doc.get("apiVersion") == "argoproj.io/v1alpha1" and doc.get("kind") == "Application":
            yield doc


def _is_local_source(settings: Settings, source: dict[str, Any]) -> bool:
    repo_url = source.get("repoURL")
    if not repo_url:
        return True
    return str(repo_url) in settings.local_repo_urls


def _resolve_executable(value: str) -> Path | None:
    if os.sep not in value and (os.altsep is None or os.altsep not in value):
        resolved = shutil.which(value)
        return Path(resolved) if resolved else None
    return Path(value).expanduser().resolve()
