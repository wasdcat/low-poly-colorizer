# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Layer 1: remap painted faces when the palette grid changes (pure, no bpy).

`lpc_uv0` stores a cell normalized to the grid size ((x + 0.5) / cols), so
any change of the grid's shape would silently repaint every face. Before a
new palette replaces the old one, `plan_remap` works out where every used
cell of the old grid goes in the new one:

    automatic  -- the old cell's column (by its stable `id`) still exists,
                  the row count is unchanged and the column's ramp still
                  reaches the cell: same column, same ramp position, new x.
                  Adding, moving and widening columns/groups are lossless.
    table      -- every other used cell (deleted column, changed row count,
                  narrower span): one row per old cell with a suggested
                  target, the nearest color in OKLab -- within the same
                  column if it still exists, else over the whole palette.
                  The user may correct each target before applying.

A cell is identified across palettes by (column id, ramp index), the ramp
index being part * rows + y (see `palette.grid_columns`).

`Remap.mapping(overrides)` gives the final old -> new cell dict;
`remap_uv` rewrites one stored `lpc_uv0` value with it. Cells the old grid
can't decode (out of range, e.g. an unpainted face's default UV) are
reported in `Remap.invalid` and left for the caller to skip.
"""

from dataclasses import dataclass, field

from . import faces
from . import palette as model_palette


@dataclass
class TableRow:
    """One old cell that needs a decision: `suggestion` is the pre-filled
    new cell, `faces` how many faces use the old cell (the affected faces
    to report), `column_kept` whether its column still exists."""
    old_cell: tuple
    suggestion: tuple
    faces: int
    column_kept: bool


@dataclass
class Remap:
    old_dims: tuple                                # (cols, rows) of old grid
    new_dims: tuple                                # (cols, rows) of new grid
    automatic: dict = field(default_factory=dict)  # old cell -> new cell
    table: list = field(default_factory=list)      # [TableRow], grid order
    invalid: dict = field(default_factory=dict)    # undecodable cell -> faces

    @property
    def needs_confirmation(self):
        """True if the user has to confirm a table before applying."""
        return bool(self.table)

    @property
    def is_identity(self):
        """True if nothing moves: same grid size, every used cell stays put
        and nothing needs the table -- the faces need no rewrite."""
        return (self.old_dims == self.new_dims and not self.table
                and all(old == new for old, new in self.automatic.items()))

    @property
    def affected_faces(self):
        """Number of faces whose cell goes through the table."""
        return sum(row.faces for row in self.table)

    def mapping(self, overrides=None):
        """Final old cell -> new cell: automatic cells, plus each table row's
        target from `overrides` (old cell -> new cell) or its suggestion.
        Raises ValueError for an override outside the new grid or for an
        old cell that isn't in the table."""
        overrides = overrides or {}
        table_cells = {row.old_cell for row in self.table}
        cols, rows = self.new_dims
        for old, new in overrides.items():
            if old not in table_cells:
                raise ValueError("cell %r is not in the table" % (old,))
            if not (0 <= new[0] < cols and 0 <= new[1] < rows):
                raise ValueError("target %r outside the new %dx%d grid"
                                 % (new, cols, rows))
        result = dict(self.automatic)
        for row in self.table:
            result[row.old_cell] = tuple(overrides.get(row.old_cell, row.suggestion))
        return result


def _cell_keys(palette):
    """Grid cell (x, y) -> (column id, ramp index), for every cell."""
    rows = palette["rows"]
    keys = {}
    for x, (column, part) in enumerate(model_palette.grid_columns(palette)):
        for y in range(rows):
            keys[(x, y)] = (column["id"], part * rows + y)
    return keys


def _column_cells(palette):
    """Column id -> its grid cells in ramp order."""
    rows = palette["rows"]
    cells = {}
    for x, (column, _part) in enumerate(model_palette.grid_columns(palette)):
        cells.setdefault(column["id"], []).extend((x, y) for y in range(rows))
    return cells


def _nearest(lab, candidates, labs):
    """Candidate cell with the smallest OKLab distance to `lab`; the first
    one in the given order on ties."""
    best = None
    best_dist = None
    for cell in candidates:
        L, a, b = labs[cell]
        dist = (L - lab[0]) ** 2 + (a - lab[1]) ** 2 + (b - lab[2]) ** 2
        if best_dist is None or dist < best_dist:
            best, best_dist = cell, dist
    return best


def _labs(palette):
    """Grid cell -> OKLab of its color."""
    cols, rows = model_palette.cell_count(palette)
    return {(x, y): model_palette.srgb_to_oklab(*model_palette.color_at(x, y, palette)[:3])
            for x in range(cols) for y in range(rows)}


def plan_remap(old_palette, new_palette, used_cells=None):
    """Where each used cell of `old_palette` goes in `new_palette` (both
    group/column palettes, see `palette.palette_from_params` for classic
    parameters).

    `used_cells` maps old cell (x, y) -> number of faces using it (e.g. from
    `count_cells`); cells outside the old grid land in `Remap.invalid`.
    None means every cell of the old grid, with 0 faces each."""
    old_cols, old_rows = model_palette.cell_count(old_palette)
    new_cols, new_rows = model_palette.cell_count(new_palette)
    result = Remap((old_cols, old_rows), (new_cols, new_rows))

    old_keys = _cell_keys(old_palette)
    if used_cells is None:
        used_cells = {cell: 0 for cell in old_keys}

    new_columns = _column_cells(new_palette)
    same_rows = old_rows == new_rows
    pending = []
    for cell in sorted(used_cells):
        n_faces = used_cells[cell]
        key = old_keys.get(cell)
        if key is None:
            result.invalid[cell] = n_faces
            continue
        column_id, ramp_index = key
        target_cells = new_columns.get(column_id)
        if same_rows and target_cells is not None and ramp_index < len(target_cells):
            result.automatic[cell] = target_cells[ramp_index]
        else:
            pending.append((cell, n_faces, column_id))

    if pending:
        old_labs = _labs(old_palette)
        new_labs = _labs(new_palette)
        all_new = sorted(new_labs, key=lambda c: (c[0], c[1]))
        for cell, n_faces, column_id in pending:  # grid order (sorted above)
            kept = column_id in new_columns
            candidates = new_columns[column_id] if kept else all_new
            result.table.append(TableRow(
                old_cell=cell,
                suggestion=_nearest(old_labs[cell], candidates, new_labs),
                faces=n_faces,
                column_kept=kept,
            ))
    return result


def count_cells(uvs, cols, rows):
    """Faces per decoded cell, from one stored `lpc_uv0` value per painted
    face -- the `used_cells` input of `plan_remap`."""
    counts = {}
    for uv in uvs:
        cell = faces.decode_palette_uv(uv, cols, rows)
        counts[cell] = counts.get(cell, 0) + 1
    return counts


def remap_uv(uv, remap, mapping):
    """The stored `lpc_uv0` value `uv` (old grid) re-encoded for the new
    grid via `mapping` (from `Remap.mapping`). Returns None if the cell is
    not in `mapping` (undecodable / unused) -- the caller leaves it alone."""
    old_cols, old_rows = remap.old_dims
    new_cols, new_rows = remap.new_dims
    target = mapping.get(faces.decode_palette_uv(uv, old_cols, old_rows))
    if target is None:
        return None
    return faces.encode_palette_uv(target[0], target[1], new_cols, new_rows)
