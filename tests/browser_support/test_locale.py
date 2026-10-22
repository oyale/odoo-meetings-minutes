"""Pure unit checks for locale normalization shared by browser suites."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

TESTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS_ROOT))

from browser_support.odoo_browser import OdooBrowserSession, normalize_locale


class NormalizeLocaleChecks(unittest.TestCase):
    def test_normalizes_odoo_and_bcp47_separators(self):
        self.assertEqual(normalize_locale("en_US"), "en_US")
        self.assertEqual(normalize_locale("es-ES"), "es_ES")
        self.assertEqual(normalize_locale("ES-es"), "es_ES")
        self.assertEqual(normalize_locale("es"), "es")

    def test_empty_locale_is_unknown(self):
        self.assertIsNone(normalize_locale(None))
        self.assertIsNone(normalize_locale(""))


class VerifyLocaleChecks(unittest.TestCase):
    def test_missing_rendered_html_language_fails(self):
        session = object.__new__(OdooBrowserSession)
        session.session_info = Mock(
            return_value={
                "user_context": {"lang": "es_ES"},
                "bundle_params": {"lang": "es_ES"},
            }
        )
        session.page = Mock()
        session.console_errors = []
        session.page.locator.return_value.get_attribute.return_value = None
        session.page.locator.return_value.evaluate.return_value = "<html></html>"
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"MM_PLAYWRIGHT_SCREENSHOT_DIR": directory}),
            self.assertRaisesRegex(AssertionError, r"html\[lang\]=None"),
        ):
            session.verify_locale("es_ES")


if __name__ == "__main__":
    unittest.main()
