from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProjectTaskLinkChecks(models.AbstractModel):
    """Shared authorization and company checks for optional task links."""

    _name = "community.meeting.project.task.mixin"
    _description = "Community Meeting Project Task Link Checks"
    _abstract = True

    def _check_task_links(self, task_ids, meeting):
        if not task_ids:
            return self.env["project.task"]
        tasks = self.env["project.task"].browse(task_ids).exists()
        if set(tasks.ids) != set(task_ids):
            raise ValidationError(_("One or more linked tasks are unavailable."))
        tasks.check_access_rights("read")
        tasks.check_access_rule("read")
        tasks.check_access_rights("write")
        tasks.check_access_rule("write")
        if any(task.company_id and task.company_id != meeting.company_id for task in tasks):
            raise ValidationError(_("Linked tasks must belong to the meeting company."))
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
        records = super().read(fields=fields, load=load)
        link_fields = {"project_task_ids", "selected_project_task_ids"}
        if fields is not None and not link_fields.intersection(fields):
            return records
        returned_link_fields = link_fields.intersection(records[0]) if records else set()
        linked_ids = {
            task_id for values in records for field_name in returned_link_fields
            for task_id in values.get(field_name, [])
        }
        try:
            visible_ids = set(self.env["project.task"].search([("id", "in", list(linked_ids))]).ids)
        except AccessError:
            visible_ids = set()
        for values in records:
            for field_name in returned_link_fields:
                values[field_name] = [task_id for task_id in values[field_name] if task_id in visible_ids]
        return records


class CommunityMeetingAgendaItem(models.Model):
    _name = "community.meeting.agenda.item"
    _inherit = ["community.meeting.agenda.item", "community.meeting.project.task.mixin"]
    _description = "Meeting Agenda Item"

    project_task_ids = fields.Many2many(
        "project.task", "community_meeting_agenda_task_rel", "agenda_item_id", "task_id",
        string="Project Tasks",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("project_task_ids"):
                meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
                ids = self._task_ids_after_commands(vals["project_task_ids"])
                self.env["community.meeting.project.task.mixin"]._check_task_links(ids, meeting)
        return super().create(vals_list)

    def write(self, vals):
        if "project_task_ids" in vals:
            for record in self:
                ids = self._task_ids_after_commands(vals["project_task_ids"], record.project_task_ids.ids)
                self.env["community.meeting.project.task.mixin"]._check_task_links(ids, record.meeting_id)
        return super().write(vals)


class CommunityMeetingResolution(models.Model):
    _name = "community.meeting.resolution"
    _inherit = ["community.meeting.resolution", "community.meeting.project.task.mixin"]
    _description = "Meeting Resolution"

    project_task_ids = fields.Many2many(
        "project.task", "community_meeting_resolution_task_rel", "resolution_id", "task_id",
        string="Project Tasks",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("project_task_ids"):
                meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
                ids = self._task_ids_after_commands(vals["project_task_ids"])
                self.env["community.meeting.project.task.mixin"]._check_task_links(ids, meeting)
        return super().create(vals_list)

    def write(self, vals):
        if "project_task_ids" in vals:
            for record in self:
                ids = self._task_ids_after_commands(vals["project_task_ids"], record.project_task_ids.ids)
                self.env["community.meeting.project.task.mixin"]._check_task_links(ids, record.meeting_id)
        return super().write(vals)


class CommunityMeetingAction(models.Model):
    _name = "community.meeting.action"
    _inherit = ["community.meeting.action", "community.meeting.project.task.mixin"]
    _description = "Meeting Follow-up Action"

    project_task_ids = fields.Many2many(
        "project.task", "community_meeting_action_task_rel", "action_id", "task_id",
        string="Project Tasks",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("project_task_ids"):
                meeting = self.env["community.meeting"].browse(vals.get("meeting_id"))
                ids = self._task_ids_after_commands(vals["project_task_ids"])
                self.env["community.meeting.project.task.mixin"]._check_task_links(ids, meeting)
        return super().create(vals_list)

    def write(self, vals):
        if "project_task_ids" in vals:
            for record in self:
                ids = self._task_ids_after_commands(vals["project_task_ids"], record.project_task_ids.ids)
                self.env["community.meeting.project.task.mixin"]._check_task_links(ids, record.meeting_id)
        return super().write(vals)

    def action_create_project_task(self):
        self.ensure_one()
        self.check_access_rights("write")
        self.check_access_rule("write")
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Project Task"),
            "res_model": "community.meeting.project.task.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_action_id": self.id, "default_name": self.name},
        }


class CommunityMeetingProjectTaskWizard(models.TransientModel):
    _name = "community.meeting.project.task.wizard"
    _description = "Create and Link a Project Task"

    action_id = fields.Many2one("community.meeting.action", required=True, readonly=True)
    project_id = fields.Many2one("project.project", required=True)
    name = fields.Char(required=True)

    def action_create(self):
        self.ensure_one()
        self.action_id.check_access_rights("write")
        self.action_id.check_access_rule("write")
        self.env["project.task"].check_access_rights("create")
        if self.project_id.company_id and self.project_id.company_id != self.action_id.meeting_id.company_id:
            raise ValidationError(_("The project must belong to the meeting company."))
        task = self.env["project.task"].create({
            "name": self.name,
            "project_id": self.project_id.id,
        })
        self.action_id.write({"project_task_ids": [(4, task.id)]})
        return {"type": "ir.actions.act_window_close"}


class ProjectTask(models.Model):
    _inherit = "project.task"

    def action_view_community_meeting_links(self):
        self.ensure_one()
        agenda_items = self.env["community.meeting.agenda.item"].search([("project_task_ids", "in", self.id)])
        resolutions = self.env["community.meeting.resolution"].search([("project_task_ids", "in", self.id)])
        actions = self.env["community.meeting.action"].search([("project_task_ids", "in", self.id)])
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
        "community.meeting.agenda.item", "cm_task_links_agenda_rel", "wizard_id", "agenda_item_id", readonly=True,
    )
    resolution_ids = fields.Many2many(
        "community.meeting.resolution", "cm_task_links_resolution_rel", "wizard_id", "resolution_id", readonly=True,
    )
    action_ids = fields.Many2many(
        "community.meeting.action", "cm_task_links_action_rel", "wizard_id", "action_id", readonly=True,
    )


