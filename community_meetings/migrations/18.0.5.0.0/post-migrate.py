from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute(
        "UPDATE community_meeting_action SET followup_kind = 'activity' "
        "WHERE followup_kind IN ('todo', 'task')"
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    stale = env["community.meeting.action"].search([
        ("followup_kind", "=", "activity"),
        ("state", "not in", ("done", "cancelled")),
        ("followup_activity_id", "=", False),
    ])
    stale._sync_followup_activity()
