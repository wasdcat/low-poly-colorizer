# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Layer 1: palette model (pure logic, UI-free).

`color_at` is the single source of truth for cell colors (Invariant 4 in
ARCHITECTURE.md). All picker variants and the preview compute colors exclusively
here, never on their own -- this guarantees identical results regardless of
the picker implementation.

The palette is not stored (procedurally reproducible from `params`).

Grid layout:
    - `cols` is the number of hue columns, evenly spaced around the color
      wheel.
    - If `add_greyscale` is set, an extra column 0 is prepended: a plain
      white-to-black ramp, independent of the other parameters. The hue
      columns then occupy 1..cols.
    - The middle row is the base color (`saturation`/`brightness`). Rows above
      it blend toward white by up to `tint`, rows below it blend toward
      black by up to `shade`.

`params` is a mapping with the keys:
    cols, rows       -- grid dimensions (int, >= 1); `cols` counts only the
                         hue columns, independent of `add_greyscale`
    add_greyscale    -- bool, prepend a white-to-black column
    saturation       -- 0..1, saturation of the middle row (base color)
    brightness       -- 0..1, brightness of the middle row (base color)
    tint             -- 0..1, how much the top row is mixed toward white
                         (0 = like the middle row, 1 = white)
    shade            -- 0..1, how much the bottom row is mixed toward black
                         (0 = like the middle row, 1 = black)
"""

import colorsys


def cell_count(params):
    """(cols, rows) for the given palette parameters, including the
    optional greyscale column in `cols`."""
    cols = params["cols"]
    if params["add_greyscale"]:
        cols += 1
    return cols, params["rows"]


def color_at(x, y, params):
    """Deterministic RGBA color for cell (x, y), values in [0, 1].

    If `add_greyscale` is set, column 0 is a grayscale ramp from white
    (top) to black (bottom). The remaining columns select a hue from the
    full color wheel; the middle row is the base color
    (`saturation`/`brightness`), fanning out toward white (`tint`) above and
    toward black (`shade`) below.
    """
    cols, rows = cell_count(params)
    if not (0 <= x < cols):
        raise ValueError(f"x={x} out of range 0..{cols - 1}")
    if not (0 <= y < rows):
        raise ValueError(f"y={y} out of range 0..{rows - 1}")

    t = y / (rows - 1) if rows > 1 else 0.5  # 0 = top (light) .. 1 = bottom (dark)

    has_greyscale = params["add_greyscale"]
    if has_greyscale and x == 0:
        v = 1.0 - t
        return (v, v, v, 1.0)

    saturation = params["saturation"]
    brightness = params["brightness"]
    tint = params["tint"]
    shade = params["shade"]

    hue_index = x - 1 if has_greyscale else x
    hue = hue_index / params["cols"]

    if t <= 0.5:
        row_factor = 1.0 - t / 0.5  # 1 = topmost .. 0 = middle
        s = saturation * (1.0 - tint * row_factor)
        v = brightness + (1.0 - brightness) * tint * row_factor
    else:
        row_factor = (t - 0.5) / 0.5  # 0 = middle .. 1 = bottommost
        s = saturation + (1.0 - saturation) * shade * row_factor
        v = brightness * (1.0 - shade * row_factor)

    s = max(0.0, min(1.0, s))
    v = max(0.0, min(1.0, v))
    r, g, b = colorsys.hsv_to_rgb(hue, s, v)
    return (r, g, b, 1.0)


def build_pixels(params):
    """Flat row-major RGBA float buffer for the whole grid, one texel per
    cell, plus its (cols, rows) -- the palette as a texture instead of a
    procedure. The single place `color_at` becomes pixels, shared by the
    Blender-preview palette image and the exported PNG (ui/preview_material.py,
    export/exporter.py) so both consumers render identical colors by
    construction, exactly as `color_at` already guarantees for the picker.

    Row order matches Blender's `Image.pixels` convention (row 0 = bottom of
    the image). `model/faces.palette_uv`/`decode_palette_uv` must address this
    SAME convention -- they do, by sharing the (x, y) -> (cols, rows)-relative
    cell indexing this function and `color_at` both use.
    """
    cols, rows = cell_count(params)
    pixels = [0.0] * (cols * rows * 4)
    for y in range(rows):
        for x in range(cols):
            i = (y * cols + x) * 4
            pixels[i:i + 4] = color_at(x, y, params)
    return pixels, cols, rows


def nearest_cell(color, params):
    """Cell (x, y) whose `color_at` result is closest to `color` (r,g,b[,a]).

    Brute-force over all cells -- palettes are small (typically < 200
    cells), and this is the only way to guarantee consistency with
    `color_at` by construction.
    """
    cols, rows = cell_count(params)
    best = None
    best_dist = None
    for y in range(rows):
        for x in range(cols):
            r, g, b, _a = color_at(x, y, params)
            dist = (r - color[0]) ** 2 + (g - color[1]) ** 2 + (b - color[2]) ** 2
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = (x, y)
    return best

