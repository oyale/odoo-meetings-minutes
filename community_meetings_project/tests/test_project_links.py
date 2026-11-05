import json
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import format_date


@tagged("post_install", "-at_install")
class TestCommunityMeetingProjectLinks(TransactionCase):
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
        cls.project = cls.env["project.project"].create({"name": "Meeting Link Test Project"})
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

    def test_project_followup_types_respect_series_allowlist(self):
        activity = self.env.ref("community_meetings.followup_kind_activity")
        self.series.sudo().write({"followup_allowed_kinds": [(6, 0, activity.ids)]})

        defaults = self.meetings[0].get_followup_defaults(self.item.id)

        self.assertEqual(defaults["allowed_kinds"], ["activity"])
        self.assertEqual(defaults["kind"], "activity")

    def test_project_todo_container_creates_private_task(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Todo container"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "name": "Point"})
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Buy milk",
                    "responsible_user_id": self.editor.id,
                    "followup_kind": "project_todo",
                }
            )
        )
        self.assertFalse(action.followup_activity_ids)
        self.assertEqual(len(action.project_task_ids), 1)
        self.assertFalse(action.project_task_ids.project_id)
        self.assertTrue(action.project_task_ids.user_ids)
        self.assertTrue(action._has_execution_evidence())

    def test_batched_evidence_is_returned_per_same_topic_action(self):
        meeting = self.meetings[0]
        actions = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                [
                    {
                        "meeting_id": meeting.id,
                        "agenda_item_id": self.item.id,
                        "name": "Same-topic action with task evidence",
                        "responsible_user_id": self.editor.id,
                        "followup_kind": "project_task",
                        "project_task_ids": [(4, self.tasks[0].id)],
                    },
                    {
                        "meeting_id": meeting.id,
                        "agenda_item_id": self.item.id,
                        "name": "Same-topic action without task evidence",
                        "responsible_user_id": self.editor.id,
                        "followup_kind": "project_task",
                    },
                ]
            )
        )

        evidence_by_action = actions._execution_evidence_by_action()

        self.assertEqual(
            evidence_by_action,
            {actions[0].id: True, actions[1].id: False},
        )

    def test_multiple_task_links_and_reverse_navigation(self):
        meeting = self.meetings[0]
        agenda = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Linked topic",
                    "project_task_ids": [(6, 0, self.tasks.ids)],
                }
            )
        )
        resolution = (
            self.env["community.meeting.resolution"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "title": "Linked resolution",
                    "agenda_item_id": agenda.id,
                    "project_task_ids": [(6, 0, [self.tasks[0].id])],
                }
            )
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Linked action",
                    "followup_kind": "project_task",
                    "agenda_item_id": agenda.id,
                    "project_task_ids": [(6, 0, [self.tasks[0].id])],
                }
            )
        )

        self.assertEqual(set(agenda.with_user(self.editor).project_task_ids.ids), set(self.tasks.ids))
        self.assertEqual(resolution.with_user(self.editor).project_task_ids, self.tasks[0])
        self.assertEqual(action.with_user(self.editor).project_task_ids, self.tasks[0])
        reverse = self.tasks[0].with_user(self.editor).action_view_community_meeting_links()
        self.assertEqual(reverse["res_model"], "community.meeting.project.task.links")
        self.assertEqual(reverse["context"]["default_agenda_item_ids"][0][2], agenda.ids)
        self.assertEqual(reverse["context"]["default_resolution_ids"][0][2], resolution.ids)
        self.assertEqual(reverse["context"]["default_action_ids"][0][2], action.ids)

    def test_meeting_reader_does_not_learn_inaccessible_project_task_ids(self):
        reader = self.env["res.users"].create(
            {
                "name": "Meeting reader without Project access",
                "login": "meeting-reader-no-project-access",
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
        meeting = self.meetings[0].with_user(self.editor)
        meeting.write({"reader_user_ids": [(4, reader.id)]})
        agenda = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Private task link",
                    "project_task_ids": [(6, 0, self.tasks.ids)],
                }
            )
        )

        with patch.object(type(self.env["project.task"]), "search", side_effect=AccessError("task is hidden")):
            returned = agenda.with_user(reader).read(["project_task_ids"])

        self.assertEqual(returned[0]["project_task_ids"], [])
        self.assertEqual(set(agenda.with_user(self.editor).project_task_ids.ids), set(self.tasks.ids))

    def test_minutes_project_tasks_are_snapshotted_and_rendered_separately(self):
        meeting = self.meetings[0].with_user(self.editor)
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "name": "Project delivery", "kind": "todo"})
        )
        extra = self.env["res.users"].create(
            {
                "name": "Task Owner <one>",
                "login": "project-task-owner-snapshot",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("project.group_project_user").id,
                        ],
                    )
                ],
            }
        )
        first, second = self.env["project.task"].create(
            [
                {
                    "name": "Prepare <budget> & plan",
                    "project_id": self.project.id,
                    "date_deadline": "2026-11-20",
                    "user_ids": [(6, 0, [self.editor.id, extra.id])],
                },
                {"name": "Publish minutes", "project_id": self.project.id, "user_ids": [(5, 0, 0)]},
            ]
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Coordinate delivery",
                    "followup_kind": "project_task",
                    "responsible_user_ids": [(6, 0, [self.editor.id])],
                    "project_task_ids": [(6, 0, [first.id, second.id])],
                }
            )
        )
        revision_model = self.env["community.meeting.revision"].with_user(self.editor)
        snapshot = revision_model._build_public_content(meeting)
        action_row = next(row for row in snapshot["actions"] if row["name"] == action.name)
        self.assertEqual(action_row["responsibles"], [self.editor.name])
        self.assertEqual(
            action_row["project_tasks"],
            [
                {
                    "name": first.name,
                    "deadline": "2026-11-20",
                    "assignees": sorted([self.editor.name, extra.name]),
                },
                {"name": second.name, "deadline": "", "assignees": []},
            ],
        )
        report_model = self.env["report.community_meetings.report_revision_document"]
        doc = report_model._prepare_document(snapshot=snapshot, draft=True)
        self.assertEqual(
            doc["actions"][0]["project_tasks"][0]["deadline_display"],
            format_date(self.env, "2026-11-20", lang_code=self.env.lang),
        )
        rendered = self.env["ir.qweb"]._render("community_meetings.report_revision_content", {"doc": doc})
        rendered_text = str(rendered)
        self.assertIn("Follow-up responsible", rendered_text)
        self.assertIn("Task assignees", rendered_text)
        self.assertIn("Prepare &lt;budget&gt; &amp; plan", rendered_text)
        self.assertNotIn("Prepare <budget> & plan", rendered_text)
        self.assertIn("Task Owner &lt;one&gt;", rendered_text)

    def test_approved_minutes_keep_project_task_snapshot_after_task_changes(self):
        meeting = self.meetings[0].with_user(self.editor)
        meeting.write({"reader_user_ids": [(4, self.editor.id)]})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "name": "Frozen Project task"})
        )
        task = self.env["project.task"].create(
            {
                "name": "Frozen task name",
                "project_id": self.project.id,
                "date_deadline": "2026-11-20",
                "user_ids": [(4, self.editor.id)],
            }
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "Frozen follow-up",
                "followup_kind": "project_task",
                "responsible_user_id": self.editor.id,
                "project_task_ids": [(4, task.id)],
            }
        )
        meeting.action_schedule()
        meeting.action_mark_held()
        meeting.action_draft_minutes()
        approver = self.env["res.users"].create(
            {
                "name": "Project Minutes Approver",
                "login": "project-minutes-snapshot-approver",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("community_meetings.group_meeting_approver").id,
                        ],
                    )
                ],
            }
        )
        meeting.write({"reader_user_ids": [(4, approver.id)]})
        report_model = self.env["ir.actions.report"]
        with patch.object(
            type(report_model),
            "_render_qweb_pdf",
            return_value=(b"%PDF-1.4\nminutes snapshot fixture\n", "pdf"),
        ):
            meeting.with_user(approver).action_approve_minutes()
        revision = meeting.approved_revision_id
        frozen_json = revision.snapshot_json
        report_document = self.env["report.community_meetings.report_revision_document"]
        snapshot = json.loads(frozen_json)
        frozen_document = report_document._prepare_document(snapshot=snapshot, revision=revision)
        frozen_render = str(
            self.env["ir.qweb"]._render("community_meetings.report_revision_content", {"doc": frozen_document})
        )
        self.assertIn("Frozen task name", frozen_render)
        task.write({"name": "Changed live task", "date_deadline": False, "user_ids": [(5, 0, 0)]})
        self.assertEqual(revision.snapshot_json, frozen_json)
        rerendered_document = report_document._prepare_document(
            snapshot=json.loads(revision.snapshot_json), revision=revision
        )
        rerendered = str(
            self.env["ir.qweb"]._render("community_meetings.report_revision_content", {"doc": rerendered_document})
        )
        self.assertEqual(rerendered, frozen_render)

    def test_project_task_minutes_projection_omits_inaccessible_tasks(self):
        reader = self.env["res.users"].create(
            {
                "name": "Minutes reader without Project access",
                "login": "minutes-reader-without-project",
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
        meeting = self.meetings[0].with_user(self.editor)
        meeting.write({"reader_user_ids": [(4, reader.id)]})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "name": "Private task link"})
        )
        task = self.env["project.task"].create(
            {
                "name": "Secret task name",
                "project_id": self.project.id,
                "date_deadline": "2026-11-20",
                "user_ids": [(4, self.editor.id)],
            }
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "Visible follow-up",
                "followup_kind": "project_task",
                "responsible_user_id": self.editor.id,
                "project_task_ids": [(4, task.id)],
            }
        )
        task_model = type(self.env["project.task"])
        original_search = task_model.search
        calls = 0

        def hide_task_during_link_read(recordset, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise AccessError("task is hidden")
            return original_search(recordset, *args, **kwargs)

        with patch.object(task_model, "search", hide_task_during_link_read):
            snapshot = (
                self.env["community.meeting.revision"]
                .with_user(reader)
                ._build_public_content(meeting.with_user(reader))
            )
        self.assertEqual(snapshot["actions"][0]["project_tasks"], [])

    def test_legacy_project_action_snapshot_renders_without_task_details(self):
        meeting = self.meetings[0].with_user(self.editor)
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "name": "Legacy snapshot point"})
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "agenda_item_id": item.id, "name": "Old action"})
        )
        legacy = self.env["community.meeting.revision"]._build_public_content(meeting)
        legacy["actions"][0].pop("project_tasks", None)
        legacy["actions"][0].pop("id", None)
        legacy["actions"][0]["name"] = action.name
        document = self.env["report.community_meetings.report_revision_document"]._prepare_document(legacy, draft=True)
        rendered = str(self.env["ir.qweb"]._render("community_meetings.report_revision_preview", {"doc": document}))
        self.assertIn("Old action", rendered)
        self.assertNotIn("o_minutes_project_task", rendered)

    def test_todo_cannot_close_without_project_task_on_followup_action(self):
        self.series.write({"meeting_todo_requirement": "project"})
        meeting = self.meetings[0]
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Implement the proposal",
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
                    "name": "Implement proposal",
                    "followup_kind": "project_task",
                }
            )
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.with_user(self.editor).write({"disposition": "closed"})

        action.with_user(self.editor).write({"project_task_ids": [(4, self.tasks[0].id)]})
        item.with_user(self.editor).write({"disposition": "closed"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.tasks[0].unlink()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            action.with_user(self.editor).write({"project_task_ids": [(5, 0, 0)]})

    def test_batch_todo_write_reaches_constraint_with_all_same_policy_items(self):
        size = 100
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Batched TODO constraint",
                    "series_id": self.series.id,
                }
            )
        )
        items = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                [
                    {
                        "meeting_id": meeting.id,
                        "name": f"Batched TODO {index}",
                        "kind": "todo",
                    }
                    for index in range(size)
                ]
            )
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            [
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": f"Batched TODO action {index}",
                    "responsible_user_id": self.editor.id,
                    "followup_kind": "activity",
                }
                for index, item in enumerate(items)
            ]
        )
        batch_sizes = []
        agenda_model = type(items)
        original_lookup = agenda_model._followup_actions_by_topic

        def record_lookup_batch(records):
            batch_sizes.append(len(records))
            return original_lookup(records)

        with patch.object(agenda_model, "_followup_actions_by_topic", record_lookup_batch):
            items.write({"disposition": "closed"})

        self.assertEqual(batch_sizes, [size])
        self.assertEqual(set(items.mapped("project_requirement_snapshot")), {"core"})

    def test_batch_todo_write_preserves_mixed_policy_snapshots(self):
        project_series = (
            self.env["community.meeting.series"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Project-required batch series",
                    "meeting_todo_requirement": "project",
                }
            )
        )
        core_meeting, project_meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                [
                    {"name": "Core-policy TODO", "series_id": self.series.id},
                    {"name": "Project-policy TODO", "series_id": project_series.id},
                ]
            )
        )
        core_item, project_item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                [
                    {
                        "meeting_id": core_meeting.id,
                        "name": "Core requirement",
                        "kind": "todo",
                    },
                    {
                        "meeting_id": project_meeting.id,
                        "name": "Project requirement",
                        "kind": "todo",
                    },
                ]
            )
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            [
                {
                    "meeting_id": core_meeting.id,
                    "agenda_item_id": core_item.id,
                    "name": "Core action",
                    "responsible_user_id": self.editor.id,
                    "followup_kind": "activity",
                },
                {
                    "meeting_id": project_meeting.id,
                    "agenda_item_id": project_item.id,
                    "name": "Project action",
                    "responsible_user_id": self.editor.id,
                    "followup_kind": "project_task",
                    "project_task_ids": [(4, self.tasks[0].id)],
                },
            ]
        )

        (core_item | project_item).write({"disposition": "closed"})

        self.assertEqual(core_item.project_requirement_snapshot, "core")
        self.assertEqual(project_item.project_requirement_snapshot, "project")

    def test_non_todo_points_do_not_require_project_tasks_to_close(self):
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": self.meetings[0].id,
                    "name": "Resolve the discussion",
                    "kind": "discussion",
                }
            )
        )
        item.with_user(self.editor).write({"disposition": "closed"})
        self.assertEqual(item.disposition, "closed")

    def test_project_task_wizard_can_override_series_project(self):
        series_project = self.env["project.project"].create(
            {
                "name": "Configured series task project",
                "company_id": self.editor.company_id.id,
            }
        )
        alternate_project = self.env["project.project"].create(
            {
                "name": "Alternate meeting task project",
                "company_id": self.editor.company_id.id,
            }
        )
        self.series.with_user(self.editor).write(
            {
                "meeting_project_mode": "series",
                "meeting_project_id": series_project.id,
            }
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": self.meetings[0].id,
                    "name": "Create in another project",
                    "followup_kind": "project_task",
                    "agenda_item_id": self.item.id,
                }
            )
        )
        wizard_model = self.env["community.meeting.project.task.wizard"].with_user(self.editor)
        defaults = wizard_model.with_context(default_action_id=action.id).default_get(
            ["action_id", "project_id", "has_default_project"]
        )
        self.assertEqual(defaults["project_id"], series_project.id)
        self.assertTrue(defaults["has_default_project"])

        wizard = wizard_model.create(
            {
                "action_id": action.id,
                "name": "Task in alternate project",
                "project_id": alternate_project.id,
                "choose_another_project": True,
            }
        )
        wizard.action_create()

        task = action.project_task_ids
        self.assertFalse(action.followup_activity_ids)
        self.assertEqual(task.project_id, alternate_project)
        self.assertEqual(task.name, "Task in alternate project")

    def test_direct_project_task_link_makes_a_point_a_carryover_candidate(self):
        self.series.with_user(self.editor).write({"carryover_policy": "review"})
        source = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": self.meetings[0].id,
                    "name": "Point with a direct Project task",
                    "project_task_ids": [(6, 0, [self.tasks[0].id])],
                }
            )
        )

        candidates = self.env["community.meeting"]._carryover_candidates(self.series, self.meetings[1].start_datetime)

        self.assertIn(source, candidates)
        self.assertFalse(source.review_next_meeting)

    def test_selected_task_is_carried_without_copying_task(self):
        source = self.meetings[0]
        destination = self.meetings[1]
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": source.id,
                    "name": "Continue this work",
                    "followup_kind": "project_task",
                    "agenda_item_id": self.item.id,
                    "project_task_ids": [(6, 0, [self.tasks[0].id])],
                }
            )
        )
        transfer = (
            self.env["community.meeting.carryover"]
            .with_user(self.editor)
            .create(
                {
                    "origin_model": "action",
                    "origin_record_id": action.id,
                    "destination_meeting_id": destination.id,
                    "selected_project_task_ids": [(6, 0, [self.tasks[0].id])],
                }
            )
        )
        transfer.with_user(self.editor).action_accept()

        self.assertEqual(transfer.destination_item_id.project_task_ids, self.tasks[0])
        self.assertEqual(transfer.destination_item_id.meeting_id, destination)
        self.assertEqual(
            self.env["project.task"].search_count([("name", "=", "First linked task")]),
            1,
        )

    def test_project_addon_keeps_core_followup_sufficient_by_default(self):
        meeting = self.env["community.meeting"].with_user(self.editor).create({"name": "Core policy"})
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"name": "Core TODO", "meeting_id": meeting.id, "kind": "todo"})
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "Assigned task",
            }
        )
        self.assertFalse(item.requires_project_task)
        item.write({"disposition": "closed"})
        self.assertEqual(item.project_requirement_snapshot, "core")

    def test_project_task_creation_is_limited_to_project_task_followups(self):
        meeting = self.meetings[0]
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Send an update",
                    "agenda_item_id": self.item.id,
                    "followup_kind": "activity",
                }
            )
        )

        with self.assertRaises(ValidationError):
            action.with_user(self.editor).action_create_project_task()
        wizard = (
            self.env["community.meeting.project.task.wizard"]
            .with_user(self.editor)
            .create(
                {
                    "action_id": action.id,
                    "project_id": self.project.id,
                    "name": "Misconfigured Project task",
                }
            )
        )
        with self.assertRaises(ValidationError):
            wizard.action_create()

    def test_task_writer_without_meeting_access_completes_delegated_actions(self):
        writer = self.env["res.users"].create(
            {
                "name": "Project Task Writer Without Meeting Access",
                "login": "project-task-writer-no-meeting-access",
                "company_id": self.editor.company_id.id,
                "company_ids": [(6, 0, [self.editor.company_id.id])],
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("project.group_project_user").id,
                        ],
                    )
                ],
            }
        )
        denied_writer = self.env["res.users"].create(
            {
                "name": "User Without Project Task Write",
                "login": "project-task-writer-denied",
                "company_id": self.editor.company_id.id,
                "company_ids": [(6, 0, [self.editor.company_id.id])],
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Private delegated Project completion",
                }
            )
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Private delegated point",
                }
            )
        )
        first, second = self.env["project.task"].create(
            [
                {
                    "name": "First delegated task",
                    "project_id": self.project.id,
                    "user_ids": [(4, writer.id)],
                },
                {
                    "name": "Shared delegated task",
                    "project_id": self.project.id,
                    "user_ids": [(4, writer.id)],
                },
            ]
        )
        first_action, shared_action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                [
                    {
                        "meeting_id": meeting.id,
                        "agenda_item_id": item.id,
                        "name": "First action requiring both tasks",
                        "followup_kind": "project_task",
                        "project_task_ids": [(6, 0, [first.id, second.id])],
                    },
                    {
                        "meeting_id": meeting.id,
                        "agenda_item_id": item.id,
                        "name": "Second action sharing one task",
                        "followup_kind": "project_task",
                        "project_task_ids": [(4, second.id)],
                    },
                ]
            )
        )

        with self.assertRaises(AccessError):
            meeting.with_user(writer).check_access("read")
        with self.assertRaises(AccessError):
            first_action.with_user(writer).check_access("read")
        with self.assertRaises(AccessError):
            first.with_user(denied_writer).write({"state": "1_done"})
        self.assertEqual(first_action.state, "open")
        self.assertEqual(shared_action.state, "open")

        first.with_user(writer).write({"state": "1_done"})
        self.assertEqual(first_action.state, "open")
        self.assertEqual(shared_action.state, "open")
        second.with_user(writer).write({"state": "1_done"})
        self.assertEqual(first_action.state, "done")
        self.assertEqual(shared_action.state, "done")

        with self.assertRaises(AccessError):
            meeting.with_user(writer).read(["name"])
        with self.assertRaises(AccessError):
            first_action.with_user(writer).read(["name"])
        second.with_user(writer).write({"state": "01_in_progress"})
        self.assertEqual(first_action.state, "done")
        self.assertEqual(shared_action.state, "done")

    def test_action_changes_keep_hidden_closed_todo_evidence_in_scope(self):
        writer = self.env["res.users"].create(
            {
                "name": "Editor for One Meeting Only",
                "login": "project-link-one-meeting-editor",
                "company_id": self.editor.company_id.id,
                "company_ids": [(6, 0, [self.editor.company_id.id])],
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("community_meetings.group_meeting_editor").id,
                            self.env.ref("project.group_project_user").id,
                        ],
                    )
                ],
            }
        )
        self.series.write({"meeting_todo_requirement": "project"})
        private_meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Hidden meeting with valid Project evidence",
                    "series_id": self.series.id,
                }
            )
        )
        visible_meeting = (
            self.env["community.meeting"]
            .with_user(writer)
            .create(
                {
                    "name": "Visible meeting sharing the point",
                    "series_id": self.series.id,
                }
            )
        )
        private_item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": private_meeting.id,
                    "name": "Private closed TODO",
                    "kind": "todo",
                }
            )
        )
        private_action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": private_meeting.id,
                    "agenda_item_id": private_item.id,
                    "name": "Valid hidden Project action",
                    "responsible_user_id": self.editor.id,
                    "followup_kind": "project_task",
                    "project_task_ids": [(4, self.tasks[0].id)],
                }
            )
        )
        private_item.with_user(self.editor).write({"disposition": "closed"})
        visible_item = (
            self.env["community.meeting.agenda.item"]
            .with_user(writer)
            .sudo()
            .create(
                {
                    "meeting_id": visible_meeting.id,
                    "topic_id": private_item.topic_id.id,
                    "name": "Visible participation of shared topic",
                }
            )
        )

        with self.assertRaises(AccessError):
            private_meeting.with_user(writer).check_access("read")
        visible_action = (
            self.env["community.meeting.action"]
            .with_user(writer)
            .create(
                {
                    "meeting_id": visible_meeting.id,
                    "agenda_item_id": visible_item.id,
                    "name": "Unassigned visible action",
                }
            )
        )
        visible_action.with_user(writer).write({"name": "Edited visible action"})
        visible_action.with_user(writer).unlink()

        with self.assertRaises(ValidationError), self.cr.savepoint():
            private_action.with_user(self.editor).write(
                {
                    "project_task_ids": [(5, 0, 0)],
                }
            )
        self.assertEqual(private_item.disposition, "closed")
        self.assertEqual(private_action.project_task_ids, self.tasks[0])

    def test_delegated_completion_preserves_approved_minutes(self):
        approver = self.env["res.users"].create(
            {
                "name": "Minutes Approver for Project Delegation",
                "login": "project-delegation-minutes-approver",
                "company_id": self.editor.company_id.id,
                "company_ids": [(6, 0, [self.editor.company_id.id])],
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("community_meetings.group_meeting_approver").id,
                        ],
                    )
                ],
            }
        )
        writer = self.env["res.users"].create(
            {
                "name": "Minutes Task Writer without Meeting Access",
                "login": "project-minutes-writer-no-meeting-access",
                "company_id": self.editor.company_id.id,
                "company_ids": [(6, 0, [self.editor.company_id.id])],
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("project.group_project_user").id,
                        ],
                    )
                ],
            }
        )
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create(
                {
                    "name": "Approved minutes with delegated Project follow-up",
                    "start_datetime": "2026-11-15 10:00:00",
                    "reader_user_ids": [(4, approver.id)],
                }
            )
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "name": "Project follow-up point",
                }
            )
        )
        task = self.env["project.task"].create(
            {
                "name": "Task completed after approval",
                "project_id": self.project.id,
                "user_ids": [(4, writer.id)],
            }
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Complete the linked task",
                    "followup_kind": "project_task",
                    "project_task_ids": [(4, task.id)],
                }
            )
        )
        meeting.with_user(self.editor).action_schedule()
        meeting.with_user(self.editor).action_mark_held()
        meeting.with_user(self.editor).action_draft_minutes()
        report_model = self.env["ir.actions.report"]
        with patch.object(
            type(report_model),
            "_render_qweb_pdf",
            return_value=(b"%PDF-1.4\nproject delegation fixture\n", "pdf"),
        ):
            meeting.with_user(approver).action_approve_minutes()
        revision = meeting.approved_revision_id
        snapshot_before = revision.snapshot_json
        pdf_before = revision.pdf_attachment_id.raw

        task.with_user(writer).write({"state": "1_done"})

        self.assertEqual(action.state, "done")
        self.assertEqual(revision.snapshot_json, snapshot_before)
        self.assertEqual(revision.pdf_attachment_id.raw, pdf_before)

    def test_series_project_is_lazy_and_existing_task_can_be_external(self):
        self.editor.write({"groups_id": [(4, self.env.ref("project.group_project_manager").id)]})
        self.series.write({"meeting_project_mode": "series"})
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create({"name": "Series project", "series_id": self.series.id})
        )
        self.assertFalse(self.series.meeting_project_id)
        project = meeting._meeting_project(create=True)
        self.assertTrue(project)
        self.assertEqual(meeting._meeting_project(create=True), project)
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "name": "External task"})
        )
        action = (
            self.env["community.meeting.action"]
            .with_user(self.editor)
            .create(
                {
                    "meeting_id": meeting.id,
                    "agenda_item_id": item.id,
                    "name": "Existing task",
                    "project_task_ids": [(4, self.tasks[0].id)],
                }
            )
        )
        self.assertEqual(action.project_task_ids, self.tasks[0])
        self.series.write({"meeting_task_scope": "configured"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            action.write({"project_task_ids": [(4, self.tasks[1].id)]})

    def test_changing_policy_does_not_retroactively_invalidate_closed_todo(self):
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create({"name": "Snapshot policy", "series_id": self.series.id})
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "name": "Policy TODO", "kind": "todo"})
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "Core assigned task",
            }
        )
        item.write({"disposition": "closed"})
        self.series.write({"meeting_todo_requirement": "project"})
        self.assertFalse(item.requires_project_task)
        item.write({"discussion_notes": "<p>Historical assignment remains valid</p>"})

    def test_required_project_task_must_stay_assigned_and_not_cancelled(self):
        self.series.write({"meeting_todo_requirement": "project"})
        meeting = (
            self.env["community.meeting"]
            .with_user(self.editor)
            .create({"name": "Assigned Project task", "series_id": self.series.id})
        )
        item = (
            self.env["community.meeting.agenda.item"]
            .with_user(self.editor)
            .create({"meeting_id": meeting.id, "name": "TODO", "kind": "todo"})
        )
        task = self.env["project.task"].create(
            {
                "name": "Initially unassigned",
                "project_id": self.project.id,
                "user_ids": [(5, 0, 0)],
            }
        )
        self.env["community.meeting.action"].with_user(self.editor).create(
            {
                "meeting_id": meeting.id,
                "agenda_item_id": item.id,
                "name": "Assigned follow-up",
                "project_task_ids": [(4, task.id)],
            }
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({"disposition": "closed"})
        task.write({"user_ids": [(4, self.editor.id)], "state": "1_canceled"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({"disposition": "closed"})
        task.write({"state": "01_in_progress"})
        item.write({"disposition": "closed"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({"user_ids": [(5, 0, 0)]})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({"state": "1_canceled"})
