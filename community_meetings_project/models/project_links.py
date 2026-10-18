from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProjectTaskLinkChecks(models.AbstractModel):
    """Shared authorization and company checks for optional task links."""

    _name = "community.meeting.project.task.mixin"
    _description = "Community Meeting Project Task Link Checks"
    _abstract = True

    def _check_closed_todo_project_tasks(
        self, agenda_items, excluded_action_ids=(), excluded_task_ids=()
    ):
        for topic in agenda_items.topic_id.sorted("id"):
            topic._lock_workflow()
        for item in agenda_items.filtered(
            lambda row: row.kind == "todo"
            and row.disposition == "closed"
            and row.requires_project_task
        ):
            actions = item.env["community.meeting.action"].search(
                [
                    ("topic_id", "=", item.topic_id.id),
                    ("state", "!=", "cancelled"),
                    ("responsible_user_id", "!=", False),
                    ("id", "not in", list(excluded_action_ids)),
                ]
            )
            tasks = actions.mapped("project_task_ids").filtered(
                lambda task, item=item: task.id not in excluded_task_ids
                and task.user_ids
                and task.state != "1_canceled"
                and task.active
                and (not task.company_id or task.company_id == item.company_id)
            )
            scope = (
                item.task_scope_snapshot
                or item.meeting_id._project_policy()["meeting_task_scope"]
            )
            if scope == "configured":
                allowed = (
                    item.allowed_project_snapshot_id
                    or item.meeting_id._meeting_project()
                )
                tasks = tasks.filtered(
                    lambda task, allowed=allowed: task.project_id == allowed
                )
            if not tasks:
                raise ValidationError(
                    _(
                        "Link a Project task to a follow-up action before resolving "
                        "this TODO."
                    )
                )

    def _check_task_links(self, task_ids, meeting):
        if not task_ids:
            return self.env["project.task"]
        tasks = self.env["project.task"].browse(task_ids).exists()
        if set(tasks.ids) != set(task_ids):
            raise ValidationError(_("One or more linked tasks are unavailable."))
        tasks.check_access("read")
        tasks.check_access("write")
        if any(
            task.company_id and task.company_id != meeting.company_id for task in tasks
        ):
            raise ValidationError(_("Linked tasks must belong to the meeting company."))
        if meeting._project_policy()["meeting_task_scope"] == "configured":
            project = meeting._meeting_project()
            if not project or any(task.project_id != project for task in tasks):
                raise ValidationError(
                    _("Select a task from the configured meeting project.")
                )
        return tasks

    @api.model
    def _task_ids_after_commands(self, commands, current=()):
        result = set(current)
        for command in commands:
            operation = command[0]
            if operation == 6:
                result = set(command[2])
            elif operation == 5:
                result.clear()
            elif operation == 4:
                result.add(command[1])
            elif operation in (2, 3):
                result.discard(command[1])
        return list(result)

    def read(self, fields=None, load="_classic_read"):
        """Strip linked tasks the reader cannot see.

        Read-time policy only: the stored relation keeps every linked task, so a
        manager still sees the full set. This deliberately trades read-back
        fidelity (``read()`` differs from the stored value) for not leaking
        inaccessible tasks; write-path integrity is enforced by
        ``_check_task_links``.
        """
        records = super().read(fields=fields, load=load)
        link_fields = {"project_task_ids", "selected_project_task_ids"}
        if fields is not None and not link_fields.intersection(fields):
            return records
        returned_link_fields = (
            link_fields.intersection(records[0]) if records else set()
        )
        linked_ids = {
            task_id
            for values in records
            for field_name in returned_link_fields
            for task_id in values.get(field_name, [])
        }
        try:
            visible_ids = set(
                self.env["project.task"].search([("id", "in", list(linked_ids))]).ids
            )
        except AccessError:
            visible_ids = set()
        for values in records:
            for field_name in returned_link_fields:
                values[field_name] = [
                    task_id for task_id in values[field_name] if task_id in visible_ids
                ]
        return records


