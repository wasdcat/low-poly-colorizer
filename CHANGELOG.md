# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2026-11-27

### Added
- **Stride export, experimental** (*Stride Materials (experimental)*, multicolor only): writes `lpc_multicolor.sdmat` plus `lpc_palette.sdtex` / `lpc_preset_lut.sdtex` texture assets next to the two PNGs, a `README.md` and the palette cheatsheet. The material uses Stride's stock texture nodes (point filtering, palette from `TEXCOORD0`, preset LUT from `TEXCOORD1`) for diffuse, roughness, metalness and emission — no custom shader. The texture assets switch off compression, mipmaps and premultiplied alpha, and sample the palette as sRGB and the LUT as raw data. Every asset carries a stable GUID derived from its file name. Stride's stock material has no clearcoat amount per face, so the preset's clearcoat is approximated: the exported LUT's roughness channel is pulled toward the *Clearcoat Roughness* by the clearcoat amount (one highlight instead of a coat on top of the base; the README explains it). Not yet supported: the singlecolor variant.

### Changed
- **Export targets are configured entirely in the registry**: the stable-ID format (`id_format`: Godot `uid://…` or GUID) and the sidecar suffixes (`sidecar_suffixes`) are fields of a template set instead of Godot constants in the exporter. A new engine is a template folder plus a registry entry, and a new ID format is one function in `ID_FORMATS`. The Godot export is byte-identical.
- The export button shows as out of date once after the update (the render context gained the preset LUT addressing used by Stride).

## [2.0.2] - 2026-11-18

### Added
- **Template *Industrial Planet***: 25 × 7 colors for a stylized sci-fi industrial world on a barren planet — groups *Neutral* (grey, steel, concrete; darker range for rubber), *Terrain* (basalt, rock, oxide, dust, ochre, lichen), *Snow & Ice* (own light range), *Industry* (hazard, safety, signal, cobalt, teal, copper, brass) and *Energy* (glow colors Volt, Sodium, Plasma, Neon, Acid, Ion with their own range for emission).
- **Template *Toon Outdoor***: 26 × 5 natural colors for toon / low-poly outdoor scenes — groups *Ground* (soil, clay, path, sand, rock, stone), *Foliage* (meadow, grass, leaf, moss, pine, sage), *Autumn*, *Wood*, *Water & Sky* (own lighter range: sky, water, lake, snow) and *Flowers*. Low tint / shade keep color in highlights and shadows, hue shift gives warm lights and cool shadows.
- **Palette cheatsheet**: the Godot export also writes `lpc_palette_cheatsheet.png` — a title line with the palette's name and "created with Low Poly Colorizer", then the palette grid as in the picker, with group names, row numbers and every column's name written vertically below it. Its `.import` file tells Godot to skip it (not imported, not exported with the game).

### Fixed
- **Color space**: palette colors are computed as sRGB but were handled as linear values — in the Blender preview material (Non-Color palette image) and in the Godot shaders (palette sampler without `source_color`). Painted faces therefore rendered too light and washed out in both. The palette image is now an 8-bit *sRGB* image, and `lpc_palette_tex` in `lpc_common.gdshaderinc` carries `source_color`. Faces now show the colors of the picker.
- **Color swatches** in the panel, the Settings dialog and *Remap Painted Faces* show the true palette colors (no longer brightened by the view transform).

### Changed
- **Palette name**: the palette keeps the name of its template or imported LPC file, editable in the *Palette* box of the Settings dialog and written into exported LPC files. Renaming marks the export as out of date (the name is the cheatsheet title).
- **Panel**: the picked cell is shown as a drop-down of the column names ("Nature · Moss") plus the row number, instead of X / Y numbers.
- **Palettes retuned for the corrected color space** — no template has black or white albedo any more (every cell roughly 40–245 in 8-bit sRGB):
  - Defaults: *Rows* 5 → 7, *Lightest* 0.93 → 0.90, *Darkest* 0.25 → 0.33, *Tint* 0.8 → 0.5.
  - *Stylized 3D*: 21 × 7 instead of 22 × 5 — 7 rows for subtler steps (lightness step 0.10 instead of 0.15), less tint so light tones keep their hue, *Nature* chroma +25 % for readability at a distance, *Grey* one column instead of span 2, with the *Neutral* group's own darker range 0.95 → 0.28 (rubber, dark metal).
  - *Classic Color Wheel*: hues 0.93 → 0.32 (was 0.94 → 0.22); the grey scale 0.97 → 0.28 instead of pure white → pure black.
- **Settings dialog** sorted top-down: one *Palette* box (rows, *Lightest* / *Darkest*, tint / shade, hue shift / warmth), then *Groups*, then *Columns of …*; the former *Globals* box is now *Material (all presets)* at the bottom.
- **Column list** shows the first, middle and last color of each column (whole ramp for span 2) instead of only the middle one; the "x2" span marker is gone.

### Removed
- **LPC 1.x compatibility**: files saved with LPC 1.x are no longer converted (no palette conversion, no "converted from LPC 1.x" notice and *Dismiss* button), and preset files of LPC 1.x (`version: 1`) are no longer read. The Godot README no longer covers UIDs of exports before 1.2. Migrating old projects is left to a separate tool.

