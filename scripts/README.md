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

# Set new version across all files (manifest, README, manual configs), test, compile, and build:
python scripts/build_dist.py --version 1.1.0

# Build extension ZIP only (skip tests and manual generation):
python scripts/build_dist.py --skip-tests --skip-manuals
```

---

## 2. `capture_screenshots.py` (Screenshot Automation)

Launches Blender in GUI mode with event simulation (`--enable-event-simulate`), captures all documentation screens, and renders precision Pillow annotations and numbered badges (①–⑥, Ⓐ–Ⓓ).

### Requirements
- Blender 4.2+ or 5.x installed and discoverable.
- Calibrated for 4K display resolution (3840×2160) with Blender maximized due to simulated UI coordinates.

### Usage

At least one target directory must be specified as a CLI argument:

```powershell
# Update both language manuals simultaneously:
python scripts/capture_screenshots.py docs/manual/de/images docs/manual/en/images

# Update only German manual directory:
python scripts/capture_screenshots.py docs/manual/de/images
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
