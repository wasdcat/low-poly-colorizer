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

The palette is not stored as colors (procedurally reproducible from its
description).

A palette is a mapping of groups of columns (docs/plan_palettengruppen.md):

    groups      -- list of groups, in grid order. A group is a mapping
                   name     -- heading in the picker
                   chroma   -- OKLCH peak chroma inherited by columns
                               without their own value (default 0.0)
                   l_top, l_bottom -- optional lightness range of the
                               group's ramps; None/missing = the palette's
                               (each end on its own)
                   columns  -- list of columns, in grid order:
                       id      -- stable, non-empty, unique across the
                                  palette (used to remap painted faces,
                                  see model/remap.py)
                       name    -- label
                       hue     -- OKLCH hue in degrees
                       chroma  -- peak chroma, or None/missing = group's
                       span    -- grid columns covered (1 or 2, default 1);
                                  the ramp then runs top-to-bottom over
                                  span * rows cells, column by column
    rows        -- number of rows (int, >= 1)
    l_top, l_bottom -- OKLab lightness of the first and the last cell of a
                   ramp (default 0.93 / 0.25)
    tint        -- 0..1, chroma reduction toward the top of a ramp
    shade       -- 0..1, chroma reduction toward the bottom of a ramp
    hue_shift   -- -1..1, highlights drift toward warm and shadows toward
                   cool (negative: the other way round)
    warmth      -- -1..1, global temperature bias

A column with an effective chroma of 0 is a neutral grey ramp (with a slight
temperature drift from hue_shift/warmth).

