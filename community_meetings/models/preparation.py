from string import Formatter
from typing import ClassVar

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Company(models.Model):
    _inherit = "res.company"

    meeting_estimated_minutes = fields.Integer(
        string="Default point estimate (minutes)",
        default=0,
        help="Default estimated duration applied to new points; a series can override it.",
    )
    meeting_coordinator_label = fields.Char(
        string="Coordination role name",
        default="Organizer",
    )
    meeting_secretary_label = fields.Char(
        string="Secretary role name",
        default="Minutes secretary",
    )
    meeting_time_tracking = fields.Boolean(
        string="Track meeting and point time",
        default=True,
        help="Show start/pause controls and point timers in the live meeting; "
        "records actual durations. A series can override it.",
    )
    meeting_add_point_policy = fields.Selection(
        [
            ("draft", "Draft only"),
            ("scheduled", "Before it starts"),
            ("ongoing", "While it runs"),
        ],
        string="Add points until",
        default="ongoing",
        required=True,
        help="Last moment when new points can be added to a meeting: only while it is a "
        "draft, until it starts, or while it runs. A series can override it.",
    )
    meeting_reorder_point_policy = fields.Selection(
        [
            ("draft", "Draft only"),
            ("scheduled", "Before it starts"),
            ("ongoing", "While it runs"),
        ],
        string="Reorder agenda points until",
        default="ongoing",
        required=True,
        help=(
            "Last moment when agenda points can be reordered: only while the meeting is a draft, "
            "until it starts, or while it runs. A series can override it."
        ),
    )


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    meeting_estimated_minutes = fields.Integer(related="company_id.meeting_estimated_minutes", readonly=False)
    meeting_coordinator_label = fields.Char(related="company_id.meeting_coordinator_label", readonly=False)
    meeting_secretary_label = fields.Char(related="company_id.meeting_secretary_label", readonly=False)
    meeting_time_tracking = fields.Boolean(related="company_id.meeting_time_tracking", readonly=False)
    meeting_add_point_policy = fields.Selection(related="company_id.meeting_add_point_policy", readonly=False)
    meeting_reorder_point_policy = fields.Selection(related="company_id.meeting_reorder_point_policy", readonly=False)


class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"

    duration_hours = fields.Float(string="Default duration", default=1.0, required=True, tracking=True)
    attendee_partner_ids = fields.Many2many("res.partner", string="Default attendees")
    default_estimated_minutes = fields.Integer(
        string="Default point estimate (minutes)",
        help="Overrides the company default for points of this series.",
        tracking=True,
    )
    company_point_estimated_minutes = fields.Integer(
        related="company_id.meeting_estimated_minutes",
        string="Company point estimate",
    )
    coordinator_label = fields.Char(
        string="Coordination role name",
        help="Optional. Overrides the default role name from Settings → Meetings for the meetings of this series.",
        tracking=True,
    )
    secretary_label = fields.Char(
        string="Secretary role name",
        help="Optional. Overrides the default role name from Settings → Meetings for the meetings of this series.",
        tracking=True,
    )
    meeting_name_pattern = fields.Char(
        string="New meeting name pattern",
        default="{date} {series}",
        required=True,
        help="Use {date} for the meeting date (YYYY-MM-DD) and {series} for this series name.",
        tracking=True,
    )
    time_tracking = fields.Selection(
        [("inherit", "Company default"), ("on", "On"), ("off", "Off")],
        default="inherit",
        required=True,
        help="Overrides the company time-tracking setting for meetings of this series.",
        tracking=True,
    )
    company_meeting_time_tracking = fields.Boolean(
        related="company_id.meeting_time_tracking",
        string="Company time tracking",
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
        help="Overrides the company rule for when new points can be added to the meetings of this series.",
        tracking=True,
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
        help="Overrides the company rule for when agenda points can be reordered in this series.",
        tracking=True,
    )

    def _point_estimated_minutes_default(self):
        self.ensure_one()
        return self.default_estimated_minutes or self.company_id.meeting_estimated_minutes or 0

    def _coordinator_label(self):
        self.ensure_one()
        return self.coordinator_label or self.company_id.meeting_coordinator_label or _("Organizer")

    def _secretary_label(self):
        self.ensure_one()
        return self.secretary_label or self.company_id.meeting_secretary_label or _("Minutes secretary")

    @api.constrains("meeting_name_pattern")
    def _check_meeting_name_pattern(self):
        for series in self:
            try:
                fields_in_pattern = {
                    field_name
                    for _, field_name, format_spec, conversion in Formatter().parse(series.meeting_name_pattern or "")
                    if field_name is not None and (format_spec or conversion or field_name not in {"date", "series"})
                }
            except ValueError as error:
                raise ValidationError(_("Invalid meeting name pattern: %(error)s", error=str(error))) from error
            if fields_in_pattern:
                raise ValidationError(_("Only the {date} and {series} placeholders are supported."))

    def _format_meeting_name(self, start_datetime):
        self.ensure_one()
        start = fields.Datetime.to_datetime(start_datetime)
        date_value = fields.Datetime.context_timestamp(self, start).strftime("%Y-%m-%d") if start else ""
        try:
            return (self.meeting_name_pattern or "{date} {series}").format(date=date_value, series=self.name).strip()
        except (KeyError, ValueError) as error:
            raise ValidationError(_("Invalid meeting name pattern: %(error)s", error=str(error))) from error

    @api.constrains("duration_hours")
    def _check_duration(self):
        if any(s.duration_hours <= 0 for s in self):
            raise ValidationError(_("Duration must be positive."))

    def action_new_meeting(self):
        self.ensure_one()
        context = {"default_series_id": self.id}
        proposed = self._proposed_next_meeting_datetime()
        if proposed:
            context["default_start_datetime"] = proposed
        return self.env["community.meeting.create.wizard"]._open(context)

    def action_propose_point(self):
        self.ensure_one()
        return self.env["community.meeting.point.wizard"]._open(
            {
                "default_propose": True,
                "default_proposal_series_id": self.id,
            }
        )


