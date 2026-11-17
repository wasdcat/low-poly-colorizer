# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from export import exporter, registry
from model import palette as model_palette
from picker import interface as picker_interface


class TestExporter(unittest.TestCase):
    def test_pascal(self):
        self.assertEqual(exporter._pascal("lpc_"), "Lpc")
        self.assertEqual(exporter._pascal("my_custom_game_"), "MyCustomGame")
        self.assertEqual(exporter._pascal("prefix"), "Prefix")
        self.assertEqual(exporter._pascal(""), "")

    def test_preset_identifiers_sanitization(self):
        # Mock scene with various preset names
        class DummyPreset:
            def __init__(self, name):
                self.name = name

        scene = SimpleNamespace(
            lpc_presets=[
                DummyPreset("Solid"),
                DummyPreset("Signal Red"),
                DummyPreset("Grün & Blau"),  # Non-ascii and special chars
                DummyPreset("123 Numeric"),   # Leading digit
                DummyPreset("!!! Special"),   # Special only
                DummyPreset("Duplicate"),     # Duplicate collision
                DummyPreset("Duplicate"),
            ]
        )

        idents = exporter._preset_identifiers(scene)
        self.assertEqual(idents[0], "SOLID")
        self.assertEqual(idents[1], "SIGNAL_RED")
        self.assertEqual(idents[2], "GRUN_BLAU")
        self.assertEqual(idents[3], "PRESET_123_NUMERIC")
        self.assertEqual(idents[4], "SPECIAL")
        self.assertEqual(idents[5], "DUPLICATE")
        self.assertEqual(idents[6], "DUPLICATE_2")

    def test_preset_identifiers_empty(self):
        scene = SimpleNamespace(lpc_presets=[])
        idents = exporter._preset_identifiers(scene)
        self.assertEqual(idents, ["PRESET_0"])

    def test_render_template(self):
        template = "uniform vec2 size = vec2({{width}}, {{height}});\n// {{unknown_tag}}"
        mapping = {"width": "16.0", "height": "9.0"}
        rendered = exporter._render(template, mapping)
        self.assertEqual(
            rendered,
            "uniform vec2 size = vec2(16.0, 9.0);\n// {{unknown_tag}}",
        )

    def test_strip_tpl(self):
        self.assertEqual(exporter._strip_tpl("shader.gdshader.tpl"), "shader.gdshader")
        self.assertEqual(exporter._strip_tpl("README.md"), "README.md")


def _preset(name, roughness=0.5, metallic=0.0, clearcoat=0.0, emission=0.0):
    return SimpleNamespace(
        name=name, roughness=roughness, metallic=metallic,
        clearcoat=clearcoat, emission=emission,
    )


def _scene(presets=None, **palette_overrides):
    palette = dict(
        cols=5, rows=4, add_greyscale=True, saturation=0.9, brightness=0.8,
        tint=0.7, shade=0.6, color_mode="OKLCH", hue_shift=0.5, warmth=-0.3,
    )
    palette.update(palette_overrides)
    return SimpleNamespace(
        lpc_palette_params=SimpleNamespace(**palette),
        lpc_globals=SimpleNamespace(emission_factor=2.0, clearcoat_roughness=0.1),
        lpc_presets=presets if presets is not None else [
            _preset("Solid", 0.8),
            _preset("Lamp", 0.8, emission=1.0),
            _preset("Chrome", 0.2, metallic=1.0, clearcoat=0.5),
        ],
    )


_FLOAT = r"(-?\d+\.\d+)"


class TestPaletteArray(unittest.TestCase):
    """The palette written into the GDScript resource as a constant array."""

    def test_lit_is_always_a_fixed_point_float(self):
        self.assertEqual(exporter._lit(1), "1.0")
        self.assertEqual(exporter._lit(0.5), "0.5")
        self.assertEqual(exporter._lit(0.1234567), "0.123457")
        self.assertEqual(exporter._lit(1e-7), "0.0")  # no "1e-07"
        self.assertEqual(exporter._lit(-0.0), "0.0")
        self.assertEqual(exporter._lit(-1e-9), "0.0")

    def test_palette_matches_color_at_cell_by_cell(self):
        params = picker_interface.params_from_scene(_scene())
        cols, rows = model_palette.cell_count(params)
        body = exporter._palette_colors_gdscript(params)
        entries = re.findall(rf"Color\({_FLOAT}, {_FLOAT}, {_FLOAT}\)", body)
        self.assertEqual(len(entries), cols * rows)
        for y in range(rows):
            for x in range(cols):
                expected = model_palette.color_at(x, y, params)[:3]
                got = tuple(float(v) for v in entries[y * cols + x])
                for e, g in zip(expected, got):
                    self.assertAlmostEqual(e, g, places=6)
        self.assertEqual(len(body.splitlines()), rows)  # one palette row per line

    def test_palette_follows_artwork_settings(self):
        # The bug this array fixes: the old GDScript recomputed HSV only.
        plain = exporter._palette_colors_gdscript(
            picker_interface.params_from_scene(_scene(color_mode="HSV", hue_shift=0.0, warmth=0.0)))
        styled = exporter._palette_colors_gdscript(
            picker_interface.params_from_scene(_scene()))
        self.assertNotEqual(plain, styled)


