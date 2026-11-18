# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Group/column palette model (docs/plan_palettengruppen.md, step 1)."""

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from model import palette as P


def _wheel_palette(cols=16, rows=9, grey=True, chroma=0.16, **overrides):
    """Test fixture: an optional "Greyscale" group (one grey column from
    white to black) plus a "Color Wheel" group of `cols` evenly spaced hues
    with ids "hue-<i>"."""
    groups = []
    if grey:
        groups.append({"name": "Greyscale", "chroma": 0.0, "l_top": 1.0, "l_bottom": 0.0,
                       "columns": [{"id": "grey", "name": "Grey", "hue": 0.0,
                                    "chroma": None, "span": 1}]})
    groups.append({"name": "Color Wheel", "chroma": chroma,
                   "columns": [{"id": "hue-%d" % i, "name": "Hue %d" % (i + 1),
                                "hue": i * 360.0 / cols, "chroma": None, "span": 1}
                               for i in range(cols)]})
    pal = {"groups": groups, "rows": rows, "l_top": 0.94, "l_bottom": 0.22,
           "tint": 0.8, "shade": 0.8, "hue_shift": 0.0, "warmth": 0.0}
    pal.update(overrides)
    return pal


# The approved palette ("Stilisiertes 3D"): 22 grid columns x 5 rows.
def _stylized_palette():
    def col(cid, name, hue, chroma=None, span=1):
        return {"id": cid, "name": name, "hue": hue, "chroma": chroma, "span": span}

    return {
        "groups": [
            {"name": "Neutral", "chroma": 0.02, "columns": [
                col("grau", "Grau", 0, 0.0, span=2),
                col("kuehl", "Kühl", 250),
                col("warm", "Warm", 70),
            ]},
            {"name": "Natur", "chroma": 0.05, "columns": [
                col("rost", "Rost", 35, 0.06), col("braun", "Braun", 55, 0.055),
                col("ocker", "Ocker", 75, 0.06), col("sand", "Sand", 85, 0.045),
                col("oliv", "Oliv", 110, 0.055), col("moos", "Moos", 135),
                col("tanne", "Tanne", 165, 0.045), col("schiefer", "Schiefer", 245, 0.035),
            ]},
            {"name": "Akzent", "chroma": 0.17, "columns": [
                col("rot", "Rot", 25), col("orange", "Orange", 50), col("gelb", "Gelb", 90),
                col("limette", "Limette", 125), col("gruen", "Grün", 150),
                col("cyan", "Cyan", 195), col("azur", "Azur", 235), col("blau", "Blau", 265),
                col("violett", "Violett", 300), col("magenta", "Magenta", 345),
            ]},
        ],
        "rows": 5, "l_top": 0.93, "l_bottom": 0.25,
        "tint": 0.8, "shade": 0.9, "hue_shift": 0.5, "warmth": 0.2,
    }


# Reference generator from the plan's appendix, verbatim apart from the
# image code: (name, hue, peak chroma[, half of the grey ramp]).
_REF_ROWS = 5
_REF_L_TOP, _REF_L_BOTTOM = 0.93, 0.25
_REF_G = dict(tint=0.8, shade=0.9, hue_shift=0.5, warmth=0.2)
_REF_COLUMNS = [
    ("Grau", 0, 0.0, 0), ("Grau+", 0, 0.0, 1), ("Kühl", 250, 0.02), ("Warm", 70, 0.02),
    ("Rost", 35, 0.06), ("Braun", 55, 0.055), ("Ocker", 75, 0.06), ("Sand", 85, 0.045),
    ("Oliv", 110, 0.055), ("Moos", 135, 0.05), ("Tanne", 165, 0.045), ("Schiefer", 245, 0.035),
    ("Rot", 25, 0.17), ("Orange", 50, 0.17), ("Gelb", 90, 0.17), ("Limette", 125, 0.17),
    ("Grün", 150, 0.17), ("Cyan", 195, 0.17), ("Azur", 235, 0.17), ("Blau", 265, 0.17),
    ("Violett", 300, 0.17), ("Magenta", 345, 0.17),
]


def _ref_cell(h0, cpeak, y, half=None):
    ROWS, G = _REF_ROWS, _REF_G
    t = y / (ROWS - 1)
    if half is not None:
        t = (half * ROWS + y) / (2 * ROWS - 1)
    hs, w = G["hue_shift"], G["warmth"]
    h = (h0 + w * 30.0) % 360.0
    if t <= 0.5:
        rf = 1 - t / 0.5
        diff = (95.0 - h + 180) % 360 - 180
        h = (h + diff * 0.22 * abs(hs) * rf) % 360
        C = cpeak * (1 - 0.5 * G["tint"] * rf)
    else:
        rf = (t - 0.5) / 0.5
        diff = (265.0 - h + 180) % 360 - 180
        h = (h + diff * 0.28 * abs(hs) * rf) % 360
        C = cpeak * (1 - 0.25 * G["shade"] * rf)
    L = _REF_L_TOP - (_REF_L_TOP - _REF_L_BOTTOM) * t
    if cpeak == 0:
        cool = (t - 0.5) * 0.02 * hs
        wb = w * 0.01
        return P._oklab_to_srgb(L, wb - cool * 0.4, wb - cool * 0.8)
    return P._oklch_to_rgb_clamped(L, C, h)