class Company(models.Model):
    _inherit = "res.company"

    followup_default_kind = fields.Selection(
        selection_add=[("project_task", "Project task"), ("project_todo", "To-do")],
        ondelete={"project_task": "set default", "project_todo": "set default"},
    )


class MeetingSeries(models.Model):
    _inherit = "community.meeting.series"

    followup_default_kind = fields.Selection(
        selection_add=[("project_task", "Project task"), ("project_todo", "To-do")],
        ondelete={"project_task": "set default", "project_todo": "set default"},
    )


class Topic(models.Model):
    _inherit = "community.meeting.topic"

    followup_default_kind = fields.Selection(
        selection_add=[("project_task", "Project task"), ("project_todo", "To-do")],
        ondelete={"project_task": "set default", "project_todo": "set default"},
    )


def post_init_allow_project_kinds(env):
    kinds = env["community.meeting.followup.kind"].search(
        [("code", "in", ["project_task", "project_todo"])]
    )
    activity = env["community.meeting.followup.kind"].search(
        [("code", "=", "activity")]
    )
    for company in env["res.company"].search([]):
        if not company.followup_allowed_kinds:
            company.followup_allowed_kinds = [(6, 0, (activity | kinds).ids)]
    for series in env["community.meeting.series"].search([]):
        if series.followup_allowed_kinds:
            missing = kinds - series.followup_allowed_kinds
            series.followup_allowed_kinds = [(4, kind.id) for kind in missing]


