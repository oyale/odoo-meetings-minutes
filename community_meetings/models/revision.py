import base64
import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html_sanitize


class CommunityMeetingRevision(models.Model):
    _name = "community.meeting.revision"
    _description = "Approved Meeting Minutes Revision"
    _order = "meeting_id, revision_number desc"
    _check_company_auto = True

    meeting_id = fields.Many2one("community.meeting", required=True, ondelete="restrict", index=True, check_company=True)
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, index=True)
    revision_number = fields.Integer(required=True, readonly=True)
    created_by_id = fields.Many2one("res.users", required=True, readonly=True)
    created_at = fields.Datetime(required=True, readonly=True)
    approved_by_id = fields.Many2one("res.users", required=True, readonly=True)
    approved_at = fields.Datetime(required=True, readonly=True)
    snapshot_json = fields.Text(required=True, readonly=True)
    snapshot_sha256 = fields.Char(required=True, readonly=True, size=64, index=True)
    pdf_attachment_id = fields.Many2one("ir.attachment", readonly=True, ondelete="restrict")
    pdf_sha256 = fields.Char(readonly=True, size=64)
    status = fields.Selection(
        [("approved", "Approved"), ("superseded", "Superseded")],
        required=True, readonly=True, default="approved", index=True,
    )
    previous_revision_id = fields.Many2one("community.meeting.revision", readonly=True, ondelete="restrict")

    _sql_constraints = [
        ("meeting_revision_unique", "unique(meeting_id, revision_number)", "Revision numbers must be unique per meeting."),
    ]

    @api.model
    def _clean_html(self, value):
        return str(html_sanitize(value or ""))

    @api.model
    def _build_snapshot(self, meeting, approver, approved_at):
        meeting.ensure_one()
        agenda = []
        for item in meeting.agenda_item_ids.sorted(lambda row: (row.sequence, row.id)):
            agenda.append({
                "sequence": item.sequence,
                "name": item.name,
                "kind": item.kind,
                "type": item.agenda_type_id.name,
                "description": self._clean_html(item.description),
                "discussion": self._clean_html(item.discussion_notes),
                "disposition": item.disposition,
                "decision_result": item.decision_result or "",
                "decision_result_label": dict(item._fields["decision_result"]._description_selection(self.env)).get(item.decision_result, ""),
                "deferral_reason": item.deferral_reason or "",
                "resolutions": [{
                    "title": resolution.title,
                    "body": self._clean_html(resolution.body),
                    "status": resolution.status,
                "decision_outcome": resolution.decision_outcome or "",
                } for resolution in meeting.resolution_ids.filtered(lambda row: row.agenda_item_id == item).sorted("id")],
            })
        # Approval has already checked the approver's write access to this meeting.
        # Read only explicitly publishable dissent records; excluded private material
        # is never loaded into the snapshot.
        included_dissents = self.env["community.meeting.dissent"].sudo().search([
            ("meeting_id", "=", meeting.id), ("include_in_minutes", "=", True),
        ], order="sequence, id")
        dissents = [{
            "kind": dissent.kind,
            "body": self._clean_html(dissent.body),
            "author": dissent.author_display_name or (dissent.author_partner_id.name if dissent.author_partner_id else ""),
            "scope": dissent.resolution_id.title if dissent.resolution_id else (
                dissent.agenda_item_id.name if dissent.agenda_item_id else meeting.name
            ),
        } for dissent in included_dissents]
        carryover_records = self.env["community.meeting.carryover"].sudo().search([
            "|", ("origin_meeting_id", "=", meeting.id), ("destination_meeting_id", "=", meeting.id),
        ], order="id")
        carryovers = [{
            "origin_model": transfer.origin_model,
            "origin_name": transfer.origin_name,
            "status": transfer.status,
            "reason": transfer.reason or "",
            "destination": transfer.destination_meeting_id.code if transfer.destination_meeting_id else "",
        } for transfer in carryover_records]
        snapshot = {
            "schema_version": 1,
            "meeting": {
                "code": meeting.code,
                "name": meeting.name,
                "company": meeting.company_id.name,
                "organizer": meeting.organizer_id.name,
                "secretary": meeting.secretary_id.name or "",
                "attendees": sorted(meeting.attendee_partner_ids.mapped("name")),
                "start_datetime": fields.Datetime.to_string(meeting.start_datetime) if meeting.start_datetime else "",
                "end_datetime": fields.Datetime.to_string(meeting.end_datetime) if meeting.end_datetime else "",
                "location": meeting.location or "",
                "meeting_url": meeting.meeting_url or "",
                "description": self._clean_html(meeting.description),
                "minutes_notes": self._clean_html(meeting.minutes_notes),
            },
            "agenda": agenda,
            "general_resolutions": [{
                "title": resolution.title,
                "body": self._clean_html(resolution.body),
                "status": resolution.status,
                "decision_outcome": resolution.decision_outcome or "",
            } for resolution in meeting.resolution_ids.filtered(lambda row: not row.agenda_item_id).sorted("id")],
            "actions": [{
                "name": action.name,
                "description": self._clean_html(action.description),
                "resolution": action.resolution_id.title if action.resolution_id else "",
                "agenda_item": action.agenda_item_id.name if action.agenda_item_id else "",
                "responsible": action.responsible_user_id.name or "",
                "deadline": fields.Date.to_string(action.deadline) if action.deadline else "",
                "state": action.state,
            } for action in meeting.action_ids.sorted(lambda row: (row.deadline or fields.Date.today(), row.id))],
            "dissents": dissents,
            "carryovers": carryovers,
            "approval": {
                "approver": approver.name,
                "approved_at": fields.Datetime.to_string(approved_at),
            },
        }
        snapshot["extensions"] = self._get_snapshot_extensions(meeting, approver, approved_at)
        return snapshot

    @api.model
    def _get_snapshot_extensions(self, meeting, approver, approved_at):
        """Return deterministic, JSON-serializable extension payloads keyed by addon."""
        return {}

    @api.model
    def _create_approved_revision(self, meeting):
        if not self.env.user.has_group("community_meetings.group_meeting_approver"):
            raise AccessError(_("Only an authorized approver can create a minutes revision."))
        meeting.check_access_rights("read")
        meeting.check_access_rule("read")
        self.env.cr.execute(
            "SELECT id FROM community_meeting WHERE id = %s FOR UPDATE", [meeting.id],
        )
        meeting.invalidate_recordset(["state", "revision_ids", "approved_revision_id"])
        if meeting.state != "minutes_draft":
            raise UserError(_("Only draft minutes can be approved."))
        if not meeting.agenda_item_ids:
            raise ValidationError(_("Add at least one agenda item before approval."))
        approved_at = fields.Datetime.now()
        snapshot = self._build_snapshot(meeting, self.env.user, approved_at)
        snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        previous = meeting.revision_ids.sorted("revision_number")[-1:] or self.browse()
        revision_number = previous.revision_number + 1 if previous else 1
        revision = self.sudo().create({
            "meeting_id": meeting.id,
            "revision_number": revision_number,
            "created_by_id": self.env.uid,
            "created_at": approved_at,
            "approved_by_id": self.env.uid,
            "approved_at": approved_at,
            "snapshot_json": snapshot_json,
            "snapshot_sha256": digest,
            "previous_revision_id": previous.id if previous else False,
            "status": "approved",
        })
        pdf, report_type = self.env["ir.actions.report"].with_context(
            force_report_rendering=True, report_pdf_no_attachment=True,
        )._render_qweb_pdf("community_meetings.report_revision_document", revision.ids)
        if report_type != "pdf" or not pdf.startswith(b"%PDF"):
            raise UserError(_("The approved minutes PDF could not be rendered."))
        attachment = self.env["ir.attachment"].sudo().create({
            "name": f"{meeting.code}-revision-{revision_number}.pdf",
            "type": "binary",
            "datas": base64.b64encode(pdf),
            "mimetype": "application/pdf",
            "res_model": revision._name,
            "res_id": revision.id,
            "public": False,
        })
        super(CommunityMeetingRevision, revision).write({
            "pdf_attachment_id": attachment.id,
            "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
        })
        if previous:
            super(CommunityMeetingRevision, previous.sudo()).write({"status": "superseded"})
        return revision.with_env(self.env)

    def write(self, vals):
        raise UserError(_("Approved revision content is immutable."))

    def unlink(self):
        raise UserError(_("Approved revisions are permanent records."))

    def copy(self, default=None):
        raise UserError(_("Approved revisions cannot be copied."))
