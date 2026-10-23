from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMeetingWorkflow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Meeting Editor",
                "login": "meeting-editor-test",
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
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Meeting Manager",
                "login": "meeting-manager-test",
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

    def _decision_agreement(self, item, outcome="approved"):
        return (
            self.env["community.meeting.resolution"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": item.meeting_id.id,
                    "agenda_item_id": item.id,
                    "title": "Recorded decision",
                    "decision_outcome": outcome,
                }
            )
        )

    def test_decisions_require_an_agreement_and_follow_its_result(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Decision rules"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Proposal",
                    "kind": "decision",
                }
            )
        )
        for values in ({"disposition": "closed"}, {"decision_result": "approved"}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                item.write(values)
        agreement = self._decision_agreement(item)
        self.assertEqual((item.decision_result, item.disposition), ("approved", "closed"))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._decision_agreement(item, "denied")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({"decision_result": "denied"})
        agreement.write({"decision_outcome": "denied"})
        self.assertEqual(item.decision_result, "denied")
        agreement.write({"status": "withdrawn"})
        self.assertEqual((item.decision_result, item.disposition), ("pending", "discussed"))

    def test_todo_requires_a_live_followup_action_before_resolving(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "TODO rules"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Prepare the draft",
                    "kind": "todo",
                }
            )
        )
        self.assertEqual(item.agenda_type_id, self.env.ref("community_meetings.agenda_type_todo"))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({"disposition": "closed"})
        first = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Prepare draft",
                }
            )
        )
        if "project_task_ids" in first._fields:
            project_group = self.env.ref("project.group_project_user")
            self.editor.write({"groups_id": [(4, project_group.id)]})
            project = (
                self.env["project.project"]
                .sudo()
                .create(
                    {
                        "name": "TODO project",
                        "user_id": self.editor.id,
                    }
                )
            )
            task = (
                self.env["project.task"]
                .sudo()
                .create(
                    {
                        "name": "Prepare draft",
                        "project_id": project.id,
                    }
                )
            )
            first.write({"project_task_ids": [(4, task.id)]})
        item.write({"disposition": "closed"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            first.write({"state": "cancelled"})
        self.assertEqual(item.disposition, "closed")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            first.unlink()

    def test_todo_can_be_postponed_without_a_followup_action(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "TODO postponement"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Wait for input",
                    "kind": "todo",
                }
            )
        )
        item.write({"disposition": "deferred", "deferral_reason": "Waiting for input"})
        self.assertEqual(item.disposition, "deferred")

    def test_followup_can_be_deleted_while_its_point_is_open(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Open follow-up cleanup",
                    "start_datetime": "2026-11-01 10:00:00",
                    "end_datetime": "2026-11-01 11:00:00",
                }
            )
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Prepare the proposal",
                    "kind": "todo",
                }
            )
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Draft it",
                }
            )
        )
        meeting.with_user(self.editor).action_schedule()

        action.with_user(self.editor).unlink()

        self.assertFalse(action.exists())
        self.assertEqual(item.disposition, "open")

    def test_informational_agenda_and_workflow(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Operations check-in",
                    "start_datetime": "2026-11-01 10:00:00",
                    "end_datetime": "2026-11-01 11:00:00",
                }
            )
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Opening information",
                    "kind": "information",
                }
            )
        )
        self.assertEqual(item.kind, "information")
        self.assertEqual(item.agenda_type_id, self.env.ref("community_meetings.agenda_type_information"))
        self.assertEqual(item.presenter_partner_id, self.editor.partner_id)
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        meeting.with_user(self.editor).action_draft_minutes()
        self.assertEqual(meeting.state, "minutes_draft")

    def test_agenda_point_type_is_shared_between_meetings(self):
        meetings = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                [
                    {"name": "First meeting"},
                    {"name": "Second meeting"},
                ]
            )
        )
        shared_type = self.env.ref("community_meetings.agenda_type_decision")
        points = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                [
                    {"meeting_id": meetings[0].id, "name": "Decision one", "agenda_type_id": shared_type.id},
                    {"meeting_id": meetings[1].id, "name": "Decision two", "agenda_type_id": shared_type.id},
                ]
            )
        )
        self.assertEqual(points.mapped("agenda_type_id"), shared_type)
        self.assertEqual(points.mapped("kind"), ["decision", "decision"])
        self.assertEqual(points.mapped("decision_result"), ["pending", "pending"])

    def test_copy_preserves_custom_agenda_type(self):
        custom_type = (
            self.env["community.meeting.agenda.type"]
            .with_user(self.manager)
            .create(
                {
                    "name": "Consent custom",
                    "behavior": "decision",
                }
            )
        )
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Original"})
        original_item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Approve the proposal",
                    "agenda_type_id": custom_type.id,
                }
            )
        )
        self._decision_agreement(original_item)

        duplicate = meeting.with_user(self.editor).copy()

        self.assertEqual(duplicate.agenda_item_ids.agenda_type_id, custom_type)
        self.assertEqual(duplicate.agenda_item_ids.decision_result, "pending")

    def test_manager_can_add_shared_type_but_cannot_redefine_used_behavior(self):
        shared_type = (
            self.env["community.meeting.agenda.type"]
            .with_user(self.manager)
            .create(
                {
                    "name": "Consent",
                    "behavior": "decision",
                }
            )
        )
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Consent meeting"})
        self.env["community.meeting.agenda.item"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "name": "Approve the minutes",
                "agenda_type_id": shared_type.id,
            }
        )
        with self.assertRaises(UserError):
            shared_type.with_user(self.manager).write({"behavior": "discussion"})

    def test_live_meeting_can_create_task_for_its_agenda_point(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Follow-up meeting"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Prepare the proposal",
                }
            )
        )
        task = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Draft proposal",
                }
            )
        )
        self.assertEqual(task.agenda_item_id, item)
        other_meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Other meeting"})
        with self.assertRaises(ValidationError):
            self.env["community.meeting.action"].with_user(self.editor).create(
                {
                    "meeting_id": other_meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Wrong meeting task",
                }
            )

    def test_direct_state_write_is_rejected(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "State guard"})
        with self.assertRaises(UserError):
            meeting.with_user(self.editor).write({"state": "scheduled"})

    def test_invalid_datetime_order_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["community.meeting"].with_user(self.editor).create(
                {
                    "name": "Invalid time",
                    "start_datetime": "2026-11-01 11:00:00",
                    "end_datetime": "2026-11-01 10:00:00",
                }
            )

    def test_meeting_must_have_a_start_time_before_scheduling(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Date required"})
        with self.assertRaises(ValidationError):
            meeting.with_user(self.editor).action_schedule()

    def test_series_can_open_a_new_meeting_with_series_defaults(self):
        series = self.env["community.meeting.series"].with_user(self.editor).create({"name": "Weekly"})
        action = series.with_user(self.editor).action_new_meeting()
        self.assertEqual(action["res_model"], "community.meeting.create.wizard")
        self.assertEqual(action["context"]["default_series_id"], series.id)

    def test_live_meeting_records_actual_start_and_end(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Actual times",
                    "start_datetime": "2026-11-01 10:00:00",
                }
            )
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_start_meeting()
        actual_start = meeting.actual_start_datetime
        self.assertTrue(actual_start)
        meeting.with_user(self.editor).action_start_meeting()
        self.assertEqual(meeting.actual_start_datetime, actual_start)
        meeting.with_user(self.editor).action_mark_held()
        self.assertEqual(meeting.state, "held")
        self.assertTrue(meeting.actual_end_datetime)
        self.assertGreaterEqual(meeting.actual_duration_minutes, 0)
        with self.assertRaises(UserError):
            meeting.with_user(self.editor).write({"actual_start_datetime": False})

    def test_live_meeting_pause_resume_excludes_paused_time_and_pauses_points(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Paused meeting",
                    "start_datetime": "2026-11-01 10:00:00",
                }
            )
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Timed discussion",
                    "kind": "discussion",
                }
            )
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_start_meeting()
        item.with_user(self.editor).action_start_timing()
        meeting.with_user(self.editor).action_pause_meeting()
        self.assertTrue(meeting.actual_paused_at)
        self.assertFalse(item.actual_started_at)
        with self.assertRaises(UserError):
            item.with_user(self.editor).action_start_timing()
        meeting.with_user(self.editor).action_resume_meeting()
        self.assertFalse(meeting.actual_paused_at)
        meeting.with_user(self.editor).action_mark_held()
        self.assertTrue(meeting.actual_end_datetime)
        self.assertGreaterEqual(meeting.actual_duration_minutes, 0)
        with self.assertRaises(UserError):
            meeting.with_user(self.editor).action_pause_meeting()

    def test_informational_agenda_does_not_need_resolution_or_action(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Information only"})
        self.env["community.meeting.agenda.item"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "name": "Notice",
                "kind": "information",
            }
        )
        self.assertFalse(meeting.resolution_ids)
        self.assertFalse(meeting.action_ids)

    def test_decision_agenda_items_record_approval_or_denial(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Decision outcomes"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Approve the proposal",
                    "kind": "decision",
                }
            )
        )
        self.assertEqual(item.decision_result, "pending")

    def test_decision_result_resolves_agenda_item(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Consistent decision"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Decision",
                    "kind": "decision",
                }
            )
        )
        self._decision_agreement(item)
        self.assertEqual(item.disposition, "closed")

    def test_switching_to_decision_clears_old_resolved_status(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Type change"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Topic",
                    "kind": "discussion",
                    "disposition": "closed",
                }
            )
        )
        item.with_user(self.editor).write({"reopen_reason": "Change the purpose of this point"})
        item.with_user(self.editor).action_reopen()
        item.with_user(self.editor).write({"kind": "decision"})
        self.assertEqual(item.disposition, "open")
        self.assertEqual(item.decision_result, "pending")
        agreement = self._decision_agreement(item)
        self.assertEqual(item.decision_result, "approved")
        agreement.write({"decision_outcome": "denied"})
        self.assertEqual(item.decision_result, "denied")
        self.assertEqual(item.disposition, "closed")
        agreement.write({"status": "withdrawn"})
        item.with_user(self.editor).write({"disposition": "deferred"})
        self.assertEqual(item.decision_result, "pending")

    def test_non_decision_agenda_items_cannot_have_a_decision_result(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Non-decision outcome"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Informational notice",
                    "kind": "information",
                }
            )
        )
        with self.assertRaises(ValidationError):
            item.with_user(self.editor).write({"decision_result": "approved"})

    def test_changing_agenda_item_type_resets_inapplicable_decision_result(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Change agenda type",
                    "start_datetime": "2026-11-01 10:00:00",
                }
            )
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Agenda point",
                    "kind": "decision",
                }
            )
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        agreement = self._decision_agreement(item)
        agreement.write({"status": "withdrawn"})
        item.with_user(self.editor).write({"kind": "information"})
        self.assertFalse(item.decision_result)
        item.with_user(self.editor).write({"kind": "decision"})
        self.assertEqual(item.decision_result, "pending")

    def test_editor_can_open_live_meeting_screen_during_meeting(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Live meeting",
                    "start_datetime": "2026-11-01 10:00:00",
                }
            )
        )
        meeting.with_user(self.editor).action_schedule()
        action = meeting.with_user(self.editor).action_open_live_meeting()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "community_meetings.live_meeting")
        self.assertEqual(action["params"]["meeting_id"], meeting.id)

    def test_live_meeting_uses_dedicated_client_action(self):
        self.assertIn(
            "community_meetings.live_meeting",
            self.env.ref("community_meetings.action_community_meeting_live_client").tag,
        )

    def test_agenda_item_cannot_be_moved_to_another_meeting(self):
        meetings = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                [
                    {"name": "First"},
                    {"name": "Second"},
                ]
            )
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meetings[0].id,
                    "name": "Keep source link",
                }
            )
        )
        with self.assertRaises(UserError):
            item.with_user(self.editor).write({"meeting_id": meetings[1].id})
