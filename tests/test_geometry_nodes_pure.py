# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import sys
from pathlib import Path

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from ui import geometry_nodes
from model import palette as model_palette


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

    def test_column_menu_labels_match_godot_column_names(self):
        pal = model_palette.palette_from_json({"groups": [
            {"name": "Nature", "columns": [
                {"id": "a", "name": "Moss"},
                {"id": "b", "name": "Grey", "span": 2}]}]})
        self.assertEqual(geometry_nodes.column_menu_labels(pal),
                         model_palette.grid_column_labels(pal))
        self.assertEqual(geometry_nodes.column_menu_labels(pal),
                         ["Nature · Moss", "Nature · Grey 1/2", "Nature · Grey 2/2"])

    def test_column_menu_labels_are_unique(self):
        pal = model_palette.palette_from_json({"groups": [
            {"name": "G", "columns": [
                {"id": "a", "name": "Red"},
                {"id": "b", "name": "Red"},
                {"id": "c", "name": "Red"}]}]})
        self.assertEqual(geometry_nodes.column_menu_labels(pal),
                         ["G · Red", "G · Red (2)", "G · Red (3)"])


if __name__ == "__main__":
    unittest.main()

