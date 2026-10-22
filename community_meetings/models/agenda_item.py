from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# Only server-owned insertion of a required approval point may cross the
# ordinary addition deadline. A JSON/RPC context value cannot supply this token.
_REQUIRED_MINUTES_APPROVAL_CREATION = object()


class CommunityMeetingAgendaItem(models.Model):
    _name = "community.meeting.agenda.item"
    _description = "Meeting Agenda Item"
    _order = "sequence, id"
    _check_company_auto = True

    meeting_id = fields.Many2one(
        "community.meeting",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    reorderable = fields.Boolean(default=True, string="Can be reordered")
    can_move_up = fields.Boolean(compute="_compute_reorder_neighbors")
    can_move_down = fields.Boolean(compute="_compute_reorder_neighbors")
    name = fields.Char(required=True)
    kind = fields.Selection(
        [
            ("information", "Information"),
            ("discussion", "Discussion"),
            ("decision", "Decision"),
            ("todo", "TODO"),
            ("minutes_approval", "Minutes Approval"),
            ("next_meeting", "Next Meeting"),
            ("followup", "Follow-up"),
        ],
        default="discussion",
        required=True,
    )
    agenda_type_id = fields.Many2one(
        "community.meeting.agenda.type",
        string="Point type",
        required=True,
        default=lambda self: self.env.ref("community_meetings.agenda_type_discussion", raise_if_not_found=False),
        ondelete="restrict",
        domain="[('active', '=', True)]",
    )
    description = fields.Html()
    discussion_notes = fields.Html()
    presenter_partner_id = fields.Many2one(
        "res.partner",
        related="topic_id.presenter_partner_id",
        readonly=False,
    )
    disposition = fields.Selection(
        [
            ("open", "Open"),
            ("discussed", "Treated / Discussed"),
            ("deferred", "Postponed"),
            ("closed", "Resolved"),
        ],
        default="open",
        required=True,
    )
    decision_result = fields.Selection(
        [
            ("pending", "Pending Decision"),
            ("approved", "Approved"),
            ("denied", "Denied"),
        ],
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
        string="Next meeting date",
        copy=False,
        help="Date chosen for the next meeting by a 'Next Meeting' point.",
    )
    minutes_approval_ids = fields.One2many(
        "community.meeting.minutes.approval",
        "agenda_item_id",
        string="Approved previous minutes",
        copy=False,
    )
    private_note_ids = fields.One2many(
        "community.meeting.editor.note",
        "agenda_item_id",
        groups="community_meetings.group_meeting_editor",
    )
    carryover_id = fields.Many2one(
        "community.meeting.carryover",
        ondelete="restrict",
        copy=False,
        groups="community_meetings.group_meeting_editor",
    )

    @api.constrains("meeting_id")
    def _check_meeting_editable(self):
        if any(item.meeting_id.state in ("approved", "cancelled") for item in self):
            raise ValidationError(_("Agenda items cannot be added to approved or cancelled meetings."))

    @api.depends(
        "sequence",
        "kind",
        "reorderable",
        "meeting_id.reorder_points_allowed",
        "meeting_id.agenda_item_ids.sequence",
        "meeting_id.agenda_item_ids.kind",
        "meeting_id.agenda_item_ids.reorderable",
    )
    def _compute_reorder_neighbors(self):
        for item in self:
            item.can_move_up = False
            item.can_move_down = False
        for meeting in self.mapped("meeting_id"):
            items = meeting.agenda_item_ids.sorted(lambda row: row.sequence)
            positions = {item.id: index for index, item in enumerate(items)}
            meeting_item_ids = [row.id for row in self if row.meeting_id == meeting]
            for item in self.browse(meeting_item_ids):
                index = positions.get(item.id, -1)
                movable = (
                    index >= 0
                    and meeting.reorder_points_allowed
                    and item.reorderable
                    and item.kind
                    not in (
                        "minutes_approval",
                        "next_meeting",
                    )
                )
                item.can_move_up = bool(
                    movable
                    and index > 0
                    and items[index - 1].reorderable
                    and items[index - 1].kind not in ("minutes_approval", "next_meeting")
                )
                item.can_move_down = bool(
                    movable
                    and index + 1 < len(items)
                    and items[index + 1].reorderable
                    and items[index + 1].kind not in ("minutes_approval", "next_meeting")
                )

    def _active_workflow_resolutions(self):
        resolutions = self.env["community.meeting.resolution"].search(
            [
                ("agenda_item_id", "in", self.ids),
                ("status", "=", "active"),
                ("decision_outcome", "!=", False),
            ]
        )
        by_item = {}
        for resolution in resolutions:
            by_item.setdefault(resolution.agenda_item_id.id, resolution)
        return by_item

    def _workflow_todo_actions(self, workflow_items):
        todo_items = workflow_items.filtered(lambda row: row.kind == "todo" and row.disposition == "closed")
        return todo_items._followup_actions_by_topic()

    def _check_non_decision_resolution(self, workflow_items, resolutions_by_item):
        if resolutions_by_item is None:
            resolutions_by_item = workflow_items._active_workflow_resolutions()
        if resolutions_by_item.get(self.id):
            raise ValidationError(_("Withdraw the decision agreement before changing the point type."))
        return resolutions_by_item

    def _check_decision_resolution(self, workflow_items, resolutions_by_item):
        if resolutions_by_item is None:
            resolutions_by_item = workflow_items._active_workflow_resolutions()
        agreement = resolutions_by_item.get(self.id)
        if (self.disposition == "closed" or self.decision_result in ("approved", "denied") or agreement) and (
            not agreement or self.decision_result != agreement.decision_outcome or self.disposition != "closed"
        ):
            raise ValidationError(
                _(
                    "Record an active agreement approving or rejecting this "
                    "decision before closing it. The point's result must match "
                    "that agreement."
                )
            )
        return resolutions_by_item

    def _followup_actions_by_topic(self):
        topics = self.topic_id
        if not topics:
            return {}
        action_model = self.env["community.meeting.action"]
        actions_by_topic = {topic.id: action_model for topic in topics}
        actions = self.env["community.meeting.action"].search(
            [
                ("topic_id", "in", topics.ids),
                ("state", "!=", "cancelled"),
                ("responsible_user_id", "!=", False),
            ]
        )
        evidence_by_action = actions._execution_evidence_by_action()
        actions = actions.filtered(lambda action: evidence_by_action.get(action.id))
        if len(topics) == 1:
            return {topics.id: actions}
        actions.mapped("topic_id")
        for action in actions:
            actions_by_topic[action.topic_id.id] |= action
        return actions_by_topic

    def _check_workflow_item(self, workflow_items, state):
        if self.kind != "decision":
            if self.decision_result:
                raise ValidationError(_("Only decision agenda items can have a decision outcome."))
            if state["resolutions"] is None:
                state["resolutions"] = workflow_items._active_workflow_resolutions()
            self._check_non_decision_resolution(workflow_items, state["resolutions"])
        if self.decision_result in ("approved", "denied") and self.disposition != "closed":
            raise ValidationError(_("An approved or denied decision must be marked as resolved."))
        if self.kind == "decision":
            if state["resolutions"] is None:
                state["resolutions"] = workflow_items._active_workflow_resolutions()
            self._check_decision_resolution(workflow_items, state["resolutions"])
        if self.kind == "todo" and self.disposition == "closed":
            if state["todo_actions"] is None:
                state["todo_actions"] = self._workflow_todo_actions(workflow_items)
            if not state["todo_actions"].get(self.topic_id.id):
                raise ValidationError(_("Create a follow-up task for this TODO before resolving it."))

    @api.constrains("kind", "decision_result", "disposition")
    def _check_workflow_requirements(self):
        workflow_items = self
        state = {"resolutions": None, "todo_actions": None}
        for item in self:
            item._check_workflow_item(workflow_items, state)

    def _lock_required_minutes_approval_meetings(self):
        meetings = self.mapped("meeting_id").filtered(
            lambda meeting: meeting.series_id.has_minutes_approval_point and meeting.state != "cancelled"
        )
        if meetings:
            meetings._lock_live_workflow()
            meetings.invalidate_recordset(["agenda_item_ids"])

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
        default_types = {}
        values_list = []
        for original_vals in vals_list:
            vals = dict(original_vals)
            if vals.get("agenda_type_id"):
                kind = self.env["community.meeting.agenda.type"].browse(vals["agenda_type_id"]).behavior
                vals["kind"] = kind
            else:
                kind = vals.get("kind") or self.default_get(["kind"]).get("kind", "discussion")
                if kind not in default_types:
                    default_types[kind] = self.env["community.meeting.agenda.type"].search(
                        [("behavior", "=", kind), ("active", "=", True)],
                        order="sequence, id",
                        limit=1,
                    )
                vals["agenda_type_id"] = default_types[kind].id
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

    @api.model
    def _prepare_agenda_creation(self, vals_list):
        """Validate all destinations before creating their persistent topics."""
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("You are not allowed to edit agendas."))
        defaults = self.default_get(["meeting_id"]) if any("meeting_id" not in vals for vals in vals_list) else {}
        values_list = [{**defaults, **vals} for vals in vals_list]
        meetings = self.env["community.meeting"].browse([vals.get("meeting_id") for vals in values_list])
        meetings.check_access("write")
        meetings._lock_live_workflow()
        meetings.invalidate_recordset(["add_point_policy", "add_point_allowed", "agenda_item_ids"])
        structural = self.env.context.get("_meeting_required_minutes_approval") is _REQUIRED_MINUTES_APPROVAL_CREATION
        for values in values_list:
            meeting = self.env["community.meeting"].browse(values.get("meeting_id"))
            kind = (
                self.env["community.meeting.agenda.type"].browse(values["agenda_type_id"]).behavior
                if values.get("agenda_type_id")
                else values.get("kind")
            )
            required_approval = (
                structural
                and kind == "minutes_approval"
                and not values.get("topic_id")
                and meeting.series_id.has_minutes_approval_point
                and meeting.state in ("draft", "scheduled", "held", "minutes_draft")
                and not meeting.agenda_item_ids.filtered(lambda row: row.kind == "minutes_approval")
            )
            if not meeting.add_point_allowed and not required_approval:
                raise UserError(_("New points cannot be added to this meeting anymore."))
        return values_list

    # Keep these checks ordered at the workflow boundary for live point writes.
    def write(self, vals):  # noqa: C901
        if "sequence" in vals:
            meetings = self.mapped("meeting_id")
            if len(meetings) != 1:
                raise ValidationError(_("Agenda points can only be reordered within one meeting."))
            meeting = meetings.ensure_one()
            meeting.check_access("write")
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise AccessError(_("Only meeting editors can reorder agenda points."))
            meeting._lock_live_workflow()
            meeting.invalidate_recordset(["state", "agenda_item_ids", "reorder_points_allowed"])
            if not meeting.reorder_points_allowed:
                raise UserError(_("Agenda points can no longer be reordered for this meeting."))
            all_items = meeting.agenda_item_ids.sorted(lambda item: (item.sequence, item.id))
            structural_positions = [
                (index, item.id)
                for index, item in enumerate(all_items)
                if not item.reorderable or item.kind in ("minutes_approval", "next_meeting")
            ]
            proposed_sequences = {item.id: vals["sequence"] for item in self}
            proposed = all_items.sorted(lambda item: (proposed_sequences.get(item.id, item.sequence), item.id))
            proposed_structural_positions = [
                (index, item.id)
                for index, item in enumerate(proposed)
                if not item.reorderable or item.kind in ("minutes_approval", "next_meeting")
            ]
            if proposed_structural_positions != structural_positions:
                raise ValidationError(_("Fixed agenda points must keep their positions."))
        if "meeting_id" in vals and any(item.meeting_id.id != vals["meeting_id"] for item in self):
            raise UserError(_("An agenda item cannot be moved to another meeting."))
        if "carryover_id" in vals:
            raise UserError(_("An agenda item's carryover link cannot be changed."))
        if any(item.meeting_id.state in ("approved", "cancelled") for item in self):
            raise UserError(_("Agenda items in approved or cancelled meetings cannot be edited."))
        if "agenda_type_id" in vals or "kind" in vals:
            self._lock_required_minutes_approval_meetings()
            destination_type = (
                self.env["community.meeting.agenda.type"].browse(vals["agenda_type_id"])
                if vals.get("agenda_type_id")
                else self.env["community.meeting.agenda.type"].search(
                    [("behavior", "=", vals.get("kind")), ("active", "=", True)],
                    order="sequence, id",
                    limit=1,
                )
            )
            destination_kind = destination_type.behavior if destination_type else vals.get("kind")
            if destination_kind != "minutes_approval":
                meetings = self.mapped("meeting_id")
                removing = self.filtered(lambda item: item.kind == "minutes_approval")
                for meeting in meetings:
                    required = meeting.series_id.has_minutes_approval_point and meeting.state != "cancelled"
                    remaining = meeting.agenda_item_ids.filtered(
                        lambda item: item.kind == "minutes_approval" and item not in removing
                    )
                    if required and not remaining:
                        raise UserError(_("A meeting in this series must keep its minutes approval point."))
        if "agenda_type_id" in vals:
            agenda_type = self.env["community.meeting.agenda.type"].browse(vals["agenda_type_id"])
            vals = dict(vals, kind=agenda_type.behavior)
        elif "kind" in vals:
            agenda_type = self.env["community.meeting.agenda.type"].search(
                [("behavior", "=", vals["kind"]), ("active", "=", True)],
                order="sequence, id",
                limit=1,
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

    def action_move_agenda_item(self, direction=None):
        self.ensure_one()
        direction = direction if direction is not None else self.env.context.get("direction")
        if direction not in (-1, 1):
            raise ValidationError(_("Choose whether to move the point up or down."))
        meeting = self.meeting_id
        meeting.check_access("write")
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise AccessError(_("Only meeting editors can reorder agenda points."))
        if not meeting.reorder_points_allowed:
            raise UserError(_("Agenda points can no longer be reordered for this meeting."))
        items = meeting.agenda_item_ids.sorted(lambda item: (item.sequence, item.id))
        index = items.ids.index(self.id)
        other_index = index + direction
        if not 0 <= other_index < len(items):
            return True
        other = items[other_index]
        fixed_kind = ("minutes_approval", "next_meeting")
        if not self.reorderable or not other.reorderable or self.kind in fixed_kind or other.kind in fixed_kind:
            return True
        ordered_ids = items.ids
        ordered_ids[index], ordered_ids[other_index] = ordered_ids[other_index], ordered_ids[index]
        return meeting.action_reorder_agenda_items(ordered_ids)

    def unlink(self):
        if any(item.meeting_id.state not in ("draft", "cancelled") for item in self):
            raise UserError(_("Agenda items can only be deleted from draft meetings."))
        if any(item.carryover_id.status == "accepted" for item in self if item.carryover_id):
            raise UserError(_("An accepted carryover agenda item cannot be deleted."))
        self._lock_required_minutes_approval_meetings()
        for meeting in self.mapped("meeting_id"):
            approval_points = meeting.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
            if (
                meeting.series_id.has_minutes_approval_point
                and meeting.state != "cancelled"
                and approval_points
                and not (approval_points - self)
            ):
                raise UserError(_("A meeting in this series must keep its minutes approval point."))
        return super().unlink()

    def action_request_followup(self):
        self.ensure_one()
        self.check_access("write")
        if self.meeting_id.state in ("approved", "cancelled"):
            raise UserError(_("Agenda items cannot be deferred after approval or cancellation."))
        return self.env["community.meeting.carryover.wizard"].action_open_for(self, "agenda_item")

    def _check_todo_has_followup_action(self):
        items = self.filtered(lambda row: row.kind == "todo" and row.disposition == "closed")
        actions_by_topic = items._followup_actions_by_topic()
        for item in items:
            if not actions_by_topic.get(item.topic_id.id):
                raise ValidationError(_("A resolved TODO must keep at least one non-cancelled follow-up task."))

    def _consume_review(self):
        # Scheduling metadata may change after approval; snapshots remain immutable.
        return super().write({"review_next_meeting": False})

    def _restore_review(self):
        return super().write({"review_next_meeting": True})
