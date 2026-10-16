import uuid
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from .topic import PRIORITIES
from .followup_activity import FOLLOWUP_POLICIES, FOLLOWUP_KINDS


class MeetingCreateWizard(models.TransientModel):
    _name = "community.meeting.create.wizard"
    _description = "Prepare a Meeting"

    step = fields.Selection(
        [
            ("series", "Series"),
            ("when", "When"),
            ("people", "Attendees"),
            ("carryover", "Continue points"),
            ("agenda", "Agenda"),
        ],
        default="series",
        required=True,
    )
    series_id = fields.Many2one("community.meeting.series")
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    name = fields.Char(string="Meeting title")
    suggested_name = fields.Char()
    start_datetime = fields.Datetime(string="Estimated Start Datetime", default=fields.Datetime.now)
    duration_hours = fields.Float(string="Approximate duration", default=1.0)
    attendee_partner_ids = fields.Many2many("res.partner", string="Attendees")
    defaults_applied = fields.Boolean()
    last_default_duration = fields.Float(default=1.0)
    last_default_attendee_ids = fields.Many2many(
        "res.partner", "community_meeting_wizard_defaults_rel"
    )
    line_ids = fields.One2many("community.meeting.point.wizard", "creation_wizard_id")
    carry_line_ids = fields.One2many("community.meeting.carry.review.line", "wizard_id")
    created_meeting_id = fields.Many2one("community.meeting", readonly=True)
    token = fields.Char(
        default=lambda self: str(uuid.uuid4()), readonly=True, required=True
    )

    @api.model
    def _open(self, context):
        return {
            "type": "ir.actions.act_window",
            "name": _("Prepare a Meeting"),
            "res_model": self._name,
            "views": [
                (
                    self.env.ref("community_meetings.view_meeting_create_wizard").id,
                    "form",
                )
            ],
            "target": "new",
            "context": context,
        }

    def _reload(self):
        return {**self._open({}), "res_id": self.id}

    @api.onchange("series_id", "start_datetime")
    def _onchange_series(self):
        if self.series_id:
            if self.duration_hours == self.last_default_duration:
                self.duration_hours = self.series_id.duration_hours
            if set(self.attendee_partner_ids.ids) == set(
                self.last_default_attendee_ids.ids
            ):
                self.attendee_partner_ids = self.series_id.attendee_partner_ids
            self.company_id = self.series_id.company_id
            self._suggest_series_name()
            self.last_default_duration = self.series_id.duration_hours
            self.last_default_attendee_ids = self.series_id.attendee_partner_ids
            self.defaults_applied = True

    def _suggest_series_name(self):
        for wizard in self:
            if not wizard.series_id:
                continue
            suggestion = wizard.series_id._format_meeting_name(wizard.start_datetime)
            if not wizard.name or wizard.name == wizard.suggested_name:
                wizard.name = suggestion
            wizard.suggested_name = suggestion

    def action_use_series_defaults(self):
        self.ensure_one()
        if self.series_id:
            self.write(
                {
                    "duration_hours": self.series_id.duration_hours,
                    "attendee_partner_ids": [
                        (6, 0, self.series_id.attendee_partner_ids.ids)
                    ],
                    "defaults_applied": True,
                    "company_id": self.series_id.company_id.id,
                    "last_default_duration": self.series_id.duration_hours,
                    "last_default_attendee_ids": [
                        (6, 0, self.series_id.attendee_partner_ids.ids)
                    ],
                }
            )
        return self._reload()

    def action_next(self):
        self.ensure_one()
        if self.step == "when":
            self._suggest_series_name()
        steps = ["series", "when", "people", "carryover", "agenda"]
        if self.step == "when" and (
            not self.name or not self.start_datetime or self.duration_hours <= 0
        ):
            raise ValidationError(_("Enter a title, start time and positive duration."))
        if self.step == "people":
            choices = {line.candidate_key: line.accept for line in self.carry_line_ids}
            self.carry_line_ids.unlink()
            candidates = self.env["community.meeting"]._agenda_candidates(
                self.series_id, self.start_datetime
            )
            self.carry_line_ids = [
                (0, 0, {"candidate_key": candidate["key"],
                        **{k: v for k, v in candidate.items() if k != "key"},
                        "accept": choices.get(candidate["key"], True)})
                for candidate in candidates
            ]
        self.step = steps[min(steps.index(self.step) + 1, len(steps) - 1)]
        return self._reload()

    def action_back(self):
        self.ensure_one()
        steps = ["series", "when", "people", "carryover", "agenda"]
        self.step = steps[max(0, steps.index(self.step) - 1)]
        return self._reload()

    def action_add_point(self):
        self.ensure_one()
        return self.env["community.meeting.point.wizard"]._open(
            {"default_creation_wizard_id": self.id}
        )

    def action_finish(self):
        self.ensure_one()
        self.check_access("write")
        self._suggest_series_name()
        self.env.cr.execute(
            "SELECT id FROM community_meeting_create_wizard WHERE id=%s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["created_meeting_id"])
        if self.created_meeting_id:
            meeting = self.created_meeting_id
        else:
            if not self.name or not self.start_datetime or self.duration_hours <= 0:
                raise ValidationError(
                    _("Enter a title, start time and positive duration.")
                )
            meeting = (
                self.env["community.meeting"]
                .with_context(review_carryovers_in_wizard=True, defer_carryover_processing=True)
                .create(
                    {
                        "name": self.name,
                        "series_id": self.series_id.id,
                        "company_id": self.company_id.id,
                        "start_datetime": self.start_datetime,
                        "duration_hours": self.duration_hours,
                        "attendee_partner_ids": [(6, 0, self.attendee_partner_ids.ids)],
                        "creation_token": self.token,
                    }
                )
            )
            for line in self.line_ids.filtered("included"):
                self.env["community.meeting.agenda.item"].create(
                    line._item_values(meeting)
                )
            for line in self.carry_line_ids.filtered("accept"):
                meeting._include_agenda_candidate({"key": line.candidate_key})
            self.created_meeting_id = meeting
        return {
            "type": "ir.actions.act_window",
            "name": _("Meeting"),
            "res_model": "community.meeting",
            "res_id": meeting.id,
            "views": [(False, "form")],
            "target": "current",
        }


class CarryReviewLine(models.TransientModel):
    _name = "community.meeting.carry.review.line"
    _description = "Review Continuing Point"

    wizard_id = fields.Many2one(
        "community.meeting.create.wizard", required=True, ondelete="cascade"
    )
    candidate_key = fields.Char(required=True)
    source_id = fields.Many2one("community.meeting.agenda.item")
    transfer_id = fields.Many2one("community.meeting.carryover")
    topic_id = fields.Many2one("community.meeting.topic")
    name = fields.Char()
    origin_meeting_id = fields.Many2one("community.meeting")
    reason = fields.Text()
    accept = fields.Boolean(string="Include")


class PointWizard(models.TransientModel):
    _name = "community.meeting.point.wizard"
    _description = "Add an Agenda Point"

    meeting_id = fields.Many2one("community.meeting")
    creation_wizard_id = fields.Many2one(
        "community.meeting.create.wizard", ondelete="cascade"
    )
    series_id = fields.Many2one("community.meeting.series", compute="_compute_scope")
    company_id = fields.Many2one("res.company", compute="_compute_scope")
    topic_id = fields.Many2one("community.meeting.topic", string="Existing point")
    followup_policy = fields.Selection([("inherit", "Series/company default")] + FOLLOWUP_POLICIES, default="inherit", required=True)
    default_followup_kind = fields.Selection([("inherit", "Series/company default")] + FOLLOWUP_KINDS, default="inherit", required=True)
    name = fields.Char(string="Title")
    agenda_type_id = fields.Many2one(
        "community.meeting.agenda.type",
        string="Point type",
        default=lambda self: self.env.ref("community_meetings.agenda_type_discussion"),
    )
    description = fields.Html(string="Develop the point")
    priority = fields.Selection(PRIORITIES, default="1", required=True)
    more_options = fields.Boolean(string="More options")
    deadline = fields.Date()
    estimated_minutes = fields.Integer()
    included = fields.Boolean(readonly=True)
    created_item_id = fields.Many2one("community.meeting.agenda.item", readonly=True)

    @api.depends(
        "meeting_id", "creation_wizard_id.series_id", "creation_wizard_id.company_id"
    )
    def _compute_scope(self):
        for w in self:
            parent = w.meeting_id or w.creation_wizard_id
            w.series_id = parent.series_id
            w.company_id = parent.company_id

    @api.model
    def _open(self, context):
        return {
            "type": "ir.actions.act_window",
            "name": _("Add Point"),
            "res_model": self._name,
            "views": [
                (self.env.ref("community_meetings.view_point_wizard").id, "form")
            ],
            "target": "new",
            "context": context,
        }

    def _item_values(self, meeting):
        self.ensure_one()
        if self.topic_id:
            return {"meeting_id": meeting.id, "topic_id": self.topic_id.id}
        if not self.name or not self.agenda_type_id:
            raise ValidationError(_("Enter a title and select a point type."))
        return {
            "meeting_id": meeting.id,
            "name": self.name,
            "agenda_type_id": self.agenda_type_id.id,
            "description": self.description,
            "priority": self.priority,
            "deadline": self.deadline,
            "estimated_minutes": self.estimated_minutes,
            "followup_policy": self.followup_policy,
            "default_followup_kind": self.default_followup_kind,
        }

    def action_save(self):
        self.ensure_one()
        self.check_access("write")
        self.env.cr.execute(
            "SELECT id FROM community_meeting_point_wizard WHERE id=%s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["included", "created_item_id"])
        if not self.name and not self.topic_id:
            raise ValidationError(_("Enter a title or select an existing point."))
        if self.estimated_minutes < 0:
            raise ValidationError(_("Estimated minutes cannot be negative."))
        if self.meeting_id and not self.created_item_id:
            self.created_item_id = self.env["community.meeting.agenda.item"].create(
                self._item_values(self.meeting_id)
            )
        elif not self.meeting_id and not self.creation_wizard_id:
            raise UserError(_("Choose a meeting first."))
        self.included = True
        return (
            self.creation_wizard_id._reload()
            if self.creation_wizard_id
            else {"type": "ir.actions.act_window_close"}
        )

    def action_cancel(self):
        self.ensure_one()
        return (
            self.creation_wizard_id._reload()
            if self.creation_wizard_id
            else {"type": "ir.actions.act_window_close"}
        )

    def action_save_another(self):
        self.action_save()
        return self._open(
            {
                "default_meeting_id": self.meeting_id.id,
                "default_creation_wizard_id": self.creation_wizard_id.id,
            }
        )
