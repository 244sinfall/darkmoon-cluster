#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from common import (  # noqa: E402
    SecretSourceReference,
    build_secret_source_index,
    decode_secret_data_bytes,
    display_path,
    load_settings,
    object_name_path,
    object_namespace,
    prepare_output_root,
    render_cluster,
    safe_path_part,
    secret_value_field,
    secret_string_data,
    write_yaml,
)


def main() -> int:
    settings = load_settings()
    output_root = settings.output_root / "secrets"
    prepare_output_root(output_root, clean=settings.clean_output)
    source_index = build_secret_source_index(settings)

    secret_dirs = set()
    for rendered in render_cluster(settings):
        secret = rendered.doc
        if secret.get("kind") != "Secret":
            continue

        namespace = object_namespace(secret, rendered.destination_namespace)
        secret_name = object_name_path(secret)
        secret_dir = output_root / namespace / secret_name
        secret_dir.mkdir(parents=True, exist_ok=True)

        values = flattened_secret_values(secret)
        key_map = build_key_map(values)
        source_ref = source_index.get((rendered.source_name, str(secret.get("metadata", {}).get("name"))))
        metadata = build_metadata(settings, rendered, secret, namespace, source_ref, key_map)
        write_yaml(secret_dir / "metadata.yaml", metadata)

        for file_name, key in key_map.items():
            (secret_dir / file_name).write_bytes(values[key])

        secret_dirs.add(secret_dir)

    print(f"Flattened {len(secret_dirs)} secrets into {display_path(output_root, settings.repo_root)}")
    return 0


def build_metadata(
    settings,
    rendered,
    secret: dict,
    namespace: str,
    source_ref: SecretSourceReference | None,
    key_map: dict[str, str],
) -> dict:
    source_secret = source_ref.secret if source_ref is not None else secret
    metadata = {
        key: source_secret.get(key)
        for key in ("apiVersion", "kind", "metadata", "type", "immutable")
        if source_secret.get(key) is not None
    }
    metadata["source"] = {
        "application": rendered.source_name,
        "path": rendered.source_path,
        "renderedNamespace": namespace,
    }
    metadata["keys"] = key_map

    if source_ref is not None:
        metadata["source"].update(
            {
                "encryptedPath": display_path(source_ref.encrypted_path, settings.repo_root),
                "generatorPath": display_path(source_ref.generator_path, settings.repo_root),
                "generatorFile": source_ref.generator_file,
                "valueField": secret_value_field(source_ref.secret),
            }
        )
    return metadata


def flattened_secret_values(secret: dict) -> dict[str, bytes]:
    values = decode_secret_data_bytes(secret)
    values.update({key: value.encode("utf-8") for key, value in secret_string_data(secret).items()})
    return values


def build_key_map(values: dict[str, bytes]) -> dict[str, str]:
    key_map: dict[str, str] = {}
    for key in sorted(values):
        base_name = safe_path_part(str(key))
        file_name = base_name
        suffix = 2
        while file_name in key_map:
            file_name = f"{base_name}--{suffix}"
            suffix += 1
        key_map[file_name] = str(key)
    return key_map


if __name__ == "__main__":
    raise SystemExit(main())
