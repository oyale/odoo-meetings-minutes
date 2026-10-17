import calendar
from datetime import timedelta
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CommunityMeetingSeries(models.Model):
    _name = "community.meeting.series"
    _description = "Community Meeting Series"
    _order = "name, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    timezone = fields.Selection([(tz, tz) for tz in pytz.all_timezones], required=True,
                                default=lambda self: self.env.user.tz or "UTC", string="Meeting timezone")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True,
    )
    meeting_kind_id = fields.Many2one(
        "community.meeting.kind", string="Kind", required=True, ondelete="restrict",
        default=lambda self: self.env.ref("community_meetings.kind_operational", raise_if_not_found=False),
    )
    description = fields.Html(translate=True)
    coordinator_user_ids = fields.Many2many(
        "res.users", "community_meeting_series_coordinator_rel",
        "series_id", "user_id", string="Coordinators", check_company=True,
        help="People responsible for preparing the meetings of this series.",
    )
    meeting_ids = fields.One2many("community.meeting", "series_id", string="Meetings")
    carryover_policy = fields.Selection(
        [("review", "Review"), ("automatic", "Automatic"), ("manual", "Manual")],
        default="review", required=True,
        help="Review: unfinished points are offered to the next meeting, which accepts or "
             "discards them. Automatic: unfinished points are carried into the next meeting "
             "without asking. Manual: someone moves each point explicitly.",
    )
    has_minutes_approval_point = fields.Boolean(
        string="Minutes approval point",
        help="Add a 'Minutes Approval' point as the first agenda item of each meeting.",
    )
    has_next_meeting_point = fields.Boolean(
        string="Next meeting point",
        help="Add a 'Next Meeting' point as the last agenda item of each meeting.",
    )
    next_meeting_rule = fields.Selection(
        [
            ("weekday", "Next weekday"),
            ("day_of_month", "Next day of month"),
            ("interval_days", "After N days"),
        ],
        string="Next meeting default",
        help="Default rule used to propose the next meeting date for 'Next Meeting' points.",
    )
    next_meeting_weekday = fields.Selection(
        [
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
    )
    next_meeting_day_of_month = fields.Integer(string="Day of month")
    next_meeting_interval_days = fields.Integer(string="Days")

    def _propose_next_meeting_datetime(self, from_datetime):
        """Compute the proposed next meeting date from the series default."""
        self.ensure_one()
        base = fields.Datetime.to_datetime(from_datetime)
        if not base:
            return False
        zone = pytz.timezone(self.timezone)
        base = pytz.UTC.localize(base).astimezone(zone).replace(tzinfo=None)
        target = None
        if self.next_meeting_rule == "interval_days":
            if not self.next_meeting_interval_days:
                return False
            target = base + timedelta(days=self.next_meeting_interval_days)
        if self.next_meeting_rule == "weekday":
            if self.next_meeting_weekday is False:
                return False
            days_ahead = (int(self.next_meeting_weekday) - base.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target = base + timedelta(days=days_ahead)
        if self.next_meeting_rule == "day_of_month":
            if not self.next_meeting_day_of_month:
                return False
            year, month = base.year, base.month
            if base.day >= self.next_meeting_day_of_month:
                month += 1
                if month > 12:
                    month, year = 1, year + 1
            day = min(self.next_meeting_day_of_month, calendar.monthrange(year, month)[1])
            target = base.replace(year=year, month=month, day=day)
        if target is None:
            return False
        try:
            return zone.localize(target, is_dst=None).astimezone(pytz.UTC).replace(tzinfo=None)
        except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
            raise ValidationError(_("The proposed meeting time is ambiguous or does not exist in the series timezone. Choose another time."))

    @api.constrains("next_meeting_rule", "next_meeting_interval_days", "next_meeting_day_of_month")
    def _check_next_meeting_rule(self):
        for series in self:
            if series.next_meeting_rule == "interval_days" and series.next_meeting_interval_days <= 0:
                raise ValidationError(_("The interval must be positive."))
            if series.next_meeting_rule == "day_of_month" and not 1 <= series.next_meeting_day_of_month <= 31:
                raise ValidationError(_("Choose a day of month between 1 and 31."))

    def _proposed_next_meeting_datetime(self):
        """Date agreed in the last meeting, else the series rule."""
        self.ensure_one()
        meetings = self.env["community.meeting"].search([
            ("series_id", "=", self.id), ("state", "!=", "cancelled"),
        ], order="start_datetime desc, id desc")
        for meeting in meetings:
            agreed = meeting.agenda_item_ids.filtered(
                lambda item: item.kind == "next_meeting" and item.next_meeting_datetime
            )
            if agreed:
                return agreed[:1].next_meeting_datetime
        last = meetings[:1]
        if last and last.start_datetime:
            return self._propose_next_meeting_datetime(last.start_datetime)
        return False

    def action_new_meeting(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return {
            "type": "ir.actions.act_window",
            "name": _("New Meeting in %(series)s", series=self.name),
            "res_model": "community.meeting",
            "view_mode": "form",
            "views": [(self.env.ref("community_meetings.view_community_meeting_form").id, "form")],
            "target": "current",
            "context": {
                **self.env.context,
                "default_series_id": self.id,
                "default_company_id": self.company_id.id,
                "default_meeting_kind_id": self.meeting_kind_id.id,
            },
        }

    _sql_constraints = [
        ("name_company_unique", "unique(company_id, name)", "Series names must be unique per company."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("Only meeting editors can create a meeting series."))
        for vals in vals_list:
            coordinators = vals.get("coordinator_user_ids", [])
            commands = coordinators if isinstance(coordinators, list) else []
            if not self.env.user.has_group("community_meetings.group_meeting_manager") and not commands:
                vals["coordinator_user_ids"] = [(4, self.env.uid)]
        return super().create(vals_list)

    def write(self, vals):
        if "company_id" in vals and any(series.company_id.id != vals["company_id"] for series in self):
            raise UserError(_("A meeting series cannot be moved to another company."))
        if not self.env.user.has_group("community_meetings.group_meeting_manager"):
            if any(self.env.user not in series.coordinator_user_ids for series in self):
                raise UserError(_("Only a series coordinator or meeting manager can edit this series."))
        if "meeting_kind_id" in vals and self.env["community.meeting"].sudo().search_count(
            [("series_id", "in", self.ids)]
        ):
            raise UserError(_("The kind of a series with meetings cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if any(self.env["community.meeting"].search_count([("series_id", "=", series.id)]) for series in self):
            raise ValidationError(_("A series with meetings cannot be deleted."))
        return super().unlink()
