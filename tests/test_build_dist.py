"""CHANGELOG release step of scripts/build_dist.py (--version)."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_dist", ROOT / "scripts" / "build_dist.py")
build_dist = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_dist)

CHANGELOG = """# Changelog

Intro.

## [Unreleased]

### Added
- New thing.

## [2.0.1] - 2026-11-17

### Changed
- Old thing.
"""


class TestReleaseChangelog(unittest.TestCase):
    def test_unreleased_becomes_the_release(self):
        text, status = build_dist.release_changelog(CHANGELOG, "2.1.0", "2026-11-18")
        self.assertEqual(status, "released")
        self.assertIn("## [Unreleased]\n\n## [2.1.0] - 2026-11-18\n\n### Added\n- New thing.", text)
        self.assertEqual(text.count("## [Unreleased]"), 1)
        self.assertIn("## [2.0.1] - 2026-11-17", text)

    def test_repeated_bump_is_a_no_op(self):
        once, _ = build_dist.release_changelog(CHANGELOG, "2.1.0", "2026-11-18")
        twice, status = build_dist.release_changelog(once, "2.1.0", "2026-11-19")
        self.assertEqual(status, "exists")
        self.assertEqual(twice, once)

    def test_empty_unreleased_section(self):
        released, _ = build_dist.release_changelog(CHANGELOG, "2.1.0", "2026-11-18")
        result, status = build_dist.release_changelog(released, "2.2.0", "2026-11-19")
        self.assertEqual(status, "empty")
        self.assertEqual(result, released)

    def test_without_unreleased_section(self):
        text = CHANGELOG.replace("## [Unreleased]\n\n### Added\n- New thing.\n\n", "")
        result, status = build_dist.release_changelog(text, "2.1.0", "2026-11-18")
        self.assertEqual(status, "missing")
        self.assertEqual(result, text)


if __name__ == "__main__":
    unittest.main()
