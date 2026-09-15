# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Assign/Sample/Select operators + Fix UV Maps (texture/array lookup redesign).

Assign: paint the current brush -- picked palette cell (x, y) + SELECTED
PRESET -- onto the selected faces (Edit Mode) or whole selected objects
(Object Mode). In one atomic step it writes the face's preset uid
(`lpc_index`), the picked cell into `lpc_uv0`, the preset's CURRENT LIST
POSITION into `lpc_uv1.x`, AND binds the face's `material_index` to the
shared lpc material slot (model/faces.assign_*); the slot is resolved lazily
per object (ui/preview_material).

The brush identity is the pair (preset uid, palette cell). Assign, Select,
Deselect and Sample all act on that SAME pair -- now an EXACT match (the cell
is read straight off `lpc_uv0`, no float-color rounding/approximation), so a
face "is the current brush" only when both its preset AND its exact cell
match.

Sample: read the active/selected face back into the UI -- its preset (via the
uid it carries) and the EXACT palette cell (via `lpc_uv0`, no nearest-cell
approximation needed anymore). Only for a homogeneous selection of one
painted (preset, cell).

Fix UV Maps: repair the param UV maps on every painted mesh -- recreate
missing ones, move them to the first two slots (so Godot imports them as
UV / UV2), and refill `lpc_uv1` (list positions) from the presets. `lpc_uv0`
(the picked palette cell) has no such source if it was missing/recreated --
those faces are flagged for repainting instead of silently zero-filled.

