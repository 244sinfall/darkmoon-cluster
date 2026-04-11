#!/usr/bin/env python3
from __future__ import annotations

import base64
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

sys.dont_write_bytecode = True

from common import (  # noqa: E402
    build_kustomize,
    command_env,
    display_path,
    is_kubernetes_object,
    load_settings,
    local_applications,
)


def main() -> int:
    args = parse_args()
    settings = load_settings()
    secrets_root = settings.output_root / "secrets"
    if not secrets_root.exists():
        raise SystemExit(f"Flattened secrets directory does not exist: {display_path(secrets_root, settings.repo_root)}")

    source_index = build_source_index(settings)
    count = 0
    for metadata_path in sorted(secrets_root.glob("*/*/metadata.yaml")):
        secret_dir = metadata_path.parent
        metadata = read_yaml(metadata_path)
        source = metadata.get("source") or {}
        app_name = source.get("application")
        secret_name = metadata.get("metadata", {}).get("name")
        if not app_name or not secret_name:
            print(f"Skipping {metadata_path}: missing source.application or metadata.name", file=sys.stderr)
            continue

        target_path = source_index.get((str(app_name), str(secret_name)))
        if target_path is None:
            raise RuntimeError(f"No encrypted source found for {app_name}/{secret_name}")

        template = decrypt_secret(settings, target_path)
        updated = apply_flattened_values(template, secret_dir)
        if args.dry_run:
            print(f"Would re-encrypt {app_name}/{secret_name} -> {display_path(target_path, settings.repo_root)}")
        else:
            encrypt_secret(settings, updated, target_path)
            print(f"Re-encrypted {app_name}/{secret_name} -> {display_path(target_path, settings.repo_root)}")
        count += 1

    action = "Checked" if args.dry_run else "Re-encrypted"
    print(f"{action} {count} secrets from {display_path(secrets_root, settings.repo_root)}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild SOPS-encrypted Secret manifests from .local/tmp/secrets."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve sources and rebuild in memory without writing encrypted files.",
    )
    return parser.parse_args()


def build_source_index(settings) -> dict[tuple[str, str], Path]:
    index: dict[tuple[str, str], Path] = {}
    for app in local_applications(settings):
        encrypted_files = collect_ksops_files(settings.repo_root / app.source_path)
        if not encrypted_files:
            continue

        secret_sources: dict[str, Path] = {}
        for encrypted_file in encrypted_files:
            secret = decrypt_secret(settings, encrypted_file)
            name = secret.get("metadata", {}).get("name")
            if not name:
                continue
            if name in secret_sources:
                raise RuntimeError(f"Duplicate secret name {name} in Application {app.name}")
            secret_sources[str(name)] = encrypted_file

        for doc in build_kustomize(settings, app.source_path):
            if is_kubernetes_object(doc) and doc.get("kind") == "Secret":
                rendered_name = str(doc.get("metadata", {}).get("name"))
                source_path = secret_sources.get(rendered_name)
                if source_path is None:
                    continue
                key = (app.name, rendered_name)
                existing = index.get(key)
                if existing is not None and existing != source_path:
                    raise RuntimeError(f"Ambiguous encrypted source for {app.name}/{rendered_name}")
                index[key] = source_path
    return index


def collect_ksops_files(root: Path) -> list[Path]:
    seen: set[Path] = set()
    encrypted_files: list[Path] = []
    visit_kustomization(root, seen, encrypted_files)
    return encrypted_files


def visit_kustomization(path: Path, seen: set[Path], encrypted_files: list[Path]) -> None:
    path = path.resolve()
    if path in seen or not path.exists():
        return
    seen.add(path)

    kustomization = path / "kustomization.yaml"
    if not kustomization.exists():
        return
    doc = read_yaml(kustomization)

    for generator in doc.get("generators") or []:
        generator_path = (path / str(generator)).resolve()
        if not generator_path.exists():
            continue
        generator_doc = read_yaml(generator_path)
        if generator_doc.get("kind") != "ksops":
            continue
        for encrypted_file in generator_doc.get("files") or []:
            encrypted_files.append((generator_path.parent / str(encrypted_file)).resolve())

    for resource in doc.get("resources") or []:
        resource_path = (path / str(resource)).resolve()
        if resource_path.is_dir():
            visit_kustomization(resource_path, seen, encrypted_files)


def decrypt_secret(settings, encrypted_path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [settings.sops_bin, "-d", str(encrypted_path)],
        cwd=settings.repo_root,
        env=command_env(settings),
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sops decrypt failed for {display_path(encrypted_path, settings.repo_root)}\n{result.stderr}")
    doc = yaml.safe_load(result.stdout)
    if not isinstance(doc, dict) or doc.get("kind") != "Secret":
        raise RuntimeError(f"Decrypted file is not a Secret: {display_path(encrypted_path, settings.repo_root)}")
    return doc


def apply_flattened_values(secret: dict[str, Any], secret_dir: Path) -> dict[str, Any]:
    metadata_file = secret_dir / "metadata.yaml"
    values = {
        path.name: base64.b64encode(path.read_bytes()).decode("ascii")
        for path in sorted(secret_dir.iterdir())
        if path.is_file() and path != metadata_file
    }
    updated = dict(secret)
    updated.pop("stringData", None)
    updated["data"] = values
    return updated


def encrypt_secret(settings, secret: dict[str, Any], target_path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False) as temp_file:
        yaml.safe_dump(secret, temp_file, sort_keys=False)
        temp_path = Path(temp_file.name)
    try:
        result = subprocess.run(
            [
                settings.sops_bin,
                "-e",
                "--filename-override",
                str(target_path.relative_to(settings.repo_root)),
                "--output",
                str(target_path),
                str(temp_path),
            ],
            cwd=settings.repo_root,
            env=command_env(settings),
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"sops encrypt failed for {display_path(target_path, settings.repo_root)}\n{result.stderr}")
    finally:
        temp_path.unlink(missing_ok=True)


def read_yaml(path: Path) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc if isinstance(doc, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
