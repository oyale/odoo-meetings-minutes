from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMeetingLiveAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Live workspace editor",
            "login": "meeting-live-workspace-editor-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })

    def test_draft_meeting_opens_live_workspace_with_editor_capabilities(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({
            "name": "Draft live workspace",
            "start_datetime": "2026-11-03 10:00:00",
        })

        action = meeting.with_user(self.editor).action_open_live_meeting()
        capabilities = meeting.with_user(self.editor).get_live_capabilities()

        self.assertEqual(action["tag"], "community_meetings.live_meeting")
        self.assertEqual(action["params"]["meeting_id"], meeting.id)
        self.assertTrue(capabilities["can_edit"])
        self.assertTrue(capabilities["can_add_point"])
