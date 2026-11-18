# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""The palette cheatsheet: a human-readable PNG of the palette grid.

A title line on top (the palette's name + "created with Low Poly
Colorizer"), then the grid drawn like the modal picker -- groups with a gap
and their name above, row 0 at the bottom -- plus the row numbers on the
left and every column's name written vertically underneath it. Exported next to the data textures for
looking things up; its `.import` sidecar tells Godot not to import it.

`layout` is pure (no bpy, testable with plain `python`): rectangles and text
placements in pixels, origin bottom-left. `render_png` draws that layout in
a GPU offscreen buffer and saves it -- it needs Blender with a GPU context
(not available in every background session; the exporter skips it then).
"""

import math

try:
    from ..model import palette as model_palette
    from ..picker import geometry
except ImportError:  # plain-python tests put the addon dir on sys.path
    from model import palette as model_palette
    from picker import geometry

CELL = 56              # cell size in pixels
GROUP_GAP = 0.5        # gap between groups, in cells (as in the picker)
CELL_LINE = 2          # dark line between cells, in pixels
BACKGROUND = (0.13, 0.13, 0.13, 1.0)
GRID_BACKGROUND = (0.05, 0.05, 0.05, 1.0)
TEXT_COLOR = (0.9, 0.9, 0.9, 1.0)
CREDIT_COLOR = (0.6, 0.6, 0.6, 1.0)
CREDIT = "created with Low Poly Colorizer"


def layout(params, measure, cell=CELL, font_size=None, title=""):
    """Placement of everything on the cheatsheet.

    `measure(text, size)` returns the (width, height) of `text` at font
    size `size` in pixels; `title` is the palette's name ("Palette" if
    empty). Returns a dict:

        size   (width, height) of the image
        rects  [(x0, y0, x1, y1, rgba)], drawn in order
        texts  [{"text", "x", "y", "size", "rotation", "color"}], baseline
               origin; rotation in radians (-pi/2 = reads top to bottom)
    """
    palette = params
    cols, rows = model_palette.cell_count(palette)
    size = font_size or max(8, round(cell * 0.42))
    cap = size * 0.7                  # approximate cap height
    pad = round(cell * 0.25)
    margin = round(cell * 0.75)
    title = " ".join(str(title or "").split()) or "Palette"
    title_size = round(size * 1.6)
    title_cap = title_size * 0.7
    title_w = measure(title, title_size)[0]
    credit_gap = round(size * 1.2)
    credit_w = measure(CREDIT, size)[0]

    groups = [(name, start, n) for name, start, n
              in model_palette.group_ranges(palette) if n > 0]
    geo = geometry.PickerGeometry(
        origin_x=0.0, origin_y=0.0, swatch_size=cell,
        group_starts=tuple(start for _n, start, _c in groups if start > 0),
        gap=GROUP_GAP,
    )

    # One label per COLUMN (a spanning column gets one name across its
    # grid columns): (name, first grid column, grid column count).
    columns = []
    x = 0
    for group in palette["groups"]:
        for column in group["columns"]:
            span = column.get("span", 1)
            columns.append((column["name"], x, span))
            x += span

    row_label_w = max((measure(str(r), size)[0] for r in range(rows)), default=0)
    name_h = max((measure(name, size)[0] for name, _x, _s in columns), default=0)

    grid_x = margin + row_label_w + pad
    grid_y = margin + name_h + pad
    grid_w = geo.grid_width_cells(cols) * cell
    grid_h = rows * cell
    heading_top = grid_y + grid_h + pad + size          # top of group headings
    title_y = heading_top + 2 * pad                     # title baseline
    width = int(math.ceil(max(grid_x + grid_w + margin,
                              margin + title_w + credit_gap + credit_w + margin)))
    height = int(math.ceil(title_y + title_cap + margin))
    geo.origin_x, geo.origin_y = grid_x, grid_y

    rects = [(0, 0, width, height, BACKGROUND)]
    # Dark backing per group: shows through as the lines between cells.
    for _name, start, n in groups:
        x0, y0 = geo.cell_to_screen(start, 0)
        rects.append((x0 - CELL_LINE, y0 - CELL_LINE, x0 + n * cell,
                      y0 + grid_h, GRID_BACKGROUND))
    for y in range(rows):
        for x in range(cols):
            x0, y0, x1, y1 = geo.cell_rect(x, y)
            rects.append((x0, y0, x1 - CELL_LINE, y1 - CELL_LINE,
                          model_palette.color_at(x, y, palette)))

    texts = [
        {"text": title, "x": margin, "y": title_y, "size": title_size,
         "rotation": 0.0, "color": TEXT_COLOR},
        {"text": CREDIT, "x": margin + title_w + credit_gap, "y": title_y,
         "size": size, "rotation": 0.0, "color": CREDIT_COLOR},
    ]
    for name, start, _n in groups:
        x0, _y0 = geo.cell_to_screen(start, 0)
        texts.append({"text": name, "x": x0, "y": grid_y + grid_h + pad,
                      "size": size, "rotation": 0.0})
    for r in range(rows):
        text = str(r)
        w = measure(text, size)[0]
        texts.append({"text": text, "x": grid_x - pad - w,
                      "y": grid_y + (r + 0.5) * cell - cap / 2,
                      "size": size, "rotation": 0.0})
    for name, start, span in columns:
        x0, _y0 = geo.cell_to_screen(start, 0)
        center = x0 + (span * cell - CELL_LINE) / 2
        # Rotated -90 degrees the glyphs stand to the RIGHT of the baseline,
        # so the baseline sits half a cap height left of the center.
        texts.append({"text": name, "x": center - cap / 2,
                      "y": grid_y - CELL_LINE - pad,
                      "size": size, "rotation": -math.pi / 2})
    return {"size": (width, height), "rects": rects, "texts": texts}


def render_png(params, path, cell=CELL, title=""):
    """Draw the cheatsheet of `params` and save it as an 8-bit sRGB PNG at
    `path`. Colors are written as they come from `color_at` (sRGB), like
    the palette texture. Raises RuntimeError without a GPU context."""
    import blf
    import bpy
    import gpu
    from gpu_extras.batch import batch_for_shader
    from mathutils import Matrix

    font = 0

    def measure(text, size):
        blf.size(font, size)
        return blf.dimensions(font, text)

    lay = layout(params, measure, cell, title=title)
    width, height = lay["size"]
    try:
        offscreen = gpu.types.GPUOffScreen(width, height)
    except Exception as exc:  # no GPU context (e.g. some background runs)
        raise RuntimeError(f"no GPU context for the cheatsheet: {exc}") from exc

    try:
        with offscreen.bind():
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=BACKGROUND)
            projection = Matrix((
                (2.0 / width, 0.0, 0.0, -1.0),
                (0.0, 2.0 / height, 0.0, -1.0),
                (0.0, 0.0, 1.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
            ))
            with gpu.matrix.push_pop(), gpu.matrix.push_pop_projection():
                gpu.matrix.load_matrix(Matrix.Identity(4))
                gpu.matrix.load_projection_matrix(projection)
                shader = gpu.shader.from_builtin("UNIFORM_COLOR")
                for x0, y0, x1, y1, color in lay["rects"]:
                    batch = batch_for_shader(shader, "TRI_FAN", {
                        "pos": ((x0, y0), (x1, y0), (x1, y1), (x0, y1))})
                    shader.uniform_float("color", color)
                    batch.draw(shader)
                gpu.state.blend_set("ALPHA")
                for t in lay["texts"]:
                    blf.color(font, *t.get("color", TEXT_COLOR))
                    blf.size(font, t["size"])
                    if t["rotation"]:
                        blf.enable(font, blf.ROTATION)
                        blf.rotation(font, t["rotation"])
                    blf.position(font, t["x"], t["y"], 0)
                    blf.draw(font, t["text"])
                    if t["rotation"]:
                        blf.disable(font, blf.ROTATION)
                gpu.state.blend_set("NONE")
            buffer = fb.read_color(0, 0, width, height, 4, 0, "FLOAT")
    finally:
        offscreen.free()

    buffer.dimensions = width * height * 4
    image = bpy.data.images.new("lpc_cheatsheet_tmp", width, height,
                                alpha=False, float_buffer=False)
    try:
        image.colorspace_settings.name = "sRGB"
        try:
            image.pixels.foreach_set(buffer)
        except TypeError:  # a Buffer without the buffer protocol
            image.pixels.foreach_set(buffer.to_list())
        image.filepath_raw = path
        image.file_format = "PNG"
        image.save()
    finally:
        bpy.data.images.remove(image)