Mesh access follows the convention: BMesh in Edit Mode, mesh data in Object
Mode (inside model/faces.py).
"""

import bmesh
import bpy

from ..model import faces as model_faces
from ..model import palette
from ..model import presets as model_presets
from ..picker import interface as picker_interface
from ..ui import preview_material


def _current_brush(context):
    """The brush as (x, y, preset), or None if no valid palette cell is
    picked or no preset is selected. The (x, y) cell is the SOURCE the paint
    path writes into `lpc_uv0` -- the mesh carries the cell itself, never a
    baked color (Invariant 4: `color_at(x, y, params)` is only ever used for
    DISPLAY, e.g. the swatch and the picker overlay)."""
    scene = context.scene
    result = context.window_manager.lpc_picker_result
    params = picker_interface.params_from_scene(scene)
    cols, rows = palette.cell_count(params)
    if not (0 <= result.x < cols and 0 <= result.y < rows):
        return None
    index = scene.lpc_presets_active
    if not (0 <= index < len(scene.lpc_presets)):
        return None
    return result.x, result.y, scene.lpc_presets[index]


def _brush_key(context):
    """The current brush as a (preset uid, x, y) key, or None. The single
    identity Assign paints and Select / Deselect / Sample match on -- EXACT
    (the cell is the integer coordinates directly, no float color to
    round)."""
    brush = _current_brush(context)
    if brush is None:
        return None
    x, y, preset = brush
    return preset.uid, x, y


def _edit_mesh_objects(context):
    """Mesh objects in Edit Mode, one per unique mesh datablock."""
    seen = set()
    for obj in context.view_layer.objects:
        if obj.type == "MESH" and obj.mode == "EDIT" and obj.data not in seen:
            seen.add(obj.data)
            yield obj


def _face_key(face, index_layer, uv0_layer, cols, rows):
    """A face's (preset uid, x, y) identity -- same shape as `_brush_key`.
    Reads `lpc_uv0` directly via `decode_palette_uv` -- exact, no
    approximation. `cols, rows` are computed once by the caller, not per
    face."""
    uid = face[index_layer] if index_layer is not None else model_presets.UNASSIGNED
    if uv0_layer is None:
        return uid, None, None
    for loop in face.loops:
        x, y = model_faces.decode_palette_uv(loop[uv0_layer].uv, cols, rows)
        return uid, x, y
    return uid, None, None


def selection_state(context):
    """ONE pass over the current selection for the panel: how much is
    selected (summary + Assign enable) and whether Sample is well-defined
    (one distinct painted preset+cell). Returns a dict with keys: edit,
    faces, objects, has_target, sample_ok."""
    if context.mode == "EDIT_MESH":
        params = picker_interface.params_from_scene(context.scene)
        cols, rows = palette.cell_count(params)
        keys = []
        objects = 0
        for obj in _edit_mesh_objects(context):
            bm = bmesh.from_edit_mesh(obj.data)
            uv0_layer = bm.loops.layers.uv.get(model_faces.UV0_NAME)
            index_layer = bm.faces.layers.int.get(model_faces.INDEX_ATTRIBUTE)
            obj_faces = 0
            for face in bm.faces:
                if not face.select:
                    continue
                obj_faces += 1
                keys.append(_face_key(face, index_layer, uv0_layer, cols, rows))
            if obj_faces:
                objects += 1
        faces = len(keys)
        sample_ok = faces >= 1 and len(set(keys)) == 1
        if sample_ok:
            uid, _x, _y = next(iter(keys))
            sample_ok = (
                model_presets.preset_for_uid(context.scene, uid) is not None
            )
        return {
            "edit": True,
            "faces": faces,
            "objects": objects,
            "has_target": faces > 0,
            "sample_ok": sample_ok,
        }
    objects = sum(
        1
        for obj in context.view_layer.objects
        if obj.type == "MESH" and obj.select_get()
    )
    return {
        "edit": False,
        "faces": 0,
        "objects": objects,
        "has_target": objects > 0,
        "sample_ok": False,
    }


def sample_selection_is_homogeneous(context):
    """The Sample gate (one distinct painted material+cell selected)."""
    return selection_state(context)["sample_ok"]


def any_uv_fix_needed(context):
    """True if any painted mesh in the scene has its param UVs missing or out
    of TEXCOORD_0/1 order (so Godot would mis-import them). Drives the panel
    warning. Light per-object work (material slots + uv-layer names)."""
    seen = set()
    for obj in context.scene.objects:
        if obj.type == "MESH" and obj.data not in seen:
            seen.add(obj.data)
            if preview_material.mesh_needs_uv_fix(obj.data):
                return True
    return False


# --------------------------------------------------------------------------
# Painting: index + UVs + material binding in one step. The slot the preset's
# material occupies on each object is resolved lazily here (only objects you
# actually paint accumulate the slot).
#
# The two paint paths differ in slot 0 on a material-less object:
#   * Partial (Edit Mode): slot 0 is kept EMPTY, so the faces you never select
#     render the plain default -- and their material_index 0 keeps pointing at
#     that empty slot. This is load-bearing (see _paint_partial).
#   * Whole (Object Mode): NO empty slot -- every face is bound to the lpc slot,
#     so an empty slot 0 would be unreferenced clutter (and a spurious material
#     on Godot import). New geometry inherits the source face's paint via
#     Blender's own attribute copy on extrude/subdivide, so nothing is lost.
# On an object with its own materials we touch nothing extra either way and
# unpainted faces keep that material.
# --------------------------------------------------------------------------

def _paint_partial(obj, x, y, preset, scene):
    preview_material.ensure_unpainted_front(obj)
    slot = preview_material.ensure_lpc_slot(obj.data, scene)
    cols, rows = palette.cell_count(picker_interface.params_from_scene(scene))
    palette_uv0 = model_faces.encode_palette_uv(x, y, cols, rows)
    position = model_presets.preset_list_position(scene, preset.uid)
    return model_faces.assign_selected_faces(
        obj.data, palette_uv0, preset.uid, position, slot
    )


def _paint_whole(obj, x, y, preset, scene):
    # No empty slot 0 here (unlike _paint_partial): a whole-mesh paint binds
    # EVERY face to the lpc slot, so an empty slot 0 would be unreferenced --
    # dead weight in Blender and, worse, a spurious extra material on glTF/Godot
    # import. It also protects nothing: extrude/subdivide/loop-cut copy the
    # source face's lpc_uv0 + lpc_index + material_index, so new geometry
    # inherits the paint regardless of which slot lpc sits on.
    slot = preview_material.ensure_lpc_slot(obj.data, scene)
    cols, rows = palette.cell_count(picker_interface.params_from_scene(scene))
    palette_uv0 = model_faces.encode_palette_uv(x, y, cols, rows)
    position = model_presets.preset_list_position(scene, preset.uid)
    model_faces.assign_whole_mesh(
        obj.data, palette_uv0, preset.uid, position, slot
    )
    # Object-mode paint is the one moment we can safely reorder (the only path
    # that introduces the problem: first paint of a mesh that already had UVs).
    # No-op once the lpc maps are in front. Edit-mode paint can't reorder
    # inline -- the panel warning + Fix UV Maps cover that case.
    model_faces.reorder_param_uvs_first(obj.data)


def assign_current(context):
    """Paint the current brush onto the selection. Returns the painted count
    (faces in Edit Mode, objects in Object Mode) or None if the brush is
    incomplete."""
    brush = _current_brush(context)
    if brush is None:
        return None
    scene = context.scene
    x, y, preset = brush

    painted = 0
    edit_objects = list(_edit_mesh_objects(context))
    if edit_objects:
        for obj in edit_objects:
            painted += _paint_partial(obj, x, y, preset, scene)
    else:
        objects = [
            obj for obj in context.view_layer.objects
            if obj.type == "MESH" and obj.select_get()
        ]
        for obj in objects:
            _paint_whole(obj, x, y, preset, scene)
        painted = len(objects)
    return painted


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------

class LPC_OT_assign(bpy.types.Operator):
    """Paint the current brush -- the picked color and the active preset's material -- onto the selected faces (Edit Mode) or the whole selected objects (Object Mode)"""

    bl_idname = "lpc.assign"
    bl_label = "Assign"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def execute(self, context):
        painted = assign_current(context)
        if painted is None:
            self.report({"WARNING"}, "Pick a palette cell and select a preset first")
            return {"CANCELLED"}
        if painted == 0:
            self.report({"WARNING"}, "Nothing selected to paint")
            return {"CANCELLED"}
        return {"FINISHED"}


