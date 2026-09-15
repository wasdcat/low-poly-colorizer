# Low Poly Colorizer — User Manual

This directory contains the official **User Manual for Low Poly Colorizer (LPC)** in English. It is aimed at 3D artists, game developers, and technical artists who want to efficiently colorize 3D models in Blender and export prepared materials and shaders to game engines like Godot 4.

---

## Table of Contents

- [Foreword](00_foreword.md)
1. [Installation and Quickstart](01_installation_and_quickstart.md)
2. [The User Interface](02_the_user_interface.md)
3. [Color Palette and PBR Presets](03_color_palette_and_presets.md)
4. [Engine Export and Integration](04_engine_export_and_integration.md)

---

## Screenshot & Asset Automation

The screenshots and annotations used throughout this manual can be automatically generated, cropped, and annotated directly from Blender:

```powershell
python scripts/capture_screenshots.py docs/manual/de/images docs/manual/en/images
```

---

## PDF Generation with markpublish

This manual is compiled into PDF using [markpublish](https://github.com/fwdotcom/markpublish):

```powershell
# Compile individually:
markpublish build docs/manual/en/markpublish.yaml -o manual/low_poly_colorizer_en.pdf

# Or execute complete test and release build:
python scripts/build_dist.py
```

The compiled PDF document will be output to `manual/low_poly_colorizer_en.pdf`.

