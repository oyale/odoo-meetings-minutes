from typing import ClassVar

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CommunityMeetingEditorNote(models.Model):
    _name = "community.meeting.editor.note"
    _description = "Restricted Meeting Editorial Note"
    _order = "id"
    _check_company_auto = True

    meeting_id = fields.Many2one(
        "community.meeting", required=True, ondelete="cascade", index=True, check_company=True
    )
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, index=True)
    agenda_item_id = fields.Many2one("community.meeting.agenda.item", ondelete="cascade", check_company=True)
    content = fields.Html(required=True)
    created_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    create_date = fields.Datetime(readonly=True)

    @api.constrains("meeting_id", "agenda_item_id")
    def _check_scope(self):
        for note in self:
            if note.agenda_item_id and note.agenda_item_id.meeting_id != note.meeting_id:
                raise ValidationError(_("An editorial note's agenda item must belong to the same meeting."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("Only meeting editors can add editorial notes."))
        for vals in vals_list:
            vals["created_by_id"] = self.env.uid
            meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
            if meeting.state in ("approved", "cancelled"):
                raise UserError(_("Editorial notes cannot be added after approval or cancellation."))
        return super().create(vals_list)

    def write(self, vals):
        if any(note.meeting_id.state in ("approved", "cancelled") for note in self):
            raise UserError(_("Editorial notes are locked after approval or cancellation."))
        if {"meeting_id", "agenda_item_id", "created_by_id"}.intersection(vals):
            raise UserError(_("An editorial note's scope and author cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if any(note.meeting_id.state not in ("draft", "cancelled") for note in self):
            raise UserError(_("Editorial notes can only be deleted from draft meetings."))
        return super().unlink()


class CommunityMeetingDissentReason(models.Model):
    _name = "community.meeting.dissent.reason"
    _description = "Dissent Reason"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints: ClassVar[list[tuple[str, str, str]]] = [
        ("name_unique", "unique(name)", "Dissent reason names must be unique.")
    ]


class CommunityMeetingDissent(models.Model):
    _name = "community.meeting.dissent"
    _description = "Meeting Dissent or Reservation"
    _order = "sequence, id"
    _check_company_auto = True

    meeting_id = fields.Many2one(
        "community.meeting", required=True, ondelete="cascade", index=True, check_company=True
    )
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, index=True)
    agenda_item_id = fields.Many2one("community.meeting.agenda.item", ondelete="restrict", check_company=True)
    resolution_id = fields.Many2one("community.meeting.resolution", ondelete="restrict", check_company=True)
    body = fields.Html(required=True)
    author_partner_id = fields.Many2one("res.partner")
    author_display_name = fields.Char()
    recorded_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    recorded_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    reason_id = fields.Many2one(
        "community.meeting.dissent.reason",
        string="Statement type",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.ref("community_meetings.dissent_reason_dissent", raise_if_not_found=False),
    )
    sequence = fields.Integer(default=10)

    @api.constrains("meeting_id", "agenda_item_id", "resolution_id")
    def _check_scope(self):
        for dissent in self:
            if not dissent.agenda_item_id and not dissent.resolution_id:
                raise ValidationError(_("A dissent must be linked to an agenda point or an agreement."))
            if dissent.agenda_item_id and dissent.agenda_item_id.meeting_id != dissent.meeting_id:
                raise ValidationError(_("A dissent's agenda item must belong to the same meeting."))
            if dissent.resolution_id and dissent.resolution_id.meeting_id != dissent.meeting_id:
                raise ValidationError(_("A dissent's resolution must belong to the same meeting."))
            if (
                dissent.resolution_id
                and dissent.agenda_item_id
                and dissent.resolution_id.agenda_item_id != dissent.agenda_item_id
            ):
                raise ValidationError(_("A dissent's resolution must belong to the selected agenda item."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("Only meeting editors can record dissent."))
        for vals in vals_list:
            vals["recorded_by_id"] = self.env.uid
            vals["recorded_at"] = fields.Datetime.now()
            meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
            if meeting.state in ("approved", "cancelled"):
                raise UserError(_("Dissent cannot be added after approval or cancellation."))
        return super().create(vals_list)

    def write(self, vals):
        if any(record.meeting_id.state in ("approved", "cancelled") for record in self):
            raise UserError(_("Dissent in approved or cancelled meetings cannot be edited."))
        if {"meeting_id", "agenda_item_id", "resolution_id", "recorded_by_id", "recorded_at"}.intersection(vals):
            raise UserError(_("Dissent scope and recording attribution cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if any(record.meeting_id.state not in ("draft", "cancelled") for record in self):
            raise UserError(_("Dissent can only be deleted from draft meetings."))
        return super().unlink()
