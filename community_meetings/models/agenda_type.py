from odoo import _, fields, models
from odoo.exceptions import UserError


class CommunityMeetingAgendaType(models.Model):
    _name = "community.meeting.agenda.type"
    _description = "Meeting Agenda Point Type"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    behavior = fields.Selection(
        [("information", "Informational"), ("discussion", "Discussion"), ("decision", "Decision"), ("todo", "TODO"),
         ("minutes_approval", "Minutes Approval"), ("next_meeting", "Next Meeting"), ("followup", "Follow-up")],
        required=True, default="discussion",
        help="Controls which meeting workflow fields apply to points using this type.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [("name_unique", "unique(name)", "Agenda point type names must be unique.")]

    def write(self, vals):
        if "behavior" in vals and any(
            item.agenda_type_id for item in self.env["community.meeting.agenda.item"].sudo().search([
                ("agenda_type_id", "in", self.ids),
            ])
        ):
            raise UserError(_("The workflow behavior of a type already in use cannot be changed."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Agenda point types are shared configuration and cannot be deleted. Archive unused types instead."))
