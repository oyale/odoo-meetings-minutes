from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMeetingRoleRotation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_ids = [cls.env.ref("base.group_user").id, cls.env.ref("community_meetings.group_meeting_editor").id]
        cls.users = cls.env["res.users"].create(
            [
                {"name": f"Rotation user {index}", "login": f"rotation-user-{index}", "groups_id": [(6, 0, group_ids)]}
                for index in range(3)
            ]
        )
        cls.series = (
            cls.env["community.meeting.series"]
            .with_user(cls.users[0])
            .create(
                {
                    "name": "Rotation series",
                    "coordinator_user_ids": [(6, 0, cls.users.ids)],
                    "secretary_user_ids": [(6, 0, cls.users.ids)],
                    "attendee_partner_ids": [(6, 0, cls.users.mapped("partner_id").ids)],
                }
            )
        )

    def test_initial_rotation_is_stable_and_roles_differ(self):
        organizer = self.series._next_role_assignee("organizer_id", self.series.attendee_partner_ids)
        secretary = self.series._next_role_assignee(
            "secretary_id", self.series.attendee_partner_ids, exclude=organizer
        )
        self.assertEqual(organizer, self.users[0])
        self.assertEqual(secretary, self.users[1])

    def test_unavailable_people_are_skipped_and_remain_in_pool(self):
        unavailable = self.users[0]
        suggested = self.series._next_role_assignee("organizer_id", self.series.attendee_partner_ids, unavailable)
        self.assertEqual(suggested, self.users[1])
        self.assertIn(unavailable, self.series._role_rotation_pool("organizer_id", self.series.attendee_partner_ids))

    def test_rotation_advances_after_the_current_assignment(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.users[0])
            .create(
                {
                    "name": "Existing rotation meeting",
                    "series_id": self.series.id,
                    "organizer_id": self.users[0].id,
                    "secretary_id": self.users[1].id,
                    "start_datetime": "2026-11-02 10:00:00",
                }
            )
        )
        next_user = self.series._next_role_assignee(
            "organizer_id",
            meeting.attendee_partner_ids,
            after=meeting.organizer_id,
        )
        self.assertEqual(next_user, self.users[1])

    def test_creation_wizard_can_apply_a_rotated_coordinator(self):
        wizard = (
            self.env["community.meeting.create.wizard"]
            .with_user(self.users[0])
            .create(
                {
                    "series_id": self.series.id,
                    "name": "Created by rotation",
                    "start_datetime": "2026-11-02 10:00:00",
                    "duration_hours": 1,
                    "attendee_partner_ids": [(6, 0, self.series.attendee_partner_ids.ids)],
                    "organizer_id": self.users[1].id,
                    "secretary_id": self.users[2].id,
                }
            )
        )
        action = wizard.action_finish()
        meeting = self.env["community.meeting"].browse(action["res_id"])
        self.assertEqual(meeting.organizer_id, self.users[1])
        self.assertEqual(meeting.secretary_id, self.users[2])

    def test_rotation_wizard_applies_only_selected_roles_after_confirmation(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.users[0])
            .create(
                {
                    "name": "Rotation meeting",
                    "series_id": self.series.id,
                    "organizer_id": self.users[0].id,
                    "secretary_id": self.users[1].id,
                    "start_datetime": "2026-11-02 10:00:00",
                }
            )
        )
        wizard = (
            self.env["community.meeting.role.rotation.wizard"]
            .with_user(self.users[0])
            .create(
                {
                    "meeting_id": meeting.id,
                    "organizer_id": self.users[2].id,
                    "secretary_id": self.users[0].id,
                    "update_organizer": False,
                }
            )
        )
        wizard.action_apply()
        self.assertEqual(meeting.organizer_id, self.users[0])
        self.assertEqual(meeting.secretary_id, self.users[0])
