from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CommunityMeetingAction(models.Model):
    _name = "community.meeting.action"
    _description = "Meeting Follow-up Action"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "deadline, id"
    _check_company_auto = True

    meeting_id = fields.Many2one(
        "community.meeting", required=True, ondelete="cascade", index=True,
        check_company=True,
    )
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, index=True)
    resolution_id = fields.Many2one(
        "community.meeting.resolution", ondelete="restrict", check_company=True,
    )
    agenda_item_id = fields.Many2one("community.meeting.agenda.item", ondelete="restrict", check_company=True)
    topic_id = fields.Many2one(related="agenda_item_id.topic_id", store=True, index=True)
    name = fields.Char(required=True)
    description = fields.Html()
    responsible_user_id = fields.Many2one("res.users", default=lambda self: self.env.user, check_company=True, tracking=True)
    deadline = fields.Date(tracking=True)
    state = fields.Selection(
        [("open", "Open"), ("in_progress", "In Progress"), ("done", "Done"), ("cancelled", "Cancelled")],
        default="open", required=True, tracking=True,
    )
    completed_on = fields.Date()
    carryover_ids = fields.One2many(
        "community.meeting.carryover", "origin_action_id",
        groups="community_meetings.group_meeting_editor",
    )

    @api.constrains("meeting_id", "resolution_id", "agenda_item_id", "state", "completed_on")
    def _check_links_and_completion(self):
        for action in self:
            if action.resolution_id and action.resolution_id.meeting_id != action.meeting_id:
                raise ValidationError(_("An action's resolution must belong to the same meeting."))
            if action.agenda_item_id and action.agenda_item_id.meeting_id != action.meeting_id:
                raise ValidationError(_("An action's agenda point must belong to the same meeting."))
            if action.completed_on and action.state != "done":
                raise ValidationError(_("Only completed actions can have a completion date."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("You are not allowed to create follow-up actions."))
        meetings = self.env["community.meeting"].browse([vals.get("meeting_id") for vals in vals_list])
        if any(meeting.state in ("approved", "cancelled") for meeting in meetings):
            raise UserError(_("Actions cannot be added to approved or cancelled meetings."))
        return super().create(vals_list)

    def write(self, vals):
        if "meeting_id" in vals and any(record.meeting_id.id != vals["meeting_id"] for record in self):
            raise UserError(_("An action cannot be moved to another meeting."))
        if any(record.meeting_id.state == "cancelled" and not record.topic_id for record in self):
            raise UserError(_("Actions in cancelled meetings cannot be edited."))
        agenda_items = self.mapped("agenda_item_id")
        topics_before = agenda_items.topic_id
        if vals.get('agenda_item_id'):
            target = self.env['community.meeting.agenda.item'].browse(vals['agenda_item_id'])
            target.check_access('read')
            topics_before |= target.topic_id
        for topic in topics_before.sorted('id'):
            topic._lock_workflow()
        result = super().write(vals)
        topics = (agenda_items | self.mapped("agenda_item_id")).mapped('topic_id')
        self.env['community.meeting.agenda.item'].sudo().search([('topic_id', 'in', topics.ids)])._check_todo_has_followup_action()
        return result

    def unlink(self):
        if any(record.meeting_id.state not in ("draft", "cancelled") for record in self):
            raise UserError(_("Actions can only be deleted from draft meetings."))
        topics = self.mapped('topic_id')
        for topic in topics.sorted('id'):
            topic._lock_workflow()
        for item in self.env['community.meeting.agenda.item'].sudo().search([
            ('topic_id', 'in', topics.ids), ('kind', '=', 'todo'), ('disposition', '=', 'closed')]):
            remaining = item._followup_actions() - self
            if not remaining:
                raise ValidationError(_("A resolved TODO must keep at least one non-cancelled follow-up task."))
        return super().unlink()

    def action_request_followup(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return self.env["community.meeting.carryover.wizard"].action_open_for(self, "action")
