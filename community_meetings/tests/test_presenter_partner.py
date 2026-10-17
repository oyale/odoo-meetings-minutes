from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPresenterPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Presenter Editor",
            "login": "presenter-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
                cls.env.ref("community_meetings.group_agenda_proposer").id,
            ])],
        })
        cls.meeting = cls.env["community.meeting"].with_user(cls.editor).create({
            "name": "Presenter meeting",
        })

    def _point(self, name, meeting=None):
        return self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": (meeting or self.meeting).id, "name": name, "kind": "discussion",
        })

    def test_new_point_defaults_to_creator(self):
        item = self._point("Owned point")
        self.assertEqual(item.presenter_partner_id, self.editor.partner_id)
        self.assertEqual(item.topic_id.presenter_partner_id, self.editor.partner_id)

    def test_writing_item_presenter_updates_the_point(self):
        item = self._point("Editable point")
        other = self.env["res.partner"].create({"name": "Other responsible"})
        item.with_user(self.editor).write({"presenter_partner_id": other.id})
        self.assertEqual(item.topic_id.presenter_partner_id, other)
        item.invalidate_recordset(["presenter_partner_id"])
        self.assertEqual(item.presenter_partner_id, other)

    def test_reused_point_keeps_its_responsible(self):
        source = self.env["community.meeting"].with_user(self.editor).create({"name": "Source"})
        original = self._point("Shared point", meeting=source)
        other = self.env["res.partner"].create({"name": "Point owner"})
        original.topic_id.presenter_partner_id = other
        reused = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.meeting.id, "topic_id": original.topic_id.id,
        })
        self.assertEqual(reused.presenter_partner_id, other)
