from odoo import fields, models


class CommunityMeeting(models.Model):
    _inherit = "community.meeting"

    meeting_kind = fields.Selection(
        selection_add=[("demo", "Demonstration")],
        ondelete={"demo": "set default"},
    )
    demo_reference = fields.Char()


class CommunityMeetingRevision(models.Model):
    _inherit = "community.meeting.revision"

    def _get_snapshot_extensions(self, meeting, approver, approved_at):
        payload = super()._get_snapshot_extensions(meeting, approver, approved_at)
        payload["community_meetings_extension_demo"] = {
            "reference": meeting.demo_reference or "",
            "kind": meeting.meeting_kind,
        }
        return payload
