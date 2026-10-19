from typing import ClassVar

from odoo import fields, models


class CommunityMeetingFollowupKind(models.Model):
    _name = "community.meeting.followup.kind"
    _description = "Meeting Follow-up Kind"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints: ClassVar[list[tuple[str, str, str]]] = [
        (
            "community_meeting_followup_kind_code_uniq",
            "unique(code)",
            "A follow-up kind with this code already exists.",
        ),
    ]
