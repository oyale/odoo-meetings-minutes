"""Create deterministic actor accounts for the acceptance workflow database."""

import os

from odoo import SUPERUSER_ID, api

password = os.environ["ACCEPTANCE_ACTOR_PASSWORD"]
shell_env = env  # noqa: F821 - provided by `odoo shell`
env = api.Environment(shell_env.cr, SUPERUSER_ID, {})


def ensure_user(login, name, group_xmlids):
    groups = env["res.groups"].browse([env.ref(xmlid).id for xmlid in group_xmlids])
    user = env["res.users"].search([("login", "=", login)], limit=1)
    values = {
        "name": name,
        "login": login,
        "password": password,
        "groups_id": [(6, 0, groups.ids)],
    }
    if user:
        user.write(values)
    else:
        env["res.users"].create(values)


internal = "base.group_user"
ensure_user(
    "acceptance_editor",
    "Acceptance Editor",
    [
        internal,
        "community_meetings.group_meeting_editor",
        "project.group_project_user",
        "project.group_project_manager",
    ],
)
ensure_user(
    "acceptance_approver",
    "Acceptance Approver",
    [internal, "community_meetings.group_meeting_approver"],
)
ensure_user(
    "acceptance_reader",
    "Acceptance Reader",
    [internal, "community_meetings.group_meeting_reader"],
)
env.cr.commit()
