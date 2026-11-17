# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Export template-set registry (the export "config").

One entry per export target ("template set"): a human label shown in the
export dropdown mapped to a folder of `.tpl` files under `addon/export/`.
Godot is just one target -- supporting another engine means adding a template
folder plus an entry here IN THE SOURCE REPOSITORY, shipped as a new add-on
version. This is not a runtime extension point: the installed add-on directory
is owned by Blender and is never written to, neither by the add-on nor by the
user.

The exporter (exporter.py) renders EVERY `.tpl` in the chosen set's folder
into the chosen output directory, substituting the scene's material
parameters (build_context). Each template uses whatever placeholders it needs.
"""

import os

# id          stable key, stored in the scene's lpc_export_target enum
# label       shown in the dropdown
# dir         folder under export/ holding this set's .tpl files
# description tooltip
#
# How the palette and the presets reach the target -- per set, because the
# right form depends on the engine and on the data's size, not on the user:
# palette_texture  optional, default True: write the palette as a PNG
#                  (exporter.PALETTE_IMAGE_FILENAME). Off means the templates
#                  take it as text instead (palette_colors_* placeholders).
# preset_texture   optional, default True: write the preset LUT as a PNG
#                  (exporter.PRESET_LUT_IMAGE_FILENAME). Off means the
#                  templates take the presets as text instead
#                  (preset_values_* placeholders).
# The text placeholders are always in the render context, whatever the flags
# say -- a flag only decides whether the PNG is written as well.
TEMPLATE_SETS = (
    {
        "id": "godot",
        "label": "Godot Materials",
        "dir": "godot",
        "description": "Godot 4 spatial shader + ShaderMaterial (.tres)",
        # Palette: a texture. It can hold thousands of cells, which as a
        # constant shader array would not compile on the Compatibility
        # renderer (OpenGL) and costs compile time everywhere; the import
        # settings it needs travel in a generated .import file.
        "palette_texture": True,
        # Presets: a texture too (the LUT). A constant shader array was
        # measured as well (Godot 4.8, Vulkan + OpenGL): never faster, up to
        # ~2.5x slower when neighboring pixels use different presets, and
        # noticeably slower on the Compatibility renderer. Its one gain --
        # exact instead of 8-bit values -- is invisible for these
        # parameters, and the LUT's import pitfall (Fix Alpha Border) is
        # handled by the generated .import file.
        "preset_texture": True,
    },
)

_BASE = os.path.dirname(__file__)


def get(set_id):
    """The set entry for `set_id`, or None."""
    for entry in TEMPLATE_SETS:
        if entry["id"] == set_id:
            return entry
    return None


def template_dir(set_id):
    """Absolute path of the set's template folder, or None for an unknown id."""
    entry = get(set_id)
    return os.path.join(_BASE, entry["dir"]) if entry is not None else None


def writes_palette_texture(set_id):
    """Whether exporting `set_id` writes the palette PNG (default True)."""
    entry = get(set_id)
    return entry is not None and bool(entry.get("palette_texture", True))


def writes_preset_texture(set_id):
    """Whether exporting `set_id` writes the preset LUT PNG (default True)."""
    entry = get(set_id)
    return entry is not None and bool(entry.get("preset_texture", True))


def enum_items():
    """`(id, label, description)` tuples for an EnumProperty. Kept alive by the
    caller (Blender does not copy enum item strings)."""
    return [
        (e["id"], e["label"], e.get("description", "")) for e in TEMPLATE_SETS
    ]

