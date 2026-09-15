# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Addon-wide constants.

Tuning values that users rarely or never change, so no UI is needed for
them. Collected here instead of being scattered as magic numbers through
the modules.
"""

# Namespace prefix for every NAME the add-on writes into mesh/material
# data -- exposed so a user can resolve name clashes in their .blend and
# in exports by changing it in this one place. It controls exactly the
# names that show up in the .blend data and get carried into exports:
#   - the per-face data names (model/faces.py): lpc_index (preset uid),
#     lpc_uv0 / lpc_uv1 (param UV maps)
#   - the shared material datablock + its node names (ui/preview_material.py):
#     lpc_multicolor, the emission-factor / clearcoat-roughness /
#     preset-count value nodes, and the node-version + managed custom-prop
#     keys (lpc_nodes_version, lpc_managed)
#   - the two managed preview images + their stamp keys
#     (ui/preview_material.py): lpc_palette / lpc_preset_lut,
#     lpc_palette_managed / lpc_preset_lut_managed
#   - the shared Geometry Node group datablock + its stamp key
#     (ui/geometry_nodes.py): lpc_set_material, lpc_geo_nodes_managed
#   - the entire exported Godot fileset (export/): the prefix feeds both the
#     output FILENAMES (the templates are named {{prefix}}multicolor.tres.tpl
#     etc., rendered like their bodies) and the names inside them -- the .tres
#     resource_name (lpc_multicolor / lpc_singlecolor), the ExtResource shader
#     paths + #include lines pointing between the files, the exported texture
#     filenames (lpc_palette.png / lpc_preset_lut.png), and -- via a PascalCase
#     form of it derived in export/exporter.py -- the GDScript class_name of
#     the exported look resource (LpcSinglecolorResource). That class_name is
#     registered PROJECT-WIDE in Godot, so two LPC exports sharing one Godot
#     project must use different prefixes.
#
# IMPORTANT: choose this BEFORE painting any faces. Changing it on a file
# that already has painted faces orphans the existing lpc_* data (fresh ones
# are recreated under the new names) and unlinks the shared material's nodes
# from them. There is no automatic migration.
#
# NOT controlled by this knob (and correctly so): the Scene/WindowManager
# custom properties (scene.lpc_presets, ...) are add-on-private config --
# not mesh data, never exported -- and are accessed as Python attributes,
# so they can't derive from a constant without getattr/setattr at every
# call site; operator bl_idnames use the dotted "lpc." namespace (runtime
# only, not stored in the .blend); the exported Godot shader/material
# templates hardcode their own "lpc_"-prefixed uniform/sampler names
# (lpc_palette_tex, lpc_palette_cell_x, ...) as literal template text, not
# derived from this constant. UI labels keep their own wording.
PREFIX = "lpc_"

# Picker: frame around the palette grid.
PICKER_FRAME_COLOR = (0.1, 0.1, 0.1, 1.0)  # RGBA, dark grey
PICKER_FRAME_WIDTH = 3.0  # frame thickness in pixels (float; scaled by ui_scale)

# Picker: marker for the CURRENTLY picked cell (the x/y already stored in
# lpc_picker_result) so the overlay opens showing which cell is active. An
# amber accent, distinct from the white hover outline; drawn over a dark
# backing line so it reads on any palette color underneath.
PICKER_SELECTED_COLOR = (1.0, 0.55, 0.1, 1.0)  # RGBA, amber

# Default palette parameters for a fresh file. These seed the
# LPC_PaletteParams defaults (picker/interface.py); the user can still change
# them per scene in the Settings dialog.
DEFAULT_PALETTE_COLS = 16          # hue columns (excluding the greyscale column)
DEFAULT_PALETTE_ROWS = 9
DEFAULT_PALETTE_ADD_GREYSCALE = True
DEFAULT_PALETTE_SATURATION = 1.0   # middle row (base color)
DEFAULT_PALETTE_BRIGHTNESS = 1.0   # middle row (base color)
DEFAULT_PALETTE_TINT = 0.8         # how far the top row goes toward white
DEFAULT_PALETTE_SHADE = 0.8        # how far the bottom row goes toward black

# Default global material values for a fresh file (seed LPC_Globals,
# model/presets.py); editable per scene in the Settings dialog.
DEFAULT_EMISSION_FACTOR = 1.0      # global multiplier on every preset's emission
DEFAULT_CLEARCOAT_ROUGHNESS = 0.0  # project-wide coat roughness

# Default presets, loaded via "Load Default Presets" and also used to seed
# a fresh file's preset list automatically (addon/__init__.py). Edit or
# extend freely. The format is exactly the "presets" list of an exported
# preset JSON file, so entries can be copied between here and exports.
# A preset always defines ALL four parameters (0..1 each), so every
# entry lists all of them explicitly -- missing or unknown keys raise on
# load, so nothing slips through silently.
DEFAULT_PRESETS = (
    {"name": "Solid",
     "roughness": 0.8, "metallic": 0.0, "emission": 0.0, "clearcoat": 0.0},
    {"name": "Metallic",
     "roughness": 0.3, "metallic": 1.0, "emission": 0.0, "clearcoat": 0.0},
    {"name": "Clearcoat",
     "roughness": 0.4, "metallic": 0.0, "emission": 0.0, "clearcoat": 1.0},
    {"name": "Emission",
     "roughness": 0.8, "metallic": 0.0, "emission": 1.0, "clearcoat": 0.0},
)

