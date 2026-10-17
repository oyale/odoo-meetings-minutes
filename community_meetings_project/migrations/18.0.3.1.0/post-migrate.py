from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute(
        "UPDATE community_meeting_action SET followup_kind = 'project_task' "
        "WHERE followup_kind = 'task'"
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.company"].search([]).filtered(lambda c: not c.followup_allowed_kinds).followup_allowed_kinds = [
        (6, 0, env["community.meeting.followup.kind"].search([]).ids)
    ]
