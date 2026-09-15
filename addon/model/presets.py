# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Presets + globals (texture/array lookup redesign 2026-06-19).

A **Preset** is a NAMED parameter combination (R, M, E, C). Faces reference a
preset by carrying its `uid` in the `lpc_index` face attribute -- the stable
identity tying a face to its preset, unaffected by list order. The preset's
PBR parameters themselves live centrally, in a small LUT image (Blender
preview) / shader array (Godot export), indexed by the preset's CURRENT LIST
POSITION, which is the derived value scattered onto faces' `lpc_uv1.x`
(model/faces.py). So a value edit only touches the LUT, not any face; only a
list reorder/delete (`rescatter_all_list_positions`) touches faces, and only
their `lpc_uv1.x`.

There is one shared material for the whole project (ui/preview_material.py),
not one per preset.

Lifecycle (Invariant 6): refcounts are lazy (decision #4), computed on demand
by counting faces whose `lpc_index` is the preset's uid across all meshes.
Delete is allowed at refcount 0 only.

The pure counting logic is bpy-free and testable; only the PropertyGroup
layer below needs `bpy`.
"""

try:
    import bpy
except ModuleNotFoundError:  # plain-python tests without Blender
    bpy = None

try:
    from .. import constants
except ImportError:  # plain-python tests put the addon dir on sys.path
    import constants

# Immutable "no preset" uid sentinel. Real preset uids start at 1
# (lpc_preset_next_uid) so they never collide with it.
UNASSIGNED = 0

# Preset parameter keys + neutral defaults. The single definition of the
# parameter list: the UI sliders, the JSON logic (ops/presets.py) and the
# default-preset validation all derive from these keys.
# (No occlusion: invisible in a Principled preview. No alpha: transparency
# is a material-level property -- a per-face alpha < 1 would force the
# material out of opaque mode.)
PRESET_VALUE_KEYS = ("roughness", "metallic", "emission", "clearcoat")
PRESET_VALUE_DEFAULTS = {
    "roughness": 0.8, "metallic": 0.0, "emission": 0.0, "clearcoat": 0.0,
}

# --------------------------------------------------------------------------
# Pure logic (no bpy)
# --------------------------------------------------------------------------

def reference_counts(keys, referenced_keys):
    """Reference count per key (aligned with `keys`) from an iterable of
    referenced keys. `None` keys and unknown references are ignored --
    degrade gracefully on foreign data."""
    counts = [0] * len(keys)
    index_by_key = {k: i for i, k in enumerate(keys) if k is not None}
    for key in referenced_keys:
        i = index_by_key.get(key)
        if i is not None:
            counts[i] += 1
    return counts


# --------------------------------------------------------------------------
# bpy layer
# --------------------------------------------------------------------------

if bpy is not None:

    def _preset_values_changed(self, context):
        """A preset's parameters changed -> regenerate the Blender-preview
        preset LUT image (Invariant 8: one-directional preset -> faces, just
        via the LUT now instead of a per-face UV rewrite). No per-face mesh
        write is needed: `lpc_uv1.x` carries the preset's LIST POSITION, which
        a value edit never changes -- only the LUT pixel at that position
        does. Lazy import: model must not import ui at load time as a
        sibling cycle."""
        if context is None or getattr(context, "scene", None) is None:
            return
        from ..ui import preview_material

        preview_material.update_preset_lut(context.scene)

    def _preset_name_changed(self, context):
        """A preset's name changed -> update the Geometry Node group's Menu
        Switch items if the node group exists."""
        if context is None or getattr(context, "scene", None) is None:
            return
        from ..ui import geometry_nodes

        geometry_nodes.update_lpc_geo_node_group(context.scene)

    class LPC_Preset(bpy.types.PropertyGroup):
        """One named parameter combination. `uid` is set once by `new_preset`
        and never changes; it is the identity faces reference via `lpc_index`.
        The name is purely cosmetic (a readable label / Godot surface hint)."""

        name: bpy.props.StringProperty(
            name="Name", default="Preset", update=_preset_name_changed
        )
        uid: bpy.props.IntProperty(
            name="UID", default=UNASSIGNED,
            description="Immutable preset identity",
        )
        roughness: bpy.props.FloatProperty(
            name="Roughness", default=0.8, min=0.0, max=1.0,
            description="Roughness (R)", update=_preset_values_changed,
        )
        metallic: bpy.props.FloatProperty(
            name="Metallic", default=0.0, min=0.0, max=1.0,
            description="Metallic (M)", update=_preset_values_changed,
        )
        emission: bpy.props.FloatProperty(
            name="Emission", default=0.0, min=0.0, max=1.0,
            description="Emission strength (E), scaled by the global "
            "emission factor", update=_preset_values_changed,
        )
        clearcoat: bpy.props.FloatProperty(
            name="Clearcoat", default=0.0, min=0.0, max=1.0,
            description="Clearcoat intensity (C)", update=_preset_values_changed,
        )

    def _globals_changed(self, context):
        # Globals live as value nodes / uniforms on the ONE shared material
        # (emission factor multiplies the per-face emission, coat roughness is
        # a project-wide constant). A globals edit updates that material only
        # -- no per-face rescatter needed.
        from ..ui import preview_material

        preview_material.update_globals(context.scene)

    class LPC_Globals(bpy.types.PropertyGroup):
        """Global material values -- project-wide constants applied to the one
        shared material (Invariant 8)."""

        emission_factor: bpy.props.FloatProperty(
            name="Emission Factor", default=constants.DEFAULT_EMISSION_FACTOR,
            min=0.0, soft_max=16.0,
            description="Global multiplier on every preset's emission",
            update=_globals_changed,
        )
        clearcoat_roughness: bpy.props.FloatProperty(
            name="Clearcoat Roughness",
            default=constants.DEFAULT_CLEARCOAT_ROUGHNESS, min=0.0, max=1.0,
            description="Project-wide constant clearcoat roughness",
            update=_globals_changed,
        )

    def new_preset(scene, name=""):
        """Append a preset with a fresh uid (the ONLY place uids are
        assigned). The shared material is created lazily on first paint."""
        preset = scene.lpc_presets.add()
        preset.uid = scene.lpc_preset_next_uid
        scene.lpc_preset_next_uid += 1
        if name:
            preset.name = name
        return preset

    def preset_for_uid(scene, uid):
        """The preset with `uid`, or None (Sample / Select: uid -> preset)."""
        if uid == UNASSIGNED:
            return None
        for preset in scene.lpc_presets:
            if preset.uid == uid:
                return preset
        return None

    def preset_list_position(scene, uid):
        """The preset's current index in `scene.lpc_presets`, or None. This is
        the value written onto faces' `lpc_uv1.x` (the shader-array index) --
        DERIVED from list order, unlike `uid` which is the face's permanent
        reference."""
        for i, preset in enumerate(scene.lpc_presets):
            if preset.uid == uid:
                return i
        return None

    def build_preset_lut_pixels(scene):
        """Flat RGBA float buffer, one texel per preset IN LIST ORDER:
        R=roughness, G=metallic, B=clearcoat, A=emission (raw, before the
        global emission factor). Width is `max(len(presets), 1)` so an empty
        list still yields a valid 1x1 image. The preset-array equivalent of
        `model.palette.build_pixels` -- shared by the Blender-preview LUT
        image and the exported LUT texture."""
        presets = list(scene.lpc_presets)
        width = max(len(presets), 1)
        pixels = [0.0] * (width * 4)
        for i, preset in enumerate(presets):
            pixels[i * 4:i * 4 + 4] = (
                preset.roughness, preset.metallic,
                preset.clearcoat, preset.emission,
            )
        return pixels

    def rescatter_all_list_positions(scene):
        """Push every preset's CURRENT list position onto `lpc_uv1.x` of every
        face carrying its uid, across all meshes. The list-position
        equivalent of the old per-value scatter -- called after any
        operation that can change preset order/membership (today: only
        delete shifts positions; add/duplicate/import are cheap no-ops here
        since appending never moves an existing preset)."""
        from . import faces as model_faces

        for position, preset in enumerate(scene.lpc_presets):
            model_faces.scatter_list_position(preset.uid, position)

    def resync_after_list_change(scene):
        """Call after ANY operation that adds, removes, or reorders presets:
        keeps the per-face `lpc_uv1.x` positions AND the Blender-preview LUT
        image/divisor node in sync with the current list."""
        from ..ui import preview_material
        from ..ui import geometry_nodes

        rescatter_all_list_positions(scene)
        preview_material.update_preset_lut(scene)
        geometry_nodes.update_lpc_geo_node_group(scene)

    def preset_refcounts(scene):
        """Lazy refcount per preset (aligned with `scene.lpc_presets`): how
        many faces across ALL meshes carry the preset's uid (decision #4)."""
        from . import faces

        keys = [preset.uid for preset in scene.lpc_presets]
        return reference_counts(
            keys,
            (
                uid
                for mesh_indices in faces.iter_face_indices_per_mesh()
                for uid in mesh_indices
                if uid != UNASSIGNED
            ),
        )

