from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAuditBatching(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Domain editor",
                "login": "domain-editor-test",
                "email": "domain-editor@example.test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_manager").id,
                        ],
                    )
                ],
            }
        )

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.editor)

    def test_legacy_native_evidence_override_is_honored_in_batch(self):
        meeting = self.env["community.meeting"].create(
            {"name": "Legacy native evidence"}
        )
        item = self.env["community.meeting.agenda.item"].create(
            {
                "meeting_id": meeting.id,
                "name": "Native TODO",
                "kind": "todo",
            }
        )
        action = self.env["community.meeting.action"].create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "Native activity",
                "responsible_user_id": self.editor.id,
                "followup_kind": "activity",
            }
        )
        action_class = type(action)
        original = action_class._has_execution_evidence

        def legacy_extension(record):
            return original(record) and record.id != action.id

        self.assertTrue(action._has_execution_evidence())
        with patch.object(action_class, "_has_execution_evidence", legacy_extension):
            self.assertEqual(action._execution_evidence_by_action(), {action.id: False})
            with self.assertRaises(ValidationError), self.cr.savepoint():
                item.write({"disposition": "closed"})
        self.assertEqual(item.disposition, "open")

    def test_batch_results_do_not_close_two_primary_participations_of_one_topic(self):
        series = self.env["community.meeting.series"].create(
            {"name": "Batch result series"}
        )
        meetings = self.env["community.meeting"].create(
            [
                {"name": "First primary participation", "series_id": series.id},
                {"name": "Second primary participation", "series_id": series.id},
            ]
        )
        first = self.env["community.meeting.agenda.item"].create(
            {
                "meeting_id": meetings[0].id,
                "name": "Shared batch result",
            }
        )
        second = self.env["community.meeting.agenda.item"].create(
            {
                "meeting_id": meetings[1].id,
                "topic_id": first.topic_id.id,
            }
        )
        self.assertFalse(first.is_followup or second.is_followup)
        # Warm both values used by _record_result before the batched write.
        self.assertEqual(first.topic_id.state, "open")
        self.assertFalse(first.topic_id.last_participation_id)

        with self.assertRaises(UserError), self.cr.savepoint():
            (first | second).write({"disposition": "closed"})

        self.assertEqual((first | second).mapped("disposition"), ["open", "open"])
        self.assertEqual(first.topic_id.state, "open")
        self.assertFalse(first.topic_id.last_participation_id)

    def test_batch_results_refresh_preloaded_topic_state_after_lock(self):
        series = self.env["community.meeting.series"].create(
            {"name": "Stale batch result"}
        )
        meetings = self.env["community.meeting"].create(
            [
                {"name": "Recorded origin", "series_id": series.id},
                {"name": "Later participation", "series_id": series.id},
            ]
        )
        first = self.env["community.meeting.agenda.item"].create(
            {
                "meeting_id": meetings[0].id,
                "name": "Preloaded topic",
            }
        )
        second = self.env["community.meeting.agenda.item"].create(
            {
                "meeting_id": meetings[1].id,
                "topic_id": first.topic_id.id,
            }
        )
        topic = first.topic_id
        self.assertEqual(topic.state, "open")
        self.assertFalse(topic.last_participation_id)
        self.env.flush_all()
        # Simulate an out-of-cache result before acquiring the workflow lock.
        self.cr.execute(
            "UPDATE community_meeting_topic SET state='closed', "
            "last_participation_id=%s WHERE id=%s",
            [first.id, topic.id],
        )
        with self.assertRaises(UserError), self.cr.savepoint():
            second.write({"disposition": "closed"})
        topic.invalidate_recordset()
        self.assertEqual(topic.state, "closed")
        self.assertEqual(topic.last_participation_id, first)
        self.assertEqual(second.disposition, "open")
