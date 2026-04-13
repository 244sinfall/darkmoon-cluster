#!/usr/bin/env python3
from __future__ import annotations

import base64
import argparse
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from common import (  # noqa: E402
    SecretSourceReference,
    build_secret_source_index,
    command_env,
    decode_secret_data_bytes,
    decrypt_secret_source,
    display_path,
    load_settings,
    read_yaml,
    secret_string_data,
    secret_value_field,
    write_yaml,
)


@dataclass(frozen=True)
class SecretRequest:
    metadata_path: Path
    secret_dir: Path
    app_name: str
    secret_name: str
    target_path: Path
    generator_path: Path | None
    value_field: str | None
    metadata: dict[str, Any]
    values: dict[str, bytes]


def main() -> int:
    args = parse_args()
    settings = load_settings()
    secrets_root = settings.output_root / "secrets"
    if not secrets_root.exists():
        raise SystemExit(f"Flattened secrets directory does not exist: {display_path(secrets_root, settings.repo_root)}")

    source_index = build_secret_source_index(settings)
    requests = collect_requests(settings, secrets_root, source_index)

    changed = 0
    skipped = 0
    generator_updates = 0
    for target_path, target_requests in grouped_by_target(requests).items():
        request = merged_request(settings, target_path, target_requests)
        target_exists = target_path.exists()
        template = decrypt_secret_source(settings, target_path) if target_exists else build_new_secret_template(request.metadata)
        updated = apply_flattened_values(template, request.values, request.value_field)
        generator_needs_entry = (
            not target_exists
            and request.generator_path is not None
            and not generator_contains_target(request.generator_path, target_path)
        )

        if target_exists and secret_values(template) == secret_values(updated):
            print(f"Skipped unchanged {request.app_name}/{request.secret_name} -> {display_path(target_path, settings.repo_root)}")
            skipped += 1
            continue

        if args.dry_run:
            action = "create" if not target_exists else "re-encrypt"
            print(f"Would {action} {request.app_name}/{request.secret_name} -> {display_path(target_path, settings.repo_root)}")
            if generator_needs_entry and request.generator_path is not None:
                print(
                    "Would add "
                    f"{generator_file_entry(request.generator_path, target_path)} "
                    f"to {display_path(request.generator_path, settings.repo_root)}"
                )
        else:
            encrypt_secret(settings, updated, target_path)
            if not target_exists and request.generator_path is not None:
                if generator_needs_entry and add_generator_entry(settings, request.generator_path, target_path):
                    generator_updates += 1
                print(f"Created {request.app_name}/{request.secret_name} -> {display_path(target_path, settings.repo_root)}")
            else:
                print(f"Re-encrypted {request.app_name}/{request.secret_name} -> {display_path(target_path, settings.repo_root)}")
        changed += 1

    action = "Checked" if args.dry_run else "Updated"
    print(
        f"{action} {changed} changed/new secrets from {display_path(secrets_root, settings.repo_root)}; "
        f"skipped {skipped} unchanged"
    )
    if generator_updates:
        print(f"Updated {generator_updates} KSOPS generator files")
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


def collect_requests(
    settings,
    secrets_root: Path,
    source_index: dict[tuple[str, str], SecretSourceReference],
) -> list[SecretRequest]:
    requests: list[SecretRequest] = []
    for metadata_path in sorted(secrets_root.glob("*/*/metadata.yaml")):
        secret_dir = metadata_path.parent
        metadata = read_yaml(metadata_path)
        source = metadata.get("source") or {}
        if not isinstance(source, dict):
            raise RuntimeError(f"Invalid source metadata in {display_path(metadata_path, settings.repo_root)}")
        app_name = source.get("application")
        secret_name = metadata.get("metadata", {}).get("name")
        if not app_name or not secret_name:
            print(f"Skipping {metadata_path}: missing source.application or metadata.name", file=sys.stderr)
            continue

        source_ref = source_index.get((str(app_name), str(secret_name)))
        target_path = resolve_target_path(settings, source, source_ref)
        generator_path = resolve_generator_path(settings, source, source_ref, target_path)
        value_field = str(source.get("valueField")) if source.get("valueField") else None

        requests.append(
            SecretRequest(
                metadata_path=metadata_path,
                secret_dir=secret_dir,
                app_name=str(app_name),
                secret_name=str(secret_name),
                target_path=target_path,
                generator_path=generator_path,
                value_field=value_field,
                metadata=metadata,
                values=read_flattened_values(secret_dir, metadata),
            )
        )
    return requests


