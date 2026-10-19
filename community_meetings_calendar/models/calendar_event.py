import base64
import re
from typing import ClassVar

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import single_email_re


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    community_meeting_id = fields.Many2one(
        "community.meeting",
        string="Community Meeting",
        copy=False,
        index=True,
        ondelete="cascade",
    )
    community_calendar_uid = fields.Char(copy=False, index=True)

    _sql_constraints: ClassVar[list[tuple[str, str, str]]] = [
        (
            "community_meeting_calendar_event_unique",
            "unique(community_meeting_id)",
            "A community meeting can have only one Calendar event.",
        ),
        (
            "community_calendar_uid_unique",
            "unique(community_calendar_uid)",
            "A managed Calendar event UID must be unique.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get("community_meeting_id") or values.get("community_calendar_uid") for values in vals_list):
            raise AccessError(_("Meeting Calendar events are managed from the meeting."))
        return super().create(vals_list)

    def write(self, values):
        if {"community_meeting_id", "community_calendar_uid"}.intersection(values):
            raise AccessError(_("Meeting Calendar events are managed from the meeting."))
        if self.filtered("community_meeting_id"):
            raise AccessError(_("Meeting Calendar events are managed from the meeting."))
        return super().write(values)

    @api.depends("partner_ids", "privacy", "user_id", "community_meeting_id")
    @api.depends_context("uid")
    def _compute_user_can_edit(self):
        super()._compute_user_can_edit()
        self.filtered("community_meeting_id").user_can_edit = False

    def unlink(self):
        if self.filtered("community_meeting_id"):
            raise AccessError(_("Cancel the meeting to remove its Calendar event."))
        return super().unlink()

    def action_open_community_meeting(self):
        self.ensure_one()
        meeting = self.community_meeting_id
        if not meeting:
            raise AccessError(_("This Calendar event is not linked to a community meeting."))
        meeting.check_access("read")
        return meeting.get_formview_action()

    @api.model_create_multi
    def _community_meetings_calendar_create(self, vals_list):
        """Create integration-owned events through a non-RPC server path."""
        return super().create(vals_list)

    def _community_meetings_calendar_write(self, values):
        """Update integration-owned events through a non-RPC server path."""
        return super().write(values)

    def _community_meetings_calendar_unlink(self):
        """Delete integration-owned events through a non-RPC server path."""
        return super().unlink()

    @api.model
    def _community_meetings_calendar_uninstall_cleanup(self):
        managed = self.sudo().search([("community_meeting_id", "!=", False)])
        return managed._community_meetings_calendar_unlink()

    def _get_ics_file(self):
        files = super()._get_ics_file()
        for event in self.filtered(lambda row: row.community_meeting_id):
            ics = files.get(event.id)
            if not ics:
                continue
            uid_line = b"UID:" + event.community_calendar_uid.encode("ascii")
            if re.search(rb"(?m)^UID:.*$", ics):
                files[event.id] = re.sub(rb"(?m)^UID:.*$", uid_line, ics, count=1)
            else:
                marker = b"BEGIN:VEVENT"
                files[event.id] = ics.replace(marker, marker + b"\r\n" + uid_line, 1)
        return files

    @staticmethod
    def _ical_escape(value):
        value = (value or "").replace("\\", "\\\\")
        value = value.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
        return value.replace(",", "\\,").replace(";", "\\;")

    @staticmethod
    def _ical_fold(line):
        """Fold an iCalendar content line at 75 UTF-8 octets."""
        chunks = []
        current = ""
        current_size = 0
        for character in line:
            size = len(character.encode("utf-8"))
            if current_size + size > 75:
                chunks.append(current)
                current = " "
                current_size = 1
            current += character
            current_size += size
        chunks.append(current)
        return "\r\n".join(chunks)

    def _community_meetings_calendar_cancel_mail(self, removed_partners=None):
        """Queue minimal RFC 5546 cancellation notices for invitees."""
        self.ensure_one()
        if self.env["ir.config_parameter"].sudo().get_param("calendar.block_mail"):
            return self.env["mail.mail"]
        if self.env.context.get("no_mail_to_attendees"):
            return self.env["mail.mail"]

        removed_partners = removed_partners or self.partner_ids
        organizer_email = self.user_id.partner_id.email
        sender = organizer_email or self.env.company.email
        if not sender or not single_email_re.fullmatch(sender):
            return self.env["mail.mail"]

        attendees = (self.partner_ids | removed_partners) - self.user_id.partner_id
        mail_model = self.env["mail.mail"].sudo()
        created_mails = mail_model
        now = fields.Datetime.now().strftime("%Y%m%dT%H%M%SZ")
        start = fields.Datetime.to_datetime(self.start).strftime("%Y%m%dT%H%M%SZ")
        stop = fields.Datetime.to_datetime(self.stop).strftime("%Y%m%dT%H%M%SZ")
        organizer_line = f"ORGANIZER:mailto:{organizer_email}" if organizer_email else None

        for partner in attendees:
            recipient = partner.email or ""
            if not single_email_re.fullmatch(recipient):
                continue
            lines = [
                "BEGIN:VCALENDAR",
                "PRODID:-//Community Meetings//Calendar Integration//EN",
                "VERSION:2.0",
                "CALSCALE:GREGORIAN",
                "METHOD:CANCEL",
                "BEGIN:VEVENT",
                f"UID:{self.community_calendar_uid}",
                "SEQUENCE:1",
                f"DTSTAMP:{now}",
                f"DTSTART:{start}",
                f"DTEND:{stop}",
                f"SUMMARY:{self._ical_escape(self.name)}",
                "STATUS:CANCELLED",
            ]
            if self.location:
                lines.append(f"LOCATION:{self._ical_escape(self.location)}")
            if organizer_line:
                lines.append(organizer_line)
            for attendee in attendees:
                if attendee.email and single_email_re.fullmatch(attendee.email):
                    lines.append(f"ATTENDEE;CN={self._ical_escape(attendee.name)}:mailto:{attendee.email}")
            lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
            ics = "\r\n".join(self._ical_fold(line) for line in lines).encode("utf-8")
            mail = mail_model.create(
                {
                    "email_from": sender,
                    "email_to": recipient,
                    "subject": _("Cancelled: %s", self.name),
                    "body_html": _("The meeting %(meeting)s was cancelled.", meeting=self.name),
                    "auto_delete": True,
                }
            )
            attachment = (
                self.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": "meeting-cancellation.ics",
                        "type": "binary",
                        "datas": base64.b64encode(ics),
                        "mimetype": "text/calendar; method=CANCEL; charset=UTF-8",
                        "res_model": "mail.mail",
                        "res_id": mail.id,
                    }
                )
            )
            mail.attachment_ids = [(4, attachment.id)]
            created_mails |= mail
        return created_mails
