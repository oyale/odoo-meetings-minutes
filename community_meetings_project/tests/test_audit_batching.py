from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.community_meetings.models.followup_activity import FollowupActivity


@tagged("post_install", "-at_install")
class TestAuditBatching(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create(
            {
                "name": "Meeting Project Editor",
                "login": "meeting-project-link-test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("community_meetings.group_meeting_editor").id,
                            cls.env.ref("project.group_project_user").id,
                        ],
                    )
                ],
            }
        )
        cls.project = cls.env["project.project"].create(
            {"name": "Meeting Link Test Project"}
        )
        cls.tasks = cls.env["project.task"].create(
            [
                {
                    "name": "First linked task",
                    "project_id": cls.project.id,
                    "user_ids": [(4, cls.editor.id)],
                },
                {
                    "name": "Second linked task",
                    "project_id": cls.project.id,
                    "user_ids": [(4, cls.editor.id)],
                },
            ]
        )
        cls.series = (
            cls.env["community.meeting.series"]
            .with_user(cls.editor)
            .create(
                {
                    "name": "Project Link Test Series",
                }
            )
        )
        cls.meetings = (
            cls.env["community.meeting"]
            .with_user(cls.editor)
            .create(
                [
                    {
                        "name": "Source project link meeting",
                        "series_id": cls.series.id,
                        "start_datetime": "2026-11-01 10:00:00",
                    },
                    {
                        "name": "Destination project link meeting",
                        "series_id": cls.series.id,
                        "start_datetime": "2026-11-08 10:00:00",
                    },
                ]
            )
        )
        cls.item = (
            cls.env["community.meeting.agenda.item"]
            .with_user(cls.editor)
            .create(
                {
                    "meeting_id": cls.meetings[0].id,
                    "name": "Project integration point",
                }
            )
        )

    def test_task_removal_locks_open_topics_before_filtering(self):
        """An open TODO must serialize with a concurrent closure too."""
        self.series.write({"meeting_todo_requirement": "project"})
        self.item.write({"kind": "todo"})
        topic_class = type(self.item.topic_id)
        original_lock = topic_class._lock_workflow
        locked = []

        def record_lock(topics):
            locked.extend(topics.ids)
            return original_lock(topics)

        with patch.object(topic_class, "_lock_workflow", record_lock):
            self.env[
                "community.meeting.project.task.mixin"
            ]._check_closed_todo_project_tasks(self.item)

        self.assertEqual(locked, self.item.topic_id.ids)

    def test_legacy_evidence_override_is_honored_by_todo_validation(self):
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": self.meetings[0].id,
                    "agenda_item_id": self.item.id,
                    "name": "Evidence vetoed by another addon",
                    "responsible_user_id": self.editor.id,
                    "followup_kind": "project_task",
                    "project_task_ids": [(4, self.tasks[0].id)],
                }
            )
        )
        self.item.write({"kind": "todo"})
        action_class = type(action)
        original_evidence = action_class._has_execution_evidence
        calls = []

        def extension_evidence(record):
            calls.append(record.id)
            # Legacy addons often refine the inherited predicate.
            return original_evidence(record) and record.id != action.id

        with patch.object(action_class, "_has_execution_evidence", extension_evidence):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.item.write({"disposition": "closed"})

        self.assertIn(action.id, calls)
        self.assertEqual(self.item.disposition, "open")

    def test_project_evidence_delegates_native_actions_to_parent_batch_hook(self):
        native, project = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                [
                    {
                        "meeting_id": self.meetings[0].id,
                        "agenda_item_id": self.item.id,
                        "name": "Native evidence refined by parent addon",
                        "responsible_user_id": self.editor.id,
                        "followup_kind": "activity",
                    },
                    {
                        "meeting_id": self.meetings[0].id,
                        "agenda_item_id": self.item.id,
                        "name": "Project evidence",
                        "responsible_user_id": self.editor.id,
                        "followup_kind": "project_task",
                        "project_task_ids": [(4, self.tasks[0].id)],
                    },
                ]
            )
        )
        original = FollowupActivity._default_execution_evidence_by_action
        delegated = []

        def parent_extension(records):
            delegated.extend(records.ids)
            result = original(records)
            return {key: value and key != native.id for key, value in result.items()}

        with patch.object(
            FollowupActivity, "_default_execution_evidence_by_action", parent_extension
        ):
            evidence = (native | project)._execution_evidence_by_action()

        self.assertEqual(delegated, native.ids)
        self.assertEqual(evidence, {native.id: False, project.id: True})