class LPC_OT_sample(bpy.types.Operator):
    """Load the selected face's brush into the UI -- its preset and the exact palette cell. Needs a selection of a single painted preset + color"""

    bl_idname = "lpc.sample"
    bl_label = "Sample"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.edit_object is not None

    def execute(self, context):
        if not sample_selection_is_homogeneous(context):
            self.report(
                {"WARNING"},
                "Select faces of a single painted preset and color to sample",
            )
            return {"CANCELLED"}

        scene = context.scene
        mesh = context.edit_object.data
        bm = bmesh.from_edit_mesh(mesh)
        uv0_layer = bm.loops.layers.uv.get(model_faces.UV0_NAME)
        index_layer = bm.faces.layers.int.get(model_faces.INDEX_ATTRIBUTE)

        face = bm.faces.active
        if face is None or not face.select:
            face = next((f for f in bm.faces if f.select), None)
        if face is None:
            self.report({"WARNING"}, "No face selected")
            return {"CANCELLED"}

        uid = face[index_layer] if index_layer is not None else (
            model_presets.UNASSIGNED
        )
        preset = model_presets.preset_for_uid(scene, uid)
        if preset is None:
            self.report({"WARNING"}, "Face has not been painted yet")
            return {"CANCELLED"}

        params = picker_interface.params_from_scene(scene)
        cols, rows = palette.cell_count(params)
        x, y = 0, 0
        if uv0_layer is not None:
            for loop in face.loops:
                x, y = model_faces.decode_palette_uv(loop[uv0_layer].uv, cols, rows)
                break
        # Silent: loading the UI from the face must not repaint it.
        picker_interface.set_picked_cell(context, x, y, live=False)
        for i, p in enumerate(scene.lpc_presets):
            if p == preset:
                scene.lpc_presets_active = i
                break
        return {"FINISHED"}


