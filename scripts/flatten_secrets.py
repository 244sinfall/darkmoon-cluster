#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from common import (  # noqa: E402
    decode_secret_data_bytes,
    display_path,
    load_settings,
    object_name_path,
    object_namespace,
    prepare_output_root,
    render_cluster,
    safe_path_part,
    secret_string_data,
    write_yaml,
)


def main() -> int:
    settings = load_settings()
    output_root = settings.output_root / "secrets"
    prepare_output_root(output_root, clean=settings.clean_output)

    secret_dirs = set()
    for rendered in render_cluster(settings):
        secret = rendered.doc
        if secret.get("kind") != "Secret":
            continue

        namespace = object_namespace(secret, rendered.destination_namespace)
        secret_name = object_name_path(secret)
        secret_dir = output_root / namespace / secret_name
        secret_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "apiVersion": secret.get("apiVersion"),
            "kind": secret.get("kind"),
            "metadata": secret.get("metadata", {}),
            "type": secret.get("type"),
            "source": {
                "application": rendered.source_name,
                "path": rendered.source_path,
            },
        }
        write_yaml(secret_dir / "metadata.yaml", metadata)

        for key, value in decode_secret_data_bytes(secret).items():
            (secret_dir / safe_path_part(str(key))).write_bytes(value)
        for key, value in secret_string_data(secret).items():
            (secret_dir / safe_path_part(str(key))).write_text(value, encoding="utf-8")

        secret_dirs.add(secret_dir)

    print(f"Flattened {len(secret_dirs)} secrets into {display_path(output_root, settings.repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
