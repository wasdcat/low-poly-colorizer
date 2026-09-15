# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Layer 3: ModalPalettePicker -- GPU-drawn viewport overlay.

The primary picker variant (ARCHITECTURE.md decision #5: "Modal-Picker zuerst").
Draws the palette grid as an overlay in the 3D viewport and uses
`picker.geometry.PickerGeometry` for the cell<->pixel transform (Invariant
5) -- the same formula for drawing AND hit-testing, including `ui_scale`.

Controls:
    - Left-click on a cell: selects it, reports (x, y) through
      `interface.set_picked_cell` (layer 2; live-applies to the current
      selection), finishes with FINISHED.
    - Left-click outside the grid / right-click / Escape: cancel
      (CANCELLED), `lpc_picker_result` stays unchanged.
    - Mouse wheel: zoom, centered on the cursor.
    - Middle mouse button + drag: pan.
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from .. import constants
from ..model import palette
from . import geometry
from . import interface

ZOOM_FACTOR = 1.1
ZOOM_MIN = 0.25
ZOOM_MAX = 4.0


class LPC_OT_modal_palette_picker(bpy.types.Operator):
    """Open the palette picker as a GPU overlay and pick a cell (x, y)"""

    bl_idname = "lpc.modal_palette_picker"
    bl_label = "Palette Picker"
    # UNDO: the pick live-assigns to the selection -- picking and the
    # resulting paint must be one undo step.
    bl_options = {"REGISTER", "UNDO"}

    _handle = None

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Palette picker requires the 3D viewport")
            return {"CANCELLED"}

        # The trigger button lives in the N-panel ("UI" region), but the
        # overlay is drawn in the 3D viewport's "WINDOW" region.
        # event.mouse_region_x/y is relative to the region that triggered
        # the event (i.e. the sidebar) -- used as-is for the WINDOW
        # region's origin, the grid ends up at the wrong position and can
        # (partially) disappear behind the N-panel. So: look up the WINDOW
        # region explicitly and base all coordinates on the screen offset
        # (event.mouse_x/y - region.x/y).
        region = next(
            (r for r in context.area.regions if r.type == "WINDOW"), None
        )
        if region is None:
            self.report({"WARNING"}, "Palette picker: no WINDOW region found")
            return {"CANCELLED"}
        self.region = region

        self.params = interface.params_from_scene(context.scene)
        self.cols, self.rows = palette.cell_count(self.params)

        ui_scale = context.preferences.system.ui_scale
        swatch_size = 24.0
        grid_w = self.cols * swatch_size * ui_scale
        grid_h = self.rows * swatch_size * ui_scale

        # Open centered in the viewport so the grid is always fully visible
        # regardless of the click position (not hidden under a docked
        # sidebar).
        self.geo = geometry.PickerGeometry(
            origin_x=(self.region.width - grid_w) / 2.0,
            origin_y=(self.region.height - grid_h) / 2.0,
            swatch_size=swatch_size,
            ui_scale=ui_scale,
        )
        self.hover = None
        # The cell the brush currently names (lpc_picker_result), marked as a
        # persistent highlight so the picker opens on the active cell. None if
        # it falls outside the current grid (e.g. a transient -1/-1).
        result = context.window_manager.lpc_picker_result
        self.selected = (
            (result.x, result.y)
            if 0 <= result.x < self.cols and 0 <= result.y < self.rows
            else None
        )
        self._panning = False
        self._pan_last = (0, 0)

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw, (), "WINDOW", "POST_PIXEL"
        )
        context.window_manager.modal_handler_add(self)
        self.region.tag_redraw()
        return {"RUNNING_MODAL"}

    def _event_xy(self, event):
        """Convert the mouse position to WINDOW-region-local pixels (Invariant 5)."""
        return event.mouse_x - self.region.x, event.mouse_y - self.region.y

    def modal(self, context, event):
        self.region.tag_redraw()
        mx, my = self._event_xy(event)

        if event.type == "MOUSEMOVE":
            self.hover = self.geo.hit_test(mx, my, self.cols, self.rows)
            if self._panning:
                dx = mx - self._pan_last[0]
                dy = my - self._pan_last[1]
                self.geo.pan_x += dx
                self.geo.pan_y += dy
                self._pan_last = (mx, my)

        elif event.type == "MIDDLEMOUSE":
            if event.value == "PRESS":
                self._panning = True
                self._pan_last = (mx, my)
            elif event.value == "RELEASE":
                self._panning = False

        elif event.type == "WHEELUPMOUSE":
            self._zoom(mx, my, ZOOM_FACTOR)
        elif event.type == "WHEELDOWNMOUSE":
            self._zoom(mx, my, 1.0 / ZOOM_FACTOR)

        elif event.type == "LEFTMOUSE" and event.value == "PRESS":
            cell = self.geo.hit_test(mx, my, self.cols, self.rows)
            self._finish(context)
            if cell is None:
                return {"CANCELLED"}
            interface.set_picked_cell(context, cell[0], cell[1])
            return {"FINISHED"}

        elif event.type in {"RIGHTMOUSE", "ESC"}:
            self._finish(context)
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def _zoom(self, mx, my, factor):
        old_size = self.geo.cell_size
        self.geo.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.geo.zoom * factor))
        new_size = self.geo.cell_size
        ratio = new_size / old_size
        # Adjust pan so the cell under the cursor stays in place.
        self.geo.pan_x = mx - self.geo.origin_x - (mx - self.geo.origin_x - self.geo.pan_x) * ratio
        self.geo.pan_y = my - self.geo.origin_y - (my - self.geo.origin_y - self.geo.pan_y) * ratio

    def _finish(self, context):
        # Idempotent: guard against a double remove (e.g. cancel paths).
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        # Tag ALL regions of the area, not just WINDOW: the N-panel (UI
        # region) shows the picked color and would otherwise only update
        # on the next mouse event over it.
        if context.area is not None:
            for region in context.area.regions:
                region.tag_redraw()

    def _draw(self):
        cols, rows = self.cols, self.rows
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")

        gpu.state.blend_set("ALPHA")

        bx0, by0 = self.geo.cell_to_screen(0, 0)
        bx1, by1 = self.geo.cell_to_screen(cols, rows)

        # Frame: a filled rectangle underneath the grid, enlarged by the
        # frame width -- avoids the frayed corners of stroked line joins.
        fw = constants.PICKER_FRAME_WIDTH * self.geo.ui_scale
        frame_verts = (
            (bx0 - fw, by0 - fw),
            (bx1 + fw, by0 - fw),
            (bx1 + fw, by1 + fw),
            (bx0 - fw, by1 + fw),
        )
        frame_batch = batch_for_shader(shader, "TRI_FAN", {"pos": frame_verts})
        shader.uniform_float("color", constants.PICKER_FRAME_COLOR)
        frame_batch.draw(shader)

        bg_verts = ((bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1))
        bg_batch = batch_for_shader(shader, "TRI_FAN", {"pos": bg_verts})
        shader.uniform_float("color", (0.05, 0.05, 0.05, 0.85))
        bg_batch.draw(shader)

        for y in range(rows):
            for x in range(cols):
                x0, y0, x1, y1 = self.geo.cell_rect(x, y)
                verts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
                color = palette.color_at(x, y, self.params)
                batch = batch_for_shader(shader, "TRI_FAN", {"pos": verts})
                shader.uniform_float("color", color)
                batch.draw(shader)

        # Current cell first (a persistent marker), hover on top -- so hovering
        # the active cell still shows the white hover outline over the amber.
        if self.selected is not None:
            self._outline_cell(self.selected, (0.0, 0.0, 0.0, 1.0), 5.0)
            self._outline_cell(
                self.selected, constants.PICKER_SELECTED_COLOR, 2.5
            )

        if self.hover is not None:
            self._outline_cell(self.hover, (1.0, 1.0, 1.0, 1.0), 2.0)

        gpu.state.blend_set("NONE")

    def _outline_cell(self, cell, color, width):
        """Stroke the outline of `cell` in `color` at `width` pixels (used for
        both the current-cell marker and the hover highlight)."""
        x0, y0, x1, y1 = self.geo.cell_rect(*cell)
        shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
        shader.uniform_float("color", color)
        shader.uniform_float(
            "viewportSize", (self.region.width, self.region.height)
        )
        shader.uniform_float("lineWidth", width)
        verts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))
        batch = batch_for_shader(shader, "LINE_STRIP", {"pos": verts})
        batch.draw(shader)

