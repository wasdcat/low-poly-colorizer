# Developer Scripts

This directory contains automation, testing, and release build scripts for **Low Poly Colorizer**.

---

## 1. `build_dist.py` (Main Build Pipeline)

Executes the complete distribution build and validation cycle:
1. **Tests:** Runs the `pytest` suite (including cross-project version consistency checks).
2. **User Manuals:** Compiles both German and English PDF manuals via `markpublish` into `/manual/`.
3. **Extension Package:** Packages the official Blender 4.2+ extension archive `dist/low_poly_colorizer-<version>.zip`.

### Usage

```powershell
# Standard build with current version:
python scripts/build_dist.py

# Set new version across all files (manifest, README, manual configs), turn the CHANGELOG's
# [Unreleased] section into [1.1.0] - <today> (with a new empty [Unreleased] above), test, compile, and build.
# Aborts before changing anything if the CHANGELOG has no [Unreleased] section or an empty one
# (a repeated run with the same version is fine):
python scripts/build_dist.py --version 1.1.0

# Build extension ZIP only (skip tests and manual generation):
python scripts/build_dist.py --skip-tests --skip-manuals
```

---

## 2. `capture_screenshots.py` (Screenshot Automation)

Launches Blender in GUI mode with event simulation (`--enable-event-simulate`), captures all documentation screens, and renders precision Pillow annotations and numbered badges (N-Panel ①–⑥, Settings ①–④, Picker Ⓐ–Ⓓ).

### Requirements
- Blender 4.2+ or 5.x installed and discoverable.
- The N-Panel crop and the LPC tab click use fixed coordinates, calibrated for a maximized Blender window of 5120×1351 px (the picker and Settings crops adapt to any size).
- It drives the **installed** extension, not the repository code — install the current build first.

### Usage

Screenshots are saved to `docs/manual/common/images` by default:

```powershell
# Standard capture to common images directory:
python scripts/capture_screenshots.py

# Or specify custom target directories:
python scripts/capture_screenshots.py docs/manual/common/images
```

---

## 3. `validate_manifest.py` (Manifest & Package Verification)

Validates `addon/blender_manifest.toml` for compliance with the official Blender 4.2+ Extension specification and checks the internal archive layout of built ZIP files.

### Usage

```powershell
# Validate syntax and required fields in manifest:
python scripts/validate_manifest.py

# Verify that a Git tag matches the manifest version (used in CI):
python scripts/validate_manifest.py --check-tag v1.0.0

# Verify that a built ZIP contains blender_manifest.toml at archive root:
python scripts/validate_manifest.py --check-zip dist/low_poly_colorizer-1.0.0.zip
```
