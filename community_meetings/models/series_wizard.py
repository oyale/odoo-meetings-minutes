import pytz
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MeetingSeriesWizard(models.TransientModel):
    _name = "community.meeting.series.wizard"
    _description = "Create a Meeting Series"

    step = fields.Selection(
        [
            ("basics", "Series"),
            ("schedule", "Schedule"),
            ("structure", "Structure"),
            ("review", "Review"),
        ],
        default="basics",
        required=True,
    )
    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)
    coordinator_user_ids = fields.Many2many(
        "res.users", "community_meeting_series_wizard_coordinator_rel"
    )
    carryover_policy = fields.Selection(
        [("review", "Review"), ("automatic", "Automatic"), ("manual", "Manual")],
        default="review",
        required=True,
    )
    timezone = fields.Selection(
        [(tz, tz) for tz in pytz.all_timezones],
        required=True,
        default=lambda self: self.env.user.tz or "UTC",
    )
    duration_hours = fields.Float(string="Default duration", default=1.0, required=True)
    attendee_partner_ids = fields.Many2many(
        "res.partner", "community_meeting_series_wizard_attendee_rel"
    )
    meeting_name_pattern = fields.Char(default="{date} {series}", required=True)
    has_minutes_approval_point = fields.Boolean()
    has_next_meeting_point = fields.Boolean()
    next_meeting_rule = fields.Selection(
        [("weekday", "Next weekday"), ("day_of_month", "Next day of month"), ("interval_days", "After N days")]
    )
    next_meeting_weekday = fields.Selection(
        [("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"), ("3", "Thursday"),
         ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday")]
    )
    next_meeting_day_of_month = fields.Integer()
    next_meeting_interval_days = fields.Integer()
    created_series_id = fields.Many2one("community.meeting.series", readonly=True)

    @api.model
    def _open(self, context):
        return {
            "type": "ir.actions.act_window",
            "name": _("New Meeting Series"),
            "res_model": self._name,
            "views": [(self.env.ref("community_meetings.view_series_wizard").id, "form")],
            "target": "new",
            "context": context,
        }

    def _reload(self):
        return {**self._open({}), "res_id": self.id}

    def action_next(self):
        self.ensure_one()
        if self.step == "basics" and not (self.name or "").strip():
            raise ValidationError(_("Enter a name for the series."))
        if self.step == "schedule" and self.duration_hours <= 0:
            raise ValidationError(_("Duration must be positive."))
        steps = ["basics", "schedule", "structure", "review"]
        self.step = steps[min(steps.index(self.step) + 1, len(steps) - 1)]
        return self._reload()

    def action_back(self):
        self.ensure_one()
        steps = ["basics", "schedule", "structure", "review"]
        self.step = steps[max(0, steps.index(self.step) - 1)]
        return self._reload()

    def action_finish(self):
        self.ensure_one()
        self.check_access("write")
        self.env.cr.execute(
            "SELECT id FROM community_meeting_series_wizard WHERE id=%s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["created_series_id"])
        if not self.created_series_id:
            if not (self.name or "").strip():
                raise ValidationError(_("Enter a name for the series."))
            values = {
                "name": self.name,
                "company_id": self.company_id.id,
                "active": self.active,
                "carryover_policy": self.carryover_policy,
                "timezone": self.timezone,
                "duration_hours": self.duration_hours,
                "attendee_partner_ids": [(6, 0, self.attendee_partner_ids.ids)],
                "meeting_name_pattern": self.meeting_name_pattern,
                "has_minutes_approval_point": self.has_minutes_approval_point,
                "has_next_meeting_point": self.has_next_meeting_point,
                "next_meeting_rule": self.next_meeting_rule,
                "next_meeting_weekday": self.next_meeting_weekday,
                "next_meeting_day_of_month": self.next_meeting_day_of_month,
                "next_meeting_interval_days": self.next_meeting_interval_days,
            }
            # Only send coordinators when the user picked some, so the series
            # default (creator as coordinator) keeps the record rule satisfied.
            if self.coordinator_user_ids:
                values["coordinator_user_ids"] = [(6, 0, self.coordinator_user_ids.ids)]
            self.created_series_id = self.env["community.meeting.series"].create(values)
        return {
            "type": "ir.actions.act_window",
            "name": _("Meeting Series"),
            "res_model": "community.meeting.series",
            "res_id": self.created_series_id.id,
            "views": [(False, "form")],
            "target": "current",
        }
