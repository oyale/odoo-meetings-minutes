"""Focused contract tests for the public browser catalog helper."""

import tempfile
import unittest
from pathlib import Path

from catalog_lookup import CatalogLookup

HEADER = (
    'msgid ""\nmsgstr ""\n'
    '"Project-Id-Version: test\\n"\n'
    '"Content-Type: text/plain; charset=UTF-8\\n"\n'
    '"Content-Transfer-Encoding: 8bit\\n"\n'
    '"Language: es\\n"\n'
    '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
)


class PublicCatalogLookupChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="public-catalog-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.addon = self.root / "sample_addon"
        (self.addon / "i18n").mkdir(parents=True)

    def catalog(self, code, body):
        path = self.addon / "i18n" / f"{code}.po"
        path.write_text(HEADER + body, encoding="utf-8")
        return path

    def test_source_language_and_new_locale(self):
        self.assertEqual(CatalogLookup(self.root, None).translate("sample_addon", "Save"), "Save")
        self.catalog("fr", 'msgid "Save"\nmsgstr "Enregistrer"\n')
        self.assertEqual(CatalogLookup(self.root, "fr_FR").translate("sample_addon", "Save"), "Enregistrer")

    def test_explicit_locale_has_no_missing_or_empty_fallback(self):
        self.catalog("es", 'msgid "Save"\nmsgstr ""\n')
        lookup = CatalogLookup(self.root, "es_ES")
        with self.assertRaisesRegex(ValueError, "empty translation"):
            lookup.translate("sample_addon", "Save")
        with self.assertRaisesRegex(ValueError, "found 0"):
            lookup.translate("sample_addon", "Missing")

    def test_context_and_plural_are_explicit(self):
        self.catalog(
            "es",
            'msgctxt "button"\nmsgid "Open"\nmsgstr "Abrir"\n\n'
            'msgctxt "status"\nmsgid "Open"\nmsgstr "Abierto"\n\n'
            'msgid "One item"\nmsgid_plural "Many items"\n'
            'msgstr[0] "Un elemento"\nmsgstr[1] "Varios elementos"\n',
        )
        lookup = CatalogLookup(self.root, "es_ES")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            lookup.translate("sample_addon", "Open")
        self.assertEqual(lookup.translate("sample_addon", "Open", context="button"), "Abrir")
        with self.assertRaisesRegex(ValueError, "pass plural_index"):
            lookup.translate("sample_addon", "One item")
        self.assertEqual(
            lookup.translate("sample_addon", "One item", plural_index=1), "Varios elementos"
        )

    def test_malformed_catalog_reports_path(self):
        path = self.catalog("es", 'msgid "Save"\nmsgstr "Guardar"\ninvalid\n')
        with self.assertRaisesRegex(ValueError, str(path)):
            CatalogLookup(self.root, "es_ES").translate("sample_addon", "Save")


if __name__ == "__main__":
    unittest.main()
