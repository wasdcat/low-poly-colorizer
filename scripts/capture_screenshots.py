# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Automated screenshot capture pipeline for Low Poly Colorizer documentation.

Launches Blender in GUI mode with event simulation:
1. Expands the 3D viewport sidebar and activates the LPC tab.
2. Captures and crops the N-Panel (n_panel.png & n_panel_annotated.png with badges 1..6).
3. Hides the scene objects and triggers the GPU Modal Palette Picker overlay
   (palette_picker_annotated.png with badges A..D;
   cropped from the screen change, badges placed from the geometry Blender reports).
4. Extracts the inline palette picker icon (icon_picker.png, found as the bright glyph in the button).
5. Opens the LPC Settings dialog (settings_annotated.png with badges 1..4: Palette, Groups,
   Columns, Material; the dialog and its layout boxes are found in the screenshot, not at fixed
   coordinates).
6. Constructs and captures the LPC Set Material Geometry Node tree (geo_nodes_lpc_set_material.png).

Requirements:
- Blender 4.2+ or 5.x installed and discoverable.
- The N-Panel crop and the LPC tab click use fixed coordinates, calibrated for a maximized
  Blender window of 5120x1351 px (the picker and Settings crops adapt to any size).

Usage:
    python scripts/capture_screenshots.py [<output_dir> ...]

Examples:
    python scripts/capture_screenshots.py
    python scripts/capture_screenshots.py docs/manual/common/images
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent

# Window position (x, y up) of the simulated mouse when the Settings dialog
# opens -- the dialog appears around it, the crop searches from it.
SETTINGS_MOUSE = (2560, 675)

BLENDER_CANDIDATES = [
    shutil.which("blender"),
    r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
]


# Runs inside Blender (embedded into the automation script): where the picker
# overlay draws -- the same PickerGeometry, swatch size and centering as
# LPC_OT_modal_palette_picker.invoke -- in window pixels, y up.
PICKER_GEOMETRY_DUMP = """
import json
from addon.model import palette as _pal
from addon.picker import geometry as _geo, interface as _iface, modal as _modal

def dump_picker_geometry(region, path):
    ctx = bpy.context
    params = _iface.params_from_scene(ctx.scene)
    cols, rows = _pal.cell_count(params)
    groups = [(n, s, c) for n, s, c in _pal.group_ranges(params) if c > 0]
    geo = _geo.PickerGeometry(
        origin_x=0.0, origin_y=0.0, swatch_size=24.0,
        ui_scale=ctx.preferences.system.ui_scale,
        group_starts=tuple(s for _n, s, _c in groups if s > 0), gap=_modal.GROUP_GAP)
    geo.origin_x = (region.width - geo.grid_width_cells(cols) * geo.cell_size) / 2.0
    geo.origin_y = (region.height - rows * geo.cell_size) / 2.0
    def to_win(x, y):
        return [region.x + x, region.y + y]
    def rect(x, y):
        x0, y0, x1, y1 = geo.cell_rect(x, y)
        return to_win(x0, y0) + to_win(x1, y1)
    result = ctx.window_manager.lpc_picker_result
    data = {
        "cols": cols, "rows": rows, "cell": geo.cell_size,
        "grid": to_win(*geo.cell_to_screen(0, 0)) + to_win(*geo.cell_to_screen(cols, rows)),
        "groups": [{"name": n, "first": s, "count": c,
                    "x0": to_win(*geo.cell_to_screen(s, 0))[0],
                    "x1": to_win(*geo.cell_to_screen(s + c - 1, 0))[0] + geo.cell_size}
                   for n, s, c in groups],
        "active": rect(result.x, result.y),
    }
    with open(path, "w") as f:
        json.dump(data, f)
"""


