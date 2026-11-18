# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Local build & distribution pipeline for Low Poly Colorizer.

Workflow:
1. (Optional) Bumps version across manifest, README, and manual configs (--version <X.Y.Z>)
   and turns the CHANGELOG's [Unreleased] section into the release section.
2. Executes unit tests and version consistency checks (pytest).
3. Generates user manuals (German and English) directly into /manual (git-tracked).
4. Packages the Blender 4.2+ extension into dist/{id}-{version}.zip for local testing.

Usage:
    python scripts/build_dist.py                     # Build with current version
    python scripts/build_dist.py --version 1.1.0     # Set version everywhere, test, render, build
    python scripts/build_dist.py --skip-tests        # Skip pytest
    python scripts/build_dist.py --skip-manuals      # Skip markpublish compilation
"""

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADDON_DIR = ROOT / "addon"
DIST_DIR = ROOT / "dist"
MANUAL_DIR = ROOT / "manual"
MANIFEST_PATH = ADDON_DIR / "blender_manifest.toml"


def read_manifest():
    with MANIFEST_PATH.open("rb") as f:
        return tomllib.load(f)


def read_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            branch = result.stdout.strip()
            # Detached HEAD (CI checkouts of a release tag or PR merge ref) has
            # no branch name -- treat it like main, so no second "-HEAD" copy
            # lands next to the release ZIP in dist/.
            if branch == "HEAD":
                return "main"
            return re.sub(r"[^A-Za-z0-9._-]+", "-", branch)
    except Exception:
        pass
    return "main"


def bump_version(new_version: str):
    clean_version = new_version.lstrip("v")
    if not re.match(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$", clean_version):
        print(
            f"ERROR: Invalid version format '{new_version}'. Expected semantic version (e.g. '1.1.0').",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check the CHANGELOG first: without documented changes nothing is touched.
    changelog_file = ROOT / "CHANGELOG.md"
    if not changelog_file.is_file():
        print(f"ERROR: {changelog_file.relative_to(ROOT)} not found.", file=sys.stderr)
        sys.exit(1)
    raw = changelog_file.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    changelog, cl_status = release_changelog(raw.replace("\r\n", "\n"), clean_version,
                                             date.today().isoformat())
    if cl_status in ("missing", "empty"):
        reason = ("has no [Unreleased] section" if cl_status == "missing"
                  else "has an empty [Unreleased] section")
        print(
            f"ERROR: {changelog_file.relative_to(ROOT)} {reason}. Document the changes for "
            f"{clean_version} under '## [Unreleased]' first. Nothing was changed.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\n--- Setting Project Version to {clean_version} ---")

    # 1. addon/blender_manifest.toml
    manifest_file = ROOT / "addon" / "blender_manifest.toml"
    content = manifest_file.read_text(encoding="utf-8")
    content = re.sub(r'(?m)^version\s*=\s*"[^"]*"', f'version = "{clean_version}"', content)
    manifest_file.write_text(content, encoding="utf-8")
    print(f"  [OK] Updated {manifest_file.relative_to(ROOT)}")

    # 2. README.md
    readme_file = ROOT / "README.md"
    content = readme_file.read_text(encoding="utf-8")
    content = re.sub(
        r'img\.shields\.io/badge/version-[0-9A-Za-z.\-_]+-blue',
        f'img.shields.io/badge/version-{clean_version}-blue',
        content,
    )
    content = re.sub(
        r'low_poly_colorizer-[0-9A-Za-z.\-_]+\.zip',
        f'low_poly_colorizer-{clean_version}.zip',
        content,
    )
    readme_file.write_text(content, encoding="utf-8")
    print(f"  [OK] Updated {readme_file.relative_to(ROOT)}")

    # 3. docs/manual/de/markpublish.yaml
    de_yaml = ROOT / "docs" / "manual" / "de" / "markpublish.yaml"
    content = de_yaml.read_text(encoding="utf-8")
    content = re.sub(r'(?m)^\s*version:\s*"[^"]*"', f'  version: "{clean_version}"', content)
    de_yaml.write_text(content, encoding="utf-8")
    print(f"  [OK] Updated {de_yaml.relative_to(ROOT)}")

    # 4. docs/manual/en/markpublish.yaml
    en_yaml = ROOT / "docs" / "manual" / "en" / "markpublish.yaml"
    content = en_yaml.read_text(encoding="utf-8")
    content = re.sub(r'(?m)^\s*version:\s*"[^"]*"', f'  version: "{clean_version}"', content)
    en_yaml.write_text(content, encoding="utf-8")
    print(f"  [OK] Updated {en_yaml.relative_to(ROOT)}")

    # 5. CHANGELOG.md: the [Unreleased] section becomes the release
    if cl_status == "released":
        changelog_file.write_bytes(changelog.replace("\n", newline).encode("utf-8"))
        print(f"  [OK] Updated {changelog_file.relative_to(ROOT)}: "
              f"[Unreleased] -> [{clean_version}], new empty [Unreleased]")
    else:  # "exists": a repeated bump to the same version
        print(f"  [OK] {changelog_file.relative_to(ROOT)} already has [{clean_version}]")

    print(f"[OK] Version set to {clean_version} across all files.\n")


def release_changelog(text: str, version: str, day: str):
    """Turn the `## [Unreleased]` section of a Keep-a-Changelog `text` into
    `## [<version>] - <day>` and put a new, empty `## [Unreleased]` above it.

    Returns (text, status): "released" (changed), "exists" (a section for
    `version` is already there -- unchanged, so a repeated bump is a no-op),
    "missing" (no [Unreleased] section) or "empty" (an [Unreleased] section
    without content) -- both unchanged; the caller aborts on them."""
    if re.search(rf"(?m)^## \[{re.escape(version)}\]", text):
        return text, "exists"
    match = re.search(r"(?m)^## \[Unreleased\][^\n]*$", text)
    if match is None:
        return text, "missing"
    following = re.search(r"(?m)^## \[", text[match.end():])
    body = text[match.end():match.end() + following.start()] if following else text[match.end():]
    if not body.strip():
        return text, "empty"
    released = f"## [Unreleased]\n\n## [{version}] - {day}"
    return text[:match.start()] + released + text[match.end():], "released"


def run_tests():
    print("\n--- 1/3: Running Test Suite & Version Checks ---")
    result = subprocess.run([sys.executable, "-m", "pytest", "-v"], cwd=ROOT)
    if result.returncode != 0:
        print("\nERROR: Tests failed! Aborting build.", file=sys.stderr)
        sys.exit(result.returncode)
    print("[OK] All tests passed successfully.")


def build_manuals():
    print("\n--- 2/3: Generating User Manuals into /manual ---")
    MANUAL_DIR.mkdir(exist_ok=True)
    markpublish_bin = shutil.which("markpublish")

    if not markpublish_bin:
        print("NOTE: 'markpublish' executable not found in PATH.")
        de_pdf = MANUAL_DIR / "low_poly_colorizer_de.pdf"
        en_pdf = MANUAL_DIR / "low_poly_colorizer_en.pdf"
        if de_pdf.is_file() and en_pdf.is_file():
            print("[OK] Found existing pre-compiled manuals in manual/.")
            return
        else:
            print("ERROR: markpublish not found and manual PDFs missing in manual/!", file=sys.stderr)
            sys.exit(1)

    de_cfg = ROOT / "docs" / "manual" / "de" / "markpublish.yaml"
    de_out = MANUAL_DIR / "low_poly_colorizer_de.pdf"
    print(f"Compiling German manual -> {de_out}...")
    res_de = subprocess.run([markpublish_bin, "build", str(de_cfg), "-o", str(de_out)], cwd=ROOT)
    if res_de.returncode != 0:
        print("ERROR: Failed to compile German manual!", file=sys.stderr)
        sys.exit(res_de.returncode)

    en_cfg = ROOT / "docs" / "manual" / "en" / "markpublish.yaml"
    en_out = MANUAL_DIR / "low_poly_colorizer_en.pdf"
    print(f"Compiling English manual -> {en_out}...")
    res_en = subprocess.run([markpublish_bin, "build", str(en_cfg), "-o", str(en_out)], cwd=ROOT)
    if res_en.returncode != 0:
        print("ERROR: Failed to compile English manual!", file=sys.stderr)
        sys.exit(res_en.returncode)

    print("[OK] Both manuals generated into manual/.")


def build_extension(version: str, module_name: str, branch: str) -> Path:
    print("\n--- 3/3: Packaging Blender Extension into dist/ (local use) ---")
    DIST_DIR.mkdir(exist_ok=True)

    zip_name = f"{module_name}-{version}.zip"
    zip_path = DIST_DIR / zip_name
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ADDON_DIR.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue
            arcname = path.relative_to(ADDON_DIR)
            zf.write(path, arcname)

    print(f"created: {zip_path}")

    if branch and branch != "main":
        branch_zip = DIST_DIR / f"{module_name}-{version}-{branch}.zip"
        if branch_zip.exists():
            branch_zip.unlink()
        shutil.copy2(zip_path, branch_zip)
        print(f"created: {branch_zip}")

    print("[OK] Extension package built for local use.")
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Build pipeline for Low Poly Colorizer.")
    parser.add_argument(
        "-v",
        "--version",
        "--bump-version",
        dest="bump_version",
        help="Set new version (e.g. '1.0.0' or '1.1.0') across all manifest, README, and manual config files before building.",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest test execution.")
    parser.add_argument("--skip-manuals", action="store_true", help="Skip compiling user manuals with markpublish.")
    args = parser.parse_args()

    if args.bump_version:
        bump_version(args.bump_version)

    manifest = read_manifest()
    version = manifest["version"]
    module_name = manifest["id"]
    branch = read_branch()

    print(f"=== Low Poly Colorizer Build (v{version} on {branch}) ===")

    if not args.skip_tests:
        run_tests()
    else:
        print("\n--- Skipping tests as requested ---")

    if not args.skip_manuals:
        build_manuals()
    else:
        print("\n--- Skipping manual generation as requested ---")

    build_extension(version, module_name, branch)
    print(f"\n[DONE] Build completed successfully for v{version}.")


if __name__ == "__main__":
    main()
