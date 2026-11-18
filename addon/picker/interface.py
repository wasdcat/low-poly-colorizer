# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Layer 2: picker contract and the palette as scene data.

Every picker implementation (Modal, Embedded, XYField, ...) is an operator
and follows the same contract:

- On open, the current palette is read from the scene (`params_from_scene`,
  a layer-1 palette dict).
- On selection, the picker reports the chosen cell through
  `set_picked_cell(context, x, y)` -- the common callback. It writes
  `context.window_manager.lpc_picker_result` (`LPC_PickerResult`) and
  applies the pick to the current selection immediately (live assign);
  the picker operator finishes with `{'FINISHED'}`.
- On cancel (Escape, right-click, click outside), `lpc_picker_result` is
  NOT changed, and the operator finishes with `{'CANCELLED'}`.
- The picker NEVER returns a color (Invariant 4) -- the color is derived
  exclusively from `model.palette.color_at(x, y, palette)`.

Manual x/y edits in the panel are the XYFieldPicker and live-apply too
(via the property update callbacks). Programmatic result writes that must
NOT paint (Sample, grid clamping) go through `set_picked_cell(...,
live=False)` / the suppression flag.

The palette lives in `scene.lpc_palette_params` (`LPC_PaletteParams`):
groups of columns plus the global values. `palette_from_props` /
`write_palette` convert between the properties and the layer-1 dict. A
scene whose palette was never written (`initialized` False) reads as the
default template (`default_palette`).
"""

try:
    import bpy
except ModuleNotFoundError:  # plain-python tests without Blender
    bpy = None

try:
    from .. import constants  # noqa: F401  (kept for callers' convenience)
    from ..model import palette
    from ..model import templates
except ImportError:  # plain-python tests put the addon dir on sys.path
    import constants  # noqa: F401
    from model import palette
    from model import templates

# True while the result is being written programmatically -- the x/y
# update callbacks must not live-apply then (Sample would repaint the
# sampled face, a grid clamp would repaint on palette resize).
_suppress_live_apply = False

# True while `write_palette` fills the properties -- the per-property
# update callbacks must not refresh images for every single field then.
_suppress_palette_updates = False


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
    palette changes, so the result always names a valid cell. The clamp
    assignments are suppressed so the re-triggered callback neither
    recurses nor paints half-written state.
    """
    global _suppress_live_apply
    cols, rows = palette.cell_count(params_from_scene(context.scene))
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


def _palette_changed(self, context):
    """Any palette property changed -> keep the picked cell inside the grid
    and regenerate everything derived from the palette. Painted faces are
    NOT remapped here: structural edits are committed (and remapped) when
    the Settings dialog is confirmed (ops/palette.py)."""
    if _suppress_palette_updates:
        return
    refresh_palette_consumers(context)


def refresh_palette_consumers(context):
    """Re-clamp the picked cell (suppressed: a palette edit must never
    repaint the selection) and rebuild the palette image and the Geometry
    Node group."""
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


