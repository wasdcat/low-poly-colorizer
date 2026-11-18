# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Preset operators and the preset part of the LPC file format.

The preset DATA MODEL (PropertyGroup, uid, the LUT/list-position scatter)
lives in model/presets.py -- presets are the authority for parameter values.
This module provides the operators around it: add / delete (refcount-guarded,
Invariant 6) / duplicate, the bundled defaults from
constants.DEFAULT_PRESETS, and the preset (de)serialization the LPC file
import/export uses (ops/file_io.py).

Every operator that can add, remove, or reorder a preset calls
`model_presets.resync_after_list_change` at the end -- it keeps the per-face
`lpc_uv1.x` (list position) and the Blender-preview LUT image/divisor node in
sync with the current list. Cheap even when technically a no-op (e.g.
appending a preset never shifts any existing preset's position); delete is
the one action that actually shifts positions, since it's the only one that
removes from the middle of the list.

Setting preset properties (add_preset_from_dict, JSON import) triggers the
property update callbacks -- a value edit only touches the LUT image, never
a face (model layer); only a list-membership/order change touches faces, via
the resync call above.

There is no "apply preset to brush" anymore: the brush IS (picked
palette cell + selected preset), and editing a preset's sliders
propagates directly to every face using it.

The JSON (de)serialization and validation are pure Python and testable
without Blender; only the operator layer needs `bpy`.
"""


try:
    import bpy
except ModuleNotFoundError:  # plain-python tests without Blender
    bpy = None

try:
    from .. import constants
    from ..model import presets as model_presets
except ImportError:  # plain-python tests put the addon dir on sys.path
    import constants
    from model import presets as model_presets


# --------------------------------------------------------------------------
# Pure logic (no bpy)
# --------------------------------------------------------------------------

# Parameter keys / neutral defaults -- defined once in the model layer.
VALUE_KEYS = model_presets.PRESET_VALUE_KEYS
VALUE_DEFAULTS = model_presets.PRESET_VALUE_DEFAULTS

# Slack for "did this preset value change on import?" -- absorbs the
# float32 storage round-trip (0.3 read back as 0.30000001) so an unchanged
# re-import is not miscounted as an update. A real edit differs far more.
_VALUE_MATCH_EPS = 1e-6


def make_preset(name, **values):
    """A preset as a plain dict; unspecified parameter values default to
    the neutral defaults."""
    defaults = dict(VALUE_DEFAULTS)
    unknown = set(values) - set(VALUE_KEYS)
    if unknown:
        raise ValueError(f"unknown preset keys: {sorted(unknown)}")
    defaults.update(values)
    return {"name": str(name), **defaults}


def default_presets():
    """The bundled standard templates. The data lives in
    `constants.DEFAULT_PRESETS` for easy user tweaking, in the same
    format as the "presets" list of an exported JSON file. Strict mode:
    a typo'd or missing key in constants should raise, not be silently
    dropped/defaulted."""
    return presets_from_list(constants.DEFAULT_PRESETS, strict=True)


def rounded_presets(presets):
    """Preset dicts with their values rounded to 2 decimals, for writing to
    a file: the float32 sliders carry round-trip noise (0.3 ->
    0.30000001192...) that would otherwise litter the export, and 2 decimals
    is finer than the slider's visible precision."""
    return [
        {k: (round(v, 2) if k in VALUE_KEYS else v) for k, v in preset.items()}
        for preset in presets
    ]


def presets_from_list(raw_presets, strict=False):
    """Validate a list of raw preset dicts into clean preset dicts.

    Shared by the JSON import and `default_presets` -- one format, one
    validator. Raises ValueError on anything malformed. Parameter values
    are clamped to 0..1 -- bad input never puts the UI into an invalid
    state. Unknown keys (e.g. the palette cell from older exports) are
    ignored and missing values fall back to VALUE_DEFAULTS -- unless
    `strict` is set, which rejects both (hand-edited sources should be
    explicit: a preset always defines all four parameters).
    """
    if not isinstance(raw_presets, (list, tuple)):
        raise ValueError("'presets' must be a list")
    presets = []
    for i, raw in enumerate(raw_presets):
        if not isinstance(raw, dict):
            raise ValueError(f"preset {i}: expected an object")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"preset {i}: missing or empty 'name'")
        if strict:
            unknown = set(raw) - {"name", *VALUE_KEYS}
            if unknown:
                raise ValueError(
                    f"preset {i} ({name}): unknown keys {sorted(unknown)}"
                )
            missing = set(VALUE_KEYS) - set(raw)
            if missing:
                raise ValueError(
                    f"preset {i} ({name}): missing keys {sorted(missing)}"
                )
        preset = {"name": name}
        for key in VALUE_KEYS:
            value = raw.get(key, VALUE_DEFAULTS[key])
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"preset {i} ({name}): '{key}' must be a number")
            preset[key] = min(max(float(value), 0.0), 1.0)
        presets.append(preset)
    return presets


# --------------------------------------------------------------------------
# bpy layer
# --------------------------------------------------------------------------

