# Licensing

Low Poly Colorizer is split into two parts with different licenses:

| Part | What it covers | License | File |
|------|----------------|---------|------|
| **Add-on** | The Blender add-on itself (all Python source under `addon/`, the panel/operators/model). | **GPL-3.0-or-later** | [addon/LICENSE](addon/LICENSE) |
| **Exported engine templates** | The output the add-on writes per target — e.g. the Godot `lpc_multicolor.gdshader` + `lpc_multicolor.tres`, generated from the templates in `addon/export/<target>/` (currently `addon/export/godot/`). | **MIT** | [addon/export/godot/LICENSE](addon/export/godot/LICENSE) |

The add-on is GPL so it stays free software. The exported shader/material
templates are MIT so the files you ship inside your own Godot project carry no
copyleft obligation — you can use them in any project, open or closed.