from __future__ import annotations

import unittest
from types import SimpleNamespace

from acceptance.features.steps.preview_draft_minutes import preview_did_not_write


class PreviewStepTests(unittest.TestCase):
    def test_then_fails_when_preview_writes_to_the_meeting(self):
        context = SimpleNamespace(
            saved_draft_before_preview=(
                {"id": 3, "state": "minutes_draft", "write_date": "before"},
                {"id": 7, "discussion_notes": "Earlier notes", "write_date": "same"},
                "<p>Saved minutes</p>",
            ),
            meeting_id=3,
            live_meeting_fixture=SimpleNamespace(item_ids={"discussion": 7}),
            browser_session=SimpleNamespace(
                record=lambda model, record_id, fields: (
                    {"id": 3, "state": "minutes_draft", "write_date": "after"}
                    if model == "community.meeting"
                    else {"id": 7, "discussion_notes": "Earlier notes", "write_date": "same"}
                ),
                rpc=lambda *args: "<p>Saved minutes</p>",
            ),
        )

        with self.assertRaises(AssertionError):
            preview_did_not_write(context)


if __name__ == "__main__":
    unittest.main()
