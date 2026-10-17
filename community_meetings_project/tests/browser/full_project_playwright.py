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
    "test_project_task_can_use_alternate_project": [
        "configure Project requirement",
        "choose a different project for a new task",
    ],
}


class ProjectMeetingBrowserChecks(FullMeetingBrowserChecks):
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
        card.get_by_label("Follow-up type", exact=True).select_option("task")
        card.get_by_role("button", name="Add follow-up", exact=True).click()
        expect(self.outcome("todo")).to_have_text("Project task required")
        expect(card.get_by_role("button", name="Done")).to_be_disabled()
        card.get_by_role("button", name="Create Project task").click()
        dialog = self.page.get_by_role("dialog").last
        expect(dialog.get_by_label("Choose a different project")).to_be_visible()
        expect(dialog.locator('.o_field_widget[name="project_id"]')).not_to_be_visible()
        dialog.get_by_label("Choose a different project").check()
        project_field = dialog.locator('.o_field_widget[name="project_id"] input')
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



if __name__ == "__main__":
    run_suite(ProjectMeetingBrowserChecks, {**CORE_ACTIONS, **PROJECT_ACTIONS})
