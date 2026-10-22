from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SeriesWizard(models.TransientModel):
    _inherit = "community.meeting.series.wizard"

    link_project = fields.Boolean(string="Link a Project")
    project_id = fields.Many2one("project.project", string="Project")
    new_project = fields.Boolean(string="Project source", default=False)
    new_project_name = fields.Char(string="New project name")
    created_project_id = fields.Many2one("project.project", readonly=True, copy=False)

    @api.onchange("link_project")
    def _onchange_link_project(self):
        if not self.link_project:
            self.project_id = False
            self.new_project = False
            self.new_project_name = False

    def action_finish(self):
        result = super().action_finish()
        series = self.created_series_id
        if series and self.link_project:
            series.check_access("write")
            if self.new_project:
                name = (self.new_project_name or series.name or "").strip()
                if not name:
                    raise ValidationError(_("Enter a name for the new project."))
                project = self.created_project_id or series.meeting_project_id
                if not project:
                    project = self.env["project.project"].create(
                        {
                            "name": name,
                            "company_id": series.company_id.id,
                        }
                    )
                    self.created_project_id = project
                project.check_access("read")
                if project.company_id and project.company_id != series.company_id:
                    raise ValidationError(_("The project must belong to the series company."))
            else:
                project = self.project_id
                if not project:
                    raise ValidationError(_("Choose a project or create a new one."))
                project.check_access("read")
                if project.company_id and project.company_id != series.company_id:
                    raise ValidationError(_("The project must belong to the series company."))
            series.write(
                {
                    "meeting_project_id": project.id,
                    "meeting_project_mode": "series",
                }
            )
        return result
