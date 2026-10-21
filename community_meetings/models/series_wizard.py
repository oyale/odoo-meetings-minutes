import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"

    @api.model
    def action_create_series(self):
        return self.env["community.meeting.series.wizard"]._open({})


class MeetingSeriesWizard(models.TransientModel):
    _name = "community.meeting.series.wizard"
    _description = "Create a Meeting Series"

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        # Seed the policy controls explicitly: the structure step may not be
        # mounted when the form first asks for its defaults, and uninitialized
        # toggles would be saved as series-specific overrides when advancing.
        company = self.env["res.company"].browse(values.get("company_id") or self.env.company.id)
        time_tracking = values.get("time_tracking", "inherit")
        add_point_policy = values.get("add_point_policy", "inherit")
        reorder_point_policy = values.get("reorder_point_policy", "inherit")
        if "use_company_time_tracking" in fields_list:
            values["use_company_time_tracking"] = time_tracking == "inherit"
        if "time_tracking_override" in fields_list:
            values["time_tracking_override"] = (
                ("on" if company.meeting_time_tracking else "off") if time_tracking == "inherit" else time_tracking
            )
        if "use_company_add_point_policy" in fields_list:
            values["use_company_add_point_policy"] = add_point_policy == "inherit"
        if "add_point_policy_override" in fields_list:
            values["add_point_policy_override"] = (
                company.meeting_add_point_policy if add_point_policy == "inherit" else add_point_policy
            )
        if "use_company_reorder_point_policy" in fields_list:
            values["use_company_reorder_point_policy"] = reorder_point_policy == "inherit"
        if "reorder_point_policy_override" in fields_list:
            values["reorder_point_policy_override"] = (
                company.meeting_reorder_point_policy if reorder_point_policy == "inherit" else reorder_point_policy
            )
        if "use_company_estimated_minutes" in fields_list:
            values["use_company_estimated_minutes"] = not values.get("default_estimated_minutes", 0)
        return values

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
    name = fields.Char(string="Series name", required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    coordinator_user_ids = fields.Many2many(
        "res.users",
        "community_meeting_series_wizard_coordinator_rel",
        string="Coordinators",
    )
    carryover_policy = fields.Selection(
        [("review", "Review"), ("automatic", "Automatic"), ("manual", "Manual")],
        default="review",
        required=True,
        string="Unfinished points",
    )
    timezone = fields.Selection(
        [(tz, tz) for tz in pytz.all_timezones],
        required=True,
        default=lambda self: self.env.user.tz or "UTC",
        string="Time zone",
    )
    duration_hours = fields.Float(string="Default duration", default=1.0, required=True)
    attendee_partner_ids = fields.Many2many(
        "res.partner",
        "community_meeting_series_wizard_attendee_rel",
        string="Usual attendees",
    )
    meeting_name_pattern = fields.Char(string="Meeting title pattern", default="{date} {series}", required=True)
    has_minutes_approval_point = fields.Boolean(string="Add a minutes approval point")
    has_next_meeting_point = fields.Boolean(string="Add a next meeting point")
    next_meeting_rule = fields.Selection(
        [
            ("weekday", "Next weekday"),
            ("day_of_month", "Next day of month"),
            ("interval_days", "After N days"),
        ],
        string="Suggest the next date by",
    )
    next_meeting_weekday = fields.Selection(
        [
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        string="Weekday",
    )
    next_meeting_day_of_month = fields.Integer(string="Day of month")
    next_meeting_interval_days = fields.Integer(string="Days later")
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

    time_tracking = fields.Selection(
        [("inherit", "Company default"), ("on", "On"), ("off", "Off")],
        default="inherit",
        required=True,
        string="Time tracking",
    )
    use_company_time_tracking = fields.Boolean(
        default=True,
        string="Company time-tracking default",
    )
    time_tracking_override = fields.Selection(
        [("on", "On"), ("off", "Off")],
        compute="_compute_time_tracking_override",
        inverse="_inverse_time_tracking_override",
        string="Time tracking for this series",
    )
    add_point_policy = fields.Selection(
        [
            ("inherit", "Company default"),
            ("draft", "Draft only"),
            ("scheduled", "Before it starts"),
            ("ongoing", "While it runs"),
        ],
        default="inherit",
        required=True,
        string="When points can be added",
    )
    use_company_add_point_policy = fields.Boolean(
        default=True,
        string="Company point-policy default",
    )
    add_point_policy_override = fields.Selection(
        [
            ("draft", "Draft only"),
            ("scheduled", "Before it starts"),
            ("ongoing", "While it runs"),
        ],
        compute="_compute_add_point_policy_override",
        inverse="_inverse_add_point_policy_override",
        string="Adding points for this series",
    )
    reorder_point_policy = fields.Selection(
        [
            ("inherit", "Company default"),
            ("draft", "Draft only"),
            ("scheduled", "Before it starts"),
            ("ongoing", "While it runs"),
        ],
        default="inherit",
        required=True,
        string="When agenda points can be reordered",
    )
    use_company_reorder_point_policy = fields.Boolean(
        default=True,
        string="Company reorder-policy default",
    )
    reorder_point_policy_override = fields.Selection(
        [
            ("draft", "Draft only"),
            ("scheduled", "Before it starts"),
            ("ongoing", "While it runs"),
        ],
        compute="_compute_reorder_point_policy_override",
        inverse="_inverse_reorder_point_policy_override",
        string="Reordering points for this series",
    )
    default_estimated_minutes = fields.Integer(string="Default point estimate (minutes)")
    use_company_estimated_minutes = fields.Boolean(
        compute="_compute_use_company_estimated_minutes",
        inverse="_inverse_use_company_estimated_minutes",
        string="Company default point estimate",
    )

    @api.onchange("use_company_time_tracking")
    def _onchange_use_company_time_tracking(self):
        for wizard in self:
            if wizard.use_company_time_tracking:
                wizard.time_tracking = "inherit"
            elif wizard.time_tracking == "inherit":
                wizard.time_tracking = "on" if wizard.company_id.meeting_time_tracking else "off"

    @api.depends("time_tracking", "company_id.meeting_time_tracking")
    def _compute_time_tracking_override(self):
        for wizard in self:
            wizard.time_tracking_override = (
                wizard.time_tracking
                if wizard.time_tracking != "inherit"
                else "on"
                if wizard.company_id.meeting_time_tracking
                else "off"
            )

    def _inverse_time_tracking_override(self):
        for wizard in self:
            wizard.time_tracking = wizard.time_tracking_override

    @api.onchange("use_company_add_point_policy")
    def _onchange_use_company_add_point_policy(self):
        for wizard in self:
            if wizard.use_company_add_point_policy:
                wizard.add_point_policy = "inherit"
            elif wizard.add_point_policy == "inherit":
                wizard.add_point_policy = wizard.company_id.meeting_add_point_policy

    @api.depends("add_point_policy", "company_id.meeting_add_point_policy")
    def _compute_add_point_policy_override(self):
        for wizard in self:
            wizard.add_point_policy_override = (
                wizard.add_point_policy
                if wizard.add_point_policy != "inherit"
                else wizard.company_id.meeting_add_point_policy
            )

    def _inverse_add_point_policy_override(self):
        for wizard in self:
            wizard.add_point_policy = wizard.add_point_policy_override

    @api.onchange("use_company_reorder_point_policy")
    def _onchange_use_company_reorder_point_policy(self):
        for wizard in self:
            if wizard.use_company_reorder_point_policy:
                wizard.reorder_point_policy = "inherit"
            elif wizard.reorder_point_policy == "inherit":
                wizard.reorder_point_policy = wizard.company_id.meeting_reorder_point_policy

    @api.depends("reorder_point_policy", "company_id.meeting_reorder_point_policy")
    def _compute_reorder_point_policy_override(self):
        for wizard in self:
            wizard.reorder_point_policy_override = (
                wizard.reorder_point_policy
                if wizard.reorder_point_policy != "inherit"
                else wizard.company_id.meeting_reorder_point_policy
            )

    def _inverse_reorder_point_policy_override(self):
        for wizard in self:
            wizard.reorder_point_policy = wizard.reorder_point_policy_override

    @api.depends("default_estimated_minutes")
    def _compute_use_company_estimated_minutes(self):
        for wizard in self:
            wizard.use_company_estimated_minutes = not wizard.default_estimated_minutes

    def _inverse_use_company_estimated_minutes(self):
        for wizard in self:
            if wizard.use_company_estimated_minutes:
                wizard.default_estimated_minutes = 0
            elif not wizard.default_estimated_minutes:
                wizard.default_estimated_minutes = wizard.company_id.meeting_estimated_minutes or 5

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
                "time_tracking": self.time_tracking,
                "add_point_policy": self.add_point_policy,
                "reorder_point_policy": self.reorder_point_policy,
                "default_estimated_minutes": self.default_estimated_minutes,
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
