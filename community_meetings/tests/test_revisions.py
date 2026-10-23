import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMeetingRevisions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Minutes Editor",
                "login": "minutes-editor-revision-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_editor").id,
                        ],
                    )
                ],
            }
        )
        cls.approver = cls.env["res.users"].create(
            {
                "name": "Minutes Approver",
                "login": "minutes-approver-revision-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_approver").id,
                        ],
                    )
                ],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Minutes Manager",
                "login": "minutes-manager-revision-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_manager").id,
                        ],
                    )
                ],
            }
        )

    def _approved_meeting(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Revision stability test",
                    "start_datetime": "2026-11-01 10:00:00",
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        review = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Review open actions",
                    "discussion_notes": "<p>Initial discussion</p>",
                }
            )
        )
        decision = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Approve the budget",
                    "kind": "decision",
                    "sequence": 20,
                }
            )
        )
        self.env["community.meeting.resolution"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": decision.id,
                "title": "Budget approved",
                "decision_outcome": "approved",
            }
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": review.id,
                    "name": "Prepare follow-up",
                }
            )
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        meeting.with_user(self.editor).action_draft_minutes()
        approved = meeting.with_user(self.approver)
        revision = self._approve_without_rendering_pdf(approved)
        return meeting, action, revision

    def _drafted_meeting(self, name, series=None, start_datetime="2026-11-01 10:00:00"):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": name,
                    "series_id": series.id if series else False,
                    "start_datetime": start_datetime,
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        self.env["community.meeting.agenda.item"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "name": "Review open actions",
                "discussion_notes": "<p>Initial discussion</p>",
            }
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        meeting.with_user(self.editor).action_draft_minutes()
        return meeting

    def _approve_without_rendering_pdf(self, meeting):
        report_model = self.env["ir.actions.report"]
        pdf_fixture = b"%PDF-1.4\n% wkhtmltopdf is smoke-tested separately in CI.\n"
        with patch.object(type(report_model), "_render_qweb_pdf", return_value=(pdf_fixture, "pdf")):
            return meeting.action_approve_minutes()

    def test_approve_minutes_recordset_approves_all(self):
        first = self._drafted_meeting("First recordset approval")
        second = self._drafted_meeting("Second recordset approval")
        revisions = self._approve_without_rendering_pdf((first | second).with_user(self.approver))
        # F1: the loop must not return early; both meetings get approved.
        self.assertEqual(len(revisions), 2)
        self.assertEqual(first.state, "approved")
        self.assertEqual(second.state, "approved")

    def test_later_approval_point_records_exact_amendment_revision(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "Minutes approval policy", "has_minutes_approval_point": True})
        )
        earlier = self._drafted_meeting("Earlier minutes in policy series", series=series)
        later = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Later meeting with approval point",
                    "series_id": series.id,
                    "start_datetime": "2026-11-10 10:00:00",
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        point = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        self.assertTrue(point)
        with self.assertRaises(UserError), self.cr.savepoint():
            self._approve_without_rendering_pdf(earlier.with_user(self.approver))

        later.with_user(self.editor).action_schedule()
        with self.assertRaises(UserError), self.cr.savepoint():
            later.with_user(self.editor).action_approve_pending_minutes(point.id, [earlier.id])
        with self.assertRaises(UserError), self.cr.savepoint():
            later.with_user(self.approver).action_approve_pending_minutes(point.id, [earlier.id])
        later.with_user(self.editor).action_start_meeting()
        with patch.object(type(self.env["ir.actions.report"]), "_render_qweb_pdf", return_value=(b"%PDF-1.4", "pdf")):
            later.with_user(self.editor).action_approve_pending_minutes(point.id, [earlier.id])
        first_revision = earlier.approved_revision_id
        record = point.minutes_approval_ids.filtered(lambda row: row.meeting_id == earlier)
        snapshot = json.loads(first_revision.snapshot_json)
        self.assertEqual(snapshot["approval"]["meeting_code"], later.code)
        self.assertEqual(snapshot["approval"]["point_name"], point.name)
        self.assertFalse(snapshot["approval"]["manual"])
        self.assertEqual(snapshot["approval"]["origin"], "meeting")
        self.assertFalse(snapshot["approval"]["offline"])
        legacy = json.loads(first_revision.snapshot_json)
        for key in ("origin", "meeting_code", "meeting_name", "point_name", "offline"):
            legacy["approval"].pop(key, None)
        report_model = self.env["report.community_meetings.report_revision_document"]
        doc = report_model._prepare_document(legacy, revision=first_revision)
        self.assertEqual(doc["snapshot"]["approval"]["meeting_code"], later.code)
        self.assertEqual(doc["snapshot"]["approval"]["origin"], "meeting")
        self.assertEqual(record.revision_id, first_revision)
        later_snapshot = self.env["community.meeting.revision"]._build_public_content(later)
        approval_item = next(row for row in later_snapshot["agenda"] if row["kind"] == "minutes_approval")
        self.assertEqual(approval_item["minutes_approvals"][0]["meeting_code"], earlier.code)
        self.assertEqual(
            approval_item["minutes_approvals"][0]["revision_number"],
            first_revision.revision_number,
        )
        preview_html = report_model._render_preview(later)
        self.assertIn("Approved previous minutes", preview_html)
        self.assertIn(earlier.code, preview_html)

        earlier.with_user(self.manager).action_start_amendment()
        earlier.agenda_item_ids[0].with_user(self.manager).write({"discussion_notes": "Amended discussion"})
        with patch.object(type(self.env["ir.actions.report"]), "_render_qweb_pdf", return_value=(b"%PDF-1.4", "pdf")):
            later.with_user(self.editor).action_approve_pending_minutes(point.id, [earlier.id])
        history = point.minutes_approval_ids.filtered(lambda row: row.meeting_id == earlier).sorted("id")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1].revision_id, earlier.approved_revision_id)
        self.assertNotEqual(history[0].revision_id, history[1].revision_id)

    def test_legacy_approval_record_does_not_guess_its_revision(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "Legacy approval history without revision"})
        )
        earlier = self._drafted_meeting("Legacy approved minutes", series=series)
        self._approve_without_rendering_pdf(earlier.with_user(self.approver))
        later = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Later meeting with legacy approval history",
                    "series_id": series.id,
                    "start_datetime": "2026-11-15 10:00:00",
                }
            )
        )
        approval_point = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        if not approval_point:
            approval_type = self.env["community.meeting.agenda.type"].search(
                [("behavior", "=", "minutes_approval")], limit=1
            )
            approval_point = (
                self.env["community.meeting.agenda.item"]
                .with_user(self.editor)
                .create(
                    {
                        "meeting_id": later.id,
                        "name": "Approve previous minutes",
                        "agenda_type_id": approval_type.id,
                    }
                )
            )

        legacy_approval = self.env["community.meeting.minutes.approval"].create(
            {
                "agenda_item_id": approval_point.id,
                "meeting_id": earlier.id,
            }
        )
        history = later.get_minutes_approval_history()

        self.assertTrue(earlier.approved_revision_id)
        self.assertFalse(legacy_approval.revision_id)
        self.assertEqual(len(history), 1)
        self.assertFalse(history[0]["revision_id"])
        self.assertFalse(history[0]["revision_number"])

    def test_assigned_secretary_approves_previous_minutes_from_point(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "Offline approval policy", "has_minutes_approval_point": True})
        )
        earlier = self._drafted_meeting("Earlier offline minutes", series=series)
        later = self._drafted_meeting(
            "Offline minutes with approval", series=series, start_datetime="2026-11-08 10:00:00"
        )
        secretary = self.env["res.users"].create(
            {
                "name": "Assigned minutes secretary",
                "login": "assigned-minutes-secretary",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("community_meetings.group_meeting_reader").id,
                        ],
                    )
                ],
            }
        )
        earlier.with_user(self.editor).write({"reader_user_ids": [(4, secretary.id)]})
        later.with_user(self.editor).write({"secretary_id": secretary.id, "reader_user_ids": [(4, secretary.id)]})
        point = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        self.assertTrue(point)
        self.assertFalse(later.actual_start_datetime)
        with self.assertRaises(AccessError), self.cr.savepoint():
            later.with_user(self.editor).action_approve_pending_minutes(point.id, [earlier.id])
        self.assertTrue(self.approver.has_group("community_meetings.group_meeting_approver"))
        self.assertFalse(later.with_user(self.approver).get_live_capabilities()["can_approve_previous_minutes"])
        with self.assertRaises(AccessError), self.cr.savepoint():
            later.with_user(self.approver).action_approve_pending_minutes(point.id, [earlier.id])
        self.assertTrue(later.with_user(secretary).get_live_capabilities()["can_approve_previous_minutes"])
        with patch.object(type(self.env["ir.actions.report"]), "_render_qweb_pdf", return_value=(b"%PDF-1.4", "pdf")):
            revisions = later.with_user(secretary).action_approve_pending_minutes(point.id, [earlier.id])
        self.assertEqual({revision.meeting_id for revision in revisions}, {earlier})
        self.assertEqual((earlier.state, later.state), ("approved", "minutes_draft"))
        self.assertEqual(point.disposition, "closed")
        snapshot = json.loads(earlier.approved_revision_id.snapshot_json)
        self.assertEqual(snapshot["approval"]["origin"], "offline")
        self.assertTrue(snapshot["approval"]["offline"])
        approval = point.minutes_approval_ids.filtered(lambda row: row.meeting_id == earlier)
        self.assertEqual(approval.revision_id, earlier.approved_revision_id)

    def test_minutes_approval_queue_is_readable_and_empty_without_prior_minutes(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "Read-only approval queue", "has_minutes_approval_point": True})
        )
        current = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Current meeting without prior minutes",
                    "series_id": series.id,
                    "start_datetime": "2026-11-20 10:00:00",
                }
            )
        )
        point = current.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        self.assertEqual(current.get_pending_minutes_for_approval(), [])

        held = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Held minutes for reader",
                    "series_id": series.id,
                    "start_datetime": "2026-11-10 10:00:00",
                }
            )
        )
        held.action_schedule()
        held.action_mark_held()
        reader = self.env["res.users"].create(
            {
                "name": "Read-only minutes reviewer",
                "login": "read-only-minutes-reviewer",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("community_meetings.group_meeting_reader").id,
                        ],
                    )
                ],
            }
        )
        held.with_user(self.editor).write({"reader_user_ids": [(4, reader.id)]})
        current.with_user(self.editor).write({"reader_user_ids": [(4, reader.id)]})

        pending = current.with_user(reader).get_pending_minutes_for_approval()
        self.assertEqual([(row["id"], row["state"]) for row in pending], [(held.id, "held")])
        self.assertFalse(current.with_user(reader).get_live_capabilities()["can_approve_previous_minutes"])
        with self.assertRaises(UserError), self.cr.savepoint():
            current.with_user(reader).action_approve_pending_minutes(point.id, [held.id])

    def test_snapshot_records_pending_destination_series(self):
        meeting = self._drafted_meeting("Pending follow-up destination")
        destination = self.env["community.meeting.series"].with_user(self.editor).create({"name": "Future assembly"})
        resolution = (
            self.env["community.meeting.resolution"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": meeting.agenda_item_ids[0].id,
                    "title": "Review later",
                }
            )
        )
        self.env["community.meeting.carryover"].with_user(self.editor).create(
            {
                "origin_model": "resolution",
                "origin_record_id": resolution.id,
                "destination_series_id": destination.id,
            }
        )
        revision = self._approve_without_rendering_pdf(meeting.with_user(self.approver))
        snapshot = json.loads(revision.snapshot_json)
        self.assertEqual(snapshot["schema_version"], 3)
        self.assertEqual(
            snapshot["carryovers"][0]["destination_series"],
            {"id": destination.id, "name": destination.name},
        )
        carry = snapshot["carryovers"][0]
        self.assertIn(meeting.code, carry["origin_meeting"])
        self.assertIn(meeting.name, carry["origin_meeting"])
        self.assertEqual(carry["destination_meeting"], "")
        self.assertEqual(snapshot["agenda"][0]["moved_to"], destination.name)
        self.assertEqual(snapshot["agenda"][0]["moved_to_kind"], "series")
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "community_meetings.report_revision_document", revision.ids
        )
        self.assertIn(b"Next meeting in", html)
        self.assertIn(destination.name.encode(), html)

    def test_report_shows_presenter_actual_end_and_localized_status(self):
        presenter = self.env["res.partner"].create({"name": "Report Presenter"})
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Report clarity",
                    "start_datetime": "2026-11-01 10:00:00",
                    "end_datetime": "2026-11-01 12:00:00",
                    "location": False,
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Presented point",
                    "kind": "information",
                    "discussion_notes": "<p>Report discussion</p>",
                    "disposition": "discussed",
                }
            )
        )
        item.topic_id.with_user(self.editor).write({"presenter_partner_id": presenter.id})
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_start_meeting()
        meeting.with_user(self.editor).action_mark_held()
        meeting.with_user(self.editor).action_draft_minutes()
        meeting.with_user(self.editor).write({"minutes_notes": "<p><br></p>"})
        revision = self._approve_without_rendering_pdf(meeting.with_user(self.approver))
        snapshot = json.loads(revision.snapshot_json)
        report_model = self.env["report.community_meetings.report_revision_document"]
        document = report_model._prepare_document(snapshot, revision=revision)
        self.assertFalse(document["has_minutes_notes"])
        self.assertFalse(document["has_description"])
        self.assertEqual(snapshot["meeting"]["end_datetime"], "2026-11-01 12:00:00")
        self.assertNotIn("end_datetime_display", snapshot["meeting"])
        self.assertTrue(snapshot["meeting"]["actual_start_datetime_display"])
        self.assertTrue(snapshot["meeting"]["actual_end_datetime_display"])
        self.assertTrue(snapshot["meeting"]["actual_end_same_day"])
        self.assertTrue(snapshot["meeting"]["actual_end_time_display"])
        self.assertEqual(snapshot["agenda"][0]["presenter"], presenter.name)
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "community_meetings.report_revision_document", revision.ids
        )
        self.assertIn(b"Proposed by", html)
        self.assertIn(presenter.name.encode(), html)
        self.assertIn(b"Meeting end", html)
        self.assertIn(b"Meeting date", html)
        self.assertIn(b"Scheduled date", html)
        self.assertNotIn(b"Location", html)
        self.assertIn(b"Discussed", html)
        self.assertNotIn(b">discussed<", html)
        self.assertNotIn(b"<h2>Minutes</h2>", html)

    def test_draft_preview_contains_only_public_content_and_has_no_write_effects(self):
        meeting = self._drafted_meeting("Draft preview content")
        item = meeting.agenda_item_ids[0]
        meeting.with_user(self.editor).write({"minutes_notes": "<p>Preview narrative</p>"})
        self.env["community.meeting.resolution"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "title": "Preview agreement",
                "body": "<p>Public agreement</p>",
            }
        )
        self.env["community.meeting.editor.note"].with_user(self.editor).create(
            {"meeting_id": meeting.id, "agenda_item_id": item.id, "content": "PRIVATE_PREVIEW_NOTE"}
        )
        self.env["community.meeting.dissent"].with_user(self.editor).create(
            [
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "body": "<p>Preview dissent</p>",
                },
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "body": "SECOND_PREVIEW_DISSENT",
                },
            ]
        )

        before_state = meeting.state
        before_revisions = meeting.revision_ids.ids
        preview = meeting.with_user(self.editor).get_minutes_preview_html()

        self.assertTrue("Draft — not approved." in preview or "Borrador — sin aprobar." in preview)
        self.assertIn("Preview narrative", preview)
        self.assertIn("Preview agreement", preview)
        self.assertIn("Preview dissent", preview)
        self.assertIn("SECOND_PREVIEW_DISSENT", preview)
        self.assertNotIn("PRIVATE_PREVIEW_NOTE", preview)
        self.assertEqual(meeting.state, before_state)
        self.assertEqual(meeting.revision_ids.ids, before_revisions)

        meeting.with_user(self.editor).write({"minutes_notes": "<p>Updated preview narrative</p>"})
        updated_preview = meeting.with_user(self.editor).get_minutes_preview_html()
        self.assertIn("Updated preview narrative", updated_preview)
        self.assertNotIn("Preview narrative", updated_preview)

        approver_meeting = meeting.with_user(self.approver)
        public_content = (
            self.env["community.meeting.revision"]
            .with_user(self.approver)
            ._build_public_content(
                approver_meeting,
                timezone=(meeting.series_id.timezone or meeting.company_id.partner_id.tz or "UTC"),
            )
        )
        revision = self._approve_without_rendering_pdf(meeting.with_user(self.approver))
        snapshot = json.loads(revision.snapshot_json)
        self.assertEqual({key: snapshot[key] for key in public_content}, public_content)

    def test_minutes_preview_and_approved_snapshot_use_their_expected_timezones(self):
        self.editor.write({"tz": "America/Los_Angeles"})
        self.approver.write({"tz": "Pacific/Honolulu"})
        self.env.company.partner_id.tz = "Europe/Madrid"
        meeting = self._drafted_meeting("Minutes timezone behavior", start_datetime="2026-11-01 10:00:00")

        preview = meeting.with_user(self.editor).get_minutes_preview_html()
        self.assertIn("2:00 AM", preview)
        self.assertIn("America/Los_Angeles", preview)

        revision = self._approve_without_rendering_pdf(meeting.with_user(self.approver))
        snapshot = json.loads(revision.snapshot_json)
        self.assertEqual(snapshot["meeting"]["start_timezone"], "Europe/Madrid")
        self.assertEqual(snapshot["meeting"]["start_datetime_display"], "11/1/26, 11:00 AM")

    def test_approved_minutes_use_series_timezone_before_company_timezone(self):
        self.approver.write({"tz": "Pacific/Honolulu"})
        self.env.company.partner_id.tz = "Europe/Madrid"
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "Tokyo timezone", "timezone": "Asia/Tokyo"})
        )
        meeting = self._drafted_meeting("Series timezone behavior", series=series)

        revision = self._approve_without_rendering_pdf(meeting.with_user(self.approver))
        snapshot = json.loads(revision.snapshot_json)
        self.assertEqual(snapshot["meeting"]["start_timezone"], "Asia/Tokyo")
        self.assertEqual(snapshot["meeting"]["start_datetime_display"], "11/1/26, 7:00 PM")

    def test_approved_minutes_fall_back_to_utc_without_a_meeting_timezone(self):
        self.env.company.partner_id.tz = False
        meeting = self._drafted_meeting("UTC timezone fallback")

        revision = self._approve_without_rendering_pdf(meeting.with_user(self.approver))
        snapshot = json.loads(revision.snapshot_json)
        self.assertEqual(snapshot["meeting"]["start_timezone"], "UTC")
        self.assertEqual(snapshot["meeting"]["start_datetime_display"], "11/1/26, 10:00 AM")

    def test_preview_action_points_to_preview_client_action(self):
        meeting = self._drafted_meeting("Preview client action")
        action = meeting.with_user(self.editor).action_preview_minutes()
        self.assertEqual(action["tag"], "community_meetings.minutes_preview")
        self.assertEqual(action["params"]["meeting_id"], meeting.id)

    def test_minutes_snapshot_renumbers_structural_agenda_points(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Renumbered minutes series",
                    "has_minutes_approval_point": True,
                    "has_next_meeting_point": True,
                }
            )
        )
        meeting = self._drafted_meeting("Renumber structural points", series=series)

        agenda = self.env["community.meeting.revision"]._build_public_content(meeting)["agenda"]

        self.assertGreaterEqual(len(agenda), 3)
        self.assertEqual([item["sequence"] for item in agenda], list(range(1, len(agenda) + 1)))
        self.assertEqual(agenda[0]["kind"], "minutes_approval")
        self.assertEqual(agenda[-1]["kind"], "next_meeting")

    def test_minutes_snapshot_preserves_agreed_next_meeting_datetime_and_timezone(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Next meeting snapshot",
                    "timezone": "Europe/Madrid",
                    "has_next_meeting_point": True,
                }
            )
        )
        meeting = self._drafted_meeting("Next meeting snapshot", series=series)
        next_point = meeting.agenda_item_ids.filtered(lambda item: item.kind == "next_meeting")
        next_point.write({"next_meeting_datetime": "2026-11-15 09:30:00"})

        item = next(
            row
            for row in self.env["community.meeting.revision"]._build_public_content(meeting, timezone=series.timezone)[
                "agenda"
            ]
            if row["kind"] == "next_meeting"
        )

        self.assertEqual(item["next_meeting_datetime"], "2026-11-15 09:30:00")
        self.assertEqual(item["next_meeting_timezone"], "Europe/Madrid")
        self.assertTrue(item["next_meeting_datetime_display"])

        revision = self._approve_without_rendering_pdf(meeting.with_user(self.approver))
        frozen = json.loads(revision.snapshot_json)["agenda"][-1]
        self.assertEqual(frozen["next_meeting_datetime"], "2026-11-15 09:30:00")
        report_html, report_type = self.env["ir.actions.report"]._render_qweb_html(
            "community_meetings.report_revision_document", revision.ids
        )
        self.assertEqual(report_type, "html")
        self.assertIn(item["next_meeting_datetime_display"].encode(), report_html)
        self.assertIn(b"Europe/Madrid", report_html)
        # Later changes to the live agenda and series must not rewrite the
        # approved record or its already generated PDF.
        approved_json = revision.snapshot_json
        approved_pdf = revision.pdf_attachment_id.raw
        manager_meeting = meeting.with_user(self.manager)
        manager_meeting.action_start_amendment()
        next_point.with_user(self.manager).write({"next_meeting_datetime": "2026-12-15 09:30:00"})
        amended_revision = self._approve_without_rendering_pdf(manager_meeting)
        series.timezone = "UTC"
        self.assertEqual(revision.snapshot_json, approved_json)
        self.assertEqual(revision.pdf_attachment_id.raw, approved_pdf)
        self.assertEqual(
            json.loads(amended_revision.snapshot_json)["agenda"][-1]["next_meeting_datetime"],
            "2026-12-15 09:30:00",
        )
        updated_html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "community_meetings.report_revision_document", revision.ids
        )
        self.assertEqual(updated_html, report_html)

    def test_minutes_snapshot_keeps_an_empty_next_meeting_date_empty(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "No agreed next meeting", "has_next_meeting_point": True})
        )
        meeting = self._drafted_meeting("No next date", series=series)
        next_point = meeting.agenda_item_ids.filtered(lambda item: item.kind == "next_meeting")
        self.assertFalse(next_point.next_meeting_datetime)

        item = next(
            row
            for row in self.env["community.meeting.revision"]._build_public_content(meeting)["agenda"]
            if row["kind"] == "next_meeting"
        )
        self.assertEqual(item["next_meeting_datetime"], "")
        self.assertEqual(item["next_meeting_datetime_display"], "")
        self.assertEqual(item["next_meeting_timezone"], "")

    def test_approved_minutes_follow_reordered_agenda(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Reordered minutes series",
                    "has_minutes_approval_point": True,
                    "has_next_meeting_point": True,
                }
            )
        )
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Reordered minutes",
                    "series_id": series.id,
                    "start_datetime": "2026-11-01 10:00:00",
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        items = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                [
                    {"meeting_id": meeting.id, "name": "Review open actions"},
                    {"meeting_id": meeting.id, "name": "Second discussion"},
                ]
            )
        )
        ordered_ids = meeting.agenda_item_ids.sorted("sequence").ids
        first_index = ordered_ids.index(items[0].id)
        second_index = ordered_ids.index(items[1].id)
        ordered_ids[first_index], ordered_ids[second_index] = (
            ordered_ids[second_index],
            ordered_ids[first_index],
        )
        meeting.action_reorder_agenda_items(ordered_ids)
        meeting.action_schedule()
        meeting.action_mark_held()
        meeting.action_draft_minutes()

        later = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Later meeting approves reordered minutes",
                    "series_id": series.id,
                    "start_datetime": "2026-11-10 10:00:00",
                    "secretary_id": self.editor.id,
                    "reader_user_ids": [(4, self.approver.id)],
                }
            )
        )
        approval_point = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        later.action_schedule()
        later.action_start_meeting()
        with patch.object(
            type(self.env["ir.actions.report"]),
            "_render_qweb_pdf",
            return_value=(b"%PDF-1.4\n", "pdf"),
        ):
            later.with_user(self.editor).action_approve_pending_minutes(approval_point.id, [meeting.id])
        revision = meeting.approved_revision_id
        agenda = json.loads(revision.snapshot_json)["agenda"]

        self.assertEqual([item["sequence"] for item in agenda], list(range(1, len(agenda) + 1)))
        self.assertEqual(
            [item["name"] for item in agenda if item["kind"] not in {"minutes_approval", "next_meeting"}],
            ["Second discussion", "Review open actions"],
        )

    def test_approved_minutes_actions_open_the_approved_revision(self):
        meeting, _action, revision = self._approved_meeting()
        action = meeting.with_user(self.approver).action_view_approved_minutes()
        self.assertEqual(action["tag"], "community_meetings.minutes_preview")
        self.assertEqual(action["params"]["meeting_id"], meeting.id)
        self.assertEqual(action["params"]["revision_id"], revision.id)
        self.assertEqual(action["params"]["return_to"], "form")
        list_action = (
            meeting.with_user(self.approver).with_context(minutes_return_to="list").action_view_approved_minutes()
        )
        self.assertEqual(list_action["params"]["return_to"], "list")
        html = revision.get_approved_minutes_preview_html()
        self.assertIn("Revision stability test", html)
        self.assertIn("Review open actions", html)

    def test_approved_minutes_action_requires_a_revision(self):
        meeting = self._drafted_meeting("No approved minutes yet")
        with self.assertRaises(UserError):
            meeting.with_user(self.approver).action_view_approved_minutes()

    def test_live_direct_approval_records_live_origin(self):
        meeting = self._drafted_meeting("Live direct approval")
        with patch.object(
            type(self.env["ir.actions.report"]),
            "_render_qweb_pdf",
            return_value=(b"%PDF-1.4", "pdf"),
        ):
            revision = meeting.with_user(self.approver).action_approve_minutes_live()
        snapshot = json.loads(revision.snapshot_json)
        self.assertEqual(snapshot["approval"]["origin"], "live")
        self.assertFalse(snapshot["approval"]["manual"])
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "community_meetings.report_revision_document", revision.ids
        )
        self.assertIn(b"in the meeting", html)

    def test_report_html_and_snapshot_are_stable_after_action_changes(self):
        _, action, revision = self._approved_meeting()
        before_json = revision.snapshot_json
        before_pdf = revision.pdf_attachment_id.raw
        rendered_html, report_type = self.env["ir.actions.report"]._render_qweb_html(
            "community_meetings.report_revision_document", revision.ids
        )
        snapshot = json.loads(before_json)
        self.assertEqual(report_type, "html")
        self.assertIn(b"Review open actions", rendered_html)
        self.assertIn(b"Follow-ups", rendered_html)
        self.assertIn(b"Manual approval", rendered_html)
        self.assertTrue(snapshot["approval"]["manual"])
        legacy = json.loads(before_json)
        for key in ("origin", "meeting_code", "meeting_name", "point_name", "offline"):
            legacy["approval"].pop(key, None)
        report_model = self.env["report.community_meetings.report_revision_document"]
        doc = report_model._prepare_document(legacy, revision=revision)
        self.assertEqual(doc["snapshot"]["approval"]["origin"], "direct")
        self.assertIn(b"From point", rendered_html)
        self.assertGreaterEqual(rendered_html.count(b"Prepare follow-up"), 2)
        self.assertEqual(snapshot["agenda"][0]["discussion"], "<p>Initial discussion</p>")
        self.assertEqual(snapshot["agenda"][1]["decision_result"], "approved")
        self.assertEqual(snapshot["agenda"][1]["resolutions"][0]["decision_outcome"], "approved")
        self.assertEqual(snapshot["agenda"][1]["decision_result_label"], "Approved")
        self.assertTrue(before_pdf.startswith(b"%PDF"))
        self.assertEqual(len(revision.snapshot_sha256), 64)
        self.assertEqual(len(revision.pdf_sha256), 64)

        action.with_user(self.editor).write({"state": "done"})
        self.assertEqual(revision.snapshot_json, before_json)
        self.assertEqual(revision.pdf_attachment_id.raw, before_pdf)

    def test_amendment_creates_a_new_revision_and_keeps_the_old_pdf(self):
        meeting, _action, first = self._approved_meeting()
        first_pdf = first.pdf_attachment_id.raw
        manager_meeting = meeting.with_user(self.manager)
        manager_meeting.action_start_amendment()
        manager_meeting.write({"minutes_notes": "Corrected wording"})
        second = self._approve_without_rendering_pdf(manager_meeting)

        self.assertEqual(second.revision_number, 2)
        self.assertEqual(second.previous_revision_id, first)
        self.assertEqual(first.status, "superseded")
        self.assertEqual(first.pdf_attachment_id.raw, first_pdf)
        self.assertEqual(meeting.approved_revision_id, second)

    def test_direct_minutes_approval_requires_the_approver_role(self):
        meeting = self._drafted_meeting("Direct approval authorization")
        reader = self.env["res.users"].create(
            {
                "name": "Minutes Reader",
                "login": "minutes-reader-revision-test",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        meeting.with_user(self.editor).write({"reader_user_ids": [(4, reader.id)]})
        self.assertFalse(reader.has_group("community_meetings.group_meeting_approver"))
        with self.assertRaises(AccessError), self.cr.savepoint():
            meeting.with_user(reader)._approve_minutes()
        with self.assertRaises(AccessError), self.cr.savepoint():
            meeting.with_user(reader).action_approve_minutes()

    def test_offline_approval_requires_the_assigned_secretary_and_draft_point_meeting(self):
        series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "Offline secretary authorization", "has_minutes_approval_point": True})
        )
        earlier = self._drafted_meeting("Earlier offline approval", series=series)
        later = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Later offline approval",
                    "series_id": series.id,
                    "start_datetime": "2026-11-12 10:00:00",
                    "secretary_id": self.approver.id,
                }
            )
        )
        point = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        self.assertTrue(point)
        with self.assertRaises(AccessError), self.cr.savepoint():
            earlier.with_user(self.editor)._approve_minutes(point, offline=True)

        later.with_user(self.editor).write({"secretary_id": self.editor.id})
        with self.assertRaises(UserError), self.cr.savepoint():
            earlier.with_user(self.editor)._approve_minutes(point, offline=True)

    def test_later_approval_point_cannot_cross_series(self):
        first_series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "First approval series", "has_minutes_approval_point": True})
        )
        second_series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create({"name": "Second approval series", "has_minutes_approval_point": True})
        )
        earlier = self._drafted_meeting("Minutes in first series", series=first_series)
        later = self._drafted_meeting(
            "Approval point in another series", series=second_series, start_datetime="2026-11-12 10:00:00"
        )
        later.with_user(self.editor).write({"secretary_id": self.editor.id})
        point = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")

        with self.assertRaises(UserError), self.cr.savepoint():
            earlier.with_user(self.editor)._approve_minutes(point, offline=True)

    def test_approved_revision_is_immutable_and_pdf_download_checks_access(self):
        meeting, _action, revision = self._approved_meeting()
        with self.assertRaises(UserError), self.cr.savepoint():
            revision.write({"snapshot_json": "{}"})
        with self.assertRaises(UserError), self.cr.savepoint():
            revision.unlink()
        with self.assertRaises(UserError), self.cr.savepoint():
            revision.copy()

        download = revision.with_user(self.approver).action_download_pdf()
        self.assertEqual(download["type"], "ir.actions.act_url")
        self.assertEqual(download["url"], f"/web/content/{revision.pdf_attachment_id.id}?download=true")

        outsider = self.env["res.users"].create(
            {
                "name": "Revision download outsider",
                "login": "revision-download-outsider",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError), self.cr.savepoint():
            revision.with_user(outsider).action_download_pdf()

        revision_without_pdf = (
            self.env["community.meeting.revision"]
            .sudo()
            .create(
                {
                    "meeting_id": meeting.id,
                    "revision_number": 99,
                    "created_by_id": self.approver.id,
                    "created_at": "2026-11-01 10:00:00",
                    "approved_by_id": self.approver.id,
                    "approved_at": "2026-11-01 10:00:00",
                    "snapshot_json": "{}",
                    "snapshot_sha256": "0" * 64,
                    "status": "approved",
                }
            )
        )
        with self.assertRaises(UserError), self.cr.savepoint():
            revision_without_pdf.with_user(self.approver).action_download_pdf()

    def test_invalid_pdf_render_rolls_back_revision_and_approval(self):
        meeting = self._drafted_meeting("Invalid PDF approval")
        report_model = self.env["ir.actions.report"]
        with (
            patch.object(type(report_model), "_render_qweb_pdf", return_value=(b"not a PDF", "pdf")),
            self.assertRaises(UserError),
            self.cr.savepoint(),
        ):
            meeting.with_user(self.approver).action_approve_minutes()

        self.assertEqual(meeting.state, "minutes_draft")
        self.assertFalse(meeting.approved_revision_id)
        self.assertFalse(meeting.revision_ids)

    def test_agenda_type_can_be_changed_only_through_an_immutable_revision_amendment(
        self,
    ):
        meeting, _action, first = self._approved_meeting()
        decision = meeting.agenda_item_ids.filtered(lambda item: item.kind == "decision")
        with self.assertRaises(UserError):
            decision.with_user(self.manager).write({"kind": "information"})

        manager_meeting = meeting.with_user(self.manager)
        manager_meeting.action_start_amendment()
        meeting.resolution_ids.with_user(self.manager).write({"status": "withdrawn"})
        decision.with_user(self.manager).write({"kind": "information"})
        second = self._approve_without_rendering_pdf(manager_meeting)

        self.assertEqual(first.status, "superseded")
        self.assertEqual(second.revision_number, 2)
        self.assertEqual(json.loads(first.snapshot_json)["agenda"][1]["decision_result"], "approved")
        self.assertEqual(json.loads(second.snapshot_json)["agenda"][1]["kind"], "information")