class TestStylizedPalette(unittest.TestCase):
    """The approved palette matches the plan's reference generator."""

    def setUp(self):
        self.pal = _stylized_palette()

    def test_valid_and_dimensions(self):
        P.validate_palette(self.pal)
        self.assertEqual(P.cell_count(self.pal), (22, 5))
        self.assertEqual(P.group_ranges(self.pal), [
            ("Neutral", 0, 4), ("Natur", 4, 8), ("Akzent", 12, 10)])

    def test_matches_reference_generator(self):
        for x, spec in enumerate(_REF_COLUMNS):
            _name, h0, cpeak = spec[:3]
            half = spec[3] if len(spec) > 3 else None
            for y in range(_REF_ROWS):
                with self.subTest(column=spec[0], y=y):
                    self.assertEqual(P.color_at(x, y, self.pal)[:3],
                                     _ref_cell(h0, cpeak, y, half))

    def test_grey_ramp_spans_two_columns(self):
        (c0, p0), (c1, p1) = P.grid_columns(self.pal)[:2]
        self.assertIs(c0, c1)
        self.assertEqual((p0, p1), (0, 1))
        # One continuous ramp: lightness strictly decreasing over 10 cells.
        cells = [P.color_at(x, y, self.pal) for x in (0, 1) for y in range(5)]
        lum = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b, _a in cells]
        self.assertEqual(lum, sorted(lum, reverse=True))
        self.assertEqual(len(set(lum)), 10)

    def test_chroma_inheritance(self):
        groups = self.pal["groups"]
        moos = groups[1]["columns"][5]
        self.assertEqual(P.column_chroma(moos, groups[1]), 0.05)
        rost = groups[1]["columns"][0]
        self.assertEqual(P.column_chroma(rost, groups[1]), 0.06)
        # Changing the group's chroma moves inheriting columns only.
        groups[1]["chroma"] = 0.1
        self.assertNotEqual(P.color_at(9, 2, self.pal)[:3], _ref_cell(135, 0.05, 2))
        self.assertEqual(P.color_at(4, 2, self.pal)[:3], _ref_cell(35, 0.06, 2))

    def test_group_lightness_range(self):
        groups = self.pal["groups"]
        self.assertEqual(P.lightness_range(groups[0], self.pal), (0.93, 0.25))
        groups[0]["l_bottom"] = 0.05                       # Neutral darker
        self.assertEqual(P.lightness_range(groups[0], self.pal), (0.93, 0.05))
        # Only that group changes; the top end still comes from the palette.
        self.assertEqual(P.color_at(0, 0, self.pal)[:3], _ref_cell(0, 0.0, 0, 0))
        self.assertNotEqual(P.color_at(1, 4, self.pal)[:3], _ref_cell(0, 0.0, 4, 1))
        self.assertEqual(P.color_at(4, 4, self.pal)[:3], _ref_cell(35, 0.06, 4))
        L, _a, _b = P.srgb_to_oklab(*P.color_at(1, 4, self.pal)[:3])
        self.assertAlmostEqual(L, 0.05, places=3)
        groups[0]["l_top"] = 1.0
        L, _a, _b = P.srgb_to_oklab(*P.color_at(0, 0, self.pal)[:3])
        self.assertAlmostEqual(L, 1.0, places=2)  # warmth tint clipped at white

    def test_reorder_moves_group_as_block(self):
        groups = self.pal["groups"]
        before = [P.color_at(x, 3, self.pal) for x in range(12, 22)]
        groups.insert(0, groups.pop())  # Akzent first
        self.assertEqual([P.color_at(x, 3, self.pal) for x in range(10)], before)

    def test_bounds(self):
        with self.assertRaises(ValueError):
            P.color_at(22, 0, self.pal)
        with self.assertRaises(ValueError):
            P.color_at(0, 5, self.pal)

    def test_single_row(self):
        self.pal["rows"] = 1
        P.validate_palette(self.pal)
        pixels, cols, rows = P.build_pixels(self.pal)
        self.assertEqual((cols, rows), (22, 1))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in pixels))


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.pal = _stylized_palette()

    def test_duplicate_id(self):
        self.pal["groups"][2]["columns"][0]["id"] = "rost"
        with self.assertRaises(ValueError):
            P.validate_palette(self.pal)

    def test_missing_id(self):
        self.pal["groups"][0]["columns"][1]["id"] = ""
        with self.assertRaises(ValueError):
            P.validate_palette(self.pal)

    def test_span_out_of_range(self):
        self.pal["groups"][0]["columns"][0]["span"] = 3
        with self.assertRaises(ValueError):
            P.validate_palette(self.pal)

    def test_no_columns(self):
        self.pal["groups"] = [{"name": "Leer", "chroma": 0.1, "columns": []}]
        with self.assertRaises(ValueError):
            P.validate_palette(self.pal)


if __name__ == "__main__":
    unittest.main()
