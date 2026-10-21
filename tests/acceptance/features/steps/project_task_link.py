"""Browser UI steps for creating and linking a Project task."""

from __future__ import annotations

from uuid import uuid4

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, open_live_meeting
from playwright.sync_api import expect


@given("a meeting has a Project-required follow-up and an alternate project")
def meeting_with_project_followup(context):
    session = context.browser_session
    suffix = uuid4().hex[:8]
    company = session.rpc("res.company", "search_read", [[]], {"fields": ["id"], "limit": 1})[0]
    configured_project = session.rpc(
        "project.project",
        "create",
        [{"name": f"Acceptance configured project {suffix}", "company_id": company["id"]}],
    )
    context.alternate_project_name = f"Acceptance alternate project {suffix}"
    context.alternate_project_id = session.rpc(
        "project.project",
        "create",
        [{"name": context.alternate_project_name, "company_id": company["id"]}],
    )
    series_id = session.rpc(
        "community.meeting.series",
        "create",
        [
            {
                "name": f"Acceptance series {suffix}",
                "meeting_todo_requirement": "project",
                "meeting_project_mode": "series",
                "meeting_task_scope": "any",
                "meeting_project_id": configured_project,
            }
        ],
    )
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(session, f"project link {suffix}")
    context.meeting_id = fixture.meeting_id
    context.agenda_item_id = fixture.item_ids["todo"]
    session.rpc("community.meeting", "write", [[fixture.meeting_id], {"series_id": series_id}])
    context.requires_database_drop = True
    context.followup_name = f"Acceptance follow-up {suffix}"
    open_live_meeting(session, fixture.meeting_id)


@when("I create the follow-up task in the alternate project")
def create_followup_task_in_alternate_project(context):
    card = context.page.locator(f"#agenda-card-{context.agenda_item_id}")
    start_meeting = context.page.get_by_role("button", name="Start Meeting", exact=True)
    if start_meeting.count():
        start_meeting.click()
    expect(context.page.get_by_role("button", name="Finish Meeting", exact=True)).to_be_visible()
    begin_point = card.get_by_role("button", name="Begin point", exact=True)
    if begin_point.count():
        begin_point.click()
    expect(card.get_by_role("button", name="Pause point", exact=True)).to_be_visible()

    card.get_by_role("button", name="Add follow-up", exact=True).click()
    form = card.locator(".o_live_task_form")
    form.get_by_label("Task name", exact=True).fill(context.followup_name)
    form.get_by_label("Follow-up type", exact=True).select_option("project_task")
    form.get_by_role("button", name="Add follow-up", exact=True).click()
    expect(card).to_contain_text("Project task required")
    card.get_by_role("button", name="Create Project task", exact=True).click()

    dialog = context.page.get_by_role("dialog").last
    context.task_dialog = dialog
    dialog.get_by_label("Choose a different project", exact=True).check()
    project_field = dialog.locator('.o_field_widget[name="project_id"] input')
    expect(project_field).to_be_visible()
    project_field.fill(context.alternate_project_name)
    context.page.get_by_role("option", name=context.alternate_project_name, exact=True).click()
    context.task_name = dialog.locator('.o_field_widget[name="name"] input').input_value()
    assert context.task_name, "The Project wizard should prefill the task name."
    dialog.locator('button[name="action_create"]').click()


@then("the task is linked to the meeting follow-up")
def task_is_linked_to_followup(context):
    expect(context.task_dialog).not_to_be_visible()
    actions = context.browser_session.rpc(
        "community.meeting.action",
        "search_read",
        [[("meeting_id", "=", context.meeting_id), ("name", "=", context.followup_name)]],
        {"fields": ["id", "project_task_ids"]},
    )
    assert len(actions) == 1, actions
    tasks = context.browser_session.rpc(
        "project.task",
        "search_read",
        [[("name", "=", context.task_name)]],
        {"fields": ["id", "project_id"]},
    )
    assert len(tasks) == 1, tasks
    assert tasks[0]["project_id"][0] == context.alternate_project_id, tasks
    assert tasks[0]["id"] in actions[0]["project_task_ids"], (actions, tasks)


@given("a Project-required follow-up and an existing task are available")
def project_followup_and_existing_task(context):
    session = context.browser_session
    suffix = uuid4().hex[:8]
    company = session.rpc("res.company", "search_read", [[]], {"fields": ["id"], "limit": 1})[0]
    project_name = f"Acceptance existing-task project {suffix}"
    project_id = session.rpc("project.project", "create", [{"name": project_name, "company_id": company["id"]}])
    context.existing_task_name = f"Acceptance existing task {suffix}"
    context.existing_task_id = session.rpc(
        "project.task",
        "create",
        [{"name": context.existing_task_name, "project_id": project_id}],
    )
    series_id = session.rpc(
        "community.meeting.series",
        "create",
        [
            {
                "name": f"Acceptance existing-task series {suffix}",
                "meeting_todo_requirement": "project",
                "meeting_project_mode": "series",
                "meeting_task_scope": "any",
                "meeting_project_id": project_id,
            }
        ],
    )
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(session, f"existing task {suffix}")
    context.meeting_id = fixture.meeting_id
    context.agenda_item_id = fixture.item_ids["todo"]
    session.rpc("community.meeting", "write", [[fixture.meeting_id], {"series_id": series_id}])
    context.requires_database_drop = True
    context.followup_name = f"Acceptance existing-task follow-up {suffix}"
    open_live_meeting(session, fixture.meeting_id)


@when("I select the existing task in the follow-up wizard")
def select_existing_task(context):
    card = context.page.locator(f"#agenda-card-{context.agenda_item_id}")
    start_meeting = context.page.get_by_role("button", name="Start Meeting", exact=True)
    if start_meeting.count():
        start_meeting.click()
    expect(context.page.get_by_role("button", name="Finish Meeting", exact=True)).to_be_visible()
    begin_point = card.get_by_role("button", name="Begin point", exact=True)
    if begin_point.count():
        begin_point.click()
    expect(card.get_by_role("button", name="Pause point", exact=True)).to_be_visible()
    card.get_by_role("button", name="Add follow-up", exact=True).click()
    form = card.locator(".o_live_task_form")
    form.get_by_label("Task name", exact=True).fill(context.followup_name)
    form.get_by_label("Follow-up type", exact=True).select_option("project_task")
    form.get_by_role("button", name="Add follow-up", exact=True).click()
    expect(card).to_contain_text("Project task required")
    card.get_by_role("button", name="Create Project task", exact=True).click()

    dialog = context.page.get_by_role("dialog").last
    task_field = dialog.locator('.o_field_widget[name="existing_task_id"] input')
    task_field.fill(context.existing_task_name)
    context.page.get_by_role("option", name=context.existing_task_name, exact=True).click()
    with context.page.expect_response(
        lambda response: "/call_button/community.meeting.project.task.wizard/action_create" in response.url
    ):
        dialog.get_by_role("button", name="Create and Link", exact=True).click()


@then("the existing task is linked to the meeting follow-up")
def existing_task_is_linked(context):
    actions = context.browser_session.rpc(
        "community.meeting.action",
        "search_read",
        [[("meeting_id", "=", context.meeting_id), ("name", "=", context.followup_name)]],
        {"fields": ["id", "project_task_ids"]},
    )
    task = context.browser_session.record("project.task", context.existing_task_id, ["project_id"])
    assert len(actions) == 1 and context.existing_task_id in actions[0]["project_task_ids"], actions
    assert task["project_id"], task
