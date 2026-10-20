import unittest

from acceptance.config import AcceptanceConfig, AcceptanceConfigurationError


class AcceptanceConfigTests(unittest.TestCase):
    def test_requires_explicit_disposable_environment_consent(self):
        with self.assertRaisesRegex(AcceptanceConfigurationError, "ALLOW_DISPOSABLE"):
            AcceptanceConfig.from_environment({})

    def test_requires_explicit_url_database_credentials_and_scope(self):
        values = {
            "ODOO_ACCEPTANCE_ALLOW_DISPOSABLE": "1",
            "ODOO_BASE_URL": "http://127.0.0.1:18069",
            "ODOO_DB": "mm_dev_acceptance",
            "ODOO_LOGIN": "editor",
            "ODOO_PASSWORD": "secret",
        }
        with self.assertRaisesRegex(AcceptanceConfigurationError, "ODOO_ACCEPTANCE_SCOPE"):
            AcceptanceConfig.from_environment(values)

    def test_rejects_non_http_url_userinfo_and_query(self):
        base = {
            "ODOO_ACCEPTANCE_ALLOW_DISPOSABLE": "1",
            "ODOO_DB": "mm_dev_acceptance",
            "ODOO_LOGIN": "editor",
            "ODOO_PASSWORD": "secret",
            "ODOO_ACCEPTANCE_SCOPE": "core",
        }
        for url in ("ftp://host/db", "http://user:pass@host", "http://host/?db=other"):
            with self.subTest(url=url), self.assertRaises(AcceptanceConfigurationError):
                AcceptanceConfig.from_environment({**base, "ODOO_BASE_URL": url})

    def test_requires_safe_database_identifier_and_supported_scope(self):
        base = {
            "ODOO_ACCEPTANCE_ALLOW_DISPOSABLE": "1",
            "ODOO_BASE_URL": "http://127.0.0.1:18069",
            "ODOO_LOGIN": "editor",
            "ODOO_PASSWORD": "secret",
            "ODOO_ACCEPTANCE_SCOPE": "core",
        }
        with self.assertRaisesRegex(AcceptanceConfigurationError, "ODOO_DB"):
            AcceptanceConfig.from_environment({**base, "ODOO_DB": "prod;drop"})
        with self.assertRaisesRegex(AcceptanceConfigurationError, "SCOPE"):
            AcceptanceConfig.from_environment({**base, "ODOO_DB": "test", "ODOO_ACCEPTANCE_SCOPE": "unknown"})

    def test_accepts_explicit_disposable_runtime(self):
        config = AcceptanceConfig.from_environment(
            {
                "ODOO_ACCEPTANCE_ALLOW_DISPOSABLE": "1",
                "ODOO_BASE_URL": "http://127.0.0.1:18069",
                "ODOO_DB": "mm_dev_acceptance",
                "ODOO_LOGIN": "editor",
                "ODOO_PASSWORD": "secret",
                "ODOO_ACCEPTANCE_SCOPE": "core",
                "PLAYWRIGHT_HEADFUL": "1",
            }
        )
        self.assertEqual(config.base_url, "http://127.0.0.1:18069")
        self.assertEqual(config.database, "mm_dev_acceptance")
        self.assertEqual(config.scope, "core")
        self.assertTrue(config.headful)

    def test_accepts_configured_reviewer_and_reader_accounts(self):
        config = AcceptanceConfig.from_environment(
            {
                "ODOO_ACCEPTANCE_ALLOW_DISPOSABLE": "1",
                "ODOO_BASE_URL": "http://127.0.0.1:18069",
                "ODOO_DB": "mm_dev_acceptance",
                "ODOO_LOGIN": "editor",
                "ODOO_PASSWORD": "secret",
                "ODOO_ACCEPTANCE_SCOPE": "core",
                "ODOO_REVIEWER_LOGIN": "reviewer",
                "ODOO_REVIEWER_PASSWORD": "reviewer-secret",
                "ODOO_READER_LOGIN": "reader",
                "ODOO_READER_PASSWORD": "reader-secret",
            }
        )
        self.assertEqual(config.reviewer_login, "reviewer")
        self.assertEqual(config.reader_login, "reader")

    def test_reviewer_password_defaults_to_primary_test_password(self):
        config = AcceptanceConfig.from_environment(
            {
                "ODOO_ACCEPTANCE_ALLOW_DISPOSABLE": "1",
                "ODOO_BASE_URL": "http://127.0.0.1:18069",
                "ODOO_DB": "mm_dev_acceptance",
                "ODOO_LOGIN": "editor",
                "ODOO_PASSWORD": "secret",
                "ODOO_REVIEWER_LOGIN": "reviewer",
                "ODOO_ACCEPTANCE_SCOPE": "core",
            }
        )
        self.assertEqual(config.reviewer_password, "secret")

    def test_reviewer_and_reader_credentials_must_be_complete_pairs(self):
        base = {
            "ODOO_ACCEPTANCE_ALLOW_DISPOSABLE": "1",
            "ODOO_BASE_URL": "http://127.0.0.1:18069",
            "ODOO_DB": "mm_dev_acceptance",
            "ODOO_LOGIN": "editor",
            "ODOO_PASSWORD": "secret",
            "ODOO_ACCEPTANCE_SCOPE": "core",
        }
        for environment in (
            {**base, "ODOO_REVIEWER_PASSWORD": "secret"},
            {**base, "ODOO_READER_LOGIN": "configured-user"},
        ):
            with self.subTest(environment=environment), self.assertRaises(AcceptanceConfigurationError):
                AcceptanceConfig.from_environment(environment)

    def test_configured_roles_must_use_distinct_accounts(self):
        base = {
            "ODOO_ACCEPTANCE_ALLOW_DISPOSABLE": "1",
            "ODOO_BASE_URL": "http://127.0.0.1:18069",
            "ODOO_DB": "mm_dev_acceptance",
            "ODOO_LOGIN": "editor",
            "ODOO_PASSWORD": "secret",
            "ODOO_ACCEPTANCE_SCOPE": "core",
        }
        with self.assertRaisesRegex(AcceptanceConfigurationError, "must be distinct"):
            AcceptanceConfig.from_environment(
                {**base, "ODOO_REVIEWER_LOGIN": "editor", "ODOO_REVIEWER_PASSWORD": "reviewer-secret"}
            )


if __name__ == "__main__":
    unittest.main()
