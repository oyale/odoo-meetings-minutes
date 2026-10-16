from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CommunityMeetingSeries(models.Model):
    _name = "community.meeting.series"
    _description = "Community Meeting Series"
    _order = "name, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True,
    )
    meeting_kind = fields.Selection(
        [("operational", "Operational")], default="operational", required=True,
    )
    coordinator_user_ids = fields.Many2many(
        "res.users", "community_meeting_series_coordinator_rel",
        "series_id", "user_id", string="Coordinators", check_company=True,
    )
    carryover_policy = fields.Selection(
        [("review", "Review"), ("automatic", "Automatic"), ("manual", "Manual")],
        default="review", required=True,
    )

    _sql_constraints = [
        ("name_company_unique", "unique(company_id, name)", "Series names must be unique per company."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("Only meeting editors can create a meeting series."))
        for vals in vals_list:
            coordinators = vals.get("coordinator_user_ids", [])
            commands = coordinators if isinstance(coordinators, list) else []
            if not self.env.user.has_group("community_meetings.group_meeting_manager") and not commands:
                vals["coordinator_user_ids"] = [(4, self.env.uid)]
        return super().create(vals_list)

    def write(self, vals):
        if "company_id" in vals and any(series.company_id.id != vals["company_id"] for series in self):
            raise UserError(_("A meeting series cannot be moved to another company."))
        if not self.env.user.has_group("community_meetings.group_meeting_manager"):
            if any(self.env.user not in series.coordinator_user_ids for series in self):
                raise UserError(_("Only a series coordinator or meeting manager can edit this series."))
        return super().write(vals)

    def unlink(self):
        if any(self.env["community.meeting"].search_count([("series_id", "=", series.id)]) for series in self):
            raise ValidationError(_("A series with meetings cannot be deleted."))
        return super().unlink()
