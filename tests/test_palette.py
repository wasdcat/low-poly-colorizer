# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Palette functions with flat LPC 1.x parameters (converted on the fly)."""

import unittest
import sys
from pathlib import Path

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from model import palette


def _luminance(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


class TestPalette(unittest.TestCase):
    def setUp(self):
        self.params_default = {
            "cols": 16,
            "rows": 9,
            "add_greyscale": True,
            "saturation": 1.0,
            "brightness": 1.0,
            "tint": 0.8,
            "shade": 0.8,
        }
        self.params_no_grey = {
            "cols": 8,
            "rows": 5,
            "add_greyscale": False,
            "saturation": 1.0,
            "brightness": 1.0,
            "tint": 0.5,
            "shade": 0.5,
        }

    def test_cell_count(self):
        self.assertEqual(palette.cell_count(self.params_default), (17, 9))
        self.assertEqual(palette.cell_count(self.params_no_grey), (8, 5))

    def test_greyscale_column_is_neutral_and_descending(self):
        cols, rows = palette.cell_count(self.params_default)
        lum = []
        for y in range(rows):
            r, g, b, a = palette.color_at(0, y, self.params_default)
            self.assertAlmostEqual(r, g, places=4)
            self.assertAlmostEqual(g, b, places=4)
            self.assertEqual(a, 1.0)
            lum.append(_luminance((r, g, b)))
        self.assertEqual(lum, sorted(lum, reverse=True))
        # White to black, as in 1.x (the Greyscale group's own L range).
        for v in palette.color_at(0, 0, self.params_default)[:3]:
            self.assertAlmostEqual(v, 1.0, places=4)
        for v in palette.color_at(0, rows - 1, self.params_default)[:3]:
            self.assertAlmostEqual(v, 0.0, places=4)
        # Independent of brightness.
        dark = dict(self.params_default, brightness=0.5)
        self.assertEqual(palette.color_at(0, 0, dark), palette.color_at(0, 0, self.params_default))

    def test_color_at_bounds_and_validity(self):
        params = dict(self.params_default, hue_shift=0.5, warmth=0.2)
        cols, rows = palette.cell_count(params)
        for y in range(rows):
            for x in range(cols):
                r, g, b, a = palette.color_at(x, y, params)
                self.assertTrue(0.0 <= r <= 1.0)
                self.assertTrue(0.0 <= g <= 1.0)
                self.assertTrue(0.0 <= b <= 1.0)
                self.assertEqual(a, 1.0)

        with self.assertRaises(ValueError):
            palette.color_at(-1, 0, params)
        with self.assertRaises(ValueError):
            palette.color_at(cols, 0, params)
        with self.assertRaises(ValueError):
            palette.color_at(0, -1, params)
        with self.assertRaises(ValueError):
            palette.color_at(0, rows, params)

    def test_build_pixels(self):
        pixels, cols, rows = palette.build_pixels(self.params_default)
        self.assertEqual((cols, rows), (17, 9))
        self.assertEqual(len(pixels), cols * rows * 4)
        for x, y in ((0, 0), (5, 3), (16, 8)):
            i = (y * cols + x) * 4
            self.assertEqual(tuple(pixels[i:i + 4]),
                             palette.color_at(x, y, self.params_default))

    def test_nearest_cell(self):
        for cell in ((0, 0), (0, 8), (5, 3), (16, 8)):
            color = palette.color_at(*cell, self.params_default)
            self.assertEqual(palette.nearest_cell(color, self.params_default), cell)
        self.assertEqual(palette.nearest_cell((1.0, 1.0, 1.0), self.params_default), (0, 0))
        self.assertEqual(palette.nearest_cell((0.0, 0.0, 0.0), self.params_default), (0, 8))

    def test_warmth_biases_temperature(self):
        neutral = palette.color_at(0, 4, self.params_default)
        warm = palette.color_at(0, 4, dict(self.params_default, warmth=0.5))
        cool = palette.color_at(0, 4, dict(self.params_default, warmth=-0.5))
        self.assertGreater(warm[0], neutral[0])  # warmer -> redder
        self.assertLess(warm[2], neutral[2])     # warmer -> less blue
        self.assertLess(cool[0], neutral[0])
        self.assertGreater(cool[2], neutral[2])

    def test_saturation_and_brightness(self):
        grey = palette.color_at(3, 4, dict(self.params_default, saturation=0.0))
        self.assertAlmostEqual(grey[0], grey[1], places=4)
        self.assertAlmostEqual(grey[1], grey[2], places=4)
        bright = palette.color_at(3, 4, self.params_default)
        dark = palette.color_at(3, 4, dict(self.params_default, brightness=0.5))
        self.assertLess(_luminance(dark), _luminance(bright))

    def test_color_mode_is_ignored(self):
        # LPC 2.0 has no HSV mode; old scenes keep their grid, not their colors.
        hsv = dict(self.params_default, color_mode="HSV")
        oklch = dict(self.params_default, color_mode="OKLCH")
        self.assertEqual(palette.build_pixels(hsv), palette.build_pixels(oklch))


if __name__ == "__main__":
    unittest.main()
