# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Palette editing operators: groups, columns, templates, and the commit.

Editing happens in the Settings dialog (ui/panel.py), which snapshots the
palette on open. Every operator here that changes the layout (add / remove
/ move a group or column, load a template) only STAGES the change: it is
`INTERNAL` (not in F3 search) and leaves the painted faces alone. When the
dialog is confirmed, `commit_palette` compares the snapshot with the
current palette (model/remap.py):

    identity       -- nothing to do
    automatic      -- every painted face is moved to its column's new place
    needs a table  -- `LPC_OT_palette_remap` asks how to map the old cells
                      that have no automatic target (deleted columns,
                      changed row count, narrower span); cancelling it
                      restores the snapshot

Cancelling the Settings dialog restores the snapshot as well.
"""

import json

import bpy

from ..model import faces as model_faces
from ..model import palette as model_palette
from ..model import remap as model_remap
from ..model import templates as model_templates
from ..picker import interface as picker_interface


# --------------------------------------------------------------------------
# Commit: remap painted faces from the snapshot to the current palette
# --------------------------------------------------------------------------

def _used_cells(old_palette):
    cols, rows = model_palette.cell_count(old_palette)
    return model_remap.count_cells(model_faces.painted_cell_uvs(), cols, rows)


def _remap_picked_cell(context, old_palette, new_palette, mapping):
    """Move the brush's cell along with the faces (silently, no paint)."""
    result = context.window_manager.lpc_picker_result
    cell = (result.x, result.y)
    target = mapping.get(cell)
    if target is None:
        plan = model_remap.plan_remap(old_palette, new_palette, {cell: 0})
        target = plan.automatic.get(cell)
        if target is None and plan.table:
            target = plan.table[0].suggestion
    if target is not None:
        picker_interface.set_picked_cell(context, target[0], target[1], live=False)


def apply_remap(context, old_palette, plan, mapping):
    """Rewrite every painted face per `mapping`, move the brush cell, and
    refresh the palette consumers. Returns the number of moved faces."""
    new_palette = picker_interface.params_from_scene(context.scene)
    moved = model_faces.remap_painted_uv0(
        lambda uv: model_remap.remap_uv(uv, plan, mapping))
    _remap_picked_cell(context, old_palette, new_palette, mapping)
    picker_interface.refresh_palette_consumers(context)
    return moved


def commit_palette(context, old_palette):
    """Bring the painted faces from `old_palette` to the scene's current
    palette. Returns (status, message): status "done" or "table" (the
    remap dialog was opened and finishes the job)."""
    new_palette = picker_interface.params_from_scene(context.scene)
    plan = model_remap.plan_remap(old_palette, new_palette, _used_cells(old_palette))
    if plan.is_identity:
        picker_interface.refresh_palette_consumers(context)
        return "done", ""
    if not plan.needs_confirmation:
        moved = apply_remap(context, old_palette, plan, plan.mapping())
        msg = "Palette updated, %d face(s) moved" % moved if moved else "Palette updated"
        return "done", msg
    _stage_table(context, old_palette, new_palette, plan)
    bpy.ops.lpc.palette_remap("INVOKE_DEFAULT")
    return "table", ""


def _stage_table(context, old_palette, new_palette, plan):
    wm = context.window_manager
    wm.lpc_remap_old_palette = json.dumps(old_palette)
    rows = wm.lpc_remap_rows
    rows.clear()
    for row in plan.table:
        item = rows.add()
        item.old_x, item.old_y = row.old_cell
        item.label = model_palette.cell_label(old_palette, *row.old_cell)
        item.faces = row.faces
        item.old_color = model_palette.color_at(row.old_cell[0], row.old_cell[1], old_palette)
        item.new_x, item.new_y = row.suggestion
    wm.lpc_remap_active = 0


def _restore(context, old_palette):
    picker_interface.write_palette(context.scene.lpc_palette_params, old_palette)
    picker_interface.refresh_palette_consumers(context)


