"""Browser UI steps for scheduling a meeting with required details."""

from __future__ import annotations

from behave import given, then, when
from browser_support.meeting import LiveMeetingFixture, assert_meeting_form
from playwright.sync_api import expect


@given("a draft meeting without a date or time")
def draft_meeting_without_datetime(context):
    fixture = LiveMeetingFixture.create_draft_meeting(context.browser_session, "schedule without date")
    context.live_meeting_fixture = fixture
    context.meeting_id = fixture.meeting_id
    context.meeting_name = context.browser_session.record("community.meeting", fixture.meeting_id, ["name"])["name"]
    context.meeting_before_schedule = context.browser_session.record(
        "community.meeting",
        fixture.meeting_id,
        ["name", "state", "start_datetime", "write_date"],
    )
    assert context.meeting_before_schedule["state"] == "draft"
    assert not context.meeting_before_schedule["start_datetime"]
    context.page.goto(
        f"{context.acceptance_config.base_url}/web#model=community.meeting&id={fixture.meeting_id}&view_type=form"
    )
    assert_meeting_form(context.page, context.meeting_name)


@when("I choose Schedule from its meeting form")
def schedule_draft_from_form(context):
    context.page.locator('button[name="action_schedule"]').click()


@then("the form explains that a date and time are required")
def schedule_error_is_visible(context):
    expect(context.page.get_by_role("dialog")).to_contain_text(
        context.browser_session.ui_text("community_meetings", "Set a meeting date and time before scheduling it.")
    )


@then("the meeting remains a draft without a scheduled date")
def meeting_remains_unscheduled(context):
    meeting_after = context.browser_session.record(
        "community.meeting",
        context.meeting_id,
        ["name", "state", "start_datetime", "write_date"],
    )
    assert meeting_after == context.meeting_before_schedule, (
        context.meeting_before_schedule,
        meeting_after,
    )
