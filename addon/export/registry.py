# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Export template-set registry (the export "config").

One entry per export target ("template set"): a human label shown in the
export dropdown mapped to a folder of `.tpl` files under `addon/export/`.
Godot and Stride are just two targets -- supporting another engine means adding a template
folder plus an entry here IN THE SOURCE REPOSITORY, shipped as a new add-on
version. This is not a runtime extension point: the installed add-on directory
is owned by Blender and is never written to, neither by the add-on nor by the
user.

The exporter (exporter.py) renders EVERY `.tpl` in the chosen set's folder
into the chosen output directory, substituting the scene's material
parameters (build_context). Each template uses whatever placeholders it needs.

Everything engine-specific the exporter itself has to know -- how a stable
file ID is spelled, which files are sidecars describing another file, which
PNGs to write -- is a field of the set's entry here, never a branch on the
set's id in exporter.py.
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
# cheatsheet       optional, default False: also write the palette as a
#                  labeled PNG for people (exporter.CHEATSHEET_FILENAME,
#                  export/cheatsheet.py) -- not read by any template.
#
# Stable file IDs (exporter.uid_context), per set because every engine spells
# them differently:
# id_format        optional, default None: a key of exporter.ID_FORMATS
#                  ("godot_uid" -> uid://..., "guid" -> 8-4-4-4-12 GUID).
#                  Set, the render context gets one `uid_<name>` placeholder
#                  per exported file, derived from its output filename only.
#                  None means the set uses no IDs (no uid_* placeholders).
# sidecar_suffixes optional, default (): output-name suffixes that mark a
#                  file describing ANOTHER file (Godot: "x.png.import",
#                  "x.gd.uid"). A sidecar carries its subject's ID instead of
#                  its own -- which is how a PNG written by write_textures,
#                  outside the template mechanism, gets an ID.
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
        # Cheatsheet: a labeled palette PNG to look things up; its .import
        # sidecar ("skip") keeps Godot from importing or exporting it.
        "cheatsheet": True,
        # ResourceUID text form; a texture's ID lives in its .import file,
        # a script's / shader's in its .uid file.
        "id_format": "godot_uid",
        "sidecar_suffixes": (".import", ".uid"),
    },
    {
        "id": "stride",
        "label": "Stride Materials",
        "dir": "stride",
        "description": "Stride 4 material (.sdmat) + texture assets (.sdtex), multicolor only",
        # Both data textures, read by stock material nodes (Texture color /
        # Texture scalar with point filtering) -- no custom shader, so the
        # material compiles in Game Studio like any hand-made one. Each PNG
        # gets a .sdtex asset template that sets sRGB / premultiply / mips.
        "palette_texture": True,
        "preset_texture": True,
        # Nothing reads it; it sits next to the assets for people.
        "cheatsheet": True,
        # Stride assets carry a GUID (`Id:`) and reference each other as
        # `guid:url`. The .sdtex IS the asset (it points at its PNG via
        # `Source:`), so it carries its own ID -- no sidecars.
        "id_format": "guid",
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


def writes_cheatsheet(set_id):
    """Whether exporting `set_id` writes the palette cheatsheet PNG
    (default False)."""
    entry = get(set_id)
    return entry is not None and bool(entry.get("cheatsheet", False))


def id_format(set_id):
    """The set's stable-ID format (a key of exporter.ID_FORMATS), or None."""
    entry = get(set_id)
    return entry.get("id_format") if entry is not None else None


def sidecar_suffixes(set_id):
    """The set's sidecar output-name suffixes (default: none)."""
    entry = get(set_id)
    return tuple(entry.get("sidecar_suffixes", ())) if entry is not None else ()


def enum_items():
    """`(id, label, description)` tuples for an EnumProperty. Kept alive by the
    caller (Blender does not copy enum item strings)."""
    return [
        (e["id"], e["label"], e.get("description", "")) for e in TEMPLATE_SETS
    ]

