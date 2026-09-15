# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

# Add addon directory to sys.path for standalone testing
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))

from export import exporter


class TestExporter(unittest.TestCase):
    def test_pascal(self):
        self.assertEqual(exporter._pascal("lpc_"), "Lpc")
        self.assertEqual(exporter._pascal("my_custom_game_"), "MyCustomGame")
        self.assertEqual(exporter._pascal("prefix"), "Prefix")
        self.assertEqual(exporter._pascal(""), "")

    def test_preset_identifiers_sanitization(self):
        # Mock scene with various preset names
        class DummyPreset:
            def __init__(self, name):
                self.name = name

        scene = SimpleNamespace(
            lpc_presets=[
                DummyPreset("Solid"),
                DummyPreset("Signal Red"),
                DummyPreset("Grün & Blau"),  # Non-ascii and special chars
                DummyPreset("123 Numeric"),   # Leading digit
                DummyPreset("!!! Special"),   # Special only
                DummyPreset("Duplicate"),     # Duplicate collision
                DummyPreset("Duplicate"),
            ]
        )

        idents = exporter._preset_identifiers(scene)
        self.assertEqual(idents[0], "SOLID")
        self.assertEqual(idents[1], "SIGNAL_RED")
        self.assertEqual(idents[2], "GRUN_BLAU")
        self.assertEqual(idents[3], "PRESET_123_NUMERIC")
        self.assertEqual(idents[4], "SPECIAL")
        self.assertEqual(idents[5], "DUPLICATE")
        self.assertEqual(idents[6], "DUPLICATE_2")

    def test_preset_identifiers_empty(self):
        scene = SimpleNamespace(lpc_presets=[])
        idents = exporter._preset_identifiers(scene)
        self.assertEqual(idents, ["PRESET_0"])

    def test_render_template(self):
        template = "uniform vec2 size = vec2({{width}}, {{height}});\n// {{unknown_tag}}"
        mapping = {"width": "16.0", "height": "9.0"}
        rendered = exporter._render(template, mapping)
        self.assertEqual(
            rendered,
            "uniform vec2 size = vec2(16.0, 9.0);\n// {{unknown_tag}}",
        )

    def test_strip_tpl(self):
        self.assertEqual(exporter._strip_tpl("shader.gdshader.tpl"), "shader.gdshader")
        self.assertEqual(exporter._strip_tpl("README.md"), "README.md")


if __name__ == "__main__":
    unittest.main()

