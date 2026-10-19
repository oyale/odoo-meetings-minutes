from odoo import api, fields, models


class MeetingCreateWizard(models.TransientModel):
    _inherit = "community.meeting.create.wizard"

    recurring_line_ids = fields.One2many("community.meeting.recurring.point.review.line", "wizard_id")

    def _load_recurring_points(self):
        for wizard in self:
            previous_choices = {
                line.template_id.id: line.included for line in wizard.recurring_line_ids if line.template_id
            }
            wizard.recurring_line_ids.unlink()
            if not wizard.series_id:
                continue
            wizard.series_id.check_access("read")
            templates = self.env["community.meeting.series.agenda.template"].search(
                [("series_id", "=", wizard.series_id.id), ("active", "=", True)],
                order="sequence, id",
            )
            wizard.recurring_line_ids = [
                (
                    0,
                    0,
                    {
                        "template_id": template.id,
                        "included": previous_choices.get(template.id, True),
                    },
                )
                for template in templates
            ]


class MeetingRecurringPointReviewLine(models.TransientModel):
    _name = "community.meeting.recurring.point.review.line"
    _description = "Recurring Point for Meeting Preparation"
    _order = "sequence, id"

    wizard_id = fields.Many2one("community.meeting.create.wizard", required=True, ondelete="cascade")
    template_id = fields.Many2one("community.meeting.series.agenda.template", required=True, ondelete="cascade")
    included = fields.Boolean(default=True)
    sequence = fields.Integer(related="template_id.sequence")
    name = fields.Char(related="template_id.name")
    agenda_type_id = fields.Many2one(related="template_id.agenda_type_id")
    priority = fields.Selection(related="template_id.priority")
    estimated_minutes = fields.Integer(compute="_compute_estimated_minutes")

    @api.depends(
        "template_id.estimated_minutes",
        "wizard_id.series_id.default_estimated_minutes",
        "wizard_id.series_id.company_id.meeting_estimated_minutes",
    )
    def _compute_estimated_minutes(self):
        for line in self:
            line.estimated_minutes = line.template_id.estimated_minutes or (
                line.wizard_id.series_id._point_estimated_minutes_default()
                if line.wizard_id.series_id
                else line.wizard_id.company_id.meeting_estimated_minutes
            )
