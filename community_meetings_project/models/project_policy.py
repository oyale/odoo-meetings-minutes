from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

MODES = [
    ("none", "No default project"),
    ("global", "Company project"),
    ("series", "Project per series"),
]
REQUIREMENTS = [
    ("core", "Assigned meeting task or Odoo activity"),
    ("project", "Assigned follow-up with linked Project task"),
]
SCOPES = [("any", "Any accessible project"), ("configured", "Configured project only")]


class Company(models.Model):
    _inherit = "res.company"

    meeting_project_mode = fields.Selection(
        MODES, string="Project destination", default="none", required=True
    )
    meeting_project_id = fields.Many2one("project.project", check_company=True)
    meeting_todo_requirement = fields.Selection(
        REQUIREMENTS,
        string="Evidence required to close a TODO",
        default="core",
        required=True,
    )
    meeting_task_scope = fields.Selection(
        SCOPES, string="Selectable tasks", default="any", required=True
    )


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    meeting_project_mode = fields.Selection(
        related="company_id.meeting_project_mode", readonly=False
    )
    meeting_project_id = fields.Many2one(
        related="company_id.meeting_project_id", readonly=False
    )
    meeting_todo_requirement = fields.Selection(
        related="company_id.meeting_todo_requirement", readonly=False
    )
    meeting_task_scope = fields.Selection(
        related="company_id.meeting_task_scope", readonly=False
    )


class Series(models.Model):
    _inherit = "community.meeting.series"

    meeting_project_mode = fields.Selection(
        [("inherit", "Company default")] + MODES,
        string="Project destination",
        default="inherit",
        required=True,
    )
    meeting_project_id = fields.Many2one(
        "project.project", check_company=True, string="Series project"
    )
    meeting_todo_requirement = fields.Selection(
        [("inherit", "Company default")] + REQUIREMENTS,
        string="Evidence required to close a TODO",
        default="inherit",
        required=True,
    )
    meeting_task_scope = fields.Selection(
        [("inherit", "Company default")] + SCOPES,
        string="Selectable tasks",
        default="inherit",
        required=True,
    )


class Meeting(models.Model):
    _inherit = "community.meeting"

    def get_followup_defaults(self, item_id=False):
        values = super().get_followup_defaults(item_id)
        if self.env.user.has_group("project.group_project_user"):
            values["allowed_kinds"].append("task")
        return values

    def _project_policy(self):
        self.ensure_one()
        result = {}
        for key in (
            "meeting_project_mode",
            "meeting_todo_requirement",
            "meeting_task_scope",
        ):
            value = self.series_id[key] if self.series_id else "inherit"
            result[key] = self.company_id[key] if value == "inherit" else value
        return result

    def _meeting_project(self, create=False):
        self.ensure_one()
        policy = self._project_policy()
        if policy["meeting_project_mode"] == "none":
            return self.env["project.project"]
        if policy["meeting_project_mode"] == "global":
            project = self.company_id.meeting_project_id
            if not project:
                raise ValidationError(_("Configure the company meeting project first."))
            project.check_access("read")
            return project
        series = self.series_id
        if not series:
            raise ValidationError(_("A project per series requires a meeting series."))
        if create:
            series.check_access("write")
            self.env.cr.execute(
                "SELECT id FROM community_meeting_series WHERE id=%s FOR UPDATE",
                [series.id],
            )
            series.invalidate_recordset(["meeting_project_id"])
        project = series.meeting_project_id
        if not project and create:
            project = self.env["project.project"].create(
                {"name": series.name, "company_id": self.company_id.id}
            )
            series.write({"meeting_project_id": project.id})
        if project:
            project.check_access("read")
        return project


class Agenda(models.Model):
    _inherit = "community.meeting.agenda.item"

    project_requirement_snapshot = fields.Selection(
        REQUIREMENTS, readonly=True, copy=False
    )
    task_scope_snapshot = fields.Selection(SCOPES, readonly=True, copy=False)
    allowed_project_snapshot_id = fields.Many2one(
        "project.project", readonly=True, copy=False, ondelete="restrict"
    )
    requires_project_task = fields.Boolean(compute="_compute_requires_project_task")

    @api.depends(
        "disposition",
        "project_requirement_snapshot",
        "meeting_id.series_id.meeting_todo_requirement",
        "meeting_id.company_id.meeting_todo_requirement",
    )
    def _compute_requires_project_task(self):
        for item in self:
            requirement = (
                item.project_requirement_snapshot
                if item.disposition == "closed"
                else False
            )
            item.requires_project_task = (
                requirement
                or item.meeting_id._project_policy()["meeting_todo_requirement"]
            ) == "project"

    def _validate_followup_removal(self, actions):
        super()._validate_followup_removal(actions)
        self.env[
            "community.meeting.project.task.mixin"
        ].sudo()._check_closed_todo_project_tasks(self, excluded_action_ids=actions.ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if {
                "project_requirement_snapshot",
                "task_scope_snapshot",
                "allowed_project_snapshot_id",
            }.intersection(vals):
                raise UserError(
                    _("The task requirement is recorded by the point workflow.")
                )
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("disposition") == "closed":
                meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
                policy = meeting._project_policy()
                vals["project_requirement_snapshot"] = policy[
                    "meeting_todo_requirement"
                ]
                vals["task_scope_snapshot"] = policy["meeting_task_scope"]
                vals["allowed_project_snapshot_id"] = (
                    meeting._meeting_project().id
                    if policy["meeting_task_scope"] == "configured"
                    else False
                )
            prepared.append(vals)
        records = super().create(prepared)
        records._check_closed_todo_project_tasks(records)
        return records

    def write(self, vals):
        if {
            "project_requirement_snapshot",
            "task_scope_snapshot",
            "allowed_project_snapshot_id",
        }.intersection(vals):
            raise UserError(
                _("The task requirement is recorded by the point workflow.")
            )
        for item in self:
            values = dict(vals)
            if (
                values.get("disposition") == "closed"
                and item.kind == "todo"
                and item.disposition != "closed"
            ):
                policy = item.meeting_id._project_policy()
                values["project_requirement_snapshot"] = policy[
                    "meeting_todo_requirement"
                ]
                values["task_scope_snapshot"] = policy["meeting_task_scope"]
                values["allowed_project_snapshot_id"] = (
                    item.meeting_id._meeting_project().id
                    if policy["meeting_task_scope"] == "configured"
                    else False
                )
            super(Agenda, item).write(values)
        return True
