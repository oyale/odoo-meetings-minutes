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
            {"name": "First linked task", "project_id": cls.project.id},
            {"name": "Second linked task", "project_id": cls.project.id},
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