def _column_cell(self, where):
    """Cell of this column's ramp in the current palette (display only):
    where = "first" | "middle" | "last" -- over the whole ramp, i.e. both
    grid columns with span 2."""
    try:
        pal = params_from_scene(bpy.context.scene)
        rows = pal["rows"]
        for x, (column, _part) in enumerate(palette.grid_columns(pal)):
            if column["id"] == self.column_id:
                cells = column.get("span", 1) * rows
                k = {"first": 0, "middle": cells // 2, "last": cells - 1}[where]
                return palette.color_at(x + k // rows, k % rows, pal)
    except Exception:
        pass
    return (0.0, 0.0, 0.0, 1.0)


def _column_preview_first_get(self):
    return _column_cell(self, "first")


def _column_preview_get(self):
    return _column_cell(self, "middle")


def _column_preview_last_get(self):
    return _column_cell(self, "last")


if bpy is not None:
    class LPC_PaletteColumn(bpy.types.PropertyGroup):
        """One palette column: a ramp of `rows` cells (2 x rows with span 2).
        `name` (inherited) is its label."""

        column_id: bpy.props.StringProperty(
            name="ID",
            description="Stable id of the column, used to keep painted faces "
            "on their color when the palette layout changes",
        )
        hue: bpy.props.FloatProperty(
            name="Hue", default=0.0, min=0.0, max=360.0, precision=1,
            description="OKLCH hue in degrees",
            update=_palette_changed,
        )
        use_chroma: bpy.props.BoolProperty(
            name="Own Chroma", default=False,
            description="Use an own chroma instead of the group's",
            update=_palette_changed,
        )
        chroma: bpy.props.FloatProperty(
            name="Chroma", default=0.1, min=0.0, max=palette.MAX_CHROMA,
            precision=3, step=0.1,
            description="OKLCH peak chroma (0 = neutral grey)",
            update=_palette_changed,
        )
        span: bpy.props.IntProperty(
            name="Span", default=1, min=1, max=palette.MAX_SPAN,
            description="Grid columns this ramp covers (2 = one ramp over "
            "twice the rows, e.g. a long grey scale)",
            update=_palette_changed,
        )
        preview_color: bpy.props.FloatVectorProperty(
            name="Preview", subtype="COLOR_GAMMA", size=4, min=0.0, max=1.0,
            get=_column_preview_get,  # derived, never stored
            description="Middle color of this column",
        )
        preview_first: bpy.props.FloatVectorProperty(
            name="Preview First", subtype="COLOR_GAMMA", size=4, min=0.0, max=1.0,
            get=_column_preview_first_get,  # derived, never stored
            description="First (lightest) color of this column",
        )
        preview_last: bpy.props.FloatVectorProperty(
            name="Preview Last", subtype="COLOR_GAMMA", size=4, min=0.0, max=1.0,
            get=_column_preview_last_get,  # derived, never stored
            description="Last (darkest) color of this column",
        )

    class LPC_PaletteGroup(bpy.types.PropertyGroup):
        """A group of columns: heading in the picker, chroma default for its
        columns, optional own lightness range. `name` (inherited) is the
        heading."""

        chroma: bpy.props.FloatProperty(
            name="Chroma", default=0.1, min=0.0, max=palette.MAX_CHROMA,
            precision=3, step=0.1,
            description="OKLCH peak chroma of every column without an own value",
            update=_palette_changed,
        )
        use_l_top: bpy.props.BoolProperty(
            name="Own Lightest", default=False,
            description="Use an own lightness for the first cell of the ramps",
            update=_palette_changed,
        )
        l_top: bpy.props.FloatProperty(
            name="Lightest", default=palette.DEFAULT_L_TOP, min=0.0, max=1.0,
            description="OKLab lightness of the first cell of each ramp",
            update=_palette_changed,
        )
        use_l_bottom: bpy.props.BoolProperty(
            name="Own Darkest", default=False,
            description="Use an own lightness for the last cell of the ramps",
            update=_palette_changed,
        )
        l_bottom: bpy.props.FloatProperty(
            name="Darkest", default=palette.DEFAULT_L_BOTTOM, min=0.0, max=1.0,
            description="OKLab lightness of the last cell of each ramp",
            update=_palette_changed,
        )
        columns: bpy.props.CollectionProperty(type=LPC_PaletteColumn)
        columns_active: bpy.props.IntProperty(name="Active Column", default=0, min=0)

    class LPC_PaletteParams(bpy.types.PropertyGroup):
        """The palette, project-wide (Scene). The inherited `name` is the
        palette's display name (from its template or LPC file; shown in the
        Settings dialog and on the exported cheatsheet)."""

        groups: bpy.props.CollectionProperty(type=LPC_PaletteGroup)
        groups_active: bpy.props.IntProperty(name="Active Group", default=0, min=0)
        rows: bpy.props.IntProperty(
            name="Rows", default=palette.DEFAULT_ROWS, min=1, max=palette.MAX_ROWS,
            description="Number of rows (cells per ramp)",
            update=_palette_changed,
        )
        l_top: bpy.props.FloatProperty(
            name="Lightest", default=palette.DEFAULT_L_TOP, min=0.0, max=1.0,
            description="OKLab lightness of the first row",
            update=_palette_changed,
        )
        l_bottom: bpy.props.FloatProperty(
            name="Darkest", default=palette.DEFAULT_L_BOTTOM, min=0.0, max=1.0,
            description="OKLab lightness of the last row",
            update=_palette_changed,
        )
        tint: bpy.props.FloatProperty(
            name="Tint", default=palette.DEFAULT_TINT, min=0.0, max=1.0,
            description="How much chroma fades toward the lightest row",
            update=_palette_changed,
        )
        shade: bpy.props.FloatProperty(
            name="Shade", default=palette.DEFAULT_SHADE, min=0.0, max=1.0,
            description="How much chroma fades toward the darkest row",
            update=_palette_changed,
        )
        hue_shift: bpy.props.FloatProperty(
            name="Hue Shift", default=palette.DEFAULT_HUE_SHIFT,
            min=-1.0, max=1.0,
            description="Shift highlights toward warm/cool and shadows toward the opposite (0 = none, + = warm highlights / cool shadows)",
            update=_palette_changed,
        )
        warmth: bpy.props.FloatProperty(
            name="Warmth", default=palette.DEFAULT_WARMTH,
            min=-1.0, max=1.0,
            description="Global color temperature bias (-1 = cool / blue, +1 = warm / amber)",
            update=_palette_changed,
        )
        next_column_id: bpy.props.IntProperty(
            name="Next Column ID", default=1, min=1,
            description="Counter for the ids of new columns",
        )
        initialized: bpy.props.BoolProperty(
            name="Initialized", default=False,
            description="The palette has been written into this scene "
            "(from a template or a file)",
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


# EnumProperty items must outlive the callback (Blender keeps no copy of the
# strings), so the last list handed out is held here.
_column_items = []


def _result_column_items(self, context):
    """One item per grid column, value = x, named like the picker hover
    label / the Godot `palette_cell_x` drop-down ("Nature · Moss")."""
    global _column_items
    try:
        labels = palette.grid_column_labels(params_from_scene(context.scene))
    except Exception:
        labels = []
    _column_items = [(str(x), label, "", x) for x, label in enumerate(labels)]         or [("0", "(no columns)", "", 0)]
    return _column_items


def _result_column_get(self):
    return max(self.x, 0)


def _result_column_set(self, value):
    # Through `x`, so its update (clamp + live-apply to the selection)
    # runs exactly as for a manual X edit.
    self.x = value


if bpy is not None:
    class LPC_PickerResult(bpy.types.PropertyGroup):
        """Shared result of all picker variants: the chosen cell (x, y).

        Defaults to cell (0, 0) so a fresh file already has a usable brush
        (no empty -1/-1 state); -1 stays a legal value the grid clamp can pass
        through transiently. `x`/`y` are directly editable in the panel (the
        XYField way of picking) and are clamped live to the grid.
        """

        x: bpy.props.IntProperty(name="X", default=0, min=-1, update=_clamp_result_xy)
        y: bpy.props.IntProperty(name="Row", default=0, min=-1, update=_clamp_result_xy,
                                 description="Row of the picked cell (0 = first row)")
        # The panel's view of `x`: the column by name instead of a number.
        column: bpy.props.EnumProperty(
            name="Column", items=_result_column_items,
            get=_result_column_get, set=_result_column_set,
            description="Column of the picked cell",
        )
        color: bpy.props.FloatVectorProperty(
            name="Color", subtype="COLOR_GAMMA", size=4, min=0.0, max=1.0,
            get=_result_color_get,  # read-only: derived, never stored
            description="Color of the picked palette cell",
            # COLOR_GAMMA: `color_at` returns gamma-encoded sRGB, and this
            # subtype shows the value as such -- no scene view transform
            # (AgX), so the swatch matches the modal picker grid. Same for
            # every other palette swatch (column previews, remap dialog).
        )


# --------------------------------------------------------------------------
# Palette <-> properties (duck-typed: works on SimpleNamespace in tests)
# --------------------------------------------------------------------------

def palette_from_props(p):
    """The layer-1 palette dict of an `LPC_PaletteParams`."""
    groups = []
    for g in p.groups:
        groups.append({
            "name": g.name,
            "chroma": g.chroma,
            "l_top": g.l_top if g.use_l_top else None,
            "l_bottom": g.l_bottom if g.use_l_bottom else None,
            "columns": [{
                "id": c.column_id,
                "name": c.name,
                "hue": c.hue,
                "chroma": c.chroma if c.use_chroma else None,
                "span": c.span,
            } for c in g.columns],
        })
    return {
        "groups": groups,
        "rows": p.rows,
        "l_top": p.l_top,
        "l_bottom": p.l_bottom,
        "tint": p.tint,
        "shade": p.shade,
        "hue_shift": p.hue_shift,
        "warmth": p.warmth,
    }


def _usable(pal):
    try:
        palette.validate_palette(pal)
    except ValueError:
        return False
    return True


_default_template_cache = None


def default_palette():
    """The default template's palette (cached; a fresh copy each call)."""
    global _default_template_cache
    if _default_template_cache is None:
        _default_template_cache = templates.load_template(templates.DEFAULT_TEMPLATE)
    return _copy_palette(_default_template_cache)


def _copy_palette(pal):
    copied = dict(pal)
    copied["groups"] = [dict(g, columns=[dict(c) for c in g["columns"]])
                        for g in pal["groups"]]
    return copied


def params_from_scene(scene):
    """The scene's palette as a layer-1 palette dict."""
    p = scene.lpc_palette_params
    if getattr(p, "initialized", False):
        pal = palette_from_props(p)
        if _usable(pal):
            return pal
    return default_palette()


def new_column_id(p, existing=()):
    """A fresh column id ("c<n>") not used in `p` nor in `existing`."""
    used = {c.column_id for g in p.groups for c in g.columns} | set(existing)
    while True:
        cid = "c%d" % p.next_column_id
        p.next_column_id += 1
        if cid not in used:
            return cid


def write_palette(p, pal):
    """Replace the palette in `p` (an `LPC_PaletteParams`) with `pal`,
    without per-field update callbacks; marks it initialized. The caller
    refreshes the consumers once (`refresh_palette_consumers`)."""
    global _suppress_palette_updates
    outer = _suppress_palette_updates
    _suppress_palette_updates = True
    try:
        p.groups.clear()
        for gdata in pal["groups"]:
            g = p.groups.add()
            g.name = gdata["name"]
            g.chroma = gdata.get("chroma", 0.0)
            g.use_l_top = gdata.get("l_top") is not None
            if g.use_l_top:
                g.l_top = gdata["l_top"]
            g.use_l_bottom = gdata.get("l_bottom") is not None
            if g.use_l_bottom:
                g.l_bottom = gdata["l_bottom"]
            for cdata in gdata["columns"]:
                c = g.columns.add()
                c.name = cdata["name"]
                c.column_id = cdata["id"]
                c.hue = cdata["hue"]
                c.use_chroma = cdata.get("chroma") is not None
                if c.use_chroma:
                    c.chroma = cdata["chroma"]
                c.span = cdata.get("span", 1)
            g.columns_active = 0
        p.groups_active = 0
        p.rows = pal["rows"]
        for key, default in (("l_top", palette.DEFAULT_L_TOP),
                             ("l_bottom", palette.DEFAULT_L_BOTTOM),
                             ("tint", palette.DEFAULT_TINT),
                             ("shade", palette.DEFAULT_SHADE),
                             ("hue_shift", palette.DEFAULT_HUE_SHIFT),
                             ("warmth", palette.DEFAULT_WARMTH)):
            setattr(p, key, pal.get(key, default))
        p.initialized = True
    finally:
        _suppress_palette_updates = outer


def ensure_palette_initialized(scene):
    """Write the default template into a scene that has no palette yet.
    Returns True if it wrote. Must run outside draw callbacks (load
    handler, timer, operators)."""
    p = scene.lpc_palette_params
    if p.initialized:
        return False
    write_palette(p, default_palette())
    p.name = templates.template_name(templates.DEFAULT_TEMPLATE)
    return True