class TestStableUid(unittest.TestCase):
    def test_godot_encoding(self):
        # Reference values from ResourceUID.id_to_text in Godot 4.8.
        def encode(n):
            text = ""
            while True:
                n, d = divmod(n, 34)
                text = exporter._UID_ALPHABET[d] + text
                if n == 0:
                    return "uid://" + text
        self.assertEqual(encode(0), "uid://a")
        self.assertEqual(encode(25), "uid://0")
        self.assertEqual(encode(34), "uid://ba")
        self.assertEqual(encode(1000000), "uid://0pb1")
        self.assertEqual(encode(2**63 - 1), "uid://d4n4ub6itg400")

    def test_uid_is_stable_valid_and_name_dependent(self):
        a = exporter.stable_uid("lpc_palette.png")
        self.assertEqual(a, exporter.stable_uid("lpc_palette.png"))
        self.assertNotEqual(a, exporter.stable_uid("lpc_preset_lut.png"))
        self.assertNotEqual(a, exporter.stable_uid("other_palette.png"))  # prefix matters
        self.assertRegex(a, r"^uid://[a-y0-8]{1,13}$")
        n = 0
        for ch in a[len("uid://"):]:
            n = n * 34 + exporter._UID_ALPHABET.index(ch)
        self.assertLess(n, 2**63)

    def test_sidecars_share_their_subjects_uid(self):
        entries = [
            "{{prefix}}palette.png.import.tpl",
            "{{prefix}}multicolor.gdshader.tpl",
            "{{prefix}}multicolor.gdshader.uid.tpl",
            "{{prefix}}multicolor.tres.tpl",
        ]
        uids = exporter.uid_context(entries, {"prefix": "lpc_"})
        self.assertEqual(set(uids), {"uid_palette_png", "uid_multicolor_gdshader", "uid_multicolor_tres"})
        self.assertEqual(uids["uid_palette_png"], exporter.stable_uid("lpc_palette.png"))
        self.assertEqual(uids["uid_multicolor_gdshader"], exporter.stable_uid("lpc_multicolor.gdshader"))


class TestGodotSet(unittest.TestCase):
    def _render(self, scene=None):
        context = exporter.build_context(scene or _scene())
        with tempfile.TemporaryDirectory() as out_dir:
            written = exporter.render_set("godot", out_dir, context)
            texts = {}
            for name in written:
                with open(os.path.join(out_dir, name), encoding="utf-8") as f:
                    texts[name] = f.read()
        return texts

    def test_templates_render_completely(self):
        for name, text in self._render().items():
            self.assertNotRegex(text, r"\{\{\w+\}\}", f"unresolved placeholder in {name}")

    def test_every_uid_bearing_file_gets_its_sidecar(self):
        texts = self._render()
        for name in ("lpc_common.gdshaderinc", "lpc_multicolor.gdshader",
                     "lpc_singlecolor.gdshader", "lpc_singlecolor_resource.gd",
                     "lpc_palette_color_resource.gd"):
            self.assertEqual(texts[name + ".uid"], exporter.stable_uid(name) + "\n")
        for png in (exporter.PALETTE_IMAGE_FILENAME, exporter.PRESET_LUT_IMAGE_FILENAME):
            imp = texts[png + ".import"]
            self.assertIn(f'uid="{exporter.stable_uid(png)}"', imp)
            for setting in ("compress/mode=0", "mipmaps/generate=false",
                            "process/fix_alpha_border=false", "detect_3d/compress_to=0"):
                self.assertIn(setting, imp)

    def test_materials_reference_by_stable_uid(self):
        texts = self._render()
        for variant in ("multicolor", "singlecolor"):
            tres = texts[f"lpc_{variant}.tres"]
            self.assertIn(f'uid="{exporter.stable_uid(f"lpc_{variant}.tres")}"', tres.splitlines()[0])
            self.assertIn(f'uid="{exporter.stable_uid(f"lpc_{variant}.gdshader")}"', tres)
            self.assertIn(f'uid="{exporter.stable_uid("lpc_palette.png")}"', tres)
            self.assertIn(f'uid="{exporter.stable_uid("lpc_preset_lut.png")}"', tres)

    def test_singlecolor_extends_palette_color(self):
        texts = self._render()
        base = texts["lpc_palette_color_resource.gd"]
        look = texts["lpc_singlecolor_resource.gd"]
        self.assertIn("class_name LpcPaletteColorResource\nextends Resource", base)
        self.assertIn("class_name LpcSinglecolorResource\nextends LpcPaletteColorResource", look)
        self.assertIn("const PALETTE: PackedColorArray = [", base)
        self.assertIn("var palette_cell_x", base)
        # the cell lives in the base only -- a redeclaration would be a parse error
        self.assertNotIn("var palette_cell_x", look)
        self.assertNotIn("const PALETTE", look)
