# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import json
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


def _palette_props(pal):
    """An initialized LPC_PaletteParams stand-in holding `pal`."""
    groups = [SimpleNamespace(
        name=g["name"], chroma=g["chroma"],
        use_l_top=g.get("l_top") is not None, l_top=g.get("l_top") or 0.0,
        use_l_bottom=g.get("l_bottom") is not None, l_bottom=g.get("l_bottom") or 0.0,
        columns=[SimpleNamespace(
            column_id=c["id"], name=c["name"], hue=c["hue"],
            use_chroma=c.get("chroma") is not None, chroma=c.get("chroma") or 0.0,
            span=c.get("span", 1)) for c in g["columns"]],
    ) for g in pal["groups"]]
    return SimpleNamespace(
        groups=groups, rows=pal["rows"], l_top=pal["l_top"], l_bottom=pal["l_bottom"],
        tint=pal["tint"], shade=pal["shade"], hue_shift=pal["hue_shift"],
        warmth=pal["warmth"], initialized=True,
    )


def _scene(presets=None, **palette_overrides):
    pal = model_palette.palette_from_params(model_palette.params_from_legacy(dict(
        cols=5, rows=4, add_greyscale=True, saturation=0.9, brightness=0.8,
        tint=0.7, shade=0.6, hue_shift=0.5, warmth=-0.3,
    )))
    pal.update(palette_overrides)
    return SimpleNamespace(
        lpc_palette_params=_palette_props(pal),
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
            picker_interface.params_from_scene(_scene(hue_shift=0.0, warmth=0.0)))
        styled = exporter._palette_colors_gdscript(
            picker_interface.params_from_scene(_scene()))
        self.assertNotEqual(plain, styled)


ENUM_SEP = ",\n\t\t"  # separator of _palette_cell_x_enum's entries


class TestPaletteStructure(unittest.TestCase):
    """Groups, column names and the Inspector enum for palette_cell_x."""

    def _params(self):
        return picker_interface.params_from_scene(_scene())

    def test_groups(self):
        body = exporter._palette_groups_gdscript(self._params())
        self.assertEqual(body.splitlines(), [
            '\t{"name": "Greyscale", "first": 0, "count": 1},',
            '\t{"name": "Color Wheel", "first": 1, "count": 5},',
        ])

    def test_column_names_and_enum_align_with_x(self):
        params = self._params()
        names = exporter._palette_column_names_gdscript(params).splitlines()
        self.assertEqual(len(names), 6)
        self.assertEqual(names[0], '\t"Greyscale · Grey",')
        enum = exporter._palette_cell_x_enum(params).split(ENUM_SEP)
        self.assertEqual(len(enum), 6)
        self.assertEqual(enum[3], '"Color Wheel · Hue 3:3"')

    def test_free_text_is_escaped(self):
        backslash = chr(92)
        pal = model_palette.palette_from_json({"groups": [{"name": 'Say "hi", ok', "columns": [
            {"id": "a", "name": "A:B" + backslash + "C", "span": 2}]}]})
        enum = exporter._palette_cell_x_enum(pal).split(ENUM_SEP)
        # "," and ":" would split Godot's enum hint -> spaces; quotes and
        # backslashes are escaped as in JSON (valid GDScript).
        plain = 'Say "hi"  ok · A B' + backslash + 'C'
        self.assertEqual(enum[0], json.dumps(plain + " 1/2:0", ensure_ascii=False))
        self.assertEqual(enum[1], json.dumps(plain + " 2/2:1", ensure_ascii=False))
        groups = exporter._palette_groups_gdscript(pal)
        self.assertIn('"name": ' + json.dumps('Say "hi", ok'), groups)

    def test_shader_hint_enum_aligns_with_x(self):
        entries = exporter._palette_cell_x_hint_enum(self._params()).split(",\n    ")
        self.assertEqual(len(entries), 6)
        self.assertEqual(entries[0], '"Greyscale · Grey"')
        self.assertEqual(entries[3], '"Color Wheel · Hue 3"')

    def test_shader_hint_enum_has_no_escapes(self):
        # Godot's shader tokenizer knows no escape sequences: no `"` or
        # backslash inside a string; "," / ":" would split the enum hint.
        backslash = chr(92)
        pal = model_palette.palette_from_json({"groups": [{"name": 'Say "hi", ok', "columns": [
            {"id": "a", "name": "A:B" + backslash + "C"}]}]})
        self.assertEqual(exporter._palette_cell_x_hint_enum(pal),
                         '"Say \'hi\'  ok · A B/C"')

    def test_in_context(self):
        context = exporter.build_context(_scene())
        for key in ("palette_groups_gdscript", "palette_column_names_gdscript",
                    "palette_cell_x_enum", "palette_cell_x_hint_enum"):
            self.assertIn(key, context)
        for key in ("palette_has_greyscale", "palette_saturation",
                    "palette_brightness", "palette_color_mode"):
            self.assertNotIn(key, context)


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


