# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Layer 2: picker contract.

Every picker implementation (Modal, Embedded, XYField, ...) is an operator
and follows the same contract:

- On open, the current palette parameters are read from `LPC_PaletteParams`
  (see `params_from_scene`).
- On selection, the picker reports the chosen cell through
  `set_picked_cell(context, x, y)` -- the common callback. It writes
  `context.window_manager.lpc_picker_result` (`LPC_PickerResult`) and
  applies the pick to the current selection immediately (live assign);
  the picker operator finishes with `{'FINISHED'}`.
- On cancel (Escape, right-click, click outside), `lpc_picker_result` is
  NOT changed, and the operator finishes with `{'CANCELLED'}`.
- The picker NEVER returns a color (Invariant 4) -- the color is derived
  exclusively from `model.palette.color_at(x, y, params)`.

Manual x/y edits in the panel are the XYFieldPicker and live-apply too
(via the property update callbacks). Programmatic result writes that must
NOT paint (Sample, grid clamping) go through `set_picked_cell(...,
live=False)` / the suppression flag.
"""

try:
    import bpy
except ModuleNotFoundError:  # plain-python tests without Blender
    bpy = None

try:
    from .. import constants
    from ..model import palette
except ImportError:  # plain-python tests put the addon dir on sys.path
    import constants
    from model import palette

# True while the result is being written programmatically -- the x/y
# update callbacks must not live-apply then (Sample would repaint the
# sampled face, a grid clamp would repaint on palette resize).
_suppress_live_apply = False


def apply_picked_cell(context):
    """Assign the current brush to the selection (picking a color applies
    directly). A silent no-op without a complete brush or
    without a selection. Lazy import: ops imports this module."""
    from ..ops import assign_sample

    assign_sample.assign_current(context)


def set_picked_cell(context, x, y, live=True):
    """The layer-2 common callback: write the picked cell to the shared
    result and (by default) apply it to the selection. Pickers and
    Sample write the result through here, never property by property --
    the update callbacks would live-apply a half-written (x, y) pair."""
    global _suppress_live_apply
    result = context.window_manager.lpc_picker_result
    _suppress_live_apply = True
    try:
        result.x = x
        result.y = y
    finally:
        _suppress_live_apply = False
    if live:
        apply_picked_cell(context)


def _clamp_result_xy(self, context):
    """Clamp the picked cell to the current grid bounds, then live-apply.

    Runs on manual x/y edits in the panel (the XYFieldPicker path) AND on
    grid-size changes in the palette params, so the result always names a
    valid cell. The clamp assignments are suppressed so the re-triggered
    callback neither recurses nor paints half-written state.
    """
    global _suppress_live_apply
    params = params_from_scene(context.scene)
    cols, rows = palette.cell_count(params)
    x = min(max(self.x, 0), cols - 1)
    y = min(max(self.y, 0), rows - 1)
    if x != self.x or y != self.y:
        outer = _suppress_live_apply
        _suppress_live_apply = True
        try:
            if x != self.x:
                self.x = x
            if y != self.y:
                self.y = y
        finally:
            _suppress_live_apply = outer
    if not _suppress_live_apply:
        apply_picked_cell(context)


def _grid_params_changed(self, context):
    """Keep an already picked cell valid when the grid shrinks (suppressed:
    resizing the palette must never repaint the selection), AND regenerate
    the palette image -- a dimension change invalidates the image's size,
    not just the picked cell."""
    global _suppress_live_apply
    result = context.window_manager.lpc_picker_result
    if result.x >= 0 and result.y >= 0:
        outer = _suppress_live_apply
        _suppress_live_apply = True
        try:
            _clamp_result_xy(result, context)
        finally:
            _suppress_live_apply = outer
    from ..ui import preview_material
    from ..ui import geometry_nodes

    preview_material.update_palette_image(context.scene)
    geometry_nodes.update_lpc_geo_node_group(context.scene)


def _palette_image_changed(self, context):
    """A palette color-tuning param changed (saturation/brightness/tint/
    shade) -> regenerate the palette image. No clamp needed here (the cell
    count doesn't change); unlike `_grid_params_changed`'s mesh-data-affecting
    siblings, every already-painted face's lpc_uv0 names a (x, y) cell that
    stays valid -- only the COLOR at that cell changes, automatically
    "repainting" every face with zero mesh traversal."""
    from ..ui import preview_material

    preview_material.update_palette_image(context.scene)


if bpy is not None:
    class LPC_PaletteParams(bpy.types.PropertyGroup):
        """Palette parameters (layer-1 `params`), project-wide (Scene)."""

        cols: bpy.props.IntProperty(
            name="Columns", default=constants.DEFAULT_PALETTE_COLS, min=1, max=64,
            description="Number of hue columns (excluding the optional greyscale column)",
            update=_grid_params_changed,
        )
        rows: bpy.props.IntProperty(
            name="Rows", default=constants.DEFAULT_PALETTE_ROWS, min=1, max=64,
            description="Number of rows",
            update=_grid_params_changed,
        )
        add_greyscale: bpy.props.BoolProperty(
            name="Add Greyscale Column",
            default=constants.DEFAULT_PALETTE_ADD_GREYSCALE,
            description="Prepend an extra column with a plain white-to-black ramp",
            update=_grid_params_changed,
        )
        saturation: bpy.props.FloatProperty(
            name="Saturation", default=constants.DEFAULT_PALETTE_SATURATION,
            min=0.0, max=1.0,
            description="Saturation of the middle row (base color)",
            update=_palette_image_changed,
        )
        brightness: bpy.props.FloatProperty(
            name="Brightness", default=constants.DEFAULT_PALETTE_BRIGHTNESS,
            min=0.0, max=1.0,
            description="Brightness of the middle row (base color)",
            update=_palette_image_changed,
        )
        tint: bpy.props.FloatProperty(
            name="Tint", default=constants.DEFAULT_PALETTE_TINT, min=0.0, max=1.0,
            description="How much the lightest row (row 0) is mixed toward white (0 = like the middle row, 1 = white)",
            update=_palette_image_changed,
        )
        shade: bpy.props.FloatProperty(
            name="Shade", default=constants.DEFAULT_PALETTE_SHADE, min=0.0, max=1.0,
            description="How much the darkest row (the last one) is mixed toward black (0 = like the middle row, 1 = black)",
            update=_palette_image_changed,
        )


def _result_color_get(self):
    """Live-derived swatch color for the picked cell (Invariant 4: colors
    come exclusively from `palette.color_at`, never stored)."""
    try:
        scene = getattr(bpy.context, "scene", None)
        if scene is None:
            return (0.0, 0.0, 0.0, 1.0)
        params = params_from_scene(scene)
        cols, rows = palette.cell_count(params)
        if not (0 <= self.x < cols and 0 <= self.y < rows):
            return (0.0, 0.0, 0.0, 1.0)
        return palette.color_at(self.x, self.y, params)
    except Exception:
        return (0.0, 0.0, 0.0, 1.0)


if bpy is not None:
    class LPC_PickerResult(bpy.types.PropertyGroup):
        """Shared result of all picker variants: the chosen cell (x, y).

        Defaults to cell (0, 0) so a fresh file already has a usable brush
        (no empty -1/-1 state); -1 stays a legal value the grid clamp can pass
        through transiently. `x`/`y` are directly editable in the panel (the
        XYField way of picking) and are clamped live to the grid.
        """

        x: bpy.props.IntProperty(name="X", default=0, min=-1, update=_clamp_result_xy)
        y: bpy.props.IntProperty(name="Y", default=0, min=-1, update=_clamp_result_xy)
        color: bpy.props.FloatVectorProperty(
            name="Color", subtype="COLOR", size=4, min=0.0, max=1.0,
            get=_result_color_get,  # read-only: derived, never stored
            description="Color of the picked palette cell",
            # NOTE: the swatch never shows the LITERAL colour -- Blender draws
            # every UI colour button through the scene view transform (AgX by
            # default), so linear white renders as grey. The stored value is
            # correct (hover shows it); no property subtype bypasses the view
            # transform. The modal picker grid shows the true colours.
        )


def params_from_scene(scene):
    """Read the scene's `LPC_PaletteParams` as a layer-1 `params` dict."""
    p = scene.lpc_palette_params
    return {
        "cols": p.cols,
        "rows": p.rows,
        "add_greyscale": p.add_greyscale,
        "saturation": p.saturation,
        "brightness": p.brightness,
        "tint": p.tint,
        "shade": p.shade,
    }

