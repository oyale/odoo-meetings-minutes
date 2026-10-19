from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .followup_activity import FOLLOWUP_KIND_CODES
from .topic import PRIORITIES


class MeetingSeriesAgendaTemplate(models.Model):
    _name = "community.meeting.series.agenda.template"
    _description = "Recurring Meeting Agenda Point"
    _order = "sequence, id"
    _check_company_auto = True

    series_id = fields.Many2one(
        "community.meeting.series", required=True, ondelete="cascade", check_company=True
    )
    company_id = fields.Many2one(related="series_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    description = fields.Html()
    agenda_type_id = fields.Many2one(
        "community.meeting.agenda.type",
        string="Point type",
        required=True,
        default=lambda self: self.env.ref("community_meetings.agenda_type_discussion"),
        ondelete="restrict",
    )
    priority = fields.Selection(PRIORITIES, default="1", required=True)
    estimated_minutes = fields.Integer(
        help="Leave at zero to use the series or company default."
    )
    presenter_partner_id = fields.Many2one("res.partner", string="Responsible")
    followup_allowed_kinds = fields.Many2many(
        "community.meeting.followup.kind",
        "community_meeting_series_agenda_template_followup_rel",
        "template_id",
        "kind_id",
        string="Allowed follow-up types",
    )
    followup_default_kind = fields.Selection(
        [("inherit", "Series/company default")] + FOLLOWUP_KIND_CODES,
        default="inherit",
        required=True,
    )

    @api.constrains("estimated_minutes")
    def _check_estimated_minutes(self):
        if any(template.estimated_minutes < 0 for template in self):
            raise ValidationError(_("Estimated minutes cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("Only meeting editors can manage recurring agenda points."))
        series_ids = [values.get("series_id") for values in vals_list]
        self.env["community.meeting.series"].browse(series_ids).check_access("write")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("Only meeting editors can manage recurring agenda points."))
        self.series_id.check_access("write")
        if "series_id" in vals:
            self.env["community.meeting.series"].browse(vals["series_id"]).check_access("write")
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise UserError(_("Only meeting editors can manage recurring agenda points."))
        self.series_id.check_access("write")
        return super().unlink()

    def _create_occurrence(self, meeting):
        self.ensure_one()
        meeting.check_access("write")
        if meeting.series_id != self.series_id:
            raise ValidationError(_("A recurring point can only be added to a meeting in its series."))

        previous_item = self.env["community.meeting.agenda.item"].search(
            [
                ("topic_id.recurring_template_id", "=", self.id),
                ("meeting_id.series_id", "=", self.series_id.id),
                ("meeting_id.start_datetime", "<", meeting.start_datetime),
            ],
            order="meeting_id.start_datetime desc, id desc",
            limit=1,
        )
        topic = self.env["community.meeting.topic"].create(
            {
                "name": self.name,
                "description": self.description,
                "agenda_type_id": self.agenda_type_id.id,
                "priority": self.priority,
                "estimated_minutes": self.estimated_minutes
                or self.series_id._point_estimated_minutes_default(),
                "presenter_partner_id": self.presenter_partner_id.id or False,
                "followup_allowed_kinds": [(6, 0, self.followup_allowed_kinds.ids)],
                "followup_default_kind": self.followup_default_kind,
                "company_id": self.series_id.company_id.id,
                "series_id": self.series_id.id,
                "recurring_template_id": self.id,
                "previous_occurrence_id": previous_item.topic_id.id or False,
            }
        )
        return self.env["community.meeting.agenda.item"].create(
            {"meeting_id": meeting.id, "topic_id": topic.id}
        )
