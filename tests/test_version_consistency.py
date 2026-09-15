# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Tests that verify version number consistency across the entire project.

Ensures that:
- addon/blender_manifest.toml (single source of truth)
- README.md (version badge)
- docs/manual/de/markpublish.yaml
- docs/manual/en/markpublish.yaml
all declare the identical version string.
Also verifies that the compiled user manuals exist.
"""

import re
import tomllib
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent


def get_manifest_version() -> str:
    manifest_path = ROOT / "addon" / "blender_manifest.toml"
    assert manifest_path.is_file(), f"Manifest not found: {manifest_path}"
    with manifest_path.open("rb") as f:
        data = tomllib.load(f)
    version = data.get("version")
    assert version, "version key missing or empty in blender_manifest.toml"
    return version


def test_readme_version_badge_matches_manifest():
    manifest_version = get_manifest_version()
    readme_path = ROOT / "README.md"
    assert readme_path.is_file(), f"README.md not found: {readme_path}"
    content = readme_path.read_text(encoding="utf-8")

    # Match badge: ![Version](https://img.shields.io/badge/version-<version>-blue)
    match = re.search(r"img\.shields\.io/badge/version-([0-9A-Za-z.\-_]+)-blue", content)
    assert match is not None, "Version badge not found in README.md"
    readme_version = match.group(1)
    assert readme_version == manifest_version, (
        f"Version mismatch: README.md badge has '{readme_version}', "
        f"but blender_manifest.toml has '{manifest_version}'"
    )


def test_de_manual_markpublish_version_matches_manifest():
    manifest_version = get_manifest_version()
    yaml_path = ROOT / "docs" / "manual" / "de" / "markpublish.yaml"
    assert yaml_path.is_file(), f"markpublish.yaml not found: {yaml_path}"
    content = yaml_path.read_text(encoding="utf-8")

    match = re.search(r'version:\s*["\']?([0-9A-Za-z.\-_]+)["\']?', content)
    assert match is not None, "version not found in docs/manual/de/markpublish.yaml"
    yaml_version = match.group(1)
    assert yaml_version == manifest_version, (
        f"Version mismatch: docs/manual/de/markpublish.yaml has '{yaml_version}', "
        f"but blender_manifest.toml has '{manifest_version}'"
    )


def test_en_manual_markpublish_version_matches_manifest():
    manifest_version = get_manifest_version()
    yaml_path = ROOT / "docs" / "manual" / "en" / "markpublish.yaml"
    assert yaml_path.is_file(), f"markpublish.yaml not found: {yaml_path}"
    content = yaml_path.read_text(encoding="utf-8")

    match = re.search(r'version:\s*["\']?([0-9A-Za-z.\-_]+)["\']?', content)
    assert match is not None, "version not found in docs/manual/en/markpublish.yaml"
    yaml_version = match.group(1)
    assert yaml_version == manifest_version, (
        f"Version mismatch: docs/manual/en/markpublish.yaml has '{yaml_version}', "
        f"but blender_manifest.toml has '{manifest_version}'"
    )


def test_manual_pdfs_exist_and_valid():
    de_pdf = ROOT / "manual" / "low_poly_colorizer_de.pdf"
    en_pdf = ROOT / "manual" / "low_poly_colorizer_en.pdf"
    assert de_pdf.is_file(), f"German manual PDF missing: {de_pdf}"
    assert de_pdf.stat().st_size > 10000, "German manual PDF is empty or corrupt"
    assert en_pdf.is_file(), f"English manual PDF missing: {en_pdf}"
    assert en_pdf.stat().st_size > 10000, "English manual PDF is empty or corrupt"

