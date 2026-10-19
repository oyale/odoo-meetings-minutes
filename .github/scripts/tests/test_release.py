from __future__ import annotations

import datetime as dt
import importlib.util
import unittest
from pathlib import Path

release_path = Path(__file__).resolve().parents[1] / "release.py"
release_spec = importlib.util.spec_from_file_location("release", release_path)
assert release_spec and release_spec.loader
release = importlib.util.module_from_spec(release_spec)
release_spec.loader.exec_module(release)


class ReleaseVersionTests(unittest.TestCase):
    def test_release_tag_accepts_optional_v_prefix(self) -> None:
        self.assertEqual(release.normalize_tag("v18.0.20261019.1"), "18.0.20261019.1")

    def test_next_release_version_starts_daily_sequence_at_zero(self) -> None:
        version = release.next_release_version("18.0.20261018.2", dt.date(2026, 10, 19))
        self.assertEqual(version, "18.0.20261019.0")

    def test_next_release_version_increments_same_day_sequence(self) -> None:
        version = release.next_release_version("18.0.20261019.1", dt.date(2026, 10, 19))
        self.assertEqual(version, "18.0.20261019.2")

    def test_next_addon_version_increments_patch_only_if_not_bumped(self) -> None:
        self.assertEqual(
            release.next_addon_version("18.0.6.2.1", "18.0.6.2.1"),
            "18.0.6.2.2",
        )
        self.assertEqual(
            release.next_addon_version("18.0.6.2.2", "18.0.6.2.1"),
            "18.0.6.2.2",
        )

    def test_addon_version_cannot_go_backwards(self) -> None:
        with self.assertRaises(SystemExit):
            release.next_addon_version("18.0.6.2.0", "18.0.6.2.1")

    def test_release_notes_select_one_section(self) -> None:
        changelog = """# Changelog

## Odoo Meetings Minutes 18.0.20261019.1 (2026-10-19)

### Features

- New feature.

## Odoo Meetings Minutes 18.0.20261018.2 (2026-10-18)

- Previous release.
"""
        notes = release.read_release_notes(changelog, "18.0.20261019.1")
        self.assertIn("- New feature.", notes)
        self.assertNotIn("Previous release", notes)


if __name__ == "__main__":
    unittest.main()
