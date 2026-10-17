from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPresenterPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Presenter Editor",
            "login": "presenter-editor-test",
            "email": "presenter-editor@example.test",
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

    def test_promoted_followup_takes_the_responsible(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Followup meeting", "start_datetime": "2026-11-01 10:00:00",
        })
        item = self._point("Closes", meeting=meeting)
        owner = self.env["res.users"].create({
            "name": "Follow-up owner", "login": "presenter-followup-owner",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("community_meetings.group_meeting_reader").id,
            ])],
        })
        meeting.with_user(self.editor).write({"reader_user_ids": [(4, owner.id)]})
        action = self.env["community.meeting.action"].with_user(self.editor).create({
            "meeting_id": meeting.id, "agenda_item_id": item.id, "name": "Next step",
            "responsible_user_id": owner.id,
        })
        item.with_user(self.editor).write({"disposition": "closed"})
        self.assertEqual(item.topic_id.state, "closed")
        meeting._promote_followups()
        promoted = self.env["community.meeting.topic"].search(
            [("origin_action_id", "=", action.id)]
        )
        self.assertEqual(promoted.presenter_partner_id, owner.partner_id)

    def test_structural_points_stay_empty(self):
        series = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "Structural series", "has_next_meeting_point": True,
        })
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Structural meeting", "series_id": series.id,
            "start_datetime": "2026-12-01 10:00:00",
        })
        next_point = meeting.agenda_item_ids.filtered(lambda i: i.kind == "next_meeting")
        self.assertTrue(next_point)
        self.assertFalse(next_point.presenter_partner_id)

    def test_admitted_proposal_takes_the_proposer(self):
        series = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "Proposal series",
        })
        topic = self.env["community.meeting.topic"].with_user(self.editor).propose({
            "name": "Proposed point",
            "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
            "series_id": series.id,
            "company_id": series.company_id.id,
        })
        self.assertEqual(topic.presenter_partner_id, self.editor.partner_id)

    def test_proposal_responsible_uses_the_proposer(self):
        series = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "Proposal proposer series",
        })
        proposer = self.env["res.partner"].create({"name": "Proposer contact"})
        topic = self.env["community.meeting.topic"].with_user(self.editor)._create_proposal(
            {
                "name": "On-behalf point",
                "agenda_type_id": self.env.ref("community_meetings.agenda_type_discussion").id,
                "series_id": series.id,
                "company_id": series.company_id.id,
            },
            proposer,
            self.editor,
        )
        self.assertEqual(topic.presenter_partner_id, proposer)
        self.assertNotEqual(topic.presenter_partner_id, self.editor.partner_id)
