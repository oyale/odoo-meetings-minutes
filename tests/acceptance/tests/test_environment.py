from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from acceptance.features.environment import after_scenario, after_step, before_all
from behave.model import Status


class AcceptanceEnvironmentTests(unittest.TestCase):
    def test_empty_behave_selection_fails_before_browser_startup(self):
        scenario = SimpleNamespace(should_run=Mock(return_value=False))
        feature = SimpleNamespace(walk_scenarios=lambda: [scenario])
        runner = SimpleNamespace(features=[feature], config=object())
        context = SimpleNamespace(_runner=runner)
        with (
            patch("acceptance.features.environment.AcceptanceConfig.from_environment", return_value=object()),
            self.assertRaisesRegex(RuntimeError, "selected no acceptance scenarios"),
        ):
            before_all(context)

    def test_failed_or_errored_step_saves_screenshot_dom_and_console(self):
        with tempfile.TemporaryDirectory() as temporary:
            page = Mock()
            page.content.return_value = "<html>failure state</html>"

            def save_screenshot(*, path, full_page):
                Path(path).write_bytes(b"png")

            page.screenshot.side_effect = save_screenshot
            session = SimpleNamespace(page=page, console_errors=["Uncaught TypeError: fixture error"])
            context = SimpleNamespace(
                browser_session=session,
                acceptance_config=SimpleNamespace(database="mm_dev_test"),
                scenario=SimpleNamespace(name="A failing UI step"),
            )
            artifacts = []
            with patch("acceptance.features.environment.tempfile.gettempdir", return_value=temporary):
                for status in (Status.failed, Status.error):
                    after_step(context, SimpleNamespace(status=status))
                    artifacts.append(context.failed_step_artifacts)

            self.assertEqual(page.screenshot.call_count, 2)
            screenshot, html, console = artifacts[-1]
            self.assertEqual(screenshot.read_bytes(), b"png")
            self.assertEqual(html.read_text(encoding="utf-8"), "<html>failure state</html>")
            self.assertEqual(console.read_text(encoding="utf-8"), "Uncaught TypeError: fixture error\n")
            self.assertEqual(screenshot.stat().st_mode & 0o777, 0o600)
            self.assertEqual(html.stat().st_mode & 0o777, 0o600)
            self.assertEqual(console.stat().st_mode & 0o777, 0o600)
            self.assertEqual(page.screenshot.call_args.kwargs, {"path": str(screenshot), "full_page": True})

    def test_selected_skipped_scenario_is_a_failure(self):
        scenario = SimpleNamespace(name="should not silently skip", status=Status.skipped)

        with self.assertRaisesRegex(AssertionError, "was skipped"):
            after_scenario(SimpleNamespace(), scenario)


if __name__ == "__main__":
    unittest.main()
