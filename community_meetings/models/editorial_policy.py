from odoo import _, api, models
from odoo.exceptions import UserError


class MeetingEditorialPolicy(models.Model):
    _inherit = "community.meeting"

    def _check_live_editorial(self, items=None, result_change=False):
        """Order editorial writes against pauses; no client-controlled bypass."""
        for meeting in self.sorted("id"):
            meeting.check_access("write")
            meeting._lock_live_workflow()
            if meeting.state in ("approved", "cancelled"):
                raise UserError(_("This meeting's editorial content is locked."))
            if meeting.state != "scheduled" or not meeting.actual_start_datetime:
                continue
            if meeting.actual_paused_at:
                raise UserError(_("Resume the meeting before editing live records."))
            for item in items.filtered(lambda i: i.meeting_id == meeting) if items is not None else []:
                item.invalidate_recordset(["actual_started_at", "disposition"])
                if not item.actual_started_at and not (result_change and item.disposition in ("closed", "discussed", "deferred")):
                    raise UserError(_("Begin or resume this point before editing live records."))

    def write(self, vals):
        if "minutes_notes" in vals:
            self._check_live_editorial()
        return super().write(vals)


class AgendaEditorialPolicy(models.Model):
    _inherit = "community.meeting.agenda.item"

    def _write_workflow_result(self, vals):
        """Use only from server-owned agreement and reopen actions."""
        self.meeting_id._check_live_editorial(self, result_change=True)
        return super().write(vals)

    def write(self, vals):
        if {"discussion_notes", "disposition", "decision_result"}.intersection(vals):
            self.meeting_id._check_live_editorial(self)
        return super().write(vals)


class ResolutionEditorialPolicy(models.Model):
    _inherit = "community.meeting.resolution"

    @api.model_create_multi
    def create(self, vals_list):
        defaults = self.default_get(["agenda_item_id", "meeting_id"])
        vals_list = [{**defaults, **vals} for vals in vals_list]
        items = self.env["community.meeting.agenda.item"].browse([v["agenda_item_id"] for v in vals_list if v.get("agenda_item_id")])
        items.meeting_id._check_live_editorial(items)
        return super().create(vals_list)

    def write(self, vals):
        self.meeting_id._check_live_editorial(self.agenda_item_id, result_change=set(vals) <= {"status", "decision_outcome"})
        return super().write(vals)


class DissentEditorialPolicy(models.Model):
    _inherit = "community.meeting.dissent"

    @api.model_create_multi
    def create(self, vals_list):
        defaults = self.default_get(["agenda_item_id", "meeting_id", "resolution_id"])
        vals_list = [{**defaults, **vals} for vals in vals_list]
        for vals in vals_list:
            item = self.env["community.meeting.agenda.item"].browse(vals.get("agenda_item_id"))
            if not item and vals.get("resolution_id"):
                item = self.env["community.meeting.resolution"].browse(vals["resolution_id"]).agenda_item_id
            self.env["community.meeting"].browse(vals.get("meeting_id"))._check_live_editorial(item)
        return super().create(vals_list)

    def write(self, vals):
        self.meeting_id._check_live_editorial(self.agenda_item_id | self.resolution_id.agenda_item_id)
        return super().write(vals)


class PrivateNoteEditorialPolicy(models.Model):
    _inherit = "community.meeting.editor.note"

    @api.model_create_multi
    def create(self, vals_list):
        defaults = self.default_get(["agenda_item_id", "meeting_id"])
        vals_list = [{**defaults, **vals} for vals in vals_list]
        for vals in vals_list:
            item = self.env["community.meeting.agenda.item"].browse(vals.get("agenda_item_id"))
            self.env["community.meeting"].browse(vals.get("meeting_id"))._check_live_editorial(item)
        return super().create(vals_list)

    def write(self, vals):
        self.meeting_id._check_live_editorial(self.agenda_item_id)
        return super().write(vals)


class FollowupEditorialPolicy(models.Model):
    _inherit = "community.meeting.action"

    @api.model_create_multi
    def create(self, vals_list):
        defaults = self.default_get(["agenda_item_id", "meeting_id"])
        vals_list = [{**defaults, **vals} for vals in vals_list]
        items = self.env["community.meeting.agenda.item"].browse([v["agenda_item_id"] for v in vals_list if v.get("agenda_item_id")])
        items.meeting_id._check_live_editorial(items)
        return super().create(vals_list)

    def write(self, vals):
        if {"name", "description", "agenda_item_id", "resolution_id", "followup_kind"}.intersection(vals):
            self.meeting_id._check_live_editorial(self.agenda_item_id)
        return super().write(vals)

    def unlink(self):
        self.filtered(lambda action: action.meeting_id.state not in ("draft", "cancelled")).meeting_id._check_live_editorial(
            self.filtered(lambda action: action.meeting_id.state not in ("draft", "cancelled")).agenda_item_id)
        return super().unlink()
