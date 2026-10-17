from odoo import _, fields, models
from odoo.exceptions import UserError


class CommunityMeetingKind(models.Model):
    _name = "community.meeting.kind"
    _description = "Meeting Kind"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Stable identifier used by extensions and revision snapshots. Avoid changing it once in use.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Meeting kind codes must be unique."),
        ("name_unique", "unique(name)", "Meeting kind names must be unique."),
    ]

    def _is_in_use(self):
        return bool(
            self.env["community.meeting.series"].sudo().search_count([
                ("meeting_kind_id", "in", self.ids),
            ])
            or self.env["community.meeting"].sudo().search_count([
                ("meeting_kind_id", "in", self.ids),
            ])
        )

    def write(self, vals):
        if "code" in vals and self._is_in_use():
            raise UserError(_("The code of a meeting kind already in use cannot be changed."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Meeting kinds are shared configuration and cannot be deleted. Archive unused kinds instead."))
