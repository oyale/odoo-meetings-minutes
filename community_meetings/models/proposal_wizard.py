from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CommunityMeetingProposalAcceptWizard(models.TransientModel):
    _name = "community.meeting.proposal.accept.wizard"
    _description = "Accept Agenda Proposal"

    proposal_id = fields.Many2one("community.meeting.agenda.proposal", required=True, readonly=True)
    meeting_id = fields.Many2one(
        "community.meeting", required=True,
        domain="[('state', '=', 'draft'), ('company_id', '=', proposal_company_id), ('series_id', '=', proposal_series_id)]",
    )
    proposal_company_id = fields.Many2one(related="proposal_id.company_id", readonly=True)
    proposal_series_id = fields.Many2one(related="proposal_id.series_id", readonly=True)

    def action_accept(self):
        self.ensure_one()
        if not self.meeting_id:
            raise ValidationError(_("Choose an accessible draft meeting."))
        self.proposal_id.action_accept(self.meeting_id.id)
        return {"type": "ir.actions.act_window_close"}
