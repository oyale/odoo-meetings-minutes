from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

PRIORITIES = [("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Critical")]
CONTENT_FIELDS = (
    "name",
    "description",
    "agenda_type_id",
    "priority",
    "deadline",
    "estimated_minutes",
    "followup_allowed_kinds",
    "followup_default_kind",
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
    origin_topic_id = fields.Many2one(
        "community.meeting.topic", ondelete="set null", string="Origin point", copy=False,
    )
    origin_action_id = fields.Many2one(
        "community.meeting.action", ondelete="set null", string="Promoted from follow-up", copy=False,
    )
    agenda_type_id = fields.Many2one(
        "community.meeting.agenda.type", required=True, ondelete="restrict"
    )
    priority = fields.Selection(PRIORITIES, default="1", required=True, tracking=True)
    deadline = fields.Date(tracking=True)
    estimated_minutes = fields.Integer()
    related_topic_ids = fields.Many2many(
        "community.meeting.topic",
        "community_meeting_topic_related_rel",
        "topic_id",
        "related_topic_id",
        string="Related points",
        check_company=True,
    )
    proposer_partner_id = fields.Many2one("res.partner", ondelete="restrict", index=True)
    submitted_by_user_id = fields.Many2one("res.users", readonly=True, index=True)
    submitted_at = fields.Datetime(readonly=True)
    proposal_status = fields.Selection(
        [("submitted", "Submitted"), ("accepted", "Accepted"),
         ("rejected", "Rejected"), ("withdrawn", "Withdrawn")],
        copy=False, index=True,
    )
    proposal_response = fields.Text()
    responded_by_id = fields.Many2one("res.users", readonly=True)
    responded_at = fields.Datetime(readonly=True)
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
        # compute_sudo=False with uid/allowed_company_ids in depends_context:
        # the visible links are access-filtered per user, so the cache must
        # invalidate when those change.
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

    @api.constrains("related_topic_ids")
    def _check_related_points(self):
        for topic in self:
            if topic in topic.related_topic_ids:
                raise ValidationError(_("A point cannot be related to itself."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("proposal_status") in ("accepted", "rejected", "withdrawn"):
                raise ValidationError(_("Use a proposal workflow action to change its status."))
            vals.pop("responded_by_id", None)
            vals.pop("responded_at", None)
            if not self.env.context.get("meeting_proposal_create"):
                for server_field in ("proposer_partner_id", "submitted_by_user_id", "submitted_at"):
                    vals.pop(server_field, None)
            if (
                vals.get("state", "open") not in ("open", "proposed")
                or vals.get("outcome")
                or vals.get("postponed")
            ):
                raise ValidationError(_("Use the meeting workflow to resolve a point."))
        return super().create(vals_list)

    def write(self, vals):
        if {
            "proposal_status", "responded_by_id", "responded_at",
            "submitted_by_user_id", "submitted_at",
            "proposer_partner_id", "proposal_response",
        }.intersection(vals):
            raise UserError(_("Use a proposal workflow action to change its status."))
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
        # Content is shared only by deliberate reuse. Propagation stops at the
        # editable frontier: only participations on draft/scheduled meetings that
        # have not started follow the point. Held/minutes_draft minutes keep their
        # own snapshot, so minutes under review cannot shift under approvers.
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
        return super().write({"series_id": series.id if series else False})

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
            body=_("Reopened: %s", reason) if reason else _("Reopened."),
            message_type="notification",
            email_from=self.env.user.email or "meetings@localhost",
        )

    def action_admit(self):
        self.check_access("write")
        if any(t.state != "proposed" for t in self):
            raise UserError(_("Only proposed points can be admitted."))
        return super().write({"state": "open"})

    def _check_proposal_review_access(self):
        if not (
            self.env.user.has_group("community_meetings.group_meeting_editor")
            or self.env.user.has_group("community_meetings.group_meeting_manager")
        ):
            raise AccessError(_("Only meeting editors can review agenda proposals."))

    def action_accept_proposal(self):
        self._check_proposal_review_access()
        self.check_access("write")
        if any(t.state != "proposed" or t.proposal_status != "submitted" for t in self):
            raise UserError(_("Only submitted proposals can be accepted."))
        for topic in self:
            super(MeetingTopic, topic.sudo()).write({
                "state": "open", "proposal_status": "accepted",
                "responded_by_id": self.env.uid, "responded_at": fields.Datetime.now(),
            })
        return True

    def action_reject_proposal(self, response=False):
        self._check_proposal_review_access()
        self.check_access("write")
        if any(t.proposal_status != "submitted" for t in self):
            raise UserError(_("Only submitted proposals can be rejected."))
        for topic in self:
            super(MeetingTopic, topic.sudo()).write({
                "proposal_status": "rejected", "proposal_response": response,
                "responded_by_id": self.env.uid, "responded_at": fields.Datetime.now(),
            })
        return True

    def action_withdraw_proposal(self):
        self.check_access("write")
        for topic in self:
            if topic.proposal_status != "submitted" or topic.submitted_by_user_id != self.env.user:
                raise AccessError(_("You can withdraw only your own submitted proposal."))
            super(MeetingTopic, topic.sudo()).write({
                "proposal_status": "withdrawn",
                "responded_by_id": self.env.uid, "responded_at": fields.Datetime.now(),
            })
        return True

    @api.model
    def _has_proposal_capability(self):
        # Default: every internal user may propose (base.group_user implies
        # group_agenda_proposer). To restrict who may propose without code,
        # list authorized proposer groups; when any exist, only their members
        # (and meeting managers) may propose.
        user = self.env.user
        policy_groups = self.env["community.meeting.proposal.group.policy"].sudo().search(
            [("active", "=", True)]
        ).group_id
        if not policy_groups:
            return user.has_group("community_meetings.group_agenda_proposer")
        return (
            user.has_group("community_meetings.group_meeting_manager")
            or bool(user.groups_id & policy_groups)
        )

    @api.model
    def _validate_proposal_target(self, company_id, series_id):
        if company_id not in self.env.user.company_ids.ids:
            raise AccessError(_("You cannot submit proposals for this company."))
        series = self.env["community.meeting.series"].sudo().browse(series_id).exists()
        if not series or series.company_id.id != company_id or not series.active:
            raise ValidationError(_("The selected proposal scope is unavailable."))
        return series

    @api.model
    def propose(self, values):
        values = dict(values)
        company_id = values.get("company_id", self.env.company.id)
        series = self._validate_proposal_target(company_id, values.get("series_id"))
        values["company_id"] = company_id
        values["series_id"] = series.id
        return self._create_proposal(values, self.env.user.partner_id, self.env.uid)

    @api.model
    def _create_proposal(self, values, proposer_partner, submitted_by):
        if not self._has_proposal_capability():
            raise AccessError(_("You are not authorized to submit agenda proposals."))
        values = dict(values)
        for guarded in (
            "proposal_status", "submitted_by_user_id", "submitted_at", "proposal_response",
        ):
            values.pop(guarded, None)
        values.update({
            "state": "proposed",
            "proposal_status": "submitted",
            "proposer_partner_id": proposer_partner.id,
            "submitted_by_user_id": submitted_by.id if hasattr(submitted_by, "id") else submitted_by,
            "submitted_at": fields.Datetime.now(),
        })
        return self.with_context(meeting_proposal_create=True).sudo().create(values)

    @api.model
    def submit_on_behalf(self, partner_id, values):
        if not (
            self.env.user.has_group("community_meetings.group_meeting_editor")
            or self.env.user.has_group("community_meetings.group_meeting_manager")
        ):
            raise AccessError(_("Only a meeting editor can record a proposal on behalf of a contact."))
        partner = self.env["res.partner"].browse(partner_id).exists()
        if not partner:
            raise ValidationError(_("The proposed contact is unavailable."))
        company_id = values.get("company_id", self.env.company.id)
        series = self._validate_proposal_target(company_id, values.get("series_id"))
        today = fields.Date.context_today(self)
        grant = self.env["community.meeting.proposal.grant"].sudo().search([
            ("partner_id", "=", partner.id), ("company_id", "=", company_id), ("active", "=", True),
            "|", ("active_from", "=", False), ("active_from", "<=", today),
            "|", ("active_until", "=", False), ("active_until", ">=", today),
            "|", ("series_id", "=", False), ("series_id", "=", series.id),
        ], limit=1)
        if not grant:
            raise AccessError(_("This contact is not eligible to propose topics in the selected scope."))
        values = dict(values, company_id=company_id, series_id=series.id)
        return self._create_proposal(values, partner, self.env.uid)

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
    actual_minutes = fields.Integer(string="Actual minutes", copy=False)
    actual_seconds = fields.Integer(copy=False)
    actual_started_at = fields.Datetime(copy=False)
    has_started = fields.Boolean(readonly=True, copy=False)
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

    @api.constrains("estimated_minutes", "actual_minutes", "actual_seconds")
    def _check_estimated_minutes(self):
        if any(
            i.estimated_minutes < 0 or i.actual_minutes < 0 or i.actual_seconds < 0
            for i in self
        ):
            raise ValidationError(_("Estimated and actual minutes cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("has_started"):
                raise UserError(_("A point can only be started from the live meeting."))
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
        if "has_started" in vals:
            raise UserError(_("Point start status is managed by the live meeting."))
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
            self.meeting_id._lock_live_workflow()
            # Serialize changes across sessions sharing a point.
            for topic in self.mapped("topic_id").sorted("id"):
                topic._lock_workflow()
        result = super().write(vals)
        for item in self:
            if (
                item.actual_started_at
                and vals.get("disposition") in ("discussed", "closed", "deferred")
            ):
                item._pause_timing()
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

    def _pause_timing(self):
        self.meeting_id._lock_live_workflow()
        self.invalidate_recordset(["actual_started_at", "actual_seconds", "actual_minutes"])
        now = fields.Datetime.now()
        for item in self.filtered("actual_started_at"):
            started = fields.Datetime.to_datetime(item.actual_started_at)
            elapsed = max(0, int((now - started).total_seconds()))
            total_seconds = (item.actual_seconds or item.actual_minutes * 60) + elapsed
            super(AgendaParticipation, item).write(
                {
                    "actual_seconds": total_seconds,
                    "actual_minutes": (total_seconds + 30) // 60,
                    "actual_started_at": False,
                }
            )

    def action_start_timing(self):
        for item in self:
            item.check_access("write")
            meeting = item.meeting_id
            meeting.check_access("write")
            meeting._lock_live_workflow()
            item.invalidate_recordset(["disposition", "actual_started_at", "actual_seconds", "actual_minutes"])
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise UserError(_("Only meeting editors can start a point timer."))
            if (
                meeting.state != "scheduled"
                or not meeting.actual_start_datetime
                or meeting.actual_paused_at
                or meeting.actual_end_datetime
            ):
                raise UserError(_("Start the live meeting before timing an agenda point."))
            if item.disposition == "closed" or (
                item.kind == "information" and item.disposition == "discussed"
            ):
                raise UserError(_("Reopen a completed point before timing it again."))
            meeting.agenda_item_ids.filtered("actual_started_at")._pause_timing()
            if not item.actual_seconds and item.actual_minutes:
                super(AgendaParticipation, item).write(
                    {"actual_seconds": item.actual_minutes * 60}
                )
            super(AgendaParticipation, item).write(
                {"actual_started_at": fields.Datetime.now(), "has_started": True}
            )
        return True

    def action_pause_timing(self):
        for item in self:
            item.check_access("write")
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise UserError(_("Only meeting editors can pause a point timer."))
        self._pause_timing()
        return True

    def action_reopen(self):
        for item in self:
            item.check_access("write")
            if item.meeting_id.state in ("approved", "cancelled"):
                raise UserError(_("Reopen this point in an editable meeting."))
            item.meeting_id._check_live_editorial(item, result_change=True)
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
            item._write_workflow_result(
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
        return actions.filtered(lambda action: action._has_execution_evidence())


class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"

    topic_ids = fields.One2many("community.meeting.topic", "series_id", string="Points")
    pending_proposal_ids = fields.One2many(
        "community.meeting.topic", compute="_compute_pending_proposals",
        groups="community_meetings.group_meeting_editor",
    )

    @api.depends("topic_ids.state", "topic_ids.proposal_status")
    def _compute_pending_proposals(self):
        for series in self:
            series.pending_proposal_ids = self.env["community.meeting.topic"].search([
                ("series_id", "=", series.id),
                ("state", "=", "proposed"),
                ("proposal_status", "=", "submitted"),
            ])


class MeetingTopicCopy(models.Model):
    _inherit = "community.meeting.topic"

    def action_copy_to_series(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": _("Copy Point to Another Series"),
            "res_model": "community.meeting.topic.copy.wizard",
            "view_mode": "form",
            "views": [(self.env.ref("community_meetings.view_topic_copy_wizard").id, "form")],
            "target": "new",
            "context": {"default_topic_id": self.id},
        }


class TopicCopyWizard(models.TransientModel):
    _name = "community.meeting.topic.copy.wizard"
    _description = "Copy a Point to Another Series"

    topic_id = fields.Many2one("community.meeting.topic", required=True, readonly=True)
    company_id = fields.Many2one(related="topic_id.company_id", readonly=True)
    destination_series_id = fields.Many2one(
        "community.meeting.series", required=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )

    def action_copy(self):
        self.ensure_one()
        source = self.topic_id
        self.env["community.meeting.topic"].check_access_rights("create")
        self.destination_series_id.check_access("read")
        if self.destination_series_id.company_id != source.company_id:
            raise ValidationError(_("Choose a series in the same company."))
        new = self.env["community.meeting.topic"].create({
            "name": source.name,
            "description": source.description,
            "agenda_type_id": source.agenda_type_id.id,
            "priority": source.priority,
            "deadline": source.deadline,
            "estimated_minutes": source.estimated_minutes,
            "followup_allowed_kinds": [(6, 0, source.followup_allowed_kinds.ids)],
            "followup_default_kind": source.followup_default_kind,
            "company_id": source.company_id.id,
            "series_id": self.destination_series_id.id,
            "state": "open",
            "origin_topic_id": source.id,
        })
        return {
            "type": "ir.actions.act_window", "name": _("Point"),
            "res_model": "community.meeting.topic", "res_id": new.id,
            "views": [(False, "form")], "target": "current",
        }
