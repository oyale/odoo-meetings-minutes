from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDiscussionHistory(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Discussion history editor",
                "login": "discussion-history-editor-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_editor").id,
                        ],
                    )
                ],
            }
        )
        cls.reader = cls.env["res.users"].create(
            {
                "name": "Discussion history reader",
                "login": "discussion-history-reader-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_reader").id,
                        ],
                    )
                ],
            }
        )
        cls.series = (
            cls.env["community.meeting.series"]
            .with_user(cls.editor)
            .create(
                {
                    "name": "Discussion history series",
                }
            )
        )

    def _meeting(self, name, start, readers=()):
        return (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": name,
                    "series_id": self.series.id,
                    "start_datetime": start,
                    "reader_user_ids": [(6, 0, [user.id for user in readers])],
                }
            )
        )

    def _carry(self, source, destination):
        transfer = (
            self.env["community.meeting.carryover"]
            .with_user(self.editor)
            .create(
                {
                    "origin_model": "agenda_item",
                    "origin_record_id": source.id,
                    "destination_meeting_id": destination.id,
                }
            )
        )
        transfer.action_accept()
        return transfer.destination_item_id

    def test_previous_notes_are_separate_and_cutoff_stops_older_context(self):
        first = self._meeting("First", "2026-11-02 10:00:00")
        second = self._meeting("Second", "2026-11-09 10:00:00")
        third = self._meeting("Third", "2026-11-16 10:00:00")
        agenda = self.env["community.meeting.agenda.item"].with_user(self.editor)
        source = agenda.create({"meeting_id": first.id, "name": "Topic"})
        source.discussion_notes = "<p>First discussion</p>"
        current = self._carry(source, second)
        self.assertIn("First discussion", current.previous_discussion_html)
        self.assertFalse(current.discussion_notes)

        current.discussion_notes = "<p>Second discussion</p>"
        current.discard_previous_discussion = True
        self.assertFalse(current.previous_discussion_html)
        latest = self._carry(current, third)
        self.assertIn("Second discussion", latest.previous_discussion_html)
        self.assertNotIn("First discussion", latest.previous_discussion_html)

        current.discard_previous_discussion = False
        self.assertIn("First discussion", current.previous_discussion_html)

    def test_reader_cannot_get_notes_from_an_inaccessible_source_meeting(self):
        source_meeting = self._meeting("Private source", "2026-11-02 10:00:00")
        destination_meeting = self._meeting(
            "Visible destination",
            "2026-11-09 10:00:00",
            readers=(self.reader,),
        )
        agenda = self.env["community.meeting.agenda.item"].with_user(self.editor)
        source = agenda.create({"meeting_id": source_meeting.id, "name": "Private topic"})
        source.discussion_notes = "<p>Secret earlier notes</p>"
        destination = self._carry(source, destination_meeting)

        visible = destination.with_user(self.reader)
        self.assertFalse(visible.previous_discussion_html)
        self.assertFalse(visible.has_previous_discussion)
        with self.assertRaises(AccessError):
            visible.write({"discard_previous_discussion": True})

    def test_inaccessible_intermediate_source_stops_the_history_chain(self):
        first_meeting = self._meeting("Visible oldest source", "2026-11-02 10:00:00", readers=(self.reader,))
        hidden_meeting = self._meeting("Hidden intermediate", "2026-11-09 10:00:00")
        destination_meeting = self._meeting("Visible destination", "2026-11-16 10:00:00", readers=(self.reader,))
        agenda = self.env["community.meeting.agenda.item"].with_user(self.editor)
        oldest = agenda.create({"meeting_id": first_meeting.id, "name": "Topic"})
        oldest.discussion_notes = "<p>Must not skip the hidden meeting</p>"
        hidden = self._carry(oldest, hidden_meeting)
        hidden.discussion_notes = "<p>Hidden discussion</p>"
        current = self._carry(hidden, destination_meeting)

        visible = current.with_user(self.reader)
        self.assertFalse(visible.previous_discussion_html)
        self.assertFalse(visible.discussion_history["entries"])

    def test_minutes_snapshot_contains_only_current_discussion(self):
        first = self._meeting("First", "2026-11-02 10:00:00")
        second = self._meeting("Second", "2026-11-09 10:00:00")
        agenda = self.env["community.meeting.agenda.item"].with_user(self.editor)
        source = agenda.create({"meeting_id": first.id, "name": "Topic"})
        current = self._carry(source, second)
        source.discussion_notes = "<p>Historical only</p>"
        current.discussion_notes = "<p>Current only</p>"

        snapshot = self.env["community.meeting.revision"]._build_public_content(second)
        discussion = snapshot["agenda"][0]["discussion"]
        self.assertIn("Current only", discussion)
        self.assertNotIn("Historical only", discussion)

    def test_cutoff_without_notes_remains_visible_and_restorable(self):
        first = self._meeting("First", "2026-11-02 10:00:00")
        second = self._meeting("Second", "2026-11-09 10:00:00")
        agenda = self.env["community.meeting.agenda.item"].with_user(self.editor)
        source = agenda.create({"meeting_id": first.id, "name": "Topic"})
        current = self._carry(source, second)

        self.assertTrue(current.discussion_history["available"])
        self.assertFalse(current.discussion_history["entries"])
        current.discard_previous_discussion = True
        self.assertTrue(current.discussion_history["available"])
        self.assertFalse(current.discussion_history["entries"])
        current.discard_previous_discussion = False
        self.assertTrue(current.discussion_history["available"])

    def test_recurring_history_does_not_skip_cancelled_occurrence(self):
        template = (
            self.env["community.meeting.series.agenda.template"]
            .with_user(self.editor)
            .create(
                {
                    "series_id": self.series.id,
                    "name": "Recurring topic",
                    "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
                }
            )
        )
        first = template._create_occurrence(self._meeting("First", "2026-11-02 10:00:00"))
        first.discussion_notes = "<p>Old discussion</p>"
        cancelled_meeting = self._meeting("Cancelled", "2026-11-09 10:00:00")
        cancelled = template._create_occurrence(cancelled_meeting)
        cancelled_meeting.action_cancel()
        later = template._create_occurrence(self._meeting("Later", "2026-11-16 10:00:00"))

        self.assertEqual(later.topic_id.previous_occurrence_id, cancelled.topic_id)
        self.assertFalse(later.previous_discussion_html)
