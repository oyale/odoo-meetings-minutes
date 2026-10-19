from typing import ClassVar

from odoo import fields, models


class CommunityMeetingMinutesApproval(models.Model):
    _name = "community.meeting.minutes.approval"
    _description = "Approved Previous Minutes"
    _check_company_auto = True

    agenda_item_id = fields.Many2one(
        "community.meeting.agenda.item",
        required=True,
        ondelete="cascade",
        index=True,
    )
    meeting_id = fields.Many2one(
        "community.meeting",
        string="Approved meeting",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, index=True)

    _sql_constraints: ClassVar[list[tuple[str, str, str]]] = [
        (
            "point_meeting_unique",
            "unique(agenda_item_id, meeting_id)",
            "This meeting's minutes are already recorded for this point.",
        )
    ]