def _new_color_get(self):
    try:
        pal = picker_interface.params_from_scene(bpy.context.scene)
        cols, rows = model_palette.cell_count(pal)
        x = min(max(self.new_x, 0), cols - 1)
        y = min(max(self.new_y, 0), rows - 1)
        return model_palette.color_at(x, y, pal)
    except Exception:
        return (0.0, 0.0, 0.0, 1.0)


def _new_label_get(self):
    try:
        pal = picker_interface.params_from_scene(bpy.context.scene)
        return model_palette.cell_label(pal, self.new_x, self.new_y) or "outside the palette"
    except Exception:
        return ""


class LPC_RemapRow(bpy.types.PropertyGroup):
    """One old cell of the remap table and its chosen new cell."""

    old_x: bpy.props.IntProperty()
    old_y: bpy.props.IntProperty()
    label: bpy.props.StringProperty()
    faces: bpy.props.IntProperty()
    old_color: bpy.props.FloatVectorProperty(subtype="COLOR", size=4, min=0.0, max=1.0)
    new_x: bpy.props.IntProperty(name="X", min=0)
    new_y: bpy.props.IntProperty(name="Y", min=0)
    new_color: bpy.props.FloatVectorProperty(
        subtype="COLOR", size=4, min=0.0, max=1.0, get=_new_color_get)
    new_label: bpy.props.StringProperty(get=_new_label_get)


class LPC_UL_remap_rows(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index):
        row = layout.row(align=True)
        sw = row.row()
        sw.ui_units_x = 1.5
        sw.prop(item, "old_color", text="")
        row.label(text="%s (%d)" % (item.label, item.faces))
        row.label(text="", icon="FORWARD")
        sw = row.row()
        sw.ui_units_x = 1.5
        sw.prop(item, "new_color", text="")
        sub = row.row(align=True)
        sub.ui_units_x = 5
        sub.prop(item, "new_x", text="")
        sub.prop(item, "new_y", text="")
        row.label(text=item.new_label)


class LPC_OT_palette_remap(bpy.types.Operator):
    """Choose where painted faces go whose color has no automatic place in
    the changed palette"""

    bl_idname = "lpc.palette_remap"
    bl_label = "Remap Painted Faces"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=640)

    def draw(self, context):
        wm = context.window_manager
        layout = self.layout
        total = sum(r.faces for r in wm.lpc_remap_rows)
        layout.label(
            text="%d color(s) on %d face(s) have no place in the new palette."
            % (len(wm.lpc_remap_rows), total), icon="INFO")
        layout.label(text="Each is preset to the nearest color -- correct where needed (X / Y):")
        layout.template_list("LPC_UL_remap_rows", "", wm, "lpc_remap_rows",
                             wm, "lpc_remap_active", rows=8)
        layout.label(text="Cancel keeps the previous palette.")

    def execute(self, context):
        wm = context.window_manager
        old_palette = json.loads(wm.lpc_remap_old_palette)
        new_palette = picker_interface.params_from_scene(context.scene)
        cols, rows = model_palette.cell_count(new_palette)
        plan = model_remap.plan_remap(old_palette, new_palette, _used_cells(old_palette))
        table_cells = {row.old_cell for row in plan.table}
        overrides = {}
        for item in wm.lpc_remap_rows:
            cell = (item.old_x, item.old_y)
            if cell in table_cells:
                overrides[cell] = (min(item.new_x, cols - 1), min(item.new_y, rows - 1))
        moved = apply_remap(context, old_palette, plan, plan.mapping(overrides))
        wm.lpc_remap_rows.clear()
        self.report({"INFO"}, "Palette updated, %d face(s) moved" % moved)
        return {"FINISHED"}

    def cancel(self, context):
        wm = context.window_manager
        if wm.lpc_remap_old_palette:
            _restore(context, json.loads(wm.lpc_remap_old_palette))
        wm.lpc_remap_rows.clear()