class CommunityMeetingAgendaItem(models.Model):
    _name = "community.meeting.agenda.item"
    _inherit = ["community.meeting.agenda.item", "community.meeting.project.task.mixin"]
    _description = "Meeting Agenda Item"

    followup_default_kind = fields.Selection(
        selection_add=[("project_task", "Project task"), ("project_todo", "To-do")],
        ondelete={"project_task": "set default", "project_todo": "set default"},
    )
    project_task_ids = fields.Many2many(
        "project.task",
        "community_meeting_agenda_task_rel",
        "agenda_item_id",
        "task_id",
        string="Project Tasks",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("project_task_ids"):
                meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
                ids = self._task_ids_after_commands(vals["project_task_ids"])
                self.env["community.meeting.project.task.mixin"]._check_task_links(
                    ids, meeting
                )
        return super().create(vals_list)

    def write(self, vals):
        if "project_task_ids" in vals:
            for record in self:
                ids = self._task_ids_after_commands(
                    vals["project_task_ids"], record.project_task_ids.ids
                )
                self.env["community.meeting.project.task.mixin"]._check_task_links(
                    ids, record.meeting_id
                )
        result = super().write(vals)
        self._check_closed_todo_project_tasks(self)
        return result


class CommunityMeetingResolution(models.Model):
    _name = "community.meeting.resolution"
    _inherit = ["community.meeting.resolution", "community.meeting.project.task.mixin"]
    _description = "Meeting Resolution"

    project_task_ids = fields.Many2many(
        "project.task",
        "community_meeting_resolution_task_rel",
        "resolution_id",
        "task_id",
        string="Project Tasks",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("project_task_ids"):
                meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
                ids = self._task_ids_after_commands(vals["project_task_ids"])
                self.env["community.meeting.project.task.mixin"]._check_task_links(
                    ids, meeting
                )
        return super().create(vals_list)

    def write(self, vals):
        if "project_task_ids" in vals:
            for record in self:
                ids = self._task_ids_after_commands(
                    vals["project_task_ids"], record.project_task_ids.ids
                )
                self.env["community.meeting.project.task.mixin"]._check_task_links(
                    ids, record.meeting_id
                )
        return super().write(vals)


class CommunityMeetingAction(models.Model):
    _name = "community.meeting.action"
    _inherit = ["community.meeting.action", "community.meeting.project.task.mixin"]
    _description = "Meeting Follow-up Action"
    followup_kind = fields.Selection(
        selection_add=[("project_task", "Project task"), ("project_todo", "To-do")],
        ondelete={"project_task": "set default", "project_todo": "set default"},
    )

    def _has_execution_evidence(self):
        self.ensure_one()
        if self.followup_kind not in ("project_task", "project_todo"):
            return super()._has_execution_evidence()
        return bool(
            self.project_task_ids.filtered(
                lambda task: task.active
                and task.user_ids
                and task.state != "1_canceled"
            )
        )

    def _sync_external_artifact(self):
        for action in self:
            if action.followup_kind == "project_todo":
                action._sync_project_todo()
            # project_task links existing tasks through the wizard; nothing to sync.
        return True

    def _sync_project_todo(self):
        self.ensure_one()
        owners = self.responsible_user_ids
        tasks = self.project_task_ids.filtered(lambda task: not task.project_id)
        if self.state in ("done", "cancelled") or not owners:
            return True
        values = {
            "name": self.name,
            "date_deadline": self.deadline or fields.Date.context_today(self),
            "user_ids": [(6, 0, owners.ids)],
        }
        if tasks:
            tasks.write(values)
        else:
            task = self.env["project.task"].create(
                {**values, "company_id": self.company_id.id}
            )
            self.write({"project_task_ids": [(4, task.id)]})
        return True

    def _clear_followup_artifact(self):
        result = super()._clear_followup_artifact()
        for action in self:
            if action.followup_kind == "project_todo":
                projects = action.project_task_ids.filtered(
                    lambda task: not task.project_id
                )
                action.write({"project_task_ids": [(3, task.id) for task in projects]})
            elif action.followup_kind == "project_task":
                action.write({"project_task_ids": [(5, 0, 0)]})
        return result

    project_task_ids = fields.Many2many(
        "project.task",
        "community_meeting_action_task_rel",
        "action_id",
        "task_id",
        string="Project Tasks",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("project_task_ids"):
                meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
                ids = self._task_ids_after_commands(vals["project_task_ids"])
                self.env["community.meeting.project.task.mixin"]._check_task_links(
                    ids, meeting
                )
        records = super().create(vals_list)
        items = (
            self.env["community.meeting.agenda.item"]
            .sudo()
            .search([("topic_id", "in", records.topic_id.ids)])
        )
        self._check_closed_todo_project_tasks(items)
        return records

    def write(self, vals):
        if "project_task_ids" in vals:
            for record in self:
                ids = self._task_ids_after_commands(
                    vals["project_task_ids"], record.project_task_ids.ids
                )
                self.env["community.meeting.project.task.mixin"]._check_task_links(
                    ids, record.meeting_id
                )
        agenda_items = self.mapped("agenda_item_id")
        result = super().write(vals)
        if {"responsible_user_ids", "responsible_user_id"}.intersection(vals):
            for action in self.filtered(
                lambda record: record.followup_kind == "project_task"
            ):
                if action.project_task_ids:
                    action.project_task_ids.write(
                        {
                            "user_ids": [
                                (4, uid) for uid in action.responsible_user_ids.ids
                            ]
                        }
                    )
        items = (
            self.env["community.meeting.agenda.item"]
            .sudo()
            .search(
                [
                    (
                        "topic_id",
                        "in",
                        (agenda_items | self.mapped("agenda_item_id")).topic_id.ids,
                    )
                ]
            )
        )
        self._check_closed_todo_project_tasks(items)
        return result

    def unlink(self):
        affected_items = (
            self.env["community.meeting.agenda.item"]
            .sudo()
            .search([("topic_id", "in", self.topic_id.ids)])
        )
        self.env[
            "community.meeting.project.task.mixin"
        ]._check_closed_todo_project_tasks(affected_items, excluded_action_ids=self.ids)
        return super().unlink()

    def action_create_project_task(self):
        self.ensure_one()
        if self.followup_kind != "project_task":
            raise ValidationError(
                _("Project tasks can only be linked to Project task follow-ups.")
            )
        self.check_access("write")
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Project Task"),
            "res_model": "community.meeting.project.task.wizard",
            "view_mode": "form",
            "views": [
                (
                    self.env.ref(
                        "community_meetings_project.view_community_meeting_project_task_wizard"
                    ).id,
                    "form",
                )
            ],
            "target": "new",
            "context": {"default_action_id": self.id, "default_name": self.name},
        }


class CommunityMeetingProjectTaskWizard(models.TransientModel):
    _name = "community.meeting.project.task.wizard"
    _description = "Create and Link a Project Task"

    action_id = fields.Many2one(
        "community.meeting.action", required=True, readonly=True
    )
    project_id = fields.Many2one("project.project")
    has_default_project = fields.Boolean(readonly=True)
    choose_another_project = fields.Boolean(string="Choose a different project")
    name = fields.Char(required=True)
    existing_task_id = fields.Many2one("project.task", string="Existing task")

    @api.model
    def default_get(self, names):
        values = super().default_get(names)
        if values.get("action_id"):
            action = self.env["community.meeting.action"].browse(values["action_id"])
            action.check_access("write")
            project = action.meeting_id._meeting_project(create=False)
            if project:
                values["project_id"] = project.id
                values["has_default_project"] = True
        return values

    @api.onchange("choose_another_project")
    def _onchange_choose_another_project(self):
        if self.choose_another_project:
            self.project_id = False

    def action_create(self):
        self.ensure_one()
        self.action_id.check_access("write")
        if self.action_id.followup_kind != "project_task":
            raise ValidationError(
                _("Project tasks can only be linked to Project task follow-ups.")
            )
        self.env["project.task"].check_access("create")
        if (
            self.choose_another_project
            and not self.project_id
            and not self.existing_task_id
        ):
            raise ValidationError(_("Choose the project for this task."))
        if (
            self.project_id.company_id
            and self.project_id.company_id != self.action_id.meeting_id.company_id
        ):
            raise ValidationError(_("The project must belong to the meeting company."))
        if self.existing_task_id:
            task = self.existing_task_id
        else:
            project = self.project_id or self.action_id.meeting_id._meeting_project(
                create=True
            )
            if not project:
                raise ValidationError(_("Choose a project or select an existing task."))
            project.check_access("read")
            task = self.env["project.task"].create(
                {
                    "name": self.name,
                    "project_id": project.id,
                    "user_ids": [(6, 0, self.action_id.responsible_user_ids.ids)],
                }
            )
        if self.existing_task_id:
            task.write(
                {
                    "user_ids": [
                        (4, uid) for uid in self.action_id.responsible_user_ids.ids
                    ]
                }
            )
        self.action_id.write({"project_task_ids": [(4, task.id)]})
        return {"type": "ir.actions.act_window_close"}


class ProjectTask(models.Model):
    _inherit = "project.task"

    def write(self, vals):
        actions = (
            self.env["community.meeting.action"]
            .sudo()
            .search([("project_task_ids", "in", self.ids)])
        )
        for topic in actions.topic_id.sorted("id"):
            topic._lock_workflow()
        result = super().write(vals)
        if "state" in vals:
            completable = actions.filtered(
                lambda a: a.followup_kind in ("project_task", "project_todo")
                and a.state not in ("done", "cancelled")
            )
            for action in completable:
                tasks = action.project_task_ids
                if tasks and all(task.state == "1_done" for task in tasks):
                    action.write({"state": "done"})
        items = (
            self.env["community.meeting.agenda.item"]
            .sudo()
            .search([("topic_id", "in", actions.topic_id.ids)])
        )
        self.env[
            "community.meeting.project.task.mixin"
        ].sudo()._check_closed_todo_project_tasks(items)
        return result

    def unlink(self):
        # Validate the same rule as closure, including historical scope and company.
        actions = (
            self.env["community.meeting.action"]
            .sudo()
            .search([("project_task_ids", "in", self.ids)])
        )
        items = (
            self.env["community.meeting.agenda.item"]
            .sudo()
            .search([("topic_id", "in", actions.topic_id.ids)])
        )
        self.env[
            "community.meeting.project.task.mixin"
        ].sudo()._check_closed_todo_project_tasks(items, excluded_task_ids=self.ids)
        return super().unlink()

    def action_view_community_meeting_links(self):
        self.ensure_one()
        agenda_items = self.env["community.meeting.agenda.item"].search(
            [("project_task_ids", "in", self.id)]
        )
        resolutions = self.env["community.meeting.resolution"].search(
            [("project_task_ids", "in", self.id)]
        )
        actions = self.env["community.meeting.action"].search(
            [("project_task_ids", "in", self.id)]
        )
        if not agenda_items and not resolutions and not actions:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "name": _("Meeting Agenda Links"),
            "res_model": "community.meeting.project.task.links",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_agenda_item_ids": [(6, 0, agenda_items.ids)],
                "default_resolution_ids": [(6, 0, resolutions.ids)],
                "default_action_ids": [(6, 0, actions.ids)],
            },
        }


