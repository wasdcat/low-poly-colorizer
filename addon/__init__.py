# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Low Poly Colorizer.

Blender add-on for painting mesh faces with PBR material values via a
generated color palette, with a WYSIWYG viewport preview. The source of
truth lives in face attributes + the preset list and persists natively
in the .blend -- no derived state, nothing to reconstruct on load.

Metadata (name, version, ...) lives in `blender_manifest.toml` (the single
source of truth for the extension). Architecture and invariants: see
ARCHITECTURE.md.
"""

import bpy
from bpy.app.handlers import persistent

from .export import exporter as export_exporter
from .model import presets as model_presets
from .ops import assign_sample as ops_assign_sample
from .ops import presets as ops_presets
from .picker import interface as picker_interface
from .picker import modal as picker_modal
from .ui import geometry_nodes as ui_geometry_nodes
from .ui import panel as ui_panel

classes = (
    model_presets.LPC_Preset,
    model_presets.LPC_Globals,
    picker_interface.LPC_PaletteParams,
    picker_interface.LPC_PickerResult,
    picker_modal.LPC_OT_modal_palette_picker,
    ops_assign_sample.LPC_OT_assign,
    ops_assign_sample.LPC_OT_sample,
    ops_assign_sample.LPC_OT_preset_select,
    ops_assign_sample.LPC_OT_preset_deselect,
    ops_assign_sample.LPC_OT_fix_uv_maps,
    ops_presets.LPC_OT_preset_add,
    ops_presets.LPC_OT_preset_delete,
    ops_presets.LPC_OT_preset_duplicate,
    ops_presets.LPC_OT_preset_load_defaults,
    ops_presets.LPC_OT_preset_export_json,
    ops_presets.LPC_OT_preset_import_json,
    export_exporter.LPC_OT_export,
    ui_geometry_nodes.LPC_OT_add_geo_node_group,
    ui_panel.LPC_OT_palette_settings,
    ui_panel.LPC_UL_presets,
    ui_panel.LPC_MT_presets,
    # Panels in display order (children render after the parent).
    ui_panel.LPC_PT_palette_panel,
    ui_panel.LPC_PT_footer,
)


def _seed_pathless_empty_scenes():
    """Seed the bundled defaults into the scenes of a NEW / startup file
    (no path yet) whose preset list is still empty. An opened, saved
    .blend has a path and is left exactly as the user saved it. Idempotent.

    NOTE: a deliberate, narrow exception to "no load handlers" (Invariant
    3): it INITIALISES primary user data when empty, it does not
    reconstruct derived state. See ARCHITECTURE.md."""
    if bpy.data.filepath:
        return
    for scene in bpy.data.scenes:
        ops_presets.seed_default_presets(scene)


@persistent
def _seed_presets_on_load(*_args):
    """File > New / open -> seed a fresh file (see _seed_pathless_empty_scenes)."""
    _seed_pathless_empty_scenes()


def _seed_on_enable():
    """One-shot timer: seed the file that is ALREADY open when the add-on
    is enabled / Blender starts (load_post does not fire for it). Returns
    None so the timer runs exactly once."""
    _seed_pathless_empty_scenes()
    return None


@persistent
def _redraw_on_undo_redo(*_args):
    """Force every 3D-viewport area (where the N-panel lives) to redraw
    after an undo/redo step. The Export button's dirty state
    (export.exporter.is_export_dirty) is computed live in the panel's
    draw() rather than bound via a watched `.prop()`, so Blender does not
    reliably know to redraw that region on its own after undo/redo
    restores a preset/palette/globals value -- without this the button can
    keep showing red (or stay unhighlighted) after an undo until something
    else happens to trigger a redraw."""
    if bpy.context.window is None:  # background mode: no screen to redraw
        return
    for window in bpy.context.window_manager.windows:
        if window.screen is None:  # transient window mid construction/teardown
            continue
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.lpc_presets = bpy.props.CollectionProperty(
        type=model_presets.LPC_Preset
    )
    bpy.types.Scene.lpc_presets_active = bpy.props.IntProperty(
        name="Active Preset", default=0, min=0
    )
    bpy.types.Scene.lpc_preset_next_uid = bpy.props.IntProperty(
        name="Next Preset UID", default=1, min=1,
        description="Monotonic counter; the only source of preset uids "
        "(starts at 1 -- 0 is the UNASSIGNED sentinel for unpainted faces)",
    )
    bpy.types.Scene.lpc_globals = bpy.props.PointerProperty(
        type=model_presets.LPC_Globals
    )
    bpy.types.Scene.lpc_export_target = bpy.props.EnumProperty(
        name="Export Target",
        description="Which template set the Export button writes",
        items=export_exporter.EXPORT_TARGET_ITEMS,
    )
    bpy.types.Scene.lpc_export_fingerprint = bpy.props.StringProperty(
        name="Last Export Fingerprint", default="",
        description="Snapshot of every value baked into the exported "
        "files as of the last successful export (export.exporter."
        "export_fingerprint) -- compared live against the current scene "
        "to decide whether the Export button should flag as out of date. "
        "A real Scene property (persists across saves) rather than "
        "process-only state, safe because LPC_OT_export is itself "
        "undo-registered",
    )
    bpy.types.Scene.lpc_palette_params = bpy.props.PointerProperty(
        type=picker_interface.LPC_PaletteParams
    )
    bpy.types.WindowManager.lpc_picker_result = bpy.props.PointerProperty(
        type=picker_interface.LPC_PickerResult
    )
    if _seed_presets_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_seed_presets_on_load)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _redraw_on_undo_redo not in handlers:
            handlers.append(_redraw_on_undo_redo)
    # Seed the file that is already open (install / Blender start). Deferred
    # via a timer because data must not be mutated during registration; not
    # in background (no main loop, and tests manage their own presets).
    if not bpy.app.background:
        bpy.app.timers.register(_seed_on_enable, first_interval=0.0)


def unregister():
    if bpy.app.timers.is_registered(_seed_on_enable):
        bpy.app.timers.unregister(_seed_on_enable)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _redraw_on_undo_redo in handlers:
            handlers.remove(_redraw_on_undo_redo)
    if _seed_presets_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_seed_presets_on_load)
    if hasattr(bpy.types.WindowManager, "lpc_picker_result"):
        del bpy.types.WindowManager.lpc_picker_result
    for prop in (
        "lpc_palette_params",
        "lpc_export_fingerprint",
        "lpc_export_target",
        "lpc_globals",
        "lpc_preset_next_uid",
        "lpc_presets_active",
        "lpc_presets",
    ):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

