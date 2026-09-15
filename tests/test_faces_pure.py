# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import sys
from pathlib import Path

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from model import faces


class TestFacesPure(unittest.TestCase):
    def test_palette_uv_encoding_roundtrip(self):
        cols, rows = 16, 9
        for y in range(rows):
            for x in range(cols):
                # Encode (x, y) into pre-compensated UV0
                uv0 = faces.encode_palette_uv(x, y, cols, rows)
                # Decode back
                dx, dy = faces.decode_palette_uv(uv0, cols, rows)
                self.assertEqual(dx, x, f"Mismatch on x for ({x}, {y})")
                self.assertEqual(dy, y, f"Mismatch on y for ({x}, {y})")

    def test_gltf_v_flip_compensation(self):
        # palette_uv(0, 0, 10, 10) = (0.05, 0.05)
        # encoded should flip V: (0.05, 1.0 - 0.05) = (0.05, 0.95)
        raw_uv = faces.palette_uv(0, 0, 10, 10)
        self.assertAlmostEqual(raw_uv[0], 0.05)
        self.assertAlmostEqual(raw_uv[1], 0.05)

        enc_uv = faces.encode_palette_uv(0, 0, 10, 10)
        self.assertAlmostEqual(enc_uv[0], 0.05)
        self.assertAlmostEqual(enc_uv[1], 0.95)


if __name__ == "__main__":
    unittest.main()

