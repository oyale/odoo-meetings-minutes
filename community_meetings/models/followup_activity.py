from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


FOLLOWUP_KINDS = [
    ("activity", "Odoo activity"),
    ("todo", "Odoo To-do"),
]
FOLLOWUP_POLICIES = [("activity", "Activities only"), ("todo", "To-dos only"), ("both", "Activities and To-dos")]


class Company(models.Model):
    _inherit = "res.company"

    meeting_default_followup_kind = fields.Selection(
        FOLLOWUP_KINDS, string="Default follow-up type", default="todo", required=True
    )
    meeting_followup_policy = fields.Selection(FOLLOWUP_POLICIES, default="both", required=True)
    meeting_default_activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Default Odoo activity type",
        default=lambda self: self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        ),
    )


class Settings(models.TransientModel):
    _inherit = "res.config.settings"
    meeting_followup_policy = fields.Selection(related="company_id.meeting_followup_policy", readonly=False)

    meeting_default_followup_kind = fields.Selection(
        related="company_id.meeting_default_followup_kind", readonly=False
    )
    meeting_default_activity_type_id = fields.Many2one(
        related="company_id.meeting_default_activity_type_id", readonly=False
    )


class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"
    followup_policy = fields.Selection([("inherit", "Company default")] + FOLLOWUP_POLICIES, default="inherit", required=True)

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

    def get_followup_defaults(self, item_id=False):
        self.ensure_one()
        self.check_access("read")
        series = self.series_id
        kind = series.default_followup_kind if series else "inherit"
        if kind == "inherit":
            kind = self.company_id.meeting_default_followup_kind
        policy = series.followup_policy if series and series.followup_policy != "inherit" else self.company_id.meeting_followup_policy
        item = self.env["community.meeting.agenda.item"].browse(item_id).exists()
        if item:
            item.check_access("read")
            if item.meeting_id != self:
                raise ValidationError(_("The point must belong to this meeting."))
            if item.topic_id.followup_policy != "inherit":
                policy = item.topic_id.followup_policy
            if item.topic_id.default_followup_kind != "inherit":
                kind = item.topic_id.default_followup_kind
        allowed = ["activity", "todo"] if policy == "both" else [policy]
        if kind not in allowed:
            kind = allowed[0]
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
            "allowed_kinds": allowed,
            "activity_type_id": activity_type.id if activity_type else False,
            "todo_activity_type_id": todo_type.id if todo_type else False,
        }


class TopicFollowupPolicy(models.Model):
    _inherit = "community.meeting.topic"

    followup_policy = fields.Selection([("inherit", "Series/company default")] + FOLLOWUP_POLICIES, default="inherit", required=True)
    default_followup_kind = fields.Selection([("inherit", "Series/company default")] + FOLLOWUP_KINDS, default="inherit", required=True)


class PointFollowupPolicy(models.Model):
    _inherit = "community.meeting.agenda.item"

    followup_policy = fields.Selection([("inherit", "Series/company default")] + FOLLOWUP_POLICIES, default="inherit", required=True)
    default_followup_kind = fields.Selection([("inherit", "Series/company default")] + FOLLOWUP_KINDS, default="inherit", required=True)

    def get_followup_defaults(self):
        self.ensure_one()
        return self.meeting_id.get_followup_defaults(self.id)


