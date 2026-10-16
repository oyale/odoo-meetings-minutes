from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

PRIORITIES = [("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Critical")]
CONTENT_FIELDS = (
    "name",
    "description",
    "agenda_type_id",
    "priority",
    "deadline",
    "estimated_minutes",
)


class MeetingTopic(models.Model):
    _name = "community.meeting.topic"
    _description = "Meeting Point"
    _inherit = ["mail.thread"]
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    description = fields.Html()
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    series_id = fields.Many2one(
        "community.meeting.series", check_company=True, ondelete="restrict"
    )
    agenda_type_id = fields.Many2one(
        "community.meeting.agenda.type", required=True, ondelete="restrict"
    )
    priority = fields.Selection(PRIORITIES, default="1", required=True, tracking=True)
    deadline = fields.Date(tracking=True)
    estimated_minutes = fields.Integer()
    state = fields.Selection(
        [("proposed", "Proposed"), ("open", "Open"), ("closed", "Closed")],
        default="open",
        required=True,
        tracking=True,
    )
    outcome = fields.Char(readonly=True, tracking=True)
    last_participation_id = fields.Many2one(
        "community.meeting.agenda.item",
        readonly=True,
        ondelete="set null",
        groups="community_meetings.group_meeting_manager",
    )
    postponed = fields.Boolean(readonly=True, tracking=True)
    all_participation_ids = fields.One2many(
        "community.meeting.agenda.item",
        "topic_id",
        groups="community_meetings.group_meeting_manager",
    )
    participation_ids = fields.One2many(
        "community.meeting.agenda.item",
        compute="_compute_visible_links",
        compute_sudo=False,
    )
    all_action_ids = fields.One2many(
        "community.meeting.action",
        "topic_id",
        groups="community_meetings.group_meeting_manager",
    )
    action_ids = fields.One2many(
        "community.meeting.action", compute="_compute_visible_links", compute_sudo=False
    )

    @api.depends("all_participation_ids", "all_action_ids")
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_visible_links(self):
        for topic in self:
            topic.participation_ids = self.env["community.meeting.agenda.item"].search(
                [("topic_id", "=", topic.id)]
            )
            topic.action_ids = self.env["community.meeting.action"].search(
                [("topic_id", "=", topic.id)]
            )

    @api.constrains("estimated_minutes")
    def _check_minutes(self):
        if any(t.estimated_minutes < 0 for t in self):
            raise ValidationError(_("Estimated minutes cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("state", "open") not in ("open", "proposed")
                or vals.get("outcome")
                or vals.get("postponed")
            ):
                raise ValidationError(_("Use the meeting workflow to resolve a point."))
        return super().create(vals_list)

    def write(self, vals):
        if {
            "state",
            "outcome",
            "postponed",
            "last_participation_id",
            "company_id",
            "series_id",
        }.intersection(vals):
            raise UserError(
                _("Use the meeting workflow to change point state or scope.")
            )
        # Content is shared only by deliberate reuse. Never rewrite past sessions.
        if "agenda_type_id" in vals and any(t.state == "closed" for t in self):
            raise UserError(_("Reopen the point before changing its type."))
        result = super().write(vals)
        for topic in self:
            upcoming = topic.participation_ids.filtered(
                lambda i: (
                    i.meeting_id.state in ("draft", "scheduled")
                    and not i.meeting_id.actual_start_datetime
                )
            )
            for item in upcoming:
                item.check_access("write")
                item._write_topic_content(
                    {k: v for k, v in vals.items() if k in CONTENT_FIELDS}
                )
        return result

    def _lock_workflow(self):
        # A row update also serializes repeatable-read snapshots: stale concurrent
        # requests are retried by Odoo instead of validating against old task rows.
        for topic in self.sorted("id"):
            self.env.cr.execute(
                "UPDATE community_meeting_topic SET write_date=clock_timestamp() WHERE id=%s",
                [topic.id],
            )
        self.invalidate_recordset(["write_date"])

    def _record_result(self, item):
        self.ensure_one()
        self.check_access("write")
        self._lock_workflow()
        self.invalidate_recordset()
        if item.is_followup:
            return
        if (
            self.state == "closed"
            and self.sudo().last_participation_id
            and self.sudo().last_participation_id != item
        ):
            raise UserError(_("Reopen the closed point before recording a new result."))
        closed = item.disposition == "closed" or (
            item.kind == "information" and item.disposition == "discussed"
        )
        values = {
            "last_participation_id": item.id,
            "state": "closed" if closed else "open",
            "postponed": item.disposition == "deferred",
            "outcome": (
                item.decision_result if item.kind == "decision" else item.disposition
            )
            if closed
            else False,
        }
        super(MeetingTopic, self.sudo()).write(values)

    def _set_series(self, series):
        self.check_access("write")
        for topic in self:
            if topic.sudo().participation_ids.filtered(
                lambda i: i.meeting_id.series_id != series
            ):
                raise UserError(
                    _("A shared point cannot be moved to a different series.")
                )
        return super().write({"series_id": series.id})

    def _reopen(self, reason):
        self.check_access("write")
        super(MeetingTopic, self.sudo()).write(
            {
                "state": "open",
                "outcome": False,
                "postponed": False,
                "last_participation_id": False,
            }
        )
        self.message_post(
            body=_("Reopened: %s", reason),
            message_type="notification",
            email_from=self.env.user.email or "meetings@localhost",
        )

    def action_admit(self):
        self.check_access("write")
        if any(t.state != "proposed" for t in self):
            raise UserError(_("Only proposed points can be admitted."))
        return super().write({"state": "open"})

    def action_open(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "views": [(False, "form")],
            "target": "current",
        }


class AgendaParticipation(models.Model):
    _inherit = "community.meeting.agenda.item"

    topic_id = fields.Many2one(
        "community.meeting.topic",
        ondelete="restrict",
        index=True,
        copy=False,
        check_company=True,
    )
    priority = fields.Selection(PRIORITIES, default="1", required=True)
    deadline = fields.Date()
    estimated_minutes = fields.Integer()
    review_next_meeting = fields.Boolean(string="Review at next meeting", copy=False)
    is_followup = fields.Boolean(readonly=True, copy=False)
    topic_state = fields.Selection(related="topic_id.state")
    topic_outcome = fields.Char(related="topic_id.outcome")
    reopen_reason = fields.Char(copy=False)

    _sql_constraints = [
        (
            "meeting_topic_unique",
            "unique(meeting_id, topic_id)",
            "This point is already on this meeting agenda.",
        )
    ]

    @api.constrains("estimated_minutes")
    def _check_estimated_minutes(self):
        if any(i.estimated_minutes < 0 for i in self):
            raise ValidationError(_("Estimated minutes cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
            meeting.check_access("write")
            topic = self.env["community.meeting.topic"].browse(vals.get("topic_id"))
            if topic:
                topic.check_access("read")
                if self.search_count(
                    [("meeting_id", "=", meeting.id), ("topic_id", "=", topic.id)]
                ):
                    raise ValidationError(
                        _("This point is already on this meeting agenda.")
                    )
                if (
                    topic.company_id != meeting.company_id
                    or topic.series_id != meeting.series_id
                ):
                    raise ValidationError(
                        _("Reuse points only within their original company and series.")
                    )
                for key in CONTENT_FIELDS:
                    value = topic[key]
                    vals[key] = value.id if key == "agenda_type_id" else value
                vals["is_followup"] = topic.state == "closed"
            else:
                if not vals.get("agenda_type_id"):
                    vals["agenda_type_id"] = (
                        self.env["community.meeting.agenda.type"]
                        .search(
                            [
                                ("behavior", "=", vals.get("kind", "discussion")),
                                ("active", "=", True),
                            ],
                            limit=1,
                        )
                        .id
                    )
                topic = self.env["community.meeting.topic"].create(
                    {
                        **{k: vals[k] for k in CONTENT_FIELDS if k in vals},
                        "company_id": meeting.company_id.id,
                        "series_id": meeting.series_id.id,
                    }
                )
                vals["topic_id"] = topic.id
            prepared.append(vals)
        items = super().create(prepared)
        for item in items:
            if item.disposition != "open":
                item.topic_id._record_result(item)
        return items

    def _write_topic_content(self, vals):
        if vals:
            return super(AgendaParticipation, self).write(vals)
        return True

    def write(self, vals):
        if "topic_id" in vals or "is_followup" in vals:
            raise UserError(_("A participation cannot be moved to another point."))
        if vals.get("disposition") in ("open", "discussed", "deferred"):
            for item in self:
                was_closed = item.disposition == "closed" or (
                    item.kind == "information" and item.disposition == "discussed"
                )
                if (
                    was_closed
                    and item.topic_id.state == "closed"
                    and not item.is_followup
                ):
                    raise UserError(
                        _("Reopen the point with a reason before changing its result.")
                    )
        if {"disposition", "decision_result"}.intersection(vals):
            # Serialize changes across sessions sharing a point.
            for topic in self.mapped("topic_id").sorted("id"):
                topic._lock_workflow()
        result = super().write(vals)
        for item in self:
            if vals.get("disposition") == "deferred":
                super(AgendaParticipation, item).write({"review_next_meeting": True})
            if {"disposition", "decision_result"}.intersection(vals) and item.topic_id:
                item.topic_id._record_result(item)
            content = {
                k: item[k].id if k == "agenda_type_id" else item[k]
                for k in CONTENT_FIELDS
                if k in vals
            }
            if "kind" in vals:
                content["agenda_type_id"] = item.agenda_type_id.id
            if content and item.topic_id:
                item.topic_id.write(content)
        return result

    def action_reopen(self):
        for item in self:
            item.check_access("write")
            if not item.reopen_reason:
                raise ValidationError(_("Enter a reason for reopening the point."))
            if item.meeting_id.state in ("approved", "cancelled"):
                raise UserError(_("Reopen this point in an editable meeting."))
            item.topic_id._reopen(item.reopen_reason)
            agreements = self.env["community.meeting.resolution"].search(
                [
                    ("agenda_item_id", "=", item.id),
                    ("status", "=", "active"),
                    ("decision_outcome", "!=", False),
                ]
            )
            agreements.write({"status": "withdrawn"})
            super(AgendaParticipation, item).write({"is_followup": False})
            item.write(
                {
                    "disposition": "open",
                    "decision_result": "pending" if item.kind == "decision" else False,
                }
            )
        return True

    def action_edit_point(self):
        self.ensure_one()
        return self.topic_id.action_open()

    def _validate_followup_removal(self, actions):
        for item in self.filtered(
            lambda i: i.kind == "todo" and i.disposition == "closed"
        ):
            if not (item._followup_actions() - actions):
                raise ValidationError(
                    _(
                        "A resolved TODO must keep at least one non-cancelled follow-up task."
                    )
                )

    def _followup_actions(self):
        self.ensure_one()
        actions = self.env["community.meeting.action"].search(
            [
                ("topic_id", "=", self.topic_id.id),
                ("state", "!=", "cancelled"),
                ("responsible_user_id", "!=", False),
            ]
        )
        return actions.filtered(
            lambda action: action.followup_kind == "task"
            or action.followup_activity_id
            or action.followup_activity_completed_on
        )
