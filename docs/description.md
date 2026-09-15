Low Poly Colorizer (LPC) paints low-poly meshes with colors from a generated palette combined with PBR presets (roughness, metallic, emission, clearcoat). All painted faces share one material. Each face stores only two references in dedicated UV maps: its palette cell (`lpc_uv0`) and its preset (`lpc_uv1`).

## Key Features

- **Palette picker**: GPU overlay in the 3D Viewport with zoom and pan. Clicking a cell paints the selected faces (Edit Mode) or whole objects (Object Mode).
- **Generated palette**: Configurable grid of hues × brightness steps, optional greyscale column, adjustable saturation, brightness, tint and shade.
- **PBR presets**: Named presets for roughness, metallic, emission and clearcoat. Presets still in use cannot be deleted. Preset sets can be imported and exported as JSON.
- **One shared material**: No material slot per color. Palette and presets live in two small textures, so changing the palette or a preset updates every painted face immediately without rewriting mesh data.
- **Tools**: Assign, Sample (load color + preset of the selected faces), Select/Deselect faces with the same color and preset, Fix UV Maps after joins, booleans or imports.
- **Geometry Nodes**: The `LPC Set Material` node group sets palette cell and preset procedurally.

**Manual:** [English (PDF)](https://github.com/wasdcat/low-poly-colorizer/blob/main/manual/low_poly_colorizer_en.pdf) · [Deutsch (PDF)](https://github.com/wasdcat/low-poly-colorizer/blob/main/manual/low_poly_colorizer_de.pdf) · Online: [en](https://github.com/wasdcat/low-poly-colorizer/tree/main/docs/manual/en) · [de](https://github.com/wasdcat/low-poly-colorizer/tree/main/docs/manual/de)

## Godot 4 Pipeline

LPC does not export geometry. Models go to Godot as usual (`.blend` or glTF), and the per-face data travels in the first two UV maps (UV/UV2 in Godot). All painted faces of a mesh import as a single surface. **Export** writes the matching material package into a folder of your choice:

- `lpc_palette.png`, `lpc_preset_lut.png`: palette and preset data textures
- `lpc_multicolor` shader + material: for painted meshes, reads color and preset per face
- `lpc_singlecolor` shader + material: for any other mesh, one palette color + preset per `MeshInstance3D` via instance uniforms on a single shared material
- `lpc_singlecolor_resource.gd`: resource class for reusable named looks, with a generated `Preset` enum
- `README.md`: the texture import settings Godot needs

The Export button turns red when the exported files are out of date.

The export is template-based: a target is a set of `.tpl` text templates filled with the scene's palette and preset data. Godot 4 is the bundled template set; other engines can be added as further template sets without changes to the exporter.

## Quick Start

1. In the 3D Viewport, press `N` and open the **LPC** tab.
2. Select faces (Edit Mode) or objects (Object Mode) and a preset in the list.
3. Click the palette button and pick a cell.
4. Click **Export** and choose a folder inside your Godot project.

## Demo Project

[low-poly-colorizer-demo](https://github.com/wasdcat/low-poly-colorizer-demo) is a small playable puzzle cube game for Godot 4.8 built on the exported LPC files. Every body and sticker of the cube shares the `lpc_singlecolor` material, and color schemes and material presets can be switched while playing. Ready-to-run builds for Windows, Linux and macOS are available on its releases page.
