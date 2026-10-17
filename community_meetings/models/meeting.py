from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class CommunityMeeting(models.Model):
    _name = "community.meeting"
    _description = "Community Meeting"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, readonly=True, copy=False, default="New", tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    organizer_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user,
        check_company=True, tracking=True,
    )
    secretary_id = fields.Many2one(
        "res.users", string="Minutes secretary", check_company=True, tracking=True,
        default=lambda self: self.env.user,
    )
    editor_user_ids = fields.Many2many(
        "res.users", "community_meeting_editor_rel", "meeting_id", "user_id",
        string="Editors", check_company=True,
    )
    reader_user_ids = fields.Many2many(
        "res.users", "community_meeting_reader_rel", "meeting_id", "user_id",
        string="Readers", check_company=True,
    )
    attendee_partner_ids = fields.Many2many("res.partner", string="Attendees")
    start_datetime = fields.Datetime(string="Estimated Start Datetime", tracking=True)
    end_datetime = fields.Datetime(string="Estimated End Datetime", tracking=True)
    actual_start_datetime = fields.Datetime(readonly=True, copy=False, tracking=True)
    actual_paused_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    actual_paused_seconds = fields.Integer(readonly=True, copy=False, default=0)
    actual_end_datetime = fields.Datetime(readonly=True, copy=False, tracking=True)
    actual_duration_minutes = fields.Integer(
        string="Actual duration (minutes)", compute="_compute_actual_duration_minutes", store=True
    )
    location = fields.Char()
    meeting_url = fields.Char()
    description = fields.Html()
    minutes_notes = fields.Html()
    meeting_kind_id = fields.Many2one(
        "community.meeting.kind", string="Kind", required=True, ondelete="restrict",
        default=lambda self: self.env.ref("community_meetings.kind_operational", raise_if_not_found=False),
    )
    series_id = fields.Many2one(
        "community.meeting.series", check_company=True, ondelete="restrict",
    )
    series_carryover_policy = fields.Selection(related="series_id.carryover_policy", readonly=True)
    series_description = fields.Html(related="series_id.description", readonly=True, string="Series description")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("held", "Held"),
            ("minutes_draft", "Minutes Draft"),
            ("approved", "Approved"),
            ("cancelled", "Cancelled"),
        ], default="draft", required=True, copy=False, tracking=True, index=True,
    )
    agenda_item_ids = fields.One2many("community.meeting.agenda.item", "meeting_id")
    resolution_ids = fields.One2many("community.meeting.resolution", "meeting_id")
    action_ids = fields.One2many("community.meeting.action", "meeting_id")
    incoming_carryover_ids = fields.One2many(
        "community.meeting.carryover", "destination_meeting_id",
        groups="community_meetings.group_meeting_editor",
    )
    private_note_ids = fields.One2many(
        "community.meeting.editor.note", "meeting_id", groups="community_meetings.group_meeting_editor",
    )
    dissent_ids = fields.One2many(
        "community.meeting.dissent", "meeting_id", groups="community_meetings.group_meeting_editor",
    )
    carryover_ids = fields.One2many(
        "community.meeting.carryover", "origin_meeting_id",
        groups="community_meetings.group_meeting_editor",
    )
    revision_ids = fields.One2many("community.meeting.revision", "meeting_id", copy=False)
    approved_revision_id = fields.Many2one(
        "community.meeting.revision", readonly=True, copy=False, ondelete="restrict",
    )

    _sql_constraints = [
        ("code_company_unique", "unique(company_id, code)", "Meeting references must be unique per company."),
    ]

    @api.depends("actual_start_datetime", "actual_end_datetime", "actual_paused_seconds")
    def _compute_actual_duration_minutes(self):
        for meeting in self:
            if meeting.actual_start_datetime and meeting.actual_end_datetime:
                seconds = (meeting.actual_end_datetime - meeting.actual_start_datetime).total_seconds()
                seconds -= meeting.actual_paused_seconds
                meeting.actual_duration_minutes = max(0, round(seconds / 60))
            else:
                meeting.actual_duration_minutes = 0

    @api.constrains("start_datetime", "end_datetime")
    def _check_end_after_start(self):
        for meeting in self:
            if meeting.start_datetime and meeting.end_datetime and meeting.end_datetime < meeting.start_datetime:
                raise ValidationError(_("The meeting end must be after its start."))

    @api.onchange("start_datetime")
    def _onchange_start_datetime(self):
        for meeting in self:
            if meeting.start_datetime and not meeting.end_datetime:
                meeting.end_datetime = fields.Datetime.add(meeting.start_datetime, hours=1)

    @api.onchange("series_id")
    def _onchange_series_id(self):
        for meeting in self:
            if meeting.series_id:
                meeting.meeting_kind_id = meeting.series_id.meeting_kind_id

    @api.constrains("series_id", "company_id", "meeting_kind_id")
    def _check_series_scope(self):
        for meeting in self:
            if meeting.series_id and (
                meeting.series_id.company_id != meeting.company_id
                or meeting.series_id.meeting_kind_id != meeting.meeting_kind_id
                or not meeting.series_id.active
            ):
                raise ValidationError(_("The meeting series must be active and match the meeting company and kind."))

    def _prepare_notice_values(self):
        """Return core notice values; extensions may add their own fields."""
        self.ensure_one()
        return {"meeting_id": self.id, "recipient_partner_ids": self.attendee_partner_ids.ids}

    @api.model
    def _resolve_invitees(self, manual_partner_ids=None):
        """Resolve explicitly supplied contacts; extensions may add authorized sources."""
        return self.env["res.partner"].browse(manual_partner_ids or []).exists()

    def _validate_before_approval(self):
        """Extension hook for approval checks. Core operational rules run separately."""
        return True

    def _lock_live_workflow(self):
        # A row update also serializes repeatable-read snapshots, so concurrent
        # live writes are retried by Odoo instead of validating stale state.
        for meeting in self.sorted("id"):
            self.env.cr.execute("UPDATE community_meeting SET write_date=clock_timestamp() WHERE id=%s", [meeting.id])
        self.invalidate_recordset(["state", "actual_start_datetime", "actual_paused_at", "actual_end_datetime"])

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise AccessError(_("You are not allowed to create meetings."))
        for vals in vals_list:
            if vals.get("code") not in (None, False, "New"):
                raise ValidationError(_("Meeting references are assigned by the system."))
            if vals.get("approved_revision_id") or vals.get("revision_ids"):
                raise ValidationError(_("Approved revisions cannot be assigned during meeting creation."))
            if vals.get("code", "New") == "New":
                # Editors may create meetings but should not gain general sequence access.
                code = self.env["ir.sequence"].sudo().next_by_code("community.meeting")
                if not code:
                    raise ValidationError(_("The meeting reference sequence is not configured."))
                vals["code"] = code
            if vals.get("state", "draft") != "draft":
                raise ValidationError(_("Meetings must be created as drafts."))
            if vals.get("organizer_id", self.env.uid) != self.env.uid and not self.env.user.has_group(
                "community_meetings.group_meeting_manager"
            ):
                raise UserError(_("Only a meeting manager can create a meeting for another organizer."))
            if vals.get("series_id") and "meeting_kind_id" not in vals:
                series = self.env["community.meeting.series"].browse(vals["series_id"])
                if series:
                    vals["meeting_kind_id"] = series.meeting_kind_id.id
        meetings = super().create(vals_list)
        self.env["community.meeting.carryover"]._process_new_meetings(meetings)
        return meetings

    def _can_change_series(self):
        self.ensure_one()
        return (
            self.state in ("draft", "scheduled")
            and not self.actual_start_datetime
            and not self.approved_revision_id
        )

    def write(self, vals):
        if "series_id" in vals:
            self._lock_live_workflow()
            self.invalidate_recordset(["series_id", "approved_revision_id"])
            destination = self.env["community.meeting.series"].browse(vals["series_id"]).exists()
            if destination and "meeting_kind_id" not in vals:
                vals["meeting_kind_id"] = destination.meeting_kind_id.id
            for meeting in self:
                if destination and (
                    destination.company_id != meeting.company_id or not destination.active
                ):
                    raise ValidationError(
                        _("Choose an active series in the meeting's company.")
                    )
                if (
                    meeting.series_id.id != (destination.id if destination else False)
                    and not meeting._can_change_series()
                ):
                    raise UserError(
                        _("The series can only change before the meeting starts and before its minutes are approved.")
                    )
        if "state" in vals:
            raise UserError(_("Use a meeting workflow action to change its state."))
        if "code" in vals:
            raise UserError(_("A meeting reference cannot be changed."))
        if {"actual_start_datetime", "actual_paused_at", "actual_paused_seconds", "actual_end_datetime"}.intersection(vals):
            raise UserError(_("Actual meeting times are recorded through the meeting workflow."))
        if {"approved_revision_id", "revision_ids"}.intersection(vals):
            raise UserError(_("Use the approval workflow to manage meeting revisions."))
        if "company_id" in vals and any(meeting.company_id.id != vals["company_id"] for meeting in self):
            raise UserError(_("A meeting cannot be moved to another company."))
        protected_fields = {"organizer_id", "editor_user_ids", "reader_user_ids"}.intersection(vals)
        if protected_fields and not self.env.user.has_group("community_meetings.group_meeting_manager"):
            if any(meeting.organizer_id != self.env.user for meeting in self):
                raise UserError(_("Only the organizer or a meeting manager can change meeting access."))
        if any(meeting.state in ("approved", "cancelled") for meeting in self):
            raise UserError(_("Approved or cancelled meetings cannot be edited."))
        return super().write(vals)

    def _transition(self, allowed, target):
        for meeting in self:
            meeting.check_access_rights("write")
            meeting.check_access_rule("write")
            if meeting.state not in allowed:
                raise UserError(_("This workflow action is not allowed from the current state."))
            if not (
                self.env.user.has_group("community_meetings.group_meeting_editor")
                or self.env.user.has_group("community_meetings.group_meeting_manager")
            ):
                raise UserError(_("You are not allowed to change this meeting."))
        return super(CommunityMeeting, self).write({"state": target})

    def action_schedule(self):
        if any(not meeting.start_datetime for meeting in self):
            raise ValidationError(_("Set a meeting date and time before scheduling it."))
        result = self._transition(("draft",), "scheduled")
        self.env["community.meeting.carryover"]._process_new_meetings(self)
        return result

    def action_mark_held(self):
        result = self._transition(("scheduled",), "held")
        items = self.mapped("agenda_item_ids")
        items.filtered("actual_started_at")._pause_timing()
        unfinished = items.filtered(
            lambda item: item.has_started and item.disposition in ("open", "deferred")
        )
        if unfinished:
            unfinished.write({"review_next_meeting": True})
        now = fields.Datetime.now()
        for meeting in self:
            vals = {"actual_end_datetime": now}
            if meeting.actual_paused_at:
                vals["actual_paused_seconds"] = meeting.actual_paused_seconds + max(
                    0, int((now - meeting.actual_paused_at).total_seconds())
                )
                vals["actual_paused_at"] = False
            super(CommunityMeeting, meeting).write(vals)
        self._promote_followups()
        return result

    def _promote_followups(self):
        """At meeting close (held), promote open follow-ups whose origin point
        is closed into new persistent points, keeping traceability to both."""
        for meeting in self:
            actions = self.env["community.meeting.action"].search([
                ("meeting_id", "=", meeting.id),
                ("state", "not in", ("done", "cancelled")),
                ("topic_id.state", "=", "closed"),
            ])
            for action in actions:
                if self.env["community.meeting.topic"].search_count([
                    ("origin_action_id", "=", action.id),
                ]):
                    continue
                default_type = self.env["community.meeting.agenda.type"].search(
                    [("behavior", "=", "followup"), ("active", "=", True)], limit=1
                )
                self.env["community.meeting.topic"].create({
                    "name": action.name,
                    "agenda_type_id": default_type.id,
                    "origin_topic_id": action.topic_id.id,
                    "origin_action_id": action.id,
                    "company_id": meeting.company_id.id,
                    "series_id": meeting.series_id.id,
                })

    def get_pending_minutes_for_approval(self):
        """Previous meetings in the same series whose minutes are not approved."""
        self.ensure_one()
        if not self.series_id or not self.start_datetime:
            return []
        meetings = self.env["community.meeting"].search([
            ("series_id", "=", self.series_id.id),
            ("state", "in", ("held", "minutes_draft")),
            ("start_datetime", "<", self.start_datetime),
            ("id", "!=", self.id),
        ], order="start_datetime, id")
        return [
            {"id": m.id, "code": m.code, "name": m.name, "state": m.state}
            for m in meetings
        ]

    def _record_approved_previous_minutes(self):
        """Register this approval on the minutes-approval point of later meetings.

        The live "pending minutes" list is a query; without this the approval
        would leave no trace once the previous meeting leaves held/minutes_draft.
        """
        self.ensure_one()
        if not self.series_id or not self.start_datetime:
            return
        later = self.env["community.meeting"].sudo().search([
            ("series_id", "=", self.series_id.id),
            ("start_datetime", ">", self.start_datetime),
            ("state", "in", ("draft", "scheduled", "held", "minutes_draft")),
        ])
        points = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        approvals = self.env["community.meeting.minutes.approval"].sudo()
        for point in points:
            if not approvals.search_count([
                ("agenda_item_id", "=", point.id), ("meeting_id", "=", self.id),
            ]):
                approvals.create({"agenda_item_id": point.id, "meeting_id": self.id})

    def get_minutes_approval_history(self):
        """Previously approved minutes recorded on this meeting's approval points."""
        self.ensure_one()
        records = self.env["community.meeting.minutes.approval"].search([
            ("agenda_item_id.meeting_id", "=", self.id),
        ])
        return [
            {
                "id": record.id,
                "agenda_item_id": record.agenda_item_id.id,
                "meeting_id": record.meeting_id.id,
                "code": record.meeting_id.code,
                "name": record.meeting_id.name,
            }
            for record in records
        ]

    def action_start_meeting(self):
        for meeting in self:
            meeting.check_access_rights("write")
            meeting.check_access_rule("write")
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise AccessError(_("Only meeting editors can start a meeting."))
            self.env.cr.execute(
                "SELECT id FROM community_meeting WHERE id = %s FOR UPDATE", [meeting.id],
            )
            meeting.invalidate_recordset(["state", "actual_start_datetime", "actual_paused_at"])
            if meeting.state != "scheduled":
                raise UserError(_("Only a scheduled meeting can be started."))
            if not meeting.actual_start_datetime:
                super(CommunityMeeting, meeting).write({"actual_start_datetime": fields.Datetime.now()})
        return True

    def action_pause_meeting(self):
        for meeting in self:
            meeting.check_access_rights("write")
            meeting.check_access_rule("write")
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise AccessError(_("Only meeting editors can pause a meeting."))
            self.env.cr.execute("SELECT id FROM community_meeting WHERE id = %s FOR UPDATE", [meeting.id])
            meeting.invalidate_recordset(["state", "actual_start_datetime", "actual_end_datetime", "actual_paused_at"])
            if meeting.state != "scheduled" or not meeting.actual_start_datetime or meeting.actual_end_datetime:
                raise UserError(_("Only a running meeting can be paused."))
            if meeting.actual_paused_at:
                raise UserError(_("This meeting is already paused."))
            meeting.agenda_item_ids.filtered("actual_started_at")._pause_timing()
            super(CommunityMeeting, meeting).write({"actual_paused_at": fields.Datetime.now()})
        return True

    def action_resume_meeting(self):
        for meeting in self:
            meeting.check_access_rights("write")
            meeting.check_access_rule("write")
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise AccessError(_("Only meeting editors can resume a meeting."))
            self.env.cr.execute("SELECT id FROM community_meeting WHERE id = %s FOR UPDATE", [meeting.id])
            meeting.invalidate_recordset(["state", "actual_start_datetime", "actual_end_datetime", "actual_paused_at", "actual_paused_seconds"])
            if meeting.state != "scheduled" or not meeting.actual_paused_at or meeting.actual_end_datetime:
                raise UserError(_("Only a paused meeting can be resumed."))
            paused_seconds = meeting.actual_paused_seconds + max(
                0, int((fields.Datetime.now() - meeting.actual_paused_at).total_seconds())
            )
            super(CommunityMeeting, meeting).write({"actual_paused_at": False, "actual_paused_seconds": paused_seconds})
        return True

    def action_draft_minutes(self):
        return self._transition(("held",), "minutes_draft")

    def action_cancel(self):
        return self._transition(("draft", "scheduled"), "cancelled")

    def action_open_live_meeting(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        if self.state not in ("scheduled", "held", "minutes_draft", "approved"):
            raise UserError(_("The live meeting view is available for scheduled, ongoing or approved meetings."))
        return {"type": "ir.actions.client", "tag": "community_meetings.live_meeting",
                "name": _("Live Meeting"), "target": "main",
                "context": {"active_model": self._name, "active_id": self.id, "active_ids": self.ids},
                "params": {"meeting_id": self.id}}

    def get_live_capabilities(self):
        self.ensure_one()
        self.check_access("read")
        editorial = self.env.user.has_group("community_meetings.group_meeting_editor")
        return {
            "timezone": self.series_id.timezone or self.env.user.tz or "UTC",
            "can_edit": editorial and self.has_access("write") and self.state not in ("approved", "cancelled"),
            "can_view_editorial": editorial and self.has_access("write"),
            "can_approve": self.env.user.has_group("community_meetings.group_meeting_approver"),
        }

    def get_live_published_dissents(self):
        """Read only the publishable projection after checking meeting visibility."""
        self.ensure_one()
        self.check_access("read")
        records = self.env["community.meeting.dissent"].sudo().search(
            [("meeting_id", "=", self.id), ("include_in_minutes", "=", True)],
            order="sequence, id",
        )
        return [{"id": record.id, "agenda_item_id": [record.agenda_item_id.id, record.agenda_item_id.name] if record.agenda_item_id else False,
                 "resolution_id": [record.resolution_id.id, record.resolution_id.title] if record.resolution_id else False,
                 "body": record.body, "kind": record.reason_id.name or "",
                 "author_display_name": record.author_display_name or record.author_partner_id.name or ""} for record in records]

    def unlink(self):
        if any(meeting.state not in ("draft", "cancelled") for meeting in self):
            raise UserError(_("Only draft or cancelled meetings can be deleted."))
        return super().unlink()

    def copy(self, default=None):
        self.ensure_one()
        values = dict(default or {})
        values.update({
            "code": "New",
            "state": "draft",
            "approved_revision_id": False,
            "revision_ids": [],
            "name": values.get("name") or _("Copy of %(name)s", name=self.name),
            "agenda_item_ids": [(0, 0, {
                "name": item.name,
                "sequence": item.sequence,
                "agenda_type_id": item.agenda_type_id.id,
                "kind": item.kind,
                "description": item.description,
                "presenter_partner_id": item.presenter_partner_id.id,
            }) for item in self.agenda_item_ids],
            "resolution_ids": [],
            "action_ids": [],
            "private_note_ids": [],
            "dissent_ids": [],
            "carryover_ids": [],
        })
        return super().copy(values)

    def action_approve_minutes(self):
        revisions = self.env["community.meeting.revision"]
        for meeting in self:
            if not self.env.user.has_group("community_meetings.group_meeting_approver"):
                raise AccessError(_("Only an authorized meeting approver can approve minutes."))
            meeting.check_access_rights("read")
            meeting.check_access_rule("read")
            if meeting.state != "minutes_draft":
                raise UserError(_("Only draft minutes can be approved."))
            if not meeting.agenda_item_ids:
                raise ValidationError(_("Add at least one agenda item before approving the minutes."))
            meeting._validate_before_approval()
            revision = self.env["community.meeting.revision"]._create_approved_revision(meeting)
            meeting._set_approved_revision(revision)
            meeting._record_approved_previous_minutes()
            revisions |= revision
        return revisions

    def action_start_amendment(self):
        if not self.env.user.has_group("community_meetings.group_meeting_manager"):
            raise AccessError(_("Only a meeting manager can start an amendment."))
        for meeting in self:
            meeting.check_access_rights("write")
            meeting.check_access_rule("write")
            if meeting.state != "approved":
                raise UserError(_("Only approved minutes can be amended."))
        return super(CommunityMeeting, self).write({"state": "minutes_draft"})

    def _set_approved_revision(self, revision):
        # Approvers have read-only meeting access, so the approved state and
        # revision link are written with sudo. Keep the payload to exactly
        # these two fields; pinned by the approver approval test.
        self.ensure_one()
        return super(CommunityMeeting, self.sudo()).write({
            "state": "approved", "approved_revision_id": revision.id,
        })
