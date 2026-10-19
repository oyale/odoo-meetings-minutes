from odoo.tests import TransactionCase, tagged

from odoo.addons.mail.tests.common import MailCase


@tagged("post_install", "-at_install")
class TestAuditBatching(TransactionCase, MailCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Calendar meeting editor",
                    "login": "calendar-meeting-editor-test",
                    "email": "editor@example.test",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref(
                                    "community_meetings.group_meeting_editor"
                                ).id,
                            ],
                        )
                    ],
                }
            )
        )
        cls.other = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Calendar meeting attendee",
                    "login": "calendar-meeting-attendee-test",
                    "email": "attendee@example.test",
                    "notification_type": "email",
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        cls.reader = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Calendar meeting reader",
                    "login": "calendar-meeting-reader-test",
                    "email": "reader@example.test",
                    "notification_type": "email",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref(
                                    "community_meetings.group_meeting_reader"
                                ).id,
                            ],
                        )
                    ],
                }
            )
        )

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().search(
            [
                ("key", "=", "calendar.block_mail"),
            ]
        ).unlink()
        self.meetings = self.env["community.meeting"].with_user(self.editor)

    def _meeting(self, **values):
        defaults = {
            "name": "Calendar planning",
            "start_datetime": "2026-12-01 10:00:00",
            "attendee_partner_ids": [(6, 0, [self.other.partner_id.id])],
            "location": "Room 4",
        }
        defaults.update(values)
        return self.meetings.create(defaults)

    def _assert_sent_ics(self, email, uid):
        sent = [mail for mail in self._mails if email in str(mail.get("email_to"))]
        self.assertTrue(sent, f"Odoo did not send a Calendar email to {email}")
        attachments = [
            content
            for mail in sent
            for name, content, _mimetype in mail.get("attachments", [])
            if name == "invitation.ics"
        ]
        self.assertTrue(
            attachments, "The Calendar email did not contain invitation.ics"
        )
        self.assertTrue(
            any(f"UID:{uid}".encode("ascii") in content for content in attachments)
        )

    def test_calendar_batch_preserves_owners_invitations_and_existing_events(self):
        self.other.write(
            {
                "groups_id": [
                    (4, self.env.ref("community_meetings.group_meeting_editor").id)
                ]
            }
        )
        existing = self._meeting(name="Existing event in mixed batch")
        with self.mock_mail_gateway():
            existing.action_schedule()
        original_event = existing.calendar_event_ids
        original_uid = original_event.community_calendar_uid
        first = self._meeting(name="New event for first owner")
        second = (
            self.env["community.meeting"]
            .with_user(self.other)
            .create(
                {
                    "name": "New event for second owner",
                    "start_datetime": "2026-12-02 10:00:00",
                    "end_datetime": "2026-12-02 11:00:00",
                    "attendee_partner_ids": [(6, 0, [self.reader.partner_id.id])],
                }
            )
        )
        meetings = self.env["community.meeting"].browse(
            [existing.id, first.id, second.id]
        )
        self.env.flush_all()
        self.cr.execute(
            "UPDATE community_meeting SET name=%s, "
            "start_datetime='2026-12-03 10:00:00', "
            "end_datetime='2026-12-03 11:00:00' WHERE id=%s",
            ["Updated event in mixed batch", existing.id],
        )
        self.cr.execute(
            "UPDATE community_meeting SET state='scheduled' WHERE id IN %s",
            [tuple((first | second).ids)],
        )
        meetings.invalidate_recordset(["state", "name"])
        meetings._lock_calendar_event()
        with self.mock_mail_gateway():
            meetings._sync_calendar_event()

        self.assertEqual(existing.calendar_event_ids, original_event)
        self.assertEqual(original_event.community_calendar_uid, original_uid)
        self.assertEqual(original_event.name, "Updated event in mixed batch")
        self.assertEqual(len(meetings.calendar_event_ids), 3)
        self.assertEqual(first.calendar_event_ids.user_id, self.editor)
        self.assertEqual(second.calendar_event_ids.user_id, self.other)
        self.assertEqual(first.calendar_event_ids.create_uid, self.editor)
        self.assertEqual(second.calendar_event_ids.create_uid, self.other)
        uids = meetings.calendar_event_ids.mapped("community_calendar_uid")
        self.assertEqual(len(set(uids)), 3)
        for meeting in meetings:
            event = meeting.calendar_event_ids
            ics = event._get_ics_file()[event.id].decode("utf-8")
            self.assertIn("UID:" + event.community_calendar_uid, ics)
            self.assertIn(meeting.organizer_id.email, ics)
            self.assertIn(meeting.name, ics)
        self._assert_sent_ics(self.other.email, original_uid)
        self._assert_sent_ics(
            self.other.email, first.calendar_event_ids.community_calendar_uid
        )
        self._assert_sent_ics(
            self.reader.email, second.calendar_event_ids.community_calendar_uid
        )