class Meeting(models.Model):
    _inherit = "community.meeting"

    duration_hours = fields.Float(string="Approximate duration", default=1.0, required=True)
    coordinator_role_label = fields.Char(compute="_compute_role_labels")
    secretary_role_label = fields.Char(compute="_compute_role_labels")

    @api.depends("series_id", "company_id")
    def _compute_role_labels(self):
        for meeting in self:
            if meeting.series_id:
                meeting.coordinator_role_label = meeting.series_id._coordinator_label()
                meeting.secretary_role_label = meeting.series_id._secretary_label()
            else:
                meeting.coordinator_role_label = meeting.company_id.meeting_coordinator_label or _("Organizer")
                meeting.secretary_role_label = meeting.company_id.meeting_secretary_label or _("Minutes secretary")

    duration_minutes = fields.Integer(compute="_compute_duration_minutes", store=True)
    agenda_minutes = fields.Integer(compute="_compute_agenda_minutes")
    agenda_over_budget = fields.Boolean(compute="_compute_agenda_minutes")
    creation_token = fields.Char(copy=False, index=True)
    pending_carryover_ids = fields.One2many(
        "community.meeting.carryover",
        compute="_compute_pending_carryovers",
        groups="community_meetings.group_meeting_editor",
    )

    @api.depends("incoming_carryover_ids.status")
    def _compute_pending_carryovers(self):
        for meeting in self:
            meeting.pending_carryover_ids = self.env["community.meeting.carryover"].search(
                [
                    ("destination_meeting_id", "=", meeting.id),
                    ("status", "in", ["pending", "proposed"]),
                ]
            )

    _sql_constraints: ClassVar[list[tuple[str, str, str]]] = [
        (
            "creation_token_unique",
            "unique(creation_token)",
            "This meeting has already been created.",
        )
    ]

    @api.depends("duration_hours")
    def _compute_duration_minutes(self):
        for meeting in self:
            meeting.duration_minutes = round(meeting.duration_hours * 60)

    @api.depends("agenda_item_ids.estimated_minutes", "duration_minutes")
    def _compute_agenda_minutes(self):
        for meeting in self:
            meeting.agenda_minutes = sum(meeting.agenda_item_ids.mapped("estimated_minutes"))
            meeting.agenda_over_budget = meeting.agenda_minutes > meeting.duration_minutes

    @api.constrains("duration_hours")
    def _check_duration(self):
        if any(m.duration_hours <= 0 or m.duration_hours > 168 for m in self):
            raise ValidationError(_("Duration must be between one minute and one week."))

    @api.onchange("series_id")
    def _onchange_series_defaults(self):
        if self.series_id:
            self.duration_hours = self.series_id.duration_hours
            self.attendee_partner_ids = self.series_id.attendee_partner_ids

    @api.onchange("start_datetime", "duration_hours")
    def _onchange_start_datetime(self):
        if self.start_datetime:
            self.end_datetime = fields.Datetime.add(self.start_datetime, minutes=round(self.duration_hours * 60))

    @api.onchange("end_datetime")
    def _onchange_end_duration(self):
        if self.start_datetime and self.end_datetime:
            self.duration_hours = (self.end_datetime - self.start_datetime).total_seconds() / 3600

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            series = self.env["community.meeting.series"].browse(vals.get("series_id"))
            if series:
                series.check_access("read")
                vals.setdefault("duration_hours", series.duration_hours)
                vals.setdefault("attendee_partner_ids", [(6, 0, series.attendee_partner_ids.ids)])
            start = fields.Datetime.to_datetime(vals.get("start_datetime"))
            end = fields.Datetime.to_datetime(vals.get("end_datetime"))
            if start and end and "duration_hours" not in vals:
                vals["duration_hours"] = (end - start).total_seconds() / 3600
            if start:
                vals["end_datetime"] = fields.Datetime.add(start, minutes=round(vals.get("duration_hours", 1.0) * 60))
            prepared.append(vals)
        meetings = super().create(prepared)
        meetings._add_structural_points()
        return meetings

    def _add_structural_points(self):
        """Add series-configured structural points (minutes approval first,
        next meeting last) when a meeting is created for a series."""
        for meeting in self:
            series = meeting.series_id
            if not series:
                continue
            meeting._ensure_minutes_approval_point()
            if series.has_next_meeting_point and not meeting.agenda_item_ids.filtered(
                lambda item: item.agenda_type_id.behavior == "next_meeting"
            ):
                proposed = (
                    series._propose_next_meeting_datetime(meeting.start_datetime) if meeting.start_datetime else False
                )
                meeting.agenda_item_ids.create(
                    {
                        "meeting_id": meeting.id,
                        "name": _("Next meeting"),
                        "kind": "next_meeting",
                        "sequence": 1000,
                        "estimated_minutes": 5,
                        "next_meeting_datetime": proposed,
                        "presenter_partner_id": False,
                    }
                )

    def _ensure_minutes_approval_point(self):
        for meeting in self:
            if not meeting.series_id.has_minutes_approval_point:
                continue
            meeting._lock_live_workflow()
            meeting.invalidate_recordset(["agenda_item_ids"])
            if meeting.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval"):
                continue
            pending = meeting.get_pending_minutes_for_approval()
            self.env["community.meeting.agenda.item"].create(
                {
                    "meeting_id": meeting.id,
                    "name": _("Approve previous minutes"),
                    "kind": "minutes_approval",
                    "sequence": -1,
                    "estimated_minutes": 5 * len(pending),
                    "presenter_partner_id": False,
                }
            )

    def write(self, vals):
        for meeting in self:
            values = dict(vals)
            start = fields.Datetime.to_datetime(values.get("start_datetime", meeting.start_datetime))
            if "end_datetime" in values and "duration_hours" not in values and start and values["end_datetime"]:
                values["duration_hours"] = (
                    fields.Datetime.to_datetime(values["end_datetime"]) - start
                ).total_seconds() / 3600
            if start and {
                "start_datetime",
                "duration_hours",
                "end_datetime",
            }.intersection(values):
                values["end_datetime"] = fields.Datetime.add(
                    start,
                    minutes=round(values.get("duration_hours", meeting.duration_hours) * 60),
                )
            super(Meeting, meeting).write(values)
            if "series_id" in values:
                meeting.agenda_item_ids.topic_id._set_series(meeting.series_id)
                meeting._ensure_minutes_approval_point()
        return True

    def unlink(self):
        self.check_access("unlink")
        actions = self.mapped("action_ids")
        for topic in actions.topic_id.sorted("id"):
            topic._lock_workflow()
        external = (
            self.env["community.meeting.agenda.item"]
            .sudo()
            .search(
                [
                    ("topic_id", "in", actions.topic_id.ids),
                    ("meeting_id", "not in", self.ids),
                ]
            )
        )
        if external and any(a.state != "cancelled" and a.topic_id in external.topic_id for a in actions):
            raise ValidationError(
                _("This meeting contains tasks for points used elsewhere. Keep their origin for task history.")
            )
        external._validate_followup_removal(actions)
        return super().unlink()

    def action_cancel(self):
        result = super().action_cancel()
        for meeting in self:
            for source in meeting.incoming_carryover_ids.filtered(lambda t: t.status == "accepted").mapped(
                "origin_agenda_item_id"
            ):
                source._restore_review()
        return result

    def action_refresh_carryovers(self):
        self.check_access("write")
        self.env["community.meeting.carryover"]._process_new_meetings(self)
        return True

    def action_add_point(self):
        self.ensure_one()
        if not self.add_point_allowed:
            raise ValidationError(_("New points cannot be added to this meeting anymore."))
        return self.env["community.meeting.point.wizard"]._open({"default_meeting_id": self.id})

    def action_add_point_live(self):
        self.ensure_one()
        if not self.add_point_allowed:
            raise ValidationError(_("New points cannot be added to this meeting anymore."))
        return self.env["community.meeting.point.wizard"]._open({"default_meeting_id": self.id, "from_live": True})

    @api.model
    def action_create_guided(self):
        return self.env["community.meeting.create.wizard"]._open({})

    @api.model
    def _carryover_candidates(self, series, start):
        if not series or not start or series.carryover_policy == "manual":
            return self.env["community.meeting.agenda.item"]
        series.check_access("read")
        sources = self.env["community.meeting.agenda.item"].search(
            [
                ("meeting_id.series_id", "=", series.id),
                ("meeting_id.company_id", "=", series.company_id.id),
                ("meeting_id.start_datetime", "<", start),
                ("meeting_id.state", "!=", "cancelled"),
            ],
            order="id desc",
        )
        # Completed actions still count: the next meeting may review them.
        active_followup_items = set(
            self.env["community.meeting.action"]
            .search(
                [
                    ("agenda_item_id", "in", sources.ids),
                    ("state", "!=", "cancelled"),
                ]
            )
            .mapped("agenda_item_id")
            .ids
        )
        already_continued = set(
            self.env["community.meeting.carryover"]
            .search(
                [
                    ("origin_agenda_item_id", "in", sources.ids),
                    ("status", "=", "accepted"),
                ]
            )
            .filtered(lambda transfer: transfer.destination_meeting_id.state != "cancelled")
            .mapped("origin_agenda_item_id")
            .ids
        )
        sources = sources.filtered(
            lambda source: (
                source.id not in already_continued
                and (
                    source.review_next_meeting
                    or source.id in active_followup_items
                    # Project is optional, so core must not depend on its fields.
                    or ("project_task_ids" in source._fields and source.project_task_ids)
                )
            )
        )
        # Keep the most recent occurrence per point; pending requests survive gaps.
        result = self.env["community.meeting.agenda.item"]
        seen = set()
        for source in sorted(
            sources,
            key=lambda i: (i.meeting_id.start_datetime, i.meeting_id.id, i.id),
            reverse=True,
        ):
            if source.topic_id.id not in seen:
                seen.add(source.topic_id.id)
                result |= source
        return result


class ContinuingPoints(models.Model):
    _inherit = "community.meeting.carryover"

    def _materialize(self, destination, automatic=False):
        item = super()._materialize(destination, automatic=automatic)
        if self.origin_agenda_item_id:
            self.origin_agenda_item_id._consume_review()
        return item

    def action_dismiss(self, reason=False):
        result = super().action_dismiss(reason)
        for source in self.mapped("origin_agenda_item_id"):
            source._consume_review()
        return result