Flat parameters of LPC 1.x (cols, rows, add_greyscale, saturation,
brightness, tint, shade[, color_mode, hue_shift, warmth]) are converted once
by `palette_from_params`. Until the Blender layer stores palettes itself,
`color_at`, `cell_count`, `build_pixels` and `nearest_cell` accept them too
and convert on the fly. The 1.x color formulas (HSV, saturation/brightness)
are gone: converted palettes keep their grid -- so every painted face keeps
its cell -- but HSV palettes change color.
"""

import math

DEFAULT_L_TOP = 0.93
DEFAULT_L_BOTTOM = 0.25
DEFAULT_ROWS = 5
DEFAULT_TINT = 0.8
DEFAULT_SHADE = 0.8
DEFAULT_HUE_SHIFT = 0.0
DEFAULT_WARMTH = 0.0
MAX_SPAN = 2
MAX_ROWS = 64
MAX_GRID_COLS = 128
MAX_CHROMA = 0.4

# LPC 1.x palette parameters and their defaults. Blender stores a property
# only once it differs from its default, so a 1.x file may lack any of
# these -- `params_from_legacy` fills them in.
LEGACY_DEFAULTS = {
    "cols": 16,
    "rows": 9,
    "add_greyscale": True,
    "saturation": 1.0,
    "brightness": 1.0,
    "tint": 0.8,
    "shade": 0.8,
    "hue_shift": 0.0,
    "warmth": 0.0,
}
# Stored by 1.x but without effect in 2.0 (HSV/OKLCH switch).
LEGACY_IGNORED = ("color_mode",)

# Groups and ids of a palette converted from LPC 1.x parameters.
CLASSIC_GREYSCALE_GROUP = "Greyscale"
CLASSIC_WHEEL_GROUP = "Color Wheel"
CLASSIC_GREYSCALE_ID = "grey"

# Peak chroma of the 1.x color wheel at saturation 1.
CLASSIC_WHEEL_CHROMA = 0.16
# 1.x OKLCH lightness of the hue columns: (0.94 - 0.72 t) * brightness.
_CLASSIC_L_TOP = 0.94
_CLASSIC_L_BOTTOM = 0.22


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


def srgb_to_oklab(r, g, b):
    """sRGB (0..1, gamma-encoded) -> OKLab (L, a, b); inverse of
    `_oklab_to_srgb` for in-gamut colors."""
    def to_linear(c):
        c = max(0.0, min(1.0, c))
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = to_linear(r), to_linear(g), to_linear(b)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1.0 / 3.0)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1.0 / 3.0)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1.0 / 3.0)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


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


# --------------------------------------------------------------------------
# Conversion of LPC 1.x parameters
# --------------------------------------------------------------------------

def is_palette(params):
    """True if `params` is a palette rather than flat 1.x parameters."""
    return "groups" in params


def _classic_hue_id(i, n):
    """Stable id of 1.x hue column i of n: its hue as a reduced fraction of a
    turn ("hue-0", "hue-1/8"). Equal hues get equal ids whatever `n` is, so
    a later remap matches them automatically."""
    if i == 0:
        return "hue-0"
    g = math.gcd(i, n)
    return "hue-%d/%d" % (i // g, n // g)


def palette_from_params(params):
    """Flat LPC 1.x parameters as a palette with the same grid: group
    "Greyscale" (one grey column from white to black, only if
    `add_greyscale`) + group "Color Wheel" (`cols` evenly spaced hues,
    chroma 0.16 * saturation). The hue columns' lightness follows the 1.x
    OKLCH formula ((0.94 - 0.72 t) * brightness); `color_mode` is ignored
    -- HSV palettes change color."""
    n = params["cols"]
    brightness = params["brightness"]
    groups = []
    if params["add_greyscale"]:
        groups.append({
            "name": CLASSIC_GREYSCALE_GROUP,
            "chroma": 0.0,
            "l_top": 1.0,
            "l_bottom": 0.0,
            "columns": [{"id": CLASSIC_GREYSCALE_ID, "name": "Grey",
                         "hue": 0.0, "chroma": None, "span": 1}],
        })
    groups.append({
        "name": CLASSIC_WHEEL_GROUP,
        "chroma": CLASSIC_WHEEL_CHROMA * params["saturation"],
        "columns": [{"id": _classic_hue_id(i, n), "name": "Hue %d" % (i + 1),
                     "hue": i * 360.0 / n, "chroma": None, "span": 1}
                    for i in range(n)],
    })
    return {
        "groups": groups,
        "rows": params["rows"],
        "l_top": _CLASSIC_L_TOP * brightness,
        "l_bottom": _CLASSIC_L_BOTTOM * brightness,
        "tint": params["tint"],
        "shade": params["shade"],
        "hue_shift": float(params.get("hue_shift", 0.0)),
        "warmth": float(params.get("warmth", 0.0)),
    }


def params_from_legacy(raw):
    """Flat 1.x parameters from what a 1.x file actually stored (`raw`: a
    mapping, e.g. the scene's raw ID properties), each missing key at its 1.x
    default. Feed the result to `palette_from_params`."""
    params = dict(LEGACY_DEFAULTS)
    for key in LEGACY_DEFAULTS:
        if key in raw:
            value = raw[key]
            params[key] = type(LEGACY_DEFAULTS[key])(value)
    return params


def has_legacy_values(raw):
    """True if `raw` holds any 1.x-only palette parameter -- the file was
    saved by LPC 1.x with a changed palette."""
    return any(key in raw for key in ("cols", "add_greyscale", "saturation",
                                      "brightness") + LEGACY_IGNORED)


def _as_palette(params):
    return params if is_palette(params) else palette_from_params(params)


# --------------------------------------------------------------------------
# JSON form (templates, import/export)
# --------------------------------------------------------------------------

_PALETTE_KEYS = {"groups", "rows", "l_top", "l_bottom", "tint", "shade",
                 "hue_shift", "warmth"}
_GROUP_KEYS = {"name", "chroma", "l_top", "l_bottom", "columns"}
_COLUMN_KEYS = {"id", "name", "hue", "chroma", "span"}


def _number(obj, key, default, low, high, where, optional=False):
    value = obj.get(key, default)
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s: %s must be a number" % (where, key))
    if not (low <= value <= high):
        raise ValueError("%s: %s=%r outside %g..%g" % (where, key, value, low, high))
    return float(value)


def _check_keys(obj, allowed, where):
    if not isinstance(obj, dict):
        raise ValueError("%s must be an object" % where)
    unknown = set(obj) - allowed
    if unknown:
        raise ValueError("%s: unknown keys %s" % (where, sorted(unknown)))


def palette_from_json(obj):
    """A palette from its JSON form (the `palette` section of an LPC file):
    checks keys, types and ranges, fills defaults. Raises ValueError."""
    _check_keys(obj, _PALETTE_KEYS, "palette")
    rows = obj.get("rows", DEFAULT_ROWS)
    if isinstance(rows, bool) or not isinstance(rows, int) or not (1 <= rows <= MAX_ROWS):
        raise ValueError("palette: rows must be an integer 1..%d" % MAX_ROWS)
    groups = []
    raw_groups = obj.get("groups")
    if not isinstance(raw_groups, list):
        raise ValueError("palette: groups must be a list")
    for gi, raw_group in enumerate(raw_groups):
        where = "group %d" % (gi + 1)
        _check_keys(raw_group, _GROUP_KEYS, where)
        raw_columns = raw_group.get("columns")
        if not isinstance(raw_columns, list):
            raise ValueError("%s: columns must be a list" % where)
        columns = []
        for ci, raw_column in enumerate(raw_columns):
            cwhere = "%s, column %d" % (where, ci + 1)
            _check_keys(raw_column, _COLUMN_KEYS, cwhere)
            cid = raw_column.get("id")
            if not isinstance(cid, str):
                raise ValueError("%s: id must be a string" % cwhere)
            span = raw_column.get("span", 1)
            if isinstance(span, bool) or not isinstance(span, int):
                raise ValueError("%s: span must be an integer" % cwhere)
            columns.append({
                "id": cid,
                "name": str(raw_column.get("name", cid)),
                "hue": _number(raw_column, "hue", 0.0, 0.0, 360.0, cwhere),
                "chroma": _number(raw_column, "chroma", None, 0.0, MAX_CHROMA,
                                  cwhere, optional=True),
                "span": span,
            })
        groups.append({
            "name": str(raw_group.get("name", "Group %d" % (gi + 1))),
            "chroma": _number(raw_group, "chroma", 0.0, 0.0, MAX_CHROMA, where),
            "l_top": _number(raw_group, "l_top", None, 0.0, 1.0, where, optional=True),
            "l_bottom": _number(raw_group, "l_bottom", None, 0.0, 1.0, where, optional=True),
            "columns": columns,
        })
    palette = {
        "groups": groups,
        "rows": rows,
        "l_top": _number(obj, "l_top", DEFAULT_L_TOP, 0.0, 1.0, "palette"),
        "l_bottom": _number(obj, "l_bottom", DEFAULT_L_BOTTOM, 0.0, 1.0, "palette"),
        "tint": _number(obj, "tint", DEFAULT_TINT, 0.0, 1.0, "palette"),
        "shade": _number(obj, "shade", DEFAULT_SHADE, 0.0, 1.0, "palette"),
        "hue_shift": _number(obj, "hue_shift", DEFAULT_HUE_SHIFT, -1.0, 1.0, "palette"),
        "warmth": _number(obj, "warmth", DEFAULT_WARMTH, -1.0, 1.0, "palette"),
    }
    validate_palette(palette)
    return palette


def _r(value):
    """Round a stored value for the file: Blender's float32 properties turn
    0.93 into 0.9300000071525574; 4 decimals are far below anything visible."""
    return round(float(value), 4)


def palette_to_json(palette):
    """The JSON form of `palette` (inverse of `palette_from_json`): only the
    known keys, optional values left out when unset, floats rounded to 4
    decimals."""
    groups = []
    for group in palette["groups"]:
        out = {"name": group["name"], "chroma": _r(group.get("chroma", 0.0))}
        for key in ("l_top", "l_bottom"):
            if group.get(key) is not None:
                out[key] = _r(group[key])
        columns = []
        for column in group["columns"]:
            col = {"id": column["id"], "name": column["name"],
                   "hue": _r(column["hue"])}
            if column.get("chroma") is not None:
                col["chroma"] = _r(column["chroma"])
            if column.get("span", 1) != 1:
                col["span"] = column["span"]
            columns.append(col)
        out["columns"] = columns
        groups.append(out)
    result = {"rows": palette["rows"]}
    for key, default in (("l_top", DEFAULT_L_TOP), ("l_bottom", DEFAULT_L_BOTTOM),
                         ("tint", DEFAULT_TINT), ("shade", DEFAULT_SHADE),
                         ("hue_shift", DEFAULT_HUE_SHIFT), ("warmth", DEFAULT_WARMTH)):
        result[key] = _r(palette.get(key, default))
    result["groups"] = groups
    return result


# --------------------------------------------------------------------------
# Structure
# --------------------------------------------------------------------------

def validate_palette(palette):
    """Raise ValueError if `palette` is malformed: no columns, rows outside
    1..MAX_ROWS, more than MAX_GRID_COLS grid columns, span outside
    1..MAX_SPAN, or missing/duplicate column ids."""
    if not (1 <= palette["rows"] <= MAX_ROWS):
        raise ValueError("rows must be 1..%d" % MAX_ROWS)
    if grid_cols(palette) > MAX_GRID_COLS:
        raise ValueError("more than %d grid columns" % MAX_GRID_COLS)
    ids = set()
    for group in palette["groups"]:
        for column in group["columns"]:
            cid = column.get("id")
            if not cid:
                raise ValueError("column %r has no id" % column.get("name"))
            if cid in ids:
                raise ValueError("duplicate column id %r" % cid)
            ids.add(cid)
            span = column.get("span", 1)
            if not (1 <= span <= MAX_SPAN):
                raise ValueError("column %r: span %r outside 1..%d"
                                 % (cid, span, MAX_SPAN))
    if not ids:
        raise ValueError("palette has no columns")


def _grid_cells(palette):
    """(column, group, part) per grid column, left to right: `part` is
    0..span-1, the slice of a spanning column's ramp."""
    result = []
    for group in palette["groups"]:
        for column in group["columns"]:
            for part in range(column.get("span", 1)):
                result.append((column, group, part))
    return result


def grid_columns(palette):
    """One (column, part) per grid column, left to right."""
    return [(column, part) for column, _group, part in _grid_cells(palette)]


def grid_cols(palette):
    """Number of grid columns of `palette` (spans counted)."""
    return sum(column.get("span", 1)
               for group in palette["groups"] for column in group["columns"])


def group_ranges(palette):
    """(name, first grid column, grid column count) per group -- the group
    headings of the picker and the export."""
    result = []
    x = 0
    for group in palette["groups"]:
        n = sum(column.get("span", 1) for column in group["columns"])
        result.append((group["name"], x, n))
        x += n
    return result


def grid_column_labels(palette):
    """One "Group · Column" label per grid column; the halves of a spanning
    column are told apart as "Column 1/2", "Column 2/2"."""
    labels = []
    for column, group, part in _grid_cells(palette):
        span = column.get("span", 1)
        name = column["name"] if span == 1 else "%s %d/%d" % (column["name"], part + 1, span)
        labels.append("%s · %s" % (group["name"], name))
    return labels


def cell_label(palette, x, y):
    """Human label of cell (x, y): "Group · Column n", n counting the
    column's ramp from 1 (a spanning column continues in its second grid
    column). Empty string outside the grid."""
    cells = _grid_cells(palette)
    rows = palette["rows"]
    if not (0 <= x < len(cells) and 0 <= y < rows):
        return ""
    column, group, part = cells[x]
    return "%s · %s %d" % (group["name"], column["name"], part * rows + y + 1)


def column_chroma(column, group):
    """Effective peak chroma of `column` (own value, else the group's)."""
    chroma = column.get("chroma")
    if chroma is None:
        chroma = group.get("chroma", 0.0)
    return float(chroma)


def lightness_range(group, palette):
    """Effective (l_top, l_bottom) of `group`'s ramps: each end the group's
    own value, else the palette's."""
    l_top = group.get("l_top")
    if l_top is None:
        l_top = palette.get("l_top", DEFAULT_L_TOP)
    l_bottom = group.get("l_bottom")
    if l_bottom is None:
        l_bottom = palette.get("l_bottom", DEFAULT_L_BOTTOM)
    return float(l_top), float(l_bottom)


# --------------------------------------------------------------------------
# Colors
# --------------------------------------------------------------------------

def _ramp_t(y, part, span, rows):
    """Position on the column's ramp: 0 = first cell (light) .. 1 = last
    (dark). A spanning column runs over span * rows cells."""
    n = span * rows
    if n <= 1:
        return 0.5
    return (part * rows + y) / (n - 1)


def _cell_color(column, group, part, y, palette):
    """RGBA of one cell (OKLCH)."""
    t = _ramp_t(y, part, column.get("span", 1), palette["rows"])
    hue_shift = float(palette.get("hue_shift", 0.0))
    warmth = float(palette.get("warmth", 0.0))
    l_top, l_bottom = lightness_range(group, palette)
    L = max(0.0, min(1.0, l_top - (l_top - l_bottom) * t))

    c_peak = column_chroma(column, group)
    if c_peak == 0.0:
        # Neutral grey with a slight temperature drift.
        cool = (t - 0.5) * 0.02 * hue_shift
        warm_bias = warmth * 0.01
        r, g, b = _oklab_to_srgb(L, warm_bias - cool * 0.4, warm_bias - cool * 0.8)
        return (r, g, b, 1.0)

    tint = palette["tint"]
    shade = palette["shade"]
    base_h_deg = (float(column["hue"]) + warmth * 30.0) % 360.0
    warm_pole = 95.0
    cool_pole = 265.0
    if t <= 0.5:
        rf = 1.0 - t / 0.5
        target_pole = warm_pole if hue_shift >= 0 else cool_pole
        diff = (target_pole - base_h_deg + 180.0) % 360.0 - 180.0
        h = (base_h_deg + diff * (0.22 * abs(hue_shift) * rf)) % 360.0
        C = c_peak * (1.0 - 0.50 * tint * rf)
    else:
        rf = (t - 0.5) / 0.5
        target_pole = cool_pole if hue_shift >= 0 else warm_pole
        diff = (target_pole - base_h_deg + 180.0) % 360.0 - 180.0
        h = (base_h_deg + diff * (0.28 * abs(hue_shift) * rf)) % 360.0
        C = c_peak * (1.0 - 0.25 * shade * rf)
    r, g, b = _oklch_to_rgb_clamped(L, C, h)
    return (r, g, b, 1.0)


def cell_count(params):
    """(cols, rows) of the grid: grid columns (spans counted) and rows.
    For flat 1.x parameters: hue columns plus the optional greyscale one."""
    if is_palette(params):
        return grid_cols(params), params["rows"]
    cols = params["cols"] + (1 if params["add_greyscale"] else 0)
    return cols, params["rows"]


def color_at(x, y, params):
    """Deterministic RGBA color for cell (x, y), values in [0, 1].

    `params` is a palette (or flat 1.x parameters, converted on the fly)."""
    palette = _as_palette(params)
    cells = _grid_cells(palette)
    rows = palette["rows"]
    if not (0 <= x < len(cells)):
        raise ValueError(f"x={x} out of range 0..{len(cells) - 1}")
    if not (0 <= y < rows):
        raise ValueError(f"y={y} out of range 0..{rows - 1}")
    column, group, part = cells[x]
    return _cell_color(column, group, part, y, palette)


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
    palette = _as_palette(params)
    cols, rows = cell_count(palette)
    pixels = [0.0] * (cols * rows * 4)
    for y in range(rows):
        for x in range(cols):
            i = (y * cols + x) * 4
            pixels[i:i + 4] = color_at(x, y, palette)
    return pixels, cols, rows


def nearest_cell(color, params):
    """Cell (x, y) whose `color_at` result is closest to `color` (r,g,b[,a]).

    Brute-force over all cells -- palettes are small (typically < 200
    cells), and this is the only way to guarantee consistency with
    `color_at` by construction.
    """
    palette = _as_palette(params)
    cols, rows = cell_count(palette)
    best = None
    best_dist = None
    for y in range(rows):
        for x in range(cols):
            r, g, b, _a = color_at(x, y, palette)
            dist = (r - color[0]) ** 2 + (g - color[1]) ** 2 + (b - color[2]) ** 2
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = (x, y)
    return best