def resolve_target_path(settings, source: dict[str, Any], source_ref: SecretSourceReference | None) -> Path:
    metadata_target = source.get("encryptedPath") or source.get("targetPath")
    if source_ref is not None:
        if metadata_target:
            requested_path = resolve_repo_path(settings, str(metadata_target), "source.encryptedPath")
            if requested_path != source_ref.encrypted_path:
                raise RuntimeError(
                    "source.encryptedPath disagrees with rendered KSOPS source: "
                    f"{display_path(requested_path, settings.repo_root)} != "
                    f"{display_path(source_ref.encrypted_path, settings.repo_root)}"
                )
        return source_ref.encrypted_path

    if not metadata_target:
        app_name = source.get("application", "<missing application>")
        raise RuntimeError(f"No encrypted source found for {app_name}; set source.encryptedPath for new secrets")

    target_path = resolve_repo_path(settings, str(metadata_target), "source.encryptedPath")
    if not target_path.name.endswith((".enc.yaml", ".enc.yml")):
        raise RuntimeError(f"source.encryptedPath must point to a *.enc.yaml file: {display_path(target_path, settings.repo_root)}")
    return target_path


def resolve_generator_path(
    settings,
    source: dict[str, Any],
    source_ref: SecretSourceReference | None,
    target_path: Path,
) -> Path | None:
    if source_ref is not None:
        return source_ref.generator_path

    generator_value = source.get("generatorPath")
    if not generator_value:
        if target_path.exists():
            return None
        raise RuntimeError(
            "source.generatorPath is required when creating a new encrypted secret: "
            f"{display_path(target_path, settings.repo_root)}"
        )
    generator_path = resolve_repo_path(settings, str(generator_value), "source.generatorPath")
    if not generator_path.exists():
        raise RuntimeError(f"source.generatorPath does not exist: {display_path(generator_path, settings.repo_root)}")
    return generator_path


def resolve_repo_path(settings, value: str, field_name: str) -> Path:
    raw_path = Path(value).expanduser()
    path = raw_path if raw_path.is_absolute() else settings.repo_root / raw_path
    path = path.resolve()
    try:
        path.relative_to(settings.repo_root)
    except ValueError as error:
        raise RuntimeError(f"{field_name} must stay inside the repo: {value}") from error
    return path


def grouped_by_target(requests: list[SecretRequest]) -> dict[Path, list[SecretRequest]]:
    grouped: dict[Path, list[SecretRequest]] = defaultdict(list)
    for request in requests:
        grouped[request.target_path].append(request)
    return dict(sorted(grouped.items(), key=lambda item: str(item[0])))


def merged_request(settings, target_path: Path, requests: list[SecretRequest]) -> SecretRequest:
    first = requests[0]
    for request in requests[1:]:
        if request.secret_name != first.secret_name:
            raise RuntimeError(
                f"Multiple secret names point to {display_path(target_path, settings.repo_root)}: "
                f"{first.secret_name}, {request.secret_name}"
            )
        if request.values != first.values:
            paths = ", ".join(display_path(item.metadata_path.parent, settings.repo_root) for item in requests)
            raise RuntimeError(
                f"Flattened secret values for {display_path(target_path, settings.repo_root)} disagree across: {paths}"
            )
    return first


