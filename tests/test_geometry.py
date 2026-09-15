# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import sys
from pathlib import Path

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from picker.geometry import PickerGeometry


class TestGeometry(unittest.TestCase):
    def test_cell_to_screen_and_back(self):
        geo = PickerGeometry(
            origin_x=100.0,
            origin_y=200.0,
            pan_x=10.0,
            pan_y=-20.0,
            zoom=1.5,
            swatch_size=20.0,
            ui_scale=1.0,
        )
        # cell_size = 20.0 * 1.5 * 1.0 = 30.0
        self.assertEqual(geo.cell_size, 30.0)

        # cell (2, 3) -> screen coords
        # screen_x = 100 + 10 + 2 * 30 = 170.0
        # screen_y = 200 - 20 + 3 * 30 = 270.0
        sx, sy = geo.cell_to_screen(2, 3)
        self.assertEqual(sx, 170.0)
        self.assertEqual(sy, 270.0)

        # Point inside cell (2, 3), e.g. (175, 275)
        cx, cy = geo.screen_to_cell(175.0, 275.0)
        self.assertEqual(cx, 2)
        self.assertEqual(cy, 3)

    def test_hit_test(self):
        geo = PickerGeometry(origin_x=0.0, origin_y=0.0, swatch_size=10.0)
        cols, rows = 5, 5

        # Inside
        self.assertEqual(geo.hit_test(25.0, 25.0, cols, rows), (2, 2))
        self.assertEqual(geo.hit_test(0.0, 0.0, cols, rows), (0, 0))
        self.assertEqual(geo.hit_test(49.9, 49.9, cols, rows), (4, 4))

        # Outside
        self.assertIsNone(geo.hit_test(-0.1, 10.0, cols, rows))
        self.assertIsNone(geo.hit_test(10.0, -0.1, cols, rows))
        self.assertIsNone(geo.hit_test(50.0, 10.0, cols, rows))
        self.assertIsNone(geo.hit_test(10.0, 50.0, cols, rows))

    def test_cell_rect(self):
        geo = PickerGeometry(origin_x=0.0, origin_y=0.0, swatch_size=10.0)
        x0, y0, x1, y1 = geo.cell_rect(1, 1)
        self.assertEqual((x0, y0, x1, y1), (10.0, 10.0, 20.0, 20.0))


if __name__ == "__main__":
    unittest.main()