# --------------------------------------------------------------------------
# Staging operators (used inside the Settings dialog)
# --------------------------------------------------------------------------

def _params(context):
    return context.scene.lpc_palette_params


def _active_group(p):
    if 0 <= p.groups_active < len(p.groups):
        return p.groups[p.groups_active]
    return None


def _total_columns(p):
    return sum(len(g.columns) for g in p.groups)


def _grid_cols(p):
    return sum(c.span for g in p.groups for c in g.columns)


def _changed(context):
    picker_interface.refresh_palette_consumers(context)


class LPC_OT_palette_group_add(bpy.types.Operator):
    """Add a palette group after the selected one, with one column"""

    bl_idname = "lpc.palette_group_add"
    bl_label = "Add Group"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return _grid_cols(_params(context)) < model_palette.MAX_GRID_COLS

    def execute(self, context):
        p = _params(context)
        g = p.groups.add()
        g.name = "Group %d" % len(p.groups)
        g.chroma = 0.1
        c = g.columns.add()
        c.name = "Column"
        c.column_id = picker_interface.new_column_id(p)
        target = min(p.groups_active + 1, len(p.groups) - 1)
        p.groups.move(len(p.groups) - 1, target)
        p.groups_active = target
        _changed(context)
        return {"FINISHED"}


class LPC_OT_palette_group_remove(bpy.types.Operator):
    """Remove the selected group and its columns"""

    bl_idname = "lpc.palette_group_remove"
    bl_label = "Remove Group"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        p = _params(context)
        g = _active_group(p)
        if g is None:
            return False
        if _total_columns(p) - len(g.columns) < 1:
            cls.poll_message_set("The palette needs at least one column")
            return False
        return True

    def execute(self, context):
        p = _params(context)
        p.groups.remove(p.groups_active)
        p.groups_active = max(0, min(p.groups_active, len(p.groups) - 1))
        _changed(context)
        return {"FINISHED"}


class LPC_OT_palette_group_move(bpy.types.Operator):
    """Move the selected group (with its columns) up or down"""

    bl_idname = "lpc.palette_group_move"
    bl_label = "Move Group"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    direction: bpy.props.EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        p = _params(context)
        i = p.groups_active
        j = i - 1 if self.direction == "UP" else i + 1
        if not (0 <= i < len(p.groups) and 0 <= j < len(p.groups)):
            return {"CANCELLED"}
        p.groups.move(i, j)
        p.groups_active = j
        _changed(context)
        return {"FINISHED"}


class LPC_OT_palette_column_add(bpy.types.Operator):
    """Add a column after the selected one (copying its values)"""

    bl_idname = "lpc.palette_column_add"
    bl_label = "Add Column"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        p = _params(context)
        return (_active_group(p) is not None
                and _grid_cols(p) < model_palette.MAX_GRID_COLS)

    def execute(self, context):
        p = _params(context)
        g = _active_group(p)
        src = g.columns[g.columns_active] if 0 <= g.columns_active < len(g.columns) else None
        c = g.columns.add()
        c.column_id = picker_interface.new_column_id(p)
        if src is not None:
            c.name = src.name + " 2"
            c.hue = (src.hue + 30.0) % 360.0
            c.use_chroma = src.use_chroma
            c.chroma = src.chroma
        else:
            c.name = "Column"
        target = min(g.columns_active + 1, len(g.columns) - 1)
        g.columns.move(len(g.columns) - 1, target)
        g.columns_active = target
        _changed(context)
        return {"FINISHED"}


class LPC_OT_palette_column_remove(bpy.types.Operator):
    """Remove the selected column"""

    bl_idname = "lpc.palette_column_remove"
    bl_label = "Remove Column"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        p = _params(context)
        g = _active_group(p)
        if g is None or not (0 <= g.columns_active < len(g.columns)):
            return False
        if _total_columns(p) <= 1:
            cls.poll_message_set("The palette needs at least one column")
            return False
        return True

    def execute(self, context):
        p = _params(context)
        g = _active_group(p)
        g.columns.remove(g.columns_active)
        g.columns_active = max(0, min(g.columns_active, len(g.columns) - 1))
        _changed(context)
        return {"FINISHED"}


