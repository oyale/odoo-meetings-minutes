#!/usr/bin/env python3
"""Project browser extension: all core scenarios plus Project-specific behavior."""

import sys
from pathlib import Path
import uuid

from playwright.sync_api import expect

CORE_BROWSER = Path(__file__).resolve().parents[3] / "community_meetings" / "tests" / "browser"
sys.path.insert(0, str(CORE_BROWSER))
from full_meeting_playwright import ACTIONS as CORE_ACTIONS, FullMeetingBrowserChecks, run_suite

PROJECT_ACTIONS = {
    "test_related_followup_preview_links_project_task": [
        "open a promoted follow-up preview",
        "see linked Project task details and open the task",
    ],
    "test_project_task_can_use_alternate_project": [
        "configure Project requirement",
        "choose a different project for a new task",
    ],
    "test_convert_project_todo_to_project_task": [
        "create a private to-do follow-up",
        "convert it to a Project task container",
    ],
}


class ProjectMeetingBrowserChecks(FullMeetingBrowserChecks):
    def test_related_followup_preview_links_project_task(self):
        discussion_item = self.item_ids["discussion"]
        topic_id = self.record(
            "community.meeting.agenda.item", discussion_item, ["topic_id"]
        )["topic_id"][0]
        user_id = self.current_user()
        company_id = self.record(
            "community.meeting", self.meeting_id, ["company_id"]
        )["company_id"][0]
        project_name = "Related follow-up project " + uuid.uuid4().hex[:6]
        project_id = self.rpc(
            "project.project", "create",
            [{"name": project_name, "company_id": company_id}],
        )
        self.addCleanup(self.rpc, "project.project", "unlink", [[project_id]])
        task_name = "Linked source task " + uuid.uuid4().hex[:6]
        task_id = self.rpc(
            "project.task", "create",
            [{
                "name": task_name,
                "project_id": project_id,
                "user_ids": [(6, 0, [user_id])],
            }],
        )
        self.addCleanup(self.rpc, "project.task", "unlink", [[task_id]])
        outside_meeting_id = self.rpc(
            "community.meeting", "create",
            [{"name": "Follow-up destination " + uuid.uuid4().hex[:6]}],
        )
        self.addCleanup(
            self.rpc, "community.meeting", "action_cancel", [[outside_meeting_id]]
        )
        outside_type = self.rpc(
            "community.meeting.agenda.type", "search",
            [[("behavior", "=", "discussion"), ("active", "=", True)]],
            {"limit": 1},
        )[0]
        outside_item = self.rpc(
            "community.meeting.agenda.item", "create",
            [{
                "meeting_id": outside_meeting_id,
                "name": "Promoted task point",
                "kind": "discussion",
                "agenda_type_id": outside_type,
            }],
        )
        action_id = self.rpc(
            "community.meeting.action", "create",
            [{
                "meeting_id": outside_meeting_id,
                "agenda_item_id": outside_item,
                "name": "Promoted task follow-up",
                "description": "Context from the original follow-up.",
                "followup_kind": "project_task",
                "responsible_user_ids": [(6, 0, [user_id])],
                "project_task_ids": [(6, 0, [task_id])],
            }],
        )
        self.rpc(
            "community.meeting.topic", "write",
            [[topic_id], {"origin_action_id": action_id}],
        )

        self.open_live(self.meeting_id)
        card = self.card("discussion")
        chip = card.locator(
            ".o_live_related_point", has_text="Promoted task follow-up"
        )
        chip.click()
        preview = card.get_by_role(
            "region", name="Follow-up details: Promoted task follow-up"
        )
        expect(preview).to_contain_text(task_name)
        expect(preview).to_contain_text(project_name)
        expect(preview.get_by_role("button", name="Open Project task")).to_be_visible()
        preview.get_by_role("button", name="Open Project task").click()
        dialog = self.page.locator(".o_dialog .o_form_view")
        expect(self.page.get_by_text(task_name, exact=True)).to_be_visible()

    def test_project_task_can_use_alternate_project(self):
        fields = self.rpc(
            "community.meeting.series", "fields_get", [], {"attributes": ["type"]}
        )
        self.assertIn("meeting_todo_requirement", fields, "Install community_meetings_project for this suite")
        series = self.rpc(
            "community.meeting.series",
            "create",
            [
                {
                    "name": "Project policy " + uuid.uuid4().hex[:8],
                    "meeting_todo_requirement": "project",
                    "meeting_project_mode": "series",
                    "meeting_task_scope": "any",
                }
            ],
        )
        self.retained.append({"model": "community.meeting.series", "id": series})
        meeting_company = self.record(
            "community.meeting", self.meeting_id, ["company_id"]
        )["company_id"][0]
        configured_project = self.rpc(
            "project.project", "create", [{
                "name": "Configured series project " + uuid.uuid4().hex[:6],
                "company_id": meeting_company,
            }]
        )
        alternate_project_name = "Alternate live task project " + uuid.uuid4().hex[:6]
        alternate_project = self.rpc(
            "project.project", "create", [{
                "name": alternate_project_name,
                "company_id": meeting_company,
            }]
        )
        self.rpc(
            "community.meeting.series", "write",
            [[series], {"meeting_project_id": configured_project}],
        )
        self.rpc(
            "community.meeting", "write", [[self.meeting_id], {"series_id": series}]
        )
        self.open_live(self.meeting_id)
        card = self.card("todo")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        card.get_by_label("Task name", exact=True).fill(
            "Assigned follow-up with Project"
        )
        card.get_by_label("Follow-up type", exact=True).select_option("project_task")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        expect(self.outcome("todo")).to_have_text("Project task required")
        expect(card.get_by_role("button", name="Done")).to_be_disabled()
        card.get_by_role("button", name="Create Project task").click()
        dialog = self.page.get_by_role("dialog").last
        expect(dialog.get_by_label("Choose a different project")).to_be_visible()
        expect(
            dialog.locator('.o_field_widget[name="project_id"] input')
        ).not_to_be_visible()
        dialog.get_by_label("Choose a different project").check()
        project_field = dialog.locator('.o_field_widget[name="project_id"] input')
        expect(project_field).to_be_visible()
        project_field.fill(alternate_project_name)
        self.page.get_by_role("option", name=alternate_project_name, exact=True).click()
        dialog.locator('button[name="action_create"]').click()
        expect(dialog).not_to_be_visible()
        created_tasks = self.rpc(
            "project.task", "search_read",
            [[("project_id", "=", alternate_project)]],
            {"fields": ["name", "project_id"]},
        )
        linked_actions = self.rpc(
            "community.meeting.action", "search_read",
            [[("meeting_id", "=", self.meeting_id)]],
            {"fields": ["name", "project_task_ids"]},
        )
        self.assertTrue(
            created_tasks,
            "No alternate-project task. Linked actions: %r" % linked_actions,
        )
        self.assertEqual(created_tasks[0]["project_id"][0], alternate_project)
        linked_task_ids = {
            task_id
            for action in linked_actions
            for task_id in action["project_task_ids"]
        }
        self.assertTrue(set(task["id"] for task in created_tasks) & linked_task_ids)
        expect(card.get_by_role("button", name="Done")).to_be_enabled()
        card.get_by_role("button", name="Done").click()
        expect(self.outcome("todo")).to_have_text("Resolved")

    def test_convert_project_todo_to_project_task(self):
        self.open_live(self.meeting_id)
        card = self.card("discussion")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        form = card.locator(".o_live_task_form")
        form.get_by_label("Task name").fill("Private to-do follow-up")
        form.get_by_label("Follow-up type").select_option("project_todo")
        form.get_by_role("button", name="Add follow-up").click()
        row = card.locator(".o_live_followup_task").last
        expect(row).to_be_visible()
        todo = self.wait_action_record("Private to-do follow-up")
        self.assertEqual(todo["followup_kind"], "project_todo")
        before = self.record(
            "community.meeting.action", todo["id"],
            ["project_task_ids", "followup_activity_id"],
        )
        self.assertEqual(len(before["project_task_ids"]), 1)
        self.assertFalse(before["followup_activity_id"])

        convert = row.locator(".o_live_followup_convert")
        expect(convert).to_have_count(1)
        convert.get_by_role("button", name="Convert follow-up").click()
        self.page.get_by_role("button", name="Project task", exact=True).click()
        expect(row.locator(".o_live_followup_badges .badge").first).to_have_text("Project task")
        converted = self.wait_action_record("Private to-do follow-up")
        self.assertEqual(converted["followup_kind"], "project_task")
        after = self.record(
            "community.meeting.action", todo["id"],
            ["project_task_ids", "followup_activity_id"],
        )
        self.assertEqual(after["project_task_ids"], [])
        self.assertFalse(after["followup_activity_id"])



if __name__ == "__main__":
    run_suite(ProjectMeetingBrowserChecks, {**CORE_ACTIONS, **PROJECT_ACTIONS})