class FollowupActivity(models.Model):
    _inherit = "community.meeting.action"

    followup_kind = fields.Selection(
        FOLLOWUP_KINDS, string="Follow-up type", default="todo", required=True
    )
    responsible_user_ids = fields.Many2many("res.users", "meeting_followup_responsible_rel", string="Responsible people", check_company=True)
    followup_activity_ids = fields.Many2many("mail.activity", "meeting_followup_activity_rel", readonly=True, copy=False)
    completed_user_ids = fields.Many2many("res.users", "meeting_followup_completed_rel", readonly=True, copy=False)
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

    def _has_execution_evidence(self):
        self.ensure_one()
        return bool(self.followup_activity_id or self.followup_activity_completed_on)

    def _sync_followup_activity(self):
        todo_type = self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        for action in self:
            activities = action.followup_activity_ids.exists()
            owners = action.responsible_user_ids
            if action.state in ("done", "cancelled") or not owners:
                if activities:
                    if action.state == "done":
                        activities.action_feedback(feedback=_("Follow-up completed."))
                    else:
                        activities.unlink()
                continue
            if action.followup_kind not in ("activity", "todo"):
                activities.unlink()
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
            activities.filtered(lambda a: a.user_id not in owners or a.user_id in action.completed_user_ids).unlink()
            for owner in owners - action.completed_user_ids:
                if not action.with_user(owner).has_access("read"):
                    raise ValidationError(_("Each responsible person must have access to the meeting. Share it first."))
                values = {"user_id": owner.id, "summary": action.name,
                          "date_deadline": action.deadline or fields.Date.context_today(action),
                          "activity_type_id": activity_type.id}
                activity = action.followup_activity_ids.filtered(lambda a: a.user_id == owner)
                if activity:
                    activity.write(values)
                else:
                    activity = self.env["mail.activity"].create({**values,
                        "res_model_id": self.env["ir.model"]._get_id(action._name), "res_id": action.id})
                    super(FollowupActivity, action).write({"followup_activity_ids": [(4, activity.id)]})
            super(FollowupActivity, action).write({"followup_activity_id": action.followup_activity_ids[:1].id})

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if {"followup_activity_ids", "followup_activity_id", "completed_user_ids", "followup_activity_completed_on"}.intersection(vals):
                raise ValidationError(_("Activity bookkeeping is managed by the follow-up workflow."))
            item = self.env["community.meeting.agenda.item"].browse(vals.get("agenda_item_id"))
            if item:
                defaults = item.get_followup_defaults()
                vals.setdefault("followup_kind", defaults["kind"])
                if vals["followup_kind"] in ("activity", "todo") and vals["followup_kind"] not in defaults["allowed_kinds"]:
                    raise ValidationError(_("This follow-up type is not allowed for this point."))
                vals.setdefault("followup_activity_type_id", defaults["activity_type_id"])
            if "responsible_user_ids" not in vals:
                owner = vals.get("responsible_user_id", self.env.uid)
                vals["responsible_user_ids"] = [(6, 0, [owner] if owner else [])]
            prepared.append(vals)
        records = super().create(prepared)
        for action in records:
            super(FollowupActivity, action).write({"responsible_user_id": action.responsible_user_ids[:1].id})
        records._sync_followup_activity()
        return records

    def write(self, vals):
        values = dict(vals)
        reopening = self.filtered(lambda action: action.state in ("done", "cancelled")) if values.get("state") in ("open", "in_progress") else self.browse()
        if {"followup_activity_ids", "followup_activity_id", "completed_user_ids", "followup_activity_completed_on"}.intersection(values):
            raise ValidationError(_("Activity bookkeeping is managed by the follow-up workflow."))
        if "responsible_user_id" in values and "responsible_user_ids" not in values:
            values["responsible_user_ids"] = [(6, 0, [values["responsible_user_id"]] if values["responsible_user_id"] else [])]
        if "followup_kind" in values:
            for action in self:
                defaults = action.agenda_item_id.get_followup_defaults()
                if values["followup_kind"] in ("activity", "todo") and values["followup_kind"] not in defaults["allowed_kinds"]:
                    raise ValidationError(_("This follow-up type is not allowed for this point."))
        if values.get("state") == "done":
            values.setdefault("completed_on", fields.Date.context_today(self))
        elif "state" in values:
            values.setdefault("completed_on", False)
        result = super().write(values)
        if "responsible_user_ids" in values:
            for action in self:
                super(FollowupActivity, action).write({"responsible_user_id": action.responsible_user_ids[:1].id})
        if reopening:
            super(FollowupActivity, reopening).write({"completed_user_ids": [(5, 0, 0)]})
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
            "responsible_user_ids",
            "deadline",
            "name",
            "followup_kind",
            "followup_activity_type_id",
        }.intersection(values):
            self._sync_followup_activity()
        if reopening:
            super(FollowupActivity, reopening).write({"followup_activity_completed_on": False})
        return result

    def unlink(self):
        # mail.activity uses a polymorphic model/res_id pair, so deleting the
        # follow-up record does not cascade to its Odoo activity automatically.
        self.mapped("followup_activity_ids").sudo().unlink()
        return super().unlink()


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
        followups = self.env["community.meeting.action"].search([("followup_activity_ids", "in", meeting_activities.ids)])
        meeting_activities.check_access("write")
        followups.check_access("read")
        for action in followups:
            owned = meeting_activities.filtered(lambda activity: activity in action.followup_activity_ids)
            if any(activity.user_id != self.env.user for activity in owned) and not action.has_access("write"):
                raise AccessError(_("You can only complete your own follow-up activities."))
        completed = {a.id: meeting_activities.filtered(lambda activity: activity in a.followup_activity_ids).user_id.ids for a in followups}
        finished_ids = {a.id: meeting_activities.filtered(lambda activity: activity in a.followup_activity_ids).ids for a in followups}
        result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        for action in followups:
            # Native activity ownership authorizes only these completion fields;
            # it does not grant editorial write access to the meeting/follow-up.
            action = action.sudo()
            completed_ids = set(action.completed_user_ids.ids) | set(completed[action.id])
            all_done = set(action.responsible_user_ids.ids) <= completed_ids
            super(FollowupActivity, action).write({"completed_user_ids": [(4, uid) for uid in completed[action.id]],
                                                  "followup_activity_ids": [(3, aid) for aid in finished_ids[action.id]],
                                                  "followup_activity_id": action.followup_activity_ids.filtered(lambda activity: activity.id not in finished_ids[action.id])[:1].id,
                                                  "followup_activity_completed_on": fields.Datetime.now() if all_done else False})
            if all_done:
                if action.state not in ("done", "cancelled"):
                    action.write({"state": "done"})
        return result
