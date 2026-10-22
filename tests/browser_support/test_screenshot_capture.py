"""Contract tests for shared browser screenshot capture policy."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TESTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS_ROOT))

from browser_support.screenshot_capture import capture_checkpoint, capture_failure


class FakePage:
    def __init__(self, width=1280, height=720, fail_screenshot=False):
        self.size = {"width": width, "height": height}
        self.viewport_sizes = []
        self.screenshots = []
        self.fail_screenshot = fail_screenshot

    def evaluate(self, _script):
        return self.size.copy()

    def set_viewport_size(self, size):
        self.size = size.copy()
        self.viewport_sizes.append(size.copy())

    def screenshot(self, path, full_page):
        self.screenshots.append((path, full_page, self.size.copy()))
        if self.fail_screenshot:
            raise RuntimeError("capture failed")
        Path(path).write_bytes(b"png")


class ScreenshotCaptureChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="screenshot-capture-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.environment = patch.dict(
            os.environ,
            {
                "MM_PLAYWRIGHT_SCREENSHOT_DIR": str(self.root),
                "MM_PLAYWRIGHT_SCREENSHOTS": "checkpoints",
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for name in (
            "MM_PLAYWRIGHT_SCREENSHOT_NAMES",
            "MM_PLAYWRIGHT_SCREENSHOT_VIEWPORTS",
        ):
            os.environ.pop(name, None)

    def test_disabled_capture_does_not_touch_page_or_filesystem(self):
        os.environ["MM_PLAYWRIGHT_SCREENSHOTS"] = "off"
        page = FakePage()

        self.assertEqual(capture_checkpoint(page, "meeting", "test id", "en_US"), [])
        self.assertIsNone(capture_failure(page, "test id"))
        self.assertEqual(page.screenshots, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unselected_checkpoint_is_skipped(self):
        os.environ["MM_PLAYWRIGHT_SCREENSHOT_NAMES"] = "meeting-form, live-agenda"
        page = FakePage()

        self.assertEqual(capture_checkpoint(page, "series-form", "test", "en_US"), [])
        self.assertEqual(page.screenshots, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_configured_viewports_are_captured_and_original_size_is_restored(self):
        os.environ["MM_PLAYWRIGHT_SCREENSHOT_VIEWPORTS"] = (
            '[{"name":"desktop","width":1440,"height":900},{"name":"phone","width":390,"height":844}]'
        )
        page = FakePage()

        paths = capture_checkpoint(page, "agenda", "test id", "en_US")

        self.assertEqual(
            [path.name for path in paths],
            ["agenda-en_US-desktop-1440x900.png", "agenda-en_US-phone-390x844.png"],
        )
        self.assertEqual(
            [shot[2] for shot in page.screenshots],
            [
                {"width": 1440, "height": 900},
                {"width": 390, "height": 844},
            ],
        )
        self.assertEqual(page.size, {"width": 1280, "height": 720})
        self.assertEqual((paths[0].stat().st_mode & 0o777), 0o600)
        self.assertEqual((paths[0].parent.stat().st_mode & 0o777), 0o700)

    def test_original_viewport_is_restored_when_capture_fails(self):
        page = FakePage(fail_screenshot=True)

        with self.assertRaisesRegex(RuntimeError, "capture failed"):
            capture_checkpoint(page, "agenda", "test", "es_ES", viewport={"width": 900, "height": 700})

        self.assertEqual(page.size, {"width": 1280, "height": 720})

    def test_invalid_viewport_configuration_is_rejected(self):
        invalid_values = [
            "not-json",
            "{}",
            '[{"name":"desktop","width":0,"height":900}]',
            '[{"name":"desktop","width":1440,"height":true}]',
            '[{"width":1440,"height":900}]',
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                os.environ["MM_PLAYWRIGHT_SCREENSHOT_VIEWPORTS"] = value
                with self.assertRaises(ValueError):
                    capture_checkpoint(FakePage(), "agenda", "test", "en_US")

    def test_failure_capture_writes_private_screenshot(self):
        page = FakePage()

        path = capture_failure(page, "unsafe test id")

        self.assertEqual(path.name, "failure-current-1280x720.png")
        self.assertEqual(path.parent.name, "unsafe-test-id")
        self.assertTrue(path.is_file())
        self.assertEqual((path.stat().st_mode & 0o777), 0o600)
        self.assertEqual((path.parent.stat().st_mode & 0o777), 0o700)
        self.assertEqual(page.screenshots[0][1], True)


if __name__ == "__main__":
    unittest.main()
