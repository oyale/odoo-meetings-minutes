"""Browser UI steps for previewing minutes before they are ready."""

from __future__ import annotations

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, assert_meeting_form
from playwright.sync_api import expect


@given("a scheduled meeting that is not ready for minutes preview")
def scheduled_meeting_is_not_ready(context):
    fixture = LiveMeetingFixture.create_scheduled_live_meeting(context.browser_session, "unavailable preview")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    context.meeting_name = context.browser_session.record("community.meeting", fixture.meeting_id, ["name"])["name"]
    context.preview_meeting_before = context.browser_session.record(
        "community.meeting", fixture.meeting_id, ["name", "state", "write_date"]
    )
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={fixture.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)


@when("I attempt to preview its minutes")
def attempt_minutes_preview(context):
    try:
        context.browser_session.rpc("community.meeting", "action_preview_minutes", [[context.meeting_id]])
    except AssertionError as error:
        context.preview_action_error = str(error)
    else:
        raise AssertionError("The server allowed previewing a scheduled meeting")


@then("the preview action is unavailable in the meeting form")
def preview_action_is_unavailable(context):
    expect(
        context.page.get_by_role(
            "button", name=context.browser_session.ui_text("community_meetings", "Preview Minutes"), exact=True
        )
    ).to_have_count(0)


@then("the server explains that the meeting must be held first")
def server_explains_preview_requirement(context):
    assert "Minutes preview is only available for held meetings or draft minutes." in (context.preview_action_error)


@then("the meeting remains unchanged")
def scheduled_meeting_remains_unchanged(context):
    meeting_after = context.browser_session.record(
        "community.meeting", context.meeting_id, ["name", "state", "write_date"]
    )
    assert meeting_after == context.preview_meeting_before, (
        context.preview_meeting_before,
        meeting_after,
    )
