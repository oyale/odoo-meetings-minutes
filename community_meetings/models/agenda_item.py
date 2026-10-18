from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CommunityMeetingAgendaItem(models.Model):
    _name = "community.meeting.agenda.item"
    _description = "Meeting Agenda Item"
    _order = "sequence, id"
    _check_company_auto = True

    meeting_id = fields.Many2one(
        "community.meeting", required=True, ondelete="cascade", index=True,
        check_company=True,
    )
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    kind = fields.Selection(
        [("information", "Information"), ("discussion", "Discussion"), ("decision", "Decision"), ("todo", "TODO"),
         ("minutes_approval", "Minutes Approval"), ("next_meeting", "Next Meeting"), ("followup", "Follow-up")],
        default="discussion", required=True,
    )
    agenda_type_id = fields.Many2one(
        "community.meeting.agenda.type", string="Point type", required=True,
        default=lambda self: self.env.ref("community_meetings.agenda_type_discussion", raise_if_not_found=False),
        ondelete="restrict", domain="[('active', '=', True)]",
    )
    description = fields.Html()
    discussion_notes = fields.Html()
    presenter_partner_id = fields.Many2one(
        "res.partner",
        related="topic_id.presenter_partner_id",
        readonly=False,
    )
    disposition = fields.Selection(
        [("open", "Open"), ("discussed", "Treated / Discussed"),
         ("deferred", "Postponed"), ("closed", "Resolved")],
        default="open", required=True,
    )
    decision_result = fields.Selection(
        [("pending", "Pending Decision"), ("approved", "Approved"), ("denied", "Denied")],
        string="Decision outcome",
    )
    deferral_reason = fields.Text(string="Postponement reason")
    deferral_reason_code = fields.Selection(
        [
            ("blocked_point", "Blocked by another point"),
            ("blocked_task", "Blocked by a task"),
            ("blocked_activity", "Blocked by an activity"),
            ("blocked_todo", "Blocked by a To-do"),
            ("no_time", "Lack of time"),
            ("other", "Other reason"),
        ],
        string="Reason for postponing",
        copy=False,
    )
    deferral_blocked_by = fields.Reference(
        selection=[
            ("community.meeting.topic", "Point"),
            ("community.meeting.action", "Follow-up"),
        ],
        string="Blocked by",
        copy=False,
        help="Optional link to the point or follow-up that blocks this one.",
    )
    next_meeting_datetime = fields.Datetime(
        string="Next meeting date", copy=False,
        help="Date chosen for the next meeting by a 'Next Meeting' point.",
    )
    minutes_approval_ids = fields.One2many(
        "community.meeting.minutes.approval", "agenda_item_id",
        string="Approved previous minutes", copy=False,
    )
    private_note_ids = fields.One2many(
        "community.meeting.editor.note", "agenda_item_id",
        groups="community_meetings.group_meeting_editor",
    )
    carryover_id = fields.Many2one(
        "community.meeting.carryover", ondelete="restrict", copy=False,
        groups="community_meetings.group_meeting_editor",
    )

    @api.constrains("meeting_id")
    def _check_meeting_editable(self):
        if any(item.meeting_id.state in ("approved", "cancelled") for item in self):
            raise ValidationError(_("Agenda items cannot be added to approved or cancelled meetings."))

    @api.constrains("kind", "decision_result", "disposition")
    def _check_workflow_requirements(self):
        for item in self:
            if item.kind != "decision" and item.decision_result:
                raise ValidationError(_("Only decision agenda items can have a decision outcome."))
            if item.kind != "decision" and self.env["community.meeting.resolution"].search_count([
                ("agenda_item_id", "=", item.id), ("status", "=", "active"), ("decision_outcome", "!=", False),
            ]):
                raise ValidationError(_("Withdraw the decision agreement before changing the point type."))
            if item.decision_result in ("approved", "denied") and item.disposition != "closed":
                raise ValidationError(_("An approved or denied decision must be marked as resolved."))
            if item.kind == "decision":
                agreement = self.env["community.meeting.resolution"].search([
                    ("agenda_item_id", "=", item.id), ("status", "=", "active"),
                    ("decision_outcome", "!=", False),
                ], limit=1)
                if (
                    (item.disposition == "closed" or item.decision_result in ("approved", "denied") or agreement)
                    and (
                        not agreement or item.decision_result != agreement.decision_outcome
                        or item.disposition != "closed"
                    )
                ):
                    raise ValidationError(_("Record an active agreement approving or rejecting this decision before closing it. The point's result must match that agreement."))
            if item.kind == "todo" and item.disposition == "closed" and not item._followup_actions():
                raise ValidationError(_("Create a follow-up task for this TODO before resolving it."))

    @api.constrains("disposition", "deferral_reason_code", "deferral_reason", "deferral_blocked_by")
    def _check_deferral_reason(self):
        blocked = {"blocked_point", "blocked_task", "blocked_activity", "blocked_todo"}
        for item in self:
            if item.disposition != "deferred":
                continue
            if item.deferral_reason_code == "other" and not (item.deferral_reason or "").strip():
                raise ValidationError(_("Describe the reason for postponing this point."))
            if item.deferral_blocked_by:
                if item.deferral_reason_code not in blocked:
                    raise ValidationError(_("Choose a blocking reason before linking a record."))
                record = item.deferral_blocked_by
                if record.exists():
                    record.check_access("read")
                    company = record.company_id if "company_id" in record._fields else False
                    if company and company != item.company_id:
                        raise ValidationError(_("The blocking record must belong to the meeting company."))

    @api.onchange("kind")
    def _onchange_kind(self):
        for item in self:
            if item.kind == "decision":
                item.decision_result = item.decision_result or "pending"
            else:
                item.decision_result = False

    @api.onchange("agenda_type_id")
    def _onchange_agenda_type_id(self):
        for item in self:
            item.kind = item.agenda_type_id.behavior
            if item.kind == "decision":
                item.decision_result = item.decision_result or "pending"
            else:
                item.decision_result = False

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("You are not allowed to edit agendas."))
        meetings = self.env["community.meeting"].browse([vals.get("meeting_id") for vals in vals_list])
        if any(meeting.state in ("approved", "cancelled") for meeting in meetings):
            raise UserError(_("Agenda items cannot be added to approved or cancelled meetings."))
        values_list = []
        for original_vals in vals_list:
            vals = dict(original_vals)
            if vals.get("agenda_type_id"):
                kind = self.env["community.meeting.agenda.type"].browse(vals["agenda_type_id"]).behavior
                vals["kind"] = kind
            else:
                kind = vals.get("kind") or self.default_get(["kind"]).get("kind", "discussion")
                agenda_type = self.env["community.meeting.agenda.type"].search(
                    [("behavior", "=", kind), ("active", "=", True)], order="sequence, id", limit=1,
                )
                vals["agenda_type_id"] = agenda_type.id
            if kind == "decision":
                vals.setdefault("decision_result", "pending")
                if vals.get("decision_result") in ("approved", "denied"):
                    vals["disposition"] = "closed"
                elif vals.get("disposition") == "deferred":
                    vals["decision_result"] = "pending"
            else:
                vals.pop("decision_result", None)
            values_list.append(vals)
        return super().create(values_list)

    def write(self, vals):
        if "meeting_id" in vals and any(item.meeting_id.id != vals["meeting_id"] for item in self):
            raise UserError(_("An agenda item cannot be moved to another meeting."))
        if "carryover_id" in vals:
            raise UserError(_("An agenda item's carryover link cannot be changed."))
        if any(item.meeting_id.state in ("approved", "cancelled") for item in self):
            raise UserError(_("Agenda items in approved or cancelled meetings cannot be edited."))
        if "agenda_type_id" in vals:
            agenda_type = self.env["community.meeting.agenda.type"].browse(vals["agenda_type_id"])
            vals = dict(vals, kind=agenda_type.behavior)
        elif "kind" in vals:
            agenda_type = self.env["community.meeting.agenda.type"].search(
                [("behavior", "=", vals["kind"]), ("active", "=", True)], order="sequence, id", limit=1,
            )
            if agenda_type:
                vals = dict(vals, agenda_type_id=agenda_type.id)
        if "kind" in vals:
            for item in self:
                item_vals = dict(vals)
                if vals["kind"] == "decision" and item.kind != "decision":
                    item_vals.setdefault("decision_result", "pending")
                    if item.disposition == "closed":
                        item_vals["disposition"] = "open"
                elif vals["kind"] != "decision":
                    item_vals["decision_result"] = False
                if item_vals.get("disposition") == "deferred":
                    item_vals["decision_result"] = "pending" if vals["kind"] == "decision" else False
                elif item_vals.get("decision_result") in ("approved", "denied"):
                    item_vals["disposition"] = "closed"
                super(CommunityMeetingAgendaItem, item).write(item_vals)
            return True
        values = dict(vals)
        if values.get("disposition") == "deferred":
            values.pop("decision_result", None)
            result = super().write(values)
            decisions = self.filtered(lambda item: item.kind == "decision")
            if decisions:
                super(CommunityMeetingAgendaItem, decisions).write({"decision_result": "pending"})
            return result
        if values.get("decision_result") in ("approved", "denied"):
            values["disposition"] = "closed"
        return super().write(values)

    def unlink(self):
        if any(item.meeting_id.state not in ("draft", "cancelled") for item in self):
            raise UserError(_("Agenda items can only be deleted from draft meetings."))
        if any(item.carryover_id.status == "accepted" for item in self if item.carryover_id):
            raise UserError(_("An accepted carryover agenda item cannot be deleted."))
        return super().unlink()

    def action_request_followup(self):
        self.ensure_one()
        self.check_access("write")
        if self.meeting_id.state in ("approved", "cancelled"):
            raise UserError(_("Agenda items cannot be deferred after approval or cancellation."))
        return self.env["community.meeting.carryover.wizard"].action_open_for(self, "agenda_item")

    def _check_todo_has_followup_action(self):
        for item in self.filtered(lambda row: row.kind == "todo" and row.disposition == "closed"):
            if not item._followup_actions():
                raise ValidationError(_("A resolved TODO must keep at least one non-cancelled follow-up task."))

    def _consume_review(self):
        # Scheduling metadata may change after approval; snapshots remain immutable.
        return super().write({'review_next_meeting': False})

    def _restore_review(self):
        return super().write({'review_next_meeting': True})
