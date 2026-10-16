from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPostponeReasons(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Postpone Editor",
            "login": "postpone-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })

    def _meeting_with_point(self, name):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": name})
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "A point", "kind": "discussion",
        })
        return meeting, item

    def test_other_reason_requires_an_explanation(self):
        _meeting, item = self._meeting_with_point("Other reason")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({"disposition": "deferred", "deferral_reason_code": "other"})
        item.write({
            "disposition": "deferred", "deferral_reason_code": "other",
            "deferral_reason": "Waiting on legal advice",
        })
        self.assertEqual(item.deferral_reason_code, "other")

    def test_lack_of_time_needs_no_text(self):
        _meeting, item = self._meeting_with_point("No time")
        item.write({"disposition": "deferred", "deferral_reason_code": "no_time"})
        self.assertEqual(item.disposition, "deferred")
        self.assertTrue(item.review_next_meeting)

    def test_blocked_reason_can_link_a_point(self):
        meeting, item = self._meeting_with_point("Blocked point")
        blocker = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Blocker", "kind": "discussion",
        })
        item.write({
            "disposition": "deferred", "deferral_reason_code": "blocked_point",
            "deferral_blocked_by": f"community.meeting.topic,{blocker.topic_id.id}",
        })
        self.assertEqual(item.deferral_blocked_by, blocker.topic_id)

    def test_link_requires_a_blocking_reason(self):
        meeting, item = self._meeting_with_point("Link guard")
        blocker = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Blocker", "kind": "discussion",
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({
                "disposition": "deferred", "deferral_reason_code": "no_time",
                "deferral_blocked_by": f"community.meeting.topic,{blocker.topic_id.id}",
            })

    def test_existing_free_text_postponement_still_works(self):
        _meeting, item = self._meeting_with_point("Free text")
        item.write({"disposition": "deferred", "deferral_reason": "Waiting"})
        self.assertEqual(item.deferral_reason, "Waiting")
