# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Palette I/O: 1.x values, JSON form, bundled templates, labels (plan step 3)."""

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


class TestLegacy(unittest.TestCase):
    def test_missing_values_use_1x_defaults(self):
        self.assertEqual(P.params_from_legacy({}), P.LEGACY_DEFAULTS)
        params = P.params_from_legacy({"cols": 12, "brightness": 0.5, "color_mode": 1})
        self.assertEqual(params["cols"], 12)
        self.assertEqual(params["brightness"], 0.5)
        self.assertEqual(params["rows"], 9)
        self.assertNotIn("color_mode", params)

    def test_has_legacy_values(self):
        self.assertFalse(P.has_legacy_values({}))
        self.assertFalse(P.has_legacy_values({"rows": 7, "tint": 0.3}))  # also 2.0 keys
        self.assertTrue(P.has_legacy_values({"cols": 16}))
        self.assertTrue(P.has_legacy_values({"color_mode": 0}))


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
                                 "stylized_3d": "Stylized 3D"})
        self.assertIn(T.DEFAULT_TEMPLATE, slugs)

    def test_stylized_is_the_approved_palette(self):
        self.assertEqual(P.build_pixels(T.load_template("stylized_3d")),
                         P.build_pixels(_stylized_palette()))

    def test_classic_is_1x_default_converted(self):
        self.assertEqual(
            P.build_pixels(T.load_template("classic_color_wheel")),
            P.build_pixels(P.palette_from_params(P.LEGACY_DEFAULTS)))

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

    def test_1x_scene_is_converted(self):
        pal = I.params_from_scene(self._scene({"cols": 8, "rows": 6}))
        self.assertEqual(P.cell_count(pal), (9, 6))
        self.assertEqual(P.group_ranges(pal)[1][0], P.CLASSIC_WHEEL_GROUP)

    def test_default_palette_is_a_copy(self):
        a = I.default_palette()
        a["groups"][0]["columns"][0]["name"] = "changed"
        self.assertNotEqual(I.default_palette()["groups"][0]["columns"][0]["name"], "changed")


if __name__ == "__main__":
    unittest.main()
