from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from acceptance.features.steps.lifecycle_approval import minutes_draft_has_no_agenda


class LifecycleApprovalStepTests(unittest.TestCase):
    def test_failed_fixture_setup_marks_disposable_database_for_cleanup(self):
        context = SimpleNamespace(
            acceptance_config=SimpleNamespace(reviewer_login="reviewer"),
            browser_session=object(),
            requires_database_drop=False,
        )

        with (
            patch(
                "acceptance.features.steps.lifecycle_approval.LiveMeetingFixture.create_minutes_draft_without_agenda",
                side_effect=RuntimeError("fixture setup failed after creating meeting"),
            ),
            self.assertRaisesRegex(RuntimeError, "fixture setup failed"),
        ):
            minutes_draft_has_no_agenda(context)

        self.assertTrue(context.requires_database_drop)


if __name__ == "__main__":
    unittest.main()