class CommunityMeetingCarryover(models.Model):
    _name = "community.meeting.carryover"
    _inherit = ["community.meeting.carryover", "community.meeting.project.task.mixin"]
    _description = "Meeting Agenda Carryover"

    selected_project_task_ids = fields.Many2many(
        "project.task", "community_meeting_carryover_task_rel", "carryover_id", "task_id",
        string="Selected Project Tasks",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("selected_project_task_ids"):
                source_model, _source_field = self.env["community.meeting.carryover"]._source_fields(vals["origin_model"])
                source = self.env[source_model].browse(vals["origin_record_id"])
                ids = self._task_ids_after_commands(vals["selected_project_task_ids"])
                self.env["community.meeting.project.task.mixin"]._check_task_links(ids, source.meeting_id)
        return super().create(vals_list)

    def write(self, vals):
        if "selected_project_task_ids" in vals:
            if any(transfer.status in ("accepted", "dismissed", "cancelled") for transfer in self):
                raise ValidationError(_("Tasks on a closed carryover cannot be changed."))
            for transfer in self:
                ids = self._task_ids_after_commands(vals["selected_project_task_ids"], transfer.selected_project_task_ids.ids)
                self.env["community.meeting.project.task.mixin"]._check_task_links(ids, transfer.origin_meeting_id)
        return super().write(vals)

    def _materialize(self, destination, automatic=False):
        item = super()._materialize(destination, automatic=automatic)
        if self.selected_project_task_ids:
            tasks = self.selected_project_task_ids
            tasks.check_access_rights("read")
            tasks.check_access_rule("read")
            tasks.check_access_rights("write")
            tasks.check_access_rule("write")
            if any(task.company_id and task.company_id != destination.company_id for task in tasks):
                raise ValidationError(_("A selected task does not belong to the destination company."))
            item.write({"project_task_ids": [(6, 0, tasks.ids)]})
        return item


class CommunityMeetingCarryoverWizard(models.TransientModel):
    _inherit = "community.meeting.carryover.wizard"

    selected_project_task_ids = fields.Many2many(
        "project.task", string="Project Tasks to Carry Forward",
    )

    def action_request(self):
        self.ensure_one()
        model, _field = self.env["community.meeting.carryover"]._source_fields(self.origin_model)
        source = self.env[model].browse(self.origin_record_id).exists()
        if not source or source.meeting_id != self.origin_meeting_id:
            raise ValidationError(_("The selected follow-up source is unavailable."))
        tasks = self.selected_project_task_ids
        tasks.check_access_rights("read")
        tasks.check_access_rule("read")
        if any(task.company_id and task.company_id != self.company_id for task in tasks):
            raise ValidationError(_("Selected tasks must belong to the meeting company."))
        self.env["community.meeting.carryover"].create({
            "origin_model": self.origin_model,
            "origin_record_id": source.id,
            "destination_meeting_id": self.destination_meeting_id.id,
            "reason": self.reason,
            "selected_project_task_ids": [(6, 0, tasks.ids)],
        })
        return {"type": "ir.actions.act_window_close"}
