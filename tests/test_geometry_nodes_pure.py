# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import sys
from pathlib import Path

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from ui import geometry_nodes


class TestGeometryNodesPure(unittest.TestCase):
    def test_constants(self):
        self.assertTrue(geometry_nodes.NODE_GROUP_NAME.endswith("set_material"))
        self.assertEqual(geometry_nodes.NODE_GROUP_LABEL, "LPC Set Material")

    def test_is_lpc_managed(self):
        self.assertFalse(geometry_nodes.is_lpc_managed(None))
        dummy = {geometry_nodes._MANAGED_KEY: 1}
        self.assertTrue(geometry_nodes.is_lpc_managed(dummy))
        dummy_unmanaged = {}
        self.assertFalse(geometry_nodes.is_lpc_managed(dummy_unmanaged))


if __name__ == "__main__":
    unittest.main()

