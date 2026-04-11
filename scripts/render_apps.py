#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from common import (  # noqa: E402
    build_kustomize,
    decode_secret_for_yaml,
    display_path,
    is_kubernetes_object,
    load_settings,
    local_applications,
    object_kind_path,
    object_name_path,
    object_namespace,
    prepare_output_root,
    safe_path_part,
    unique_yaml_path,
    write_yaml,
)


def main() -> int:
    settings = load_settings()
    output_root = settings.output_root / "apps"
    prepare_output_root(output_root, clean=settings.clean_output)

    app_count = 0
    resource_count = 0
    for app in local_applications(settings):
        app_count += 1
        app_root = output_root / safe_path_part(app.name)
        for doc in build_kustomize(settings, app.source_path):
            if not is_kubernetes_object(doc):
                continue
            if doc.get("kind") == "Secret":
                doc = decode_secret_for_yaml(doc)

            namespace = object_namespace(doc, app.destination_namespace)
            kind = object_kind_path(doc)
            name = object_name_path(doc)
            output_dir = app_root / namespace / kind
            output_path = unique_yaml_path(output_dir, name, app.name)
            write_yaml(output_path, doc)
            resource_count += 1

    print(
        f"Rendered {resource_count} resources from {app_count} applications "
        f"into {display_path(output_root, settings.repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
