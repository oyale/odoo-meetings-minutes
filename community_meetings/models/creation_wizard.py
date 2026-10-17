import uuid
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from .topic import PRIORITIES
from .followup_activity import FOLLOWUP_KIND_CODES


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
            ("review", "Review"),
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
    last_default_start = fields.Datetime()
    last_default_attendee_ids = fields.Many2many(
        "res.partner", "community_meeting_wizard_defaults_rel"
    )
    line_ids = fields.One2many("community.meeting.point.wizard", "creation_wizard_id")
    carry_line_ids = fields.One2many("community.meeting.carry.review.line", "wizard_id")
    created_meeting_id = fields.Many2one("community.meeting", readonly=True)
    token = fields.Char(
        default=lambda self: str(uuid.uuid4()), readonly=True, required=True
    )
    review_summary = fields.Text(compute="_compute_review_summary", string="Review")

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
            proposed = self.series_id._proposed_next_meeting_datetime()
            if proposed and (not self.start_datetime or self.start_datetime == self.last_default_start):
                self.start_datetime = proposed
            self.last_default_start = self.start_datetime
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

    @api.depends(
        "series_id",
        "name",
        "start_datetime",
        "duration_hours",
        "attendee_partner_ids",
        "carry_line_ids.name",
        "carry_line_ids.decision",
        "line_ids.name",
        "line_ids.topic_id",
        "line_ids.agenda_type_id",
        "line_ids.included",
    )
    def _compute_review_summary(self):
        for wizard in self:
            when = ""
            if wizard.start_datetime:
                when = fields.Datetime.context_timestamp(
                    wizard, wizard.start_datetime
                ).strftime("%Y-%m-%d %H:%M")
            attendees = ", ".join(
                wizard.attendee_partner_ids.mapped("display_name")
            ) or _("None")
            carried = [
                "%s (%s)" % (line.name or "", line.decision)
                for line in wizard.carry_line_ids
            ]
            agenda = [
                "%s — %s" % (
                    line.name or line.topic_id.display_name or "",
                    line.agenda_type_id.display_name or "",
                )
                for line in wizard.line_ids.filtered("included")
            ]
            wizard.review_summary = "\n".join([
                _("Series: %s") % (wizard.series_id.name or _("Standalone meeting")),
                _("Title: %s") % (wizard.name or ""),
                _("When: %s (%sh)") % (when, "%g" % wizard.duration_hours),
                _("Attendees: %s") % attendees,
                _("Carried points: %s") % ("; ".join(carried) or _("None")),
                _("Agenda: %s") % ("; ".join(agenda) or _("None")),
            ])

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
        steps = ["series", "when", "people", "carryover", "agenda", "review"]
        if self.step == "when" and (
            not self.name or not self.start_datetime or self.duration_hours <= 0
        ):
            raise ValidationError(_("Enter a title, start time and positive duration."))
        if self.step == "people":
            choices = {line.candidate_key: line.decision for line in self.carry_line_ids}
            self.carry_line_ids.unlink()
            candidates = self.env["community.meeting"]._agenda_candidates(
                self.series_id, self.start_datetime
            )
            self.carry_line_ids = [
                (0, 0, {"candidate_key": candidate["key"],
                        **{k: v for k, v in candidate.items() if k != "key"},
                        "decision": choices.get(candidate["key"], "include")})
                for candidate in candidates
            ]
        self.step = steps[min(steps.index(self.step) + 1, len(steps) - 1)]
        return self._reload()

    def action_back(self):
        self.ensure_one()
        steps = ["series", "when", "people", "carryover", "agenda", "review"]
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
            values = {
                "name": self.name,
                "series_id": self.series_id.id,
                "company_id": self.company_id.id,
                "start_datetime": self.start_datetime,
                "duration_hours": self.duration_hours,
                "attendee_partner_ids": [(6, 0, self.attendee_partner_ids.ids)],
                "creation_token": self.token,
            }
            if self.series_id:
                values["meeting_kind_id"] = self.series_id.meeting_kind_id.id
            meeting = (
                self.env["community.meeting"]
                .with_context(review_carryovers_in_wizard=True, defer_carryover_processing=True)
                .create(values)
            )
            for line in self.line_ids.filtered("included"):
                item = self.env["community.meeting.agenda.item"].create(
                    line._item_values(meeting)
                )
                line._write_related_points(item.topic_id)
            for line in self.carry_line_ids.filtered(lambda l: l.decision == "include"):
                meeting._include_agenda_candidate({"key": line.candidate_key})
            for line in self.carry_line_ids.filtered(lambda l: l.decision == "discard"):
                meeting._discard_agenda_candidate(line.candidate_key)
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
    decision = fields.Selection(
        [("include", "Include"), ("postpone", "Postpone"), ("discard", "Discard")],
        default="include", required=True,
    )


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
    related_topic_ids = fields.Many2many(
        "community.meeting.topic",
        "community_meeting_point_wizard_related_rel",
        "wizard_id",
        "topic_id",
        string="Related points",
    )
    related_loaded = fields.Boolean(default=False, copy=False, readonly=True)
    origin_topic_id = fields.Many2one(related="topic_id.origin_topic_id", readonly=True)
    followup_allowed_kinds = fields.Many2many(
        "community.meeting.followup.kind",
        "point_wizard_followup_kind_rel", "wizard_id", "kind_id",
        string="Allowed follow-up types",
    )
    followup_default_kind = fields.Selection([("inherit", "Series/company default")] + FOLLOWUP_KIND_CODES, default="inherit", required=True)
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
    propose = fields.Boolean()
    proposal_series_id = fields.Many2one("community.meeting.series")

    @api.depends(
        "meeting_id", "creation_wizard_id.series_id", "creation_wizard_id.company_id", "proposal_series_id"
    )
    def _compute_scope(self):
        for w in self:
            parent = w.meeting_id or w.creation_wizard_id or w.proposal_series_id
            w.series_id = parent.series_id if parent else False
            w.company_id = parent.company_id if parent else self.env.company

    @api.onchange("topic_id")
    def _onchange_topic_id(self):
        if self.topic_id:
            self.related_topic_ids = self.topic_id.related_topic_ids
            self.related_loaded = True

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [
            dict(vals, related_loaded=True) if "related_topic_ids" in vals else vals
            for vals in vals_list
        ]
        return super().create(prepared)

    def write(self, vals):
        if "related_topic_ids" in vals:
            vals = dict(vals, related_loaded=True)
        return super().write(vals)

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
            "estimated_minutes": self.estimated_minutes or (
                self.series_id._point_estimated_minutes_default() if self.series_id else 0
            ),
            "followup_allowed_kinds": [(6, 0, self.followup_allowed_kinds.ids)],
            "followup_default_kind": self.followup_default_kind,
        }

    def _write_related_points(self, topic):
        if not topic:
            return
        # A programmatic reuse that never touched the field keeps the point's
        # existing links; only an explicit selection is authoritative.
        if self.topic_id and not self.related_loaded:
            return
        related = self.related_topic_ids - topic
        if set(related.ids) != set(topic.related_topic_ids.ids):
            topic.write({"related_topic_ids": [(6, 0, related.ids)]})

    def action_save(self):
        self.ensure_one()
        self.check_access("write")
        self.env.cr.execute(
            "SELECT id FROM community_meeting_point_wizard WHERE id=%s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["included", "created_item_id"])
        if self.propose:
            if not self.proposal_series_id:
                raise ValidationError(_("Choose a series for the proposal."))
            if not self.name or not self.agenda_type_id:
                raise ValidationError(_("Enter a title and select a point type."))
            self.env["community.meeting.topic"].propose(self._proposal_values())
            self.included = True
            return {"type": "ir.actions.act_window_close"}
        if not self.name and not self.topic_id:
            raise ValidationError(_("Enter a title or select an existing point."))
        if self.estimated_minutes < 0:
            raise ValidationError(_("Estimated minutes cannot be negative."))
        if self.meeting_id:
            if not self.created_item_id:
                self.created_item_id = self.env["community.meeting.agenda.item"].create(
                    self._item_values(self.meeting_id)
                )
            self._write_related_points(self.created_item_id.topic_id)
        elif not self.creation_wizard_id:
            raise UserError(_("Choose a meeting first."))
        self.included = True
        return (
            self.creation_wizard_id._reload()
            if self.creation_wizard_id
            else {"type": "ir.actions.act_window_close"}
        )

    def _proposal_values(self):
        return {
            "name": self.name,
            "description": self.description,
            "agenda_type_id": self.agenda_type_id.id,
            "priority": self.priority,
            "deadline": self.deadline,
            "estimated_minutes": self.estimated_minutes or self.proposal_series_id._point_estimated_minutes_default(),
            "followup_allowed_kinds": [(6, 0, self.followup_allowed_kinds.ids)],
            "followup_default_kind": self.followup_default_kind,
            "series_id": self.proposal_series_id.id,
            "company_id": self.proposal_series_id.company_id.id,
        }

    def action_cancel(self):
        self.ensure_one()
        return (
            self.creation_wizard_id._reload()
            if self.creation_wizard_id
            else {"type": "ir.actions.act_window_close"}
        )

    def action_save_another(self):
        self.action_save()
        if self.propose:
            return self._open(
                {
                    "default_propose": True,
                    "default_proposal_series_id": self.proposal_series_id.id,
                }
            )
        return self._open(
            {
                "default_meeting_id": self.meeting_id.id,
                "default_creation_wizard_id": self.creation_wizard_id.id,
            }
        )