def diff_bbox(before: Image.Image, after: Image.Image, box, thresh: int = 8):
    """Bounding box (in full-image pixels) of what changed inside `box`."""
    a = before.convert("RGB").crop(box)
    b = after.convert("RGB").crop(box)
    d = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > thresh else 0)
    bb = d.getbbox()
    if bb is None:
        return None
    return (box[0] + bb[0], box[1] + bb[1], box[0] + bb[2], box[1] + bb[3])


def popup_rect(before: Image.Image, after: Image.Image, cx: int, cy: int,
               thresh: int = 4, frac: float = 0.5, band: int = 250, gap: int = 80):
    """Rectangle of a popup that appeared around (cx, cy) between two window
    shots: the contiguous block of mostly-changed columns / rows, bridging
    short runs where the popup happens to match the background (box outlines
    are close to the viewport grey)."""
    d = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).convert("L")
    d = d.point(lambda v: 255 if v > thresh else 0)
    W, H = d.size
    px = d.load()

    def mostly(values):
        values = list(values)
        return sum(1 for v in values if v) >= frac * len(values)

    def extend(start, step, ok, limit):
        last, i, miss = start, start, 0
        while 0 <= i + step < limit and miss < gap:
            i += step
            if ok(i):
                last, miss = i, 0
            else:
                miss += 1
        return last

    y0, y1 = max(0, cy - band), min(H, cy + band)
    l = extend(cx, -1, lambda x: mostly(px[x, y] for y in range(y0, y1, 2)), W)
    r = extend(cx, 1, lambda x: mostly(px[x, y] for y in range(y0, y1, 2)), W)
    t = extend(cy, -1, lambda y: mostly(px[x, y] for x in range(l, r, 2)), H)
    b = extend(cy, 1, lambda y: mostly(px[x, y] for x in range(l, r, 2)), H)

    # Trim the popup's soft drop shadow: edges that changed only slightly.
    # Not the top edge -- a dialog reaching the window top lies over the dark
    # top bar, where its title row barely differs from what was there.
    strong = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).convert("L")
    strong = strong.point(lambda v: 255 if v > 20 else 0).load()
    while l < r and not mostly(strong[l, y] for y in range(t, b, 2)):
        l += 1
    while r > l and not mostly(strong[r, y] for y in range(t, b, 2)):
        r -= 1
    while b > t and not mostly(strong[x, b] for x in range(l, r, 2)):
        b -= 1
    return l, t, r + 1, b + 1


def layout_boxes(img: Image.Image, expected: int, min_len: int = 30):
    """(top, bottom) of the layout boxes in a cropped dialog: runs that differ
    from the dialog background along a column just inside the boxes' left
    edge. Tries columns from the left until one yields `expected` runs."""
    px = img.load()
    # Dialog background: the most frequent color of the left margin (past the
    # 2 px outline, before the boxes start).
    margin = [px[x, y] for x in range(2, 9) for y in range(0, img.height, 3)]
    bg = max(set(margin), key=margin.count)

    def runs_at(x):
        runs, start = [], None
        for y in range(img.height):
            c = px[x, y]
            inside = any(abs(c[i] - bg[i]) > 4 for i in range(3))
            if inside and start is None:
                start = y
            elif not inside and start is not None:
                if y - start >= min_len:
                    runs.append((start, y - 1))
                start = None
        return runs

    best = []
    for x in range(6, min(60, img.width)):
        runs = runs_at(x)
        if len(runs) == expected:
            return runs
        if len(runs) > len(best) and len(runs) < expected:
            best = runs
    return best


def find_blender() -> Path:
    for candidate in BLENDER_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError("Blender executable could not be found.")


def get_font(size: int = 15):
    try:
        return ImageFont.truetype("arialbd.ttf", size)
    except Exception:
        return ImageFont.load_default()


