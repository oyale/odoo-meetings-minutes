from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStructuralEstimates(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Estimate Editor", "login": "structural-estimate-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create({
            "name": "Structural estimates series",
            "has_minutes_approval_point": True,
            "has_next_meeting_point": True,
        })

    def _held_previous_meeting(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Previous", "series_id": self.series.id,
            "start_datetime": "2026-11-01 10:00:00",
        })
        meeting.action_schedule()
        meeting.action_mark_held()
        return meeting

    def _new_meeting(self, start="2026-11-08 10:00:00"):
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Current", "series_id": self.series.id,
            "start_datetime": start,
        })
        return meeting

    def test_minutes_approval_estimate_counts_pending_meetings(self):
        self._held_previous_meeting()
        meeting = self._new_meeting()
        approval = meeting.agenda_item_ids.filtered(lambda i: i.kind == "minutes_approval")
        self.assertEqual(len(approval), 1)
        self.assertEqual(approval.estimated_minutes, 5)

    def test_minutes_approval_estimate_scales_with_pending(self):
        self._held_previous_meeting()
        second = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Second previous", "series_id": self.series.id,
            "start_datetime": "2026-11-02 10:00:00",
        })
        second.action_schedule()
        second.action_mark_held()
        meeting = self._new_meeting()
        approval = meeting.agenda_item_ids.filtered(lambda i: i.kind == "minutes_approval")
        self.assertEqual(approval.estimated_minutes, 10)

    def test_next_meeting_estimate_is_five(self):
        meeting = self._new_meeting()
        nxt = meeting.agenda_item_ids.filtered(lambda i: i.kind == "next_meeting")
        self.assertEqual(len(nxt), 1)
        self.assertEqual(nxt.estimated_minutes, 5)

    def test_standalone_meeting_uses_company_estimate(self):
        self.env.company.meeting_estimated_minutes = 7
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Solo"})
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Solo point",
        })
        wizard.action_save()
        self.assertEqual(wizard.created_item_id.estimated_minutes, 7)

    def test_wizard_prefills_series_estimate(self):
        self.series.default_estimated_minutes = 12
        meeting = self._new_meeting()
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).with_context(
            default_meeting_id=meeting.id,
        ).default_get(["meeting_id", "estimated_minutes"])
        self.assertEqual(wizard["estimated_minutes"], 12)

    def test_wizard_prefills_company_estimate_without_series(self):
        self.env.company.meeting_estimated_minutes = 7
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Solo"})
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).with_context(
            default_meeting_id=meeting.id,
        ).default_get(["meeting_id", "estimated_minutes"])
        self.assertEqual(wizard["estimated_minutes"], 7)

    def test_wizard_prefills_series_estimate_falling_back_to_company(self):
        self.env.company.meeting_estimated_minutes = 9
        meeting = self._new_meeting()
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).with_context(
            default_meeting_id=meeting.id,
        ).default_get(["meeting_id", "estimated_minutes"])
        self.assertEqual(wizard["estimated_minutes"], 9)

    def test_proposal_wizard_prefills_series_estimate(self):
        self.series.default_estimated_minutes = 15
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).with_context(
            default_propose=True, default_proposal_series_id=self.series.id,
        ).default_get(["propose", "proposal_series_id", "estimated_minutes"])
        self.assertEqual(wizard["estimated_minutes"], 15)