### Upgrade notes
- Painted meshes look **darker and more saturated** than before, in Blender and in Godot — as the palette always looked in the picker. If you tuned palette values against the old preview, check them again.
- Files from earlier versions are **not** converted (their palette image stays a Non-Color float image) — start from a new file. Re-export to Godot to get the updated shader include.

## [2.0.1] - 2026-11-17

### Changed
- **Geometry Nodes**: in the `LPC Set Material` node group, *Palette Cell X* is now a drop-down of the column names ("Nature · Moss"), like `palette_cell_x` in the Godot `lpc_palette_color_resource.gd`; internally it still resolves to the column number. After palette changes the items are renamed in place, so a modifier keeps its column number. Duplicate column names get " (2)", " (3)" in the menu.
- **Godot export**: the instance shader parameters of `lpc_singlecolor.gdshader` are Inspector drop-downs (`hint_enum`): `lpc_palette_cell_x` lists the column names (the same list as `palette_cell_x` of the resource scripts), `lpc_preset_position` the preset names. What is stored are still the numbers (column, list position).

### Upgrade notes
- The exported Godot files now need **Godot 4.4 or newer** (`hint_enum` in `lpc_singlecolor.gdshader`). Instance parameter values already set on `MeshInstance3D`s are kept — they are the same numbers.
- An existing `lpc_set_material` node group is rebuilt automatically when the file is opened (or the add-on is enabled). Modifiers keep their *Selection* and *Palette Cell Y* values; because *Palette Cell X* changes from a number to a menu, it falls back to the first column — set it again from the drop-down.

## [2.0.0] - 2026-11-17

LPC 2.0 replaces the fixed color wheel with a palette of **groups and columns**. Files from 1.x are converted on load with the same grid, so painted faces keep their cells — but colors may change (see *Upgrade notes*).

### Added
- **Palette of groups and columns**: groups (heading in the picker, chroma default, optional own lightness range) of columns (hue, optional own chroma, span 1 or 2 for long ramps such as a 10-step grey scale), all computed in OKLCH. Global values: rows, lightness range (*Lightest* / *Darkest*), tint, shade, hue shift, warmth.
- **Settings dialog** rebuilt around the palette: group list and column list with color previews, add / remove / reorder (a column moved past the end of its group continues in the neighboring group).
- **Templates**: *Stylized 3D* (22 × 5, groups Neutral / Nature / Accent — the default for new files) and *Classic Color Wheel* (1.x default layout). Templates are JSON files in `addon/templates/`.
- **Painted faces follow palette changes**: on *OK*, faces are remapped by stable column ids — adding, moving and widening columns and reordering groups are lossless. Deleting a used column, changing the row count or narrowing a column opens **Remap Painted Faces**: one row per affected color with its face count and the nearest new color (OKLab) as suggestion, correctable via X/Y; *Cancel* restores the previous palette. The picked brush cell moves along.
- **Picker**: gaps and headings between groups, the hovered cell's name below the grid (e.g. *Nature · Moss 3*), fine lines between cells.
- **LPC file format `version: 2`**: one JSON file with `palette` and/or `presets`. *Import / Export Palette / Presets* (preset menu) with checkboxes for both parts. An imported palette replaces the current one and runs through the same remap. Preset files of 1.x (`version: 1`) are still read.
- **Godot export**: `PALETTE_GROUPS` (name, first column, count) and `PALETTE_COLUMN_NAMES` in `lpc_palette_color_resource.gd`; `palette_cell_x` is an Inspector drop-down of the column names ("Nature · Moss"), still saved as a number.

### Changed
- One color model: OKLCH. Lightness steps are even in perceived lightness; tint and shade now reduce chroma toward the lightest / darkest rows instead of mixing in white / black.

### Removed
- *Columns*, *Add Greyscale Column*, *Saturation*, *Brightness* and the *Color Mode* switch (HSV / OKLCH). Their roles are taken by groups, columns, chroma and the lightness range.
- Exported constants `PALETTE_HAS_GREYSCALE`, `PALETTE_SATURATION`, `PALETTE_BRIGHTNESS`, `PALETTE_COLOR_MODE`.
- The preset-only *Import / Export JSON* entries (replaced by *Import / Export Palette / Presets*).

### Upgrade notes
- **Opening a 1.x file** converts its palette once: the greyscale column becomes the group *Greyscale* (white to black), the color wheel the group *Color Wheel* with the same hues, *Saturation* its chroma, *Brightness* its lightness range. Same grid size, every painted face keeps its cell. A note in the N-Panel and the Settings dialog says so until dismissed.
- **Colors may change**: palettes in the former default mode *HSV* look visibly different; *OKLCH* palettes stay practically the same in their hue columns. If you need the old colors exactly, stay on 1.2 for that project.
- **Godot**: re-export after upgrading. Saved `palette_cell_x` values keep their numbers; after adding, removing or reordering columns they name a different column — painted meshes are remapped by the add-on, `.tres` files are not.

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