def capture(output_dirs: list[Path], raw_dir: Path | None = None):
    blender_bin = find_blender()
    
    # Resolve and create target directories
    resolved_dirs = [p.resolve() if not p.is_absolute() else p for p in output_dirs]
    for d in resolved_dirs:
        d.mkdir(parents=True, exist_ok=True)

    def save_to_targets(img: Image.Image, filename: str, dpi: tuple[int, int] = (144, 144)):
        for d in resolved_dirs:
            target_path = d / filename
            img.save(target_path, dpi=dpi)
            print(f"Generated: {target_path} ({img.size[0]}x{img.size[1]} @ {dpi[0]} DPI)")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        if raw_dir is not None:  # keep the raw window shots for inspection
            tmp_path = raw_dir.resolve()
            tmp_path.mkdir(parents=True, exist_ok=True)
        base_blend = tmp_path / "base.blend"
        shot_panel_raw = tmp_path / "shot_panel_raw.png"
        shot_palette_before = tmp_path / "shot_palette_before.png"
        shot_palette_raw = tmp_path / "shot_palette_raw.png"
        shot_settings_before = tmp_path / "shot_settings_before.png"
        shot_settings_raw = tmp_path / "shot_settings_raw.png"
        picker_geo_json = tmp_path / "picker_geometry.json"
        shot_node_raw = tmp_path / "shot_node_raw.png"
        helper_script = tmp_path / "capture_automation.py"

        # 1. Create a clean base blend file to bypass splash screen
        create_blend_expr = (
            "import bpy; "
            f"bpy.ops.wm.save_as_mainfile(filepath=r'{base_blend}')"
        )
        subprocess.run(
            [str(blender_bin), "-b", "--python-expr", create_blend_expr],
            check=True,
            capture_output=True,
        )

        # 2. Automation script inside Blender
        helper_code = f'''
import sys
sys.path.insert(0, r"{ROOT}")
import bpy
from addon.ui import geometry_nodes
{PICKER_GEOMETRY_DUMP}
step = 0
CLEAN_OVERLAY_KEYS = ("show_floor", "show_axis_x", "show_axis_y", "show_axis_z", "show_cursor")

def on_timer():
    global step
    step += 1
    win = bpy.context.window_manager.windows[0]
    area_3d = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
    
    try:
        if step == 1:
            # Open 3D Viewport sidebar (N-Panel)
            if area_3d:
                area_3d.spaces.active.show_region_ui = True
            return 0.5
            
        elif step == 2:
            # Hover LPC tab button
            win.event_simulate("MOUSEMOVE", "NOTHING", x=4186, y=711)
            return 0.2
            
        elif step == 3:
            win.event_simulate("LEFTMOUSE", "PRESS", x=4186, y=711)
            return 0.2
            
        elif step == 4:
            win.event_simulate("LEFTMOUSE", "RELEASE", x=4186, y=711)
            return 0.5
            
        elif step == 5:
            # Screenshot N-Panel
            bpy.ops.screen.screenshot(filepath=r"{shot_panel_raw}")
            # Hide the scene objects, floor grid, axes and 3D cursor so the
            # picker shot has a clean background (not the whole overlay: that
            # would hide the add-on's own drawing too).
            for obj in bpy.context.scene.objects:
                obj.hide_set(True)
            if area_3d:
                ov = area_3d.spaces.active.overlay
                for key in CLEAN_OVERLAY_KEYS:
                    setattr(ov, key, False)
            return 0.5

        elif step == 6:
            # Reference shot without the picker (the crop is the difference)
            bpy.ops.screen.screenshot(filepath=r"{shot_palette_before}")
            # Open Modal Palette Picker
            if area_3d:
                region = next(r for r in area_3d.regions if r.type == "WINDOW")
                override = {{
                    "window": win,
                    "screen": win.screen,
                    "area": area_3d,
                    "region": region,
                    "scene": bpy.context.scene,
                }}
                with bpy.context.temp_override(**override):
                    bpy.ops.lpc.modal_palette_picker("INVOKE_DEFAULT")
                dump_picker_geometry(region, r"{picker_geo_json}")
            return 0.5

        elif step == 7:
            # Screenshot Modal Palette Picker
            bpy.ops.screen.screenshot(filepath=r"{shot_palette_raw}")
            win.event_simulate("ESC", "PRESS")
            win.event_simulate("ESC", "RELEASE")
            for obj in bpy.context.scene.objects:
                obj.hide_set(False)
            if area_3d:
                ov = area_3d.spaces.active.overlay
                for key in CLEAN_OVERLAY_KEYS:
                    setattr(ov, key, True)
            return 0.3

        elif step == 8:
            # Move mouse to center of 3D Viewport
            win.event_simulate("MOUSEMOVE", "NOTHING", x={SETTINGS_MOUSE[0]}, y={SETTINGS_MOUSE[1]})
            return 0.2

        elif step == 9:
            # Reference shot without the dialog (the crop is the difference)
            bpy.ops.screen.screenshot(filepath=r"{shot_settings_before}")
            # Open Settings Dialog
            if area_3d:
                region = next(r for r in area_3d.regions if r.type == "WINDOW")
                override = {{
                    "window": win,
                    "screen": win.screen,
                    "area": area_3d,
                    "region": region,
                    "scene": bpy.context.scene,
                }}
                with bpy.context.temp_override(**override):
                    bpy.ops.lpc.palette_settings("INVOKE_DEFAULT")
            return 0.5

        elif step == 10:
            # Screenshot Settings Dialog
            bpy.ops.screen.screenshot(filepath=r"{shot_settings_raw}")
            win.event_simulate("ESC", "PRESS")
            win.event_simulate("ESC", "RELEASE")
            return 0.3

        elif step == 11:
            # Setup Geometry Node graph
            scene = bpy.context.scene
            bpy.ops.lpc.preset_load_defaults()
            ng_lpc = geometry_nodes.ensure_lpc_geo_node_group(scene)
            
            user_nt = bpy.data.node_groups.new("LPC_Geometry_Nodes", "GeometryNodeTree")
            user_nt.is_modifier = True
            user_nt.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
            user_nt.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
            
            in_node = user_nt.nodes.new("NodeGroupInput")
            in_node.location = (-300, 0)
            
            lpc_node = user_nt.nodes.new("GeometryNodeGroup")
            lpc_node.node_tree = ng_lpc
            lpc_node.name = "LPC Set Material"
            lpc_node.label = "LPC Set Material"
            lpc_node.location = (0, 0)
            lpc_node.width = 200
            
            out_node = user_nt.nodes.new("NodeGroupOutput")
            out_node.location = (300, 0)
            
            user_nt.links.new(in_node.outputs["Geometry"], lpc_node.inputs["Geometry"])
            user_nt.links.new(lpc_node.outputs["Geometry"], out_node.inputs["Geometry"])
            
            if "Palette Cell X" in lpc_node.inputs:
                # A menu socket (column names): pick the 5th item by name.
                from addon.picker import interface as _iface
                names = geometry_nodes.column_menu_labels(_iface.params_from_scene(scene))
                try:
                    lpc_node.inputs["Palette Cell X"].default_value = names[min(4, len(names) - 1)]
                except Exception:
                    pass
            if "Palette Cell Y" in lpc_node.inputs:
                try:
                    lpc_node.inputs["Palette Cell Y"].default_value = 2
                except Exception:
                    pass
            if "Preset" in lpc_node.inputs:
                try:
                    lpc_node.inputs["Preset"].default_value = "Solid"
                except Exception:
                    pass
            
            obj = bpy.data.objects.get("Cube")
            if obj:
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                mod = obj.modifiers.new("LPC Geometry Nodes", "NODES")
                mod.node_group = user_nt
            
            if area_3d:
                area_3d.type = "NODE_EDITOR"
                space = area_3d.spaces.active
                space.tree_type = "GeometryNodeTree"
                space.node_tree = user_nt
                space.show_region_ui = False
                space.show_region_toolbar = False
            
            for n in user_nt.nodes:
                n.select = True
            return 0.3

        elif step == 12:
            # Frame selected nodes
            for a in win.screen.areas:
                if a.type == "NODE_EDITOR":
                    for r in a.regions:
                        if r.type == "WINDOW":
                            with bpy.context.temp_override(window=win, area=a, region=r, space_data=a.spaces.active):
                                bpy.ops.node.view_selected()
            return 0.3

        elif step == 13:
            # Deselect nodes for clean outline
            user_nt = bpy.data.node_groups.get("LPC_Geometry_Nodes")
            if user_nt:
                for n in user_nt.nodes:
                    n.select = False
            return 0.3

        elif step == 14:
            # Screenshot Geometry Nodes
            bpy.ops.screen.screenshot(filepath=r"{shot_node_raw}")
            bpy.ops.wm.quit_blender()
            return None

    except Exception as e:
        print("ERROR IN TIMER:", e)
        bpy.ops.wm.quit_blender()
        return None

bpy.app.timers.register(on_timer, first_interval=0.5)
'''
        helper_script.write_text(helper_code, encoding="utf-8")

        print(f"Launching Blender ({blender_bin})...")
        subprocess.run(
            [
                str(blender_bin),
                str(base_blend),
                "--enable-event-simulate",
                "--python",
                str(helper_script),
            ],
            check=True,
        )

        font = get_font(14)
        badge_col = (255, 120, 0, 255)
        line_col = (255, 120, 0, 220)
        badge_r = 12

        def draw_badge(draw, cx, cy, label):
            draw.ellipse([(cx - badge_r, cy - badge_r), (cx + badge_r, cy + badge_r)], fill=badge_col)
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((cx - tw / 2, cy - th / 2 - 1), label, fill=(255, 255, 255, 255), font=font)

        # 3. Crop N-Panel (n_panel.png)
        if shot_panel_raw.is_file():
            im_panel_raw = Image.open(shot_panel_raw)
            crop_box = (3781, 128, 4159, 697)
            panel_cropped = im_panel_raw.crop(crop_box).convert("RGBA")
            pw, ph = panel_cropped.size

            mask = Image.new("L", (pw, ph), 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle([(0, 0), (pw - 1, ph - 1)], radius=7, fill=255)
            panel_cropped.putalpha(mask)

            save_to_targets(panel_cropped, "n_panel.png", dpi=(144, 144))

            # Crop Palette Button Icon (icon_picker.png)
            # The button sits at the right end of the color row; its glyph is
            # the only bright content there. Crop the glyph's bounding box + 3 px.
            button_area = (322, 46, min(pw, 376), 92)
            area = panel_cropped.crop(button_area).convert("L")
            glyph = area.point(lambda v: 255 if v > 150 else 0).getbbox()
            pad = 3
            icon_crop = panel_cropped.crop((
                button_area[0] + glyph[0] - pad, button_area[1] + glyph[1] - pad,
                button_area[0] + glyph[2] + pad, button_area[1] + glyph[3] + pad))
            save_to_targets(icon_crop, "icon_picker.png", dpi=(144, 144))

            # Generate n_panel_annotated.png with precision brackets (badges 1..6)
            extra_w = 56
            panel_canvas = Image.new("RGBA", (pw + extra_w, ph), (0, 0, 0, 0))
            panel_canvas.paste(panel_cropped, (0, 0))
            p_draw = ImageDraw.Draw(panel_canvas)

            panel_sections = [
                (1, 50, 82),   # 1: Color selection & picker
                (2, 85, 112),  # 2: Selection status
                (3, 125, 288), # 3: Preset list & actions
                (4, 296, 417), # 4: PBR sliders
                (5, 428, 460), # 5: Tools
                (6, 484, 558), # 6: Export & settings
            ]

            bx = pw + 6
            tick_len = 5
            cx = pw + 32

            for num, y1, y2 in panel_sections:
                cy = int((y1 + y2) / 2)
                p_draw.line([(bx - tick_len, y1), (bx, y1)], fill=line_col, width=2)
                p_draw.line([(bx, y1), (bx, y2)], fill=line_col, width=2)
                p_draw.line([(bx - tick_len, y2), (bx, y2)], fill=line_col, width=2)
                p_draw.line([(bx, cy), (cx - badge_r, cy)], fill=line_col, width=2)
                draw_badge(p_draw, cx, cy, str(num))

            save_to_targets(panel_canvas, "n_panel_annotated.png", dpi=(144, 144))

        def bracket_h(draw, x1, x2, y, label, up=True):
            """Horizontal bracket from x1 to x2 at y, badge above (or below)."""
            tick = 5 if up else -5
            draw.line([(x1, y + tick), (x1, y)], fill=line_col, width=2)
            draw.line([(x1, y), (x2, y)], fill=line_col, width=2)
            draw.line([(x2, y + tick), (x2, y)], fill=line_col, width=2)
            cx = int((x1 + x2) / 2)
            cy = y - 18 if up else y + 18
            draw.line([(cx, y), (cx, cy + (badge_r if up else -badge_r))], fill=line_col, width=2)
            draw_badge(draw, cx, cy, label)

        def bracket_v(draw, x, y1, y2, label):
            """Vertical bracket from y1 to y2 at x, badge to the right."""
            draw.line([(x - 5, y1), (x, y1)], fill=line_col, width=2)
            draw.line([(x, y1), (x, y2)], fill=line_col, width=2)
            draw.line([(x - 5, y2), (x, y2)], fill=line_col, width=2)
            cy = int((y1 + y2) / 2)
            cx = x + 22
            draw.line([(x, cy), (cx - badge_r, cy)], fill=line_col, width=2)
            draw_badge(draw, cx, cy, label)

        # 4. Crop Modal Palette Picker (palette_picker_annotated.png)
        #    Crop = what the overlay changed around the grid; badges sit on the
        #    geometry Blender reported (picker_geometry.json).
        if shot_palette_raw.is_file() and picker_geo_json.is_file():
            im_pal_raw = Image.open(shot_palette_raw)
            H = im_pal_raw.height
            geo = json.loads(picker_geo_json.read_text(encoding="utf-8"))
            gx0, gy0, gx1, gy1 = geo["grid"]          # window px, y up
            search = (int(gx0) - 120, int(H - gy1) - 160, int(gx1) + 120, int(H - gy0) + 120)
            bbox = diff_bbox(Image.open(shot_palette_before), im_pal_raw, search)
            m = 6
            pal_box = (bbox[0] - m, bbox[1] - m, bbox[2] + m, bbox[3] + m)
            pal_cropped = im_pal_raw.crop(pal_box).convert("RGBA")
            cw_raw, ch_raw = pal_cropped.size

            pad_left, pad_top, pad_right, pad_bot = 50, 45, 50, 45
            pal_canvas = Image.new("RGBA", (pad_left + cw_raw + pad_right, pad_top + ch_raw + pad_bot), (0, 0, 0, 0))
            pal_canvas.paste(pal_cropped, (pad_left, pad_top))
            c_draw = ImageDraw.Draw(pal_canvas)

            def cx_(x):  # window x -> canvas x
                return x - pal_box[0] + pad_left

            def cy_(y):  # window y (up) -> canvas y (down)
                return (H - y) - pal_box[1] + pad_top

            grid_top, grid_bot = cy_(gy1), cy_(gy0)
            # A: a group (the second one if there are several) -- above its heading
            groups = geo["groups"]
            g = groups[1] if len(groups) > 1 else groups[0]
            bracket_h(c_draw, cx_(g["x0"]) + 2, cx_(g["x1"]) - 2, pad_top - 6, "A")
            # B: one column (first of the last group) -- below the grid
            g = groups[-1]
            bracket_h(c_draw, cx_(g["x0"]) + 2, cx_(g["x0"] + geo["cell"]) - 3,
                      int(grid_bot) + 8, "B", up=False)
            # C: the rows -- right of the grid
            bracket_v(c_draw, pad_left + cw_raw + 6, int(grid_top) + 4, int(grid_bot) - 4, "C")
            # D: the active cell -- arrow from the left
            ax0, ay0, ax1, ay1 = geo["active"]
            target_x = cx_(ax0) - 2
            target_y = int(cy_((ay0 + ay1) / 2))
            cx_d = pad_left - 26
            c_draw.line([(cx_d + badge_r, target_y), (target_x, target_y)], fill=line_col, width=2)
            c_draw.polygon([(target_x, target_y), (target_x - 6, target_y - 4), (target_x - 6, target_y + 4)], fill=line_col)
            draw_badge(c_draw, cx_d, target_y, "D")

            save_to_targets(pal_canvas, "palette_picker_annotated.png", dpi=(144, 144))

        # 5. Crop Settings Dialog (settings_annotated.png)
        #    Crop = the popup that appeared at the mouse position; badges 1..4
        #    on the dialog's layout boxes: Palette (name + Templates row
        #    inside), Groups, Columns of ..., Material.
        if shot_settings_raw.is_file() and shot_settings_before.is_file():
            im_sett_raw = Image.open(shot_settings_raw)
            H = im_sett_raw.height
            sett_box = popup_rect(Image.open(shot_settings_before), im_sett_raw,
                                  SETTINGS_MOUSE[0], H - SETTINGS_MOUSE[1])
            sett_cropped = im_sett_raw.crop(sett_box).convert("RGBA")
            sw, sh = sett_cropped.size

            boxes = layout_boxes(sett_cropped.convert("RGB"), expected=4)
            if len(boxes) != 4:
                print(f"WARNING: found {len(boxes)} layout boxes in the Settings dialog, expected 4")

            # One image: the dialog fits a manual page.
            extra_w = 56
            mask = Image.new("L", (sw, sh), 0)
            ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (sw - 1, sh - 1)], radius=6, fill=255)
            sett_cropped.putalpha(mask)
            canvas = Image.new("RGBA", (sw + extra_w, sh), (0, 0, 0, 0))
            canvas.paste(sett_cropped, (0, 0))
            draw = ImageDraw.Draw(canvas)
            for i, (y1, y2) in enumerate(boxes):
                bracket_v(draw, sw + 6, y1, y2, str(i + 1))
            save_to_targets(canvas, "settings_annotated.png", dpi=(144, 144))

        # 6. Crop Geometry Node Graph (geo_nodes_lpc_set_material.png)
        if shot_node_raw.is_file():
            im_node_raw = Image.open(shot_node_raw)
            pad = 25
            node_box = (770 - pad, 314 - pad, 3440 + pad, 995 + pad)
            node_cropped = im_node_raw.crop(node_box)
            target_w = 1000
            target_h = int(node_cropped.height * (target_w / node_cropped.width))
            node_scaled = node_cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
            save_to_targets(node_scaled, "geo_nodes_lpc_set_material.png", dpi=(144, 144))


def main():
    parser = argparse.ArgumentParser(
        description="Automated screenshot capture pipeline for Low Poly Colorizer documentation."
    )
    default_dir = ROOT / "docs" / "manual" / "common" / "images"
    parser.add_argument(
        "output_dirs",
        nargs="*",
        type=Path,
        default=[default_dir],
        help=f"Target directories where captured and annotated images will be saved (default: {default_dir.relative_to(ROOT)}).",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Keep the raw window screenshots in this directory (default: temporary, deleted).",
    )
    args = parser.parse_args()
    capture(args.output_dirs, raw_dir=args.raw_dir)


if __name__ == "__main__":
    main()

