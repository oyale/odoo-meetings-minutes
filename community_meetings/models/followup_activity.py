from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


FOLLOWUP_KINDS = [
    ("task", "Meeting task"),
    ("activity", "Odoo activity"),
    ("todo", "Odoo To-do"),
]


class Company(models.Model):
    _inherit = "res.company"

    meeting_default_followup_kind = fields.Selection(
        FOLLOWUP_KINDS, string="Default follow-up type", default="task", required=True
    )
    meeting_default_activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Default Odoo activity type",
        default=lambda self: self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        ),
    )


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    meeting_default_followup_kind = fields.Selection(
        related="company_id.meeting_default_followup_kind", readonly=False
    )
    meeting_default_activity_type_id = fields.Many2one(
        related="company_id.meeting_default_activity_type_id", readonly=False
    )


class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"

    default_followup_kind = fields.Selection(
        [("inherit", "Company default")] + FOLLOWUP_KINDS,
        string="Default follow-up type",
        default="inherit",
        required=True,
    )
    default_activity_type_id = fields.Many2one(
        "mail.activity.type", string="Default Odoo activity type"
    )


class Meeting(models.Model):
    _inherit = "community.meeting"

    def get_followup_defaults(self):
        self.ensure_one()
        self.check_access("read")
        series = self.series_id
        kind = series.default_followup_kind if series else "inherit"
        if kind == "inherit":
            kind = self.company_id.meeting_default_followup_kind
        activity_type = (
            series.default_activity_type_id
            if series and series.default_activity_type_id
            else self.company_id.meeting_default_activity_type_id
        )
        todo_type = self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        return {
            "kind": kind,
            "activity_type_id": activity_type.id if activity_type else False,
            "todo_activity_type_id": todo_type.id if todo_type else False,
        }


class FollowupActivity(models.Model):
    _inherit = "community.meeting.action"

    followup_kind = fields.Selection(
        FOLLOWUP_KINDS, string="Follow-up type", default="task", required=True
    )
    followup_activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Odoo activity type",
        default=lambda self: self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        ),
    )
    followup_activity_id = fields.Many2one(
        "mail.activity", readonly=True, ondelete="set null", copy=False
    )
    followup_activity_completed_on = fields.Datetime(readonly=True, copy=False)

    def _sync_followup_activity(self):
        todo_type = self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        for action in self:
            activity = action.followup_activity_id.exists()
            if action.state in ("done", "cancelled") or not action.responsible_user_id:
                if activity:
                    if action.state == "done":
                        activity.action_feedback(feedback=_("Follow-up completed."))
                    else:
                        activity.unlink()
                continue
            if action.followup_kind == "task":
                # A meeting task is independent from Odoo's activity inbox.
                if activity:
                    activity.unlink()
                continue
            activity_type = (
                todo_type
                if action.followup_kind == "todo"
                else action.followup_activity_type_id
            )
            if not activity_type:
                raise ValidationError(
                    _("Choose an Odoo activity type for this follow-up.")
                )
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
                activity.write({**values, "activity_type_id": activity_type.id})
            else:
                new_activity = self.env["mail.activity"].create(
                    {
                        **values,
                        "res_model_id": self.env["ir.model"]._get_id(action._name),
                        "res_id": action.id,
                        "activity_type_id": activity_type.id,
                    }
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
        if "followup_activity_completed_on" in values and not self.env.context.get(
            "meeting_followup_activity_internal"
        ):
            raise ValidationError(_("Activity completion is managed by Odoo."))
        if values.get("state") == "done":
            values.setdefault("completed_on", fields.Date.context_today(self))
        elif "state" in values:
            values.setdefault("completed_on", False)
        result = super().write(values)
        if "followup_kind" in values and values["followup_kind"] != "activity":
            todo_type = self.env.ref(
                "mail.mail_activity_data_todo", raise_if_not_found=False
            )
            if values["followup_kind"] == "todo" and todo_type:
                super(FollowupActivity, self).write(
                    {"followup_activity_type_id": todo_type.id}
                )
        if {
            "state",
            "responsible_user_id",
            "deadline",
            "name",
            "followup_kind",
            "followup_activity_type_id",
        }.intersection(values):
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
        followups.with_context(meeting_followup_activity_internal=True).write(
            {"followup_activity_completed_on": fields.Datetime.now()}
        )
        result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        for action in followups.filtered(
            lambda a: a.state not in ("done", "cancelled")
        ):
            action.write({"state": "done"})
        return result
