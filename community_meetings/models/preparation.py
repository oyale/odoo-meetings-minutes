from string import Formatter

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"

    duration_hours = fields.Float(string="Default duration", default=1.0, required=True)
    attendee_partner_ids = fields.Many2many("res.partner", string="Default attendees")
    meeting_name_pattern = fields.Char(
        string="New meeting name pattern",
        default="{date} {series}",
        required=True,
        help="Use {date} for the meeting date (YYYY-MM-DD) and {series} for this series name.",
    )

    @api.constrains("meeting_name_pattern")
    def _check_meeting_name_pattern(self):
        for series in self:
            try:
                fields_in_pattern = {
                    field_name
                    for _, field_name, format_spec, conversion in Formatter().parse(
                        series.meeting_name_pattern or ""
                    )
                    if field_name is not None
                    and (format_spec or conversion or field_name not in {"date", "series"})
                }
            except ValueError as error:
                raise ValidationError(
                    _("Invalid meeting name pattern: %(error)s", error=str(error))
                ) from error
            if fields_in_pattern:
                raise ValidationError(
                    _("Only the {date} and {series} placeholders are supported.")
                )

    def _format_meeting_name(self, start_datetime):
        self.ensure_one()
        start = fields.Datetime.to_datetime(start_datetime)
        date_value = (
            fields.Datetime.context_timestamp(self, start).strftime("%Y-%m-%d")
            if start
            else ""
        )
        try:
            return (self.meeting_name_pattern or "{date} {series}").format(
                date=date_value, series=self.name
            ).strip()
        except (KeyError, ValueError) as error:
            raise ValidationError(
                _("Invalid meeting name pattern: %(error)s", error=str(error))
            ) from error

    @api.constrains("duration_hours")
    def _check_duration(self):
        if any(s.duration_hours <= 0 for s in self):
            raise ValidationError(_("Duration must be positive."))

    def action_new_meeting(self):
        self.ensure_one()
        return self.env["community.meeting.create.wizard"]._open(
            {"default_series_id": self.id}
        )


class Meeting(models.Model):
    _inherit = "community.meeting"

    duration_hours = fields.Float(
        string="Approximate duration", default=1.0, required=True
    )
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
            meeting.pending_carryover_ids = self.env[
                "community.meeting.carryover"
            ].search(
                [
                    ("destination_meeting_id", "=", meeting.id),
                    ("status", "in", ["pending", "proposed"]),
                ]
            )

    _sql_constraints = [
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
            meeting.agenda_minutes = sum(
                meeting.agenda_item_ids.mapped("estimated_minutes")
            )
            meeting.agenda_over_budget = (
                meeting.agenda_minutes > meeting.duration_minutes
            )

    @api.constrains("duration_hours")
    def _check_duration(self):
        if any(m.duration_hours <= 0 or m.duration_hours > 168 for m in self):
            raise ValidationError(
                _("Duration must be between one minute and one week.")
            )

    @api.onchange("series_id")
    def _onchange_series_defaults(self):
        if self.series_id:
            self.duration_hours = self.series_id.duration_hours
            self.attendee_partner_ids = self.series_id.attendee_partner_ids

    @api.onchange("start_datetime", "duration_hours")
    def _onchange_start_datetime(self):
        if self.start_datetime:
            self.end_datetime = fields.Datetime.add(
                self.start_datetime, minutes=round(self.duration_hours * 60)
            )

    @api.onchange("end_datetime")
    def _onchange_end_duration(self):
        if self.start_datetime and self.end_datetime:
            self.duration_hours = (
                self.end_datetime - self.start_datetime
            ).total_seconds() / 3600

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            series = self.env["community.meeting.series"].browse(vals.get("series_id"))
            if series:
                series.check_access("read")
                vals.setdefault("duration_hours", series.duration_hours)
                vals.setdefault(
                    "attendee_partner_ids", [(6, 0, series.attendee_partner_ids.ids)]
                )
            start = fields.Datetime.to_datetime(vals.get("start_datetime"))
            end = fields.Datetime.to_datetime(vals.get("end_datetime"))
            if start and end and "duration_hours" not in vals:
                vals["duration_hours"] = (end - start).total_seconds() / 3600
            if start:
                vals["end_datetime"] = fields.Datetime.add(
                    start, minutes=round(vals.get("duration_hours", 1.0) * 60)
                )
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        for meeting in self:
            values = dict(vals)
            start = fields.Datetime.to_datetime(
                values.get("start_datetime", meeting.start_datetime)
            )
            if (
                "end_datetime" in values
                and "duration_hours" not in values
                and start
                and values["end_datetime"]
            ):
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
                    minutes=round(
                        values.get("duration_hours", meeting.duration_hours) * 60
                    ),
                )
            if "series_id" in values and meeting.actual_start_datetime:
                raise ValidationError(
                    _("The series cannot change after the meeting starts.")
                )
            super(Meeting, meeting).write(values)
            if "series_id" in values:
                meeting.agenda_item_ids.topic_id._set_series(meeting.series_id)
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
        if external and any(
            a.state != "cancelled" and a.topic_id in external.topic_id for a in actions
        ):
            raise ValidationError(
                _(
                    "This meeting contains tasks for points used elsewhere. Keep their origin for task history."
                )
            )
        external._validate_followup_removal(actions)
        return super().unlink()

    def action_cancel(self):
        result = super().action_cancel()
        for meeting in self:
            for source in meeting.incoming_carryover_ids.filtered(
                lambda t: t.status == "accepted"
            ).mapped("origin_agenda_item_id"):
                source._restore_review()
        return result

    def action_refresh_carryovers(self):
        self.check_access("write")
        self.env["community.meeting.carryover"]._process_new_meetings(self)
        return True

    def action_add_point(self):
        self.ensure_one()
        return self.env["community.meeting.point.wizard"]._open(
            {"default_meeting_id": self.id}
        )

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
            self.env["community.meeting.action"].search([
                ("agenda_item_id", "in", sources.ids),
                ("state", "!=", "cancelled"),
            ]).mapped("agenda_item_id").ids
        )
        sources = sources.filtered(
            lambda source: source.review_next_meeting
            or source.id in active_followup_items
            # Project is optional, so core must not depend on its fields.
            or ("project_task_ids" in source._fields and source.project_task_ids)
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

    @api.model
    def _process_new_meetings(self, meetings):
        result = super()._process_new_meetings(meetings)
        for meeting in meetings.filtered(
            lambda m: (
                m.series_id
                and m.state in ("draft", "scheduled")
                and not m.actual_start_datetime
            )
        ):
            meeting.check_access("write")
            for source in self.env["community.meeting"]._carryover_candidates(
                meeting.series_id, meeting.start_datetime
            ):
                if source.meeting_id == meeting or self.env[
                    "community.meeting.agenda.item"
                ].search_count(
                    [
                        ("meeting_id", "=", meeting.id),
                        ("topic_id", "=", source.topic_id.id),
                    ]
                ):
                    continue
                existing = self.search([("origin_agenda_item_id", "=", source.id)])
                if existing:
                    for transfer in existing.filtered(
                        lambda t: (
                            t.status in ("pending", "proposed")
                            and t.destination_meeting_id.state == "cancelled"
                        )
                    ):
                        transfer.action_retarget(meeting.id)
                    if not existing.filtered(
                        lambda t: (
                            t.status == "accepted"
                            and t.destination_meeting_id.state == "cancelled"
                        )
                    ):
                        continue
                self.create(
                    {
                        "origin_model": "agenda_item",
                        "origin_record_id": source.id,
                        "destination_meeting_id": meeting.id,
                    }
                )
        return result

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
