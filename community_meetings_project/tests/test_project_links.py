from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommunityMeetingProjectLinks(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.editor = cls.env["res.users"].create({
            "name": "Meeting Project Editor",
            "login": "meeting-project-link-test",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("community_meetings.group_meeting_editor").id,
                cls.env.ref("project.group_project_user").id,
            ])],
        })
        cls.project = cls.env["project.project"].create({"name": "Meeting Link Test Project"})
        cls.tasks = cls.env["project.task"].create([
            {"name": "First linked task", "project_id": cls.project.id, "user_ids": [(4, cls.editor.id)]},
            {"name": "Second linked task", "project_id": cls.project.id, "user_ids": [(4, cls.editor.id)]},
        ])
        cls.series = cls.env["community.meeting.series"].with_user(cls.editor).create({
            "name": "Project Link Test Series",
        })
        cls.meetings = cls.env["community.meeting"].with_user(cls.editor).create([
            {"name": "Source project link meeting", "series_id": cls.series.id, "start_datetime": "2026-11-01 10:00:00"},
            {"name": "Destination project link meeting", "series_id": cls.series.id, "start_datetime": "2026-11-08 10:00:00"},
        ])

    def test_multiple_task_links_and_reverse_navigation(self):
        meeting = self.meetings[0]
        agenda = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Linked topic",
            "project_task_ids": [(6, 0, self.tasks.ids)],
        })
        resolution = self.env["community.meeting.resolution"].with_user(self.editor).create({
            "meeting_id": meeting.id, "title": "Linked resolution",
            "project_task_ids": [(6, 0, [self.tasks[0].id])],
        })
        action = self.env["community.meeting.action"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Linked action",
            "project_task_ids": [(6, 0, [self.tasks[0].id])],
        })

        self.assertEqual(set(agenda.with_user(self.editor).project_task_ids.ids), set(self.tasks.ids))
        self.assertEqual(resolution.with_user(self.editor).project_task_ids, self.tasks[0])
        self.assertEqual(action.with_user(self.editor).project_task_ids, self.tasks[0])
        reverse = self.tasks[0].with_user(self.editor).action_view_community_meeting_links()
        self.assertEqual(reverse["res_model"], "community.meeting.project.task.links")
        self.assertEqual(reverse["context"]["default_agenda_item_ids"][0][2], agenda.ids)
        self.assertEqual(reverse["context"]["default_resolution_ids"][0][2], resolution.ids)
        self.assertEqual(reverse["context"]["default_action_ids"][0][2], action.ids)

    def test_todo_cannot_close_without_project_task_on_followup_action(self):
        self.series.write({'meeting_todo_requirement': 'project'})
        meeting = self.meetings[0]
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": meeting.id, "name": "Implement the proposal", "kind": "todo",
        })
        action = self.env["community.meeting.action"].with_user(self.editor).create({
            "meeting_id": meeting.id, "agenda_item_id": item.id, "name": "Implement proposal",
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.with_user(self.editor).write({"disposition": "closed"})

        action.with_user(self.editor).write({"project_task_ids": [(4, self.tasks[0].id)]})
        item.with_user(self.editor).write({"disposition": "closed"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.tasks[0].unlink()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            action.with_user(self.editor).write({"project_task_ids": [(5, 0, 0)]})

    def test_non_todo_points_do_not_require_project_tasks_to_close(self):
        item = self.env["community.meeting.agenda.item"].with_user(self.editor).create({
            "meeting_id": self.meetings[0].id, "name": "Resolve the discussion", "kind": "discussion",
        })
        item.with_user(self.editor).write({"disposition": "closed"})
        self.assertEqual(item.disposition, "closed")

    def test_selected_task_is_carried_without_copying_task(self):
        source = self.meetings[0]
        destination = self.meetings[1]
        action = self.env["community.meeting.action"].with_user(self.editor).create({
            "meeting_id": source.id,
            "name": "Continue this work",
            "project_task_ids": [(6, 0, [self.tasks[0].id])],
        })
        transfer = self.env["community.meeting.carryover"].with_user(self.editor).create({
            "origin_model": "action",
            "origin_record_id": action.id,
            "destination_meeting_id": destination.id,
            "selected_project_task_ids": [(6, 0, [self.tasks[0].id])],
        })
        transfer.with_user(self.editor).action_accept()

        self.assertEqual(transfer.destination_item_id.project_task_ids, self.tasks[0])
        self.assertEqual(transfer.destination_item_id.meeting_id, destination)
        self.assertEqual(self.env["project.task"].search_count([("name", "=", "First linked task")]), 1)

    def test_project_addon_keeps_core_followup_sufficient_by_default(self):
        meeting = self.env['community.meeting'].with_user(self.editor).create({'name': 'Core policy'})
        item = self.env['community.meeting.agenda.item'].with_user(self.editor).create({'name': 'Core TODO', 'meeting_id': meeting.id, 'kind': 'todo'})
        self.env['community.meeting.action'].with_user(self.editor).create({'meeting_id': meeting.id, 'agenda_item_id': item.id, 'name': 'Assigned task'})
        self.assertFalse(item.requires_project_task)
        item.write({'disposition': 'closed'})
        self.assertEqual(item.project_requirement_snapshot, 'core')

    def test_series_project_is_lazy_and_existing_task_can_be_external(self):
        self.editor.write({'groups_id': [(4, self.env.ref('project.group_project_manager').id)]})
        self.series.write({'meeting_project_mode': 'series'})
        meeting = self.env['community.meeting'].with_user(self.editor).create({'name': 'Series project', 'series_id': self.series.id})
        self.assertFalse(self.series.meeting_project_id)
        project = meeting._meeting_project(create=True)
        self.assertTrue(project)
        self.assertEqual(meeting._meeting_project(create=True), project)
        item = self.env['community.meeting.agenda.item'].with_user(self.editor).create({'meeting_id': meeting.id, 'name': 'External task'})
        action = self.env['community.meeting.action'].with_user(self.editor).create({'meeting_id': meeting.id, 'agenda_item_id': item.id, 'name': 'Existing task', 'project_task_ids': [(4, self.tasks[0].id)]})
        self.assertEqual(action.project_task_ids, self.tasks[0])
        self.series.write({'meeting_task_scope': 'configured'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            action.write({'project_task_ids': [(4, self.tasks[1].id)]})

    def test_changing_policy_does_not_retroactively_invalidate_closed_todo(self):
        meeting = self.env['community.meeting'].with_user(self.editor).create({'name': 'Snapshot policy', 'series_id': self.series.id})
        item = self.env['community.meeting.agenda.item'].with_user(self.editor).create({'meeting_id': meeting.id, 'name': 'Policy TODO', 'kind': 'todo'})
        self.env['community.meeting.action'].with_user(self.editor).create({'meeting_id': meeting.id, 'agenda_item_id': item.id, 'name': 'Core assigned task'})
        item.write({'disposition': 'closed'})
        self.series.write({'meeting_todo_requirement': 'project'})
        self.assertFalse(item.requires_project_task)
        item.write({'discussion_notes': '<p>Historical assignment remains valid</p>'})

    def test_required_project_task_must_stay_assigned_and_not_cancelled(self):
        self.series.write({'meeting_todo_requirement': 'project'})
        meeting = self.env['community.meeting'].with_user(self.editor).create({'name': 'Assigned Project task', 'series_id': self.series.id})
        item = self.env['community.meeting.agenda.item'].with_user(self.editor).create({'meeting_id': meeting.id, 'name': 'TODO', 'kind': 'todo'})
        task = self.env['project.task'].create({'name': 'Initially unassigned', 'project_id': self.project.id, 'user_ids': [(5, 0, 0)]})
        self.env['community.meeting.action'].with_user(self.editor).create({'meeting_id': meeting.id, 'agenda_item_id': item.id, 'name': 'Assigned follow-up', 'project_task_ids': [(4, task.id)]})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({'disposition': 'closed'})
        task.write({'user_ids': [(4, self.editor.id)], 'state': '1_canceled'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            item.write({'disposition': 'closed'})
        task.write({'state': '01_in_progress'})
        item.write({'disposition': 'closed'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({'user_ids': [(5, 0, 0)]})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            task.write({'state': '1_canceled'})
