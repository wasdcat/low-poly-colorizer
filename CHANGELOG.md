# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-11-17

### Added
- **`lpc_palette_color_resource.gd`** (`LpcPaletteColorResource`): new exported GDScript resource holding a plain palette color -- only the palette cell (`palette_cell_x` / `palette_cell_y`), no preset, no emission -- for decals, labels, UI and lights. Provides `get_color()`, the static `color_at(x, y)`, the `PALETTE_*` parameter constants and the precomputed `PALETTE` array. Unlike a fixed `Color`, it follows palette changes on re-export. A read-only `color` field shows the cell's color in the inspector (always `get_color()`, never saved), so you see the color and not just the cell numbers.
- **Generated `.import` files** for `lpc_palette.png` and `lpc_preset_lut.png`: Godot imports both data textures correctly right away (lossless, no VRAM compression, no mipmaps, Fix Alpha Border off). Every export restores these settings.
- **Stable UIDs** for every exported file (`.uid` files for scripts and shaders, `uid=` in the `.import` files and `.tres` headers), derived deterministically from the output filename (`exporter.stable_uid`). Re-exports, fresh checkouts and other machines always produce the same UIDs, so references by UID keep resolving. The materials now reference their shader and textures by UID as well as by path.
- Export registry: per-target flags `palette_texture` / `preset_texture` decide which data textures a template set ships; the palette (`palette_colors_gdscript`) and the presets (`preset_values_glsl`) are additionally available to templates as text.

### Changed
- `LpcSinglecolorResource` now **extends** `LpcPaletteColorResource` and only adds `preset`, `emission_override` and `apply_to()`. Exports typed as the palette color accept full looks as well. Existing look `.tres` files keep working unchanged (same property names).
- The exported `README.md` no longer walks through manual texture import settings.

### Fixed
- `color_at()` / `get_color()` in the exported GDScript ignored the Artwork settings: they recomputed colors with the plain HSV formula, so with `OKLCH`, Hue Shift or Warmth the returned color differed from what the shaders render. They now read the `PALETTE` array written from the add-on's own `color_at`, so script and shader agree in every color mode.

### Upgrade notes
- Projects using an export from before 1.2 reference the exported files by the random UIDs Godot assigned back then. After the first 1.2 export, Godot falls back to the file path and warns once per reference; re-save the referencing files or replace the old UIDs project-wide. From then on the UIDs never change.

## [1.1.0] - 2026-11-17

### Added
- **Artwork Settings**: New configuration section in the Settings dialog (`LPC_OT_palette_settings`) for color theory and stylized shading:
  - **Color Mode**: Switch between standard `HSV` (classic, 100% backward-compatible) and perceptually uniform `OKLCH` (balanced perceived lightness across all hues, preventing washed-out yellows and muddy darks).
  - **Hue Shift**: Temperature drift across the vertical shading ramp (-1.0 to 1.0). Positive values shift highlights toward warm sunlight (yellow/amber) and shadows toward cool skylight (blue/violet); negative values invert the direction (moonlight / sci-fi styling).
  - **Warmth**: Global color temperature bias (-1.0 to 1.0) shifting the palette and greyscale column toward warm amber or cool blue.
- Live viewport and material preview updates when adjusting Artwork parameters.
- Extended engine export context and dirty-state detection for Artwork parameters (`palette_color_mode`, `palette_hue_shift`, `palette_warmth`).
- Comprehensive unit tests covering OKLCH conversion, hue shift, warmth bias, and backward compatibility.

## [1.0.2] - 2026-11-11

### Changed
- Replaced inferred types (`:=`) with explicit static type annotations (`: Type =`) in `color_at()` within `singlecolor_resource.gd.tpl` to comply with strict GDScript typing.

## [1.0.1] - 2026-09-12

### Changed
- **Manifest tags** reduced to `Material` and `Import-Export`, following review
  feedback from the Blender Extensions Platform.
- Clarified in `addon/export/registry.py` that further export template sets are
  added in the source repository and shipped as a new add-on version -- the
  installed add-on directory is owned by Blender and is never written to.

## [1.0.0] - 2026-09-11

### Added
- **Interactive Palette Picker**: GPU overlay in the Blender 3D Viewport with zoom and pan; clicking a cell paints the selection immediately.
- **Single-Material Architecture**: All painted faces share one material. Each face references its palette cell and PBR preset via two UV channels – one surface per mesh instead of one material per color.
- **PBR Preset Management**: Named presets for roughness, metallic, emission, and clearcoat with reference-count protection and JSON import/export.
- **Painting Tools**: Assign, Sample, Select/Deselect by color and preset, and Fix UV Maps.
- **Geometry Nodes Integration**: `LPC Set Material` node group to set palette cell and preset procedurally in Geometry Nodes modifiers.
- **Engine Export**: Template-based export for Godot 4.x (shaders, materials, palette and preset textures, GDScript look resource); the Export button turns red when the export is out of date. Further engines can be added as template sets.
- **User Documentation**: User manuals in English and German (`manual/`).

