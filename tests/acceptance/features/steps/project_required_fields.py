"""Browser UI steps for the required alternate-project choice."""

from __future__ import annotations

from uuid import uuid4

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, open_live_meeting
from playwright.sync_api import expect


@given("a project-required follow-up has a configured project")
def project_required_followup(context):
    session = context.browser_session
    suffix = uuid4().hex[:8]
    company = session.rpc("res.company", "search_read", [[]], {"fields": ["id"], "limit": 1})[0]
    project_id = session.rpc(
        "project.project",
        "create",
        [{"name": f"Acceptance project {suffix}", "company_id": company["id"]}],
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
                "meeting_project_id": project_id,
            }
        ],
    )
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(session, "project task validation")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    session.rpc("community.meeting", "write", [[fixture.meeting_id], {"series_id": series_id}])
    context.requires_database_drop = True
    context.project_followup_name = f"Acceptance follow-up {suffix}"
    open_live_meeting(session, fixture.meeting_id)


@when("I choose another project but leave it empty")
def choose_alternate_project_without_selection(context):
    todo_item_id = context.live_meeting_fixture.item_ids["todo"]
    card = context.page.locator(f"#agenda-card-{todo_item_id}")
    expand_button = card.locator(".o_live_expand")
    if expand_button.get_attribute("aria-expanded") == "false":
        expand_button.click()
    start_meeting = context.page.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Start Meeting'), exact=True)
    if start_meeting.count():
        start_meeting.click()
    expect(context.page.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Finish Meeting'), exact=True)).to_be_visible()
    begin_point = card.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Begin point'), exact=True)
    if begin_point.count():
        begin_point.click()
    expect(card.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Pause point'), exact=True)).to_be_visible()
    card.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Add follow-up'), exact=True).click()
    form = card.locator(".o_live_task_form")
    form.get_by_label(context.browser_session.ui_text('community_meetings', 'Task name'), exact=True).fill(context.project_followup_name)
    form.get_by_label(context.browser_session.ui_text('community_meetings', 'Follow-up type'), exact=True).select_option("project_task")
    form.get_by_role("button", name=context.browser_session.ui_text('community_meetings', 'Add follow-up'), exact=True).click()
    expect(card).to_contain_text(context.browser_session.ui_text('community_meetings_project', 'Project task required'))
    card.get_by_role("button", name=context.browser_session.ui_text('community_meetings_project', 'Create Project task'), exact=True).click()
    dialog = context.page.get_by_role("dialog").last
    dialog.get_by_label(context.browser_session.ui_text('community_meetings_project', 'Choose a different project'), exact=True).check()
    context.project_task_name = dialog.locator('.o_field_widget[name="name"] input').input_value()
    assert context.project_task_name, "The wizard should prefill the new task name."
    dialog.get_by_role("button", name=context.browser_session.ui_text('community_meetings_project', 'Create and Link'), exact=True).click()


@then("the project-required error appears and no task is linked")
def project_required_error_without_link(context):
    expect(context.page.get_by_text(context.browser_session.ui_text('community_meetings_project', 'Choose the project for this task.'), exact=True)).to_be_visible()
    actions = context.browser_session.rpc(
        "community.meeting.action",
        "search_read",
        [[("meeting_id", "=", context.meeting_id), ("name", "=", context.project_followup_name)]],
        {"fields": ["id", "project_task_ids"]},
    )
    assert len(actions) == 1, actions
    assert actions[0]["project_task_ids"] == [], actions
    tasks = context.browser_session.rpc(
        "project.task",
        "search_read",
        [[("name", "=", context.project_task_name)]],
        {"fields": ["id"]},
    )
    assert tasks == [], tasks