def _set_select_by_brush(context, key, select):
    """(De)select every face matching the brush `key` (preset uid + exact
    palette cell), across all Edit-Mode meshes. Returns the number of
    affected faces."""
    changed = 0
    params = picker_interface.params_from_scene(context.scene)
    cols, rows = palette.cell_count(params)
    for obj in _edit_mesh_objects(context):
        bm = bmesh.from_edit_mesh(obj.data)
        uv0_layer = bm.loops.layers.uv.get(model_faces.UV0_NAME)
        index_layer = bm.faces.layers.int.get(model_faces.INDEX_ATTRIBUTE)
        touched = 0
        for face in bm.faces:
            if _face_key(face, index_layer, uv0_layer, cols, rows) == key:
                face.select_set(select)
                touched += 1
        if touched:
            bmesh.update_edit_mesh(obj.data)
        changed += touched
    return changed


class LPC_OT_preset_select(bpy.types.Operator):
    """Add the faces painted with the current brush -- the picked color AND the active preset -- to the selection (extends it, like Blender's Select operations)"""

    bl_idname = "lpc.preset_select"
    bl_label = "Select"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and _brush_key(context) is not None

    def execute(self, context):
        _set_select_by_brush(context, _brush_key(context), True)
        return {"FINISHED"}


class LPC_OT_preset_deselect(bpy.types.Operator):
    """Deselect the faces painted with the current brush -- the picked color AND the active preset"""

    bl_idname = "lpc.preset_deselect"
    bl_label = "Deselect"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and _brush_key(context) is not None

    def execute(self, context):
        _set_select_by_brush(context, _brush_key(context), False)
        return {"FINISHED"}


class LPC_OT_fix_uv_maps(bpy.types.Operator):
    """Repair the lpc param UV maps on every painted mesh: recreate missing ones, move them to the first two UV slots, and refill lpc_uv1 (preset list positions) -- so Godot imports them as UV / UV2. Run this in Object Mode (e.g. after painting a mesh that already had UV maps)"""

    bl_idname = "lpc.fix_uv_maps"
    bl_label = "Fix UV Maps"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Rebuilding/reordering uv layers copies data via foreach, which is not
        # reachable on an edit-mode mesh, so this must run in Object Mode.
        if context.mode != "OBJECT":
            cls.poll_message_set("Switch to Object Mode first")
            return False
        return True

    def execute(self, context):
        scene = context.scene
        seen = set()
        fixed = 0
        uv0_recreated = 0
        for obj in scene.objects:
            if obj.type != "MESH" or obj.data in seen:
                continue
            seen.add(obj.data)
            mesh = obj.data
            if not preview_material.mesh_is_painted(mesh):
                continue
            if model_faces.param_uvs_status(mesh) != "ok":
                fixed += 1
            had_uv0 = model_faces.UV0_NAME in {l.name for l in mesh.uv_layers}
            model_faces.ensure_uv_layers(mesh)         # recreate any missing
            if not had_uv0:
                uv0_recreated += 1
            model_faces.reorder_param_uvs_first(mesh)  # lpc maps to front

        # Refill the (possibly just recreated) lpc_uv1 from the presets' list
        # positions. lpc_uv0 (the picked palette cell) has no such source --
        # a recreated one is unrecoverable and flagged below instead.
        model_presets.rescatter_all_list_positions(scene)

        if uv0_recreated:
            self.report(
                {"WARNING"},
                f"Fixed UV maps on {fixed} mesh(es); {uv0_recreated} had "
                f"lpc_uv0 recreated -- repaint the affected faces",
            )
        elif fixed:
            self.report({"INFO"}, f"Fixed UV maps on {fixed} mesh(es)")
        else:
            self.report({"INFO"}, "UV maps already correct")
        return {"FINISHED"}

