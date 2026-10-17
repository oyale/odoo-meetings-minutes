from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOptionalTiming(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Timing Editor", "login": "timing-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create(
            {"name": "Timing series"})

    def test_company_default_on(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "M"})
        self.assertTrue(meeting.time_tracking_enabled)

    def test_series_off_overrides_company(self):
        self.series.time_tracking = "off"
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "M", "series_id": self.series.id})
        self.assertFalse(meeting.time_tracking_enabled)

    def test_series_on_overrides_company_off(self):
        self.env.company.meeting_time_tracking = False
        self.series.time_tracking = "on"
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "M", "series_id": self.series.id})
        self.assertTrue(meeting.time_tracking_enabled)

    def test_series_inherit_follows_company(self):
        self.series.time_tracking = "inherit"
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "M", "series_id": self.series.id})
        self.assertTrue(meeting.time_tracking_enabled)
        self.env.company.meeting_time_tracking = False
        meeting.invalidate_recordset(["time_tracking_enabled"])
        self.assertFalse(meeting.time_tracking_enabled)

    def _scheduled_meeting(self, tracking="off"):
        if tracking:
            self.series.time_tracking = tracking
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "Guarded", "series_id": self.series.id,
             "start_datetime": "2026-11-02 10:00:00"})
        meeting.action_schedule()
        return meeting

    def test_start_meeting_raises_when_tracking_off(self):
        meeting = self._scheduled_meeting(tracking="off")
        with self.assertRaises(Exception):
            meeting.with_user(self.editor).action_start_meeting()

    def test_point_timing_raises_when_tracking_off(self):
        meeting = self._scheduled_meeting(tracking="off")
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create(
            {"meeting_id": meeting.id, "name": "P", "kind": "discussion"})
        with self.assertRaises(Exception):
            item.action_start_timing()

    def test_mark_held_without_start_when_off(self):
        meeting = self._scheduled_meeting(tracking="off")
        meeting.with_user(self.editor).action_mark_held()
        self.assertEqual(meeting.state, "held")
        self.assertFalse(meeting.actual_start_datetime)

    def test_start_meeting_still_works_when_on(self):
        meeting = self._scheduled_meeting(tracking="on")
        meeting.with_user(self.editor).action_start_meeting()
        self.assertTrue(meeting.actual_start_datetime)

    def test_capabilities_include_time_tracking(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create(
            {"name": "Cap", "series_id": self.series.id})
        self.series.time_tracking = "off"
        meeting.invalidate_recordset(["time_tracking_enabled"])
        self.assertFalse(meeting.get_live_capabilities()["time_tracking"])
        self.series.time_tracking = "on"
        meeting.invalidate_recordset(["time_tracking_enabled"])
        self.assertTrue(meeting.get_live_capabilities()["time_tracking"])
