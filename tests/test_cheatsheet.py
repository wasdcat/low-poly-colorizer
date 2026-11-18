"""Layout of the palette cheatsheet PNG (pure part, no bpy)."""

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT / "tests"))

from export import cheatsheet, exporter, registry
from model import palette as P
from test_palette_groups import _stylized_palette


def _measure(text, size):
    return len(text) * size * 0.6, size * 0.7


class TestCheatsheetLayout(unittest.TestCase):
    def setUp(self):
        self.pal = _stylized_palette()
        self.lay = cheatsheet.layout(self.pal, _measure, title="Stylized 3D")

    def test_one_rect_per_cell_with_its_palette_color(self):
        cols, rows = P.cell_count(self.pal)
        colors = [r[4] for r in self.lay["rects"]]
        for y in range(rows):
            for x in range(cols):
                self.assertIn(P.color_at(x, y, self.pal), colors)

    def test_every_rect_inside_the_image(self):
        w, h = self.lay["size"]
        for x0, y0, x1, y1, _c in self.lay["rects"]:
            self.assertTrue(0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h)

    def test_one_vertical_name_per_column(self):
        names = [c["name"] for g in self.pal["groups"] for c in g["columns"]]
        vertical = [t["text"] for t in self.lay["texts"]
                    if t["rotation"] == -math.pi / 2]
        self.assertEqual(vertical, names)

    def test_names_fit_below_the_grid(self):
        grid_bottom = min(r[1] for r in self.lay["rects"][1:])
        for t in self.lay["texts"]:
            if t["rotation"]:
                self.assertLessEqual(t["y"], grid_bottom)
                self.assertGreaterEqual(t["y"] - _measure(t["text"], t["size"])[0], 0)

    def test_group_headings_and_row_numbers(self):
        texts = [t["text"] for t in self.lay["texts"] if not t["rotation"]]
        for g in self.pal["groups"]:
            if g["columns"]:
                self.assertIn(g["name"], texts)
        rows = P.cell_count(self.pal)[1]
        for r in range(rows):
            self.assertIn(str(r), texts)


class TestCheatsheetTitle(unittest.TestCase):
    def test_title_line_above_everything(self):
        lay = cheatsheet.layout(_stylized_palette(), _measure, title="Pod Rush")
        texts = [t for t in lay["texts"] if not t["rotation"]]
        title, credit = texts[0], texts[1]
        self.assertEqual(title["text"], "Pod Rush")
        self.assertEqual(credit["text"], "created with Low Poly Colorizer")
        self.assertEqual(title["y"], credit["y"])
        self.assertGreater(credit["x"], title["x"] + _measure("Pod Rush", title["size"])[0])
        for t in texts[2:]:
            self.assertLess(t["y"], title["y"])
        self.assertLessEqual(title["y"] + title["size"], lay["size"][1])

    def test_empty_name_falls_back(self):
        lay = cheatsheet.layout(_stylized_palette(), _measure, title="  ")
        self.assertEqual(lay["texts"][0]["text"], "Palette")

    def test_wide_title_widens_the_image(self):
        long = "A very long palette name " * 10
        lay = cheatsheet.layout(_stylized_palette(), _measure, title=long)
        credit = lay["texts"][1]
        self.assertLessEqual(credit["x"] + _measure(credit["text"], credit["size"])[0],
                             lay["size"][0])


class TestCheatsheetExport(unittest.TestCase):
    def test_godot_writes_it_with_a_skip_sidecar(self):
        self.assertTrue(registry.writes_cheatsheet("godot"))
        tpl = (ROOT / "addon" / "export" / "godot" /
               "{{prefix}}palette_cheatsheet.png.import.tpl").read_text("utf-8")
        self.assertIn('importer="skip"', tpl)
        self.assertEqual(exporter.CHEATSHEET_FILENAME, "lpc_palette_cheatsheet.png")


if __name__ == "__main__":
    unittest.main()
