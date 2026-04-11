#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from common import (  # noqa: E402
    decode_secret_for_yaml,
    display_path,
    load_settings,
    object_kind_path,
    object_name_path,
    object_namespace,
    prepare_output_root,
    render_cluster,
    unique_yaml_path,
    write_yaml,
)


def main() -> int:
    settings = load_settings()
    output_root = settings.output_root / "cluster"
    prepare_output_root(output_root, clean=settings.clean_output)

    count = 0
    for rendered in render_cluster(settings):
        doc = rendered.doc
        if doc.get("kind") == "Secret":
            doc = decode_secret_for_yaml(doc)

        namespace = object_namespace(doc, rendered.destination_namespace)
        kind = object_kind_path(doc)
        name = object_name_path(doc)
        output_dir = output_root / namespace / kind
        output_path = unique_yaml_path(output_dir, name, rendered.source_name)
        write_yaml(output_path, doc)
        count += 1

    print(f"Rendered {count} resources into {display_path(output_root, settings.repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
