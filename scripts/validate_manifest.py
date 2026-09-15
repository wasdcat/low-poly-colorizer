# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Validates addon/blender_manifest.toml and extension packaging structure.

Checks:
1. Valid TOML syntax.
2. Presence and validity of required Blender 4.2+ Extension fields.
3. Optional check against git release tag (--check-tag <tag>).
4. Optional check of built extension archive (--check-zip <path>).

Usage:
    python scripts/validate_manifest.py
    python scripts/validate_manifest.py --check-tag v0.1.1
    python scripts/validate_manifest.py --check-zip dist/low_poly_colorizer-0.1.1.zip
"""

import argparse
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "addon" / "blender_manifest.toml"

REQUIRED_FIELDS = [
    "schema_version",
    "id",
    "version",
    "name",
    "tagline",
    "maintainer",
    "type",
    "blender_version_min",
    "license",
]


def validate_manifest(check_tag: str | None = None) -> dict:
    if not MANIFEST_PATH.is_file():
        print(f"ERROR: Manifest file not found at '{MANIFEST_PATH}'", file=sys.stderr)
        sys.exit(1)

    try:
        with MANIFEST_PATH.open("rb") as f:
            manifest = tomllib.load(f)
    except Exception as e:
        print(f"ERROR: Failed to parse TOML in '{MANIFEST_PATH}': {e}", file=sys.stderr)
        sys.exit(1)

    missing = [k for k in REQUIRED_FIELDS if k not in manifest or not manifest[k]]
    if missing:
        print(f"ERROR: Missing or empty required manifest fields: {missing}", file=sys.stderr)
        sys.exit(1)

    version = manifest.get("version", "")
    addon_id = manifest.get("id", "")

    if check_tag:
        clean_tag = check_tag.lstrip("v")
        if clean_tag != version:
            print(
                f"ERROR: Git tag version '{check_tag}' (v{clean_tag}) does not match "
                f"manifest version '{version}'!",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Tag consistency confirmed: {check_tag} matches version {version}")

    print("Manifest valid:")
    print(f"  ID:          {addon_id}")
    print(f"  Version:     {version}")
    print(f"  Name:        {manifest.get('name')}")
    print(f"  Tagline:     {manifest.get('tagline')}")
    print(f"  Blender Min: {manifest.get('blender_version_min')}")
    print(f"  License:     {manifest.get('license')}")
    return manifest


def validate_zip(zip_path: Path):
    if not zip_path.is_file():
        print(f"ERROR: ZIP archive not found at '{zip_path}'", file=sys.stderr)
        sys.exit(1)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if "blender_manifest.toml" not in names:
            print(
                f"ERROR: {zip_path.name} is missing 'blender_manifest.toml' at archive root! "
                "extensions.blender.org requires the manifest directly at the root level.",
                file=sys.stderr,
            )
            sys.exit(1)
        if "__init__.py" not in names:
            print(f"ERROR: {zip_path.name} is missing '__init__.py' at archive root!", file=sys.stderr)
            sys.exit(1)
        print(f"ZIP package structure valid: {zip_path.name} ({len(names)} files)")


def main():
    parser = argparse.ArgumentParser(description="Validate blender_manifest.toml and package structure.")
    parser.add_argument("--check-tag", help="Verify that manifest version matches this git tag (e.g. v0.1.1).")
    parser.add_argument("--check-zip", type=Path, help="Verify that the given zip archive has valid root layout.")
    args = parser.parse_args()

    validate_manifest(check_tag=args.check_tag)
    if args.check_zip:
        validate_zip(args.check_zip)


if __name__ == "__main__":
    main()

