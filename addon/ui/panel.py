# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""N-panel and settings dialog: picker invocation and result display.

Panel layout:

    Low Poly Colorizer   color row + preset list, then the ACTIVE preset's
                         parameter sliders (always visible -- edits
                         propagate live to all faces using it via scatter,
                         model/faces.py), then the button row
                         (Assign / Select / Deselect, the latter two Edit
                         Mode only) + Sample
      [no header]        UV-fix warning (when needed), the Export target +
                         button, and the Settings button

The rarely-edited values -- the palette (template, rows, lightness, groups
and their columns, tint/shade, artwork) and the global material values --
live in the modal "Settings" dialog (`LPC_OT_palette_settings`,
`invoke_props_dialog`). Confirming it commits palette layout changes,
remapping painted faces (ops/palette.py).
"""

import bpy

from ..export import exporter as export_exporter
from ..model import presets as model_presets
from ..ops import assign_sample as ops_assign_sample

# Lazy refcounts (decision #4): computed ONCE per panel redraw from the
# per-face lpc_index (preset uid) of all meshes, read by the UIList rows below.
_preset_refcounts = []


def _count_noun(count, noun):
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _format_selection(state):
    """Hint line under the color row: what a pick will paint (picks
    live-assign to the selection). Pure formatting of the
    pre-computed selection state -- no mesh scan here."""
    if state["edit"]:
        if state["faces"] == 0:
            return "No faces selected"
        return (
            f"{_count_noun(state['faces'], 'face')} in "
            f"{_count_noun(state['objects'], 'object')} selected"
        )
    if state["objects"] == 0:
        return "No objects selected"
    return f"{_count_noun(state['objects'], 'object')} selected"


class LPC_OT_palette_settings(bpy.types.Operator):
    """Edit the palette and the global material values in a modal dialog"""

    bl_idname = "lpc.palette_settings"
    bl_label = "Settings"
    bl_options = {"REGISTER", "UNDO"}

    # Keys of LPC_Globals snapshotted alongside the palette.
    _GLOBAL_KEYS = ("emission_factor", "clearcoat_roughness")

    def invoke(self, context, event):
        # Edits in the dialog apply live to the scene (preview image); the
        # palette is snapshotted here: Cancel restores it, OK commits it --
        # remapping the painted faces from the snapshot (ops/palette.py).
        from ..picker import interface as picker_interface

        scene = context.scene
        if picker_interface.ensure_palette_initialized(scene):
            picker_interface.refresh_palette_consumers(context)
        self._backup = picker_interface.params_from_scene(scene)
        self._globals_backup = {
            key: getattr(scene.lpc_globals, key) for key in self._GLOBAL_KEYS
        }
        return context.window_manager.invoke_props_dialog(self, width=460)

    def cancel(self, context):
        from ..picker import interface as picker_interface

        picker_interface.write_palette(context.scene.lpc_palette_params, self._backup)
        picker_interface.refresh_palette_consumers(context)
        # Restoring triggers the globals' update callbacks -> the preview
        # material is rolled back too.
        globals_pg = context.scene.lpc_globals
        for key, value in self._globals_backup.items():
            setattr(globals_pg, key, value)

    def draw(self, context):
        layout = self.layout
        p = context.scene.lpc_palette_params

        if p.legacy_notice:
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Palette converted from LPC 1.x.", icon="INFO")
            col.label(text="Painted faces kept their cells; colors may differ.")
            box.operator("lpc.palette_dismiss_notice")

        row = layout.row()
        row.label(text="Palette")
        row.menu("LPC_MT_palette_templates", text="Templates", icon="PRESET")

        grid_box = layout.box()
        row = grid_box.row(align=True)
        row.prop(p, "rows")
        row = grid_box.row(align=True)
        row.prop(p, "l_top")
        row.prop(p, "l_bottom")

        # Groups
        groups_box = layout.box()
        groups_box.label(text="Groups")
        row = groups_box.row()
        row.template_list("LPC_UL_palette_groups", "", p, "groups", p,
                          "groups_active", rows=3)
        col = row.column(align=True)
        col.operator("lpc.palette_group_add", text="", icon="ADD")
        col.operator("lpc.palette_group_remove", text="", icon="REMOVE")
        col.separator()
        col.operator("lpc.palette_group_move", text="", icon="TRIA_UP").direction = "UP"
        col.operator("lpc.palette_group_move", text="", icon="TRIA_DOWN").direction = "DOWN"

        group = p.groups[p.groups_active] if 0 <= p.groups_active < len(p.groups) else None
        if group is not None:
            col = groups_box.column(align=True)
            col.prop(group, "chroma")
            for use_key, key in (("use_l_top", "l_top"), ("use_l_bottom", "l_bottom")):
                row = col.row(align=True)
                row.prop(group, use_key, text="")
                sub = row.row(align=True)
                sub.active = getattr(group, use_key)
                sub.prop(group, key)

            # Columns of the selected group
            cols_box = layout.box()
            cols_box.label(text="Columns of %s" % group.name)
            row = cols_box.row()
            row.template_list("LPC_UL_palette_columns", "", group, "columns",
                              group, "columns_active", rows=5)
            col = row.column(align=True)
            col.operator("lpc.palette_column_add", text="", icon="ADD")
            col.operator("lpc.palette_column_remove", text="", icon="REMOVE")
            col.separator()
            col.operator("lpc.palette_column_move", text="", icon="TRIA_UP").direction = "UP"
            col.operator("lpc.palette_column_move", text="", icon="TRIA_DOWN").direction = "DOWN"
            if 0 <= group.columns_active < len(group.columns):
                column = group.columns[group.columns_active]
                col = cols_box.column(align=True)
                row = col.row(align=True)
                row.prop(column, "hue")
                row.prop(column, "span")
                row = col.row(align=True)
                row.prop(column, "use_chroma", text="")
                sub = row.row(align=True)
                sub.active = column.use_chroma
                sub.prop(column, "chroma")

        range_box = layout.box()
        range_box.label(text="Tint / Shade")
        row = range_box.row(align=True)
        row.prop(p, "tint")
        row.prop(p, "shade")

        art_box = layout.box()
        art_box.label(text="Artwork")
        row = art_box.row(align=True)
        row.prop(p, "hue_shift")
        row.prop(p, "warmth")

        glob_box = layout.box()
        glob_box.label(text="Globals")
        col = glob_box.column(align=True)
        col.prop(context.scene.lpc_globals, "emission_factor")
        col.prop(context.scene.lpc_globals, "clearcoat_roughness")

        layout.label(text="OK keeps painted faces on their colors (asks if unclear).")

    def execute(self, context):
        from ..ops import palette as ops_palette

        _status, message = ops_palette.commit_palette(context, self._backup)
        if message:
            self.report({"INFO"}, message)
        return {"FINISHED"}


class LPC_UL_presets(bpy.types.UIList):
    """Preset list: editable name + refcount (shield icon while faces
    still use the preset, Invariant 6 -- the "-" button next to the list
    is disabled then). Double-click renames."""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_prop, index
    ):
        count = (
            _preset_refcounts[index] if index < len(_preset_refcounts) else 0
        )
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False)
        if count > 0:
            row.label(text=str(count), icon="FAKE_USER_ON")
        else:
            row.label(text="0", icon="BLANK1")


class LPC_MT_presets(bpy.types.Menu):
    """Preset extras: duplicate, LPC file import/export (palette and/or
    presets) and the bundled defaults -- tucked away next to the list. (Fix UV Maps is surfaced by the
    footer warning only when a mesh actually needs it.)"""

    bl_idname = "LPC_MT_presets"
    bl_label = "Preset Extras"

    def draw(self, context):
        layout = self.layout
        layout.operator("lpc.preset_duplicate", icon="DUPLICATE")
        layout.separator()
        layout.operator("lpc.file_import", text="Import Palette / Presets...", icon="IMPORT")
        layout.operator("lpc.file_export", text="Export Palette / Presets...", icon="EXPORT")
        layout.separator()
        layout.operator("lpc.preset_load_defaults", icon="PRESET")
        layout.separator()
        layout.operator(
            "lpc.add_geo_node_group",
            text="Create Geometry Node Group",
            icon="GEOMETRY_NODES",
        )


class LPC_PT_palette_panel(bpy.types.Panel):
    """Main panel: the everyday tools -- color row + preset list."""

    bl_label = "Low Poly Colorizer"
    bl_idname = "LPC_PT_palette_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LPC"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        result = context.window_manager.lpc_picker_result
        row = layout.row(align=True)
        row.prop(result, "color", text="")
        row.prop(result, "x", text="X")
        row.prop(result, "y", text="Y")
        # Palette-grid picker -- a colour/palette icon (the EYEDROPPER is
        # reserved for Sample, which actually samples a face).
        row.operator("lpc.modal_palette_picker", text="", icon="COLOR")

        # One selection scan per redraw, reused for the summary line, the
        # Assign enable and the Sample enable below.
        state = ops_assign_sample.selection_state(context)

        # Picks live-assign -- tell the user what they would paint, and
        # warn when the brush is incomplete (a pick paints color AND the
        # active preset; without one it silently paints nothing).
        layout.label(text=_format_selection(state))
        if not (0 <= scene.lpc_presets_active < len(scene.lpc_presets)):
            layout.label(text="No preset selected", icon="ERROR")

        global _preset_refcounts
        _preset_refcounts = model_presets.preset_refcounts(scene)

        row = layout.row()
        row.template_list(
            "LPC_UL_presets", "", scene, "lpc_presets", scene,
            "lpc_presets_active", rows=4,
        )
        col = row.column(align=True)
        col.operator("lpc.preset_add", text="", icon="ADD")
        col.operator("lpc.preset_delete", text="", icon="REMOVE")
        col.separator()
        col.menu("LPC_MT_presets", text="", icon="DOWNARROW_HLT")

        # Parameters of the active preset, always visible -- edits
        # propagate live to every face using the preset (scatter). Rename
        # the preset in the list above (double-click); no name field here.
        index = scene.lpc_presets_active
        if 0 <= index < len(scene.lpc_presets):
            preset = scene.lpc_presets[index]
            col = layout.column(align=True)
            for key in model_presets.PRESET_VALUE_KEYS:
                col.prop(preset, key, slider=True)

        # First action row: Sample (leading) | Assign.
        #   Sample: only well-defined for a homogeneous selection.
        #   Assign: paints the selection (disabled with nothing selected).
        row = layout.row(align=True)
        sample_sub = row.row(align=True)
        sample_sub.enabled = state["sample_ok"]
        sample_sub.operator("lpc.sample", icon="EYEDROPPER")
        assign_sub = row.row(align=True)
        assign_sub.enabled = state["has_target"]
        assign_sub.operator("lpc.assign", icon="BRUSH_DATA")
        # Second action row: Select | Deselect act on the faces matching the
        # current brush (color + preset, Edit Mode) -- they create a
        # selection, so they stay enabled.
        if context.mode == "EDIT_MESH":
            row = layout.row(align=True)
            row.operator("lpc.preset_select", icon="SELECT_EXTEND")
            row.operator("lpc.preset_deselect", icon="SELECT_SUBTRACT")


class LPC_PT_footer(bpy.types.Panel):
    """Headerless section: the Settings button at the very bottom."""

    bl_label = ""
    bl_idname = "LPC_PT_footer"
    bl_parent_id = "LPC_PT_palette_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        # Warn (+ one-click fix) when a painted mesh's param UVs are missing or
        # out of TEXCOORD_0/1 order -- they would mis-import into Godot. Fix UV
        # Maps mutates meshes (Object Mode), so it stays an explicit button.
        layout = self.layout

        if ops_assign_sample.any_uv_fix_needed(context):
            box = layout.box()
            box.label(text="UV maps need fixing", icon="ERROR")
            box.operator("lpc.fix_uv_maps", icon="GROUP_UVS")

        # Export: right-aligned "Export" label, then the template set (Godot
        # is one of possibly several engines) + the Export button. The
        # button alone (not the target dropdown) goes red whenever the
        # CURRENT scene's fingerprint no longer matches the one stored at
        # the last export -- computed live so undo/redo/manual reverts are
        # reflected automatically, not toggled by the edit paths.
        split = layout.split(factor=0.3, align=True)
        head = split.row()
        head.alignment = "RIGHT"
        head.label(text="Export")
        body = split.row(align=True)
        body.prop(context.scene, "lpc_export_target", text="")
        export_sub = body.row(align=True)
        export_sub.alert = export_exporter.is_export_dirty(context.scene)
        export_sub.operator("lpc.export", text="", icon="EXPORT")

        if context.scene.lpc_palette_params.legacy_notice:
            layout.label(text="Palette converted from LPC 1.x", icon="INFO")
        layout.operator(
            "lpc.palette_settings", text="Settings...", icon="PREFERENCES"
        )

