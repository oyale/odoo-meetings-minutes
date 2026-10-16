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
    )
    title = fields.Char(required=True)
    body = fields.Html()
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

    @api.constrains("meeting_id", "agenda_item_id", "replacement_resolution_id")
    def _check_links(self):
        for resolution in self:
            if resolution.agenda_item_id and resolution.agenda_item_id.meeting_id != resolution.meeting_id:
                raise ValidationError(_("A resolution's agenda item must belong to the same meeting."))
            if resolution.replacement_resolution_id and resolution.replacement_resolution_id.meeting_id != resolution.meeting_id:
                raise ValidationError(_("A replacement resolution must belong to the same meeting."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("You are not allowed to create resolutions."))
        meetings = self.env["community.meeting"].browse([vals.get("meeting_id") for vals in vals_list])
        if any(meeting.state in ("approved", "cancelled") for meeting in meetings):
            raise UserError(_("Resolutions cannot be added to approved or cancelled meetings."))
        return super().create(vals_list)

    def write(self, vals):
        if "meeting_id" in vals and any(record.meeting_id.id != vals["meeting_id"] for record in self):
            raise UserError(_("A resolution cannot be moved to another meeting."))
        if any(record.meeting_id.state in ("approved", "cancelled") for record in self):
            raise UserError(_("Resolutions in approved or cancelled meetings cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if any(record.meeting_id.state not in ("draft", "cancelled") for record in self):
            raise UserError(_("Resolutions can only be deleted from draft meetings."))
        return super().unlink()

    def action_request_followup(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return self.env["community.meeting.carryover.wizard"].action_open_for(self, "resolution")
