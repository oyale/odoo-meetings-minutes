from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAddPointPolicy(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Policy Editor", "login": "add-point-policy-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create(
            {"name": "Add point policy series"})

    def _meeting(self, **vals):
        return self.env["community.meeting"].with_user(self.editor).create(
            dict({"name": "Policy meeting", "series_id": self.series.id}, **vals))

    def _scheduled(self, meeting):
        meeting.start_datetime = "2026-11-02 10:00:00"
        meeting.action_schedule()
        return meeting

    # --- effective-mode resolution ---

    def test_company_default_is_ongoing(self):
        meeting = self._meeting()
        self.assertEqual(meeting.add_point_policy, "ongoing")

    def test_series_overrides_company(self):
        self.series.add_point_policy = "draft"
        meeting = self._meeting()
        self.assertEqual(meeting.add_point_policy, "draft")

    def test_standalone_meeting_follows_company(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Solo"})
        self.env.company.meeting_add_point_policy = "draft"
        meeting.invalidate_recordset(["add_point_policy"])
        self.assertEqual(meeting.add_point_policy, "draft")

    # --- computed allowance ---

    def test_draft_only_blocks_scheduled(self):
        self.series.add_point_policy = "draft"
        meeting = self._scheduled(self._meeting())
        self.assertFalse(meeting.add_point_allowed)

    def test_before_start_allows_scheduled_not_started(self):
        self.series.add_point_policy = "scheduled"
        meeting = self._scheduled(self._meeting())
        self.assertTrue(meeting.add_point_allowed)
        meeting.action_start_meeting()
        self.assertFalse(meeting.add_point_allowed)

    def test_ongoing_allows_started_meeting(self):
        meeting = self._scheduled(self._meeting())
        meeting.action_start_meeting()
        self.assertTrue(meeting.add_point_allowed)
        meeting.action_mark_held()
        self.assertFalse(meeting.add_point_allowed)

    def test_never_allowed_after_held(self):
        for policy in ("draft", "scheduled", "ongoing"):
            self.series.add_point_policy = policy
            meeting = self._scheduled(self._meeting())
            meeting.action_mark_held()
            self.assertFalse(meeting.add_point_allowed)

    # --- server guards ---

    def test_action_add_point_raises_when_blocked(self):
        self.series.add_point_policy = "draft"
        meeting = self._scheduled(self._meeting())
        with self.assertRaises(UserError):
            meeting.with_user(self.editor).action_add_point()
        with self.assertRaises(UserError):
            meeting.with_user(self.editor).action_add_point_live()

    def test_action_add_point_opens_when_allowed(self):
        meeting = self._scheduled(self._meeting())
        self.assertTrue(meeting.with_user(self.editor).action_add_point()["context"]["default_meeting_id"])

    def test_wizard_save_guarded(self):
        self.series.add_point_policy = "draft"
        meeting = self._scheduled(self._meeting())
        wizard = self.env["community.meeting.point.wizard"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Blocked point",
        })
        with self.assertRaises(UserError):
            wizard.action_save()

    def test_capabilities_include_can_add_point(self):
        self.series.add_point_policy = "draft"
        meeting = self._scheduled(self._meeting())
        self.assertFalse(meeting.get_live_capabilities()["can_add_point"])
        self.series.add_point_policy = "ongoing"
        meeting.invalidate_recordset(["add_point_allowed"])
        self.assertTrue(meeting.get_live_capabilities()["can_add_point"])
