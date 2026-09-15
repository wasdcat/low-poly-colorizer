# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import sys
from pathlib import Path

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from model import palette


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
        cols, rows = palette.cell_count(self.params_default)
        self.assertEqual(cols, 17)
        self.assertEqual(rows, 9)

        cols, rows = palette.cell_count(self.params_no_grey)
        self.assertEqual(cols, 8)
        self.assertEqual(rows, 5)

    def test_color_at_greyscale_column(self):
        # Column 0 is greyscale when add_greyscale is True
        # Top (y=0) should be white (1.0, 1.0, 1.0, 1.0)
        c_top = palette.color_at(0, 0, self.params_default)
        self.assertAlmostEqual(c_top[0], 1.0)
        self.assertAlmostEqual(c_top[1], 1.0)
        self.assertAlmostEqual(c_top[2], 1.0)
        self.assertAlmostEqual(c_top[3], 1.0)

        # Bottom (y=rows-1) should be black (0.0, 0.0, 0.0, 1.0)
        c_bot = palette.color_at(0, 8, self.params_default)
        self.assertAlmostEqual(c_bot[0], 0.0)
        self.assertAlmostEqual(c_bot[1], 0.0)
        self.assertAlmostEqual(c_bot[2], 0.0)
        self.assertAlmostEqual(c_bot[3], 1.0)

        # Middle (y=4) should be mid-grey (0.5, 0.5, 0.5, 1.0)
        c_mid = palette.color_at(0, 4, self.params_default)
        self.assertAlmostEqual(c_mid[0], 0.5)
        self.assertAlmostEqual(c_mid[1], 0.5)
        self.assertAlmostEqual(c_mid[2], 0.5)

    def test_color_at_bounds_and_validity(self):
        cols, rows = palette.cell_count(self.params_default)
        for y in range(rows):
            for x in range(cols):
                r, g, b, a = palette.color_at(x, y, self.params_default)
                self.assertTrue(0.0 <= r <= 1.0)
                self.assertTrue(0.0 <= g <= 1.0)
                self.assertTrue(0.0 <= b <= 1.0)
                self.assertEqual(a, 1.0)

        # Out of range should raise ValueError
        with self.assertRaises(ValueError):
            palette.color_at(-1, 0, self.params_default)
        with self.assertRaises(ValueError):
            palette.color_at(cols, 0, self.params_default)
        with self.assertRaises(ValueError):
            palette.color_at(0, -1, self.params_default)
        with self.assertRaises(ValueError):
            palette.color_at(0, rows, self.params_default)

    def test_build_pixels(self):
        pixels, cols, rows = palette.build_pixels(self.params_default)
        self.assertEqual(cols, 17)
        self.assertEqual(rows, 9)
        self.assertEqual(len(pixels), cols * rows * 4)

        # Verify pixel at (x=0, y=0) matches color_at(0, 0)
        c_00 = palette.color_at(0, 0, self.params_default)
        self.assertAlmostEqual(pixels[0], c_00[0])
        self.assertAlmostEqual(pixels[1], c_00[1])
        self.assertAlmostEqual(pixels[2], c_00[2])
        self.assertAlmostEqual(pixels[3], c_00[3])

    def test_nearest_cell(self):
        # White should match (0, 0) in default palette
        best = palette.nearest_cell((1.0, 1.0, 1.0), self.params_default)
        self.assertEqual(best, (0, 0))

        # Black should match (0, 8) in default palette
        best = palette.nearest_cell((0.0, 0.0, 0.0), self.params_default)
        self.assertEqual(best, (0, 8))


if __name__ == "__main__":
    unittest.main()