if bpy is not None:
    def preset_to_dict(preset):
        return make_preset(
            preset.name,
            **{key: getattr(preset, key) for key in VALUE_KEYS},
        )

    def add_preset_from_dict(scene, data):
        """Append a preset (fresh uid) with the values from a validated
        preset dict."""
        preset = model_presets.new_preset(scene, data["name"])
        for key in VALUE_KEYS:
            setattr(preset, key, data[key])

    def _preset_values_match(preset, data):
        """True if `preset` already holds `data`'s values. The slack
        absorbs the float32 storage round-trip (0.3 stored == 0.30000001
        read) so an unchanged re-import is recognised as such; a real edit
        differs by far more than this."""
        return all(
            abs(getattr(preset, key) - data[key]) <= _VALUE_MATCH_EPS
            for key in VALUE_KEYS
        )

    def merge_presets_by_name(scene, presets):
        """Import presets, matching on name. A preset whose name already
        exists is UPDATED in place when its values actually differ (its uid
        is kept, so painted faces stay referenced; the writes go through the
        property update -> the one scatter path, so those faces rescatter
        live). An identical match is left untouched (no scatter). New names
        are appended. So re-importing the same file changes nothing and
        never orphans a face. Returns (added, updated, unchanged) counts.

        First-wins on duplicate names within `presets` itself: once a name
        is taken (existing or just added), later entries with that name
        compare against the same preset rather than spawning a twin."""
        by_name = {p.name: p for p in scene.lpc_presets}
        added = updated = unchanged = 0
        for data in presets:
            existing = by_name.get(data["name"])
            if existing is None:
                add_preset_from_dict(scene, data)
                by_name[data["name"]] = scene.lpc_presets[-1]
                added += 1
            elif _preset_values_match(existing, data):
                unchanged += 1
            else:
                for key in VALUE_KEYS:
                    setattr(existing, key, data[key])
                updated += 1
        return added, updated, unchanged

    def merge_report(added, updated, unchanged):
        """Human summary of a merge -- only the non-zero buckets, so an
        unchanged re-import does not falsely claim it updated anything."""
        parts = [
            f"{n} {label}"
            for n, label in (
                (added, "added"), (updated, "updated"), (unchanged, "unchanged")
            )
            if n
        ]
        return ", ".join(parts) if parts else "nothing to import"

    def seed_default_presets(scene):
        """Populate a scene that has NO presets yet with the bundled
        defaults. Idempotent -- a scene that already has presets is left
        untouched. Used by the load-time auto-preload (addon __init__) so a
        fresh file has presets to work with; the manual 'Load Default
        Presets' operator additively tops up instead."""
        if scene.lpc_presets:
            return 0
        for data in default_presets():
            add_preset_from_dict(scene, data)
        return len(scene.lpc_presets)

    def _active_preset(scene):
        index = scene.lpc_presets_active
        if 0 <= index < len(scene.lpc_presets):
            return scene.lpc_presets[index]
        return None

    class LPC_OT_preset_add(bpy.types.Operator):
        """Add a new preset with neutral default values"""

        bl_idname = "lpc.preset_add"
        bl_label = "Add Preset"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            scene = context.scene
            model_presets.new_preset(
                scene, f"Preset {len(scene.lpc_presets) + 1}"
            )
            scene.lpc_presets_active = len(scene.lpc_presets) - 1
            model_presets.resync_after_list_change(scene)
            return {"FINISHED"}

    class LPC_OT_preset_delete(bpy.types.Operator):
        """Delete the selected preset (only possible while no face uses it)"""

        bl_idname = "lpc.preset_delete"
        bl_label = "Delete Preset"
        bl_options = {"REGISTER", "UNDO"}

        @classmethod
        def poll(cls, context):
            scene = context.scene
            index = scene.lpc_presets_active
            if not (0 <= index < len(scene.lpc_presets)):
                return False
            if model_presets.preset_refcounts(scene)[index] > 0:
                cls.poll_message_set("Preset is still in use")
                return False
            return True

        def execute(self, context):
            scene = context.scene
            index = scene.lpc_presets_active
            # Refcount 0 means no face carries the preset's uid, so the entry
            # can be removed. The material is shared across all presets, so it
            # is never removed here.
            scene.lpc_presets.remove(index)
            scene.lpc_presets_active = min(index, len(scene.lpc_presets) - 1)
            # Deleting shifts every later preset's list position down by one
            # -- the only UI action that does, since faces reference a
            # preset by its uid, not its position.
            model_presets.resync_after_list_change(scene)
            return {"FINISHED"}

    class LPC_OT_preset_duplicate(bpy.types.Operator):
        """Duplicate the selected preset"""

        bl_idname = "lpc.preset_duplicate"
        bl_label = "Duplicate Preset"
        bl_options = {"REGISTER", "UNDO"}

        @classmethod
        def poll(cls, context):
            return _active_preset(context.scene) is not None

        def execute(self, context):
            scene = context.scene
            data = preset_to_dict(_active_preset(scene))
            data["name"] += " Copy"
            add_preset_from_dict(scene, data)
            scene.lpc_presets_active = len(scene.lpc_presets) - 1
            model_presets.resync_after_list_change(scene)
            return {"FINISHED"}

    class LPC_OT_preset_load_defaults(bpy.types.Operator):
        """Load the bundled standard presets: existing names are updated to
        the bundled values (only if they differ), new ones are added"""

        bl_idname = "lpc.preset_load_defaults"
        bl_label = "Load Default Presets"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            counts = merge_presets_by_name(context.scene, default_presets())
            model_presets.resync_after_list_change(context.scene)
            self.report({"INFO"}, f"Default presets: {merge_report(*counts)}")
            return {"FINISHED"}
