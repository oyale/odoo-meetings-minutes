from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMeetingKinds(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Kind Editor", "login": "kind-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.operational = cls.env.ref("community_meetings.kind_operational")

    def _series(self, name, kind=None):
        vals = {"name": name}
        if kind:
            vals["meeting_kind_id"] = kind.id
        return self.env["community.meeting.series"].with_user(self.editor).create(vals)

    def test_series_defaults_to_operational_kind(self):
        self.assertEqual(self._series("Default kind").meeting_kind_id, self.operational)

    def test_meeting_follows_series_kind_and_constraint_holds(self):
        board = self.env["community.meeting.kind"].create({"name": "Board", "code": "board"})
        series = self._series("Board series", board)
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Board meeting", "series_id": series.id,
            "start_datetime": "2026-11-01 10:00:00",
        })
        self.assertEqual(meeting.meeting_kind_id, board)
        with self.assertRaises(ValidationError):
            meeting.meeting_kind_id = self.operational

    def test_kinds_cannot_be_deleted_and_series_kind_is_locked(self):
        kind = self.env["community.meeting.kind"].create({"name": "Temporary", "code": "temporary"})
        with self.assertRaises(UserError):
            kind.unlink()
        series = self._series("Locked", kind)
        self.env["community.meeting"].with_user(self.editor).create({
            "name": "Locked meeting", "series_id": series.id,
            "start_datetime": "2026-11-02 10:00:00",
        })
        with self.assertRaises(UserError):
            series.write({"meeting_kind_id": self.operational.id})
