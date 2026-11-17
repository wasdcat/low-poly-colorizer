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
    color_mode       -- 'HSV' or 'OKLCH' (default 'HSV')
    hue_shift        -- -1..1, temperature drift across vertical rows (default 0.0)
    warmth           -- -1..1, global temperature bias (default 0.0)
"""

import colorsys
import math


def _oklab_to_srgb(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3

    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_val = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    def to_srgb(c):
        c = max(0.0, min(1.0, c))
        return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055

    return (to_srgb(r), to_srgb(g), to_srgb(b_val))


def _oklch_to_rgb_clamped(L, C, h_deg):
    h_rad = math.radians(h_deg)
    cur_c = C
    for _ in range(8):
        a = cur_c * math.cos(h_rad)
        b = cur_c * math.sin(h_rad)
        l_ = L + 0.3963377774 * a + 0.2158037573 * b
        m_ = L - 0.1055613458 * a - 0.0638541728 * b
        s_ = L - 0.0894841775 * a - 1.2914855480 * b
        l = l_ ** 3
        m = m_ ** 3
        s = s_ ** 3
        r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
        g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
        b_val = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
        if -0.01 <= r <= 1.01 and -0.01 <= g <= 1.01 and -0.01 <= b_val <= 1.01:
            break
        cur_c *= 0.85
    return _oklab_to_srgb(L, cur_c * math.cos(h_rad), cur_c * math.sin(h_rad))


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

    color_mode = params.get("color_mode", "HSV")
    hue_shift = float(params.get("hue_shift", 0.0))
    warmth = float(params.get("warmth", 0.0))

    has_greyscale = params["add_greyscale"]
    if has_greyscale and x == 0:
        if color_mode == "OKLCH":
            L = max(0.0, min(1.0, (0.95 - 0.75 * t) * params["brightness"]))
            cool = (t - 0.5) * 0.02 * hue_shift
            warm_bias = warmth * 0.01
            r, g, b = _oklab_to_srgb(L, warm_bias - cool * 0.4, warm_bias - cool * 0.8)
            return (r, g, b, 1.0)
        elif hue_shift != 0.0 or warmth != 0.0:
            v = 1.0 - t
            tint_cool = (0.5 - t) * 0.05 * hue_shift
            w = warmth * 0.04
            r = max(0.0, min(1.0, v + tint_cool * 0.5 + w))
            g = max(0.0, min(1.0, v + w * 0.5))
            b = max(0.0, min(1.0, v - tint_cool * 0.8 - w))
            return (r, g, b, 1.0)
        else:
            v = 1.0 - t
            return (v, v, v, 1.0)

    saturation = params["saturation"]
    brightness = params["brightness"]
    tint = params["tint"]
    shade = params["shade"]

    hue_index = x - 1 if has_greyscale else x
    base_hue = hue_index / params["cols"]

    if color_mode == "OKLCH":
        base_h_deg = (base_hue * 360.0 + warmth * 30.0) % 360.0
        warm_pole = 95.0
        cool_pole = 265.0
        if t <= 0.5:
            rf = 1.0 - t / 0.5
            shift_dir = 1.0 if hue_shift >= 0 else -1.0
            target_pole = warm_pole if shift_dir > 0 else cool_pole
            diff = (target_pole - base_h_deg + 180.0) % 360.0 - 180.0
            h = (base_h_deg + diff * (0.22 * abs(hue_shift) * rf)) % 360.0
            C = 0.16 * saturation * (1.0 - 0.50 * tint * rf)
        else:
            rf = (t - 0.5) / 0.5
            shift_dir = 1.0 if hue_shift >= 0 else -1.0
            target_pole = cool_pole if shift_dir > 0 else warm_pole
            diff = (target_pole - base_h_deg + 180.0) % 360.0 - 180.0
            h = (base_h_deg + diff * (0.28 * abs(hue_shift) * rf)) % 360.0
            C = 0.16 * saturation * (1.0 - 0.25 * shade * rf)

        L = max(0.02, min(0.98, (0.94 - 0.72 * t) * brightness))
        r, g, b = _oklch_to_rgb_clamped(L, C, h)
        return (r, g, b, 1.0)

    else:
        # HSV
        h = (base_hue + warmth * 0.08) % 1.0
        warm_pole = 0.14
        cool_pole = 0.68
        if t <= 0.5:
            rf = 1.0 - t / 0.5
            if hue_shift != 0.0:
                target_pole = warm_pole if hue_shift > 0 else cool_pole
                diff = (target_pole - h + 0.5) % 1.0 - 0.5
                h = (h + diff * (0.16 * abs(hue_shift) * rf)) % 1.0
            s = saturation * (1.0 - tint * rf)
            v = brightness + (1.0 - brightness) * tint * rf
        else:
            rf = (t - 0.5) / 0.5
            if hue_shift != 0.0:
                target_pole = cool_pole if hue_shift > 0 else warm_pole
                diff = (target_pole - h + 0.5) % 1.0 - 0.5
                h = (h + diff * (0.22 * abs(hue_shift) * rf)) % 1.0
            tame = (1.0 - 0.25 * abs(hue_shift)) if hue_shift != 0.0 else 1.0
            s = (saturation + (1.0 - saturation) * shade * rf) * tame
            v = brightness * (1.0 - shade * rf)

        s = max(0.0, min(1.0, s))
        v = max(0.0, min(1.0, v))
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
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

