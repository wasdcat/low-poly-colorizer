# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""LPC file import/export: palette and presets in one JSON file.

Format (`version: 2`):

    {
      "version": 2,
      "name": "...",        optional display name (templates)
      "palette": {...},     optional, see model.palette.palette_from_json
      "presets": [...]      optional, see ops.presets.presets_from_list
    }

At least one of `palette` / `presets`. Files of LPC 1.x (`version: 1`,
presets only) stay readable. Bundled palette templates
(addon/templates/*.json) use the same format.

Import: presets merge by name as before; the palette replaces the current
one as a whole and runs through the palette commit (ops/palette.py) -- the
painted faces follow automatically where column ids match, else the remap
table asks.

The (de)serialization is pure Python and testable without Blender.
"""

import json

try:
    import bpy
except ModuleNotFoundError:  # plain-python tests without Blender
    bpy = None

try:
    from ..model import palette as model_palette
    from . import presets as ops_presets
except ImportError:  # plain-python tests put the addon dir on sys.path
    from model import palette as model_palette
    from ops import presets as ops_presets

FILE_VERSION = 2
_KEYS = {"version", "name", "palette", "presets"}


# --------------------------------------------------------------------------
# Pure logic (no bpy)
# --------------------------------------------------------------------------

def write_lpc_file(palette=None, presets=None, name=None):
    """JSON text of an LPC file with the given sections (None = left out).
    Preset values are rounded like the 1.x export (float32 noise)."""
    if palette is None and presets is None:
        raise ValueError("nothing to export")
    data = {"version": FILE_VERSION}
    if name:
        data["name"] = name
    if palette is not None:
        data["palette"] = model_palette.palette_to_json(palette)
    if presets is not None:
        data["presets"] = ops_presets.rounded_presets(presets)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def read_lpc_file(text):
    """Parse an LPC file: a dict with `name` (or None), `palette` (palette
    dict or None) and `presets` (list of preset dicts or None). Accepts
    `version: 2` and the presets-only `version: 1`. Raises ValueError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("file must contain a JSON object")
    version = data.get("version")
    if version == 1:
        return {"name": None, "palette": None,
                "presets": ops_presets.presets_from_json(text)}
    if version != FILE_VERSION:
        raise ValueError(f"unsupported version: {version!r}")
    unknown = set(data) - _KEYS
    if unknown:
        raise ValueError(f"unknown keys {sorted(unknown)}")
    if "palette" not in data and "presets" not in data:
        raise ValueError("file has neither a palette nor presets")
    name = data.get("name")
    return {
        "name": str(name) if name is not None else None,
        "palette": (model_palette.palette_from_json(data["palette"])
                    if "palette" in data else None),
        "presets": (ops_presets.presets_from_list(data["presets"])
                    if "presets" in data else None),
    }


# --------------------------------------------------------------------------
# bpy layer
# --------------------------------------------------------------------------

if bpy is not None:
    from bpy_extras.io_utils import ExportHelper, ImportHelper

    from ..model import presets as model_presets
    from ..picker import interface as picker_interface
    from . import palette as ops_palette

    class LPC_OT_file_export(bpy.types.Operator, ExportHelper):
        """Save the palette and/or the presets to an LPC JSON file"""

        bl_idname = "lpc.file_export"
        bl_label = "Export LPC File"

        filename_ext = ".json"
        filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})
        include_palette: bpy.props.BoolProperty(
            name="Palette", default=True,
            description="Write the palette (groups, columns and global values)")
        include_presets: bpy.props.BoolProperty(
            name="Presets", default=True,
            description="Write all presets")

        def execute(self, context):
            scene = context.scene
            pal = picker_interface.params_from_scene(scene) if self.include_palette else None
            presets = ([ops_presets.preset_to_dict(p) for p in scene.lpc_presets]
                       if self.include_presets else None)
            try:
                text = write_lpc_file(pal, presets)
            except ValueError as exc:
                self.report({"ERROR"}, str(exc).capitalize())
                return {"CANCELLED"}
            try:
                with open(self.filepath, "w", encoding="utf-8") as f:
                    f.write(text)
            except OSError as exc:
                self.report({"ERROR"}, f"Could not write file: {exc}")
                return {"CANCELLED"}
            parts = []
            if pal is not None:
                parts.append("palette")
            if presets is not None:
                parts.append(f"{len(presets)} preset(s)")
            self.report({"INFO"}, "Exported " + " and ".join(parts))
            return {"FINISHED"}

    class LPC_OT_file_import(bpy.types.Operator, ImportHelper):
        """Load an LPC JSON file: presets are merged by name, the palette
        replaces the current one (painted faces follow; unclear colors are
        asked for). Also reads preset files of LPC 1.x"""

        bl_idname = "lpc.file_import"
        bl_label = "Import LPC File"
        bl_options = {"REGISTER", "UNDO"}

        filename_ext = ".json"
        filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})
        include_palette: bpy.props.BoolProperty(
            name="Palette", default=True,
            description="Replace the palette if the file has one")
        include_presets: bpy.props.BoolProperty(
            name="Presets", default=True,
            description="Merge the presets if the file has some")

        def execute(self, context):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    text = f.read()
            except OSError as exc:
                self.report({"ERROR"}, f"Could not read file: {exc}")
                return {"CANCELLED"}
            try:
                data = read_lpc_file(text)
            except ValueError as exc:
                self.report({"ERROR"}, f"Invalid LPC file: {exc}")
                return {"CANCELLED"}

            scene = context.scene
            messages = []
            if self.include_presets and data["presets"] is not None:
                counts = ops_presets.merge_presets_by_name(scene, data["presets"])
                model_presets.resync_after_list_change(scene)
                messages.append("presets: " + ops_presets.merge_report(*counts))
            if self.include_palette and data["palette"] is not None:
                if picker_interface.ensure_palette_initialized(scene):
                    picker_interface.refresh_palette_consumers(context)
                old = picker_interface.params_from_scene(scene)
                picker_interface.write_palette(scene.lpc_palette_params, data["palette"])
                scene.lpc_palette_params.legacy_notice = False
                status, msg = ops_palette.commit_palette(context, old)
                messages.append("palette: " + (
                    msg or ("choose where unclear colors go" if status == "table"
                            else "replaced")))
            if not messages:
                self.report({"WARNING"}, "Nothing imported (file section not selected)")
                return {"CANCELLED"}
            self.report({"INFO"}, "Imported " + "; ".join(messages))
            return {"FINISHED"}
