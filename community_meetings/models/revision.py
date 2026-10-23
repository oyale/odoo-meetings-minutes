import base64
import hashlib
import json
from typing import ClassVar

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html_sanitize
from odoo.tools.misc import format_datetime, format_time


class CommunityMeetingRevision(models.Model):
    _name = "community.meeting.revision"
    _description = "Approved Meeting Minutes Revision"
    _order = "meeting_id, revision_number desc"
    _check_company_auto = True

    meeting_id = fields.Many2one(
        "community.meeting",
        required=True,
        ondelete="restrict",
        index=True,
        check_company=True,
    )
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
        required=True,
        readonly=True,
        default="approved",
        index=True,
    )
    previous_revision_id = fields.Many2one("community.meeting.revision", readonly=True, ondelete="restrict")

    _sql_constraints: ClassVar[list[tuple[str, str, str]]] = [
        (
            "meeting_revision_unique",
            "unique(meeting_id, revision_number)",
            "Revision numbers must be unique per meeting.",
        ),
    ]

    @api.model
    def _clean_html(self, value):
        return str(html_sanitize(value or ""))

    @api.model
    def _build_public_content(self, meeting, timezone=None):
        meeting.ensure_one()
        timezone = timezone or self.env.user.tz or "UTC"
        carryover_records = (
            self.env["community.meeting.carryover"]
            .sudo()
            .search(
                [
                    "|",
                    ("origin_meeting_id", "=", meeting.id),
                    ("destination_meeting_id", "=", meeting.id),
                ],
                order="id",
            )
        )
        moved_by_item = {}
        for transfer in carryover_records:
            origin_item = transfer.origin_agenda_item_id
            if not origin_item and transfer.origin_resolution_id:
                origin_item = transfer.origin_resolution_id.agenda_item_id
            if not origin_item and transfer.origin_action_id:
                origin_item = transfer.origin_action_id.agenda_item_id
            if not origin_item:
                continue
            if transfer.destination_meeting_id:
                destination = " — ".join(
                    part
                    for part in [
                        transfer.destination_meeting_id.code,
                        transfer.destination_meeting_id.name,
                    ]
                    if part
                )
                moved_by_item[origin_item.id] = {
                    "kind": "meeting",
                    "destination": destination,
                }
            else:
                series = transfer.destination_series_id or transfer.series_id
                if series:
                    moved_by_item[origin_item.id] = {
                        "kind": "series",
                        "destination": series.name or "",
                    }
        agenda = []
        for sequence, item in enumerate(
            meeting.agenda_item_ids.sorted(lambda row: (row.sequence, row.id)),
            start=1,
        ):
            moved = moved_by_item.get(item.id, {})
            agenda.append(
                {
                    # Internal order values reserve slots for structural points;
                    # published minutes use clean, contiguous presentation numbers.
                    "id": item.id,
                    "sequence": sequence,
                    "topic_id": item.topic_id.id,
                    "priority": item.priority,
                    "deadline": fields.Date.to_string(item.deadline) if item.deadline else "",
                    "estimated_minutes": item.estimated_minutes,
                    "moved_to": moved.get("destination", ""),
                    "moved_to_kind": moved.get("kind", ""),
                    "name": item.name,
                    "kind": item.kind,
                    "type": item.agenda_type_id.name,
                    "presenter": item.presenter_partner_id.name or "",
                    "related": [
                        {"name": topic.name, "state": topic.state or ""} for topic in item.topic_id.related_topic_ids
                    ]
                    if item.topic_id
                    else [],
                    "description": self._clean_html(item.description),
                    "discussion": self._clean_html(item.discussion_notes),
                    "disposition": item.disposition,
                    "decision_result": item.decision_result or "",
                    "decision_result_label": dict(
                        item._fields["decision_result"]._description_selection(self.env)
                    ).get(item.decision_result, ""),
                    "next_meeting_datetime": (
                        fields.Datetime.to_string(item.next_meeting_datetime) if item.next_meeting_datetime else ""
                    ),
                    "next_meeting_datetime_display": format_datetime(
                        self.env,
                        item.next_meeting_datetime,
                        tz=timezone,
                        dt_format="short",
                    )
                    if item.next_meeting_datetime
                    else "",
                    "next_meeting_timezone": timezone if item.next_meeting_datetime else "",
                    "deferral_reason": item.deferral_reason or "",
                    "deferral_reason_code": item.deferral_reason_code or "",
                    "resolutions": [
                        {
                            "title": resolution.title,
                            "body": self._clean_html(resolution.body),
                            "status": resolution.status,
                            "decision_outcome": resolution.decision_outcome or "",
                        }
                        for resolution in meeting.resolution_ids.filtered(
                            lambda row, item=item: row.agenda_item_id == item
                        ).sorted("id")
                    ],
                }
            )
        # Approval has already checked the approver's write access to this meeting.
        # Every recorded dissent belongs to the minutes; private editorial notes
        # remain a separate model and are never loaded into the snapshot.
        meeting_dissents = (
            self.env["community.meeting.dissent"]
            .sudo()
            .search(
                [("meeting_id", "=", meeting.id)],
                order="sequence, id",
            )
        )
        dissents = [
            {
                "kind": dissent.reason_id.name or "",
                "body": self._clean_html(dissent.body),
                "author": dissent.author_display_name
                or (dissent.author_partner_id.name if dissent.author_partner_id else ""),
                "scope": dissent.resolution_id.title
                if dissent.resolution_id
                else (dissent.agenda_item_id.name if dissent.agenda_item_id else meeting.name),
            }
            for dissent in meeting_dissents
        ]
        carryovers = [
            {
                "origin_model": transfer.origin_model,
                "origin_name": transfer.origin_name,
                "origin_meeting": " — ".join(
                    part for part in [transfer.origin_meeting_id.code, transfer.origin_meeting_id.name] if part
                ),
                "status": transfer.status,
                "reason": transfer.reason or "",
                "destination": transfer.destination_meeting_id.code if transfer.destination_meeting_id else "",
                "destination_meeting": " — ".join(
                    part
                    for part in [
                        transfer.destination_meeting_id.code,
                        transfer.destination_meeting_id.name,
                    ]
                    if part
                )
                if transfer.destination_meeting_id
                else "",
                "destination_series": {
                    "id": (transfer.destination_series_id or transfer.series_id).id,
                    "name": (transfer.destination_series_id or transfer.series_id).name or "",
                },
            }
            for transfer in carryover_records
        ]
        actual_start = meeting.actual_start_datetime
        actual_end = meeting.actual_end_datetime
        reference_start = actual_start or meeting.start_datetime
        same_day = bool(
            actual_end
            and reference_start
            and pytz.utc.localize(reference_start).astimezone(pytz.timezone(timezone)).date()
            == pytz.utc.localize(actual_end).astimezone(pytz.timezone(timezone)).date()
        )
        snapshot = {
            "schema_version": 3,
            "meeting": {
                "code": meeting.code,
                "name": meeting.name,
                "company": meeting.company_id.name,
                "organizer": meeting.organizer_id.name,
                "secretary": meeting.secretary_id.name or "",
                "attendees": sorted(meeting.attendee_partner_ids.mapped("name")),
                "start_datetime": fields.Datetime.to_string(meeting.start_datetime) if meeting.start_datetime else "",
                "end_datetime": fields.Datetime.to_string(meeting.end_datetime) if meeting.end_datetime else "",
                "start_datetime_display": format_datetime(
                    self.env,
                    meeting.start_datetime,
                    tz=timezone,
                    dt_format="short",
                )
                if meeting.start_datetime
                else "",
                "start_timezone": timezone if meeting.start_datetime else "",
                "actual_start_datetime_display": format_datetime(
                    self.env,
                    actual_start,
                    tz=timezone,
                    dt_format="short",
                )
                if actual_start
                else "",
                "actual_start_timezone": timezone if actual_start else "",
                "actual_end_same_day": same_day,
                "actual_end_time_display": format_time(self.env, actual_end, tz=timezone)
                if actual_end and same_day
                else "",
                "actual_end_datetime_display": format_datetime(
                    self.env,
                    actual_end,
                    tz=timezone,
                    dt_format="short",
                )
                if actual_end
                else "",
                "actual_end_timezone": timezone if meeting.actual_end_datetime else "",
                "location": meeting.location or "",
                "meeting_url": meeting.meeting_url or "",
                "description": self._clean_html(meeting.description),
                "minutes_notes": self._clean_html(meeting.minutes_notes),
            },
            "agenda": agenda,
            "general_resolutions": [
                {
                    "title": resolution.title,
                    "body": self._clean_html(resolution.body),
                    "status": resolution.status,
                    "decision_outcome": resolution.decision_outcome or "",
                }
                for resolution in meeting.resolution_ids.filtered(lambda row: not row.agenda_item_id).sorted("id")
            ],
            "actions": [
                {
                    "name": action.name,
                    "description": self._clean_html(action.description),
                    "resolution": action.resolution_id.title if action.resolution_id else "",
                    "agenda_item": action.agenda_item_id.name if action.agenda_item_id else "",
                    "agenda_item_id": action.agenda_item_id.id or 0,
                    "activity_type": action.followup_activity_type_id.name or "",
                    "responsible": action.responsible_user_id.name or "",
                    "responsibles": sorted(action.responsible_user_ids.mapped("name")),
                    "followup_kind": action.followup_kind,
                    "deadline": fields.Date.to_string(action.deadline) if action.deadline else "",
                    "state": action.state,
                }
                for action in meeting.action_ids.sorted(lambda row: (row.deadline or fields.Date.today(), row.id))
            ],
            "dissents": dissents,
            "carryovers": carryovers,
        }
        return snapshot

    @api.model
    def _build_snapshot(self, meeting, approver, approved_at):
        timezone = meeting.series_id.timezone or meeting.company_id.partner_id.tz or "UTC"
        snapshot = self._build_public_content(meeting, timezone=timezone)
        snapshot["approval"] = {
            "approver": approver.name,
            "approved_at": fields.Datetime.to_string(approved_at),
        }
        snapshot["extensions"] = self._get_snapshot_extensions(meeting, approver, approved_at)
        return snapshot

    @api.model
    def _get_snapshot_extensions(self, meeting, approver, approved_at):
        """Return deterministic, JSON-serializable extension payloads keyed by addon."""
        return {}

    @api.model
    def _create_approved_revision(self, meeting, approval_point=None, offline=False):
        if approval_point:
            point_meeting = approval_point.meeting_id
            live_editor_approval = (
                not offline
                and self.env.user.has_group("community_meetings.group_meeting_editor")
                and point_meeting.state == "scheduled"
                and point_meeting.actual_start_datetime
                and not point_meeting.actual_end_datetime
            )
            offline_secretary_approval = (
                offline
                and point_meeting.secretary_id == self.env.user
                and point_meeting.state == "minutes_draft"
                and not point_meeting.actual_start_datetime
            )
            if not (live_editor_approval or offline_secretary_approval):
                raise AccessError(
                    _(
                        "Only the assigned minutes secretary can approve from this point; live approval also "
                        "requires the Editor role and edit access."
                    )
                )
            if (
                approval_point.kind != "minutes_approval"
                or point_meeting.series_id != meeting.series_id
                or not point_meeting.start_datetime
                or point_meeting.start_datetime <= meeting.start_datetime
            ):
                raise UserError(_("The minutes approval point must belong to a later meeting in this series."))
        elif not self.env.user.has_group("community_meetings.group_meeting_approver"):
            raise AccessError(_("Only an authorized approver can create a minutes revision."))
        meeting.check_access("read")
        self.env.cr.execute(
            "SELECT id FROM community_meeting WHERE id = %s FOR UPDATE",
            [meeting.id],
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
        # Approvers are read-only on the meeting; sudo is required to mint the
        # immutable revision record. Keep the payload fixed (no live fields).
        revision = self.sudo().create(
            {
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
            }
        )
        pdf, report_type = (
            self.env["ir.actions.report"]
            .with_context(
                force_report_rendering=True,
                report_pdf_no_attachment=True,
            )
            ._render_qweb_pdf("community_meetings.report_revision_document", revision.ids)
        )
        if report_type != "pdf" or not pdf.startswith(b"%PDF"):
            raise UserError(_("The approved minutes PDF could not be rendered."))
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": f"{meeting.code}-revision-{revision_number}.pdf",
                    "type": "binary",
                    "datas": base64.b64encode(pdf),
                    "mimetype": "application/pdf",
                    "res_model": revision._name,
                    "res_id": revision.id,
                    "public": False,
                }
            )
        )
        super(CommunityMeetingRevision, revision).write(
            {
                "pdf_attachment_id": attachment.id,
                "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
            }
        )
        if previous:
            super(CommunityMeetingRevision, previous.sudo()).write({"status": "superseded"})
        return revision.with_env(self.env)

    def write(self, vals):
        raise UserError(_("Approved revision content is immutable."))

    def unlink(self):
        raise UserError(_("Approved revisions are permanent records."))

    def copy(self, default=None):
        raise UserError(_("Approved revisions cannot be copied."))

    def action_download_pdf(self):
        self.ensure_one()
        self.check_access("read")
        self.meeting_id.check_access("read")
        if not self.pdf_attachment_id:
            raise UserError(_("The approved PDF is unavailable."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.pdf_attachment_id.id}?download=true",
            "target": "self",
        }

    def get_approved_minutes_preview_html(self):
        self.ensure_one()
        self.check_access("read")
        self.meeting_id.check_access("read")
        return self.env["report.community_meetings.report_revision_document"]._render_revision_preview(self)
