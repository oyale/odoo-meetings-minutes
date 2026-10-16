from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class CommunityMeetingProposalGroupPolicy(models.Model):
    _name = "community.meeting.proposal.group.policy"
    _description = "Authorized Agenda Proposer Group"

    group_id = fields.Many2one("res.groups", required=True, ondelete="cascade")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("group_unique", "unique(group_id)", "A user group can have only one proposal policy."),
    ]


class CommunityMeetingProposalGrant(models.Model):
    _name = "community.meeting.proposal.grant"
    _description = "Agenda Proposal Eligibility Grant"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _check_company_auto = True

    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True,
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
        if not self.env.user.has_group("community_meetings.group_meeting_manager"):
            if any(not grant.series_id or self.env.user not in grant.series_id.coordinator_user_ids for grant in self):
                raise AccessError(_("Only a meeting manager or series coordinator can change this grant."))
        if {"granted_by_id", "partner_id", "company_id", "series_id"}.intersection(vals):
            raise UserError(_("Grant identity and scope cannot be changed; revoke it and create a new grant."))
        return super().write(vals)


class CommunityMeetingAgendaProposal(models.Model):
    _name = "community.meeting.agenda.proposal"
    _description = "Meeting Agenda Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "submitted_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    description = fields.Html()
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True,
    )
    series_id = fields.Many2one("community.meeting.series", ondelete="restrict", check_company=True)
    meeting_id = fields.Many2one("community.meeting", ondelete="restrict", check_company=True)
    proposer_partner_id = fields.Many2one("res.partner", required=True, default=lambda self: self.env.user.partner_id, ondelete="restrict", index=True)
    submitted_by_user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True, index=True)
    status = fields.Selection(
        [("submitted", "Submitted"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("withdrawn", "Withdrawn")],
        default="submitted", required=True, index=True,
    )
    response = fields.Text()
    destination_item_id = fields.Many2one("community.meeting.agenda.item", readonly=True, ondelete="restrict")
    submitted_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    responded_by_id = fields.Many2one("res.users", readonly=True)
    responded_at = fields.Datetime(readonly=True)

    @api.constrains("company_id", "series_id", "meeting_id")
    def _check_target(self):
        for proposal in self:
            series = self.env["community.meeting.series"].sudo().browse(proposal.series_id.id)
            meeting = self.env["community.meeting"].sudo().browse(proposal.meeting_id.id)
            if series and series.company_id != proposal.company_id:
                raise ValidationError(_("The proposal's series must belong to the selected company."))
            if meeting and meeting.company_id != proposal.company_id:
                raise ValidationError(_("The proposal's meeting must belong to the selected company."))
            if meeting and proposal.series_id != meeting.series_id:
                raise ValidationError(_("The proposal's meeting must belong to its selected series."))
            if not proposal.series_id and not proposal.meeting_id:
                raise ValidationError(_("Select a meeting series or a specific meeting for the proposal."))

    @api.model
    def _has_proposal_capability(self):
        user = self.env.user
        if user.has_group("community_meetings.group_agenda_proposer"):
            return True
        policy_groups = self.env["community.meeting.proposal.group.policy"].sudo().search([("active", "=", True)]).group_id
        return bool(user.groups_id & policy_groups)

    @api.model
    def _validate_target(self, company_id, series_id=False, meeting_id=False):
        if company_id not in self.env.user.company_ids.ids:
            raise AccessError(_("You cannot submit proposals for this company."))
        # The target's existence and scope are checked without granting read access to its contents.
        series = self.env["community.meeting.series"].sudo().browse(series_id).exists() if series_id else self.env["community.meeting.series"]
        meeting = self.env["community.meeting"].sudo().browse(meeting_id).exists() if meeting_id else self.env["community.meeting"]
        if series_id and (not series or series.company_id.id != company_id or not series.active):
            raise ValidationError(_("The selected proposal scope is unavailable."))
        if meeting_id and (
            not meeting or meeting.company_id.id != company_id
            or meeting.state not in ("draft", "scheduled")
            or (series_id and meeting.series_id != series)
        ):
            raise ValidationError(_("The selected proposal scope is unavailable."))
        if not series_id and not meeting_id:
            raise ValidationError(_("Choose a meeting series or an upcoming meeting."))
        return series, meeting

    @api.model_create_multi
    def create(self, vals_list):
        if not self._has_proposal_capability():
            raise AccessError(_("You are not authorized to submit agenda proposals."))
        for vals in vals_list:
            if vals.get("proposer_partner_id") and vals["proposer_partner_id"] != self.env.user.partner_id.id:
                raise AccessError(_("You cannot submit a proposal as another contact."))
            if vals.get('submitted_by_user_id') not in (None, False, self.env.uid) or vals.get('status') not in (None, False, 'submitted'):
                raise AccessError(_("Proposal attribution and status are assigned by the server."))
            if any(vals.get(key) for key in ('destination_item_id', 'responded_by_id', 'responded_at', 'response')):
                raise AccessError(_("Proposal attribution and status are assigned by the server."))
            vals["proposer_partner_id"] = self.env.user.partner_id.id
            vals["submitted_by_user_id"] = self.env.uid
            vals["submitted_at"] = fields.Datetime.now()
            vals["status"] = "submitted"
            series, meeting = self._validate_target(
                vals.get("company_id", self.env.company.id), vals.get("series_id"), vals.get("meeting_id"),
            )
            if meeting and not vals.get("series_id") and meeting.series_id:
                vals["series_id"] = meeting.series_id.id
        return super().create(vals_list)

    @api.model
    def submit_on_behalf(self, partner_id, name, description=False, company_id=False, series_id=False, meeting_id=False):
        if not (
            self.env.user.has_group("community_meetings.group_meeting_editor")
            or self.env.user.has_group("community_meetings.group_meeting_manager")
        ):
            raise AccessError(_("Only a meeting editor can record a proposal on behalf of a contact."))
        company_id = company_id or self.env.company.id
        partner = self.env["res.partner"].browse(partner_id).exists()
        if not partner:
            raise ValidationError(_("The proposed contact is unavailable."))
        series, meeting = self._validate_target(company_id, series_id, meeting_id)
        today = fields.Date.context_today(self)
        grant_domain = [
            ("partner_id", "=", partner.id), ("company_id", "=", company_id), ("active", "=", True),
            "|", ("active_from", "=", False), ("active_from", "<=", today),
            "|", ("active_until", "=", False), ("active_until", ">=", today),
        ]
        if series:
            grant_domain += ["|", ("series_id", "=", False), ("series_id", "=", series.id)]
        if meeting and meeting.series_id:
            grant_domain += ["|", ("series_id", "=", False), ("series_id", "=", meeting.series_id.id)]
        grant = self.env["community.meeting.proposal.grant"].sudo().search(grant_domain, limit=1)
        if not grant:
            raise AccessError(_("This contact is not eligible to propose topics in the selected scope."))
        if not self._has_proposal_capability():
            raise AccessError(_("You are not authorized to submit agenda proposals."))
        return super(CommunityMeetingAgendaProposal, self).create({
            "name": name,
            "description": description,
            "company_id": company_id,
            "series_id": series.id if series else False,
            "meeting_id": meeting.id if meeting else False,
            "proposer_partner_id": partner.id,
            "submitted_by_user_id": self.env.uid,
            "submitted_at": fields.Datetime.now(),
            "status": "submitted",
        })

    def write(self, vals):
        raise UserError(_("Use a proposal workflow action to change its status."))

    def unlink(self):
        raise UserError(_("Agenda proposals are retained as an audit record."))

    def _review_access(self):
        if not (
            self.env.user.has_group("community_meetings.group_meeting_editor")
            or self.env.user.has_group("community_meetings.group_meeting_manager")
        ):
            raise AccessError(_("Only meeting editors can review agenda proposals."))

    def action_accept(self, destination_meeting_id=False):
        self.ensure_one()
        self._review_access()
        self.check_access_rights("write")
        self.check_access_rule("write")
        if self.submitted_by_user_id == self.env.user or self.proposer_partner_id == self.env.user.partner_id:
            raise AccessError(_("You cannot accept your own agenda proposal."))
        self.env.cr.execute(
            "SELECT id FROM community_meeting_agenda_proposal WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["status", "destination_item_id"])
        if self.status == "accepted":
            return True
        if self.status != "submitted":
            raise UserError(_("Only submitted proposals can be accepted."))
        meeting_id = destination_meeting_id or self.meeting_id.id
        if not meeting_id:
            raise ValidationError(_("Choose a destination meeting for this proposal."))
        meeting = self.env["community.meeting"].browse(meeting_id)
        meeting.check_access_rights("write")
        meeting.check_access_rule("write")
        if meeting.state != "draft" or meeting.company_id != self.company_id:
            raise ValidationError(_("Proposals can only be accepted into an accessible draft meeting in the same company."))
        if self.series_id and meeting.series_id != self.series_id:
            raise ValidationError(_("Choose a destination meeting in the proposal's series."))
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id,
            "name": self.name,
            "description": self.description,
        })
        super(CommunityMeetingAgendaProposal, self).write({
            "meeting_id": meeting.id,
            "destination_item_id": item.id,
            "status": "accepted",
            "responded_by_id": self.env.uid,
            "responded_at": fields.Datetime.now(),
        })
        return item

    def action_reject(self, response=False):
        self.ensure_one()
        self._review_access()
        self.check_access_rights("write")
        self.check_access_rule("write")
        if self.status != "submitted":
            raise UserError(_("Only submitted proposals can be rejected."))
        super(CommunityMeetingAgendaProposal, self).write({
            "status": "rejected", "response": response,
            "responded_by_id": self.env.uid, "responded_at": fields.Datetime.now(),
        })
        return True

    def action_submit(self):
        self.ensure_one()
        self.check_access('read')
        if self.submitted_by_user_id != self.env.user:
            raise AccessError(_('You can submit only your own proposal.'))
        return True

    def action_withdraw(self):
        self.ensure_one()
        self.check_access_rights("write")
        self.check_access_rule("write")
        if self.status != "submitted" or self.submitted_by_user_id != self.env.user:
            raise AccessError(_("You can withdraw only your own submitted proposal."))
        super(CommunityMeetingAgendaProposal, self).write({
            "status": "withdrawn", "responded_by_id": self.env.uid,
            "responded_at": fields.Datetime.now(),
        })
        return True

    def action_open_accept_wizard(self):
        self.ensure_one()
        self._review_access()
        self.check_access_rights("read")
        self.check_access_rule("read")
        return {
            "type": "ir.actions.act_window",
            "name": _("Accept Agenda Proposal"),
            "res_model": "community.meeting.proposal.accept.wizard",
            "views": [(self.env.ref("community_meetings.view_community_meeting_proposal_accept_wizard").id, "form")],
            "view_mode": "form",
            "target": "new",
            "context": {"default_proposal_id": self.id, "default_meeting_id": self.meeting_id.id},
        }
