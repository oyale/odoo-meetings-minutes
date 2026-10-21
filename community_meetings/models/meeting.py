from typing import ClassVar

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class CommunityMeeting(models.Model):
    _name = "community.meeting"
    _description = "Community Meeting"
    _inherit: ClassVar[list[str]] = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, readonly=True, copy=False, default="New", tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    organizer_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        check_company=True,
        tracking=True,
    )
    secretary_id = fields.Many2one(
        "res.users",
        string="Minutes secretary",
        check_company=True,
        tracking=True,
        default=lambda self: self.env.user,
    )
    editor_user_ids = fields.Many2many(
        "res.users",
        "community_meeting_editor_rel",
        "meeting_id",
        "user_id",
        string="Editors",
        check_company=True,
    )
    reader_user_ids = fields.Many2many(
        "res.users",
        "community_meeting_reader_rel",
        "meeting_id",
        "user_id",
        string="Readers",
        check_company=True,
    )
    attendee_partner_ids = fields.Many2many("res.partner", string="Attendees")
    start_datetime = fields.Datetime(string="Estimated Start Datetime", tracking=True)
    end_datetime = fields.Datetime(string="Estimated End Datetime", tracking=True)
    actual_start_datetime = fields.Datetime(readonly=True, copy=False, tracking=True)
    actual_paused_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    actual_paused_seconds = fields.Integer(readonly=True, copy=False, default=0)
    actual_end_datetime = fields.Datetime(readonly=True, copy=False, tracking=True)
    actual_duration_minutes = fields.Integer(
        string="Actual duration (minutes)",
        compute="_compute_actual_duration_minutes",
        store=True,
    )
    location = fields.Char()
    meeting_url = fields.Char()
    description = fields.Html()
    minutes_notes = fields.Html()
    meeting_kind_id = fields.Many2one(
        "community.meeting.kind",
        string="Kind",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.ref("community_meetings.kind_operational", raise_if_not_found=False),
    )
    series_id = fields.Many2one(
        "community.meeting.series",
        check_company=True,
        ondelete="restrict",
    )
    requires_later_minutes_approval = fields.Boolean(
        related="series_id.has_minutes_approval_point",
        string="Requires approval from a later meeting",
        readonly=True,
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
        ],
        default="draft",
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )
    time_tracking_enabled = fields.Boolean(
        string="Time tracking",
        compute="_compute_time_tracking_enabled",
        help=("Series override of the company setting; standalone meetings follow the company."),
    )
    add_point_policy = fields.Selection(
        [
            ("draft", "Draft only"),
            ("scheduled", "Before it starts"),
            ("ongoing", "While it runs"),
        ],
        string="Add points until",
        compute="_compute_add_point_policy",
        help=("Series override of the company setting; standalone meetings follow the company."),
    )
    add_point_allowed = fields.Boolean(
        string="Can add points",
        compute="_compute_add_point_allowed",
        help=("Whether new points can still be added to this meeting under the current policy."),
    )
    agenda_item_ids = fields.One2many("community.meeting.agenda.item", "meeting_id")
    # ponytail: display-only "In Progress" derived from scheduled + actual_start;
    # upgrade path: real 'in_progress' state if workflows/filters need to target it.
    display_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("held", "Held"),
            ("minutes_draft", "Minutes Draft"),
            ("approved", "Approved"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        compute="_compute_display_state",
    )
    resolution_ids = fields.One2many("community.meeting.resolution", "meeting_id")
    action_ids = fields.One2many("community.meeting.action", "meeting_id")
    incoming_carryover_ids = fields.One2many(
        "community.meeting.carryover",
        "destination_meeting_id",
        groups="community_meetings.group_meeting_editor",
    )
    private_note_ids = fields.One2many(
        "community.meeting.editor.note",
        "meeting_id",
        groups="community_meetings.group_meeting_editor",
    )
    dissent_ids = fields.One2many(
        "community.meeting.dissent",
        "meeting_id",
        groups="community_meetings.group_meeting_editor",
    )
    carryover_ids = fields.One2many(
        "community.meeting.carryover",
        "origin_meeting_id",
        groups="community_meetings.group_meeting_editor",
    )
    revision_ids = fields.One2many("community.meeting.revision", "meeting_id", copy=False)
    approved_revision_id = fields.Many2one(
        "community.meeting.revision",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    _sql_constraints: ClassVar[list[tuple[str, str, str]]] = [
        (
            "code_company_unique",
            "unique(company_id, code)",
            "Meeting references must be unique per company.",
        ),
    ]

    @api.depends("series_id.time_tracking", "company_id.meeting_time_tracking")
    def _compute_time_tracking_enabled(self):
        for meeting in self:
            series_mode = meeting.series_id.time_tracking or "inherit"
            meeting.time_tracking_enabled = (
                meeting.company_id.meeting_time_tracking if series_mode == "inherit" else series_mode == "on"
            )

    @api.depends("series_id.add_point_policy", "company_id.meeting_add_point_policy")
    def _compute_add_point_policy(self):
        for meeting in self:
            series_mode = meeting.series_id.add_point_policy or "inherit"
            meeting.add_point_policy = (
                meeting.company_id.meeting_add_point_policy if series_mode == "inherit" else series_mode
            )

    @api.depends("state", "actual_start_datetime", "add_point_policy")
    def _compute_add_point_allowed(self):
        for meeting in self:
            if meeting.state in ("held", "minutes_draft", "approved", "cancelled"):
                meeting.add_point_allowed = False
            elif meeting.state == "draft":
                meeting.add_point_allowed = True
            elif meeting.add_point_policy == "draft":
                meeting.add_point_allowed = False
            else:  # scheduled or ongoing
                meeting.add_point_allowed = meeting.add_point_policy == "ongoing" or not meeting.actual_start_datetime

    @api.depends("state", "actual_start_datetime")
    def _compute_display_state(self):
        for meeting in self:
            meeting.display_state = (
                "in_progress" if meeting.state == "scheduled" and meeting.actual_start_datetime else meeting.state
            )

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
        return {
            "meeting_id": self.id,
            "recipient_partner_ids": self.attendee_partner_ids.ids,
        }

    @api.model
    def _resolve_invitees(self, manual_partner_ids=None):
        """Resolve explicitly supplied contacts; extensions may add sources."""
        return self.env["res.partner"].browse(manual_partner_ids or []).exists()

    def _validate_before_approval(self):
        """Extension hook for approval checks. Core operational rules run separately."""
        return True

    def _lock_live_workflow(self):
        # A row update also serializes repeatable-read snapshots, so concurrent
        # live writes are retried by Odoo instead of validating stale state.
        for meeting in self.sorted("id"):
            self.env.cr.execute(
                "UPDATE community_meeting SET write_date=clock_timestamp() WHERE id=%s",
                [meeting.id],
            )
        self.invalidate_recordset(
            [
                "state",
                "actual_start_datetime",
                "actual_paused_at",
                "actual_end_datetime",
            ]
        )

    @api.model_create_multi
    # Generate protected references and materialize carryovers in one transaction.
    def create(self, vals_list):  # noqa: C901
        if not self.env.user.has_group("community_meetings.group_meeting_editor"):
            raise AccessError(_("You are not allowed to create meetings."))
        for vals in vals_list:
            if vals.get("code") not in (None, False, "New"):
                raise ValidationError(_("Meeting references are assigned by the system."))
            if vals.get("approved_revision_id") or vals.get("revision_ids"):
                raise ValidationError(_("Approved revisions cannot be assigned during meeting creation."))
            if vals.get("code", "New") == "New":
                # Editors may create meetings without gaining general sequence
                # access.
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
            self.state in ("draft", "scheduled") and not self.actual_start_datetime and not self.approved_revision_id
        )

    # Preserve the ordering of series, workflow, timing, and permission guards.
    def write(self, vals):  # noqa: C901
        if "series_id" in vals:
            self._lock_live_workflow()
            self.invalidate_recordset(["series_id", "approved_revision_id"])
            destination = self.env["community.meeting.series"].browse(vals["series_id"]).exists()
            if destination and "meeting_kind_id" not in vals:
                vals["meeting_kind_id"] = destination.meeting_kind_id.id
            for meeting in self:
                if destination and (destination.company_id != meeting.company_id or not destination.active):
                    raise ValidationError(_("Choose an active series in the meeting's company."))
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
        if {
            "actual_start_datetime",
            "actual_paused_at",
            "actual_paused_seconds",
            "actual_end_datetime",
        }.intersection(vals):
            raise UserError(_("Actual meeting times are recorded through the meeting workflow."))
        if {"approved_revision_id", "revision_ids"}.intersection(vals):
            raise UserError(_("Use the approval workflow to manage meeting revisions."))
        if "company_id" in vals and any(meeting.company_id.id != vals["company_id"] for meeting in self):
            raise UserError(_("A meeting cannot be moved to another company."))
        protected_fields = {
            "organizer_id",
            "editor_user_ids",
            "reader_user_ids",
        }.intersection(vals)
        if (
            protected_fields
            and not self.env.user.has_group("community_meetings.group_meeting_manager")
            and any(meeting.organizer_id != self.env.user for meeting in self)
        ):
            raise UserError(_("Only the organizer or a meeting manager can change meeting access."))
        if any(meeting.state in ("approved", "cancelled") for meeting in self):
            raise UserError(_("Approved or cancelled meetings cannot be edited."))
        result = super().write(vals)
        if vals.get("series_id"):
            self._ensure_minutes_approval_point()
        return result

    def _transition(self, allowed, target):
        for meeting in self:
            meeting.check_access("write")
            if meeting.state not in allowed:
                raise UserError(_("This workflow action is not allowed from the current state."))
            if not (
                self.env.user.has_group("community_meetings.group_meeting_editor")
                or self.env.user.has_group("community_meetings.group_meeting_manager")
            ):
                raise UserError(_("You are not allowed to change this meeting."))
        return super().write({"state": target})

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
        unfinished = items.filtered(lambda item: item.has_started and item.disposition in ("open", "deferred"))
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
        if not self:
            return True
        actions = self.env["community.meeting.action"].search(
            [
                ("meeting_id", "in", self.ids),
                ("state", "not in", ("done", "cancelled")),
                ("topic_id.state", "=", "closed"),
            ]
        )
        if not actions:
            return True
        actions_by_meeting = {}
        for action in actions:
            actions_by_meeting.setdefault(action.meeting_id.id, self.env["community.meeting.action"])
            actions_by_meeting[action.meeting_id.id] |= action
        existing_action_ids = set(
            self.env["community.meeting.topic"]
            .search([("origin_action_id", "in", actions.ids)])
            .mapped("origin_action_id")
            .ids
        )
        pending = actions.filtered(lambda action: action.id not in existing_action_ids)
        if not pending:
            return True
        default_type = self.env["community.meeting.agenda.type"].search(
            [("behavior", "=", "followup"), ("active", "=", True)], limit=1
        )
        values_list = []
        for meeting in self:
            for action in actions_by_meeting.get(meeting.id, self.env["community.meeting.action"]):
                if action.id not in existing_action_ids:
                    responsible = action.responsible_user_id.partner_id
                    values_list.append(
                        {
                            "name": action.name,
                            "agenda_type_id": default_type.id,
                            "origin_topic_id": action.topic_id.id,
                            "origin_action_id": action.id,
                            "company_id": meeting.company_id.id,
                            "series_id": meeting.series_id.id,
                            "presenter_partner_id": (responsible.id if responsible else self.env.user.partner_id.id),
                        }
                    )
        self.env["community.meeting.topic"].create(values_list)
        return True

    def get_pending_minutes_for_approval(self):
        """Previous meetings in the same series whose minutes are not approved."""
        self.ensure_one()
        if not self.series_id or not self.start_datetime:
            return []
        meetings = self.env["community.meeting"].search(
            [
                ("series_id", "=", self.series_id.id),
                ("state", "in", ("held", "minutes_draft")),
                ("start_datetime", "<", self.start_datetime),
                ("id", "!=", self.id),
            ],
            order="start_datetime, id",
        )
        return [
            {
                "id": m.id,
                "code": m.code,
                "name": m.name,
                "state": m.state,
                "start_datetime": m.start_datetime,
                "location": m.location,
            }
            for m in meetings
        ]

    def _record_approved_previous_minutes(self, revision):
        """Register this approval on the minutes-approval point of later meetings.

        The live "pending minutes" list is a query; without this the approval
        would leave no trace once the previous meeting leaves held/minutes_draft.
        """
        self.ensure_one()
        if not self.series_id or not self.start_datetime:
            return
        later = (
            self.env["community.meeting"]
            .sudo()
            .search(
                [
                    ("series_id", "=", self.series_id.id),
                    ("start_datetime", ">", self.start_datetime),
                    ("state", "in", ("draft", "scheduled", "held", "minutes_draft")),
                ]
            )
        )
        points = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        approvals = self.env["community.meeting.minutes.approval"].sudo()
        for point in points:
            if not approvals.search_count(
                [
                    ("agenda_item_id", "=", point.id),
                    ("meeting_id", "=", self.id),
                    ("revision_id", "=", revision.id),
                ]
            ):
                approvals.create(
                    {"agenda_item_id": point.id, "meeting_id": self.id, "revision_id": revision.id}
                )

    def get_minutes_approval_history(self):
        """Previously approved minutes recorded on this meeting's approval points."""
        self.ensure_one()
        records = self.env["community.meeting.minutes.approval"].search(
            [
                ("agenda_item_id.meeting_id", "=", self.id),
            ]
        )
        return [
            {
                "id": record.id,
                "agenda_item_id": record.agenda_item_id.id,
                "meeting_id": record.meeting_id.id,
                "revision_id": record.revision_id.id,
                "revision_number": record.revision_id.revision_number if record.revision_id else False,
                "code": record.meeting_id.code,
                "name": record.meeting_id.name,
                "start_datetime": record.meeting_id.start_datetime,
                "location": record.meeting_id.location,
            }
            for record in records
        ]

    def action_start_meeting(self):
        for meeting in self:
            meeting.check_access("write")
            if not meeting.time_tracking_enabled:
                raise UserError(_("Time tracking is disabled for this meeting."))
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise AccessError(_("Only meeting editors can start a meeting."))
            self.env.cr.execute(
                "SELECT id FROM community_meeting WHERE id = %s FOR UPDATE",
                [meeting.id],
            )
            meeting.invalidate_recordset(["state", "actual_start_datetime", "actual_paused_at"])
            if meeting.state != "scheduled":
                raise UserError(_("Only a scheduled meeting can be started."))
            if not meeting.actual_start_datetime:
                super(CommunityMeeting, meeting).write({"actual_start_datetime": fields.Datetime.now()})
        return True

    def action_pause_meeting(self):
        for meeting in self:
            meeting.check_access("write")
            if not meeting.time_tracking_enabled:
                raise UserError(_("Time tracking is disabled for this meeting."))
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise AccessError(_("Only meeting editors can pause a meeting."))
            self.env.cr.execute(
                "SELECT id FROM community_meeting WHERE id = %s FOR UPDATE",
                [meeting.id],
            )
            meeting.invalidate_recordset(
                [
                    "state",
                    "actual_start_datetime",
                    "actual_end_datetime",
                    "actual_paused_at",
                ]
            )
            if meeting.state != "scheduled" or not meeting.actual_start_datetime or meeting.actual_end_datetime:
                raise UserError(_("Only a running meeting can be paused."))
            if meeting.actual_paused_at:
                raise UserError(_("This meeting is already paused."))
            meeting.agenda_item_ids.filtered("actual_started_at")._pause_timing()
            super(CommunityMeeting, meeting).write({"actual_paused_at": fields.Datetime.now()})
        return True

    def action_resume_meeting(self):
        for meeting in self:
            meeting.check_access("write")
            if not meeting.time_tracking_enabled:
                raise UserError(_("Time tracking is disabled for this meeting."))
            if not self.env.user.has_group("community_meetings.group_meeting_editor"):
                raise AccessError(_("Only meeting editors can resume a meeting."))
            self.env.cr.execute(
                "SELECT id FROM community_meeting WHERE id = %s FOR UPDATE",
                [meeting.id],
            )
            meeting.invalidate_recordset(
                [
                    "state",
                    "actual_start_datetime",
                    "actual_end_datetime",
                    "actual_paused_at",
                    "actual_paused_seconds",
                ]
            )
            if meeting.state != "scheduled" or not meeting.actual_paused_at or meeting.actual_end_datetime:
                raise UserError(_("Only a paused meeting can be resumed."))
            paused_seconds = meeting.actual_paused_seconds + max(
                0,
                int((fields.Datetime.now() - meeting.actual_paused_at).total_seconds()),
            )
            super(CommunityMeeting, meeting).write(
                {"actual_paused_at": False, "actual_paused_seconds": paused_seconds}
            )
        return True

    def action_draft_minutes(self):
        return self._transition(("held",), "minutes_draft")

    def action_cancel(self):
        return self._transition(("draft", "scheduled"), "cancelled")

    def action_open_live_meeting(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.client",
            "tag": "community_meetings.live_meeting",
            "name": _("Meeting"),
            "target": "main",
            "context": {
                "active_model": self._name,
                "active_id": self.id,
                "active_ids": self.ids,
            },
            "params": {"meeting_id": self.id},
        }

    def _check_minutes_preview_access(self):
        self.ensure_one()
        self.check_access("read")
        if not (
            self.env.user.has_group("community_meetings.group_meeting_editor")
            or self.env.user.has_group("community_meetings.group_meeting_approver")
        ):
            raise AccessError(_("Only meeting editors and approvers can preview draft minutes."))
        if self.state not in ("held", "minutes_draft"):
            raise UserError(_("Minutes preview is only available for held meetings or draft minutes."))

    def action_preview_minutes(self):
        self.ensure_one()
        self._check_minutes_preview_access()
        return {
            "type": "ir.actions.client",
            "tag": "community_meetings.minutes_preview",
            "name": _("Draft Minutes Preview"),
            "target": "current",
            "params": {"meeting_id": self.id},
        }

    def get_minutes_preview_html(self):
        self.ensure_one()
        self._check_minutes_preview_access()
        return str(self.env["report.community_meetings.report_revision_document"]._render_preview(self))

    def get_live_capabilities(self):
        self.ensure_one()
        self.check_access("read")
        editorial = self.env.user.has_group("community_meetings.group_meeting_editor")
        minutes_reviewer = editorial or self.env.user.has_group("community_meetings.group_meeting_approver")
        return {
            "timezone": self.series_id.timezone or self.env.user.tz or "UTC",
            "can_edit": editorial and self.has_access("write") and self.state not in ("approved", "cancelled"),
            "can_view_editorial": editorial and self.has_access("write"),
            "can_approve": self.env.user.has_group("community_meetings.group_meeting_approver"),
            "can_approve_previous_minutes": bool(
                self.series_id.has_minutes_approval_point
                and (
                    (
                        editorial
                        and self.secretary_id == self.env.user
                        and self.has_access("write")
                        and self.state == "scheduled"
                        and self.actual_start_datetime
                        and not self.actual_end_datetime
                    )
                    or (
                        self.secretary_id == self.env.user
                        and self.state == "minutes_draft"
                        and not self.actual_start_datetime
                    )
                )
            ),
            "requires_later_minutes_approval": bool(self.series_id.has_minutes_approval_point),
            "can_preview_minutes": minutes_reviewer,
            "time_tracking": self.time_tracking_enabled,
            "can_add_point": self.add_point_allowed,
        }

    def get_live_published_dissents(self):
        """Read only the publishable projection after checking meeting visibility."""
        self.ensure_one()
        self.check_access("read")
        records = (
            self.env["community.meeting.dissent"]
            .sudo()
            .search(
                [("meeting_id", "=", self.id), ("include_in_minutes", "=", True)],
                order="sequence, id",
            )
        )
        return [
            {
                "id": record.id,
                "agenda_item_id": [record.agenda_item_id.id, record.agenda_item_id.name]
                if record.agenda_item_id
                else False,
                "resolution_id": [record.resolution_id.id, record.resolution_id.title]
                if record.resolution_id
                else False,
                "body": record.body,
                "kind": record.reason_id.name or "",
                "author_display_name": record.author_display_name or record.author_partner_id.name or "",
            }
            for record in records
        ]

    def unlink(self):
        if any(meeting.state not in ("draft", "cancelled") for meeting in self):
            raise UserError(_("Only draft or cancelled meetings can be deleted."))
        return super().unlink()

    def copy(self, default=None):
        self.ensure_one()
        values = dict(default or {})
        values.update(
            {
                "code": "New",
                "state": "draft",
                "approved_revision_id": False,
                "revision_ids": [],
                "name": values.get("name") or _("Copy of %(name)s", name=self.name),
                "agenda_item_ids": [
                    (
                        0,
                        0,
                        {
                            "name": item.name,
                            "sequence": item.sequence,
                            "agenda_type_id": item.agenda_type_id.id,
                            "kind": item.kind,
                            "description": item.description,
                            "presenter_partner_id": item.presenter_partner_id.id,
                        },
                    )
                    for item in self.agenda_item_ids
                ],
                "resolution_ids": [],
                "action_ids": [],
                "private_note_ids": [],
                "dissent_ids": [],
                "carryover_ids": [],
            }
        )
        return super().copy(values)

    def action_approve_minutes(self):
        if not self.env.user.has_group("community_meetings.group_meeting_approver"):
            raise AccessError(_("Only an authorized meeting approver can approve minutes."))
        if any(meeting.series_id.has_minutes_approval_point for meeting in self):
            raise UserError(_("Approve these minutes from a later meeting's minutes approval point."))
        return self._approve_minutes()

    def _check_previous_minutes_approval_route(self, live, offline):
        if live:
            # Approval authority follows the secretary assigned to this
            # meeting; editor access alone must not grant it.
            self.check_access("write")
            if (
                not self.env.user.has_group("community_meetings.group_meeting_editor")
                or self.secretary_id != self.env.user
            ):
                raise AccessError(
                    _("Only the assigned minutes secretary can approve previous minutes during a live meeting.")
                )
        elif offline:
            if self.secretary_id != self.env.user:
                raise AccessError(
                    _(
                        "Only the assigned minutes secretary can approve previous minutes while preparing "
                        "offline minutes."
                    )
                )
        else:
            raise UserError(
                _("Previous minutes can only be approved during a live meeting or while preparing offline minutes.")
            )

    def action_approve_pending_minutes(self, agenda_item_id, meeting_ids):
        """Approve selected earlier minutes from this meeting's approval point."""
        self.ensure_one()
        self.check_access("read")
        if not self.series_id.has_minutes_approval_point:
            raise UserError(_("This series does not require approval from a later meeting."))
        live = self.state == "scheduled" and bool(self.actual_start_datetime) and not self.actual_end_datetime
        offline = self.state == "minutes_draft" and not self.actual_start_datetime
        self._check_previous_minutes_approval_route(live, offline)
        point = self.agenda_item_ids.filtered(
            lambda item: item.id == agenda_item_id and item.kind == "minutes_approval"
        )
        if not point:
            raise UserError(_("Choose a minutes approval point from this meeting."))
        pending_ids = {row["id"] for row in self.get_pending_minutes_for_approval()}
        selected_ids = set(meeting_ids or [])
        if not selected_ids or not selected_ids.issubset(pending_ids):
            raise UserError(_("Select pending minutes from an earlier meeting in this series."))
        revisions = self.env["community.meeting.revision"]
        for meeting in self.env["community.meeting"].browse(sorted(selected_ids)).exists():
            if meeting.series_id != self.series_id or not meeting.start_datetime or meeting.start_datetime >= self.start_datetime:
                raise UserError(_("Only earlier meetings in this series can be approved here."))
            revisions |= meeting._approve_minutes(approval_point=point, offline=offline)
        if offline and not self.get_pending_minutes_for_approval():
            point.sudo().write({"disposition": "closed"})
        return revisions

    def _approve_minutes(self, approval_point=None, offline=False):
        revisions = self.env["community.meeting.revision"]
        for meeting in self:
            if approval_point:
                if offline:
                    if approval_point.meeting_id.secretary_id != self.env.user:
                        raise AccessError(_("Only the assigned minutes secretary can approve minutes offline."))
                    point_meeting = approval_point.meeting_id
                    if point_meeting.state != "minutes_draft" or point_meeting.actual_start_datetime:
                        raise UserError(_("Previous minutes can only be approved while preparing offline minutes."))
                elif (
                    not self.env.user.has_group("community_meetings.group_meeting_editor")
                    or approval_point.meeting_id.secretary_id != self.env.user
                ):
                    raise AccessError(
                        _("Only the assigned minutes secretary can approve previous minutes from a live meeting.")
                    )
                if not meeting.series_id.has_minutes_approval_point:
                    raise UserError(_("This series does not require approval from a later meeting."))
            elif not self.env.user.has_group("community_meetings.group_meeting_approver"):
                raise AccessError(_("Only an authorized meeting approver can approve minutes."))
            meeting.check_access("read")
            if meeting.state != "minutes_draft":
                raise UserError(_("Only draft minutes can be approved."))
            if meeting.series_id.has_minutes_approval_point and not approval_point:
                raise UserError(_("Approve these minutes from a later meeting's minutes approval point."))
            if approval_point and (
                approval_point.kind != "minutes_approval"
                or approval_point.meeting_id.series_id != meeting.series_id
                or not approval_point.meeting_id.start_datetime
                or approval_point.meeting_id.start_datetime <= meeting.start_datetime
            ):
                raise UserError(_("The minutes approval point must belong to a later meeting in this series."))
            if not meeting.agenda_item_ids:
                raise ValidationError(_("Add at least one agenda item before approving the minutes."))
            meeting._validate_before_approval()
            revision = self.env["community.meeting.revision"]._create_approved_revision(
                meeting, approval_point=approval_point, offline=offline
            )
            meeting._set_approved_revision(revision)
            if approval_point:
                self.env["community.meeting.minutes.approval"].sudo().create(
                    {"agenda_item_id": approval_point.id, "meeting_id": meeting.id, "revision_id": revision.id}
                )
            meeting._record_approved_previous_minutes(revision)
            revisions |= revision
        return revisions

    def action_start_amendment(self):
        if not self.env.user.has_group("community_meetings.group_meeting_manager"):
            raise AccessError(_("Only a meeting manager can start an amendment."))
        for meeting in self:
            meeting.check_access("write")
            if meeting.state != "approved":
                raise UserError(_("Only approved minutes can be amended."))
        return super().write({"state": "minutes_draft"})

    def _set_approved_revision(self, revision):
        # Approvers have read-only meeting access, so the approved state and
        # revision link are written with sudo. Keep the payload to exactly
        # these two fields; pinned by the approver approval test.
        self.ensure_one()
        return super(CommunityMeeting, self.sudo()).write(
            {
                "state": "approved",
                "approved_revision_id": revision.id,
            }
        )
