from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

FOLLOWUP_KIND_CODES = [("activity", "Odoo activity")]


class Company(models.Model):
    _inherit = "res.company"

    followup_allowed_kinds = fields.Many2many(
        "community.meeting.followup.kind", "company_followup_kind_rel",
        "company_id", "kind_id", string="Allowed follow-up types",
    )
    followup_default_kind = fields.Selection(
        FOLLOWUP_KIND_CODES, string="Default follow-up type", default="activity", required=True,
    )
    meeting_default_activity_type_id = fields.Many2one(
        "mail.activity.type", string="Default Odoo activity type",
        default=lambda self: self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False),
    )


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    followup_allowed_kinds = fields.Many2many(
        related="company_id.followup_allowed_kinds", readonly=False,
    )
    followup_default_kind = fields.Selection(
        related="company_id.followup_default_kind", readonly=False,
    )
    meeting_default_activity_type_id = fields.Many2one(
        related="company_id.meeting_default_activity_type_id", readonly=False,
    )


class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"

    followup_allowed_kinds = fields.Many2many(
        "community.meeting.followup.kind", "series_followup_kind_rel",
        "series_id", "kind_id", string="Allowed follow-up types",
    )
    followup_default_kind = fields.Selection(
        [("inherit", "Series/company default")] + FOLLOWUP_KIND_CODES,
        default="inherit", required=True,
    )
    default_activity_type_id = fields.Many2one("mail.activity.type", string="Default Odoo activity type")


class Meeting(models.Model):
    _inherit = "community.meeting"

    def _followup_available_codes(self):
        return self.env["community.meeting.followup.kind"].search([]).mapped("code")

    def _followup_allowed_codes(self, item=False):
        self.ensure_one()
        available = self._followup_available_codes()
        levels = (self.company_id, self.series_id, item.topic_id if item else False, item if item else False)
        allowed = []
        for record in levels:
            if record and record.followup_allowed_kinds:
                allowed = record.followup_allowed_kinds.mapped("code")
                break
        if not allowed:
            allowed = self.company_id.followup_allowed_kinds.mapped("code")
        return [code for code in allowed if code in available]

    def get_followup_defaults(self, item_id=False):
        self.ensure_one()
        self.check_access("read")
        item = self.env["community.meeting.agenda.item"].browse(item_id).exists()
        if item and item.meeting_id != self:
            raise ValidationError(_("The point must belong to this meeting."))
        # ponytail: company.followup_allowed_kinds stays empty in a fresh core
        # install; the fallback below keeps activity as the implicit default.
        allowed = self._followup_allowed_codes(item) or ["activity"]
        kind = self.company_id.followup_default_kind
        for record in (self.series_id, item.topic_id if item else False, item if item else False):
            if record and record.followup_default_kind and record.followup_default_kind != "inherit":
                kind = record.followup_default_kind
        if kind not in allowed:
            kind = allowed[0]
        series = self.series_id
        activity_type = (
            series.default_activity_type_id
            if series and series.default_activity_type_id
            else self.company_id.meeting_default_activity_type_id
        )
        return {
            "kind": kind,
            "allowed_kinds": allowed,
            "activity_type_id": activity_type.id if activity_type else False,
        }


class TopicFollowupPolicy(models.Model):
    _inherit = "community.meeting.topic"

    followup_allowed_kinds = fields.Many2many(
        "community.meeting.followup.kind", "topic_followup_kind_rel",
        "topic_id", "kind_id", string="Allowed follow-up types",
    )
    followup_default_kind = fields.Selection(
        [("inherit", "Series/company default")] + FOLLOWUP_KIND_CODES,
        default="inherit", required=True,
    )


class PointFollowupPolicy(models.Model):
    _inherit = "community.meeting.agenda.item"

    followup_allowed_kinds = fields.Many2many(
        "community.meeting.followup.kind", "item_followup_kind_rel",
        "item_id", "kind_id", string="Allowed follow-up types",
    )
    followup_default_kind = fields.Selection(
        [("inherit", "Series/company default")] + FOLLOWUP_KIND_CODES,
        default="inherit", required=True,
    )

    def get_followup_defaults(self):
        self.ensure_one()
        return self.meeting_id.get_followup_defaults(self.id)


