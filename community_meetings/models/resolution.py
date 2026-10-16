from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CommunityMeetingResolution(models.Model):
    _name = "community.meeting.resolution"
    _description = "Meeting Resolution"
    _order = "id desc"
    _check_company_auto = True

    meeting_id = fields.Many2one(
        "community.meeting", required=True, ondelete="cascade", index=True,
        check_company=True,
    )
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, index=True)
    agenda_item_id = fields.Many2one(
        "community.meeting.agenda.item", ondelete="restrict", check_company=True,
        required=True,
    )
    title = fields.Char(required=True)
    body = fields.Html()
    decision_outcome = fields.Selection(
        [("approved", "Approved"), ("denied", "Rejected")],
        string="Decision result", copy=False,
    )
    status = fields.Selection(
        [("active", "Active"), ("superseded", "Superseded"), ("withdrawn", "Withdrawn")],
        default="active", required=True,
    )
    replacement_resolution_id = fields.Many2one(
        "community.meeting.resolution", ondelete="restrict", check_company=True,
    )
    dissent_ids = fields.One2many(
        "community.meeting.dissent", "resolution_id", groups="community_meetings.group_meeting_editor",
    )
    carryover_ids = fields.One2many(
        "community.meeting.carryover", "origin_resolution_id",
        groups="community_meetings.group_meeting_editor",
    )

    def init(self):
        self.env.cr.execute("""CREATE UNIQUE INDEX IF NOT EXISTS community_meeting_one_active_decision
            ON community_meeting_resolution(agenda_item_id)
            WHERE status='active' AND decision_outcome IS NOT NULL""")

    @api.constrains("meeting_id", "agenda_item_id", "replacement_resolution_id")
    def _check_links(self):
        for resolution in self:
            if resolution.agenda_item_id and resolution.agenda_item_id.meeting_id != resolution.meeting_id:
                raise ValidationError(_("A resolution's agenda item must belong to the same meeting."))
            if resolution.replacement_resolution_id and resolution.replacement_resolution_id.meeting_id != resolution.meeting_id:
                raise ValidationError(_("A replacement resolution must belong to the same meeting."))

    @api.constrains("decision_outcome", "agenda_item_id", "status")
    def _check_decision_outcome(self):
        for resolution in self.filtered("decision_outcome"):
            item = resolution.agenda_item_id
            if not item or (resolution.status == "active" and item.kind != "decision"):
                raise ValidationError(_("A decision result requires a decision agenda point."))
            if resolution.status == "active" and item.is_followup:
                raise ValidationError(_('Reopen this point before recording a new decision.'))
            if resolution.status == "active" and self.search_count([
                ("agenda_item_id", "=", item.id), ("status", "=", "active"),
                ("decision_outcome", "!=", False), ("id", "!=", resolution.id),
            ]):
                raise ValidationError(_("Only one active agreement can determine a point's decision. Edit or withdraw the existing agreement first."))

    def _sync_decision_items(self, items):
        for item in items.filtered(lambda point: point.kind == "decision" and point.meeting_id.state not in ("approved", "cancelled")):
            agreement = self.search([
                ("agenda_item_id", "=", item.id), ("status", "=", "active"),
                ("decision_outcome", "!=", False),
            ], limit=1)
            if agreement:
                item._write_workflow_result({"decision_result": agreement.decision_outcome, "disposition": "closed"})
            elif item.decision_result in ("approved", "denied"):
                if item.topic_id.state == 'closed':
                    item.topic_id._reopen(_('Decision agreement withdrawn.'))
                item._write_workflow_result({"decision_result": "pending", "disposition": "discussed"})

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("You are not allowed to create resolutions."))
        if any(not vals.get("agenda_item_id") for vals in vals_list):
            raise ValidationError(_("A resolution must be linked to an agenda point."))
        meetings = self.env["community.meeting"].browse([vals.get("meeting_id") for vals in vals_list])
        if any(meeting.state in ("approved", "cancelled") for meeting in meetings):
            raise UserError(_("Resolutions cannot be added to approved or cancelled meetings."))
        # Serialize before inserting: retain a clear ORM error as well as the SQL guard.
        item_ids = sorted({v['agenda_item_id'] for v in vals_list if v.get('agenda_item_id') and v.get('decision_outcome') and v.get('status', 'active') == 'active'})
        for item_id in item_ids:
            self.env.cr.execute('SELECT id FROM community_meeting_agenda_item WHERE id=%s FOR UPDATE', [item_id])
            if self.search_count([('agenda_item_id', '=', item_id), ('status', '=', 'active'), ('decision_outcome', '!=', False)]):
                raise ValidationError(_('Only one active agreement can determine a point decision.'))
        records = super().create(vals_list)
        records._sync_decision_items(records.agenda_item_id)
        return records

    def write(self, vals):
        if "meeting_id" in vals and any(record.meeting_id.id != vals["meeting_id"] for record in self):
            raise UserError(_("A resolution cannot be moved to another meeting."))
        if any(record.meeting_id.state in ("approved", "cancelled") for record in self):
            raise UserError(_("Resolutions in approved or cancelled meetings cannot be edited."))
        items = self.agenda_item_id
        result = super().write(vals)
        if {"decision_outcome", "status", "agenda_item_id"} & vals.keys():
            self._sync_decision_items(items | self.agenda_item_id)
        return result

    def unlink(self):
        if any(record.meeting_id.state not in ("draft", "cancelled") for record in self):
            raise UserError(_("Resolutions can only be deleted from draft meetings."))
        items = self.agenda_item_id
        result = super().unlink()
        self._sync_decision_items(items)
        return result

    def action_request_followup(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return self.env["community.meeting.carryover.wizard"].action_open_for(self, "resolution")
