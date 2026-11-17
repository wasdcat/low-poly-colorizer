# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Shared cell<->pixel geometry helper (Invariant 5 in ARCHITECTURE.md).

Drawing and hit-testing MUST use the same transform formula, otherwise the
hit area drifts apart from the drawn swatch -- this is the main source of
bugs with zoom/pan/HiDPI. Both directions are combined here in ONE module:

    screen = origin + pan + (cell + gaps_before(cell) * gap) * size
    cell   = floor((screen - origin - pan) / size - gaps_before * gap)
    size   = swatch_size * zoom * ui_scale

Palette groups are separated by a gap of `gap` cells in x: `group_starts`
lists the first grid column of every group but the first. A point inside
a gap hits no cell.

Pure Python logic, no bpy dependency -- testable with plain `python`, not
just inside Blender.
"""

import math
from dataclasses import dataclass, field


@dataclass
class PickerGeometry:
    """State for a picker session: origin, pan, zoom, base size."""

    origin_x: float
    origin_y: float
    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom: float = 1.0
    swatch_size: float = 24.0  # base size in pixels at zoom=1, ui_scale=1
    ui_scale: float = 1.0
    group_starts: tuple = field(default_factory=tuple)  # sorted, all > 0
    gap: float = 0.5  # gap between groups, in cells

    def _gaps_before(self, cell_x):
        """Number of group gaps left of grid line `cell_x`."""
        return sum(1 for s in self.group_starts if s <= cell_x)

    def grid_width_cells(self, cols):
        """Width of a `cols`-column grid in cells, gaps included."""
        return cols + self._gaps_before(cols) * self.gap

    @property
    def cell_size(self):
        return self.swatch_size * self.zoom * self.ui_scale

    def cell_to_screen(self, cell_x, cell_y):
        """Screen position (pixels) of cell corner (cell_x, cell_y)."""
        size = self.cell_size
        x = self.origin_x + self.pan_x + (cell_x + self._gaps_before(cell_x) * self.gap) * size
        y = self.origin_y + self.pan_y + cell_y * size
        return x, y

    def screen_to_cell(self, screen_x, screen_y):
        """Cell under the screen position (screen_x, screen_y); x is -1 inside
        a gap between groups."""
        size = self.cell_size
        u = (screen_x - self.origin_x - self.pan_x) / size
        gaps = 0
        for start in self.group_starts:
            if u >= start + (gaps + 1) * self.gap:
                gaps += 1           # right of this gap
            elif u >= start + gaps * self.gap:
                u = None            # inside this gap
                break
            else:
                break
        cell_x = -1 if u is None else math.floor(u - gaps * self.gap)
        cell_y = math.floor((screen_y - self.origin_y - self.pan_y) / size)
        return cell_x, cell_y

    def cell_rect(self, cell_x, cell_y):
        """(x0, y0, x1, y1) of the swatch rectangle for cell (cell_x, cell_y)."""
        x0, y0 = self.cell_to_screen(cell_x, cell_y)
        size = self.cell_size
        return x0, y0, x0 + size, y0 + size

    def hit_test(self, screen_x, screen_y, cols, rows):
        """Cell under (screen_x, screen_y), or None if outside the valid
        grid area (cols x rows)."""
        cell_x, cell_y = self.screen_to_cell(screen_x, screen_y)
        if 0 <= cell_x < cols and 0 <= cell_y < rows:
            return cell_x, cell_y
        return None

