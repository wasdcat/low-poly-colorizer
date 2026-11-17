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

    def test_oklch_mode_validity_and_bounds(self):
        params_oklch = dict(self.params_default)
        params_oklch["color_mode"] = "OKLCH"
        params_oklch["hue_shift"] = 0.5
        params_oklch["warmth"] = 0.2

        cols, rows = palette.cell_count(params_oklch)
        for y in range(rows):
            for x in range(cols):
                r, g, b, a = palette.color_at(x, y, params_oklch)
                self.assertTrue(0.0 <= r <= 1.0, f"r={r} out of bounds at ({x}, {y})")
                self.assertTrue(0.0 <= g <= 1.0, f"g={g} out of bounds at ({x}, {y})")
                self.assertTrue(0.0 <= b <= 1.0, f"b={b} out of bounds at ({x}, {y})")
                self.assertEqual(a, 1.0)

        # Greyscale column monotonic descent
        for y in range(rows - 1):
            c_curr = palette.color_at(0, y, params_oklch)
            c_next = palette.color_at(0, y + 1, params_oklch)
            lum_curr = 0.2126 * c_curr[0] + 0.7152 * c_curr[1] + 0.0722 * c_curr[2]
            lum_next = 0.2126 * c_next[0] + 0.7152 * c_next[1] + 0.0722 * c_next[2]
            self.assertGreater(lum_curr, lum_next, f"Luminance did not decrease at row {y}")

    def test_hsv_hue_shift_and_warmth_effects(self):
        # Warmth > 0 should bias colors warmer (more red / less blue)
        params_neutral = dict(self.params_default)
        params_warm = dict(self.params_default, warmth=0.5)
        params_cool = dict(self.params_default, warmth=-0.5)

        c_neutral = palette.color_at(0, 4, params_neutral)
        c_warm = palette.color_at(0, 4, params_warm)
        c_cool = palette.color_at(0, 4, params_cool)

        self.assertGreater(c_warm[0], c_neutral[0])  # warmer -> redder
        self.assertLess(c_warm[2], c_neutral[2])     # warmer -> less blue
        self.assertLess(c_cool[0], c_neutral[0])     # cooler -> less red
        self.assertGreater(c_cool[2], c_neutral[2])  # cooler -> more blue

    def test_backward_compatibility_defaults(self):
        # Calling with explicit default artwork params must match calling without them
        explicit_defaults = dict(
            self.params_default,
            color_mode="HSV",
            hue_shift=0.0,
            warmth=0.0,
        )
        cols, rows = palette.cell_count(self.params_default)
        for y in range(rows):
            for x in range(cols):
                c_implicit = palette.color_at(x, y, self.params_default)
                c_explicit = palette.color_at(x, y, explicit_defaults)
                self.assertEqual(c_implicit, c_explicit)


if __name__ == "__main__":
    unittest.main()

