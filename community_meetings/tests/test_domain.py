from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install")
class TestMeetingDomain(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Domain editor",
                "login": "domain-editor-test",
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

    def test_point_actual_minutes_are_recorded_and_non_negative(self):
        meeting = self.env["community.meeting"].create({"name": "Timing"})
        item = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": meeting.id, "name": "Timed point", "estimated_minutes": 20}
        )
        item.write({"actual_minutes": 27})
        self.assertEqual(item.actual_minutes, 27)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({"actual_minutes": -1})

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

    def test_followup_defaults_inherit_company_and_allow_series_override(self):
        company = self.env.company
        call_type = self.env["mail.activity.type"].search(
            [("category", "=", "phonecall")], limit=1
        )
        self.assertTrue(call_type, "Odoo Call activity type must be installed")
        company.sudo().write(
            {
                "meeting_default_followup_kind": "activity",
                "meeting_default_activity_type_id": call_type.id,
            }
        )
        series = self.env["community.meeting.series"].create(
            {"name": "Follow-up defaults", "default_followup_kind": "inherit"}
        )
        meeting = self.env["community.meeting"].create(
            {"name": "Inherited follow-up defaults", "series_id": series.id}
        )
        defaults = meeting.get_followup_defaults()
        self.assertEqual(defaults["kind"], "activity")
        self.assertEqual(defaults["activity_type_id"], call_type.id)
        series.write({"default_followup_kind": "task"})
        self.assertEqual(meeting.get_followup_defaults()["kind"], "task")
        series.write({"default_followup_kind": "todo"})
        self.assertEqual(meeting.get_followup_defaults()["kind"], "todo")

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

    def test_meeting_task_does_not_create_an_odoo_activity(self):
        meeting = self.env["community.meeting"].create({"name": "Task meeting"})
        item = self.env["community.meeting.agenda.item"].create(
            {"meeting_id": meeting.id, "name": "TODO", "kind": "todo"}
        )
        task = self.env["community.meeting.action"].create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "A meeting task",
                "followup_kind": "task",
            }
        )
        self.assertFalse(task.followup_activity_id)
        self.assertTrue(item._followup_actions())
        item.write({"disposition": "closed"})
        task.write({"state": "done"})
        self.assertEqual(task.state, "done")

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
        wizard.carry_line_ids.write({"accept": False})
        meeting = self.env["community.meeting"].browse(wizard.action_finish()["res_id"])
        self.assertFalse(meeting.agenda_item_ids)
        self.assertEqual(meeting.incoming_carryover_ids.status, "dismissed")

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
