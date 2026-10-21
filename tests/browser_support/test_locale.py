"""Pure unit checks for locale normalization shared by browser suites."""

import unittest

from odoo_browser import normalize_locale


class NormalizeLocaleChecks(unittest.TestCase):
    def test_normalizes_odoo_and_bcp47_separators(self):
        self.assertEqual(normalize_locale("en_US"), "en_US")
        self.assertEqual(normalize_locale("es-ES"), "es_ES")
        self.assertEqual(normalize_locale("ES-es"), "es_ES")
        self.assertEqual(normalize_locale("es"), "es")

    def test_empty_locale_is_unknown(self):
        self.assertIsNone(normalize_locale(None))
        self.assertIsNone(normalize_locale(""))


if __name__ == "__main__":
    unittest.main()
