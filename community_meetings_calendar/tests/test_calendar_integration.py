from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.mail.tests.common import MailCase


@tagged("post_install", "-at_install")
class TestCommunityMeetingCalendar(TransactionCase, MailCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Calendar meeting editor",
            "login": "calendar-meeting-editor-test",
            "email": "editor@example.test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
            ])],
        })
        cls.other = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Calendar meeting attendee",
            "login": "calendar-meeting-attendee-test",
            "email": "attendee@example.test",
            "notification_type": "email",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.reader = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Calendar meeting reader",
            "login": "calendar-meeting-reader-test",
            "email": "reader@example.test",
            "notification_type": "email",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_reader").id,
            ])],
        })

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().search([
            ("key", "=", "calendar.block_mail"),
        ]).unlink()
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
        self.assertTrue(sent, "Odoo did not send a Calendar email to %s" % email)
        attachments = [
            content
            for mail in sent
            for name, content, _mimetype in mail.get("attachments", [])
            if name == "invitation.ics"
        ]
        self.assertTrue(attachments, "The Calendar email did not contain invitation.ics")
        self.assertTrue(any(("UID:%s" % uid).encode("ascii") in content for content in attachments))

    def test_scheduling_creates_one_private_event_with_stable_document_link(self):
        meeting = self._meeting(secretary_id=self.reader.id)
        self.assertFalse(meeting.calendar_event_ids)

        meeting.action_schedule()

        self.assertEqual(len(meeting.calendar_event_ids), 1)
        event = meeting.calendar_event_ids
        self.assertEqual(event.name, meeting.name)
        self.assertEqual(event.start, meeting.start_datetime)
        self.assertEqual(event.stop, meeting.end_datetime)
        self.assertEqual(event.location, meeting.location)
        self.assertEqual(event.user_id, self.editor)
        self.assertEqual(event.privacy, "private")
        self.assertFalse(event.description)
        self.assertFalse(event.alarm_ids)
        self.assertFalse(event.recurrency)
        self.assertFalse(event.user_can_edit)
        self.assertEqual(event.res_model, "community.meeting")
        self.assertEqual(event.res_id, meeting.id)
        self.assertTrue(event.community_calendar_uid)
        action = event.action_open_calendar_event()
        self.assertEqual(action["res_model"], "community.meeting")
        self.assertEqual(action["res_id"], meeting.id)
        meeting_action = meeting.action_open_calendar_event()
        self.assertEqual(meeting_action["res_model"], "calendar.event")
        self.assertEqual(meeting_action["res_id"], event.id)
        event_meeting_action = event.action_open_community_meeting()
        self.assertEqual(event_meeting_action["res_model"], "community.meeting")
        self.assertEqual(event_meeting_action["res_id"], meeting.id)
        self.assertEqual(
            set(event.partner_ids.ids),
            {
                self.editor.partner_id.id,
                self.other.partner_id.id,
                self.reader.partner_id.id,
            },
        )
        invitation = event._get_ics_file()[event.id].decode("utf-8")
        self.assertIn("UID:%s" % event.community_calendar_uid, invitation)
        self.assertNotIn("minutes", invitation.lower())

        with self.assertRaises(AccessError):
            meeting.with_user(self.other).check_access("read")

        messages_before = set(event.message_ids.ids)
        meeting._lock_calendar_event()
        meeting._sync_calendar_event()
        self.assertEqual(len(meeting.calendar_event_ids), 1)
        self.assertEqual(set(event.message_ids.ids), messages_before)

        readable = self._meeting(
            name="Calendar reader link",
            attendee_partner_ids=[(6, 0, [self.reader.partner_id.id])],
            reader_user_ids=[(4, self.reader.id)],
        )
        readable.action_schedule()
        readable_event = readable.calendar_event_ids.with_user(self.reader)
        self.assertEqual(
            readable_event.action_open_calendar_event()["res_id"],
            readable.id,
        )
        self.assertEqual(
            readable_event.action_open_community_meeting()["res_id"],
            readable.id,
        )
        readable.with_user(self.reader).check_access("read")
        with self.assertRaises(AccessError):
            readable_event.with_user(self.other).action_open_community_meeting()

    def test_schedule_fills_end_from_series_and_rejects_invalid_duration(self):
        series = self.env["community.meeting.series"].with_user(self.editor).create({
            "name": "Calendar duration",
            "duration_hours": 1.5,
        })
        meeting = self._meeting(series_id=series.id, end_datetime=False)
        meeting.action_schedule()
        self.assertEqual(str(meeting.end_datetime), "2026-12-01 11:30:00")

        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._meeting(
                name="Invalid duration",
                start_datetime="2026-12-02 10:00:00",
                end_datetime="2026-12-02 10:00:00",
            )

    def test_meeting_edits_update_same_event_and_removed_attendee_gets_cancellation(self):
        meeting = self._meeting()
        with self.mock_mail_gateway():
            meeting.action_schedule()
        event = meeting.calendar_event_ids
        uid = event.community_calendar_uid
        self._assert_sent_ics(self.other.email, uid)
        old_start = event.start

        with self.mock_mail_gateway():
            meeting.write({
                "name": "Rescheduled planning",
                "start_datetime": "2026-12-03 10:00:00",
                "end_datetime": "2026-12-03 11:00:00",
                "location": "Room 8",
            })

        self.assertEqual(meeting.calendar_event_ids, event)
        self.assertNotEqual(event.start, old_start)
        self.assertEqual(event.name, "Rescheduled planning")
        self.assertEqual(event.location, "Room 8")
        self._assert_sent_ics(self.other.email, uid)

        with self.mock_mail_gateway():
            self.env["community.meeting"].browse(meeting.id).write({
                "attendee_partner_ids": [(6, 0, [self.reader.partner_id.id])],
            })
        self._assert_sent_ics(self.reader.email, uid)
        cancellations = self.env["mail.mail"].search([("email_to", "=", self.other.email)])
        self.assertTrue(any(
            "METHOD:CANCEL" in attachment.raw.decode("utf-8")
            for mail in cancellations for attachment in mail.attachment_ids
        ))

    def test_calendar_rpc_cannot_edit_or_delete_managed_event(self):
        meeting = self._meeting()
        meeting.action_schedule()
        event = meeting.calendar_event_ids

        with self.assertRaises(AccessError):
            event.with_user(self.editor).write({"name": "Edited in Calendar"})
        with self.assertRaises(AccessError):
            event.with_user(self.editor).unlink()
        with self.assertRaises(AccessError):
            event.with_user(self.editor).with_context(allow_managed_calendar_edit=True).write({
                "community_meeting_id": False,
            })
        with self.assertRaises(AccessError):
            self.env["calendar.event"].with_user(self.editor).create({
                "name": "Forged managed event",
                "start": "2026-12-01 10:00:00",
                "stop": "2026-12-01 11:00:00",
                "community_meeting_id": meeting.id,
            })
        unmanaged = self.env["calendar.event"].with_user(self.editor).create({
            "name": "Unmanaged event",
            "start": "2020-01-01 10:00:00",
            "stop": "2020-01-01 11:00:00",
        })
        with self.assertRaises(AccessError):
            unmanaged.with_user(self.editor).write({"community_meeting_id": meeting.id})
        with self.assertRaises(AccessError):
            unmanaged.with_user(self.editor).write({"community_calendar_uid": "forged@example.test"})

    def test_external_and_cross_company_attendees_are_rejected(self):
        external = self.env["res.partner"].create({"name": "External contact"})
        with self.assertRaises(ValidationError):
            self._meeting(attendee_partner_ids=[(6, 0, [external.id])])

        other_company = self.env["res.company"].create({"name": "Other company"})
        cross_company = self.env["res.users"].create({
            "name": "Other company attendee",
            "login": "calendar-cross-company-test",
            "company_id": other_company.id,
            "company_ids": [(6, 0, [other_company.id])],
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(ValidationError):
            self._meeting(attendee_partner_ids=[(6, 0, [cross_company.partner_id.id])])

    def test_calendar_sync_validates_a_meeting_batch_before_creating_events(self):
        valid = self._meeting(name="First valid batch invite")
        invalid = self._meeting(name="Invalid batch invite")
        invalid_partner = self.env["res.partner"].create(
            {"name": "External batch invite"}
        )
        attendees = self.env["community.meeting"]._fields["attendee_partner_ids"]
        self.env.cr.execute(
            f"INSERT INTO {attendees.relation} ({attendees.column1}, {attendees.column2}) "
            "VALUES (%s, %s)",
            [invalid.id, invalid_partner.id],
        )
        invalid.invalidate_recordset(["attendee_partner_ids"])
        self.env.cr.execute(
            "UPDATE community_meeting SET state='scheduled' WHERE id IN %s",
            [tuple((valid | invalid).ids)],
        )
        (valid | invalid).invalidate_recordset(["state"])
        (valid | invalid)._lock_calendar_event()

        with self.assertRaises(ValidationError):
            (valid | invalid)._sync_calendar_event()

        self.assertFalse(valid.calendar_event_ids)
        self.assertFalse(invalid.calendar_event_ids)

    def test_calendar_sync_creates_events_in_one_batch_per_owner(self):
        self.env["ir.config_parameter"].sudo().set_param("calendar.block_mail", "1")
        meetings = self._meeting(name="First batch event") | self._meeting(
            name="Second batch event"
        )
        self.env.cr.execute(
            "UPDATE community_meeting SET state='scheduled' WHERE id IN %s",
            [tuple(meetings.ids)],
        )
        meetings.invalidate_recordset(["state"])
        meetings._lock_calendar_event()

        calendar_event_class = type(self.env["calendar.event"])
        original_create = calendar_event_class._community_meetings_calendar_create
        batch_sizes = []

        def record_create(events, vals_list):
            batch_sizes.append(len(vals_list))
            return original_create(events, vals_list)

        with patch.object(
            calendar_event_class,
            "_community_meetings_calendar_create",
            record_create,
        ):
            meetings._sync_calendar_event()

        self.assertEqual(batch_sizes, [2])
        self.assertEqual(len(meetings.calendar_event_ids), 2)

    def test_cancel_removes_event_and_notifies_invitees(self):
        meeting = self._meeting()
        meeting.action_schedule()
        event = meeting.calendar_event_ids
        uid = event.community_calendar_uid

        meeting.action_cancel()

        self.assertFalse(event.exists())
        mails = self.env["mail.mail"].search([("email_to", "=", self.other.email)])
        cancellations = [
            attachment.raw.decode("utf-8")
            for mail in mails for attachment in mail.attachment_ids
            if "METHOD:CANCEL" in attachment.raw.decode("utf-8")
        ]
        self.assertTrue(cancellations)
        self.assertIn("UID:%s" % uid, cancellations[-1])

    def test_blocked_mail_and_missing_or_invalid_email_do_not_send(self):
        self.env["ir.config_parameter"].sudo().set_param("calendar.block_mail", "1")
        meeting = self._meeting()
        with self.mock_mail_gateway():
            meeting.action_schedule()
            self.assertFalse(self._mails)
        meeting.action_cancel()

        self.env["ir.config_parameter"].sudo().search([
            ("key", "=", "calendar.block_mail"),
        ]).unlink()
        no_email_user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Calendar attendee without email",
            "login": "calendar-no-email-test",
            "email": False,
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        no_email_meeting = self._meeting(
            name="Calendar attendee without email",
            attendee_partner_ids=[(6, 0, [no_email_user.partner_id.id])],
        )
        with self.mock_mail_gateway():
            no_email_meeting.action_schedule()
            self.assertFalse(self._mails)
        self.assertIn(no_email_user.partner_id, no_email_meeting.calendar_event_ids.partner_ids)

        invalid_email_user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Calendar attendee with invalid email",
            "login": "calendar-invalid-email-test",
            "email": "not-an-email",
            "notification_type": "email",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        invalid_meeting = self._meeting(
            name="Calendar attendee with invalid email",
            attendee_partner_ids=[(6, 0, [invalid_email_user.partner_id.id])],
        )
        invalid_meeting.action_schedule()
        invalid_event = invalid_meeting.calendar_event_ids.with_context(no_mail_to_attendees=False)
        self.assertFalse(
            invalid_event._community_meetings_calendar_cancel_mail(invalid_email_user.partner_id)
        )
        cancellation = invalid_event._community_meetings_calendar_cancel_mail(
            self.other.partner_id
        )
        valid_recipient_mail = cancellation.filtered(
            lambda mail: mail.email_to == self.other.email
        )
        self.assertTrue(valid_recipient_mail)
        cancellation_ics = valid_recipient_mail.attachment_ids.raw.decode("utf-8")
        self.assertNotIn(invalid_email_user.email, cancellation_ics)

    def test_schedule_rollback_does_not_leave_event_or_send_invitation(self):
        meeting = self._meeting()
        mail_ids_before = set(self.env["mail.mail"].search([]).ids)
        with self.assertRaises(RuntimeError), self.env.cr.savepoint():
            meeting.action_schedule()
            raise RuntimeError("rollback scheduled meeting")
        meeting.invalidate_recordset(["calendar_event_ids", "state"])
        self.assertFalse(meeting.calendar_event_ids)
        self.assertEqual(set(self.env["mail.mail"].search([]).ids), mail_ids_before)

    def test_uninstall_cleanup_removes_only_managed_events(self):
        meeting = self._meeting()
        meeting.action_schedule()
        managed = meeting.calendar_event_ids
        unmanaged = self.env["calendar.event"].create({
            "name": "Unmanaged calendar event",
            "start": "2020-01-01 10:00:00",
            "stop": "2020-01-01 11:00:00",
        })

        self.env["calendar.event"].sudo()._community_meetings_calendar_uninstall_cleanup()

        self.assertFalse(managed.exists())
        self.assertTrue(unmanaged.exists())

    def test_scheduled_meeting_syncs_until_held_then_freezes_calendar_event(self):
        meeting = self._meeting()
        meeting.action_schedule()
        event = meeting.calendar_event_ids
        meeting.action_start_meeting()
        meeting.write({"name": "Changed during meeting"})
        self.assertEqual(event.name, "Changed during meeting")
        meeting.action_mark_held()
        meeting.write({"name": "Edited historical meeting"})
        self.assertEqual(event.name, "Changed during meeting")
