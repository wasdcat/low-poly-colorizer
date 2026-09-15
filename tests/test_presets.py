# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import unittest
import sys
from pathlib import Path

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from model import presets as model_presets
from ops import presets as ops_presets


class TestPresets(unittest.TestCase):
    def test_reference_counts(self):
        keys = [10, 20, 30]
        refs = [10, 10, 30, 10, 99, None]  # 99 and None are unknown
        counts = model_presets.reference_counts(keys, refs)
        self.assertEqual(counts, [3, 0, 1])

    def test_make_preset(self):
        p = ops_presets.make_preset("Test", roughness=0.5, metallic=1.0)
        self.assertEqual(p["name"], "Test")
        self.assertEqual(p["roughness"], 0.5)
        self.assertEqual(p["metallic"], 1.0)
        self.assertEqual(p["emission"], 0.0)
        self.assertEqual(p["clearcoat"], 0.0)

        with self.assertRaises(ValueError):
            ops_presets.make_preset("Bad", unknown_key=1.0)

    def test_default_presets(self):
        defs = ops_presets.default_presets()
        self.assertTrue(len(defs) >= 4)
        names = [d["name"] for d in defs]
        self.assertIn("Solid", names)
        self.assertIn("Metallic", names)
        self.assertIn("Clearcoat", names)
        self.assertIn("Emission", names)

    def test_json_roundtrip(self):
        orig = [
            ops_presets.make_preset("Solid", roughness=0.8, metallic=0.0),
            ops_presets.make_preset("Gold", roughness=0.25, metallic=1.0, emission=0.1),
        ]
        json_text = ops_presets.presets_to_json(orig)
        parsed = ops_presets.presets_from_json(json_text)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["name"], "Solid")
        self.assertEqual(parsed[0]["roughness"], 0.8)
        self.assertEqual(parsed[1]["name"], "Gold")
        self.assertEqual(parsed[1]["metallic"], 1.0)

    def test_presets_validation(self):
        # Invalid JSON
        with self.assertRaises(ValueError):
            ops_presets.presets_from_json("invalid json")

        # Wrong version
        bad_ver = json.dumps({"version": 99, "presets": []})
        with self.assertRaises(ValueError):
            ops_presets.presets_from_json(bad_ver)

        # Missing presets field
        with self.assertRaises(ValueError):
            ops_presets.presets_from_json(json.dumps({"version": 1}))

        # Clamping out-of-range values
        raw = [{"name": "Clamped", "roughness": 1.5, "metallic": -0.5}]
        validated = ops_presets.presets_from_list(raw)
        self.assertEqual(validated[0]["roughness"], 1.0)
        self.assertEqual(validated[0]["metallic"], 0.0)

        # Strict mode error on missing keys
        with self.assertRaises(ValueError):
            ops_presets.presets_from_list(raw, strict=True)


if __name__ == "__main__":
    unittest.main()

