# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Palette I/O: JSON form, bundled templates, labels (plan step 3)."""

import copy
import json
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT / "tests"))

from model import palette as P
from model import templates as T
from picker import interface as I
from test_palette_groups import _stylized_palette


class TestJson(unittest.TestCase):
    def test_roundtrip(self):
        pal = _stylized_palette()
        back = P.palette_from_json(json.loads(json.dumps(P.palette_to_json(pal))))
        self.assertEqual(P.build_pixels(back), P.build_pixels(pal))
        self.assertEqual(back["groups"][0]["columns"][0]["span"], 2)
        self.assertIsNone(back["groups"][2]["columns"][0]["chroma"])

    def test_group_lightness_roundtrip(self):
        pal = _stylized_palette()
        pal["groups"][0]["l_bottom"] = 0.05
        data = P.palette_to_json(pal)
        self.assertEqual(data["groups"][0]["l_bottom"], 0.05)
        self.assertNotIn("l_top", data["groups"][0])
        back = P.palette_from_json(data)
        self.assertEqual(back["groups"][0]["l_bottom"], 0.05)
        self.assertIsNone(back["groups"][0]["l_top"])

    def test_defaults(self):
        pal = P.palette_from_json({"groups": [{"name": "G", "columns": [{"id": "a"}]}]})
        self.assertEqual(pal["rows"], P.DEFAULT_ROWS)
        self.assertEqual(pal["groups"][0]["columns"][0]["name"], "a")
        self.assertEqual(P.cell_count(pal), (1, P.DEFAULT_ROWS))

    def test_errors(self):
        good = P.palette_to_json(_stylized_palette())
        cases = [
            lambda d: d.update(colour=1),                                  # unknown key
            lambda d: d.update(rows=0),
            lambda d: d.update(rows=2.5),
            lambda d: d.update(tint=2),
            lambda d: d["groups"][0].update(chroma="x"),
            lambda d: d["groups"][1]["columns"][0].update(hue=400),
            lambda d: d["groups"][1]["columns"][0].update(id=5),
            lambda d: d["groups"][1]["columns"][0].update(id="grau"),      # duplicate
            lambda d: d["groups"][1]["columns"][0].update(span=3),
            lambda d: d["groups"][1]["columns"][0].update(spam=1),
            lambda d: d.update(groups=[]),
        ]
        for i, mutate in enumerate(cases):
            data = copy.deepcopy(good)
            mutate(data)
            with self.subTest(case=i), self.assertRaises(ValueError):
                P.palette_from_json(data)


class TestTemplates(unittest.TestCase):
    def test_bundled(self):
        slugs = dict(T.list_templates())
        self.assertEqual(slugs, {"classic_color_wheel": "Classic Color Wheel",
                                 "industrial_planet": "Industrial Planet",
                                 "stylized_3d": "Stylized 3D",
                                 "toon_outdoor": "Toon Outdoor"})
        self.assertIn(T.DEFAULT_TEMPLATE, slugs)
        self.assertEqual(T.template_name("industrial_planet"), "Industrial Planet")
        self.assertEqual(T.template_name("nope"), "nope")

    def test_stylized_is_the_approved_palette(self):
        # The plan's palette, retuned for the color space fix: 7 rows,
        # lighter top / darker bottom limits within a plausible albedo, less
        # tint, Nature chroma +25 %, grey as one column with a darker range.
        approved = _stylized_palette()
        approved.update(rows=7, l_top=0.9, l_bottom=0.33, tint=0.5)
        neutral, nature, _accent = approved["groups"]
        neutral.update(l_top=0.95, l_bottom=0.28)
        neutral["columns"][0]["span"] = 1
        nature["chroma"] = 0.0625
        for column in nature["columns"]:
            if column["chroma"] is not None:
                column["chroma"] = round(column["chroma"] * 1.25, 4)
        self.assertEqual(P.build_pixels(T.load_template("stylized_3d")),
                         P.build_pixels(approved))

    def test_classic_layout(self):
        # One grey column plus 16 evenly spaced hues, 9 rows.
        classic = T.load_template("classic_color_wheel")
        self.assertEqual(P.cell_count(classic), (17, 9))
        self.assertEqual([(name, n) for name, _x, n in P.group_ranges(classic)],
                         [("Greyscale", 1), ("Color Wheel", 16)])
        hues = [c["hue"] for c, _part in P.grid_columns(classic)][1:]
        self.assertEqual(hues, [i * 22.5 for i in range(16)])

    def test_templates_stay_plausible_albedo(self):
        # Every cell between ~40 and ~250 (8-bit sRGB luminance): no black
        # or white albedo, which no lit surface has.
        def lin(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for slug, _name in T.list_templates():
            pal = T.load_template(slug)
            cols, rows = P.cell_count(pal)
            for x in range(cols):
                for y in range(rows):
                    r, g, b = (lin(v) for v in P.color_at(x, y, pal)[:3])
                    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    with self.subTest(slug=slug, x=x, y=y):
                        self.assertTrue(0.02 <= lum <= 0.95, lum)

    def test_file_errors(self):
        with self.assertRaises(ValueError):
            T.read_palette_file("{nope")
        with self.assertRaises(ValueError):
            T.read_palette_file(json.dumps({"version": 1, "presets": []}))
        with self.assertRaises(ValueError):
            T.read_palette_file(json.dumps({"version": 2}))

    def test_write_read(self):
        text = T.write_palette_file(_stylized_palette(), "Mine")
        name, pal = T.read_palette_file(text)
        self.assertEqual(name, "Mine")
        self.assertEqual(P.build_pixels(pal), P.build_pixels(_stylized_palette()))


class TestLabels(unittest.TestCase):
    def test_cell_label(self):
        pal = _stylized_palette()
        self.assertEqual(P.cell_label(pal, 0, 0), "Neutral · Grau 1")
        self.assertEqual(P.cell_label(pal, 1, 4), "Neutral · Grau 10")
        self.assertEqual(P.cell_label(pal, 9, 2), "Natur · Moos 3")
        self.assertEqual(P.cell_label(pal, 22, 0), "")


class TestSceneFallback(unittest.TestCase):
    """`params_from_scene` on scenes whose palette was never written."""

    @staticmethod
    def _scene(raw, presets=()):
        class Raw(dict):
            initialized = False
        return SimpleNamespace(lpc_palette_params=Raw(raw), lpc_presets=list(presets))

    def test_untouched_scene_gets_default_template(self):
        pal = I.params_from_scene(self._scene({}))
        self.assertEqual(P.build_pixels(pal), P.build_pixels(T.load_template(T.DEFAULT_TEMPLATE)))

    def test_default_palette_is_a_copy(self):
        a = I.default_palette()
        a["groups"][0]["columns"][0]["name"] = "changed"
        self.assertNotEqual(I.default_palette()["groups"][0]["columns"][0]["name"], "changed")


if __name__ == "__main__":
    unittest.main()
