# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""LPC file format version 2: palette + presets (plan step 4)."""

import json
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT / "tests"))

from model import palette as P
from model import templates as T
from ops import file_io as F
from ops import presets as ops_presets
from test_palette_groups import _stylized_palette

PRESETS = [
    ops_presets.make_preset("Solid", roughness=0.8),
    ops_presets.make_preset("Gold", roughness=0.25, metallic=1.0, emission=0.30000001192),
]


class TestWriteRead(unittest.TestCase):
    def test_both_sections(self):
        data = F.read_lpc_file(F.write_lpc_file(_stylized_palette(), PRESETS, name="Mine"))
        self.assertEqual(data["name"], "Mine")
        self.assertEqual(P.build_pixels(data["palette"]), P.build_pixels(_stylized_palette()))
        self.assertEqual([p["name"] for p in data["presets"]], ["Solid", "Gold"])
        self.assertEqual(data["presets"][1]["emission"], 0.3)   # rounded

    def test_single_sections(self):
        only_palette = json.loads(F.write_lpc_file(palette=_stylized_palette()))
        self.assertNotIn("presets", only_palette)
        data = F.read_lpc_file(json.dumps(only_palette))
        self.assertIsNone(data["presets"])
        self.assertIsNotNone(data["palette"])

        only_presets = json.loads(F.write_lpc_file(presets=PRESETS))
        self.assertNotIn("palette", only_presets)
        data = F.read_lpc_file(json.dumps(only_presets))
        self.assertIsNone(data["palette"])
        self.assertEqual(len(data["presets"]), 2)

    def test_float32_noise_is_rounded(self):
        pal = _stylized_palette()
        pal["l_top"] = 0.9300000071525574
        pal["groups"][1]["columns"][0]["chroma"] = 0.05999999865889549
        data = json.loads(F.write_lpc_file(palette=pal))["palette"]
        self.assertEqual(data["l_top"], 0.93)
        self.assertEqual(data["groups"][1]["columns"][0]["chroma"], 0.06)

    def test_nothing_to_export(self):
        with self.assertRaises(ValueError):
            F.write_lpc_file()


class TestCompatibility(unittest.TestCase):
    def test_version_1_files_are_rejected(self):
        # No compatibility with LPC 1.x preset files.
        text = json.dumps({"version": 1, "presets": [
            {"name": "Old", "roughness": 0.5, "metallic": 0, "emission": 0, "clearcoat": 0}]})
        with self.assertRaises(ValueError):
            F.read_lpc_file(text)

    def test_templates_are_lpc_files(self):
        for slug, _name in T.list_templates():
            text = (T.TEMPLATE_DIR / (slug + ".json")).read_text(encoding="utf-8")
            data = F.read_lpc_file(text)
            self.assertEqual(P.build_pixels(data["palette"]),
                             P.build_pixels(T.load_template(slug)))
            self.assertIsNone(data["presets"])


class TestErrors(unittest.TestCase):
    def test_invalid(self):
        for text in (
            "{nope",
            "[]",
            json.dumps({"version": 3, "presets": []}),
            json.dumps({"version": 2}),                                   # no section
            json.dumps({"version": 2, "presets": [], "extra": 1}),        # unknown key
            json.dumps({"version": 2, "presets": [{"roughness": 1}]}),    # preset w/o name
            json.dumps({"version": 2, "palette": {"groups": []}}),        # no columns
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                F.read_lpc_file(text)


if __name__ == "__main__":
    unittest.main()
