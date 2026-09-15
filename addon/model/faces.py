# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Per-face source of truth (texture/array lookup redesign 2026-06-19).

Per face there are now these native, export-friendly facts:

    lpc_index       INT     FACE   -- which preset (its uid), SOURCE
    lpc_uv0         UV map         -- palette cell (x, y), SOURCE (brush pick)
    lpc_uv1.x       UV map (1st)   -- preset's list position, DERIVED
    lpc_uv1.y       UV map (2nd)   -- reserved, currently unwritten
    material_index  (built-in)     -- painted? (the shared lpc slot)

`lpc_index` (the preset's stable `uid`, 0 = unpainted) is the SOURCE that ties
a face to a preset; it never changes payload (still drives refcounting,
Sample/Select/Deselect identity, and which faces a list-position rescatter
must touch). `lpc_uv0` is the SOURCE for color -- the exact palette cell the
brush picked, texel-center addressed and pre-compensated for Blender's glTF
exporter's V-flip (`encode_palette_uv`/`decode_palette_uv` below). `lpc_uv1.x`
is DERIVED from the preset's CURRENT LIST POSITION (`model.presets.
rescatter_all_list_positions`); editing a preset's VALUES no longer touches
any face at all -- only the LUT image/array the position indexes into.

Both UV maps flow in carefully scoped directions: `lpc_uv0` is written once,
at paint time, and never rescattered (a palette-settings change only changes
the IMAGE a cell's color comes from, not any face's stored cell -- so no
mesh traversal is needed for that case). `lpc_uv1.x` IS rescattered, but only
when the preset LIST changes (delete is the only UI action that shifts
positions today), via `scatter_list_position`.

Mesh access convention (ARCHITECTURE.md): meshes in Edit Mode via their edit BMesh
(the datablock attributes are EMPTY there), everything else via
`mesh.attributes` / `mesh.uv_layers` + foreach_get/foreach_set.
"""

try:
    import bpy
    import bmesh
except ModuleNotFoundError:  # plain-python tests without Blender
    bpy = None

from . import presets as model_presets

try:
    from .. import constants
except ImportError:  # plain-python tests put the addon dir on sys.path
    import constants

# The per-face data names (the contract with the shared material's nodes and
# with the Godot import). All share the add-on namespace prefix.
INDEX_ATTRIBUTE = constants.PREFIX + "index"   # FACE INT, preset uid
UV0_NAME = constants.PREFIX + "uv0"            # palette cell (x, y)
UV1_NAME = constants.PREFIX + "uv1"            # (list position, reserved)

UNASSIGNED = model_presets.UNASSIGNED


# --------------------------------------------------------------------------
# Pure logic (no bpy): palette-cell <-> UV0 encoding
# --------------------------------------------------------------------------

def palette_uv(cell_x, cell_y, cols, rows):
    """Texel-center UV for palette cell (cell_x, cell_y) in a cols x rows
    palette image, BEFORE the glTF V pre-compensation `_encode_uv0` applies.
    Shared by `encode_palette_uv` and (in reverse) `decode_palette_uv`."""
    return ((cell_x + 0.5) / cols, (cell_y + 0.5) / rows)


def _encode_uv0(uv):
    """Pre-compensate `uv` for Blender's glTF exporter, which flips V
    (v' = 1-v) on EVERY UV layer at export time, not just texture-flagged
    ones -- harmless while UV0 held raw numeric params, but correctness-
    critical now that it addresses a real texture. U is untouched (glTF only
    flips V)."""
    u, v = uv
    return (u, 1.0 - v)


def encode_palette_uv(cell_x, cell_y, cols, rows):
    """The (cell_x, cell_y) palette cell, ready to write into `lpc_uv0` --
    texel-center addressed and glTF-V-pre-compensated. The one function the
    paint path (ops/assign_sample.py) calls; `decode_palette_uv` is its exact
    inverse."""
    return _encode_uv0(palette_uv(cell_x, cell_y, cols, rows))


def decode_palette_uv(uv, cols, rows):
    """Inverse of `encode_palette_uv`: the UV stored on `lpc_uv0` -> exact
    (cell_x, cell_y) ints. Round-trips exactly for any value
    `encode_palette_uv` produced (the texel-center +0.5 offset cancels
    exactly under int truncation). Used by Sample for an exact read-back."""
    u, v_stored = uv
    v = 1.0 - v_stored
    return int(u * cols), int(v * rows)


# --------------------------------------------------------------------------
# bpy layer
# --------------------------------------------------------------------------

if bpy is not None:

    # -- attribute / UV plumbing -----------------------------------------

    def ensure_index_attribute(mesh):
        """The FACE INT `lpc_index` on an Object-Mode mesh, created (0 =
        unpainted) if missing. A leftover non-FACE/non-INT attribute under the
        name is replaced."""
        attr = mesh.attributes.get(INDEX_ATTRIBUTE)
        if attr is not None and (
            attr.domain != "FACE" or attr.data_type != "INT"
        ):
            mesh.attributes.remove(attr)
            attr = None
        if attr is None:
            attr = mesh.attributes.new(INDEX_ATTRIBUTE, "INT", "FACE")
        return attr

    def ensure_uv_layers(mesh):
        """The two param UV maps on an Object-Mode mesh, created if missing.
        Returns (uv0, uv1)."""
        uv0 = mesh.uv_layers.get(UV0_NAME) or mesh.uv_layers.new(name=UV0_NAME)
        uv1 = mesh.uv_layers.get(UV1_NAME) or mesh.uv_layers.new(name=UV1_NAME)
        return uv0, uv1

    def _bmesh_index_layer(bm):
        layer = bm.faces.layers.int.get(INDEX_ATTRIBUTE)
        if layer is None:
            layer = bm.faces.layers.int.new(INDEX_ATTRIBUTE)
        return layer

    def _bmesh_uv_layers(bm):
        u0 = bm.loops.layers.uv.get(UV0_NAME) or bm.loops.layers.uv.new(UV0_NAME)
        u1 = bm.loops.layers.uv.get(UV1_NAME) or bm.loops.layers.uv.new(UV1_NAME)
        return u0, u1

    # -- assign (index + palette UV + preset position + slot, atomically) --

    def assign_selected_faces(mesh, palette_uv0, uid, preset_position, slot_index):
        """Paint the SELECTED faces of an Edit-Mode mesh in one step: the
        face's preset `uid`, `lpc_uv0` = `palette_uv0` (the already-encoded
        palette cell, every corner), `lpc_uv1.x` = `preset_position` (every
        corner, `.y` left at 0.0 -- reserved), and the face's
        `material_index` (the shared lpc slot). Returns the number of
        painted faces."""
        bm = bmesh.from_edit_mesh(mesh)
        ilayer = _bmesh_index_layer(bm)
        u0, u1 = _bmesh_uv_layers(bm)
        uv1 = (preset_position, 0.0)
        painted = 0
        for face in bm.faces:
            if face.select:
                for loop in face.loops:
                    loop[u0].uv = palette_uv0
                    loop[u1].uv = uv1
                face[ilayer] = uid
                face.material_index = slot_index
                painted += 1
        if painted:
            bmesh.update_edit_mesh(mesh)
        return painted

    def assign_whole_mesh(mesh, palette_uv0, uid, preset_position, slot_index):
        """Paint every face of an Object-Mode mesh: `lpc_uv0` = `palette_uv0`
        on every corner, every face's `uid`, `lpc_uv1.x` = `preset_position`
        on every corner (`.y` left at 0.0), all faces bound to
        `slot_index`."""
        iattr = ensure_index_attribute(mesh)
        l0, l1 = ensure_uv_layers(mesh)

        npoly = len(mesh.polygons)
        nloops = len(mesh.loops)
        iattr.data.foreach_set("value", [uid] * npoly)
        l0.data.foreach_set("uv", list(palette_uv0) * nloops)
        l1.data.foreach_set("uv", [preset_position, 0.0] * nloops)
        mesh.polygons.foreach_set("material_index", [slot_index] * npoly)
        mesh.update()

    # -- scatter: push a preset's list position onto every face with its uid --

    def scatter_list_position(uid, position):
        """Rewrite ONLY `lpc_uv1.x` (never `.y`, which is reserved) on every
        face that carries `uid`, across ALL meshes (Edit Mode via BMesh,
        Object Mode via attribute data). One-directional: preset list ->
        faces. Called from `model.presets.rescatter_all_list_positions`
        whenever the preset list's order or membership changes."""
        if uid == UNASSIGNED:
            return
        for mesh in bpy.data.meshes:
            if mesh.is_editmode:
                _scatter_edit_uv1x(mesh, uid, position)
            else:
                _scatter_object_uv1x(mesh, uid, position)

    def _scatter_edit_uv1x(mesh, uid, position):
        bm = bmesh.from_edit_mesh(mesh)
        ilayer = bm.faces.layers.int.get(INDEX_ATTRIBUTE)
        u1 = bm.loops.layers.uv.get(UV1_NAME)
        if ilayer is None or u1 is None:
            return
        changed = False
        for face in bm.faces:
            if face[ilayer] == uid:
                for loop in face.loops:
                    loop[u1].uv[0] = position
                changed = True
        if changed:
            bmesh.update_edit_mesh(mesh)

    def _scatter_object_uv1x(mesh, uid, position):
        iattr = mesh.attributes.get(INDEX_ATTRIBUTE)
        l1 = mesh.uv_layers.get(UV1_NAME)
        if iattr is None or l1 is None:
            return
        npoly = len(mesh.polygons)
        indices = [0] * npoly
        iattr.data.foreach_get("value", indices)
        if uid not in indices:
            return
        nloops = len(mesh.loops)
        b1 = [0.0] * (2 * nloops)
        l1.data.foreach_get("uv", b1)
        starts = [0] * npoly
        totals = [0] * npoly
        mesh.polygons.foreach_get("loop_start", starts)
        mesh.polygons.foreach_get("loop_total", totals)
        for p in range(npoly):
            if indices[p] != uid:
                continue
            for li in range(starts[p], starts[p] + totals[p]):
                b1[2 * li] = position  # .x only; .y (b1[2*li+1]) untouched
        l1.data.foreach_set("uv", b1)
        mesh.update()

    # -- UV map order (Godot maps TEXCOORD_0/1 -> UV/UV2) ---------------
    #
    # Blender's glTF exporter does NOT assign TEXCOORD_0 by list position --
    # it picks whichever UV layer is flagged "active render" (the camera
    # icon in the UV Maps list) for slot 0, then the rest in list order. A
    # mesh that already had its own texturing UV map keeps THAT one flagged
    # active-render even after lpc_uv0/lpc_uv1 are moved to the front of the
    # list, so list position alone is not sufficient to control what Godot
    # imports as `UV` -- the active-render flag must also point at lpc_uv0.

    def param_uvs_status(mesh):
        """Presence + order + active-render flag of the param UV maps,
        name-only (safe in any mode):
        'absent'     -- neither lpc UV map present
        'incomplete' -- only one of the two present
        'misordered' -- both present, but either not the leading two layers
                        or lpc_uv0 is not the active-render layer (either way
                        Godot would NOT import them as TEXCOORD_0/1 = UV/UV2)
        'ok'         -- lpc_uv0, lpc_uv1 are exactly the first two layers AND
                        lpc_uv0 is the active-render layer
        Whether the mesh is actually painted is the caller's call (a non-lpc
        mesh is simply 'absent')."""
        names = [layer.name for layer in mesh.uv_layers]
        has0, has1 = UV0_NAME in names, UV1_NAME in names
        if not has0 and not has1:
            return "absent"
        if not (has0 and has1):
            return "incomplete"
        if names[:2] != [UV0_NAME, UV1_NAME]:
            return "misordered"
        if not mesh.uv_layers[UV0_NAME].active_render:
            return "misordered"
        return "ok"

    def reorder_param_uvs_first(mesh):
        """Move lpc_uv0 / lpc_uv1 to the front of the mesh's uv layers AND
        force lpc_uv0 to be the active-render layer -- NOT preserving
        whatever was active-render before, since that is exactly what would
        silently re-break TEXCOORD_0 on export (see the note above). UV
        layers have no move API, so a position fix rebuilds the collection
        from scratch. Returns True if either the order or the active-render
        layer changed. OBJECT MODE only (edit-mode uv data is not reachable
        via foreach)."""
        layers = mesh.uv_layers
        current = [layer.name for layer in layers]
        leading = [n for n in (UV0_NAME, UV1_NAME) if n in current]
        if not leading:
            return False
        desired = leading + [n for n in current if n not in leading]
        order_ok = desired == current
        active_ok = layers.get(UV0_NAME).active_render
        if order_ok and active_ok:
            return False

        if order_ok:
            layers.get(UV0_NAME).active_render = True
            mesh.update()
            return True

        nloops = len(mesh.loops)
        data = {}
        for layer in layers:
            buf = [0.0] * (2 * nloops)
            layer.data.foreach_get("uv", buf)
            data[layer.name] = buf

        while len(layers) > 0:
            layers.remove(layers[0])
        for name in desired:
            new = layers.new(name=name, do_init=False)
            new.data.foreach_set("uv", data[name])
        layers.get(UV0_NAME).active_render = True
        mesh.update()
        return True

    # -- refcount source: which preset uid each face carries ------------

    def iter_face_indices_per_mesh():
        """Per-face preset uid, one list per mesh -- the input for the lazy
        preset refcounts (decision #4). Unpainted faces yield 0."""
        for mesh in bpy.data.meshes:
            if mesh.is_editmode:
                bm = bmesh.from_edit_mesh(mesh)
                ilayer = bm.faces.layers.int.get(INDEX_ATTRIBUTE)
                if ilayer is None:
                    yield [UNASSIGNED] * len(bm.faces)
                else:
                    yield [f[ilayer] for f in bm.faces]
            else:
                iattr = mesh.attributes.get(INDEX_ATTRIBUTE)
                npoly = len(mesh.polygons)
                if iattr is None:
                    yield [UNASSIGNED] * npoly
                else:
                    buffer = [0] * npoly
                    iattr.data.foreach_get("value", buffer)
                    yield buffer

