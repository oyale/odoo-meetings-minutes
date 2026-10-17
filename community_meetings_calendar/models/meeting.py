import uuid

from odoo import _, Command, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class CommunityMeeting(models.Model):
    _inherit = "community.meeting"

    calendar_event_ids = fields.One2many(
        "calendar.event", "community_meeting_id", string="Calendar Event", copy=False
    )

    @staticmethod
    def _calendar_managed_fields():
        return {
            "name",
            "start_datetime",
            "end_datetime",
            "location",
            "attendee_partner_ids",
            "organizer_id",
            "secretary_id",
        }

    def _check_calendar_attendees(self):
        user_model = self.env["res.users"].sudo()
        for meeting in self:
            partners = meeting._calendar_attendee_partner_ids()
            linked_users = user_model.search([
                ("partner_id", "in", partners.ids),
                ("active", "=", True),
                ("share", "=", False),
            ])
            users_by_partner = {}
            for user in linked_users:
                users_by_partner.setdefault(user.partner_id.id, self.env["res.users"])
                users_by_partner[user.partner_id.id] |= user
            for partner in partners:
                eligible = users_by_partner.get(partner.id, self.env["res.users"])
                if not eligible or not any(meeting.company_id in user.company_ids for user in eligible):
                    raise ValidationError(_(
                        "Calendar invitees must be active internal users in the meeting company."
                    ))

    def _calendar_attendee_partner_ids(self):
        self.ensure_one()
        partners = self.attendee_partner_ids | self.organizer_id.partner_id
        if self.secretary_id:
            partners |= self.secretary_id.partner_id
        return partners

    def _calendar_event_values(self, event=None):
        self.ensure_one()
        values = {
            "name": self.name,
            "start": self.start_datetime,
            "stop": self.end_datetime,
            "location": self.location or False,
            "description": False,
            "user_id": self.organizer_id.id,
            "partner_ids": [Command.set(self._calendar_attendee_partner_ids().ids)],
            "privacy": "private",
            "alarm_ids": [Command.clear()],
            "recurrency": False,
            "activity_ids": [Command.clear()],
            "res_model_id": self.env["ir.model"]._get_id("community.meeting"),
            "res_id": self.id,
            "community_meeting_id": self.id,
        }
        if not event:
            values["community_calendar_uid"] = "%s@community-meetings" % uuid.uuid4().hex
            return values

        scalar_fields = (
            "name", "start", "stop", "location", "user_id", "privacy", "description",
            "recurrency", "res_model_id", "res_id", "community_meeting_id",
        )
        updates = {
            field_name: values[field_name]
            for field_name in scalar_fields
            if (
                getattr(event, field_name).id
                if hasattr(getattr(event, field_name), "id")
                else getattr(event, field_name)
            ) != values[field_name]
        }
        if set(event.partner_ids.ids) != set(self._calendar_attendee_partner_ids().ids):
            updates["partner_ids"] = values["partner_ids"]
        return updates

    def _lock_calendar_event(self):
        for meeting in self.sorted("id"):
            self.env.cr.execute(
                "SELECT id FROM community_meeting WHERE id = %s FOR UPDATE", [meeting.id]
            )
        self.invalidate_recordset([
            "state", "start_datetime", "end_datetime", "actual_start_datetime",
            "organizer_id", "secretary_id", "attendee_partner_ids", "calendar_event_ids",
        ])

    def _ensure_calendar_end_datetime(self):
        for meeting in self:
            if not meeting.end_datetime and meeting.start_datetime:
                duration = meeting.series_id.duration_hours if meeting.series_id else 1.0
                end = fields.Datetime.add(meeting.start_datetime, hours=duration or 1.0)
                super(CommunityMeeting, meeting).write({"end_datetime": end})
            if not meeting.start_datetime or not meeting.end_datetime or meeting.end_datetime <= meeting.start_datetime:
                raise ValidationError(_("The meeting end must be after its start before scheduling."))

    def _sync_calendar_event(self):
        """Sync events; callers must hold the meeting row lock."""
        for meeting in self:
            if meeting.state != "scheduled":
                continue
            meeting._check_calendar_attendees()
            event = meeting.calendar_event_ids
            owner_env = self.env["calendar.event"].with_user(meeting.organizer_id).sudo()
            if event:
                values = meeting._calendar_event_values(event)
                if not values:
                    continue
                old_partners = event.partner_ids
                event.with_user(meeting.organizer_id).sudo()._community_meetings_calendar_write(values)
                event.invalidate_recordset(["partner_ids", "attendee_ids", "name", "start", "stop", "location"])
                removed = old_partners - event.partner_ids
                if removed:
                    event._community_meetings_calendar_cancel_mail(removed)
            else:
                owner_env._community_meetings_calendar_create([meeting._calendar_event_values()])

    def _cancel_calendar_event(self):
        """Cancel events; callers must hold the meeting row lock."""
        for meeting in self:
            event = meeting.calendar_event_ids.sudo()
            if not event:
                continue
            event._community_meetings_calendar_cancel_mail(event.partner_ids)
            event._community_meetings_calendar_unlink()

    def write(self, values):
        changed = self._calendar_managed_fields().intersection(values)
        if changed:
            self._lock_calendar_event()
        result = super().write(values)
        if changed:
            self.filtered(lambda meeting: meeting.state == "scheduled")._sync_calendar_event()
        return result

    def action_schedule(self):
        self._lock_calendar_event()
        for meeting in self:
            meeting.check_access("write")
        if not (
            self.env.user.has_group("community_meetings.group_meeting_editor")
            or self.env.user.has_group("community_meetings.group_meeting_manager")
        ):
            raise AccessError(_("You are not allowed to schedule meetings."))
        self._ensure_calendar_end_datetime()
        result = super().action_schedule()
        self._sync_calendar_event()
        return result

    def action_cancel(self):
        self._lock_calendar_event()
        result = super().action_cancel()
        self._cancel_calendar_event()
        return result

    @api.constrains("attendee_partner_ids", "organizer_id", "secretary_id", "company_id")
    def _constrain_calendar_attendees(self):
        self._check_calendar_attendees()
