from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged("post_install", "-at_install")
class TestMeetingDomain(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Domain editor",
                "login": "domain-editor-test",
                "email": "domain-editor@example.test",
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

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.editor)

    def test_next_meeting_recurrence_preserves_local_time_across_dst(self):
        series = self.env["community.meeting.series"].create({"name": "DST series", "timezone": "Europe/Madrid", "next_meeting_rule": "interval_days", "next_meeting_interval_days": 7})
        self.assertEqual(str(series._propose_next_meeting_datetime("2026-10-23 08:00:00")), "2026-10-30 09:00:00")
        series.write({"next_meeting_interval_days": 2})
        with self.assertRaises(ValidationError):
            series._propose_next_meeting_datetime("2026-10-23 00:30:00")

    def test_point_edits_do_not_rewrite_held_minutes(self):
        meeting = self.env["community.meeting"].create({"name": "Frozen minutes", "start_datetime": "2026-11-02 10:00:00"})
        point = self.env["community.meeting.agenda.item"].create({"meeting_id": meeting.id, "name": "Frozen point"})
        meeting.action_schedule()
        meeting.action_mark_held()
        point.topic_id.write({"name": "Edited after the session"})
        self.assertEqual(point.name, "Frozen point")
        self.assertEqual(point.topic_id.name, "Edited after the session")

    def test_pauses_reject_editorial_rpc_writes_and_allow_minutes_drafting(self):
        meeting = self.env["community.meeting"].create({"name": "Pause policy", "start_datetime": "2026-11-01 10:00:00"})
        point = self.env["community.meeting.agenda.item"].create({"meeting_id": meeting.id, "name": "Notes"})
        meeting.action_schedule()
        meeting.action_start_meeting()
        point.action_start_timing()
        point.write({"discussion_notes": "Before pause"})
        point.action_pause_timing()
        with self.assertRaises(UserError), self.cr.savepoint():
            point.write({"discussion_notes": "Forbidden during point pause"})
        with self.assertRaises(UserError), self.cr.savepoint():
            point.with_context(allow_live_edit=True).write({"disposition": "discussed"})
        self.assertEqual(point.disposition, "open")
        point.action_start_timing()
        meeting.action_pause_meeting()
        with self.assertRaises(UserError):
            meeting.write({"minutes_notes": "Forbidden during meeting pause"})
        with self.assertRaises(UserError), self.cr.savepoint():
            point.write({"disposition": "deferred", "deferral_reason": "Wait"})
        self.assertEqual(point.disposition, "open")
        with self.assertRaises(UserError):
            self.env["community.meeting.resolution"].create({"meeting_id": meeting.id, "agenda_item_id": point.id, "title": "Forbidden agreement"})
        for model, values in [
            ("community.meeting.resolution", {"title": "Default context agreement"}),
            ("community.meeting.dissent", {"body": "Default context dissent"}),
            ("community.meeting.editor.note", {"content": "Default context note"}),
            ("community.meeting.action", {"name": "Default context follow-up"}),
        ]:
            with self.assertRaises(UserError):
                self.env[model].with_context(default_meeting_id=meeting.id, default_agenda_item_id=point.id).create(values)
        meeting.action_mark_held()
        point.write({"discussion_notes": "Editorial correction after meeting"})
        self.assertIn("Editorial correction", point.discussion_notes)

    def test_preparation_unifies_requests_and_promoted_followups(self):
        series = self.env["community.meeting.series"].create({"name": "Unified preparation"})
        origin = self.env["community.meeting"].create({"name": "Origin", "series_id": series.id, "start_datetime": "2026-11-01 10:00:00"})
        item = self.env["community.meeting.agenda.item"].create({"meeting_id": origin.id, "name": "Original"})
        resolution = self.env["community.meeting.resolution"].create({"meeting_id": origin.id, "agenda_item_id": item.id, "title": "Review agreement"})
        transfer = self.env["community.meeting.carryover"].create({"origin_model": "resolution", "origin_record_id": resolution.id, "destination_series_id": series.id})
        action = self.env["community.meeting.action"].create({"meeting_id": origin.id, "agenda_item_id": item.id, "name": "Promoted work"})
        item.write({"disposition": "closed"})
        origin.action_schedule()
        origin.action_mark_held()
        wizard = self.env["community.meeting.create.wizard"].create({"name": "Next", "series_id": series.id, "start_datetime": "2026-11-08 10:00:00", "step": "people"})
        wizard.action_next()
        self.assertEqual(len(wizard.carry_line_ids), 2)
        request_line = wizard.carry_line_ids.filtered(lambda line: line.transfer_id == transfer)
        self.assertTrue(request_line)
        request_line.decision = "postpone"
        wizard.action_finish()
        self.assertEqual(transfer.status, "pending")
        self.assertFalse(transfer.destination_meeting_id)
        included = wizard.created_meeting_id.agenda_item_ids
        self.assertEqual(len(included), 1)
        self.assertEqual(included.topic_id.origin_action_id, action)
        wizard.action_finish()
        self.assertEqual(len(wizard.created_meeting_id.agenda_item_ids), 1)
        later = self.env["community.meeting"]._agenda_candidates(series, "2026-11-15 10:00:00")
        self.assertIn(f"transfer:{transfer.id}", [candidate["key"] for candidate in later])

    def test_topic_identity_and_session_history(self):
        series = self.env["community.meeting.series"].create({"name": "Domain series"})
        first, second = self.env["community.meeting"].create(
            [
                {"name": "First", "series_id": series.id},
                {"name": "Second", "series_id": series.id},
            ]
        )
        point = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": first.id, "name": "Original"}
        )
        later = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": second.id, "topic_id": point.topic_id.id}
        )
        self.assertEqual(point.topic_id, later.topic_id)
        point.write({"discussion_notes": "<p>First session only</p>"})
        self.assertFalse(later.discussion_notes)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            later.copy({"meeting_id": second.id, "topic_id": point.topic_id.id})

    def test_topic_type_change_syncs_upcoming_participation_kind(self):
        series = self.env["community.meeting.series"].create({"name": "Type sync"})
        first, second = self.env["community.meeting"].create(
            [
                {"name": "First", "series_id": series.id},
                {"name": "Second", "series_id": series.id},
            ]
        )
        point = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": first.id, "name": "Shared point"}
        )
        later = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": second.id, "topic_id": point.topic_id.id}
        )
        self.assertEqual(point.kind, "discussion")
        self.assertEqual(later.kind, "discussion")
        decision_type = self.env.ref("community_meetings.agenda_type_decision")
        point.topic_id.write({"agenda_type_id": decision_type.id})
        # F2: propagation must keep kind == agenda_type_id.behavior on the
        # shared upcoming participation, not just copy the raw type id.
        self.assertEqual(later.agenda_type_id.behavior, "decision")
        self.assertEqual(later.kind, "decision")

    def test_structural_point_types_and_kind_sync(self):
        for behavior in ("minutes_approval", "next_meeting"):
            agenda_type = self.env["community.meeting.agenda.type"].search(
                [("behavior", "=", behavior), ("active", "=", True)], limit=1
            )
            self.assertTrue(agenda_type, "Missing agenda type for %s" % behavior)
        meeting = self.env["community.meeting"].create({"name": "Structural types"})
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Next", "kind": "next_meeting",
        })
        self.assertEqual(item.agenda_type_id.behavior, "next_meeting")
        self.assertEqual(item.kind, "next_meeting")

    def test_series_structural_points_are_added_in_order(self):
        series = self.env["community.meeting.series"].create({
            "name": "Structural",
            "has_minutes_approval_point": True,
            "has_next_meeting_point": True,
        })
        previous = self.env["community.meeting"].create({
            "name": "Previous meeting", "series_id": series.id,
            "start_datetime": "2026-10-01 10:00:00",
        })
        previous.action_schedule()
        previous.action_mark_held()
        meeting = self.env["community.meeting"].create({
            "name": "Structural meeting", "series_id": series.id,
            "start_datetime": "2026-10-08 10:00:00",
        })
        self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Regular point", "kind": "discussion",
        })
        items = meeting.agenda_item_ids.sorted("sequence")
        self.assertEqual(items[0].agenda_type_id.behavior, "minutes_approval")
        self.assertEqual(items[-1].agenda_type_id.behavior, "next_meeting")

    def test_no_minutes_approval_point_without_pending_minutes(self):
        series = self.env["community.meeting.series"].create({
            "name": "No pending minutes", "has_minutes_approval_point": True,
        })
        meeting = self.env["community.meeting"].create({
            "name": "Fresh meeting", "series_id": series.id,
            "start_datetime": "2026-10-08 10:00:00",
        })
        self.assertFalse(meeting.agenda_item_ids.filtered(
            lambda item: item.agenda_type_id.behavior == "minutes_approval"
        ))

    def test_approved_previous_minutes_are_recorded_on_later_point(self):
        series = self.env["community.meeting.series"].create({
            "name": "Approval history", "has_minutes_approval_point": True,
        })
        previous = self.env["community.meeting"].create({
            "name": "Previous", "series_id": series.id,
            "start_datetime": "2026-10-01 10:00:00",
        })
        previous.action_schedule()
        previous.action_mark_held()
        previous.action_draft_minutes()
        self.env["community.meeting.agenda.item"].create({
            "meeting_id": previous.id, "name": "Topic", "kind": "discussion",
        })
        later = self.env["community.meeting"].create({
            "name": "Later", "series_id": series.id,
            "start_datetime": "2026-10-08 10:00:00",
        })
        point = later.agenda_item_ids.filtered(lambda item: item.kind == "minutes_approval")
        self.assertTrue(point)
        self.assertEqual(later.get_pending_minutes_for_approval()[0]["id"], previous.id)
        previous.action_approve_minutes()
        self.assertEqual(later.get_pending_minutes_for_approval(), [])
        history = later.get_minutes_approval_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["meeting_id"], previous.id)
        self.assertEqual(point.minutes_approval_ids.meeting_id, previous)

    def test_approved_minutes_open_read_only_in_live_view(self):
        meeting = self.env["community.meeting"].create({"name": "Approved live view", "start_datetime": "2026-11-02 10:00:00"})
        meeting.action_schedule()
        meeting.action_mark_held()
        meeting.action_draft_minutes()
        self.env["community.meeting.agenda.item"].create({"meeting_id": meeting.id, "name": "Topic", "kind": "discussion"})
        meeting.action_approve_minutes()
        self.assertEqual(meeting.state, "approved")
        action = meeting.action_open_live_meeting()
        self.assertEqual(action["tag"], "community_meetings.live_meeting")
        self.assertEqual(action["params"]["meeting_id"], meeting.id)
        self.assertFalse(meeting.get_live_capabilities()["can_edit"])
        draft = self.env["community.meeting"].create({"name": "Draft live view", "start_datetime": "2026-11-03 10:00:00"})
        with self.assertRaises(UserError):
            draft.action_open_live_meeting()

    def test_meeting_code_falls_back_without_colliding(self):
        sequence = self.env["ir.sequence"].search([("code", "=", "community.meeting")])
        self.assertTrue(sequence, "The meeting sequence should exist after install.")
        sequence.sudo().unlink()
        with self.assertRaises(ValidationError):
            self.env["community.meeting"].create({
                "name": "No sequence meeting", "start_datetime": "2026-11-02 10:00:00",
            })

    def test_approver_without_editor_can_approve_minutes(self):
        # Pins the sudo() write in _set_approved_revision: approvers are
        # read-only on the meeting, yet must be able to approve.
        approver = self.env["res.users"].sudo().create({
            "name": "Domain approver",
            "login": "domain-approver-test",
            "email": "domain-approver@example.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("community_meetings.group_meeting_approver").id,
            ])],
        })
        self.assertFalse(approver.has_group("community_meetings.group_meeting_editor"))
        meeting = self.env["community.meeting"].create({
            "name": "Approval pin", "start_datetime": "2026-11-03 10:00:00",
            "reader_user_ids": [(4, approver.id)],
        })
        self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Topic", "kind": "discussion",
        })
        meeting.action_schedule()
        meeting.action_mark_held()
        meeting.action_draft_minutes()
        revision = meeting.with_user(approver).action_approve_minutes()
        self.assertEqual(meeting.state, "approved")
        self.assertEqual(revision.approved_by_id, approver)

    def test_series_next_meeting_rule_proposes_date(self):
        series = self.env["community.meeting.series"].create({"name": "Recurrence"})
        series.write({"next_meeting_rule": "interval_days", "next_meeting_interval_days": 7})
        self.assertEqual(
            str(series._propose_next_meeting_datetime("2026-10-20 10:00:00")),
            "2026-10-27 10:00:00",
        )

    def test_new_meeting_uses_the_agreed_next_date(self):
        series = self.env["community.meeting.series"].create({
            "name": "Agreed date", "has_next_meeting_point": True,
        })
        meeting = self.env["community.meeting"].create({
            "name": "First", "series_id": series.id,
            "start_datetime": "2026-10-01 10:00:00",
        })
        agreed = fields.Datetime.to_datetime("2026-10-15 17:30:00")
        meeting.agenda_item_ids.filtered(lambda i: i.kind == "next_meeting").write({
            "next_meeting_datetime": agreed,
        })
        self.assertEqual(series._proposed_next_meeting_datetime(), agreed)
        action = series.action_new_meeting()
        self.assertEqual(action["context"]["default_start_datetime"], agreed)
        series.write({"next_meeting_rule": "weekday", "next_meeting_weekday": "1"})
        self.assertEqual(
            str(series._propose_next_meeting_datetime("2026-10-19 10:00:00")),
            "2026-10-20 10:00:00",
        )
        series.write({"next_meeting_rule": "day_of_month", "next_meeting_day_of_month": 15})
        self.assertEqual(
            str(series._propose_next_meeting_datetime("2026-10-10 10:00:00")),
            "2026-10-15 10:00:00",
        )

    def test_followup_promotes_to_point_when_origin_closes(self):
        meeting = self.env["community.meeting"].create({
            "name": "Promotion",
            "start_datetime": "2026-11-01 10:00:00",
        })
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Point", "kind": "discussion",
        })
        meeting.action_schedule()
        item.write({"disposition": "closed"})
        action = self.env["community.meeting.action"].create({
            "meeting_id": meeting.id, "agenda_item_id": item.id, "name": "Continue work",
        })
        meeting.action_mark_held()
        promoted = self.env["community.meeting.topic"].search([
            ("origin_action_id", "=", action.id),
        ])
        self.assertEqual(len(promoted), 1)
        self.assertEqual(promoted.origin_topic_id, item.topic_id)
        self.assertEqual(promoted.name, "Continue work")
        self.assertEqual(promoted.agenda_type_id.behavior, "followup")

    def test_general_dissent_is_rejected(self):
        meeting = self.env["community.meeting"].create({"name": "No general dissent"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["community.meeting.dissent"].create({
                "meeting_id": meeting.id, "body": "General dissent",
            })

    def test_unstarted_meeting_can_change_and_remove_series(self):
        series = self.env["community.meeting.series"].create({"name": "Original series"})
        other = self.env["community.meeting.series"].create({"name": "Other series"})
        meeting = self.env["community.meeting"].create({"name": "Fixed series", "series_id": series.id})
        meeting.write({"series_id": series.id})
        meeting.write({"series_id": other.id})
        self.assertEqual(meeting.series_id, other)
        meeting.write({"series_id": False})
        self.assertFalse(meeting.series_id)

    def test_series_defaults_are_copied(self):
        series = self.env["community.meeting.series"].create(
            {
                "name": "Defaults",
                "duration_hours": 1.5,
                "attendee_partner_ids": [(4, self.env.user.partner_id.id)],
            }
        )
        meeting = self.env["community.meeting"].create(
            {
                "name": "Defaults meeting",
                "series_id": series.id,
                "start_datetime": "2026-12-01 10:00:00",
            }
        )
        self.assertEqual(meeting.duration_minutes, 90)
        self.assertEqual(meeting.attendee_partner_ids, series.attendee_partner_ids)
        self.assertEqual(str(meeting.end_datetime), "2026-12-01 11:30:00")
        series.write({"duration_hours": 2, "attendee_partner_ids": [(5, 0, 0)]})
        self.assertEqual(meeting.duration_minutes, 90)
        self.assertTrue(meeting.attendee_partner_ids)
        self.assertEqual(meeting.secretary_id, self.env.user)

    def test_series_meeting_name_pattern_updates_until_manually_overridden(self):
        series = self.env["community.meeting.series"].create({
            "name": "Quarterly board",
            "meeting_name_pattern": "{date} — {series}",
        })
        wizard = self.env["community.meeting.create.wizard"].create({
            "series_id": series.id,
            "start_datetime": "2026-12-01 12:00:00",
        })
        wizard._onchange_series()
        self.assertEqual(wizard.name, "2026-12-01 — Quarterly board")
        wizard.start_datetime = "2026-12-08 12:00:00"
        wizard._onchange_series()
        self.assertEqual(wizard.name, "2026-12-08 — Quarterly board")
        wizard.name = "Planning session"
        wizard.start_datetime = "2026-12-15 12:00:00"
        wizard._onchange_series()
        self.assertEqual(wizard.name, "Planning session")

    def test_series_meeting_name_pattern_rejects_unknown_placeholders(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["community.meeting.series"].create({
                "name": "Invalid pattern",
                "meeting_name_pattern": "{date} {unknown}",
            })

    def test_point_actual_minutes_are_recorded_and_non_negative(self):
        meeting = self.env["community.meeting"].create({"name": "Timing"})
        item = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": meeting.id, "name": "Timed point", "estimated_minutes": 20}
        )
        item.write({"actual_minutes": 27})
        self.assertEqual(item.actual_minutes, 27)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({"actual_minutes": -1})

    def test_point_timer_accumulates_when_reopened(self):
        meeting = self.env["community.meeting"].create({
            "name": "Point timing",
            "start_datetime": fields.Datetime.now() + timedelta(days=1),
        })
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Timed point",
        })
        meeting.action_schedule()
        meeting.action_start_meeting()

        item.action_start_timing()
        item.write({"actual_started_at": fields.Datetime.now() - timedelta(minutes=4)})
        item.write({"disposition": "closed"})
        first_seconds = item.actual_seconds
        self.assertGreaterEqual(first_seconds, 240)
        self.assertFalse(item.actual_started_at)

        with self.assertRaises(UserError):
            item.action_start_timing()
        item.write({"reopen_reason": "Continue after the next discussion."})
        item.action_reopen()
        item.action_start_timing()
        item.write({"actual_started_at": fields.Datetime.now() - timedelta(minutes=3)})
        item.action_pause_timing()
        self.assertGreaterEqual(item.actual_seconds, first_seconds + 180)
        self.assertGreaterEqual(item.actual_minutes, 7)

    def test_navigating_timer_can_pause_and_resume_same_point(self):
        # The browser tests cover focus/collapse; this verifies the server state
        # used by those controls can stop and resume without losing elapsed time.
        meeting = self.env["community.meeting"].create({
            "name": "Timer resume",
            "start_datetime": fields.Datetime.now() + timedelta(days=1),
        })
        first, second = self.env["community.meeting.agenda.item"].create([
            {"meeting_id": meeting.id, "name": "First"},
            {"meeting_id": meeting.id, "name": "Second"},
        ])
        meeting.action_schedule()
        meeting.action_start_meeting()
        first.action_start_timing()
        first.write({"actual_started_at": fields.Datetime.now() - timedelta(minutes=2)})
        second.action_start_timing()
        self.assertFalse(first.actual_started_at)
        self.assertGreaterEqual(first.actual_minutes, 2)
        second.write({"actual_started_at": fields.Datetime.now() - timedelta(minutes=1)})
        second.action_pause_timing()
        first.action_start_timing()
        first.write({"actual_started_at": fields.Datetime.now() - timedelta(minutes=1)})
        first.action_pause_timing()
        self.assertGreaterEqual(first.actual_minutes, 3)

    def test_paused_unresolved_live_point_is_offered_at_next_meeting(self):
        meeting = self.env["community.meeting"].create({
            "name": "Carry paused point",
            "start_datetime": fields.Datetime.now() + timedelta(days=1),
        })
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Unfinished discussion",
        })
        meeting.action_schedule()
        meeting.action_start_meeting()
        item.action_start_timing()
        item.action_pause_timing()
        self.assertTrue(item.has_started)
        self.assertFalse(item.review_next_meeting)
        meeting.action_mark_held()
        self.assertTrue(item.review_next_meeting)

    def test_live_decision_can_be_undone_and_agreement_edits_sync(self):
        meeting = self.env["community.meeting"].create({
            "name": "Live decision", "start_datetime": "2026-11-01 10:00:00",
        })
        item = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": meeting.id, "name": "Decision", "kind": "decision"}
        )
        agreement = self.env["community.meeting.resolution"].create({
            "meeting_id": meeting.id, "agenda_item_id": item.id,
            "title": "Decision agreement", "decision_outcome": "approved",
        })
        agreement.write({"decision_outcome": "denied"})
        self.assertEqual(item.decision_result, "denied")
        meeting.action_schedule()
        meeting.action_start_meeting()
        item.write({"reopen_reason": "The vote needs to be checked."})
        item.action_reopen()
        self.assertEqual(item.disposition, "open")
        self.assertEqual(item.decision_result, "pending")
        self.assertEqual(agreement.status, "withdrawn")
        self.assertEqual(item.topic_id.state, "open")

    def test_automatic_carryover_keeps_point_and_does_not_duplicate(self):
        series = self.env["community.meeting.series"].create(
            {"name": "Automatic domain", "carryover_policy": "automatic"}
        )
        first = self.env["community.meeting"].create(
            {
                "name": "First",
                "series_id": series.id,
                "start_datetime": "2026-10-01 10:00:00",
            }
        )
        item = self.env["community.meeting.agenda.item"].create(
            {
                "meeting_id": first.id,
                "name": "Continue me",
                "description": "<p>Context</p>",
                "priority": "3",
                "estimated_minutes": 25,
            }
        )
        item.write({"disposition": "deferred", "deferral_reason": "Waiting"})
        later = self.env["community.meeting"].create(
            {
                "name": "Later",
                "series_id": series.id,
                "start_datetime": "2026-10-08 10:00:00",
            }
        )
        later.action_refresh_carryovers()
        self.assertEqual(len(later.agenda_item_ids), 1)
        self.assertEqual(later.agenda_item_ids.topic_id, item.topic_id)
        self.assertEqual(later.agenda_item_ids.priority, "3")
        self.assertEqual(later.agenda_item_ids.description, item.description)
        self.assertFalse(item.review_next_meeting)

    def test_review_dismissal_is_per_destination(self):
        series = self.env["community.meeting.series"].create(
            {"name": "Review domain", "carryover_policy": "review"}
        )
        first = self.env["community.meeting"].create(
            {
                "name": "First",
                "series_id": series.id,
                "start_datetime": "2026-10-01 10:00:00",
            }
        )
        item = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": first.id, "name": "Maybe continue"}
        )
        item.write({"review_next_meeting": True})
        later = self.env["community.meeting"].create(
            {
                "name": "Later",
                "series_id": series.id,
                "start_datetime": "2026-10-08 10:00:00",
            }
        )
        self.assertFalse(later.agenda_item_ids)
        later.incoming_carryover_ids.action_dismiss()
        later.action_refresh_carryovers()
        self.assertEqual(later.incoming_carryover_ids.status, "dismissed")
        self.assertEqual(item.topic_id.state, "open")
        self.assertFalse(item.review_next_meeting)

    def test_followup_actions_are_offered_for_carryover_even_when_done(self):
        series = self.env["community.meeting.series"].create(
            {"name": "Follow-up carryover", "carryover_policy": "review"}
        )
        previous = self.env["community.meeting"].create({
            "name": "Previous follow-up meeting", "series_id": series.id,
            "start_datetime": "2026-10-01 10:00:00",
        })
        point = self.env["community.meeting.agenda.item"].create({
            "meeting_id": previous.id, "name": "Completed follow-up point",
        })
        self.env["community.meeting.action"].create({
            "meeting_id": previous.id, "agenda_item_id": point.id,
            "name": "Already completed follow-up", "state": "done",
        })
        next_meeting = self.env["community.meeting"].create({
            "name": "Next follow-up meeting", "series_id": series.id,
            "start_datetime": "2026-10-08 10:00:00",
        })

        candidates = self.env["community.meeting"]._carryover_candidates(
            series, next_meeting.start_datetime
        )

        self.assertEqual(candidates, point)
        self.assertFalse(point.review_next_meeting)

    def test_points_without_review_or_followup_are_not_carryover_candidates(self):
        series = self.env["community.meeting.series"].create(
            {"name": "No follow-up carryover", "carryover_policy": "review"}
        )
        previous = self.env["community.meeting"].create({
            "name": "Previous empty meeting", "series_id": series.id,
            "start_datetime": "2026-10-01 10:00:00",
        })
        point = self.env["community.meeting.agenda.item"].create({
            "meeting_id": previous.id, "name": "No follow-up point",
        })
        next_meeting = self.env["community.meeting"].create({
            "name": "Next empty meeting", "series_id": series.id,
            "start_datetime": "2026-10-08 10:00:00",
        })

        candidates = self.env["community.meeting"]._carryover_candidates(
            series, next_meeting.start_datetime
        )

        self.assertNotIn(point, candidates)

    def test_followup_allowed_kinds_cascade(self):
        company = self.env.company
        activity = self.env.ref("community_meetings.followup_kind_activity")
        company.sudo().write({"followup_allowed_kinds": [(6, 0, activity.ids)]})
        series = self.env["community.meeting.series"].create({"name": "Allowed kinds"})
        meeting = self.env["community.meeting"].create({
            "name": "Cascade", "series_id": series.id, "start_datetime": "2026-11-05 10:00:00",
        })
        item = self.env["community.meeting.agenda.item"].create({"meeting_id": meeting.id, "name": "Point"})
        self.assertEqual(meeting.get_followup_defaults(item.id)["allowed_kinds"], ["activity"])
        self.assertEqual(meeting.get_followup_defaults(item.id)["kind"], "activity")
        # A point override narrows nothing new in core, but must be accepted.
        item.followup_default_kind = "activity"
        self.assertEqual(item.get_followup_defaults()["kind"], "activity")

    def test_activity_default_uses_company_activity_type(self):
        call_type = self.env["mail.activity.type"].search([
            ("category", "=", "phonecall"),
        ], limit=1)
        self.assertTrue(call_type)
        self.env.company.sudo().write({
            "followup_default_kind": "activity",
            "meeting_default_activity_type_id": call_type.id,
        })
        meeting = self.env["community.meeting"].create({"name": "Activity-only policy"})
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Follow-up",
        })
        defaults = item.get_followup_defaults()
        self.assertEqual(defaults["kind"], "activity")
        action = self.env["community.meeting.action"].create({
            "meeting_id": meeting.id, "agenda_item_id": item.id,
            "name": "Call attendee",
        })
        self.assertEqual(action.followup_kind, "activity")
        self.assertEqual(action.followup_activity_id.activity_type_id, call_type)

    def test_activity_completion_is_durable_and_reopening_reschedules(self):
        meeting = self.env["community.meeting"].create({"name": "Activity meeting"})
        item = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": meeting.id, "name": "TODO", "kind": "todo"}
        )
        task = self.env["community.meeting.action"].create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "Draft the report",
                "followup_kind": "activity",
                "followup_activity_type_id": self.env.ref(
                    "mail.mail_activity_data_todo"
                ).id,
            }
        )
        activity = task.followup_activity_id
        self.assertTrue(activity)
        item.write({"disposition": "closed"})
        activity.action_feedback(feedback="Finished the report")
        self.assertEqual(task.state, "done")
        self.assertTrue(task.completed_on)
        self.assertFalse(task.followup_activity_id)
        self.assertTrue(task.exists())
        task.write({"state": "open", "deadline": "2026-12-02"})
        self.assertTrue(task.followup_activity_id)
        self.assertEqual(str(task.followup_activity_id.date_deadline), "2026-12-02")

    def test_closed_todo_rejects_deleting_its_last_native_activity(self):
        meeting = self.env["community.meeting"].create({"name": "Native evidence"})
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Closed TODO", "kind": "todo",
        })
        action = self.env["community.meeting.action"].create({
            "meeting_id": meeting.id, "agenda_item_id": item.id,
            "name": "Required activity", "followup_kind": "activity",
        })
        activity = action.followup_activity_id
        item.write({"disposition": "closed"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            activity.unlink()
        self.assertTrue(activity.exists())
        self.assertEqual(item.disposition, "closed")
        activity.action_feedback(feedback="Completed")
        self.assertTrue(action.followup_activity_completed_on)
        self.assertTrue(item._followup_actions())

    def test_closed_todo_keeps_evidence_when_one_of_two_activities_is_removed(self):
        other = self.env["res.users"].sudo().create({
            "name": "Other owner", "login": "native-evidence-other-owner",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("community_meetings.group_meeting_reader").id,
            ])],
        })
        meeting = self.env["community.meeting"].create({
            "name": "Two owners", "reader_user_ids": [(4, other.id)],
        })
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Two-owner TODO", "kind": "todo",
        })
        action = self.env["community.meeting.action"].create({
            "meeting_id": meeting.id, "agenda_item_id": item.id,
            "name": "Shared work", "followup_kind": "activity",
            "responsible_user_ids": [(6, 0, [self.env.uid, other.id])],
        })
        item.write({"disposition": "closed"})
        first = action.followup_activity_id
        first.unlink()
        self.assertEqual(len(action.followup_activity_ids.exists()), 1)
        self.assertTrue(item._followup_actions())
        with self.assertRaises(ValidationError), self.cr.savepoint():
            action.followup_activity_ids.unlink()

    def test_open_todo_allows_deleting_native_activity(self):
        meeting = self.env["community.meeting"].create({"name": "Open TODO"})
        item = self.env["community.meeting.agenda.item"].create({
            "meeting_id": meeting.id, "name": "Open point", "kind": "todo",
        })
        action = self.env["community.meeting.action"].create({
            "meeting_id": meeting.id, "agenda_item_id": item.id,
            "name": "Optional activity", "followup_kind": "activity",
        })
        activity = action.followup_activity_id
        activity.unlink()
        self.assertFalse(activity.exists())

    def test_core_todo_uses_native_activity(self):
        meeting = self.env["community.meeting"].create({"name": "Task meeting"})
        item = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": meeting.id, "name": "TODO", "kind": "todo"}
        )
        task = self.env["community.meeting.action"].create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "A native meeting to-do",
                "followup_kind": "activity",
            }
        )
        self.assertTrue(task.followup_activity_id)
        self.assertTrue(item._followup_actions())
        item.write({"disposition": "closed"})
        task.write({"state": "done"})
        self.assertEqual(task.state, "done")

    def test_native_followup_creates_one_activity_per_responsible_person(self):
        other = self.env["res.users"].sudo().create({"name": "Second responsible", "login": "second-followup-owner", "email": "second-responsible@example.test", "groups_id": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("community_meetings.group_meeting_reader").id])]})
        meeting = self.env["community.meeting"].create({"name": "Shared responsibility", "reader_user_ids": [(4, other.id)]})
        item = self.env["community.meeting.agenda.item"].create({"meeting_id": meeting.id, "name": "Work"})
        action = self.env["community.meeting.action"].create({"meeting_id": meeting.id, "agenda_item_id": item.id, "name": "Shared native to-do", "responsible_user_ids": [(6, 0, [self.env.uid, other.id])]})
        self.assertEqual(len(action.followup_activity_ids), 2)
        first = action.followup_activity_ids.filtered(lambda a: a.user_id.id == self.env.uid)
        first.action_feedback(feedback="My part is done")
        self.assertEqual(action.state, "open")
        self.assertEqual(len(action.followup_activity_ids), 1)
        action.followup_activity_ids.with_user(other).action_feedback(feedback="All done")
        self.assertEqual(action.state, "done")
        self.assertTrue(action.followup_activity_completed_on)
        action.write({"state": "open"})
        self.assertEqual(len(action.followup_activity_ids), 2)
        with self.assertRaises(ValidationError):
            action.with_context(meeting_followup_activity_internal=True).write({"followup_activity_completed_on": fields.Datetime.now()})

    def test_closed_point_followup_preserves_global_result_until_explicit_reopen(self):
        series = self.env["community.meeting.series"].create({"name": "Follow-up"})
        meetings = self.env["community.meeting"].create(
            [
                {"name": "First", "series_id": series.id},
                {"name": "Later", "series_id": series.id},
            ]
        )
        first = self.env["community.meeting.agenda.item"].create(
            {"name": "Decision", "meeting_id": meetings[0].id, "kind": "decision"}
        )
        self.env["community.meeting.resolution"].create(
            {
                "meeting_id": meetings[0].id,
                "agenda_item_id": first.id,
                "title": "Approved",
                "decision_outcome": "approved",
            }
        )
        later = self.env["community.meeting.agenda.item"].create(
            {"topic_id": first.topic_id.id, "meeting_id": meetings[1].id}
        )
        self.assertTrue(later.is_followup)
        later.write({"disposition": "discussed"})
        self.assertEqual(first.topic_id.state, "closed")
        self.assertEqual(first.topic_id.outcome, "approved")
        later.write({"reopen_reason": "New evidence"})
        later.action_reopen()
        self.assertEqual(first.topic_id.state, "open")
        self.assertFalse(later.is_followup)
        self.assertEqual(first.decision_result, "approved")

    def test_wizard_confirm_is_idempotent_and_rich_point_is_saved(self):
        wizard = self.env["community.meeting.create.wizard"].create(
            {
                "name": "Guided",
                "start_datetime": "2026-12-01 10:00:00",
                "duration_hours": 1.5,
            }
        )
        point = self.env["community.meeting.point.wizard"].create(
            {
                "creation_wizard_id": wizard.id,
                "name": "Rich topic",
                "description": '<p>Context <a href="https://example.org">reference</a></p>',
                "priority": "2",
                "estimated_minutes": 20,
            }
        )
        point.action_save()
        first = wizard.action_finish()["res_id"]
        second = wizard.action_finish()["res_id"]
        self.assertEqual(first, second)
        meeting = self.env["community.meeting"].browse(first)
        self.assertEqual(len(meeting.agenda_item_ids), 1)
        self.assertIn("href=", meeting.agenda_item_ids.description)
        self.assertEqual(meeting.agenda_item_ids.estimated_minutes, 20)

    def test_restricted_session_notes_are_not_shared_through_topic(self):
        outsider = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Other reader",
                    "login": "domain-other-reader",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                self.env.ref("base.group_user").id,
                                self.env.ref(
                                    "community_meetings.group_meeting_reader"
                                ).id,
                            ],
                        )
                    ],
                }
            )
        )
        series = self.env["community.meeting.series"].create({"name": "Private series"})
        private, shared = self.env["community.meeting"].create(
            [
                {"name": "Private", "series_id": series.id},
                {
                    "name": "Shared",
                    "series_id": series.id,
                    "reader_user_ids": [(4, outsider.id)],
                },
            ]
        )
        item = self.env["community.meeting.agenda.item"].create(
            {
                "name": "Shared point",
                "meeting_id": private.id,
                "discussion_notes": "<p>Restricted discussion</p>",
            }
        )
        public_item = self.env["community.meeting.agenda.item"].create(
            {"topic_id": item.topic_id.id, "meeting_id": shared.id}
        )
        topic = item.topic_id.with_user(outsider)
        self.assertEqual(topic.name, "Shared point")
        self.assertEqual(topic.participation_ids.ids, [public_item.id])
        self.assertFalse(public_item.with_user(outsider).discussion_notes)

    def test_unrelated_activity_can_complete_without_meeting_acl(self):
        employee = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Employee only",
                    "login": "domain-employee",
                    "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
                }
            )
        )
        activity = (
            self.env["mail.activity"]
            .sudo()
            .create(
                {
                    "res_model_id": self.env["ir.model"]._get("res.partner").id,
                    "res_id": employee.partner_id.id,
                    "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
                    "user_id": employee.id,
                    "summary": "Ordinary contact reminder",
                }
            )
        )
        activity.with_user(employee).action_feedback(feedback="Done")
        self.assertFalse(activity.exists())

    def test_wizard_can_exclude_automatic_continuation(self):
        series = self.env["community.meeting.series"].create(
            {"name": "Wizard automatic", "carryover_policy": "automatic"}
        )
        first = self.env["community.meeting"].create(
            {
                "name": "First",
                "series_id": series.id,
                "start_datetime": "2026-10-01 10:00:00",
            }
        )
        point = self.env["community.meeting.agenda.item"].create(
            {
                "meeting_id": first.id,
                "name": "Optional continuation",
                "review_next_meeting": True,
            }
        )
        wizard = self.env["community.meeting.create.wizard"].create(
            {
                "name": "Explicit exclusion",
                "series_id": series.id,
                "start_datetime": "2026-10-08 10:00:00",
                "step": "people",
            }
        )
        wizard.action_next()
        self.assertEqual(wizard.carry_line_ids.source_id, point)
        wizard.carry_line_ids.write({"decision": "postpone"})
        meeting = self.env["community.meeting"].browse(wizard.action_finish()["res_id"])
        self.assertFalse(meeting.agenda_item_ids)
        self.assertFalse(meeting.incoming_carryover_ids)
        self.assertTrue(point.review_next_meeting)

    def test_cancelled_automatic_destination_does_not_lose_point(self):
        series = self.env["community.meeting.series"].create(
            {"name": "Cancelled continuation", "carryover_policy": "automatic"}
        )
        first = self.env["community.meeting"].create(
            {
                "name": "First",
                "series_id": series.id,
                "start_datetime": "2026-10-01 10:00:00",
            }
        )
        item = self.env["community.meeting.agenda.item"].create(
            {
                "meeting_id": first.id,
                "name": "Continue after cancellation",
                "review_next_meeting": True,
            }
        )
        cancelled = self.env["community.meeting"].create(
            {
                "name": "Cancelled",
                "series_id": series.id,
                "start_datetime": "2026-10-08 10:00:00",
            }
        )
        self.assertEqual(cancelled.agenda_item_ids.topic_id, item.topic_id)
        cancelled.action_cancel()
        next_meeting = self.env["community.meeting"].create(
            {
                "name": "Replacement",
                "series_id": series.id,
                "start_datetime": "2026-10-15 10:00:00",
            }
        )
        self.assertEqual(next_meeting.agenda_item_ids.topic_id, item.topic_id)

    def test_removing_task_checks_closed_participations_of_same_point(self):
        first, second = self.env["community.meeting"].create(
            [{"name": "Task origin"}, {"name": "Resolution session"}]
        )
        origin = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": first.id, "name": "TODO shared", "kind": "todo"}
        )
        action = self.env["community.meeting.action"].create(
            {
                "meeting_id": first.id,
                "agenda_item_id": origin.id,
                "name": "Only assigned task",
            }
        )
        later = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": second.id, "topic_id": origin.topic_id.id}
        )
        later.write({"disposition": "closed"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            first.action_cancel()
            first.unlink()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            action.unlink()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            action.write({"responsible_user_id": False})

    def test_closed_point_requires_explicit_reopen(self):
        from odoo.exceptions import UserError

        meeting = self.env["community.meeting"].create({"name": "Reopen audit"})
        item = self.env["community.meeting.agenda.item"].create(
            {"name": "Resolved discussion", "meeting_id": meeting.id}
        )
        item.write({"disposition": "closed"})
        with self.assertRaises(UserError), self.cr.savepoint():
            item.write({"disposition": "open"})
        item.write({"reopen_reason": "Additional evidence"})
        item.action_reopen()
        self.assertEqual(item.topic_id.state, "open")
        self.assertTrue(
            item.topic_id.message_ids.filtered(
                lambda m: "Additional evidence" in (m.body or "")
            )
        )

    def test_legacy_closed_chain_migrates_without_replaying_workflow(self):
        import importlib.util
        from pathlib import Path

        series = self.env["community.meeting.series"].create(
            {"name": "Legacy chain", "carryover_policy": "automatic"}
        )
        first, second = self.env["community.meeting"].create(
            [
                {
                    "name": "Legacy first",
                    "series_id": series.id,
                    "start_datetime": "2026-10-01 10:00:00",
                },
                {
                    "name": "Legacy later",
                    "series_id": series.id,
                    "start_datetime": "2026-10-08 10:00:00",
                },
            ]
        )
        item = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": first.id, "name": "Legacy approved", "kind": "decision"}
        )
        self.env["community.meeting.resolution"].create(
            {
                "meeting_id": first.id,
                "agenda_item_id": item.id,
                "title": "Approved in first session",
                "decision_outcome": "approved",
            }
        )
        transfer = self.env["community.meeting.carryover"].create(
            {
                "origin_model": "agenda_item",
                "origin_record_id": item.id,
                "destination_meeting_id": second.id,
            }
        )
        destination = transfer.destination_item_id
        self.assertTrue(destination)
        ids = [item.id, destination.id]
        self.env.cr.execute(
            "UPDATE community_meeting_agenda_item SET topic_id=NULL,is_followup=false WHERE id IN %s",
            [tuple(ids)],
        )
        (item | destination).invalidate_recordset(["topic_id", "is_followup"])
        script = (
            Path(__file__).resolve().parents[1]
            / "migrations/18.0.2.0.0/post-migrate.py"
        )
        spec = importlib.util.spec_from_file_location(
            "meeting_domain_migration", script
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "18.0.1.0.14")
        (item | destination).invalidate_recordset()
        self.assertEqual(item.topic_id, destination.topic_id)
        self.assertEqual(
            (item.topic_id.state, item.topic_id.outcome), ("closed", "approved")
        )
        self.assertTrue(destination.is_followup)
        self.assertEqual(item.decision_result, "approved")
        count = self.env["community.meeting.topic"].sudo().search_count([])
        module.migrate(self.env.cr, "18.0.1.0.14")
        self.assertEqual(
            self.env["community.meeting.topic"].sudo().search_count([]), count
        )