class TestPresetArray(unittest.TestCase):
    """The presets as a shader array body -- for targets without a LUT."""

    def test_in_list_order_with_names(self):
        lines = exporter._preset_values_glsl(_scene()).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("vec4(0.8, 0.0, 0.0, 1.0)", lines[1])
        self.assertIn("// 1 = Lamp", lines[1])
        self.assertIn("vec4(0.2, 1.0, 0.5, 0.0)", lines[2])
        self.assertTrue(lines[0].split("//")[0].rstrip().endswith(","))
        self.assertFalse(lines[2].split("//")[0].rstrip().endswith(","))  # GLSL: no trailing comma

    def test_name_cannot_break_out_of_comment(self):
        body = exporter._preset_values_glsl(_scene([_preset("Evil\nvoid x(){}")]))
        self.assertEqual(len(body.splitlines()), 1)

    def test_empty_preset_list_still_yields_one_entry(self):
        scene = _scene([])
        self.assertEqual(len(re.findall(r"vec4\(", exporter._preset_values_glsl(scene))), 1)
        self.assertEqual(exporter.build_context(scene)["preset_count"], "1")


class TestRegistryTextures(unittest.TestCase):
    def test_godot_ships_both_textures(self):
        self.assertTrue(registry.writes_palette_texture("godot"))
        self.assertTrue(registry.writes_preset_texture("godot"))

    def test_flags_default_to_true_and_unknown_set_writes_nothing(self):
        original = registry.TEMPLATE_SETS
        try:
            registry.TEMPLATE_SETS = ({"id": "plain", "label": "", "dir": "plain"},)
            self.assertTrue(registry.writes_palette_texture("plain"))
            self.assertTrue(registry.writes_preset_texture("plain"))
            self.assertFalse(registry.writes_palette_texture("nope"))
            self.assertFalse(registry.writes_preset_texture("nope"))
        finally:
            registry.TEMPLATE_SETS = original


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

    def test_shaders_sample_both_textures(self):
        common = self._render()["lpc_common.gdshaderinc"]
        self.assertIn("uniform sampler2D lpc_palette_tex", common)
        self.assertIn("uniform sampler2D lpc_preset_lut_tex", common)

    def test_singlecolor_cell_x_is_a_hint_enum_dropdown(self):
        shader = self._render()["lpc_singlecolor.gdshader"]
        self.assertIn('instance uniform int lpc_palette_cell_x : hint_enum(\n'
                      '    "Greyscale · Grey",\n', shader)
        self.assertNotIn("{{", shader)

    def test_singlecolor_preset_is_a_hint_enum_dropdown(self):
        shader = self._render()["lpc_singlecolor.gdshader"]
        self.assertIn('instance uniform int lpc_preset_position : hint_enum(\n'
                      '    "Solid",\n    "Lamp",\n    "Chrome"\n) = 0;', shader)

    def test_preset_hint_enum_without_presets(self):
        self.assertEqual(exporter._preset_hint_enum(_scene(presets=[])),
                         '"(no presets)"')

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

    def test_palette_color_shows_read_only_color_field(self):
        base = self._render()["lpc_palette_color_resource.gd"]
        self.assertIn("@export_color_no_alpha var color: Color:", base)
        self.assertIn("		return get_color()", base)
        # editor-only and greyed out: never saved to the .tres, cannot be set
        self.assertIn('if property.name == "color":', base)
        self.assertIn("PROPERTY_USAGE_EDITOR | PROPERTY_USAGE_READ_ONLY", base)
        self.assertNotIn("PROPERTY_USAGE_STORAGE", base)
