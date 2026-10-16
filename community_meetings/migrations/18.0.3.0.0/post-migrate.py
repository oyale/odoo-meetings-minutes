"""Preserve the kind of historical follow-ups represented by Odoo activities."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE community_meeting_action AS action
           SET followup_kind = CASE
                   WHEN activity.activity_type_id = todo.res_id THEN 'todo'
                   ELSE 'activity'
               END,
               followup_activity_type_id = activity.activity_type_id
          FROM mail_activity AS activity
          LEFT JOIN ir_model_data AS todo
            ON todo.module = 'mail' AND todo.name = 'mail_activity_data_todo'
         WHERE action.followup_activity_id = activity.id
        """
    )
    cr.execute(
        """
        UPDATE community_meeting_action
           SET followup_kind = 'task'
         WHERE followup_activity_id IS NULL
        """
    )
