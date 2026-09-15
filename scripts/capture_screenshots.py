# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Low Poly Colorizer (LPC). <https://github.com/wasdcat/low-poly-colorizer>
# A WASDCAT Games project. <https://www.wasdcat.com/>

"""Automated screenshot capture pipeline for Low Poly Colorizer documentation.

Launches Blender in GUI mode with event simulation:
1. Expands the 3D viewport sidebar and activates the LPC tab.
2. Captures and crops the N-Panel (n_panel.png & n_panel_annotated.png with badges 1..6).
3. Triggers the GPU Modal Palette Picker overlay (palette_picker_annotated.png with badges A..D).
4. Extracts the inline palette picker icon (icon_picker.png).
5. Opens the LPC Settings dialog (settings_annotated.png with badges 1..4).
6. Constructs and captures the LPC Set Material Geometry Node tree (geo_nodes_lpc_set_material.png).

Requirements:
- Blender 4.2+ or 5.x installed and discoverable.
- Calibrated for a 4K display resolution (3840x2160) with Blender maximized due to simulated UI coordinates.

Usage:
    python scripts/capture_screenshots.py <output_dir> [<output_dir> ...]

Examples:
    python scripts/capture_screenshots.py docs/manual/de/images docs/manual/en/images
    python scripts/capture_screenshots.py docs/manual/de/images
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent

BLENDER_CANDIDATES = [
    shutil.which("blender"),
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
]


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


def capture(output_dirs: list[Path]):
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
        base_blend = tmp_path / "base.blend"
        shot_panel_raw = tmp_path / "shot_panel_raw.png"
        shot_palette_raw = tmp_path / "shot_palette_raw.png"
        shot_settings_raw = tmp_path / "shot_settings_raw.png"
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

step = 0

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
            return 0.5

        elif step == 6:
            # Screenshot Modal Palette Picker
            bpy.ops.screen.screenshot(filepath=r"{shot_palette_raw}")
            win.event_simulate("ESC", "PRESS")
            win.event_simulate("ESC", "RELEASE")
            return 0.3

        elif step == 7:
            # Move mouse to center of 3D Viewport
            win.event_simulate("MOUSEMOVE", "NOTHING", x=2560, y=675)
            return 0.2

        elif step == 8:
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

        elif step == 9:
            # Screenshot Settings Dialog
            bpy.ops.screen.screenshot(filepath=r"{shot_settings_raw}")
            win.event_simulate("ESC", "PRESS")
            win.event_simulate("ESC", "RELEASE")
            return 0.3

        elif step == 10:
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
                lpc_node.inputs["Palette Cell X"].default_value = 4
            if "Palette Cell Y" in lpc_node.inputs:
                lpc_node.inputs["Palette Cell Y"].default_value = 2
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

        elif step == 11:
            # Frame selected nodes
            for a in win.screen.areas:
                if a.type == "NODE_EDITOR":
                    for r in a.regions:
                        if r.type == "WINDOW":
                            with bpy.context.temp_override(window=win, area=a, region=r, space_data=a.spaces.active):
                                bpy.ops.node.view_selected()
            return 0.3

        elif step == 12:
            # Deselect nodes for clean outline
            user_nt = bpy.data.node_groups.get("LPC_Geometry_Nodes")
            if user_nt:
                for n in user_nt.nodes:
                    n.select = False
            return 0.3

        elif step == 13:
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
            icon_crop = panel_cropped.crop((340, 54, 371, 78))
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

        # 4. Crop Modal Palette Picker (palette_picker_annotated.png)
        if shot_palette_raw.is_file():
            im_pal_raw = Image.open(shot_palette_raw)
            pal_box = (1782, 459, 2426, 804)
            pal_cropped = im_pal_raw.crop(pal_box).convert("RGBA")
            cw_raw, ch_raw = pal_cropped.size

            pad_left, pad_top, pad_right, pad_bot = 50, 45, 50, 25
            cw = pad_left + cw_raw + pad_right
            ch = pad_top + ch_raw + pad_bot

            pal_canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            pal_canvas.paste(pal_cropped, (pad_left, pad_top))
            c_draw = ImageDraw.Draw(pal_canvas)

            # A: Greyscale column
            x_g1 = pad_left + 4
            x_g2 = pad_left + 41
            y_top_br = pad_top - 6
            c_draw.line([(x_g1, y_top_br + 5), (x_g1, y_top_br)], fill=line_col, width=2)
            c_draw.line([(x_g1, y_top_br), (x_g2, y_top_br)], fill=line_col, width=2)
            c_draw.line([(x_g2, y_top_br + 5), (x_g2, y_top_br)], fill=line_col, width=2)
            cx_a = int((x_g1 + x_g2) / 2)
            cy_a = pad_top - 24
            c_draw.line([(cx_a, y_top_br), (cx_a, cy_a + badge_r)], fill=line_col, width=2)
            draw_badge(c_draw, cx_a, cy_a, "A")

            # B: Hue spectrum
            x_s1 = pad_left + 42
            x_s2 = pad_left + cw_raw - 4
            c_draw.line([(x_s1, y_top_br + 5), (x_s1, y_top_br)], fill=line_col, width=2)
            c_draw.line([(x_s1, y_top_br), (x_s2, y_top_br)], fill=line_col, width=2)
            c_draw.line([(x_s2, y_top_br + 5), (x_s2, y_top_br)], fill=line_col, width=2)
            cx_b = int((x_s1 + x_s2) / 2)
            cy_b = pad_top - 24
            c_draw.line([(cx_b, y_top_br), (cx_b, cy_b + badge_r)], fill=line_col, width=2)
            draw_badge(c_draw, cx_b, cy_b, "B")

            # C: Brightness & saturation gradient
            x_r = pad_left + cw_raw + 6
            y_r1 = pad_top + 4
            y_r2 = pad_top + ch_raw - 4
            c_draw.line([(x_r - 5, y_r1), (x_r, y_r1)], fill=line_col, width=2)
            c_draw.line([(x_r, y_r1), (x_r, y_r2)], fill=line_col, width=2)
            c_draw.line([(x_r - 5, y_r2), (x_r, y_r2)], fill=line_col, width=2)
            cy_c = int((y_r1 + y_r2) / 2)
            cx_c = x_r + 22
            c_draw.line([(x_r, cy_c), (cx_c - badge_r, cy_c)], fill=line_col, width=2)
            draw_badge(c_draw, cx_c, cy_c, "C")

            # D: Active cell & selection frame
            target_x = pad_left + 4
            target_y = pad_top + ch_raw - 22
            cx_d = pad_left - 26
            cy_d = target_y
            c_draw.line([(cx_d + badge_r, cy_d), (target_x, target_y)], fill=line_col, width=2)
            c_draw.polygon([(target_x, target_y), (target_x - 6, target_y - 4), (target_x - 6, target_y + 4)], fill=line_col)
            draw_badge(c_draw, cx_d, cy_d, "D")

            save_to_targets(pal_canvas, "palette_picker_annotated.png", dpi=(144, 144))

        # 5. Crop Settings Dialog (settings_annotated.png)
        if shot_settings_raw.is_file():
            im_sett_raw = Image.open(shot_settings_raw)
            sett_box = (2362, 605, 2841, 1185)
            sett_cropped = im_sett_raw.crop(sett_box).convert("RGBA")
            sw, sh = sett_cropped.size

            sett_mask = Image.new("L", (sw, sh), 0)
            s_draw = ImageDraw.Draw(sett_mask)
            s_draw.rounded_rectangle([(0, 0), (sw - 1, sh - 1)], radius=6, fill=255)
            sett_cropped.putalpha(sett_mask)

            extra_w = 56
            sett_canvas = Image.new("RGBA", (sw + extra_w, sh), (0, 0, 0, 0))
            sett_canvas.paste(sett_cropped, (0, 0))
            st_draw = ImageDraw.Draw(sett_canvas)

            sett_sections = [
                (1, 65, 198),   # 1: Grid
                (2, 206, 295),  # 2: Base Color
                (3, 303, 392),  # 3: Tint / Shade
                (4, 400, 521),  # 4: Globals
            ]

            bx = sw + 6
            cx = sw + 32
            for num, y1, y2 in sett_sections:
                cy = int((y1 + y2) / 2)
                st_draw.line([(bx - 5, y1), (bx, y1)], fill=line_col, width=2)
                st_draw.line([(bx, y1), (bx, y2)], fill=line_col, width=2)
                st_draw.line([(bx - 5, y2), (bx, y2)], fill=line_col, width=2)
                st_draw.line([(bx, cy), (cx - badge_r, cy)], fill=line_col, width=2)
                draw_badge(st_draw, cx, cy, str(num))

            save_to_targets(sett_canvas, "settings_annotated.png", dpi=(144, 144))

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
    parser.add_argument(
        "output_dirs",
        nargs="+",
        type=Path,
        help="One or more target directories where captured and annotated images will be saved (e.g. docs/manual/de/images docs/manual/en/images).",
    )
    args = parser.parse_args()
    capture(args.output_dirs)


if __name__ == "__main__":
    main()