class CommunityMeetingProjectTaskLinks(models.TransientModel):
    _name = "community.meeting.project.task.links"
    _description = "Accessible Meeting Links for a Project Task"

    agenda_item_ids = fields.Many2many(
        "community.meeting.agenda.item",
        "cm_task_links_agenda_rel",
        "wizard_id",
        "agenda_item_id",
        readonly=True,
    )
    resolution_ids = fields.Many2many(
        "community.meeting.resolution",
        "cm_task_links_resolution_rel",
        "wizard_id",
        "resolution_id",
        readonly=True,
    )
    action_ids = fields.Many2many(
        "community.meeting.action",
        "cm_task_links_action_rel",
        "wizard_id",
        "action_id",
        readonly=True,
    )


class CommunityMeetingCarryover(models.Model):
    _name = "community.meeting.carryover"
    _inherit = ["community.meeting.carryover", "community.meeting.project.task.mixin"]
    _description = "Meeting Agenda Carryover"

    selected_project_task_ids = fields.Many2many(
        "project.task",
        "community_meeting_carryover_task_rel",
        "carryover_id",
        "task_id",
        string="Selected Project Tasks",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("selected_project_task_ids"):
                source_model, _source_field = self.env[
                    "community.meeting.carryover"
                ]._source_fields(vals["origin_model"])
                source = self.env[source_model].browse(vals["origin_record_id"])
                ids = self._task_ids_after_commands(vals["selected_project_task_ids"])
                self.env["community.meeting.project.task.mixin"]._check_task_links(
                    ids, source.meeting_id
                )
        return super().create(vals_list)

    def write(self, vals):
        if "selected_project_task_ids" in vals:
            if any(
                transfer.status in ("accepted", "dismissed", "cancelled")
                for transfer in self
            ):
                raise ValidationError(
                    _("Tasks on a closed carryover cannot be changed.")
                )
            for transfer in self:
                ids = self._task_ids_after_commands(
                    vals["selected_project_task_ids"],
                    transfer.selected_project_task_ids.ids,
                )
                self.env["community.meeting.project.task.mixin"]._check_task_links(
                    ids, transfer.origin_meeting_id
                )
        return super().write(vals)

    def _materialize(self, destination, automatic=False):
        item = super()._materialize(destination, automatic=automatic)
        if self.selected_project_task_ids:
            tasks = self.selected_project_task_ids
            tasks.check_access("read")
            tasks.check_access("write")
            if any(
                task.company_id and task.company_id != destination.company_id
                for task in tasks
            ):
                raise ValidationError(
                    _("A selected task does not belong to the destination company.")
                )
            item.write({"project_task_ids": [(6, 0, tasks.ids)]})
        return item


class CommunityMeetingCarryoverWizard(models.TransientModel):
    _inherit = "community.meeting.carryover.wizard"

    selected_project_task_ids = fields.Many2many(
        "project.task",
        string="Project Tasks to Carry Forward",
    )

    def _prepare_carryover_values(self):
        values = super()._prepare_carryover_values()
        tasks = self.selected_project_task_ids
        tasks.check_access("read")
        if any(
            task.company_id and task.company_id != self.company_id for task in tasks
        ):
            raise ValidationError(
                _("Selected tasks must belong to the meeting company.")
            )
        values["selected_project_task_ids"] = [(6, 0, tasks.ids)]
        return values