class LPC_OT_palette_column_move(bpy.types.Operator):
    """Move the selected column up or down; at the end of its group it moves
    into the neighboring group"""

    bl_idname = "lpc.palette_column_move"
    bl_label = "Move Column"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    direction: bpy.props.EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        p = _params(context)
        gi = p.groups_active
        g = _active_group(p)
        if g is None or not (0 <= g.columns_active < len(g.columns)):
            return {"CANCELLED"}
        i = g.columns_active
        up = self.direction == "UP"
        j = i - 1 if up else i + 1
        if 0 <= j < len(g.columns):
            g.columns.move(i, j)
            g.columns_active = j
        else:
            # Cross into the neighboring group (last / first position).
            ngi = gi - 1 if up else gi + 1
            if not (0 <= ngi < len(p.groups)):
                return {"CANCELLED"}
            data = _column_dict(g.columns[i])
            g.columns.remove(i)
            g.columns_active = max(0, min(i, len(g.columns) - 1))
            ng = p.groups[ngi]
            c = ng.columns.add()
            _column_set(c, data)
            if not up:
                ng.columns.move(len(ng.columns) - 1, 0)
            p.groups_active = ngi
            ng.columns_active = len(ng.columns) - 1 if up else 0
        _changed(context)
        return {"FINISHED"}


def _column_dict(c):
    return {"name": c.name, "column_id": c.column_id, "hue": c.hue,
            "use_chroma": c.use_chroma, "chroma": c.chroma, "span": c.span}


def _column_set(c, data):
    for key, value in data.items():
        setattr(c, key, value)


def _template_items(self, context):
    items = [(slug, name, "Replace the palette with the template '%s'" % name)
             for slug, name in model_templates.list_templates()]
    _template_items.cache = items  # keep the strings alive (Blender enum rule)
    return items or [("NONE", "No templates", "")]


class LPC_OT_palette_load_template(bpy.types.Operator):
    """Replace the palette with a bundled template (painted faces are
    remapped when the dialog is confirmed)"""

    bl_idname = "lpc.palette_load_template"
    bl_label = "Load Palette Template"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    template: bpy.props.EnumProperty(name="Template", items=_template_items)

    def execute(self, context):
        try:
            pal = model_templates.load_template(self.template)
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, "Could not load template: %s" % exc)
            return {"CANCELLED"}
        p = _params(context)
        # Fresh ids would lose the automatic remap between palettes that
        # share columns, so the template's ids are kept as they are.
        picker_interface.write_palette(p, pal)
        _changed(context)
        return {"FINISHED"}


class LPC_MT_palette_templates(bpy.types.Menu):
    bl_idname = "LPC_MT_palette_templates"
    bl_label = "Palette Templates"

    def draw(self, context):
        layout = self.layout
        for slug, name in model_templates.list_templates():
            layout.operator("lpc.palette_load_template", text=name).template = slug


class LPC_OT_palette_dismiss_notice(bpy.types.Operator):
    """Hide the note about the palette converted from LPC 1.x"""

    bl_idname = "lpc.palette_dismiss_notice"
    bl_label = "Dismiss"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        _params(context).legacy_notice = False
        return {"FINISHED"}


class LPC_UL_palette_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False)
        row.label(text=str(len(item.columns)))


class LPC_UL_palette_columns(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index):
        row = layout.row(align=True)
        sw = row.row()
        sw.ui_units_x = 1.2
        sw.prop(item, "preview_color", text="")
        row.prop(item, "name", text="", emboss=False)
        if item.span > 1:
            row.label(text="x%d" % item.span)
