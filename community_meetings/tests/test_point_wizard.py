from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPointWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Point Wizard Editor",
            "login": "point-wizard-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.meeting = cls.env["community.meeting"].with_user(cls.editor).create({
            "name": "Point wizard meeting",
        })
        cls.source_meeting = cls.env["community.meeting"].with_user(cls.editor).create({
            "name": "Point wizard source meeting",
        })

    def _item(self, name, meeting=None):
        return self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": (meeting or self.source_meeting).id, "name": name, "kind": "discussion",
        })

    def test_related_points_persist_on_a_new_point(self):
        related = self._item("Related point")
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "name": "New point",
            "related_topic_ids": [(6, 0, [related.topic_id.id])],
        })
        wizard.action_save()
        self.assertEqual(wizard.created_item_id.topic_id.related_topic_ids, related.topic_id)

    def test_related_points_update_when_reusing_a_point(self):
        existing = self._item("Existing point")
        other = self._item("Other point")
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "topic_id": existing.topic_id.id,
            "related_topic_ids": [(6, 0, [other.topic_id.id])],
        })
        wizard.action_save()
        self.assertEqual(existing.topic_id.related_topic_ids, other.topic_id)

    def test_reuse_preserves_existing_related_links(self):
        existing = self._item("Reuse point")
        related = self._item("Existing related point")
        existing.topic_id.related_topic_ids = related.topic_id
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "topic_id": existing.topic_id.id,
        })
        wizard._onchange_topic_id()
        wizard.action_save()
        self.assertEqual(existing.topic_id.related_topic_ids, related.topic_id)

    def test_create_wizard_agenda_step_persists_related_points(self):
        related = self._item("Create-wizard related point")
        wizard = self.env["community.meeting.create.wizard"].with_user(self.editor).create({
            "name": "Create wizard meeting",
            "start_datetime": fields.Datetime.now(),
            "duration_hours": 1.0,
        })
        self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "creation_wizard_id": wizard.id,
            "name": "Create wizard point",
            "included": True,
            "related_topic_ids": [(6, 0, [related.topic_id.id])],
        })
        wizard.action_finish()
        topic = wizard.created_meeting_id.agenda_item_ids.topic_id
        self.assertEqual(topic.related_topic_ids, related.topic_id)

    def test_a_point_never_relates_to_itself(self):
        existing = self._item("Self point")
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "topic_id": existing.topic_id.id,
            "related_topic_ids": [(6, 0, [existing.topic_id.id])],
        })
        wizard.action_save()
        self.assertFalse(existing.topic_id.related_topic_ids)

    def test_live_add_point_marks_the_context(self):
        action = self.meeting.with_user(self.editor).action_add_point_live()
        self.assertTrue(action["context"]["from_live"])