def build_new_secret_template(metadata: dict[str, Any]) -> dict[str, Any]:
    secret = {
        key: value
        for key, value in metadata.items()
        if key not in {"source", "rendered", "data", "stringData"} and value is not None
    }
    secret["apiVersion"] = secret.get("apiVersion") or "v1"
    secret["kind"] = secret.get("kind") or "Secret"
    if secret.get("kind") != "Secret":
        raise RuntimeError("metadata.yaml must describe a Secret")
    secret_metadata = secret.get("metadata")
    if not isinstance(secret_metadata, dict) or not secret_metadata.get("name"):
        raise RuntimeError("metadata.yaml must include metadata.name")
    return secret


def apply_flattened_values(
    secret: dict[str, Any],
    values: dict[str, bytes],
    requested_value_field: str | None,
) -> dict[str, Any]:
    updated = dict(secret)
    value_field = requested_value_field or secret_value_field(secret)
    if value_field == "stringData":
        updated.pop("data", None)
        updated["stringData"] = string_data_values(values)
    elif value_field == "data":
        updated.pop("stringData", None)
        updated["data"] = data_values(values)
    else:
        raise RuntimeError(f"Unsupported source.valueField {value_field!r}; expected data or stringData")
    return updated


def read_flattened_values(secret_dir: Path, metadata: dict[str, Any]) -> dict[str, bytes]:
    metadata_file = secret_dir / "metadata.yaml"
    key_map = metadata.get("keys") or {}
    if not isinstance(key_map, dict):
        raise RuntimeError(f"metadata keys must be a mapping: {metadata_file}")
    return {
        str(key_map.get(path.name, path.name)): read_flattened_value(path)
        for path in sorted(secret_dir.iterdir())
        if path.is_file() and path != metadata_file
    }


def data_values(values: dict[str, bytes]) -> dict[str, str]:
    return {key: base64.b64encode(value).decode("ascii") for key, value in values.items()}


def string_data_values(values: dict[str, bytes]) -> dict[str, str]:
    decoded: dict[str, str] = {}
    for key, value in values.items():
        try:
            decoded[key] = value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RuntimeError(f"Cannot write binary flattened value {key!r} as stringData") from error
    return decoded


def secret_values(secret: dict[str, Any]) -> dict[str, bytes]:
    values = decode_secret_data_bytes(secret)
    values.update({key: value.encode("utf-8") for key, value in secret_string_data(secret).items()})
    return values


def read_flattened_value(path: Path) -> bytes:
    return path.read_bytes()


def generator_contains_target(generator_path: Path, target_path: Path) -> bool:
    doc = read_yaml(generator_path)
    files = ksops_generator_files(doc, generator_path)
    return any((generator_path.parent / str(item)).resolve() == target_path for item in files)


def add_generator_entry(settings, generator_path: Path, target_path: Path) -> bool:
    doc = read_yaml(generator_path)
    files = ksops_generator_files(doc, generator_path)
    if any((generator_path.parent / str(item)).resolve() == target_path for item in files):
        return False
    files.append(generator_file_entry(generator_path, target_path))
    write_yaml(generator_path, doc)
    print(f"Added {display_path(target_path, settings.repo_root)} to {display_path(generator_path, settings.repo_root)}")
    return True


def ksops_generator_files(doc: dict[str, Any], generator_path: Path) -> list[Any]:
    if doc.get("kind") != "ksops":
        raise RuntimeError(f"Generator is not a KSOPS generator: {generator_path}")
    files = doc.get("files")
    if files is None:
        files = []
        doc["files"] = files
    if not isinstance(files, list):
        raise RuntimeError(f"KSOPS generator files must be a list: {generator_path}")
    return files


def generator_file_entry(generator_path: Path, target_path: Path) -> str:
    if target_path.parent == generator_path.parent:
        return f"./{target_path.name}"
    return Path(os.path.relpath(target_path, generator_path.parent)).as_posix()


def encrypt_secret(settings, secret: dict[str, Any], target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
    write_yaml(temp_path, secret)
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


if __name__ == "__main__":
    raise SystemExit(main())