class FollowupActivity(models.Model):
    _inherit = "community.meeting.action"

    followup_kind = fields.Selection(
        FOLLOWUP_KIND_CODES, string="Follow-up type", default="activity", required=True,
    )
    responsible_user_ids = fields.Many2many("res.users", "meeting_followup_responsible_rel", string="Responsible people", check_company=True)
    followup_activity_ids = fields.Many2many("mail.activity", "meeting_followup_activity_rel", readonly=True, copy=False)
    completed_user_ids = fields.Many2many("res.users", "meeting_followup_completed_rel", readonly=True, copy=False)
    followup_activity_type_id = fields.Many2one(
        "mail.activity.type", string="Odoo activity type",
        default=lambda self: self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False),
    )
    followup_activity_id = fields.Many2one("mail.activity", readonly=True, ondelete="set null", copy=False)
    followup_activity_completed_on = fields.Datetime(readonly=True, copy=False)

    def _has_execution_evidence(self):
        self.ensure_one()
        return bool(self.followup_activity_ids.exists() or self.followup_activity_completed_on)

    def _sync_followup_activity(self):
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
            if action.followup_kind != "activity":
                activities.unlink()
                continue
            activity_type = action.followup_activity_type_id
            if not activity_type:
                raise ValidationError(_("Choose an Odoo activity type for this follow-up."))
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

    def _sync_followup_artifacts(self):
        for action in self:
            if action.followup_kind == "activity":
                action._sync_followup_activity()
            else:
                action._sync_external_artifact()

    def _sync_external_artifact(self):
        # Core has no external container; project containers override this.
        return True

    def _clear_followup_artifact(self):
        self.ensure_one()
        if self.followup_kind == "activity":
            self.followup_activity_ids.exists().unlink()
            super(FollowupActivity, self).write({
                "followup_activity_ids": [(5, 0, 0)], "followup_activity_id": False,
            })
        return True

    def action_convert_followup_kind(self, kind):
        self.ensure_one()
        self.check_access("write")
        if self.state in ("done", "cancelled"):
            raise UserError(_("Only open follow-ups can be converted."))
        if self.meeting_id.state in ("approved", "cancelled"):
            raise UserError(_("Follow-ups in approved or cancelled meetings cannot be converted."))
        allowed = self.agenda_item_id.get_followup_defaults()["allowed_kinds"]
        if kind not in allowed:
            raise UserError(_("This follow-up type is not allowed for this point."))
        if kind == self.followup_kind:
            return True
        self._clear_followup_artifact()
        self.write({"followup_kind": kind})
        return True

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
                if vals["followup_kind"] not in defaults["allowed_kinds"]:
                    raise ValidationError(_("This follow-up type is not allowed for this point."))
                vals.setdefault("followup_activity_type_id", defaults["activity_type_id"])
            if "responsible_user_ids" not in vals:
                owner = vals.get("responsible_user_id", self.env.uid)
                vals["responsible_user_ids"] = [(6, 0, [owner] if owner else [])]
            prepared.append(vals)
        records = super().create(prepared)
        for action in records:
            super(FollowupActivity, action).write({"responsible_user_id": action.responsible_user_ids[:1].id})
        records._sync_followup_artifacts()
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
                if values["followup_kind"] not in defaults["allowed_kinds"]:
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
        if {"state", "responsible_user_id", "responsible_user_ids", "deadline", "name", "followup_kind", "followup_activity_type_id"}.intersection(values):
            self._sync_followup_artifacts()
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

    def unlink(self):
        linked = self.env["community.meeting.action"].sudo().search([
            ("followup_activity_ids", "in", self.ids),
        ])
        topics = linked.topic_id
        for topic in topics.sorted("id"):
            topic._lock_workflow()
        closed = self.env["community.meeting.agenda.item"].sudo().search([
            ("topic_id", "in", topics.ids),
            ("kind", "=", "todo"),
            ("disposition", "=", "closed"),
        ])
        for item in closed:
            actions = self.env["community.meeting.action"].sudo().search([
                ("topic_id", "=", item.topic_id.id),
                ("state", "!=", "cancelled"),
                ("responsible_user_id", "!=", False),
            ])
            if not any(
                action._has_execution_evidence()
                if action not in linked or action.followup_kind != "activity"
                else bool(
                    action.followup_activity_completed_on
                    or (action.followup_activity_ids.exists() - self)
                )
                for action in actions
            ):
                raise ValidationError(_(
                    "A resolved TODO must keep at least one non-cancelled follow-up task. "
                    "Reopen the point before removing its last activity."
                ))
        return super().unlink()

    def _action_done(self, feedback=False, attachment_ids=None):
        meeting_activities = self.filtered(lambda a: a.res_model == "community.meeting.action")
        if not meeting_activities:
            return super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        followups = self.env["community.meeting.action"].search([("followup_activity_ids", "in", meeting_activities.ids)])
        meeting_activities.check_access("write")
        followups.check_access("read")
        for action in followups:
            owned = meeting_activities.filtered(lambda activity: activity in action.followup_activity_ids)
            if any(activity.user_id != self.env.user for activity in owned) and not action.has_access("write"):
                raise AccessError(_("You can only complete your own follow-up activities."))
        completed = {a.id: meeting_activities.filtered(lambda activity: activity in a.followup_activity_ids).user_id.ids for a in followups}
        finished_ids = {a.id: meeting_activities.filtered(lambda activity: activity in a.followup_activity_ids).ids for a in followups}
        # Odoo unlinks completed activities internally. Record the durable
        # evidence first so the ordinary unlink guard can distinguish completion
        # from deleting the last open activity on a closed TODO.
        for action in followups:
            completed_ids = set(action.completed_user_ids.ids) | set(completed[action.id])
            if set(action.responsible_user_ids.ids) <= completed_ids:
                super(FollowupActivity, action.sudo()).write({"followup_activity_completed_on": fields.Datetime.now()})
        result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        for action in followups:
            # Native activity ownership authorizes only these completion fields;
            # it does not grant editorial write access to the meeting/follow-up.
            action = action.sudo()
            completed_ids = set(action.completed_user_ids.ids) | set(completed[action.id])
            all_done = set(action.responsible_user_ids.ids) <= completed_ids
            super(FollowupActivity, action).write({
                "completed_user_ids": [(4, uid) for uid in completed[action.id]],
                "followup_activity_ids": [(3, aid) for aid in finished_ids[action.id]],
                "followup_activity_id": action.followup_activity_ids.filtered(lambda activity: activity.id not in finished_ids[action.id])[:1].id,
                "followup_activity_completed_on": fields.Datetime.now() if all_done else False,
            })
            if all_done:
                if action.state not in ("done", "cancelled"):
                    action.write({"state": "done"})
        return result
