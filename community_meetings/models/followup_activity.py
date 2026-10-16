from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FollowupActivity(models.Model):
    _inherit = "community.meeting.action"

    followup_activity_id = fields.Many2one(
        "mail.activity", readonly=True, ondelete="set null", copy=False
    )

    def _sync_followup_activity(self):
        for action in self:
            activity = action.followup_activity_id.exists()
            if action.state in ("done", "cancelled") or not action.responsible_user_id:
                if activity:
                    if action.state == "done":
                        activity.action_feedback(feedback=_("Follow-up completed."))
                    else:
                        activity.unlink()
                continue
            owner = action.responsible_user_id
            if not action.with_user(owner).has_access("read"):
                raise ValidationError(
                    _(
                        "The task owner must have access to its meeting. Share the meeting first."
                    )
                )
            values = {
                "user_id": owner.id,
                "summary": action.name,
                "date_deadline": action.deadline or fields.Date.context_today(action),
            }
            if activity:
                activity.write(values)
            else:
                new_activity = action.activity_schedule(
                    "mail.mail_activity_data_todo", **values
                )
                # Updating bookkeeping does not change action state or schedule another activity.
                super(FollowupActivity, action).write(
                    {"followup_activity_id": new_activity.id}
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_followup_activity()
        return records

    def write(self, vals):
        values = dict(vals)
        if values.get("state") == "done":
            values.setdefault("completed_on", fields.Date.context_today(self))
        elif "state" in values:
            values.setdefault("completed_on", False)
        result = super().write(values)
        if {"state", "responsible_user_id", "deadline", "name"}.intersection(values):
            self._sync_followup_activity()
        return result


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def _action_done(self, feedback=False, attachment_ids=None):
        meeting_activities = self.filtered(
            lambda a: a.res_model == "community.meeting.action"
        )
        if not meeting_activities:
            return super()._action_done(
                feedback=feedback, attachment_ids=attachment_ids
            )
        followups = self.env["community.meeting.action"].search(
            [("followup_activity_id", "in", meeting_activities.ids)]
        )
        followups.check_access("write")
        result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        for action in followups.filtered(
            lambda a: a.state not in ("done", "cancelled")
        ):
            action.write({"state": "done"})
        return result
