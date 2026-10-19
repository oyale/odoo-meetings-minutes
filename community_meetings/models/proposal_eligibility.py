from typing import ClassVar

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class CommunityMeetingProposalGroupPolicy(models.Model):
    _name = "community.meeting.proposal.group.policy"
    _description = "Authorized Agenda Proposer Group"

    group_id = fields.Many2one("res.groups", required=True, ondelete="cascade")
    active = fields.Boolean(default=True)

    _sql_constraints: ClassVar[list[tuple[str, str, str]]] = [
        (
            "group_unique",
            "unique(group_id)",
            "A user group can have only one proposal policy.",
        ),
    ]


class CommunityMeetingProposalGrant(models.Model):
    _name = "community.meeting.proposal.grant"
    _description = "Agenda Proposal Eligibility Grant"
    _inherit: ClassVar[list[str]] = ["mail.thread"]
    _order = "id desc"
    _check_company_auto = True

    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    series_id = fields.Many2one("community.meeting.series", ondelete="cascade", check_company=True)
    active_from = fields.Date()
    active_until = fields.Date(tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    granted_by_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)

    @api.constrains("company_id", "series_id", "active_from", "active_until")
    def _check_grant_scope(self):
        for grant in self:
            if grant.series_id and grant.series_id.company_id != grant.company_id:
                raise ValidationError(_("The grant's series must belong to the same company."))
            if grant.active_from and grant.active_until and grant.active_until < grant.active_from:
                raise ValidationError(_("A grant cannot end before it starts."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_manager"):
            for vals in vals_list:
                series = self.env["community.meeting.series"].browse(vals.get("series_id"))
                if not series or self.env.user not in series.coordinator_user_ids:
                    raise AccessError(_("Only a meeting manager or series coordinator can grant proposal access."))
        for vals in vals_list:
            vals["granted_by_id"] = self.env.uid
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.user.has_group("community_meetings.group_meeting_manager") and any(
            not grant.series_id or self.env.user not in grant.series_id.coordinator_user_ids for grant in self
        ):
            raise AccessError(_("Only a meeting manager or series coordinator can change this grant."))
        if {"granted_by_id", "partner_id", "company_id", "series_id"}.intersection(vals):
            raise UserError(_("Grant identity and scope cannot be changed; revoke it and create a new grant."))
        return super().write(vals)
