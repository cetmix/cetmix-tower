#!/usr/bin/env python3
"""Set the website key on addon manifests.

``cetmix_drone`` stays at https://drone.cetmix.com. Every other addon
uses https://tower.cetmix.com. The shared maintainer hook rewrites every
manifest it finds, including this one, so this check replaces that hook.
"""

import ast
import os
import re
import sys

TOWER_URL = "https://tower.cetmix.com"
SKIP_ADDONS = {"cetmix_drone"}
WEBSITE_KEY_RE = re.compile(r"""(["']website["']\s*:\s*["'])([^"']*)(["'])""")


def main():
    """Rewrite addon website keys, leaving ``cetmix_drone`` unchanged.

    Returns:
        int: ``0`` when every checked manifest has the expected website.
        ``1`` when a manifest could not be checked.
    """
    addons_dir = "."
    for addon_dir in sorted(os.listdir(addons_dir)):
        if addon_dir in SKIP_ADDONS:
            continue
        manifest_path = os.path.join(addons_dir, addon_dir, "__manifest__.py")
        if not os.path.isfile(manifest_path):
            continue
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest_str = manifest_file.read()
        try:
            manifest = ast.literal_eval(manifest_str)
        except (SyntaxError, ValueError):
            print(f"Error parsing manifest {manifest_path}.", file=sys.stderr)
            return 1
        if "website" not in manifest:
            print(f"website key not found in manifest in {addon_dir}.", file=sys.stderr)
            return 1
        new_manifest_str, count = WEBSITE_KEY_RE.subn(
            r"\g<1>" + TOWER_URL + r"\g<3>", manifest_str
        )
        if count != 1:
            print(
                f"website key did not match once in manifest in {addon_dir}.",
                file=sys.stderr,
            )
            return 1
        if new_manifest_str != manifest_str:
            with open(manifest_path, "w", encoding="utf-8") as manifest_file:
                manifest_file.write(new_manifest_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
