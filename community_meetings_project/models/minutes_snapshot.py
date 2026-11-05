from odoo import api, fields, models


class MeetingRevision(models.Model):
    _inherit = "community.meeting.revision"

    @api.model
    def _get_actions_snapshot_extensions(self, actions):
        values = super()._get_actions_snapshot_extensions(actions)
        project_actions = actions.filtered(lambda action: action.followup_kind in ("project_task", "project_todo"))
        if not project_actions:
            return values

        # The link field's read() applies its access filter to the whole recordset.
        # Keep this projection in the current user's environment; never elevate.
        relation_rows = project_actions.with_user(self.env.user).read(["project_task_ids"])
        task_ids_by_action = {row["id"]: row["project_task_ids"] for row in relation_rows}
        visible_task_ids = sorted({task_id for task_ids in task_ids_by_action.values() for task_id in task_ids})
        tasks = self.env["project.task"].with_user(self.env.user).search([("id", "in", visible_task_ids)])
        details_by_id = {
            task.id: {
                "name": task.name or "",
                "deadline": fields.Date.to_string(task.date_deadline) if task.date_deadline else "",
                "assignees": sorted(task.user_ids.mapped("name")),
            }
            for task in tasks
        }
        for action in project_actions:
            values[action.id] = {
                **values.get(action.id, {}),
                "project_tasks": [
                    details_by_id[task_id] for task_id in task_ids_by_action[action.id] if task_id in details_by_id
                ],
            }
        return values
